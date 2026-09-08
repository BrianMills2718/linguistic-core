"""Re-derive the frame-layer accuracy measurement, durably.

The original run's judged sample lived only in a session scratch directory and
was lost, so the taxonomy's VF-10 row carried a correlation nobody could check.
This script reproduces it and writes its output into the repository.

Sample is seeded and re-drawable. Judging uses the nine-relation mapping
vocabulary rather than correct/wrong, because a mapping to a broader frame is
imprecise, not an error -- only `incompatibleWith` is unambiguous failure.

Usage:  python evaluation/frame_layer/judge_frame_sample.py [--n 100] [--dry-run]
"""
from __future__ import annotations

import argparse, json, random, sqlite3, sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

SEED = 20260907
DONOR = Path.home() / "code/onto-canon6/data/sumo_plus.db"
OUT = Path(__file__).parent
MODEL = "openrouter/openai/gpt-5.6-luna"

Relation = Literal[
    "exactMatch", "closeMatch", "broaderThan", "narrowerThan",
    "lexicalizes", "evokes", "roleEquivalentInContext",
    "roleSpecializes", "incompatibleWith",
]


class Verdict(BaseModel):
    relation: Relation = Field(description="Relation from the predicate sense to the frame.")
    correct_frame_if_incompatible: str | None = Field(
        default=None, description="If incompatibleWith, the frame that would have been right."
    )
    rationale: str = Field(description="One sentence.")


def draw(n: int) -> list[dict]:
    con = sqlite3.connect(f"file:{DONOR}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT p.propbank_sense_id, p.description, f.name, f.description, p.mapping_confidence "
        "FROM predicates p JOIN frames f ON f.id = p.frame_id "
        "WHERE p.propbank_sense_id IS NOT NULL ORDER BY p.propbank_sense_id"
    ).fetchall()
    if not rows:
        sys.exit("no frame-mapped predicates found -- refusing to report an empty sample")
    random.Random(SEED).shuffle(rows)
    return [
        {"predicate": r[0], "predicate_gloss": r[1], "frame": r[2],
         "frame_definition": (r[3] or "")[:1200], "assigner_confidence": r[4]}
        for r in rows[:n]
    ]


def judge(item: dict):
    from llm_client import call_llm_structured
    prompt = (
        f"PropBank sense: {item['predicate']}\n"
        f"Its gloss: {item['predicate_gloss']!r}\n\n"
        f"Assigned FrameNet frame: {item['frame']}\n"
        f"That frame's definition: {item['frame_definition']}\n\n"
        "Classify the relation from the predicate sense to the frame. "
        "A frame broader than the sense is broaderThan, not an error. "
        "Reserve incompatibleWith for mappings no annotator could defend."
    )
    parsed, result = call_llm_structured(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_model=Verdict,
        reasoning_effort="low",
        num_retries=1,
    )
    return parsed, result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    sample = draw(a.n)
    (OUT / "sample.jsonl").write_text(
        "".join(json.dumps(s) + "\n" for s in sample), encoding="utf-8"
    )
    print(f"sample: {len(sample)} rows (seed {SEED}) -> {OUT/'sample.jsonl'}")
    if a.dry_run:
        return

    judged = []
    for i, item in enumerate(sample, 1):
        verdict, result = judge(item)
        rec = dict(item)
        rec.update(json.loads(verdict.model_dump_json()))
        rec["cost_usd"] = getattr(result, "cost", None)
        judged.append(rec)
        if i % 20 == 0:
            print(f"  judged {i}/{len(sample)}")
    (OUT / "judged.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in judged), encoding="utf-8"
    )
    print(f"judged -> {OUT/'judged.jsonl'}")


if __name__ == "__main__":
    main()
