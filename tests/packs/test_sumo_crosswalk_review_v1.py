"""Proposal-only semantic review queue tests for Plan 0147 Slice 3."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3

import pytest
from pydantic import ValidationError

from onto_canon6.packs.sumo_crosswalk_audit_v1 import (
    SumoCrosswalkAuditV1,
    audit_sumo_crosswalk_v1,
)
from onto_canon6.packs.sumo_crosswalk_review_v1 import (
    PropBankReviewSourceFileV1,
    PropBankReviewSourceV1,
    SumoCrosswalkReviewError,
    SumoCrosswalkSemanticReviewQueueV1,
    build_sumo_crosswalk_semantic_review_queue_v1,
)
from tests.packs.test_sumo_crosswalk_audit_v1 import _database, _projection


def _git_blob_sha(payload: bytes) -> str:
    """Compute the expected Git blob identity for fixture bytes."""

    framed = f"blob {len(payload)}\0".encode("ascii") + payload
    return hashlib.sha1(framed, usedforsecurity=False).hexdigest()


def _inputs(
    tmp_path: Path, *, exact_propbank: bool = True
) -> tuple[SumoCrosswalkAuditV1, Path, PropBankReviewSourceV1]:
    """Build one real audit with a single selected structural conflict."""

    database = tmp_path / "donor.db"
    _database(database)
    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE predicates SET propbank_sense_id = ?, description = ? "
        "WHERE name = 'missing_process'",
        (
            "affect-01" if exact_propbank else "missing-01",
            "cause an effect",
        ),
    )
    connection.execute(
        "UPDATE role_slots SET arg_position = 'ARG0', type_constraint = 'Entity' "
        "WHERE event_sense_id = 'missing_process' AND named_label = 'Supertype'"
    )
    connection.commit()
    connection.close()
    report = audit_sumo_crosswalk_v1(database, projection=_projection(tmp_path))

    payload = b"""<frameset><predicate lemma="affect"><roleset id="affect.01" name="have an effect on"><roles><role n="0" descr="thing affecting"/></roles></roleset></predicate></frameset>"""
    source_file = tmp_path / "affect.xml"
    source_file.write_bytes(payload)
    source = PropBankReviewSourceV1(
        source_commit_sha="1" * 40,
        source_tree_sha="2" * 40,
        selected_payload_sha256="3" * 64,
        files=(
            PropBankReviewSourceFileV1(
                source_relative_path="frames/affect.xml",
                local_path=source_file,
                git_blob_sha=_git_blob_sha(payload),
            ),
        ),
    )
    return report, database, source


def test_queue_selects_conflict_once_and_binds_exact_propbank_evidence(
    tmp_path: Path,
) -> None:
    report, database, source = _inputs(tmp_path)

    queue = build_sumo_crosswalk_semantic_review_queue_v1(
        report, donor_database=database, propbank_source=source
    )

    assert queue.review_authority == "none_proposal_queue_only"
    assert (
        queue.source_tree_membership_authority
        == "caller_supplied_requires_independent_verification"
    )
    assert len(queue.cases) == 1
    case = queue.cases[0]
    assert case.case_id == "sumo-review:missing_process:Supertype"
    assert case.abstract_role == "agent"
    assert case.donor_type_constraint == "Entity"
    assert case.source_constraint_types == ("AutonomousAgent",)
    assert case.propbank.resolution_status == "exact_current_source"
    assert case.propbank.roleset_name == "have an effect on"
    assert case.propbank.argument_description == "thing affecting"
    assert case.proposal_state == "awaiting_semantic_proposal"


def test_queue_preserves_missing_source_and_rejects_corruption_or_acceptance(
    tmp_path: Path,
) -> None:
    report, database, source = _inputs(tmp_path, exact_propbank=False)
    queue = build_sumo_crosswalk_semantic_review_queue_v1(
        report, donor_database=database, propbank_source=source
    )
    assert queue.cases[0].propbank.resolution_status == "source_window_not_supplied"

    promoted = queue.model_dump(mode="python")
    promoted["cases"][0]["proposal_state"] = "accepted"
    with pytest.raises(ValidationError):
        SumoCrosswalkSemanticReviewQueueV1.model_validate(promoted)

    corrupted_source = source.model_copy(
        update={
            "files": (
                source.files[0].model_copy(update={"git_blob_sha": "f" * 40}),
            )
        }
    )
    with pytest.raises(SumoCrosswalkReviewError, match="Git blob mismatch"):
        build_sumo_crosswalk_semantic_review_queue_v1(
            report, donor_database=database, propbank_source=corrupted_source
        )

    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE predicates SET description = 'substituted' WHERE name = 'missing_process'"
    )
    connection.commit()
    connection.close()
    with pytest.raises(SumoCrosswalkReviewError, match="does not match"):
        build_sumo_crosswalk_semantic_review_queue_v1(
            report, donor_database=database, propbank_source=source
        )
