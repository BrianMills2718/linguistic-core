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
    development_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    held_out_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
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
        Literal["frozen_development_manifest", "frozen_held_out_manifest", "trace_verified_evaluator"]
    , ...]
    quality_decision: Literal["none"] = "none"
    improvement_claim: Literal[False] = False
    fallback_chain: tuple[()] = ()
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _closed(self) -> "LinguisticQualityHarnessReceiptV1":
        if self.missing_activation_inputs != (
            "frozen_development_manifest",
            "frozen_held_out_manifest",
            "trace_verified_evaluator",
        ):
            raise ValueError("blocked harness must name every activation input")
        content = self.model_dump(mode="json", exclude={"content_sha256"})
        if self.content_sha256 != _sha256(content):
            raise ValueError("quality harness receipt digest does not reconcile")
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
            "frozen_development_manifest",
            "frozen_held_out_manifest",
            "trace_verified_evaluator",
        ),
        "quality_decision": "none",
        "improvement_claim": False,
        "fallback_chain": (),
    }
    return LinguisticQualityHarnessReceiptV1.model_validate(
        {**content, "content_sha256": _sha256(content)}
    )
