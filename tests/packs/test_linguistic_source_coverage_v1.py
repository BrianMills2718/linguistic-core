"""Closure and corruption controls for the linguistic source coverage record."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from onto_canon6.packs.linguistic_source_coverage_v1 import LinguisticSourceCoverageV1


def _payload() -> dict[str, object]:
    """Load the committed source-replay receipt rather than a synthetic success case."""

    path = Path(__file__).parents[2] / "docs/runs/artifacts/plan0147_source_coverage_v1.json"
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def test_committed_source_coverage_closes_all_declared_populations() -> None:
    """Keep the complete source evidence machine-readable and fail-closed."""

    coverage = LinguisticSourceCoverageV1.model_validate(_payload())
    assert coverage.propbank_selected_files == coverage.propbank_parsed_files == 7566
    assert coverage.propbank_applied_repairs == 2
    assert coverage.framenet_lexical_unit_declarations - coverage.framenet_indexed_lexical_units == 59
    assert coverage.sumo_selected_modules == 66
    assert coverage.sumo_publication_status == "blocked_mixed_license"
    assert all(source.status == "verified" for source in coverage.verification.sources)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("propbank_parsed_files", 7565, "PropBank file populations"),
        ("framenet_problem_omissions", 58, "FrameNet lexical-unit omission"),
        ("coverage_content_sha256", "0" * 64, "source coverage digest"),
    ],
)
def test_source_coverage_rejects_count_and_digest_substitution(
    field: str, value: int | str, message: str
) -> None:
    """Reject count-preserving-looking and digest-only source coverage corruption."""

    payload = _payload()
    payload[field] = value
    with pytest.raises(ValidationError, match=message):
        LinguisticSourceCoverageV1.model_validate(payload)
