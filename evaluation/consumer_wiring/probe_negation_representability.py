"""Slice 1, repeated: is negation representable once the pack carries ARGM-NEG?

4 conditions x 3 runs. Records the predicate chosen, whether a negation role was
emitted, and the candidate count, so a genuine zero-candidate outcome is
distinguishable from a parse failure.
"""
import json, os, sys, traceback
from pathlib import Path

sys.path.insert(0, "src")
from onto_canon6.ontology_runtime.loaders import compose_profile
from onto_canon6.pipeline.text_extraction import TextExtractionService

ROOT = Path(os.environ["SCRATCH"])
SENTENCES = ["Acme will acquire Beta.", "Acme will not acquire Beta."]
RUNS = 3

svc = TextExtractionService(reasoning_effort="high", max_output_tokens=8000,
                            response_schema_mode="compact_roles")
profiles = {v: compose_profile(pack_id="linguistic_core", pack_version=v, mode="closed",
                               proposal_policy="reject", packs_root=ROOT)
            for v in ("0.3.3-neg", "0.3.2")}

records = []
for version, profile in profiles.items():
    for text in SENTENCES:
        for i in range(RUNS):
            rec = {"version": version, "text": text, "run": i}
            try:
                run = svc.extract_candidate_run(
                    source_text=text, profile_id=f"scratch_{version}",
                    profile_version=version, submitted_by="slice1-probe",
                    source_ref=f"scratch://{version}/{i}/{text}",
                    loaded_profile=profile)
                imps = run.candidate_imports
                rec["n_candidates"] = len(imps)
                rec["candidates"] = []
                for imp in imps:
                    p = json.loads(imp.model_dump_json())["payload"]
                    roles = p.get("roles", {})
                    rec["candidates"].append({
                        "predicate": p.get("predicate"),
                        "roles": sorted(roles.keys()),
                        "negation": roles.get("negation"),
                    })
                rec["error"] = None
            except Exception as exc:
                rec["n_candidates"] = None
                rec["error"] = f"{type(exc).__name__}: {exc}"[:300]
                traceback.print_exc()
            records.append(rec)
            print(json.dumps({k: rec[k] for k in ("version","text","run","n_candidates","candidates","error") if k in rec}, default=str)[:600], flush=True)

Path(os.environ["OUT"]).write_text(json.dumps(records, indent=2, default=str))
print("\n=== SUMMARY ===")
for version in profiles:
    for text in SENTENCES:
        rs = [r for r in records if r["version"] == version and r["text"] == text]
        neg = sum(1 for r in rs for c in (r.get("candidates") or []) if c.get("negation"))
        counts = [r["n_candidates"] for r in rs]
        preds = sorted({c["predicate"] for r in rs for c in (r.get("candidates") or [])})
        print(f"{version:11} | {text:28} | candidates/run={counts} | runs_with_negation_role={neg}/{len(rs)} | predicates={preds}")
