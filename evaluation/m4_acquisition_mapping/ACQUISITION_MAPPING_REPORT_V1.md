# M4 acquisition mapping report v1

Candidate-only integration evidence; no published pack or consumer changed.

- Pack target: `pack_id='linguistic_core' pack_version='0.3.3'`
- Direction: `lc:buy_purchase` → `lc:acquire_get_obtain` (`narrowerThan`)
- Conditions: `commercial_transaction`
- Loss: `lossy`; `commercial_consideration`
- Role transforms: `3`
- Donor mapping asset: `ontology_packs/linguistic_core/0.3.0/semantic_mappings.jsonl`
- M3 reconciliation: `evaluation/propbank_examples/propbank_examples_reconciliation_v1.json` (projection `e2628942b04c0bc66bb6081c4e953548a29970574ac8ec73fa626f9ce2dd59b0`)
- Source-native evidence: `buy.01` — The company bought a wheel - loader from Dresser .
- Ambiguity disposition: `resolved_by_exact_source_alignment`; unresolved: `none`

## Focused cases

- `purchase_to_acquisition_allowed`: **PASS** — expected `allowed`, observed `allowed` (`ALLOWED`).
- `acquisition_to_purchase_rejected`: **PASS** — expected `rejected`, observed `rejected` (`MAPPING_DIRECTION_UNSUPPORTED declared=lc:buy_purchase->lc:acquire_get_obtain`).
- `buyer_seller_swap_rejected`: **PASS** — expected `rejected`, observed `rejected` (`ROLE_FILLER_MISMATCH source_role=lc.role.buyer target_role=lc.role.buyer`).

**Result:** 3 passed, 0 failed; content digest `14dcf083db83ffae27c012582b777e974b98e4c28b503cdcdde32a77aa5c0922`.

Reverse direction and buyer/seller filler swaps remain visible rejection cases.
