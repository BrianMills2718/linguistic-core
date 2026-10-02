# Factor-boundary audit: support and sit

**Status:** experimental review of the six-concept probe. The purpose is to find hidden circularity, not to defend the current factorization.

## Review rule

A target-bearing intermediate such as `support_relation` is acceptable only if it is itself recursively decomposed into lower-level structures. A factor with the same semantic content as the target and no non-target dependencies would merely rename the concept and fail the grounding test.

## Support

### Previous weakness

The first specimen described `support_relation` using contact, relative geometry, load/pressure, and resistance to downward displacement, but represented those cues only in prose. That made the factor look more primitive than it was.

### Revised factorization

```text
persistent tracked patterns
  -> contact pattern
  -> relative-position pattern
  -> load-response pattern
  -> support relation
  -> support disposition
```

The important distinction is between an **episode** and a **disposition**. An occurrent load-bearing relation can be observed/learned from interaction; the disposition is a counterfactual generalization over relevant conditions.

### Remaining assumptions

The decomposition still owes a grounding account of gravity-relative direction, load/pressure, bounded displacement, and how to distinguish support from attachment, suspension, friction, containment, or mere obstruction. These are now explicit gaps rather than hidden inside the word "support."

## Sit

### Previous weakness

The first specimen used factors named `sitting_body_configuration` and `sitting_event_pattern`. That is too close to the target and risks definitional circularity.

### Revised factorization

```text
body/object persistence
+ contact/relative-position structure
  -> body-posture configuration
  -> posture-transition pattern

body-posture configuration
+ support relation
+ participation in a temporal occurrence
  -> lexical/action category SIT
```

The lower factors no longer contain the lexical target.

### Remaining assumptions

The hard problem is not naming a canonical posture. Human sitting varies across chairs, stools, floors, wheelchairs, bodily morphologies, cultures, and lexical senses. The representation therefore treats posture configuration as a learned structured family, not a fixed necessary-and-sufficient geometry.

## Chair consequence

The chair concept now depends on `body_posture_configuration` and a `conventional_postural_support_function`, not a factor named "sitting event." This makes the social/artifact layer explicit: a chair need not be defined by a single realized sitting episode, but by a socially stabilized function/disposition over relevant supported postures.

## Audit verdict

The revision **reduces obvious lexical circularity but does not establish grounding**. The remaining research burden is now more precise:

1. ground gravity/load/contact/body-geometry primitives;
2. learn equivalence classes over variable posture and support episodes;
3. state when the learned classes license higher-level semantic factors;
4. keep social function distinct from sensorimotor structure.

That is a useful outcome: the probe is exposing the next missing layer rather than hiding it.
