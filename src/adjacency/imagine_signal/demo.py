"""Frozen construction inputs for the credential-free ImagineSignal demo."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from adjacency.imagine_signal.auction import (
    AuctionMechanism,
    AuctionScenario,
    BidderContext,
    BidderSpec,
    CreativeSignal,
    LearningMode,
    QueryContext,
)
from adjacency.imagine_signal.canonical import content_sha256
from adjacency.imagine_signal.contracts import (
    BrandSpec,
    CampaignSpec,
    GenerationBudget,
    LockedAttribute,
    MeasurementWindow,
    NextAction,
)
from adjacency.imagine_signal.mutations import plan_controlled_mutations
from adjacency.imagine_signal.ports import ImageGenerationRequest
from adjacency.imagine_signal.service import (
    EfficiencyInput,
    OfflineFamilyRequest,
    PlannedCreative,
)

TENANT_ID = "demo-tenant"
CAMPAIGN_ID = "demo-campaign"
CONTROL_ID = "demo-control"
WARM_ID = "demo-variant-warm"
COOL_ID = "demo-variant-cool"
MODEL = "grok-imagine-image-2026-03-02"

CONTROL_PROMPT = (
    "Fictional Orbit Bottle ad. Preserve the product, logo, composition, and text. "
    "Use the approved neutral background tone."
)
MUTATION_PROMPT_TEMPLATE = (
    "Fictional Orbit Bottle ad. Preserve the product, logo, composition, and text. "
    "Change only {axis}. Set the {axis} to {level}."
)


def _generation_request(prompt: str) -> ImageGenerationRequest:
    return ImageGenerationRequest(
        schema_version="1.0",
        model=MODEL,
        prompt=prompt,
        n=1,
        aspect_ratio="1:1",
        resolution="1k",
        data_classification="synthetic",
    )


def build_demo_request(repo_root: Path | str | None = None) -> OfflineFamilyRequest:
    """Build the exact request matched by committed synthetic replay fixtures."""

    resolved_root = (
        Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[3]
    )
    brand = BrandSpec(
        schema_version="1",
        tenant_id=TENANT_ID,
        brand_spec_id="orbit-bottle-brand-v1",
        required_elements=("fictional Orbit bottle", "ORBIT label"),
        prohibited_elements=("real brand marks", "price claim"),
        locked_text_claims=("ORBIT",),
        locked_product_identity=("orbit-bottle-v1",),
        logo_constraints=("preserve ORBIT wordmark pixels",),
        source_provenance=("synthetic_demo_brief_v1",),
    )
    window = MeasurementWindow(
        schema_version="1",
        start=datetime(2026, 8, 1, tzinfo=UTC),
        end=datetime(2026, 8, 2, tzinfo=UTC),
    )
    campaign = CampaignSpec(
        schema_version="1",
        tenant_id=TENANT_ID,
        campaign_id=CAMPAIGN_ID,
        objective="learn whether background tone merits an approved display test",
        audience_contexts=("home-feed", "search"),
        measurement_metric="observed.ctr",
        measurement_window=window,
        brand_spec_hash=brand.brand_spec_hash,
        generation_budget=GenerationBudget(
            schema_version="1",
            max_calls=3,
            max_images=3,
            max_quality_images=0,
            max_cost_in_usd_ticks=0,
            max_wallclock_ms=1_000,
        ),
        created_by="imagine-signal-offline-demo",
    )
    locked_attributes = (
        LockedAttribute(
            schema_version="1",
            name="product_identity",
            value_sha256=content_sha256({"value": "orbit-bottle-v1"}),
        ),
        LockedAttribute(
            schema_version="1",
            name="logo",
            value_sha256=content_sha256({"value": "ORBIT-pixel-mask-v1"}),
        ),
        LockedAttribute(
            schema_version="1",
            name="composition",
            value_sha256=content_sha256({"value": "centered-bottle-v1"}),
        ),
        LockedAttribute(
            schema_version="1",
            name="text",
            value_sha256=content_sha256({"value": "ORBIT"}),
        ),
    )
    mutations = plan_controlled_mutations(
        schema_version="1",
        tenant_id=TENANT_ID,
        family_id="orbit-background-tone-v1",
        campaign_id=CAMPAIGN_ID,
        root_asset_id=CONTROL_ID,
        parent_asset_id=CONTROL_ID,
        axis="background_tone",
        levels=("warm", "cool"),
        locked_attributes=locked_attributes,
        prompt_template_version="orbit-background-v1",
        prompt_template=MUTATION_PROMPT_TEMPLATE,
    )
    mutation_by_level = {mutation.level: mutation for mutation in mutations}
    planned_creatives = (
        PlannedCreative(
            creative_id=CONTROL_ID,
            root_creative_id=CONTROL_ID,
            parent_creative_id=None,
            mutation_id=None,
            request=_generation_request(CONTROL_PROMPT),
        ),
        PlannedCreative(
            creative_id=WARM_ID,
            root_creative_id=CONTROL_ID,
            parent_creative_id=CONTROL_ID,
            mutation_id=mutation_by_level["warm"].mutation_id,
            request=_generation_request(
                MUTATION_PROMPT_TEMPLATE.format(axis="background_tone", level="warm")
            ),
        ),
        PlannedCreative(
            creative_id=COOL_ID,
            root_creative_id=CONTROL_ID,
            parent_creative_id=CONTROL_ID,
            mutation_id=mutation_by_level["cool"].mutation_id,
            request=_generation_request(
                MUTATION_PROMPT_TEMPLATE.format(axis="background_tone", level="cool")
            ),
        ),
    )
    observed_locked_hashes = tuple(
        (
            mutation.mutation_id,
            tuple((locked.name, locked.value_sha256) for locked in locked_attributes),
        )
        for mutation in mutations
    )
    auction_scenario = AuctionScenario(
        scenario_id="orbit-fixed-bid-sensitivity-v1",
        contexts=(
            QueryContext("home-feed", 0.6),
            QueryContext("search", 0.4),
        ),
        bidders=(
            BidderSpec(
                bidder_id="orbit-focal",
                fixed_bid=1.7,
                contexts=(
                    BidderContext("home-feed", 0.038, 0.040, 3.0),
                    BidderContext("search", 0.048, 0.050, 3.2),
                ),
            ),
            BidderSpec(
                bidder_id="competitor-a",
                fixed_bid=1.45,
                contexts=(
                    BidderContext("home-feed", 0.046, 0.045, 2.6),
                    BidderContext("search", 0.050, 0.048, 2.7),
                ),
            ),
            BidderSpec(
                bidder_id="competitor-b",
                fixed_bid=1.2,
                contexts=(
                    BidderContext("home-feed", 0.040, 0.039, 2.4),
                    BidderContext("search", 0.041, 0.040, 2.5),
                ),
            ),
        ),
        focal_bidder_id="orbit-focal",
        variant_signals=(
            CreativeSignal("home-feed", predicted_ctr=0.044, true_ctr=0.046),
            CreativeSignal("search", predicted_ctr=0.052, true_ctr=0.054),
        ),
        mechanism=AuctionMechanism.FIRST_PRICE,
        learning_mode=LearningMode.FIXED_BID,
        horizon=5_000,
        burn_in=0,
        seeds=(7, 19, 31),
        data_origin="synthetic",
        assumptions=(
            "creative signal is the only baseline-to-variant auction change",
            "predicted CTR and response CTR are distinct inputs",
        ),
        known_limitations=(
            "synthetic bidder values and CTRs",
            "not an X Ads auction or production ranking replay",
        ),
    )
    return OfflineFamilyRequest(
        idempotency_key="orbit-offline-demo-v1",
        tenant_id=TENANT_ID,
        expected_campaign_hash=campaign.campaign_hash,
        campaign=campaign,
        brand=brand,
        mutations=mutations,
        planned_creatives=planned_creatives,
        evaluation_control_creative_id=CONTROL_ID,
        evaluation_variant_creative_id=WARM_ID,
        expected_experiment_id="demo-experiment",
        arm_assignments=((CONTROL_ID, "control-arm"), (WARM_ID, "variant-arm")),
        observed_changes=tuple(
            (mutation.mutation_id, ("background_tone",)) for mutation in mutations
        ),
        observed_locked_hashes=observed_locked_hashes,
        outcome_fixture_path=str(
            resolved_root / "fixtures" / "imagine_signal" / "outcomes" / "demo_family.json"
        ),
        auction_scenario=auction_scenario,
        baseline_efficiency=EfficiencyInput(
            generated_count=3,
            qualified_count=2,
            duplicate_paid_outputs=1,
            quality_outputs=0,
            qualified_quality_outputs=0,
            lineage_complete_count=2,
            total_cost_ticks=0,
        ),
        proposed_action=NextAction.TEST,
        now=datetime(2026, 8, 4, tzinfo=UTC),
        max_outcome_staleness=timedelta(days=2),
        min_sample_size=10_000,
        trace_id="trace-orbit-offline-demo-v1",
        created_at=datetime(2026, 8, 5, tzinfo=UTC),
    )


__all__ = [
    "CONTROL_ID",
    "CONTROL_PROMPT",
    "COOL_ID",
    "MUTATION_PROMPT_TEMPLATE",
    "WARM_ID",
    "build_demo_request",
]
