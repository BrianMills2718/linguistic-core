# M4 predicate-local role-definition probe

This directory is a **candidate construction probe**, not a published Linguistic Core pack or consumer contract.

It tests one additive representation refinement:

> A predicate/fact schema owns local `RoleDefinition` identities, and each local role may ground to a reusable Linguistic Core role concept such as `lc.role.theme`.

The probe deliberately keeps those two identities separate. For example:

- `lc.roledef.acquire_get_obtain.theme` and
- `lc.roledef.give_transfer.transferred_object`

are distinct predicate-local roles, but both ground to `lc.role.theme`.

## Cases

`role_definition_probe_v1.json` contains three bounded schemas:

1. `lc:buy_purchase` — buyer / goods / seller;
2. `lc:acquire_get_obtain` — recipient / theme / source; and
3. `lc:give_transfer` — giver / transferred_object / recipient.

The purchase→acquisition local-role transforms must resolve to the global role pairs already exercised by the existing M4 acquisition report:

```text
buyer  -> recipient
goods  -> theme
seller -> source
```

The `give_transfer` schema is also checked against World Substrate's current `binding.give.v0` semantic role map:

```text
giver              -> lc.role.donor
transferred_object -> lc.role.theme
recipient          -> lc.role.recipient
```

That compatibility fixture is grounded in `BrianMills2718/world-substrate`, `src/world_substrate/semantic.py`, blob `5b2646d886ff672cb95780f3f081b641b3c9706f` as reviewed on 2026-09-12. Only the semantic participant mapping is copied into this probe. World Substrate's `causal_class`, `causal_bearer`, `mechanic_id`, and interpretation limits remain consumer-owned and are intentionally not fields in the LC consumer-role profile.

## Run

```bash
PYTHONPATH=src python scripts/run_role_definition_probe_v1.py
PYTHONPATH=src python scripts/run_role_definition_probe_v1.py --json
pytest -q tests/packs/test_role_definition_v1.py tests/packs/test_m4_acquisition_mapping_v1.py
```

Passing establishes only that this candidate shape can preserve local role identity while remaining backward-compatible with the bounded acquisition mapping and one real consumer binding. It does **not** publish the schema, certify all role alignments, add filler-type evidence, or change World Substrate mechanics.
