"""The fail-closed gates. Seven pure functions, no model in the loop.

Every gate is a total function over already-computed structures. None of them calls a
model, touches the network, or reads a clock it was not handed. That is the point: a
language model produces a verdict, and then a set of predicates that cannot be argued
with decides whether that verdict is admissible.

Fail-closed means every failure resolves toward *not serving an ad*, never toward
serving one. `REVIEW` is a fail-closed outcome, not a neutral one: nothing is served
while an item sits in review, and a human is asked to adjudicate.

    G0  source-span grounding   compile time, on the PolicySpec
    G1  evidence grounding      per verdict
    G2  clause existence        per verdict
    G3  monotonicity            per policy revision
    G4  severity coherence      per verdict
    G5  budget                  per run
    G6  abstention floor        per verdict

G1 is the one that fires when a model hallucinates. G3 is the one that stops a policy
being loosened until everything is deliverable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from adjacency.contracts import (
    SEVERITY_ACTION,
    Action,
    ImageEvidence,
    InventoryItem,
    PolicySpec,
    TextEvidence,
    Verdict,
)


@dataclass(frozen=True, slots=True)
class GateResult:
    """The outcome of one gate against one subject.

    `code` is a stable machine-readable identifier. It is what appears in the audit
    ledger and on screen when a row turns red, so it must not be reworded casually.
    """

    gate: str
    passed: bool
    code: str | None = None
    detail: str = ""
    coerce_to: Action | None = None

    def __bool__(self) -> bool:
        return self.passed


def _ok(gate: str) -> GateResult:
    return GateResult(gate=gate, passed=True)


# --------------------------------------------------------------------------------------
# G0: every clause points at prose the advertiser actually wrote
# --------------------------------------------------------------------------------------


def g0_source_spans(spec: PolicySpec) -> list[GateResult]:
    """Compile-time gate. Each clause's span must reproduce its `source_text` exactly.

    Run once, when prose is compiled into a PolicySpec. A clause whose span does not
    land on the quoted text is a rule the compiler invented rather than derived, and an
    invented rule will silently decide real inventory forever after.
    """
    results: list[GateResult] = []
    prose = spec.prose
    for clause in spec.clauses:
        if clause.source_end > len(prose):
            results.append(
                GateResult(
                    gate="G0",
                    passed=False,
                    code="G0_SPAN_OUT_OF_RANGE",
                    detail=(
                        f"clause {clause.clause_id}: span ends at {clause.source_end} "
                        f"but prose is {len(prose)} characters"
                    ),
                )
            )
            continue
        actual = prose[clause.source_start : clause.source_end]
        if actual != clause.source_text:
            results.append(
                GateResult(
                    gate="G0",
                    passed=False,
                    code="G0_SPAN_MISMATCH",
                    detail=(
                        f"clause {clause.clause_id}: prose[{clause.source_start}:"
                        f"{clause.source_end}] is {actual!r}, clause claims "
                        f"{clause.source_text!r}"
                    ),
                )
            )
        else:
            results.append(_ok("G0"))
    return results


# --------------------------------------------------------------------------------------
# G1: cited evidence exists, exactly, where the model said it does
# --------------------------------------------------------------------------------------


def g1_evidence_grounding(verdict: Verdict, item: InventoryItem) -> GateResult:
    """Every cited span must be byte-for-byte present; every box must lie in its frame.

    This is the hallucination gate. A model that cites a quote which is not in the post,
    or draws a box outside the image, has produced a verdict about content that does not
    exist. Grok 4.5 does this rarely. At X's impression volume, rarely is millions.
    """
    for ev in verdict.evidence:
        if isinstance(ev, TextEvidence):
            if ev.end > len(item.text):
                return GateResult(
                    gate="G1",
                    passed=False,
                    code="G1_SPAN_OUT_OF_RANGE",
                    detail=(
                        f"cited span ends at {ev.end} but item text is {len(item.text)} characters"
                    ),
                    coerce_to=Action.REVIEW,
                )
            if ev.end <= ev.start:
                return GateResult(
                    gate="G1",
                    passed=False,
                    code="G1_SPAN_MALFORMED",
                    detail=f"cited span [{ev.start}, {ev.end}) is empty or inverted",
                    coerce_to=Action.REVIEW,
                )
            actual = item.text[ev.start : ev.end]
            if actual != ev.quote:
                return GateResult(
                    gate="G1",
                    passed=False,
                    code="G1_SPAN_NOT_FOUND",
                    detail=(
                        f"text[{ev.start}:{ev.end}] is {actual!r}, cited quote is {ev.quote!r}"
                    ),
                    coerce_to=Action.REVIEW,
                )
        else:
            # `Evidence` is exactly TextEvidence | ImageEvidence, so this branch is the
            # image case by construction. Written as `else` rather than a second
            # `isinstance` so there is no unreachable fall-through for a third type that
            # does not exist; adding one to the union will fail type checking here.
            ev: ImageEvidence
            media = item.media_by_id(ev.media_id)
            if media is None:
                return GateResult(
                    gate="G1",
                    passed=False,
                    code="G1_MEDIA_NOT_FOUND",
                    detail=f"cited media_id {ev.media_id!r} is not attached to this item",
                    coerce_to=Action.REVIEW,
                )
            if ev.x + ev.w > media.width or ev.y + ev.h > media.height:
                return GateResult(
                    gate="G1",
                    passed=False,
                    code="G1_BBOX_OUT_OF_BOUNDS",
                    detail=(
                        f"box ({ev.x},{ev.y},{ev.w},{ev.h}) exceeds media "
                        f"{ev.media_id} at {media.width}x{media.height}"
                    ),
                    coerce_to=Action.REVIEW,
                )
    return _ok("G1")


# --------------------------------------------------------------------------------------
# G2: every cited clause exists in the policy at this version
# --------------------------------------------------------------------------------------


def g2_clause_existence(verdict: Verdict, spec: PolicySpec) -> GateResult:
    """A verdict may only cite clauses that are in the PolicySpec it was judged against.

    Also checks the version, because a verdict carrying clause ids from a different
    revision is stale even when every id happens to resolve.
    """
    if verdict.policy_version != spec.version:
        return GateResult(
            gate="G2",
            passed=False,
            code="G2_VERSION_MISMATCH",
            detail=(
                f"verdict was judged against policy v{verdict.policy_version}, "
                f"gate is checking against v{spec.version}"
            ),
            coerce_to=Action.REVIEW,
        )
    unknown = [cid for cid in verdict.clause_ids if cid not in spec.clause_ids]
    if unknown:
        return GateResult(
            gate="G2",
            passed=False,
            code="G2_CLAUSE_NOT_FOUND",
            detail=f"clause id(s) not in policy v{spec.version}: {sorted(unknown)}",
            coerce_to=Action.REVIEW,
        )
    return _ok("G2")


# --------------------------------------------------------------------------------------
# G3: a revision cannot quietly loosen the policy
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MonotonicityReport:
    """What a policy revision would do to the frozen holdout."""

    flipped_to_allow: tuple[str, ...]
    """Items the old policy blocked and the new policy would allow, without approval."""
    approved: tuple[str, ...]
    result: GateResult


def g3_monotonicity(
    *,
    previous: dict[str, Action],
    proposed: dict[str, Action],
    approvals: frozenset[str] = frozenset(),
) -> MonotonicityReport:
    """No item may go BLOCK to ALLOW on the frozen holdout without a logged approval.

    This is the reward-hacking gate. Absent it, the cheapest way to make any brand-safety
    metric look good is to loosen the policy until everything is deliverable, and the
    loosening is invisible because it shows up as more inventory rather than as an
    incident. Tightening is always permitted; only loosening needs a human.

    `approvals` holds item ids a human has explicitly signed off on flipping.
    """
    flipped: list[str] = []
    approved_flips: list[str] = []
    for item_id, old_action in previous.items():
        new_action = proposed.get(item_id)
        if new_action is None:
            continue
        if old_action is Action.BLOCK and new_action is Action.ALLOW:
            if item_id in approvals:
                approved_flips.append(item_id)
            else:
                flipped.append(item_id)

    if flipped:
        result = GateResult(
            gate="G3",
            passed=False,
            code="G3_UNAPPROVED_LOOSENING",
            detail=(
                f"{len(flipped)} holdout item(s) would flip BLOCK to ALLOW without "
                f"approval: {sorted(flipped)[:10]}"
            ),
        )
    else:
        result = _ok("G3")

    return MonotonicityReport(
        flipped_to_allow=tuple(sorted(flipped)),
        approved=tuple(sorted(approved_flips)),
        result=result,
    )


# --------------------------------------------------------------------------------------
# G4: the action must be the one the severity table says
# --------------------------------------------------------------------------------------


def g4_severity_coherence(verdict: Verdict) -> GateResult:
    """`action` must equal `SEVERITY_ACTION[severity]`.

    A verdict claiming severity 4 and action ALLOW is not a judgement call, it is an
    incoherent object. The model does not get to negotiate with a lookup table.
    """
    expected = SEVERITY_ACTION[verdict.severity]
    if verdict.action is not expected:
        return GateResult(
            gate="G4",
            passed=False,
            code="G4_SEVERITY_INCOHERENT",
            detail=(
                f"severity {verdict.severity} requires {expected.value}, "
                f"verdict claims {verdict.action.value}"
            ),
            coerce_to=expected if expected is not Action.ALLOW else Action.REVIEW,
        )
    return _ok("G4")


# --------------------------------------------------------------------------------------
# G5: budget, checked after every layer
# --------------------------------------------------------------------------------------


@dataclass(slots=True)
class Budget:
    """Caps for one run. Mutable by design: the meter has to move as the run proceeds."""

    max_tokens: int
    max_tool_calls: int
    max_wallclock_s: float
    tokens_used: int = 0
    tool_calls_used: int = 0
    elapsed_s: float = 0.0

    def charge(self, *, tokens: int = 0, tool_calls: int = 0, seconds: float = 0.0) -> None:
        self.tokens_used += tokens
        self.tool_calls_used += tool_calls
        self.elapsed_s += seconds


def g5_budget(budget: Budget) -> GateResult:
    """On breach, every still-undecided item defaults to BLOCK.

    Failing closed here means the advertiser loses reach, never safety. That direction is
    a deliberate product decision and it is the one an advertiser would choose if asked.
    """
    breaches: list[str] = []
    if budget.tokens_used > budget.max_tokens:
        breaches.append(f"tokens {budget.tokens_used} over cap {budget.max_tokens}")
    if budget.tool_calls_used > budget.max_tool_calls:
        breaches.append(f"tool calls {budget.tool_calls_used} over cap {budget.max_tool_calls}")
    if budget.elapsed_s > budget.max_wallclock_s:
        breaches.append(f"elapsed {budget.elapsed_s:.1f}s over cap {budget.max_wallclock_s}s")

    if breaches:
        return GateResult(
            gate="G5",
            passed=False,
            code="G5_BUDGET_EXCEEDED",
            detail="; ".join(breaches),
            coerce_to=Action.BLOCK,
        )
    return _ok("G5")


# --------------------------------------------------------------------------------------
# G6: abstain rather than allow
# --------------------------------------------------------------------------------------


def g6_abstention_floor(
    verdict: Verdict,
    *,
    threshold: float = 0.6,
    escalated: Verdict | None = None,
) -> GateResult:
    """Below the confidence floor, or when two effort levels disagree, never ALLOW.

    The asymmetry is the point. An uncertain BLOCK costs reach and is recoverable. An
    uncertain ALLOW is an ad next to content the advertiser explicitly forbade, and it
    is recoverable only as an apology.
    """
    if escalated is not None and escalated.action is not verdict.action:
        if verdict.action is Action.ALLOW or escalated.action is Action.ALLOW:
            return GateResult(
                gate="G6",
                passed=False,
                code="G6_EFFORT_DISAGREEMENT",
                detail=(
                    f"low-effort pass said {verdict.action.value}, escalated pass said "
                    f"{escalated.action.value}"
                ),
                coerce_to=Action.REVIEW,
            )
    if verdict.confidence < threshold and verdict.action is Action.ALLOW:
        return GateResult(
            gate="G6",
            passed=False,
            code="G6_BELOW_CONFIDENCE_FLOOR",
            detail=f"confidence {verdict.confidence:.2f} below floor {threshold:.2f}",
            coerce_to=Action.REVIEW,
        )
    return _ok("G6")


# --------------------------------------------------------------------------------------
# The per-verdict gate chain
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GateChainResult:
    """The verdict after gating, plus every gate outcome that produced it."""

    verdict: Verdict
    results: tuple[GateResult, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> tuple[GateResult, ...]:
        return tuple(r for r in self.results if not r.passed)

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(r.code for r in self.failures if r.code is not None)


def run_verdict_gates(
    verdict: Verdict,
    item: InventoryItem,
    spec: PolicySpec,
    *,
    confidence_threshold: float = 0.6,
    escalated: Verdict | None = None,
) -> GateChainResult:
    """Run every per-verdict gate and apply the strictest coercion any of them demands.

    All gates run even after one fails, because the audit ledger should record every
    reason a verdict was rejected rather than only the first. Coercions are ordered
    BLOCK over REVIEW over ALLOW, so the strictest wins regardless of gate order.
    """
    results = (
        g1_evidence_grounding(verdict, item),
        g2_clause_existence(verdict, spec),
        g4_severity_coherence(verdict),
        g6_abstention_floor(verdict, threshold=confidence_threshold, escalated=escalated),
    )

    severity_order = {Action.ALLOW: 0, Action.REVIEW: 1, Action.BLOCK: 2}
    coercions = [r.coerce_to for r in results if r.coerce_to is not None]

    final = verdict
    if coercions:
        strictest = max(coercions, key=lambda a: severity_order[a])
        codes = ", ".join(r.code for r in results if not r.passed and r.code)
        final = verdict.coerced_to(strictest, reason=codes)

    return GateChainResult(verdict=final, results=results)
