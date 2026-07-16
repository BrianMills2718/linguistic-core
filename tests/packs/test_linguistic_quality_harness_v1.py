"""Fail-closed activation checks for the Plan 0147 quality harness."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import cast

import pytest
import yaml
from pydantic import ValidationError

from onto_canon6.packs.linguistic_crosswalk_v1 import LinguisticCrosswalkV1
from onto_canon6.packs.linguistic_quality_harness_v1 import (
    LinguisticQualityHarnessReceiptV1,
    run_blocked_linguistic_quality_harness_v1,
)
from onto_canon6.packs.linguistic_runtime_view_v1 import LinguisticRuntimeViewReceiptV1


ROOT = Path(__file__).parents[2]


def _receipt() -> LinguisticQualityHarnessReceiptV1:
    """Run the harness from committed governed inputs."""

    crosswalk = LinguisticCrosswalkV1.model_validate_json(
        gzip.open(ROOT / "docs/runs/artifacts/plan0147_linguistic_crosswalk_v1.json.gz", "rb").read()
    )
    manifest = cast(
        dict[str, object],
        yaml.safe_load((ROOT / "ontology_packs/linguistic_core/0.4.0-rc1/manifest.yaml").read_text()),
    )
    build = cast(dict[str, object], manifest["build"])
    return run_blocked_linguistic_quality_harness_v1(
        crosswalk, LinguisticRuntimeViewReceiptV1.model_validate(build["runtime_view_receipt"])
    )


def test_harness_blocks_without_fabricating_quality_or_fallback() -> None:
    """Missing frozen cases and a trace-verified evaluator produce no quality claim."""

    receipt = _receipt()
    assert receipt.status == "blocked_missing_activation_inputs"
    assert receipt.quality_decision == "none"
    assert receipt.improvement_claim is False
    assert receipt.fallback_chain == ()


def test_harness_rejects_hidden_missing_input_or_digest_substitution() -> None:
    """A caller cannot remove a blocker or forge the receipt digest."""

    payload = cast(dict[str, object], json.loads(_receipt().model_dump_json()))
    payload["missing_activation_inputs"] = ["trace_verified_evaluator"]
    with pytest.raises(ValidationError, match="must name every activation input"):
        LinguisticQualityHarnessReceiptV1.model_validate(payload)
