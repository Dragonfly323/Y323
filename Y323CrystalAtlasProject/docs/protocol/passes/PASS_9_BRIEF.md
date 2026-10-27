# PASS 9 — Brief

## Goal

Translate the approved architecture into an implementation plan concrete
enough to execute after the Implementation Gate opens.

The Implementation Planner does not begin implementation. It specifies
what implementation will consist of, in what order, with what acceptance
criteria, and with what boundary of agent freedom.

## Inputs

All planning artifacts:

- `planning/SOURCE_BASELINE.md`
- `planning/ARCHIVE_REPORT.md`
- `planning/ARCHITECTURE_MAP.md`
- `planning/GLOSSARY.md`
- `planning/CONFLICT_REPORT.md`
- `planning/MINIMAL_ARCHITECTURE.md`
- `planning/COMPLEXITY_AUDIT.md`
- `planning/SYSTEM_BOUNDARIES.md`
- `planning/VERSIONING.md`
- `planning/PRE_IMPLEMENTATION_REVIEW.md`
- `docs/decisions/DR-*.md`

## Precondition

This pass does not run if:

1. Any prior planning artifact is missing.
2. Any DR marked BLOCKING is still OPEN.
3. `PRE_IMPLEMENTATION_REVIEW.md` lists any critical finding whose
   rollback target has not been re-run.
4. Any pass in the process-integrity section of the review is marked
   `hollow` or `missing`.

If any of the four conditions holds, the pass records the condition,
updates `BUILD_STATUS.md`, and stops. The gate cannot be approached from
an incomplete architecture.

## What the Implementation Planner may do

1. Specify the repository structure for the post-Gate implementation.
2. Specify the module decomposition at the logical level.
3. Specify logical interfaces (operations the system must support).
4. Specify the logical schema realization (how the canonical logical
   model from `MINIMAL_ARCHITECTURE.md` becomes a persistent form).
5. Specify the architectural tests A–G as concrete, falsifiable tests.
6. Specify the milestone sequence.
7. Specify task dependencies.
8. Specify acceptance criteria per milestone.
9. Specify the development tooling *categories* required.
10. Specify what remains for the implementation agent to decide, and
    what does not.

## What the Implementation Planner may NOT do

1. **Write code.** Not production code, not scaffold, not
   pseudo-implementation. The brief describes, it does not implement.
2. **Commit to technology.** No database, no frontend framework, no
   agent framework, no LLM provider, no deployment platform, no
   visualization library. The brief specifies what the system must do;
   the choice of what it is made of is deferred to the implementation
   phase or to a technology-decision DR authored after the gate.
3. **Add features.** Every capability in the brief must trace to
   `MINIMAL_ARCHITECTURE.md` §1–§5 or to the MVP boundary in §9.
   Anything else is a leak.
4. **Expand the MVP.** The MVP is what `MINIMAL_ARCHITECTURE.md` §9
   approved. The brief may decompose it into milestones. It may not
   extend it.
5. **Resolve open DRs.** If a DR is open, the brief must either avoid
   the affected area or mark the affected section provisional.
6. **Design the interface.** No API design, no UI, no query language
   syntax, no visualization. Interfaces at the logical level only.
7. **Design the application layer.** No game, no agent ecosystem, no
   interface runtime.
8. **Specify the development environment beyond categories.** "A version
   control system" is a category. "Git with signed commits on a
   self-hosted Forgejo instance" is a technology commitment.
9. **Schedule anything.** No dates, no durations, no effort estimates.
   The brief is a sequence, not a calendar.
10. **Promise the gate will pass.** The gate is opened by the human. The
    brief prepares for it.

## Required output sections

The output is `planning/IMPLEMENTATION_BRIEF.md`. It must contain:

### 1. Scope

A restatement, in one paragraph, of what V1 is. Cites
`MINIMAL_ARCHITECTURE.md` §9. Does not re-interpret.

### 2. Repository structure

The layout of the implementation repository. Directories and their
purpose. Naming conventions for modules and files. Must be consistent
with the pre-build structure from `BUILD_PROTOCOL.md` §XI, which
continues into the post-Gate repo.

Structure should be small. If it needs more than two levels of
directory nesting to describe, it is probably wrong.

### 3. Modules

Each logical module with:

    - name
    - purpose (one sentence)
    - responsibility
    - what it depends on
    - what depends on it
    - which elements of MINIMAL_ARCHITECTURE.md it realizes

Modules must not depend on modules that depend on them. If a cycle
exists, one of the modules is not a module.

### 4. Logical interfaces

Operations the system must expose. Not API syntax. Not endpoints. The
set of things the system can be asked to do, and the set of things it
produces.

For each operation:

    - name
    - purpose
    - inputs (conceptual, not typed)
    - outputs (conceptual, not typed)
    - which architectural element it realizes
    - which modules participate

Interfaces are organized by role: canonical-state operations, query
operations, provenance operations, version operations, artifact
operations.

The Mathematical Engine interface is NOT in this section. It is
post-V1.

### 5. Schema realization strategy

How the canonical logical model from `MINIMAL_ARCHITECTURE.md` §1–§5
becomes a persistent form, at the level of *what must be preserved*,
not *how*.

For each primitive:

    - what must be stored
    - what may be derived
    - what must be indexed for retrieval
    - what must be versioned

For relations:

    - how typed relations are represented (as first-class records, per
      Doc III §4)
    - how provenance attaches to relations
    - how symmetric relations are distinguished from directional ones

For version history:

    - what is stored per revision
    - what is queryable
    - how "revert" is represented (as a new state, per Doc III §11)

The strategy must be technology-agnostic. If a specific storage
technology is required to describe a step, the step is stated too
concretely.

### 6. Architectural tests A–G

The tests from `BUILD_PROTOCOL.md` §XIV, instantiated as concrete,
falsifiable tests against the V1 corpus.

For each test:

    ### Test <letter> — <name>

    Purpose:
    Given:
    When:
    Then:
    Pass condition:
    Failure condition:
    Which architectural element this test verifies:

The tests must be runnable by hand or by a test harness. "Represent
faithfully" is not a pass condition. "Every entity in the frozen source
corpus is representable as an entity whose type is one of the CORE
primitives, without coercion" is.

The corpus for Test A is defined by `SOURCE_BASELINE.md` and
`ARCHIVE_REPORT.md`. The corpus for Test G is defined by the extension
scenarios from `PRE_IMPLEMENTATION_REVIEW.md` Attack 5.

### 7. Milestone sequence

Small number of milestones. Ideally three to five. Each milestone:

    ### Milestone <N> — <name>

    Goal:
    Deliverable:
    Depends on:
    Acceptance criteria: <list of testable criteria>
    What is explicitly NOT in this milestone:
    Estimated effort: (omit — the brief does not estimate)

Milestones should build strictly forward. Milestone N+1 depends on N.
No milestone should require a decision that is not yet made.

The first milestone should be the smallest implementation that can run
Test A. Not the smallest that runs all tests. Not the smallest that is
"complete." The smallest that proves the schema can represent the
corpus.

### 8. Task dependencies

A dependency graph of tasks within each milestone. Tasks are named at a
granularity that an agent can pick up and complete. Task names are
descriptive, not schedules.

### 9. Acceptance criteria per milestone

For each milestone, a checklist of what must be true for the milestone
to be considered complete. Each criterion must be testable. Each
criterion must trace to an architectural element.

### 10. Development tooling categories

The categories of tooling the implementation will require, without
naming specific tools:

    - version control
    - test execution
    - static analysis (if the chosen language category requires it)
    - schema definition
    - state snapshotting
    - migration execution (post-S_0 only)
    - documentation
    - continuous integration (if the project structure warrants it)

For each category, one sentence describing what it must provide. Not
which tool provides it.

### 11. What the implementation agent decides

A list of decisions explicitly deferred to the implementation phase.
These are decisions the architecture does not constrain and that the
implementing agent may make within the boundary of the brief.

Examples:

    - choice of programming language
    - choice of storage technology
    - choice of test framework
    - internal code organization within a module
    - naming conventions beyond the module level
    - file formats for state snapshots

### 12. What the implementation agent does not decide

A list of decisions the implementation phase may not revisit. These
are settled by the architecture and locked until a major version
change.

Examples:

    - the primitive set
    - the core relation vocabulary
    - the identity stability guarantee
    - the three version tracks
    - the extension mechanism
    - the exclusion of application and interface layers

### 13. Deviation protocol

What the implementing agent does if it discovers that the brief is
wrong — that a milestone is not achievable as specified, or that the
architecture does not fit a concrete case.

The answer: the agent writes a Decision Record. It does not silently
diverge. It does not rewrite the brief. The DR is reviewed by the human,
who may accept the deviation, request a re-run of the relevant pass, or
return the milestone.

### 14. IMPLEMENTATION_READINESS reference

Restate the IMPLEMENTATION_READINESS record from
`BUILD_PROTOCOL.md` §XVIII. The brief does not approve it. The brief
records that it is the document the gate will approve.

    Human approval: PENDING
    IMPLEMENTATION AUTHORIZATION: PENDING

### 15. Coverage

    Modules specified: <count>
    Logical operations specified: <count>
    Tests instantiated: <count> / 7
    Milestones defined: <count>
    Tasks defined: <count>
    Decisions deferred to implementation: <count>
    Decisions locked: <count>
    Open DRs referenced: <list>
    Open DRs produced: <list>

## Output format

    # Implementation Brief

    Pass: 9
    Role: Implementation Planner
    Date: <date>
    Source: all planning artifacts
    Architecture version: <S_v from VERSIONING.md>
    Protocol version: <from BUILD_PROTOCOL.md>

    Status: <final | provisional on DR-NNNN, ...>

    ---

    <sections 1–15>

## After producing output

Update `BUILD_STATUS.md`:

- If no BLOCKING decision was produced:
    - mark PASS 9 CLOSED
    - set current pass to `GATE — awaiting human authorization`
    - set next allowed action to "Human reviews IMPLEMENTATION_BRIEF.md
      and IMPLEMENTATION_READINESS; authorization is a human decision,
      not an agent action"
- If a BLOCKING decision was produced:
    - leave PASS 9 OPEN
    - list the blocking DRs
    - set next allowed action to "Await human decisions on BLOCKING
      DRs from Pass 9"

Then stop. Do not approach the gate.

---

# Notes for the human reviewer

This is the last artifact before the gate. It is also the artifact that
determines what the implementation agent does when it starts working.

Three things to check first:

**1. Does the brief avoid technology commitment?** The most common
failure of this pass is that the planner, in an earnest attempt to be
concrete, names a database. If `IMPLEMENTATION_BRIEF.md` contains the
name of a specific product, framework, or language, the pass has failed
its most important constraint. The brief describes capabilities, not
implementations of capabilities.

**2. Does the brief contain anything not in the MVP?** Compare §3–§5
of the brief against `MINIMAL_ARCHITECTURE.md` §9. Every module, every
operation, every schema element should trace. If something appears in
the brief that does not trace, the planner has smuggled in scope.

**3. Are the tests falsifiable?** Test A must be checkable by a human
in an afternoon, not by an oracle. "The system is faithful to the
corpus" is not a test. "Every entity from the frozen corpus maps to
exactly one canonical entity, and no two corpus entities map to the
same canonical entity, and every canonical entity traces to at least
one corpus entity" is.

Two things to check second:

**4. Is the milestone sequence short?** Three to five milestones is
expected. Ten is a red flag. The first milestone should produce
something runnable, not something "foundational."

**5. Does the deviation protocol exist?** The brief is going to be
wrong about something. The question is not whether the implementing
agent will find a mismatch; it's whether the protocol gives the agent a
way to report it without either silently diverging or stopping entirely.
If the deviation protocol is absent, add it before opening the gate.

The brief is not the last word. It is the first word of the
implementation phase, and it will be revised — not by rewriting it, but
by producing DRs that record where it was wrong. That is the correct
pattern. A brief that is never revised was either too vague to be
useful or too narrow to be honest.