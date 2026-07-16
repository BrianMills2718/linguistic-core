"""Build one source-bound Plan 0147 SUMO semantic-review queue artifact."""

from __future__ import annotations

import argparse
import gzip
from pathlib import Path
import subprocess
import sys


_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from onto_canon6.packs.sumo_crosswalk_audit_v1 import SumoCrosswalkAuditV1  # noqa: E402
from onto_canon6.packs.sumo_crosswalk_review_v1 import (  # noqa: E402
    PropBankReviewSourceFileV1,
    PropBankReviewSourceV1,
    build_sumo_crosswalk_semantic_review_queue_v1,
)
from onto_canon6.packs.linguistic_sources_v1 import load_linguistic_source_manifest_v1  # noqa: E402
from onto_canon6.packs.linguistic_source_audit_v1 import normalize_propbank_donor_id_v1  # noqa: E402
from onto_canon6.packs.linguistic_source_projection_v1 import PropBankProjectionV1  # noqa: E402


def _git(checkout: Path, *args: str) -> str:
    """Return one checked Git command's standard output."""

    return subprocess.run(
        ["git", "-C", str(checkout), *args], check=True, capture_output=True, text=True
    ).stdout


def _source_files(
    checkout: Path, paths: set[str]
) -> tuple[PropBankReviewSourceFileV1, ...]:
    """Bind every checked-out PropBank XML frame to its declared Git blob."""

    rows = _git(checkout, "ls-tree", "-r", "HEAD", "--", "frames").splitlines()
    files = []
    for row in rows:
        metadata, relative_path = row.split("\t", maxsplit=1)
        _, object_type, blob_sha = metadata.split()
        if object_type == "blob" and relative_path in paths:
            files.append(
                PropBankReviewSourceFileV1(
                    source_relative_path=relative_path,
                    local_path=checkout / relative_path,
                    git_blob_sha=blob_sha,
                )
            )
    return tuple(sorted(files, key=lambda item: item.source_relative_path))


def main() -> int:
    """Write one new queue, refusing unpinned source or output replacement."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--propbank-checkout", type=Path, required=True)
    parser.add_argument("--donor-db", type=Path, default=_REPO_ROOT / "data/sumo_plus.db")
    parser.add_argument(
        "--projection",
        type=Path,
        default=_REPO_ROOT / "docs/runs/artifacts/plan0147_propbank_projection_v1.json.gz",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace queue artifact: {args.output}")
    report = SumoCrosswalkAuditV1.model_validate_json(args.report.read_bytes())
    manifest = load_linguistic_source_manifest_v1(
        _REPO_ROOT / "config/linguistic_sources_v1.yaml"
    )
    propbank = next(item for item in manifest.sources if item.source_key == "propbank_frames_34")
    if propbank.git_identity is None or propbank.selected_payload is None:
        raise ValueError("PropBank source manifest lacks required pinned identity")
    commit = _git(args.propbank_checkout, "rev-parse", "HEAD").strip()
    tree = _git(args.propbank_checkout, "rev-parse", "HEAD^{tree}").strip()
    if commit != propbank.git_identity.commit_sha:
        raise ValueError("PropBank checkout does not match the Plan 0147 source pin")
    projection = PropBankProjectionV1.model_validate_json(gzip.open(args.projection, "rb").read())
    predicates = {item.donor_predicate_id: item for item in report.predicates}
    source_ids = {
        normalized
        for role in report.roles
        if role.constraint_status == "incompatible_donor_supertype"
        for normalized in [normalize_propbank_donor_id_v1(
            predicates[role.donor_predicate_id].propbank_sense_id or ""
        )]
        if normalized is not None
    }
    paths = {
        item.source_relative_path for item in projection.rolesets if item.roleset_id in source_ids
    }
    source = PropBankReviewSourceV1(
        source_commit_sha=commit,
        source_tree_sha=tree,
        selected_payload_sha256=propbank.selected_payload.sha256,
        files=_source_files(args.propbank_checkout, paths),
    )
    queue = build_sumo_crosswalk_semantic_review_queue_v1(
        report, donor_database=args.donor_db, propbank_source=source
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(queue.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(queue.queue_identity_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
