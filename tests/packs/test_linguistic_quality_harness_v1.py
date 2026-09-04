"""Fail-closed activation checks for the Plan 0147 quality harness."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import sys
from typing import cast

import pytest
import yaml
from pydantic import ValidationError

from linguistic_core.linguistic_crosswalk_v1 import LinguisticCrosswalkV1
from linguistic_core.linguistic_quality_harness_v1 import (
    build_linguistic_quality_preregistration_v1,
    LinguisticQualityHarnessReceiptV1,
    LinguisticQualityPreregistrationV1,
    run_blocked_linguistic_quality_harness_v1,
)
from linguistic_core.linguistic_runtime_view_v1 import LinguisticRuntimeViewReceiptV1
from scripts.run_linguistic_quality_harness import main as quality_main


ROOT = Path(__file__).parents[2]


def _receipt() -> LinguisticQualityHarnessReceiptV1:
    """Run the harness from committed governed inputs."""

    crosswalk = LinguisticCrosswalkV1.model_validate_json(
        gzip.open(
            ROOT / "docs/runs/artifacts/plan0147_linguistic_crosswalk_v1.json.gz", "rb"
        ).read()
    )
    manifest = cast(
        dict[str, object],
        yaml.safe_load(
            (ROOT / "ontology_packs/linguistic_core/0.4.0-rc1/manifest.yaml").read_text()
        ),
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
    assert receipt.missing_activation_inputs == (
        "accepted_complete_document_development_sample",
        "frozen_development_manifest",
        "frozen_held_out_manifest",
        "nonempty_policy_eligible_runtime_candidate",
        "trace_verified_evaluator",
    )


def test_harness_rejects_hidden_missing_input_or_digest_substitution() -> None:
    """A caller cannot remove a blocker or forge the receipt digest."""

    payload = cast(dict[str, object], json.loads(_receipt().model_dump_json()))
    payload["missing_activation_inputs"] = ["trace_verified_evaluator"]
    with pytest.raises(ValidationError, match="must name every activation input"):
        LinguisticQualityHarnessReceiptV1.model_validate(payload)


def test_preregistration_freezes_decision_and_refuses_a_score_for_empty_candidate() -> None:
    """The authorized lane remains a blocked design until its real system and cases exist."""

    runtime_manifest = cast(
        dict[str, object],
        yaml.safe_load(
            (ROOT / "ontology_packs/linguistic_core/0.4.0-rc1/manifest.yaml").read_text()
        ),
    )
    build = cast(dict[str, object], runtime_manifest["build"])
    baseline_sha256 = hashlib.sha256(
        (ROOT / "ontology_packs/linguistic_core/0.3.0/manifest.yaml").read_bytes()
    ).hexdigest()
    preregistration = build_linguistic_quality_preregistration_v1(
        LinguisticRuntimeViewReceiptV1.model_validate(build["runtime_view_receipt"]),
        baseline_manifest_sha256=baseline_sha256,
        plan0141_observation_commit="ca7b2c7c2aaa0135005ae9550adb09abcbbc7c39",
        plan0141_plan_blob_sha="a8bd6bacf2c041bf82c0cb516dfdb1345201afca",
        plan0141_plan_content_sha256=(
            "1e9ca3851c3d1320941b1c42bfbbc0b89329b28d49e8d4de55edbff640bc208a"
        ),
    )
    assert preregistration.candidate_emitted_predicate_count == 0
    assert preregistration.status == "blocked_missing_activation_inputs"
    assert preregistration.score is None
    assert preregistration.improvement_claim is False
    assert any("offset" in control for control in preregistration.controls)

    payload = cast(dict[str, object], json.loads(preregistration.model_dump_json()))
    payload["missing_activation_inputs"] = ["trace_verified_evaluator"]
    with pytest.raises(ValidationError, match="retain every current blocker"):
        LinguisticQualityPreregistrationV1.model_validate(payload)


def test_cli_rejects_incomplete_preregistration_before_writing_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A malformed optional request cannot leave a standalone receipt behind."""

    output = tmp_path / "receipt.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_linguistic_quality_harness.py",
            "--crosswalk",
            str(ROOT / "docs/runs/artifacts/plan0147_linguistic_crosswalk_v1.json.gz"),
            "--runtime-manifest",
            str(ROOT / "ontology_packs/linguistic_core/0.4.0-rc1/manifest.yaml"),
            "--output",
            str(output),
            "--preregistration-output",
            str(tmp_path / "preregistration.json"),
        ],
    )
    with pytest.raises(ValueError, match="requires baseline and exact Plan 0141 pins"):
        quality_main()
    assert not output.exists()
