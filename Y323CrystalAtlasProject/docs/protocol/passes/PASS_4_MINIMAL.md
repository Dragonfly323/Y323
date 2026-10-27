# PASS 4 — Minimal Core

## Goal

Construct the smallest architecture that faithfully satisfies the
Foundational documents. Every primitive, every relation type, every
retained entity class must be justified. Everything not justified is
removed.

The Minimalist Architect is explicitly empowered to delete proposed
architecture. It is not empowered to invent requirements.

## Inputs

- `planning/ARCHIVE_REPORT.md`
- `planning/ARCHITECTURE_MAP.md`
- `planning/GLOSSARY.md`
- `planning/CONFLICT_REPORT.md`
- `docs/decisions/DR-*.md` (all resolved and open)
- Foundational documents (reference only)

Do not read the Field Guide (Doc IV) or Vision documents (Docs V-a, V-b).

## Precondition: BLOCKING conflicts

If any DR marked BLOCKING is still OPEN, this pass does not run.
The human decides or defers first. Record the deferral in the DR.

MATERIAL conflicts may remain OPEN. If the pass proceeds with OPEN
MATERIAL DRs, every affected section of the output must cite the
relevant DR and mark itself as provisional on that decision.

## What the Minimalist Architect may do

1. Propose a core primitive set.
2. Propose a core relation vocabulary.
3. Classify each concept as one of:
   - CORE
   - EXTENSION
   - DERIVED
   - ATTRIBUTE
   - VIEW
   - DEFERRED
   - EXTERNAL
4. Remove proposed concepts.
5. Ask a DECISION REQUIRED question when the smallest architecture
   requires a choice the source documents do not resolve.

## What the Minimalist Architect may NOT do

1. **Invent requirements.** Every CORE item must trace to an Archive
   Report ID. If it does not, it does not enter CORE.
2. **Restate the source without testing it.** Doc III §2 names six
   primitives. That is a starting point. The pass must test whether each
   is genuinely needed, and whether any can be derived from the others.
3. **Confuse "needed for the vision" with "needed for V1."** The Field
   Guide, applications, agents, games, and interfaces are all outside V1
   by construction.
4. **Apply the 3–7 rule as a hard constraint.** It is a heuristic.
   Exceeding 7 requires justification. Falling below 3 does not require
   padding.
5. **Resolve conflicts.** OPEN DRs stay open. The architecture adapts
   around them or is marked provisional.
6. **Skip the justification step.** Every retained item must answer the
   standard justification questions (below).
7. **Produce application or interface design.** No API specifications,
   no UI, no agent behavior. Only the substrate.

## The standard justification questions

For every proposed primitive, every relation type, and every retained
entity class, answer all seven:

    J1. Which Archive Report ID requires this?
    J2. What is the preference-order position at which it lands?
        (see below)
    J3. Can it be represented as an attribute of an existing primitive?
    J4. Can it be derived rather than stored?
    J5. Can it be represented as a typed relation rather than an entity?
    J6. Does it constrain V1, or only a future version?
    J7. What breaks if it is removed?

If J3, J4, or J5 is answered "yes," the item does not enter CORE as an
entity. It enters at the appropriate lower level.

## The preference order

Every concept must be placed at the highest (most reductive) level it
can occupy:

    1. attribute on an existing entity
    2. typed relation
    3. derived value
    4. extension
    5. new entity
    6. new primitive

New primitives require the strongest justification. Most concepts should
land at levels 1–4.

## The 3–7 test

At each conceptual layer of the proposed architecture — primitives,
core relation types, entity categories, state classes — count the
concepts.

- 3–7: proceed.
- >7: either decompose, justify in a Decision Record, or defer some to
       EXTENSION.
- <3: do not invent new concepts to satisfy symmetry.

Record the count at every layer in the output.

## Required output sections

The output file is `planning/MINIMAL_ARCHITECTURE.md`. It must contain:

### 1. Core primitives

The smallest set of entity types the V1 schema requires.

For each:

    ### <PRIM-NNN> <name>

    Definition: <one sentence, source-faithful>
    Source: <Archive Report IDs>
    Justification:
      J1: ...
      J2: <level reached>
      J3: ...
      J4: ...
      J5: ...
      J6: ...
      J7: ...
    Layer: CORE
    Provisional on: <DR-NNNN if any, otherwise none>

### 2. Core relation vocabulary

The smallest set of relation types V1 requires.

For each:

    ### <REL-NNN> <name>

    Definition:
    Source:
    Justification:
      (same seven questions, adjusted for relations)
    Direction: directional | symmetric | N-ary
    Layer: CORE
    Provisional on: <DR-NNNN if any>

Relations that appear in the Foundational documents but are not in V1
are listed in section 6 (Deferred).

### 3. Attribute surface

Attributes that live on primitives rather than as entities. Include the
attribute → entity graduation path: which attributes, if they became
complex, would be promoted to entities, and by what rule.

### 4. Derived quantities

Anything the schema does not store but can compute from canonical state.
Each entry must state the derivation.

### 5. State model

CANONICAL / EXPERIMENTAL / BRANCH / HISTORICAL. Confirm or correct
against Doc III §15. If the pass proposes a change, cite the source and
justify.

### 6. Deferred to EXTENSION

Everything named in the Foundational documents that is not in V1.
Each entry must state why it is deferred, not merely that it is.

Deferral reasons:

    - requires a storage technology not yet selected
    - requires a capability that would violate the 3–7 rule
    - belongs to a layer above the schema (ontology, application)
    - depends on an OPEN DR
    - no V1 requirement cites it
    - it is a Vision or Field Guide concept, not Foundational

### 7. Explicitly excluded

Anything that might be mistaken for V1 material and must not be.

Examples that belong here unless a Foundational document overrides:

    - The Field Guide's exploration mechanics
    - The Asimyth Game's physical-world layer
    - Machine Resonance interface qualities
    - Automated discovery, quest generation, agent ecosystems
    - Game mechanics, achievements, progression
    - Visualization, rendering, multimodality
    - Formal proof execution (binding records are in scope; theorem
      provers are not)

### 8. 3–7 audit

Table of every conceptual layer with its count and disposition.

    Layer                     Count   Disposition
    core primitives           <n>     pass | justify | decompose
    core relation types       <n>     ...
    state classes             <n>     ...
    ...

### 9. MVP boundary

Restate Doc III §16's MVP list as the pass understands it, with each
element marked:

    CONFIRMED  — required for V1
    NARROWED   — required, but interpreted more tightly than Doc III §16
    DEFERRED   — removed from V1, with reason

Do not extend Doc III §16. If the pass believes Doc III §16 is
incomplete, record that as a DECISION REQUIRED, not as a silent addition.

### 10. Test of faithfulness

Answer the two questions from Doc III §17:

    1. Can the schema faithfully represent what we currently know?
    2. Can it absorb what we discover next?

For each, cite the specific sections of MINIMAL_ARCHITECTURE.md that
support the answer. If either answer is "not yet," record which DR is
blocking.

### 11. Open decisions this pass produces

Any new DECISION REQUIRED that arose during construction. Each gets a
DR in `docs/decisions/` in the standard format.

### 12. Coverage

    Primitives proposed: <n>
    Primitives removed: <n>
    Relations proposed: <n>
    Deferred items: <n>
    Excluded items: <n>
    Provisional sections: <n>
    Open DRs referenced: <list>
    Open DRs produced: <list>

## Output format — `MINIMAL_ARCHITECTURE.md`

    # Minimal Architecture

    Pass: 4
    Role: Minimalist Architect
    Date: <date>
    Sources: ARCHIVE_REPORT.md, ARCHITECTURE_MAP.md, GLOSSARY.md,
             CONFLICT_REPORT.md, DR-*.md

    Status: <final | provisional on DR-NNNN, DR-NNNN, ...>

    ---

    <sections 1–12 as above>

## After producing output

Update `BUILD_STATUS.md`:
- mark PASS 4 as CLOSED if no BLOCKING decision was produced
- if BLOCKING decisions were produced: leave PASS 4 OPEN and list them
- if closed: set current pass to PASS 5 — Complexity
- if open: set next allowed action to "Await human decisions on
  BLOCKING DRs from Pass 4; do not begin Pass 5"

Then stop. Do not begin Pass 5.

---

# Notes for the human reviewer

This is the first pass whose output is arguable on grounds other than
fidelity. Two reviewers can read the Foundational documents and produce
two different MINIMAL_ARCHITECTURE.md files, both faithful, and the
choice between them is a real choice.

The pass is successful if:

- Every CORE item cites an Archive Report ID.
- Every CORE item answers the seven justification questions.
- At least a few items appear under "deferred" that a less disciplined
  pass would have kept.
- The 3–7 audit has a non-trivial disposition column.
- The MVP boundary is narrower than or equal to Doc III §16, never wider.

The pass has failed if:

- It proposes more than 7 core primitives without a Decision Record.
- Any justification question is answered with "obvious" or "standard."
- Any CORE item is justified by a Vision document.
- The MVP boundary is wider than Doc III §16.
- It resolves an OPEN conflict silently.
- It contains API design, UI design, or application design.

If the pass has failed, do not attempt to salvage the output. Send it
back. The point of the pass is to produce a small architecture, and a
large architecture produced by a Minimalist Architect is a signal that
the pass was not performed.