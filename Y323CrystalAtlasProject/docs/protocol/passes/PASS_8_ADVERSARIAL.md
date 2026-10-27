# PASS 8 — Adversarial

## Goal

Attempt to break the architecture before implementation makes the break
expensive.

The Skeptic is not a reviewer. A reviewer confirms that the work meets
its stated goals. The Skeptic assumes the work has a flaw and tries to
find it. The default stance is suspicion, not trust.

The Skeptic may send the architecture backward to any previous pass.
This is not failure. Architectural rollback is preferable to
implementation debt.

## Inputs

All planning artifacts:

- `planning/ARCHIVE_REPORT.md`
- `planning/ARCHITECTURE_MAP.md`
- `planning/GLOSSARY.md`
- `planning/CONFLICT_REPORT.md`
- `planning/MINIMAL_ARCHITECTURE.md`
- `planning/COMPLEXITY_AUDIT.md`
- `planning/SYSTEM_BOUNDARIES.md`
- `planning/VERSIONING.md`
- `docs/decisions/DR-*.md`
- Foundational documents (reference only)

The Skeptic may consult the Field Guide and Vision documents only to test
whether the architecture has absorbed material it should not have. It
may not use them to justify new requirements.

## Separation of roles

The Skeptic must not have participated in producing any prior planning
artifact. If the same agent instance produced a prior pass, the Skeptic
role is invalid for this run. Record the conflict and do not proceed.

This is deliberate. An agent that built a thing is compromised as a
critic of it. The protocol has no mechanism to detect this
automatically. The pass relies on the human to enforce the separation.

## Rules of engagement

The Skeptic MAY:

- Attack any element of the architecture
- Propose deletions
- Propose rollback to a prior pass
- Question whether a requirement is genuinely Foundational
- Question whether a Decision Record should be OPEN rather than accepted
- Question whether a Conflict was correctly classified
- Question whether the extension mechanism actually supports extension
- Test the architecture against scenarios it was not designed for
- Test the process itself — whether an earlier pass was performed
  honestly

The Skeptic MAY NOT:

- Propose improvements. The Skeptic's job is to remove, not to add.
- Propose new requirements.
- Propose new features.
- Rewrite the architecture. It can only report that the architecture
  fails a test.
- Justify a finding by appealing to a Vision document.
- Recommend keeping something "because it might be useful later." That
  is exactly the failure mode the protocol exists to prevent.

If the Skeptic identifies a fix, it is recorded as a required rollback,
not as a proposed design. The pass that owns the fix does the fix.

## Attack categories

### Attack 1 — Removal

For every element of `MINIMAL_ARCHITECTURE.md`:

    - Can this be deleted?
    - What specifically breaks if it is deleted?
    - Is the answer to "what breaks" a Foundational document, or a
      preference?

Elements that survive only because of a preference do not survive. If
the answer to "what breaks" is "a Vision document would be harder to
build later," the element should be removed and the Vision document
should absorb the cost.

### Attack 2 — Speculative requirements

For every CORE element:

    - Which Foundational requirement requires it?
    - Is that requirement actually a requirement, or a statement of
      intent?
    - Would the system be functionally correct if this element were
      removed and the requirement were marked "future"?

A requirement phrased as "the Atlas should eventually support X" is not
a V1 requirement. It is a long-term goal. If the architecture has
absorbed it into CORE, the attack succeeds.

### Attack 3 — Elegance disguised as structure

For every relation type, every primitive, every state class:

    - Does this exist because the mathematics demands it?
    - Or does this exist because it sounds elegant?
    - Would a naive implementation without this abstraction fail any
      test in Doc III §17?

The specific failure mode this attack targets: an abstraction that is
defensible in a paper but unnecessary in the schema. Elegance is not a
Foundational requirement.

### Attack 4 — Foundational compliance

For every Foundational invariant in `ARCHIVE_REPORT.md` Part 4:

    - Is this invariant enforced by V1?
    - If not, is the invariant a V1 concern or a long-term concern?
    - If a V1 concern, which schema element enforces it?

An invariant that V1 is supposed to enforce but no schema element
enforces is a loss. `SYSTEM_BOUNDARIES.md` should have caught this.
If it didn't, the boundary pass was performed shallowly.

### Attack 5 — Extension test

Attempt to add a new kind of mathematical structure to the architecture
without changing the schema.

    - A new mathematical object (e.g., a sheaf, a category, a spectral
      triple) — does it fit as an entity?
    - A new relation type (e.g., "adjoint to") — does it fit as a
      relation?
    - A new representation of an existing object — does it fit as an
      attribute or a related entity?
    - A new state class (e.g., "superseded") — does it fit without
      altering the state model?

If any of these fail, the extension mechanism from
`VERSIONING.md` §6 is broken. A broken extension mechanism is a
BLOCKING finding.

### Attack 6 — Scale test

Assume the Atlas doubles in size ten times. 1,000 entities → 1,000,000
entities. 10,000 relations → 10,000,000 relations.

    - Does anything in the architecture depend on a flat list?
    - Does anything depend on a small number of types?
    - Does anything depend on a human reading the whole schema?
    - Does the 3–7 rule still hold at the layer where a user must
      choose among items?

If any element of the architecture breaks at scale, record the specific
break. Do not propose a fix. The fix belongs to Pass 4.

### Attack 7 — Unknown preservation

The system is supposed to preserve unknowns without forcing
classification. Test this:

    - Add an entity whose type is not known.
    - Add a relation whose type is not known.
    - Add a representation that doesn't match any current representation
      class.
    - Add a bridge that might be a bridge but might be a coincidence.

Does each one fit? If any of them requires choosing a category
prematurely, the architecture has violated the Unknown as First-Class
principle.

### Attack 8 — History preservation

Test the identity stability guarantee from `VERSIONING.md` §2.

    - Reclassify an entity. Does its ID survive?
    - Merge two entities. What happens to references to the merged one?
    - Delete a relation. Is the deletion recorded as a state
      transition, or is it erased?
    - Revert to a prior state. Does the revert itself become a new
      state, or does it erase the states in between?

If any of these fails, the versioning contract is broken.

### Attack 9 — Process integrity

This is the attack category the protocol uses on itself. For each prior
pass:

    - Did the pass produce the artifact it was supposed to produce?
    - Does the artifact answer the questions the pass file specified?
    - Are there sections that appear to be boilerplate?
    - Are there citations that don't check out against the source?
    - Are there contradictions between the artifacts of different passes?

A pass whose artifact is present but whose content is hollow has failed.
The Skeptic records the failure by pass name. The fix is a re-run of that
pass, not a patch to its output.

### Attack 10 — Rollback candidates

For each of the following, decide whether the architecture should be
sent back:

    - To Pass 2 if the concept map is missing a concept that
      `MINIMAL_ARCHITECTURE.md` depends on.
    - To Pass 3 if a conflict was resolved silently.
    - To Pass 4 if the architecture contains speculative requirements.
    - To Pass 5 if a layer with >7 items lacks a DR.
    - To Pass 6 if a Vision concept entered CORE, or a Foundational
      concept was excluded.
    - To Pass 7 if the extension mechanism fails Attack 5, or the
      identity guarantee fails Attack 8.

Each rollback recommendation must cite the specific failure it responds
to. A vague recommendation ("Pass 4 feels off") is not acceptable. If
the Skeptic cannot cite a specific failure, there is no rollback.

## What the Skeptic must NOT do

1. Propose fixes. Rollback to a pass that owns the fix.
2. Propose new features.
3. Defend the architecture. The Skeptic is not the architect's advocate.
4. Pad the report. A short review that finds three real problems is more
   valuable than a long review that finds thirty cosmetic ones.
5. Hedge. "This might be a problem" is a failure of the Skeptic. Say
   whether it is a problem or not.
6. Accept "it's fine because the source says so." Source citations are
   not protection against bad architecture. If the source contains an
   over-engineering, the architecture should not reproduce it. Pass 3
   exists to catch such cases; if it didn't, the Skeptic records it.

## Output format — `planning/PRE_IMPLEMENTATION_REVIEW.md`

    # Pre-Implementation Review

    Pass: 8
    Role: Skeptic
    Date: <date>
    Sources: all planning artifacts

    Separation confirmed: <yes | no — if no, invalid run>

    ---

    ## Summary

    Attacks performed: <count>
    Findings:
      critical:   <count>   (require rollback)
      serious:    <count>   (require a DR)
      minor:      <count>   (recorded, no action)
      dismissed:  <count>   (attacked and survived)

    Verdict: <PASS | RETURN TO PASS N | ESCALATE TO HUMAN>

    ---

    ## Critical findings

    ### <CRIT-NNN> — <short title>

    Attack: <which of the ten>
    Target: <element of the architecture>
    Nature of failure:
    Rollback target: Pass N
    Reason rollback is required (not merely preferred):

    (repeat)

    ---

    ## Serious findings

    ### <SER-NNN> — <short title>

    Attack:
    Target:
    Nature:
    Required: DR-NNNN in the standard format

    (repeat)

    ---

    ## Minor findings

    <list with one-line descriptions>

    ---

    ## Dismissed attacks

    <list of attacks performed and found not to succeed>

    This section is required. It is the record that the Skeptic
    actually attacked rather than merely asserted.

    ---

    ## Process integrity

    Pass 1: <pass | hollow | missing>
    Pass 2: ...
    Pass 3: ...
    Pass 4: ...
    Pass 5: ...
    Pass 6: ...
    Pass 7: ...

    If any pass is marked hollow or missing, the corresponding artifact
    should be re-produced before the architecture proceeds.

    ---

    ## Confirmation of what survived

    The following were attacked and did not fail. They should be
    preserved through any rollback:

    <list>

    ---

    ## Coverage

    Attacks attempted: <count>
    Attacks succeeded: <count>
    Attacks failed: <count>
    Rollback recommendations: <count>
    Known limitations of this review: <...>

## After producing output

Update `BUILD_STATUS.md`:

- If verdict is PASS:
    - mark PASS 8 CLOSED
    - set current pass to PASS 9
- If verdict is RETURN TO PASS N:
    - set current pass back to PASS N
    - leave PASSes N+1 through 8 in a state marked `superseded`
    - set next allowed action to "Re-run Pass N with the Skeptic's
      findings as input"
- If verdict is ESCALATE TO HUMAN:
    - leave PASS 8 open
    - produce a DECISION REQUIRED prompt

Then stop.

---

# Notes for the human reviewer

This is the pass most likely to be performed badly — by which I mean
either too gently or too harshly.

Too gently: the review reports "no critical findings" and passes.
This is possible but rare. If it happens on the first run, the human
should read the "Dismissed attacks" section carefully. A Skeptic who
dismissed every attack probably didn't actually attack.

Too harshly: the review produces twenty critical findings and
recommends rolling back every pass. This is also a failure. The Skeptic
is not trying to be maximally destructive; it is trying to find the
failures that matter. A review that finds everything wrong has found
nothing wrong — it has simply refused to prioritize.

The sweet spot is roughly:

    0–2 critical findings
    2–5 serious findings
    several minor findings
    many dismissed attacks

A review with this shape is trustworthy. A review with any other shape
should be re-run.

One specific thing to check: does the review cite specific elements of
`MINIMAL_ARCHITECTURE.md`, or does it speak in generalities? A finding
like "the architecture contains speculative requirements" is not a
finding. A finding like "PRIM-005 (Bridge) is classified as CORE, but
Doc III §10 lists it as a specialized entity type that does not appear
in the MVP boundary from §16" is a finding. If the review cannot cite
specific elements, it was not actually a review.

The most important finding this pass produces is a rollback. A rollback
is not a failure of the process. It is the process working as designed.
If the Skeptic never recommends a rollback across the entire project,
the Skeptic is not doing its job. If it recommends a rollback every
time, the architecture is not doing its job.