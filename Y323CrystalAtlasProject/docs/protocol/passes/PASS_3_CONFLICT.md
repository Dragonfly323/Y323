# PASS 3 — Conflict

## Goal

Find inconsistencies in the Foundational source material before the
architecture is built on top of them. Frame each consequential inconsistency
as a Decision Record.

The Contradiction Hunter does NOT resolve conflicts. It frames them.
Resolution happens either through a human DECISION REQUIRED, or later,
or never (a conflict may legitimately remain OPEN indefinitely).

## Inputs

- `planning/ARCHIVE_REPORT.md` (source of raw materials)
- `planning/ARCHITECTURE_MAP.md` (Part A.6–A.10 in particular)
- `planning/GLOSSARY.md` (layer membership and conflict entries)
- Foundational documents (reference only, for verification)

Do not read the Field Guide (Doc IV) or Vision documents (Docs V-a, V-b).

## What counts as a conflict

A conflict exists when two Foundational statements cannot both be true, or
cannot both be implemented, without one being chosen over the other.

Six categories:

    C1  Definitional     — the same term is defined two different ways
    C2  Ontological      — the same entity is claimed to be two different
                           kinds of thing (e.g., primitive vs. derived)
    C3  Structural       — two lists, vocabularies, or decompositions
                           claim to describe the same structure but
                           disagree on members or count
    C4  Relational       — the same relationship between two entities is
                           described in incompatible terms
    C5  Methodological   — two statements prescribe incompatible processes
    C6  Epistemic        — two statements assign incompatible status to
                           the same claim

## What does NOT count as a conflict

The Contradiction Hunter must NOT flag:

1. **Different phrasing of the same claim.** "Status is not confidence"
   and "status ≠ evidence" are the same principle. Duplicates are Pass 2
   material, not Pass 3.
2. **A general statement and a specific instance.** Doc III §2 names six
   primitives and later names specific ones. This is specialization,
   not conflict.
3. **Different levels of description.** Mathematics, ontology, and schema
   are three layers. A claim at one layer is not in conflict with a claim
   at another layer unless the layers themselves claim to describe the
   same thing.
4. **Absence.** If Doc II says X and Doc III doesn't mention X, that is a
   coverage gap, not a conflict. Gaps go in the coverage report, not the
   conflict report.
5. **Hedged claims.** "May" vs. "must" is not a conflict unless the
   underlying claim is the same. "The schema may support X" is consistent
   with "the schema does not require X."
6. **The Build Protocol's own rules.** If Doc II has nine primitives and
   the protocol's 3–7 rule would prefer fewer, this is not a source
   conflict. It is a subject for the Complexity Audit (Pass 5).
7. **Field Guide or Vision material.** Those documents are not inputs.

## Conflict severity

Each conflict receives a severity:

    BLOCKING   — a later pass cannot proceed without a decision
    MATERIAL   — affects the architecture but not immediately
    COSMETIC   — terminology or phrasing, no architectural consequence

Only BLOCKING conflicts require a human DECISION REQUIRED during this
pass. MATERIAL and COSMETIC conflicts are recorded as Decision Records
with STATUS: OPEN and revisited when a later pass requires them.

## Decision Record creation

Every BLOCKING or MATERIAL conflict becomes a Decision Record.

COSMETIC conflicts are recorded in the conflict report but do not receive
their own DR unless a later pass requests one.

A DR that duplicates an item from ARCHIVE_REPORT.md Part 5
(Already-Decided) is not created. Instead, the conflict report notes that
the item was already settled and cites the source.

## Decision Record format

Create files at `docs/decisions/DR-NNNN-<slug>.md` using the format from
BUILD_PROTOCOL.md §IX. For conflicts where no decision has yet been made:

    Status: OPEN

    Context:
    <why this conflict matters; which later pass depends on it>

    Question:
    <the specific question the decision must answer>

    Options:
    A. <option>
    B. <option>
    C. <option>

    Decision:
    (none yet — STATUS: OPEN)

    Reason:
    (none yet)

    Consequences:
    Easier:
    Harder:

    Alternatives rejected:
    (none yet)

    Reversibility:
    <easy | moderate | difficult>

    Affected documents:
    <Doc N §M, ...>

    Affected components:
    <which architectural layer this decision constrains>

    Review trigger:
    <what future evidence would justify revisiting>

An OPEN DR is not a failure. It is a recorded state.

## The DECISION REQUIRED prompt

For each BLOCKING conflict, present a DECISION REQUIRED prompt to the human.
Do not combine multiple decisions into one prompt. One prompt per DR.

Format (from BUILD_PROTOCOL.md §XV):

    DECISION REQUIRED

    DR: DR-NNNN

    Question:
    Why it matters:
    Options: A / B / C
    Agent recommendation: <optional, and only if the agent has a
                           reasoned preference; the agent may decline to
                           recommend if the choice is genuinely open>
    Reversibility:
    Consequences:

If the human responds, record the response in the DR and set Status to
accepted. If the human defers, leave Status as OPEN and proceed.

## Output

Two files:

- `planning/CONFLICT_REPORT.md` — the register of every conflict found
- `docs/decisions/DR-NNNN-*.md` — one file per BLOCKING or MATERIAL conflict

### CONFLICT_REPORT.md format

    # Conflict Report

    Pass: 3
    Role: Contradiction Hunter
    Date: <date>
    Source: ARCHIVE_REPORT.md, ARCHITECTURE_MAP.md, GLOSSARY.md

    ---

    ## Summary

    Conflicts found: <total>
      BLOCKING: <count>   → <count> DRs, <count> resolved this pass
      MATERIAL: <count>   → <count> DRs
      COSMETIC: <count>   → no DRs
      Already-decided (not conflicts): <count>

    ---

    ## Conflicts

    ### <CONFLICT-NNN> — <short title>

    Severity: BLOCKING | MATERIAL | COSMETIC
    Category: C1 | C2 | C3 | C4 | C5 | C6
    DR: DR-NNNN (if any)

    Sources:
      <Doc N §M>  formulation A
      <Doc N §M>  formulation B

    Nature of conflict:
    <description>

    Architectural consequence:
    <what a later pass will be forced to choose, if this is not resolved>

    Options:
    A. <...>
    B. <...>

    (repeat for each conflict)

    ---

    ## Non-conflicts checked

    The following were considered and confirmed not to be conflicts:

    - <Doc N §M> vs. <Doc N §M> — <reason>

    ---

    ## Coverage

    Conflicts tested: <count>
    Conflicts confirmed: <count>
    Conflicts dismissed: <count>
    Known gaps: <...>

## Known candidates to investigate

The following were flagged by Pass 2 and must be explicitly addressed
in this pass (recorded either as conflicts or as non-conflicts):

1. **Primitive count.** Doc II §1 names nine primitive entity types.
   Doc III §2 names six primitives. Both claim to describe the deepest
   level. (Likely C2 + C3, BLOCKING.)

2. **Relation vocabulary.** Doc II §2 names eight relation types.
   Doc III §4 names twelve relation words. Whether these are the same
   vocabulary at two altitudes or two incompatible vocabularies is
   undecided. (Likely C3, BLOCKING.)

3. **Status vocabulary.** Doc II §3 names nine status codes (D, A, C, O,
   Co, P, I, H, X). Doc III §7 names ten status values (definition,
   assumption, computed, observed, conjecture, theorem, interpretation,
   hypothesis, refuted, unknown). Doc III adds "refuted" and "unknown";
   Doc II does not. Doc II includes "cross-domain correspondence" (X);
   Doc III does not. (Likely C3, MATERIAL.)

4. **The central object's name.** Doc 0 calls it Y_323. Doc I calls it
   C (script-C). Doc II calls it Crystal7 / C_7. Whether these are the
   same object with different names, or two closely related objects, is
   not stated. (Likely C1, MATERIAL.)

5. **"Domain" usage.** Doc I uses "domain" to mean a mathematical field.
   Doc II §4 uses "domain" as a viewing context with many-to-many
   membership. Doc III §5 shows `domain=spectral_theory` as a single
   attribute. Whether domain is context, attribute, or relation is
   undecided. (Likely C1 + C4, MATERIAL.)

6. **"Bridge" usage.** Doc II §7 defines Bridge as a persistent named
   correspondence between representations. Doc III §10 lists Bridge as
   a specialized entity type. Whether Bridge is a relation, an entity,
   or both is undecided. (Likely C2, MATERIAL.)

These six are known candidates. The Contradiction Hunter must either
confirm each as a conflict or record a reasoned non-conflict, with
citations.

The list is not closed. Additional conflicts discovered during the pass
are recorded in the same format.

## After producing output

Update `BUILD_STATUS.md`:
- mark PASS 3 as CLOSED if no BLOCKING conflict is unresolved, otherwise
  leave PASS 3 as OPEN with a note listing the blocking DRs
- if closed: set current pass to PASS 4 — Minimal Core
- if open: set next allowed action to "Await human decisions on BLOCKING
  DRs; do not begin Pass 4"

Then stop. Do not begin Pass 4 until BLOCKING conflicts are either
resolved or explicitly deferred by the human.

---

# Notes for the human reviewer

The Contradiction Hunter is the pass most likely to over-produce. Six
BLOCKING conflicts would be a lot. Two or three would be expected.

If the pass returns with more than five BLOCKING conflicts, the first
human task is not to answer them but to ask whether some of them are
duplicates of each other, or whether some can be demoted to MATERIAL.

A conflict is not really BLOCKING unless Pass 4 (Minimal Core) will
literally be unable to proceed. Most conflicts are MATERIAL.