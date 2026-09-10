# M4 acquisition mapping report v1

Candidate-only integration evidence; no published pack or consumer changed.

- Pack target: `pack_id='linguistic_core' pack_version='0.3.3'`
- Direction: `lc:buy_purchase` → `lc:acquire_get_obtain` (`narrowerThan`)
- Conditions: `commercial_transaction`
- Loss: `lossy`; `commercial_consideration`
- Role transforms: `3`
- Donor mapping asset: `ontology_packs/linguistic_core/0.3.0/semantic_mappings.jsonl`

## Focused cases

- `purchase_to_acquisition_allowed`: **PASS** — expected `allowed`, observed `allowed` (`ALLOWED`).
- `acquisition_to_purchase_rejected`: **PASS** — expected `rejected`, observed `rejected` (`MAPPING_DIRECTION_UNSUPPORTED declared=lc:buy_purchase->lc:acquire_get_obtain`).
- `buyer_seller_swap_rejected`: **PASS** — expected `rejected`, observed `rejected` (`ROLE_FILLER_MISMATCH source_role=lc.role.buyer target_role=lc.role.buyer`).

**Result:** 3 passed, 0 failed; content digest `d6a147ab97beee8dc36952fe332ac361602f5481653e744990c8f5abfa876eaf`.

Reverse direction and buyer/seller filler swaps remain visible rejection cases.
