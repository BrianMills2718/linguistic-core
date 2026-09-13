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

## Consumer-owned relation schema probe

`world_substrate_relation_schema_v1.json` exercises the same role-typed grammar
against a downstream relation owned by another namespace. It represents
`ws:semantic_binding` with local `ws.roledef.*` roles while leaving all seven
roles ungrounded to global LC thematic roles where no such equivalence is
warranted. Filler types may still cite LC types (for example the predicate
sense) or World Substrate-owned types.

This is the boundary the first predicate-local probe could not express: the
language is reusable outside the `lc:` namespace, but the resulting application
schema does not become Linguistic Core vocabulary. In particular, the
`mechanic` role is explicitly World Substrate-owned consequence authority; its
presence in a relation schema says what participant occupies that role, not what
effects the mechanic produces.

Run:

```bash
PYTHONPATH=src python scripts/run_consumer_relation_schema_probe_v1.py --json
PYTHONPATH=src:. pytest -q tests/packs/test_consumer_relation_schema_v1.py
```

## Relation assertion / objectification probe

`world_substrate_objectification_v1.json` adds the next fact-oriented layer over
relation schemas: identity-bearing relation assertions with explicit role
bindings. A role filler may reference another relation assertion, preserving the
inner relation's participant grouping rather than flattening it into unrelated
binary edges.

The concrete probe objectifies one `ws:semantic_binding` assertion and binds it
to the `semantic_binding` role of a `ws:causal_event` assertion. The validator
checks relation-schema identity, role cardinality, nested assertion existence,
and nested relation type. A plain reference is rejected where the role expects
a relation assertion.

Run:

```bash
PYTHONPATH=src python scripts/run_relation_assertion_probe_v1.py --json
PYTHONPATH=src:. pytest -q tests/packs/test_relation_assertion_v1.py
```

## Analytic InterpretationLicense probe

`analytic_interpretation_license_v1.json` is the first direct Evidence → Action
consumer profile over the generic relation grammar. It defines
`analytic:semantic_binding` and `analytic:interpretation_license`, then
objectifies one semantic binding inside an interpretation-license assertion.

The license groups one method result with semantic grounding, optional
world/observation models, assumptions and design conditions, provenance, scope,
and licensed claim type. Provenance is mandatory; world-model cardinality is
bounded; and the semantic binding cannot be replaced by a plain reference where
the role declares `analytic:semantic_binding` as its filler relation schema.

This construction requires no new `lc:` vocabulary and no new core mechanism
beyond the merged relation-schema/objectification grammar.

## Full analytic core relation profile

`analytic_core_relation_profile_v1.json` expands the successful
`InterpretationLicense` probe into one coherent Evidence → Action consumer
profile with eleven relation schemas:

1. representation projection;
2. representation transformation;
3. semantic binding;
4. observation-model profile;
5. world-model profile;
6. analytic-methodology profile;
7. inference relation;
8. interpretation license;
9. decision-method application;
10. action realization; and
11. feedback update.

The fixture contains twelve grouped assertions and fifteen nested relation
fillers. Starting at the feedback-update assertion, the nested assertion graph
reaches every schema type. One fitted causal model deliberately keeps the same
identity while serving as the inference output, the interpretation license's
method result, and the input representation of a later transformation. This is
the compositional case that a one-way pipeline or disjoint class hierarchy would
lose.

All schemas remain `analytic:` consumer vocabulary. The construction uses the
Linguistic Core grammar but adds no analytic concepts to the `lc:` namespace.
