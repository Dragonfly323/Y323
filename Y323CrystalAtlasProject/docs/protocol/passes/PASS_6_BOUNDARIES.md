# PASS 6 — Boundaries

## Goal

Classify every capability named in the Foundational documents — and every
capability the Minimal Architecture silently acquired — into exactly one
of the seven boundary categories.

The Boundary Architect resists putting future functionality into V1. It
also resists the opposite failure: forbidding a Foundational requirement
because it feels large.

## Inputs

- `planning/MINIMAL_ARCHITECTURE.md`
- `planning/COMPLEXITY_AUDIT.md`
- `planning/ARCHIVE_REPORT.md`
- `planning/CONFLICT_REPORT.md`
- `docs/decisions/DR-*.md`
- `planning/SOURCE_BASELINE.md` (to verify source class of any cited item)

Do not read the Field Guide (Doc IV) or Vision documents (Docs V-a, V-b)
except to check whether a capability named in Pass 4 actually originated
there. Pass 4's output is the authoritative record of what was proposed;
the Field Guide and Vision documents are consulted only to confirm
provenance.

## The seven categories

    CORE         Necessary to preserve the fundamental Atlas model.
                 Enters V1.

    EXTENSION    Useful capability addable without changing the core.
                 Does not enter V1, but the schema must not foreclose it.

    VIEW         A projection of existing Atlas state. Not a source of
                 state. Rendered from canonical data.

    DERIVED      Computable from canonical information. Not stored as
                 canonical.

    EXPERIMENTAL Not yet sufficiently understood or stable. Isolated from
                 canonical state until it stabilizes.

    DEFERRED     Explicitly desired but intentionally postponed. Belongs
                 to the Atlas's own future, not to another system.

    EXTERNAL     Belongs to another system. Referenced, not absorbed.

Each capability receives exactly one classification. A capability that
appears to belong in two categories is two capabilities and must be
split, or one category is wrong.

## The source class rule

This is the pass that enforces the source document classes at the
architecture level.

    From Docs 0, I, II, III (Foundational):
      May be classified as any of the seven categories.
      May be CORE if it satisfies the Pass 4 justification questions.

    From Doc IV (Growth):
      Default classification: DEFERRED.
      May be promoted to CORE only if a Foundational document explicitly
      requires the capability.
      A promotion requires a DR.

    From Docs V-a, V-b (Vision):
      Default classification: EXTERNAL.
      The Atlas is the substrate. The Asimyth Game and the human-facing
      interface are consumers. They do not live inside the Atlas.
      May never be classified as CORE.
      May never be classified as EXTENSION.
      May be classified as VIEW only if the capability is a pure
      projection of canonical state (unlikely; most interface features
      are not).

The rule exists to prevent two failure modes:

1. A Growth or Vision concept entering CORE because it "feels
   foundational."
2. A Foundational concept being excluded because it "sounds like a
   Vision concept."

The first is a leak. The second is a loss. This pass catches both.

## The consequence rule

Each classification carries a consequence that the audit must enforce.

    CORE         → must appear in V1 scope
    EXTENSION    → must NOT appear in V1, but no schema element may make
                    it impossible to add later
    VIEW         → must be derivable; must not be a source of state
    DERIVED      → must be computable; must not be stored canonically
    EXPERIMENTAL → must be isolated from canonical state
    DEFERRED     → must be recorded with a reason
    EXTERNAL     → must be referenceable by identifier; may not be
                    imported into canonical state

If a capability's classification and its treatment in
`MINIMAL_ARCHITECTURE.md` disagree, the audit records a violation.

## The audit procedure

### Step 1 — Enumerate

Build the complete list of capabilities from:

    a. Every item in MINIMAL_ARCHITECTURE.md §1–§5 (primitives, relations,
       attributes, derived, state)
    b. Every item in MINIMAL_ARCHITECTURE.md §6 (Deferred)
    c. Every item in MINIMAL_ARCHITECTURE.md §7 (Excluded)
    d. Every capability named in the Foundational documents that is
       neither in (a) nor in (b) nor in (c)
    e. Every capability named in the Field Guide or Vision documents
       that was cited anywhere in Pass 4's output

Category (d) is the one that catches omissions. Category (e) is the one
that catches leaks.

### Step 2 — Classify

For each item, assign one of the seven categories.

For each item, record the reason in one line. "Reason: named in Doc III
§10 as a specialized entity type" is sufficient. "Reason: feels
foundational" is not.

### Step 3 — Cross-check against Pass 4

For each CORE item: does it appear in the V1 scope of
`MINIMAL_ARCHITECTURE.md`? If not, the pass and the architecture
disagree. Record a violation.

For each EXTENSION item: does anything in
`MINIMAL_ARCHITECTURE.md` foreclose it? If so, record a violation.

For each VIEW item: is it treated as a source of state anywhere? If so,
record a violation.

For each DERIVED item: is it stored as canonical state? If so, record a
violation.

For each EXPERIMENTAL item: does it appear in the canonical state model?
If so, record a violation.

For each EXTERNAL item: does any schema primitive reference its internal
structure, rather than its identifier? If so, record a violation.

### Step 4 — Detect leaks

The following are leaks and must be flagged:

1. A Field Guide concept classified as CORE without a DR.
2. A Vision concept classified as CORE or EXTENSION.
3. A schema primitive whose justification, in Pass 4's output, cites a
   Vision document.
4. An interface design element (API surface, query language, visualization
   primitive) inside `MINIMAL_ARCHITECTURE.md`.
5. A game mechanic, achievement, or exploration primitive inside
   `MINIMAL_ARCHITECTURE.md`.

### Step 5 — Detect losses

The following are losses and must be flagged:

1. A Foundational capability that appears nowhere in Pass 4's output —
   neither CORE, nor EXTENSION, nor DEFERRED, nor EXTERNAL.
2. A Foundational capability classified as EXTERNAL when the Atlas is
   supposed to contain it.
3. A Foundational invariant (from ARCHIVE_REPORT Part 4) that is not
   enforced by any V1 mechanism.

### Step 6 — Verify the MVP boundary

Restate the MVP boundary from `MINIMAL_ARCHITECTURE.md` §9 and confirm:

    - every MVP item is classified CORE
    - no MVP item is classified EXTENSION, VIEW, DERIVED, EXPERIMENTAL,
      DEFERRED, or EXTERNAL
    - no item outside the MVP is classified CORE

If any MVP item is not CORE, or any CORE item is not MVP, the audit has
found a boundary violation.

## Output format — `SYSTEM_BOUNDARIES.md`

    # System Boundaries

    Pass: 6
    Role: Boundary Architect
    Date: <date>
    Source: MINIMAL_ARCHITECTURE.md, COMPLEXITY_AUDIT.md,
            ARCHIVE_REPORT.md, SOURCE_BASELINE.md

    Status: <final | provisional on DR-NNNN, ...>

    ---

    ## Summary

    Capabilities classified: <count>

    CORE:         <n>
    EXTENSION:    <n>
    VIEW:         <n>
    DERIVED:      <n>
    EXPERIMENTAL: <n>
    DEFERRED:     <n>
    EXTERNAL:     <n>

    Leaks detected:  <count>
    Losses detected: <count>
    Violations:      <count>

    Verdict: <PASS | RETURN TO PASS 4 | ESCALATE TO HUMAN>

    ---

    ## Classification table

    | ID | Capability | Category | Source | Reason |
    |----|------------|----------|--------|--------|
    | C-001 | Entity | CORE | Doc III §3 | Foundational primitive |
    | C-002 | Relation | CORE | Doc III §4 | Foundational primitive |
    | ... | | | | |

    ---

    ## CORE — V1 scope

    <list with one-line justification each>

    ## EXTENSION — addable later

    <list with the specific extension point each will attach to>

    ## VIEW — projections

    <list with the canonical state each projects>

    ## DERIVED — computed

    <list with the derivation of each>

    ## EXPERIMENTAL — isolated

    <list with the isolation mechanism>

    ## DEFERRED — postponed

    <list with the reason for postponement>

    ## EXTERNAL — referenced

    <list with the identifier scheme by which each is referenced>

    ---

    ## Leaks

    ### <LEAK-NNN> — <capability>

    Classified in MINIMAL_ARCHITECTURE.md as: <category>
    Should be: <category>
    Reason:
    Required fix:

    (repeat)

    ---

    ## Losses

    ### <LOSS-NNN> — <capability>

    Named in: <Foundational document, section>
    Status in MINIMAL_ARCHITECTURE.md: <absent | misclassified>
    Required fix:

    (repeat)

    ---

    ## Violations

    ### <VIOLATION-NNN> — <type>

    <details>

    (repeat)

    ---

    ## MVP boundary verification

    MVP items: <count>
      classified CORE: <count>
      classified otherwise: <count>

    CORE items: <count>
      in MVP: <count>
      outside MVP: <count>

    ---

    ## Coverage

    Capabilities enumerated: <count>
    Capabilities classified: <count>
    Capabilities unclassifiable: <count>
    Known gaps: <...>

## After producing output

Update `BUILD_STATUS.md`:

- If verdict is PASS: mark PASS 6 CLOSED, set current pass to PASS 7.
- If verdict is RETURN TO PASS 4: leave PASS 4 as the current pass, note
  the required corrections, and set the current pass back to PASS 4.
- If verdict is ESCALATE TO HUMAN: leave PASS 6 open and produce a
  DECISION REQUIRED prompt.

Then stop.

---

# Notes for the human reviewer

This pass has one job that matters more than all its other jobs
combined: **it catches leaks from the Vision documents.** If
`MINIMAL_ARCHITECTURE.md` contains a single interface concern, a single
game mechanic, a single achievement, or a single narrative-driven
query pattern, Pass 6 is the last pass before the Implementation Brief
where that leak can be caught cheaply.

The second job that matters: **it catches losses.** If a Foundational
capability — say, the epistemic ledger from Doc 0 §8, or the canonical
versus experimental state distinction from Doc III §15 — silently
dropped out of Pass 4's output, the Implementation Brief will never know
it was supposed to exist. Pass 6 is the last chance to notice.

If the pass returns PASS on the first try, that is unusual and worth
sanity-checking. If it returns PASS with zero leaks and zero losses
after one read-through of `MINIMAL_ARCHITECTURE.md`, the auditor may not
have enumerated thoroughly. If it returns PASS with more than five
leaks, Pass 4 was over-inclusive and probably should be re-run rather
than patched.

A useful heuristic: the number of EXTERNAL items should be roughly
proportional to the volume of Vision material that was checked. If the
auditor reports zero EXTERNAL items after consulting the Vision
documents, the Vision documents were probably not actually consulted —
or worse, their material silently entered CORE.