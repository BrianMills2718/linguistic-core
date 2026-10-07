#!/usr/bin/env python3
"""Acquire only the preregistered PhysioNet force recordings and verify hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

BASE_URL = "https://physionet.org/files/gaitpdb/1.0.0/"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=here / "experiment_plan_v1.json")
    parser.add_argument("--cache", type=Path, default=here / ".cache" / "data")
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    selected = plan["cohort_selection"]["selected_files"]
    args.cache.mkdir(parents=True, exist_ok=True)

    for item in selected:
        name = item["file"]
        expected = item["sha256"]
        dest = args.cache / name
        if dest.exists() and sha256_file(dest) == expected:
            print(f"verified cached {name}")
            continue

        tmp = dest.with_suffix(dest.suffix + ".download")
        if tmp.exists():
            tmp.unlink()
        print(f"downloading {name}")
        with urllib.request.urlopen(BASE_URL + name, timeout=120) as response, tmp.open("wb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)

        actual = sha256_file(tmp)
        if actual != expected:
            tmp.unlink(missing_ok=True)
            raise SystemExit(
                f"SHA256 mismatch for {name}: expected {expected}, got {actual}"
            )
        tmp.replace(dest)
        print(f"verified {name}")

    print(f"verified {len(selected)} preregistered recordings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
