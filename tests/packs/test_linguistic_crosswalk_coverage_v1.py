"""Closure and corruption checks for the complete Plan 0147 crosswalk report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from onto_canon6.packs.linguistic_crosswalk_coverage_v1 import LinguisticCrosswalkCoverageV1


def _payload() -> dict[str, object]:
    """Load the committed coverage report rather than a reduced success fixture."""

    path = (
        Path(__file__).parents[2]
        / "docs/runs/artifacts/plan0147_linguistic_crosswalk_coverage_v1.json"
    )
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def test_crosswalk_coverage_accounts_for_every_source_and_record_state() -> None:
    """Keep exact source extras and the non-promotional state population visible."""

    report = LinguisticCrosswalkCoverageV1.model_validate(_payload())
    assert [(item.family, item.extra_current_source_count) for item in report.families] == [
        ("propbank", 7253),
        ("framenet", 0),
        ("sumo", 166),
    ]
    assert report.crosswalk_record_count == 46184
    assert report.verified_count == 0
    assert report.candidate_count == 2263
    assert report.rejected_count == 8


def test_crosswalk_coverage_rejects_count_preserving_substitution() -> None:
    """Reject a forged source-extra count even when the report remains populated."""

    payload = _payload()
    families = cast(list[dict[str, object]], payload["families"])
    families[0]["extra_current_source_count"] = 7252
    with pytest.raises(ValidationError, match="source identity population"):
        LinguisticCrosswalkCoverageV1.model_validate(payload)
