"""Deterministic planning and validation for one-atom creative mutations."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from string import Formatter

from adjacency.imagine_signal.canonical import content_sha256
from adjacency.imagine_signal.contracts import LockedAttribute, MutationSpec


@dataclass(frozen=True, slots=True)
class MutationValidation:
    """Machine-readable result for a controlled-family validation."""

    passed: bool
    codes: tuple[str, ...] = ()
    details: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.passed


def _add_issue(
    codes: list[str],
    details: list[str],
    code: str,
    detail: str,
) -> None:
    if code not in codes:
        codes.append(code)
    details.append(detail)


def family_hash(mutations: Sequence[MutationSpec]) -> str:
    """Hash a family independently of caller-provided sequence order."""

    if not mutations:
        raise ValueError("cannot hash an empty mutation family")
    return content_sha256(
        {
            "mutation_hashes": sorted(mutation.mutation_hash for mutation in mutations),
        }
    )


def plan_controlled_mutations(
    *,
    schema_version: str,
    tenant_id: str,
    family_id: str,
    campaign_id: str,
    root_asset_id: str,
    parent_asset_id: str,
    axis: str,
    levels: tuple[str, ...],
    locked_attributes: tuple[LockedAttribute, ...],
    prompt_template_version: str,
    prompt_template: str,
) -> tuple[MutationSpec, ...]:
    """Compile two to four levels into deterministic one-axis mutation specs.

    The prompt template may reference only ``{axis}`` and ``{level}``. Raw prompts are
    not retained in the contracts. Only their canonical hashes cross the boundary.
    """

    if not 2 <= len(levels) <= 4:
        raise ValueError("a controlled family requires two to four mutation levels")
    if any(not level for level in levels):
        raise ValueError("mutation levels must be non-empty")
    if len(levels) != len(set(levels)):
        raise ValueError("mutation levels must be unique")
    if not axis:
        raise ValueError("mutation axis must be non-empty")
    parsed_fields = []
    try:
        parsed_template = tuple(Formatter().parse(prompt_template))
    except ValueError as exc:
        raise ValueError("prompt template is malformed") from exc
    for _, field_name, format_spec, conversion in parsed_template:
        if field_name is None:
            continue
        parsed_fields.append(field_name)
        if field_name not in {"axis", "level"} or format_spec or conversion:
            raise ValueError("prompt template may reference only plain axis and level fields")
    if "level" not in parsed_fields:
        raise ValueError("prompt template must reference the mutation level")
    ordered_locks = tuple(sorted(locked_attributes, key=lambda item: item.name))
    planned: list[MutationSpec] = []
    for level in levels:
        prompt = prompt_template.format(axis=axis, level=level)
        prompt_hash = content_sha256({"prompt": prompt})
        mutation_id = content_sha256(
            {
                "tenant_id": tenant_id,
                "family_id": family_id,
                "campaign_id": campaign_id,
                "root_asset_id": root_asset_id,
                "parent_asset_id": parent_asset_id,
                "axis": axis,
                "level": level,
                "locked_attributes": [item.model_dump(mode="json") for item in ordered_locks],
                "prompt_template_version": prompt_template_version,
                "prompt_hash": prompt_hash,
            }
        )
        planned.append(
            MutationSpec(
                schema_version=schema_version,
                tenant_id=tenant_id,
                mutation_id=mutation_id,
                family_id=family_id,
                campaign_id=campaign_id,
                root_asset_id=root_asset_id,
                parent_asset_id=parent_asset_id,
                axis=axis,
                level=level,
                locked_attributes=ordered_locks,
                prompt_template_version=prompt_template_version,
                prompt_hash=prompt_hash,
            )
        )
    return tuple(planned)


def validate_controlled_family(
    mutations: Sequence[MutationSpec],
    *,
    observed_changes: Mapping[str, Collection[str]] | None = None,
    observed_locked_hashes: Mapping[str, Mapping[str, str]] | None = None,
) -> MutationValidation:
    """Validate declaration consistency and optional post-generation observations.

    When observations are supplied, each output must change exactly its declared axis.
    Every declared lock must retain its expected digest. Missing observations fail
    closed because they cannot prove a controlled mutation.
    """

    if not mutations:
        return MutationValidation(
            passed=False,
            codes=("EMPTY_FAMILY",),
            details=("the mutation family is empty",),
        )

    codes: list[str] = []
    details: list[str] = []
    first = mutations[0]
    if not 2 <= len(mutations) <= 4:
        _add_issue(
            codes,
            details,
            "FAMILY_SIZE_INVALID",
            "a controlled family requires two to four mutation levels",
        )
    common_fields = (
        "schema_version",
        "tenant_id",
        "family_id",
        "campaign_id",
        "root_asset_id",
        "parent_asset_id",
        "axis",
        "prompt_template_version",
    )
    for mutation in mutations[1:]:
        for field_name in common_fields:
            if getattr(mutation, field_name) != getattr(first, field_name):
                _add_issue(
                    codes,
                    details,
                    "FAMILY_MISMATCH",
                    f"mutation {mutation.mutation_id} differs on {field_name}",
                )
        if mutation.locked_attributes != first.locked_attributes:
            _add_issue(
                codes,
                details,
                "LOCK_DECLARATION_DRIFT",
                f"mutation {mutation.mutation_id} declares different locked attributes",
            )

    mutation_ids = tuple(mutation.mutation_id for mutation in mutations)
    levels = tuple(mutation.level for mutation in mutations)
    if len(mutation_ids) != len(set(mutation_ids)):
        _add_issue(codes, details, "DUPLICATE_MUTATION_ID", "mutation ids must be unique")
    if len(levels) != len(set(levels)):
        _add_issue(codes, details, "DUPLICATE_LEVEL", "mutation levels must be unique")

    if observed_changes is not None:
        for mutation in mutations:
            actual = observed_changes.get(mutation.mutation_id)
            if actual is None:
                _add_issue(
                    codes,
                    details,
                    "OBSERVATION_MISSING",
                    f"no changed-attribute observation for {mutation.mutation_id}",
                )
                continue
            actual_set = frozenset(actual)
            expected = frozenset({mutation.axis})
            if actual_set != expected:
                _add_issue(
                    codes,
                    details,
                    "UNCONTROLLED_MUTATION",
                    (
                        f"mutation {mutation.mutation_id} changed {sorted(actual_set)}; "
                        f"expected only {mutation.axis!r}"
                    ),
                )

    if observed_locked_hashes is not None:
        for mutation in mutations:
            actual_locks = observed_locked_hashes.get(mutation.mutation_id)
            if actual_locks is None:
                _add_issue(
                    codes,
                    details,
                    "LOCK_OBSERVATION_MISSING",
                    f"no locked-attribute observation for {mutation.mutation_id}",
                )
                continue
            expected_locks = {
                locked.name: locked.value_sha256 for locked in mutation.locked_attributes
            }
            if dict(actual_locks) != expected_locks:
                _add_issue(
                    codes,
                    details,
                    "LOCKED_ATTRIBUTE_DRIFT",
                    f"mutation {mutation.mutation_id} changed a locked attribute",
                )

    return MutationValidation(
        passed=not codes,
        codes=tuple(codes),
        details=tuple(details),
    )
