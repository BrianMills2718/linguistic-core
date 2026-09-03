"""Run the Slice B two-pass independent donor-mapping review pilot.

Reads the committed crosswalk artifact, selects `candidate`-state FrameNet
donor-mapping rows (prioritizing `Merge.kif`-tied predicates), makes two real
independent `llm_client` calls per row, and checkpoints each row's result to
a JSONL file as it completes -- so a mid-batch failure never loses completed
rows. Does not overwrite the immutable committed crosswalk artifact; use
`--write-crosswalk` to additionally emit a new crosswalk artifact with the
reviewed rows appended.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from onto_canon6.packs.linguistic_crosswalk_v1 import (
    LinguisticCrosswalkV1,
    append_independent_reviewed_donor_records_v1,
)
from onto_canon6.packs.linguistic_donor_review_v1 import (
    append_checkpoint_row_v1,
    load_checkpointed_review_results_v1,
    reviewed_donor_mappings_from_checkpoints_v1,
    run_two_pass_review_row_v1,
    select_merge_kif_framenet_candidate_rows_v1,
)


def _read_crosswalk(path: Path) -> LinguisticCrosswalkV1:
    payload = gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()
    return LinguisticCrosswalkV1.model_validate_json(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--donor-database", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--limit", type=int, required=True, help="Rows to review this run.")
    parser.add_argument(
        "--models",
        nargs=2,
        required=True,
        metavar=("MODEL_A", "MODEL_B"),
        help="Two distinct models for the two independent passes.",
    )
    parser.add_argument("--max-budget-per-call", type=float, required=True)
    parser.add_argument("--trace-id-prefix", type=str, default="plan0147-slice-b")
    parser.add_argument(
        "--write-crosswalk",
        type=Path,
        default=None,
        help="If set, write a new (non-canonical) crosswalk artifact with all checkpointed "
        "review rows appended. Refuses to overwrite an existing file.",
    )
    args = parser.parse_args()

    crosswalk = _read_crosswalk(args.crosswalk)
    already = load_checkpointed_review_results_v1(args.checkpoint)
    already_ids = {item.record_id for item in already}
    print(f"crosswalk loaded: {len(crosswalk.records)} records", flush=True)
    print(f"checkpoint has {len(already)} already-completed rows", flush=True)

    rows = select_merge_kif_framenet_candidate_rows_v1(
        crosswalk, donor_database=args.donor_database, limit=None
    )
    rows = [row for row in rows if row.record_id not in already_ids][: args.limit]
    print(f"selected {len(rows)} new rows for this run (limit={args.limit})", flush=True)

    models = (args.models[0], args.models[1])
    prompt_path = _ROOT / "prompts/linguistic/donor_mapping_independent_review_v1.yaml"
    failures_path = args.checkpoint.with_suffix(args.checkpoint.suffix + ".failures.jsonl")
    total_cost = 0.0
    failed_rows: list[str] = []
    for index, row in enumerate(rows, start=1):
        started = time.monotonic()
        try:
            result = run_two_pass_review_row_v1(
                row,
                models=models,
                trace_id_prefix=args.trace_id_prefix,
                max_budget_per_call=args.max_budget_per_call,
                prompt_path=prompt_path,
            )
        except Exception as exc:  # noqa: BLE001 -- logged loudly below, never swallowed
            elapsed = time.monotonic() - started
            failed_rows.append(row.record_id)
            failures_path.parent.mkdir(parents=True, exist_ok=True)
            with failures_path.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {
                            "record_id": row.record_id,
                            "predicate_name": row.predicate_name,
                            "frame_id": row.frame_id,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc)[:2000],
                        }
                    )
                    + "\n"
                )
            print(
                f"[{index}/{len(rows)}] {row.record_id} {row.predicate_name} -> {row.frame_id} "
                f"| FAILED after llm_client's own retries: {type(exc).__name__}: {str(exc)[:200]} "
                f"elapsed={elapsed:.2f}s -- logged to {failures_path}, skipping to next row",
                flush=True,
            )
            continue
        elapsed = time.monotonic() - started
        append_checkpoint_row_v1(args.checkpoint, result)
        row_cost = (result.cost_usd_a or 0.0) + (result.cost_usd_b or 0.0)
        total_cost += row_cost
        print(
            f"[{index}/{len(rows)}] {row.record_id} {row.predicate_name} -> {row.frame_id} "
            f"| A={result.pass_a.verdict} B={result.pass_b.verdict} -> {result.outcome} "
            f"| cost=${row_cost:.5f} elapsed={elapsed:.2f}s",
            flush=True,
        )

    print(
        f"this run: {len(rows)} rows attempted, {len(rows) - len(failed_rows)} completed, "
        f"{len(failed_rows)} failed, total observed cost=${total_cost:.5f}",
        flush=True,
    )
    if failed_rows:
        print(f"failed record_ids this run: {failed_rows}", flush=True)

    all_results = load_checkpointed_review_results_v1(args.checkpoint)
    outcome_counts = {"tentatively_verified": 0, "rejected": 0, "unresolved": 0}
    for item in all_results:
        outcome_counts[item.outcome] += 1
    print(f"checkpoint total: {len(all_results)} rows, outcomes={outcome_counts}", flush=True)

    if args.write_crosswalk is not None:
        updated = append_independent_reviewed_donor_records_v1(
            crosswalk, reviewed_donor_mappings=reviewed_donor_mappings_from_checkpoints_v1(all_results)
        )
        args.write_crosswalk.parent.mkdir(parents=True, exist_ok=True)
        payload = updated.model_dump_json().encode() + b"\n"
        with args.write_crosswalk.open("xb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as archive:
                archive.write(payload)
        print(
            f"wrote {args.write_crosswalk}: tentatively_verified_count="
            f"{updated.tentatively_verified_count} rejected_count={updated.rejected_count} "
            f"unresolved_count={updated.unresolved_count} verified_count={updated.verified_count}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
