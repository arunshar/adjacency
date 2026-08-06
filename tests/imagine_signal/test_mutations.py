"""Controlled mutation planning and post-generation validation tests."""

from __future__ import annotations

import pytest

from adjacency.imagine_signal.canonical import content_sha256
from adjacency.imagine_signal.contracts import LockedAttribute
from adjacency.imagine_signal.mutations import (
    family_hash,
    plan_controlled_mutations,
    validate_controlled_family,
)

pytestmark = pytest.mark.unit

SV = "1"
H0 = "0" * 64


def make_plan(**updates):
    values = {
        "schema_version": SV,
        "tenant_id": "tenant",
        "family_id": "family",
        "campaign_id": "campaign",
        "root_asset_id": "root",
        "parent_asset_id": "root",
        "axis": "background_tone",
        "levels": ("warm", "cool"),
        "locked_attributes": (LockedAttribute(schema_version=SV, name="logo", value_sha256=H0),),
        "prompt_template_version": "v1",
        "prompt_template": "Keep all locks; set {axis} to {level}.",
    }
    values.update(updates)
    return plan_controlled_mutations(**values)


def test_planner_produces_deterministic_one_axis_specs_without_raw_prompts():
    first = make_plan()
    second = make_plan()
    assert first == second
    assert len(first) == 2
    assert {item.axis for item in first} == {"background_tone"}
    assert {item.level for item in first} == {"warm", "cool"}
    assert first[0].prompt_hash == content_sha256(
        {"prompt": "Keep all locks; set background_tone to warm."}
    )
    assert family_hash(first) == family_hash(tuple(reversed(first)))


@pytest.mark.parametrize("levels", [("one",), ("a", "b", "c", "d", "e")])
def test_planner_rejects_family_sizes_outside_two_to_four(levels):
    with pytest.raises(ValueError, match="two to four"):
        make_plan(levels=levels)


def test_planner_rejects_blank_and_duplicate_levels_or_axis():
    with pytest.raises(ValueError, match="non-empty"):
        make_plan(levels=("warm", ""))
    with pytest.raises(ValueError, match="unique"):
        make_plan(levels=("warm", "warm"))
    with pytest.raises(ValueError, match="axis must be non-empty"):
        make_plan(axis="")


@pytest.mark.parametrize(
    "template",
    [
        "set {other}",
        "set {axis!r} to {level}",
        "set {axis:10} to {level}",
        "set {axis} only",
        "bad {",
    ],
)
def test_planner_rejects_unsafe_or_incomplete_prompt_templates(template):
    with pytest.raises(ValueError, match="prompt template"):
        make_plan(prompt_template=template)


def test_family_hash_rejects_empty_input():
    with pytest.raises(ValueError, match="empty"):
        family_hash(())


def test_validator_accepts_complete_controlled_observations():
    plan = make_plan()
    changed = {item.mutation_id: (item.axis,) for item in plan}
    locks = {item.mutation_id: {"logo": H0} for item in plan}
    result = validate_controlled_family(
        plan,
        observed_changes=changed,
        observed_locked_hashes=locks,
    )
    assert result.passed
    assert bool(result)
    assert result.codes == ()


def test_validator_rejects_an_empty_or_single_member_family():
    empty = validate_controlled_family(())
    assert not empty
    assert empty.codes == ("EMPTY_FAMILY",)
    single = validate_controlled_family(make_plan()[:1])
    assert not single
    assert "FAMILY_SIZE_INVALID" in single.codes


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "2"),
        ("tenant_id", "other"),
        ("family_id", "other"),
        ("campaign_id", "other"),
        ("root_asset_id", "other"),
        ("parent_asset_id", "other"),
        ("axis", "lighting"),
        ("prompt_template_version", "v2"),
    ],
)
def test_validator_rejects_every_family_identity_drift(field, value):
    plan = list(make_plan())
    plan[1] = plan[1].model_copy(update={field: value})
    result = validate_controlled_family(tuple(plan))
    assert not result
    assert "FAMILY_MISMATCH" in result.codes
    assert field in " ".join(result.details)


def test_validator_reports_multiple_family_mismatches_under_one_stable_code():
    plan = list(make_plan())
    plan[1] = plan[1].model_copy(update={"tenant_id": "other", "campaign_id": "other"})
    result = validate_controlled_family(tuple(plan))
    assert result.codes.count("FAMILY_MISMATCH") == 1
    assert len(result.details) == 2


def test_validator_rejects_lock_declaration_duplicate_id_and_duplicate_level():
    plan = list(make_plan())
    different_lock = LockedAttribute(
        schema_version=SV,
        name="logo",
        value_sha256="1" * 64,
    )
    plan[1] = plan[1].model_copy(
        update={
            "locked_attributes": (different_lock,),
            "mutation_id": plan[0].mutation_id,
            "level": plan[0].level,
        }
    )
    result = validate_controlled_family(tuple(plan))
    assert {
        "LOCK_DECLARATION_DRIFT",
        "DUPLICATE_MUTATION_ID",
        "DUPLICATE_LEVEL",
    }.issubset(result.codes)


def test_validator_rejects_missing_or_uncontrolled_change_observations():
    plan = make_plan()
    result = validate_controlled_family(
        plan,
        observed_changes={plan[0].mutation_id: ("lighting", "background_tone")},
    )
    assert "UNCONTROLLED_MUTATION" in result.codes
    assert "OBSERVATION_MISSING" in result.codes


def test_validator_rejects_missing_or_drifted_lock_observations():
    plan = make_plan()
    result = validate_controlled_family(
        plan,
        observed_locked_hashes={plan[0].mutation_id: {"logo": "1" * 64}},
    )
    assert "LOCKED_ATTRIBUTE_DRIFT" in result.codes
    assert "LOCK_OBSERVATION_MISSING" in result.codes
