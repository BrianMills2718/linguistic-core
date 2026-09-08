"""Follow-up to slice 1: does declaring role_expected_value_kind stabilize the
negation filler's shape? Negated sentence only, 0.3.3-neg only, 5 runs."""
import json, os, sys, traceback
from pathlib import Path
sys.path.insert(0, "src")
from onto_canon6.ontology_runtime.loaders import compose_profile
from onto_canon6.pipeline.text_extraction import TextExtractionService

ROOT = Path(os.environ["SCRATCH"])
TEXT = "Acme will not acquire Beta."
svc = TextExtractionService(reasoning_effort="high", max_output_tokens=8000,
                            response_schema_mode="compact_roles")
prof = compose_profile(pack_id="linguistic_core", pack_version="0.3.3-neg",
                       mode="closed", proposal_policy="reject", packs_root=ROOT)
recs = []
for i in range(5):
    rec = {"run": i}
    try:
        run = svc.extract_candidate_run(source_text=TEXT, profile_id="scratch_vk",
            profile_version="0.3.3-neg", submitted_by="slice1-vk",
            source_ref=f"scratch://vk/{i}", loaded_profile=prof)
        rec["negation_fillers"] = [
            json.loads(imp.model_dump_json())["payload"].get("roles", {}).get("negation")
            for imp in run.candidate_imports]
        rec["error"] = None
    except Exception as exc:
        rec["negation_fillers"] = None
        rec["error"] = f"{type(exc).__name__}: {exc}"[:200]
    recs.append(rec)
    print(json.dumps(rec, default=str)[:400], flush=True)
Path(os.environ["OUT"]).write_text(json.dumps(recs, indent=2, default=str))
fillers = [f for r in recs for fl in (r["negation_fillers"] or []) for f in (fl or [])]
kinds = sorted({str(f.get("value_kind")) for f in fillers})
norms = sorted({f"{type(f.get('normalized')).__name__}:{f.get('normalized')!r}" for f in fillers})
print("normalized values emitted:", norms)
print("\nDISTINCT value_kind values emitted:", kinds)
print("runs with a negation filler:", sum(1 for r in recs if r["negation_fillers"] and any(r["negation_fillers"])), "/", len(recs))
