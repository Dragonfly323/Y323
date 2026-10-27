# PASS 5 — Complexity

## Goal

Apply the 3–7 rule to `MINIMAL_ARCHITECTURE.md`. Confirm that the
architecture Pass 4 proposed is actually minimal, or send it back.

The Complexity Auditor is adversarial to Pass 4. It is not adversarial
to the Foundational documents.

## Inputs

- `planning/MINIMAL_ARCHITECTURE.md`
- `planning/ARCHIVE_REPORT.md` (reference)
- `docs/decisions/DR-*.md` (reference)

Do not re-derive the architecture. Do not re-read the Foundational
documents except to verify a specific citation.

## What this pass produces

One file: `planning/COMPLEXITY_AUDIT.md`

The file is short. Most of its length is the per-layer table.

## The 3–7 rule, restated

At any single conceptual layer, prefer 3–7 primary concepts.

- ≤7: proceed.
- >7: the responsible agent must either decompose, justify, defer, or
       escalate.
- <3: do not pad. Two is a valid count.

The rule is a heuristic. Its purpose is to prevent large flat taxonomies
that a human or agent cannot hold in mind at once.

## What counts as a "layer"

A layer is a set of concepts at the same altitude that a user or an
agent must hold in mind simultaneously.

Examples of layers in `MINIMAL_ARCHITECTURE.md`:

    - the core primitive set
    - the core relation vocabulary
    - the attribute surface (grouped by primitive)
    - derived quantities
    - state classes
    - each schema table's columns

A list of 40 archive items is not a layer. A list of 40 archive items
that a user must choose among while querying is.

## The audit procedure

For each layer:

1. Count.
2. If 3–7: mark `pass`.
3. If >7: apply the following tests in order:
   a. Can any items be grouped into a sublayer?
   b. Can any items be represented as relations rather than categories?
   c. Can any items be represented as attributes rather than entities?
   d. Can any items be derived rather than stored?
   e. Can any items be demoted to EXTENSION?
   f. If none of (a)–(e) apply, does a Decision Record justify the count?
4. If a test resolves the count, record the resolution. The pass does
   NOT edit `MINIMAL_ARCHITECTURE.md`. It records the required change and
   sends the pass back if the change is substantial.
5. If no test resolves the count and no DR justifies it, the layer fails
   the audit. Return to Pass 4.

## What counts as a complexity violation

1. A layer with >7 concepts and no DR justifying the count.
2. A concept in CORE whose justification answers J3, J4, or J5 "yes"
   (meaning it could have been placed lower and wasn't).
3. A CORE concept that duplicates another CORE concept.
4. An EXTENSION item that would be simpler as CORE (unlikely, but
   possible if Pass 4 over-defers for false minimalism).
5. An attribute that is effectively an entity in disguise (carries its
   own relations in practice).
6. A derived quantity that is stored as canonical state without
   justification.
7. A relation type that exists only to describe one specific edge.

## What is NOT a violation

1. More than 7 total concepts in the architecture. The rule applies per
   layer, not globally. The architecture may contain many concepts.
2. Fewer than 3 concepts in a layer. Do not pad.
3. A large archive list. Archive lists are not layers.
4. A large deferred list. Deferral is not a layer.
5. More than 7 sublayers if the top layer has ≤7 items. Layers nest.
6. A concept that appears in multiple layers. This is composition, not
   duplication, unless it is claimed as two different things.

## What to do with a violation

For each violation:

- If the resolution is obvious and mechanical (e.g., an attribute that
  clearly belongs at the attribute level), record the change required
  and mark the layer `fix-in-place`. Pass 5 does not edit the file;
  Pass 4 does.
- If the resolution requires a decision, create a DR.
- If the violation is trivial and the layer is genuinely fine, record
  the reasoning. A layer of 8 is not automatically wrong; it is
  automatically suspicious.

## Output format — `COMPLEXITY_AUDIT.md`

    # Complexity Audit

    Pass: 5
    Role: Complexity Auditor
    Date: <date>
    Source: MINIMAL_ARCHITECTURE.md

    ---

    ## Summary

    Layers audited: <n>
      pass: <n>
      fix-in-place: <n>
      DR required: <n>
      return to Pass 4: <n>

    Verdict: <PASS | RETURN TO PASS 4 | ESCALATE TO HUMAN>

    ---

    ## Layer table

    | Layer | Count | Disposition | Resolution / DR |
    |-------|-------|-------------|-----------------|
    | core primitives | 6 | pass | — |
    | core relation types | 8 | fix-in-place | merge REL-005 into REL-002 |
    | attribute groups | | | |
    | derived quantities | | | |
    | state classes | 4 | pass | — |
    | ... | | | |

    ---

    ## Violations

    ### <VIOLATION-NNN> — <layer>

    Nature:
    Test applied:
    Resolution:
      <fix-in-place | DR-NNNN | return to Pass 4>

    (repeat)

    ---

    ## Non-violations checked

    Layers considered and confirmed minimal:

    - <layer> — count <n>, reason pass

    ---

    ## Coverage

    Layers audited: <count>
    Layers with >7: <count>
    Layers with <3: <count>
    Layers with DR justification: <count>
    Known gaps: <...>

## After producing output

Update `BUILD_STATUS.md`:

- If verdict is PASS: mark PASS 5 CLOSED, set current pass to PASS 6.
- If verdict is RETURN TO PASS 4: leave PASS 4 as the current pass, note
  the required corrections, and set the current pass back to PASS 4.
- If verdict is ESCALATE TO HUMAN: leave PASS 5 open and produce a
  DECISION REQUIRED prompt.

Then stop.

---

# Notes for the human reviewer

This pass should produce a short report. If `COMPLEXITY_AUDIT.md` is
longer than `MINIMAL_ARCHITECTURE.md`, something has gone wrong — the
auditor has begun to redesign rather than audit.

A successful audit usually finds one or two fix-in-place items. Zero
findings is possible but suspicious; it suggests the auditor applied the
rule mechanically. More than five findings suggests Pass 4 was
over-ambitious and should probably be re-run rather than patched.

The one finding that most often appears: **a relation type that is
really an attribute**. Relations should be first-class only when they
carry their own identity, evidence, or status. A relation between two
entities that carries no additional information is an attribute of one
of them.

The one finding that should never appear: **"there are 15 core
primitives and that is fine."** If Pass 4 produced 15 core primitives,
Pass 5 does not accept a DR justifying it. It returns to Pass 4 for
decomposition. Fifteen core primitives is not a small footprint; it is a
schema waiting to happen.