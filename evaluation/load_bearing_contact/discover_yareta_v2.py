#!/usr/bin/env python3
"""Discover and validate the exact Yareta files selected by experiment_plan_v2.

This tool reads public archive metadata only. It does not download or inspect
sensor/event signal contents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

ARCHIVE_ID = "e72b9ec2-d097-45ac-8126-d04035407f51"
API_URL = f"https://access.yareta.unige.ch/access/metadata/{ARCHIVE_ID}/data?size=1000"
SESSION = "S01"
TRIAL_TYPES = ("SlowGait", "Gait", "FastGait")
FILE_RE = re.compile(
    r"^/(?P<participant>P\d{2})_(?P<session>S\d{2})/"
    r"(?P<area>SYNC_DATA|RAW_DATA)/"
    r"(?P=participant)_(?P=session)_"
    r"(?P<trial_type>SlowGait|Gait|FastGait)_(?P<trial_number>\d{2})"
    r"\.(?P<ext>csv|c3d)$"
)


def fetch_archive_file_metadata(url: str = API_URL) -> list[dict[str, Any]]:
    req = urllib.request.Request(url, headers={"User-Agent": "linguistic-core-grounding-probe/1"})
    with urllib.request.urlopen(req, timeout=60) as response:
        payload = json.load(response)
    rows = payload.get("_data")
    if not isinstance(rows, list):
        raise ValueError("Yareta response missing _data list")
    return rows


def selected_participants(plan: dict[str, Any]) -> set[str]:
    split = plan["participant_split"]
    calibration = set(split["calibration"])
    evaluation = set(split["evaluation"])
    overlap = calibration & evaluation
    if overlap:
        raise ValueError(f"participant split overlaps: {sorted(overlap)}")
    selected = calibration | evaluation
    excluded = set(split.get("excluded", []))
    if selected & excluded:
        raise ValueError("excluded participant is present in selected split")
    return selected


def select_manifest_rows(
    archive_rows: list[dict[str, Any]], plan: dict[str, Any]
) -> list[dict[str, Any]]:
    participants = selected_participants(plan)
    selected: list[dict[str, Any]] = []

    for item in archive_rows:
        metadata = item.get("metadata", {})
        file_meta = metadata.get("file", {})
        full_name = file_meta.get("fullName")
        if not isinstance(full_name, str):
            continue
        match = FILE_RE.match(full_name)
        if not match:
            continue
        groups = match.groupdict()
        if groups["participant"] not in participants or groups["session"] != SESSION:
            continue

        ext = groups["ext"]
        expected_area = "SYNC_DATA" if ext == "csv" else "RAW_DATA"
        if groups["area"] != expected_area:
            raise ValueError(f"unexpected area for {full_name}")

        checksums = metadata.get("checksums", {})
        sha256 = checksums.get("SHA-256")
        res_id = item.get("resId")
        size = file_meta.get("size")
        name = file_meta.get("name")
        if not all((res_id, sha256, name)) or not isinstance(size, int):
            raise ValueError(f"incomplete metadata for {full_name}")

        stem = Path(name).stem
        selected.append(
            {
                "id": res_id,
                "name": name,
                "full_name": full_name,
                "size": size,
                "sha256": sha256.lower(),
                "participant": groups["participant"],
                "trial_type": groups["trial_type"],
                "trial_number": groups["trial_number"],
                "extension": ext,
                "stem": stem,
            }
        )

    return sorted(selected, key=lambda row: row["name"])


def validate_pairs(rows: list[dict[str, Any]], plan: dict[str, Any]) -> dict[str, Any]:
    participants = selected_participants(plan)
    by_stem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_stem[row["stem"]].append(row)

    unpaired: list[dict[str, Any]] = []
    for stem, pair in sorted(by_stem.items()):
        extensions = sorted(row["extension"] for row in pair)
        if extensions != ["c3d", "csv"]:
            unpaired.append({"stem": stem, "extensions": extensions})

    observed_participants = sorted({row["participant"] for row in rows})
    missing_participants = sorted(participants - set(observed_participants))
    unexpected_participants = sorted(set(observed_participants) - participants)

    counts_by_participant: dict[str, dict[str, int]] = {}
    for participant in sorted(participants):
        counts_by_participant[participant] = {}
        for trial_type in TRIAL_TYPES:
            stems = {
                row["stem"]
                for row in rows
                if row["participant"] == participant and row["trial_type"] == trial_type
            }
            counts_by_participant[participant][trial_type] = len(stems)

    if unpaired:
        raise ValueError(f"unpaired selected trial files: {unpaired[:5]}")
    if missing_participants or unexpected_participants:
        raise ValueError(
            f"participant mismatch missing={missing_participants} unexpected={unexpected_participants}"
        )

    return {
        "selected_file_count": len(rows),
        "selected_trial_pair_count": len(by_stem),
        "selected_bytes": sum(row["size"] for row in rows),
        "participants": observed_participants,
        "counts_by_participant_and_trial_type": counts_by_participant,
        "unpaired": unpaired,
    }


def canonical_selection_hash(rows: list[dict[str, Any]]) -> str:
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_manifest(plan_path: Path, archive_rows: list[dict[str, Any]]) -> dict[str, Any]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    rows = select_manifest_rows(archive_rows, plan)
    summary = validate_pairs(rows, plan)
    return {
        "schema": "linguistic-core.yareta-contact-acquisition-manifest.v2",
        "source": {
            "archive_id": ARCHIVE_ID,
            "doi": plan["dataset"]["doi"],
            "api_url": API_URL,
            "selection_basis": "experiment_plan_v2.json public metadata only; no signal rows inspected",
        },
        "summary": summary,
        "selection_sha256": canonical_selection_hash(rows),
        "files": rows,
    }


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=here / "experiment_plan_v2.json")
    parser.add_argument(
        "--output", type=Path, default=here / "acquisition_manifest_v2.json"
    )
    args = parser.parse_args()

    manifest = build_manifest(args.plan, fetch_archive_file_metadata())
    args.output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary = manifest["summary"]
    print(
        f"selected {summary['selected_trial_pair_count']} paired trials / "
        f"{summary['selected_file_count']} files / {summary['selected_bytes']} bytes"
    )
    print(f"selection_sha256={manifest['selection_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
