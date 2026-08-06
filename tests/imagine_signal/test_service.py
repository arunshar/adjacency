from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from adjacency.imagine_signal.demo import CONTROL_ID, COOL_ID, WARM_ID, build_demo_request
from adjacency.imagine_signal.imagine_client import build_imagine_client
from adjacency.imagine_signal.ports import ImagineMode
from adjacency.imagine_signal.receipts import verify_receipt
from adjacency.imagine_signal.service import (
    EfficiencyInput,
    OfflineImagineSignalService,
    OfflineServiceError,
)

pytestmark = pytest.mark.integration


def _service():
    return OfflineImagineSignalService(build_imagine_client())


def test_complete_demo_replays_assets_outcomes_simulation_gates_and_receipt() -> None:
    service = _service()

    result = service.run(build_demo_request())

    assert tuple(asset.creative_id for asset in result.assets) == (
        CONTROL_ID,
        WARM_ID,
        COOL_ID,
    )
    assert {asset.media_sha256 for asset in result.assets} == {
        "f760c2932b70e2f65196ec13359f07eef6f5a916fa5684f499abb12b18916400",
        "300aeddfd6f32a8153015ab418004eba458a0511fdfa45eab9331f5de062c809",
        "c0c77a34d6ac5bfe4bbb0ac4a1ebfb0831281608da103911ad7642e84f70ebb9",
    }
    assert tuple(estimate.context_id for estimate in result.signal_estimates) == (
        "home-feed",
        "search",
    )
    assert result.signal_estimates[0].absolute_delta == pytest.approx(0.006)
    assert result.signal_estimates[1].absolute_delta == pytest.approx(0.004)
    assert tuple(gate.gate for gate in result.decision.gate_results) == tuple(
        f"IS{index}" for index in range(9)
    )
    assert all(gate.passed for gate in result.decision.gate_results)
    assert result.decision.final_action.value == "TEST"
    assert result.auction_result.evidence_class == "E2_SIMULATED"
    assert result.auction_record.evidence_class.value == "SIMULATED"
    assert result.auction_record.convergence_diagnostics.converged
    assert verify_receipt(result.receipt)
    assert service.receipt_ledger.get(result.receipt.receipt_id) == result.receipt
    assert result.efficiency.controlled.qualified_creative_yield == 1.0
    assert result.efficiency.unstructured_baseline.qualified_creative_yield == pytest.approx(2 / 3)
    assert result.efficiency.controlled.quality_precision is None
    assert "Nothing was published" in result.explanation

    artifact = result.to_dict()
    assert artifact["evidence_labels"]["auction"] == "E2_SIMULATED"
    assert artifact["receipt"]["receipt_sha256"] == result.receipt.receipt_sha256
    assert "The variant increases X revenue." in artifact["prohibited_claims"]


def test_exact_retry_is_idempotent_without_a_second_receipt() -> None:
    service = _service()
    request = build_demo_request()

    first = service.run(request)
    second = service.run(request)

    assert second is first
    assert service.receipt_ledger.get(first.receipt.receipt_id) is first.receipt


def test_idempotency_key_reuse_with_changed_input_is_rejected() -> None:
    service = _service()
    request = build_demo_request()
    service.run(request)

    with pytest.raises(OfflineServiceError) as error:
        service.run(replace(request, min_sample_size=request.min_sample_size + 1))
    assert error.value.code == "SERVICE_IDEMPOTENCY_CONFLICT"


def test_offline_service_rejects_non_replay_client() -> None:
    with pytest.raises(OfflineServiceError) as error:
        OfflineImagineSignalService(SimpleNamespace(mode=ImagineMode.LIVE))
    assert error.value.code == "SERVICE_MODE_NOT_REPLAY"


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (
            lambda request: replace(request, tenant_id="another-tenant"),
            "SERVICE_TENANT_MISMATCH",
        ),
        (
            lambda request: replace(request, expected_campaign_hash="0" * 64),
            "SERVICE_STALE_CAMPAIGN",
        ),
        (
            lambda request: replace(
                request,
                baseline_efficiency=EfficiencyInput(
                    generated_count=2,
                    qualified_count=2,
                    duplicate_paid_outputs=0,
                    quality_outputs=0,
                    qualified_quality_outputs=0,
                    lineage_complete_count=2,
                    total_cost_ticks=0,
                ),
            ),
            "SERVICE_BASELINE_BUDGET_MISMATCH",
        ),
    ],
)
def test_service_fails_closed_on_stale_tenant_or_budget_input(change, code) -> None:
    with pytest.raises(OfflineServiceError) as error:
        _service().run(change(build_demo_request()))
    assert error.value.code == code


def test_mutation_request_must_match_committed_prompt_hash() -> None:
    request = build_demo_request()
    warm = request.planned_creatives[1]
    changed_request = warm.request.model_copy(update={"prompt": f"{warm.request.prompt} changed"})
    changed_warm = replace(warm, request=changed_request)
    changed_family = (
        request.planned_creatives[0],
        changed_warm,
        request.planned_creatives[2],
    )

    with pytest.raises(OfflineServiceError) as error:
        _service().run(replace(request, planned_creatives=changed_family))
    assert error.value.code == "SERVICE_PROMPT_HASH_MISMATCH"


def test_outcomes_from_an_unexpected_experiment_force_hold() -> None:
    request = replace(build_demo_request(), expected_experiment_id="another-experiment")

    result = _service().run(request)

    outcome_gate = next(gate for gate in result.decision.gate_results if gate.gate == "IS5")
    assert outcome_gate.code == "IS5_EXPERIMENT_ARM_MISMATCH"
    assert result.decision.final_action.value == "HOLD"
