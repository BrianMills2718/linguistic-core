# Grounding-floor audit

**Status:** experimental and independent from the open six-concept semantic-grounding PR.

This probe asks whether the apparent low-level factors beneath `support`, `sit`, and `chair` simply move lexical circularity downward, or whether they can be connected to measurable psychophysical and sensorimotor structure.

## Factors audited

- contact
- relative position
- load response
- body posture
- persistence

## Result

The audit finds a useful but limited stopping point.

These factors can be decomposed into candidate observables such as:

- cutaneous deformation / pressure patterns;
- proprioceptive body-configuration signals;
- force/load and muscle-tension signals;
- multisensory gravity/verticality estimates;
- displacement/change signals;
- spatiotemporal and feature correspondence across perceptual episodes.

That means the current grounding program is **not merely replacing "support" with another unexplained word called support_relation**.

But the audit also rejects a stronger claim that these observables already give fully grounded semantics. The bridge from observables to semantic factors remains an inference/learning problem.

## Important distinctions exposed

### Touch evidence is not metaphysical contact

Tactile mechanoreceptors respond to skin deformation and related mechanical stimulation. A learner can use this as evidence for contact, but absence of tactile evidence does not imply absence of physical contact, and tactile signals can be ambiguous.

### Spatial relations require a reference frame

"Above", "below", and orientation are not free primitives. Gravity-relative structure depends on multisensory estimates of verticality; other relations may be egocentric, allocentric, or object-centered.

### Force is not support

Force/load, pressure, and bounded displacement can support a learned support hypothesis, but they do not by themselves distinguish support from attachment, suspension, friction, containment, or obstruction.

### Posture is a family of configurations

Proprioceptive and contact signals give measurable body configurations. A category such as sitting must be learned over variable configurations rather than defined by one rigid geometry.

### Tracking is not yet identity

Vision research supports mid-level representations that maintain object continuity using space, time, and features. This is a plausible precursor to a grounded object/persistence factor, but it is not yet a complete ontological identity criterion.

## Files

- `grounding_floor_review.json` — machine-readable audit, sources, candidate observables, factor decompositions, and remaining gaps.

## Source boundary

The review uses peer-reviewed review/experimental literature available through PubMed Central for tactile sensing, proprioception, gravity/verticality estimation, and object persistence. The source evidence supports the existence and measurability of the lower-level variables. It does **not** prove the proposed Grounding IR or Phenomenal Meaning Generator theory.

## Next gate

The next useful artifact should be executable and tiny:

1. represent one **support episode** as raw observations -> inferred contact/position/load-response factors -> a support hypothesis;
2. represent one **posture/persistence episode** as raw proprioceptive/spatial/temporal observations -> inferred configuration/track factors;
3. keep raw observations, inferred factors, uncertainty, and semantic classification as separate levels;
4. include negative/adversarial cases so the system must refuse obvious false groundings.

Do not expand the vocabulary before that works.
