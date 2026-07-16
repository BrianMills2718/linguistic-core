"""Fail-closed quality-harness contracts for the linguistic runtime successor."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from onto_canon6.packs.linguistic_crosswalk_v1 import LinguisticCrosswalkV1
from onto_canon6.packs.linguistic_runtime_view_v1 import LinguisticRuntimeViewReceiptV1


def _sha256(value: object) -> str:
    """Hash canonical JSON evidence without accepting an implicit fallback."""

    return hashlib.sha256(
        json.dumps(
            value,
            default=lambda item: item.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


class LinguisticQualityManifestV1(BaseModel):
    """Required frozen development/held-out and evaluator inputs for one quality decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["linguistic-quality-manifest-v1"] = "linguistic-quality-manifest-v1"
    accepted_complete_document_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    development_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    held_out_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_runtime_view_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_emitted_predicate_count: int = Field(gt=0)
    evaluator_trace_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_trace_verified: Literal[True]
    label_isolation_verified: Literal[True]
    fallback_chain: tuple[()] = ()


class LinguisticQualityHarnessReceiptV1(BaseModel):
    """A quality decision or a precise non-authorizing blocked receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["linguistic-quality-harness-receipt-v1"] = (
        "linguistic-quality-harness-receipt-v1"
    )
    crosswalk_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_view_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["blocked_missing_activation_inputs"]
    missing_activation_inputs: tuple[
        Literal[
            "accepted_complete_document_development_sample",
            "frozen_development_manifest",
            "frozen_held_out_manifest",
            "nonempty_policy_eligible_runtime_candidate",
            "trace_verified_evaluator",
        ]
    , ...]
    quality_decision: Literal["none"] = "none"
    improvement_claim: Literal[False] = False
    fallback_chain: tuple[()] = ()
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _closed(self) -> "LinguisticQualityHarnessReceiptV1":
        if self.missing_activation_inputs != (
            "accepted_complete_document_development_sample",
            "frozen_development_manifest",
            "frozen_held_out_manifest",
            "nonempty_policy_eligible_runtime_candidate",
            "trace_verified_evaluator",
        ):
            raise ValueError("blocked harness must name every activation input")
        content = self.model_dump(mode="json", exclude={"content_sha256"})
        if self.content_sha256 != _sha256(content):
            raise ValueError("quality harness receipt digest does not reconcile")
        return self


class LinguisticQualityPreregistrationV1(BaseModel):
    """Decision-first activation contract frozen before any held-out labels exist."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["linguistic-quality-preregistration-v1"] = (
        "linguistic-quality-preregistration-v1"
    )
    stage: Literal["pilot"] = "pilot"
    claim: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    unit_of_analysis: str = Field(min_length=1)
    population: str = Field(min_length=1)
    baseline_pack_ref: Literal["linguistic_core@0.3.0"] = "linguistic_core@0.3.0"
    baseline_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_pack_ref: Literal["linguistic_core@0.4.0-rc1"] = (
        "linguistic_core@0.4.0-rc1"
    )
    candidate_runtime_view_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_emitted_predicate_count: int = Field(ge=0)
    plan0141_observation_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    plan0141_plan_blob_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    plan0141_plan_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dependency_observation: Literal[
        "bounded_source_window_only_no_accepted_complete_document"
    ] = "bounded_source_window_only_no_accepted_complete_document"
    failure_taxonomy_rule: str = Field(min_length=1)
    split_and_leakage_rule: str = Field(min_length=1)
    primary_metric: str = Field(min_length=1)
    secondary_metrics: tuple[str, ...] = Field(min_length=1)
    controls: tuple[str, ...] = Field(min_length=2)
    invalid_run_conditions: tuple[str, ...] = Field(min_length=1)
    decision_rules: tuple[str, ...] = Field(min_length=3)
    non_claims: tuple[str, ...] = Field(min_length=1)
    status: Literal["blocked_missing_activation_inputs"]
    missing_activation_inputs: tuple[
        Literal[
            "accepted_complete_document_development_sample",
            "frozen_development_manifest",
            "frozen_held_out_manifest",
            "nonempty_policy_eligible_runtime_candidate",
            "trace_verified_evaluator",
        ],
        ...,
    ]
    score: None = None
    improvement_claim: Literal[False] = False
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _blocked_preregistration_is_honest(self) -> "LinguisticQualityPreregistrationV1":
        expected_missing = (
            "accepted_complete_document_development_sample",
            "frozen_development_manifest",
            "frozen_held_out_manifest",
            "nonempty_policy_eligible_runtime_candidate",
            "trace_verified_evaluator",
        )
        if self.missing_activation_inputs != expected_missing:
            raise ValueError("quality preregistration must retain every current blocker")
        if self.candidate_emitted_predicate_count != 0:
            raise ValueError("current preregistration is bound to the observed sparse candidate")
        content = self.model_dump(mode="json", exclude={"content_sha256"})
        if self.content_sha256 != _sha256(content):
            raise ValueError("quality preregistration digest does not reconcile")
        return self


def run_blocked_linguistic_quality_harness_v1(
    crosswalk: LinguisticCrosswalkV1, runtime_view: LinguisticRuntimeViewReceiptV1
) -> LinguisticQualityHarnessReceiptV1:
    """Return the only honest result while quality activation evidence is unavailable."""

    content = {
        "schema_version": "linguistic-quality-harness-receipt-v1",
        "crosswalk_content_sha256": crosswalk.content_sha256,
        "runtime_view_content_sha256": runtime_view.content_sha256,
        "status": "blocked_missing_activation_inputs",
        "missing_activation_inputs": (
            "accepted_complete_document_development_sample",
            "frozen_development_manifest",
            "frozen_held_out_manifest",
            "nonempty_policy_eligible_runtime_candidate",
            "trace_verified_evaluator",
        ),
        "quality_decision": "none",
        "improvement_claim": False,
        "fallback_chain": (),
    }
    return LinguisticQualityHarnessReceiptV1.model_validate(
        {**content, "content_sha256": _sha256(content)}
    )


def build_linguistic_quality_preregistration_v1(
    runtime_view: LinguisticRuntimeViewReceiptV1,
    *,
    baseline_manifest_sha256: str,
    plan0141_observation_commit: str,
    plan0141_plan_blob_sha: str,
    plan0141_plan_content_sha256: str,
) -> LinguisticQualityPreregistrationV1:
    """Freeze the valid future readout while retaining every observed blocker."""

    content = {
        "schema_version": "linguistic-quality-preregistration-v1",
        "stage": "pilot",
        "claim": (
            "After a complete-document development sample yields a fixed nonempty candidate, "
            "the candidate makes more exact predicate-role-type decisions than 0.3.0 on "
            "independently frozen same-class held-out cases, with no critical regression."
        ),
        "decision": (
            "After independent eval sign-off, continue toward a non-default release, revise the "
            "candidate on development evidence, or reject the quality hypothesis."
        ),
        "unit_of_analysis": (
            "One source-grounded semantic decision containing predicate, roles, type constraints, "
            "and exact supporting span."
        ),
        "population": (
            "Ordinary and boundary cases from the same failure classes observed in the first "
            "accepted complete-document semantic graph."
        ),
        "baseline_pack_ref": "linguistic_core@0.3.0",
        "baseline_manifest_sha256": baseline_manifest_sha256,
        "candidate_pack_ref": "linguistic_core@0.4.0-rc1",
        "candidate_runtime_view_sha256": runtime_view.content_sha256,
        "candidate_emitted_predicate_count": runtime_view.emitted_predicate_count,
        "plan0141_observation_commit": plan0141_observation_commit,
        "plan0141_plan_blob_sha": plan0141_plan_blob_sha,
        "plan0141_plan_content_sha256": plan0141_plan_content_sha256,
        "dependency_observation": "bounded_source_window_only_no_accepted_complete_document",
        "failure_taxonomy_rule": (
            "Freeze the taxonomy from accepted complete-document development failures before "
            "repair; include at least one ordinary and one boundary held-out case per class."
        ),
        "split_and_leakage_rule": (
            "An independent author freezes held-out sources, labels, hashes, and evidence spans; "
            "implementation sees development labels only, and any content or source overlap "
            "invalidates the run."
        ),
        "primary_metric": (
            "Paired exact-case wins: every predicate, role, type constraint, and evidence span "
            "must match; report each case and the candidate-minus-baseline total."
        ),
        "secondary_metrics": (
            "exact predicate selection by failure class",
            "exact role and type-constraint decisions by failure class",
            "evidence quote and offset validity",
            "abstention and unresolved-state correctness",
        ),
        "controls": (
            "known-good positive case that both builds must preserve",
            "known-bad evidence-offset corruption that the evaluator must reject",
            "candidate runtime digest substitution that the runner must reject",
            "held-out label or source overlap that the leakage check must reject",
        ),
        "invalid_run_conditions": (
            "missing or timed-out evaluator",
            "missing full trace or raw output",
            "hidden retry cache or fallback",
            "post-result label rubric threshold or case change",
            "empty candidate or unavailable baseline",
            "failed positive negative corruption or leakage control",
        ),
        "decision_rules": (
            "continue only if the candidate has more exact-case wins, no failure class worsens, "
            "and every critical control passes",
            "revise only from development evidence when the run is valid but does not meet the "
            "continue rule; obtain a fresh held-out set before rerun",
            "reject the quality claim when any critical regression occurs or independent sign-off "
            "rejects validity or representativeness",
        ),
        "non_claims": (
            "production readiness",
            "default activation",
            "whole-corpus representativeness",
            "semantic verification of unresolved crosswalk rows",
        ),
        "status": "blocked_missing_activation_inputs",
        "missing_activation_inputs": (
            "accepted_complete_document_development_sample",
            "frozen_development_manifest",
            "frozen_held_out_manifest",
            "nonempty_policy_eligible_runtime_candidate",
            "trace_verified_evaluator",
        ),
        "score": None,
        "improvement_claim": False,
    }
    return LinguisticQualityPreregistrationV1.model_validate(
        {**content, "content_sha256": _sha256(content)}
    )
