# PASS 7 — Evolution

## Goal

Define the version contract under which the Atlas's canonical state may
change over time. Establish identity stability, schema versioning, and
compatibility guarantees such that the system can grow without
destroying history or forcing rewrites.

The Version Architect does not design future features. It designs the
mechanisms by which features may be added later without breaking what
V1 established.

## Inputs

- `planning/MINIMAL_ARCHITECTURE.md`
- `planning/COMPLEXITY_AUDIT.md`
- `planning/SYSTEM_BOUNDARIES.md`
- `planning/ARCHIVE_REPORT.md` (Part 4 — permanent invariants)
- `docs/decisions/DR-*.md`

The source documents' relevant sections are:

    Doc III §3   Entity identity
    Doc III §11  Versioning and evolution
    Doc III §17  Schema invariants
    Doc II  §5   Preserve before compress
    Doc II  §13  Foundational rules (identity, provenance, evolution,
                 non-closure)
    Doc I   §4   Key principles (Unknown as first-class, Preserve before
                 compress)

Do not read the Field Guide (Doc IV) or Vision documents (Docs V-a, V-b).
Versioning is a Foundational concern. Growth and Vision layers inherit
it; they do not constrain it.

## What this pass produces

One file: `planning/VERSIONING.md`

The file defines the contract. It does not implement the contract.

## What a "version" means in the Atlas

Three distinct version tracks:

    SCHEMA VERSION     — the shape of the canonical logical model
                         (entities, relations, attributes, states). Governed
                         by this document. Denoted S_v.

    STATE VERSION      — a snapshot of the canonical Atlas at a point in
                         time. Every mutation produces a new state version.
                         Denoted A_t.

    ENTITY VERSION     — a revision of one entity within the canonical
                         state. Denoted E^(n).

These three are independent. A schema change does not automatically
produce a new entity version. An entity revision does not imply a schema
change. A state snapshot preserves every entity version that was current
at the time.

If a later pass or an implementation conflates these, the audit records
a violation.

## The seven contract elements

`VERSIONING.md` must define exactly these seven elements. Additional
material is permitted only if it serves one of these.

### 1. Initial schema version

Assign the first schema version.

    S_0 = the canonical logical model as approved by Pass 4

Recommendation: use `S_0` for the pre-implementation architecture and
`S_1` for the first implemented schema, so that architecture-only changes
before the Implementation Gate do not increment the implemented schema
version. If a different convention is chosen, record it.

State the version identifier, the date it takes effect, and the
`IMPLEMENTATION_READINESS` record it references.

### 2. Identity stability guarantee

State the guarantee that entity IDs survive every operation except
explicit deletion.

Include:

- What an entity ID is (from Doc III §3)
- When it is assigned
- Under what operations it persists
- What causes an entity to be deleted (the answer should be: almost
  nothing; reclassification is preferred — Doc III §11)
- What happens to relations referencing a reclassified entity
- What happens to artifacts referencing an entity

The guarantee must be strong enough that a researcher who cites an
entity in a paper can rely on the ID resolving ten years later.

### 3. Change classification

Define patch / minor / major in terms of the canonical logical model,
not in terms of release cadence.

    PATCH    No change to the canonical logical model.
             Examples: bug fixes, performance, documentation,
             internal representation.

    MINOR    Backward-compatible extension of the canonical logical
             model.
             Examples: a new optional attribute, a new entity type that
             does not change existing types, a new relation type, a
             new derived quantity.

    MAJOR    A change that invalidates prior guarantees.
             Examples: changed identity semantics, removed required
             fields, renamed canonical relations, changed meaning of
             an existing relation type.

The list of examples is illustrative. The rule is: if an existing
canonical entity can no longer be interpreted under the new schema
without reinterpretation, the change is major.

### 4. Migration policy

For each class of change, state what migration produces:

    PATCH:    No migration required.
    MINOR:    Additive migration. Old data remains valid under the new
              schema. Migration tool may exist but is optional.
    MAJOR:    Explicit migration required. Migration must:
                - preserve prior state
                - record the migration as a Decision Record
                - produce a new state version A_t+1
                - leave A_t readable by an old reader if feasible
                - produce a compatibility report

The migration policy also states:

- Who may author a migration (any agent, with a DR)
- Who must approve a major migration (the Human Owner)
- Where migration code lives (not in the canonical schema module)
- How migrations are tested (against the source corpus from the
  SOURCE_BASELINE)

### 5. Compatibility guarantees

State what V1 guarantees about reading older and newer state.

    READ OLD     V1 must read state produced by any prior schema version
                 at or above S_min (define S_min).
    EXPORT OLD   V1 must be able to export canonical state in a form
                 readable by the schema version that produced it, if
                 feasible.
    MIGRATE OLD  V1 must provide a documented migration path from any
                 prior schema version at or above S_min.
    REFERENCE OLD  V1 must preserve references to entities defined under
                 older schema versions even when those entities are not
                 re-expressible under the current schema.

If any of the four cannot be guaranteed, state the exception and the
reason.

### 6. Extension mechanism

State how the schema grows without a major version bump.

Include:

- The procedure for introducing a new entity type
- The procedure for introducing a new relation type
- The procedure for promoting an attribute to an entity
      (the graduation path from Doc II §1 and Doc III §5)
- The procedure for retiring a type that is no longer used
      (retirement is not deletion; retired types remain readable)
- How new types are versioned independently of the schema

The mechanism must satisfy the growth invariant from Doc III §17:

    New mathematics should extend the Atlas before it forces a redesign
    of the Atlas.

If the mechanism does not satisfy this, the mechanism is wrong.

### 7. Major version discipline

State the rules under which a major version may occur.

From the Build Protocol §X: at most one major revision per year is the
target. This is a planning discipline, not a prohibition against
emergency correction.

Also state:

- What evidence justifies a major revision (accumulated requirements
  the current model cannot absorb — not merely the existence of a
  better idea)
- What must be preserved across a major revision
- What may change
- What the review trigger is for a future reconsideration

## Anti-patterns this pass must refuse

The following are not acceptable versioning strategies, even if they
appear simpler:

1. **Delete-and-recreate.** An entity that is reclassified is not
   deleted. It is reclassified. History is preserved.
2. **Silent redefinition.** A relation type whose meaning changes is a
   new relation type, not a redefinition of the old one.
3. **Compatibility by reinterpretation.** "Old readers can read new
   data if they ignore the new fields" is acceptable only if the old
   reader's interpretation of the old fields is unchanged.
4. **Migration without provenance.** A migration that does not record
   its own operation as a state transition has lost the reason for the
   change.
5. **Version inflation.** Adding an optional field does not require a
   major version. Adding a mandatory field does.
6. **Version collapse.** Collapsing schema, state, and entity versions
   into one number makes the system unable to distinguish "the schema
   changed" from "the data changed" from "this entity was revised."

## What this pass does NOT do

- It does not implement migration code.
- It does not implement version tracking.
- It does not select a storage technology. Versioning is a logical
  concern; storage realizes it.
- It does not commit to a numbering scheme for releases. `S_0, S_1, ...`
  are schema versions, not product versions.
- It does not define the release process. Release is post-Gate.

## Output format — `VERSIONING.md`

    # Versioning

    Pass: 7
    Role: Version Architect
    Date: <date>
    Source: MINIMAL_ARCHITECTURE.md, COMPLEXITY_AUDIT.md,
            SYSTEM_BOUNDARIES.md, ARCHIVE_REPORT.md

    Status: <final | provisional on DR-NNNN, ...>

    ---

    ## 1. Initial schema version

    ## 2. Identity stability guarantee

    ## 3. Change classification

    ## 4. Migration policy

    ## 5. Compatibility guarantees

    ## 6. Extension mechanism

    ## 7. Major version discipline

    ---

    ## Anti-patterns rejected

    <list of strategies considered and rejected, with reason>

    ---

    ## DRs this pass produces

    <list of new Decision Records required>

    ---

    ## Coverage

    Contract elements defined: <count> / 7
    Open questions: <count>
    Known gaps: <...>

## After producing output

Update `BUILD_STATUS.md`:

- If no BLOCKING decision was produced: mark PASS 7 CLOSED, set current
  pass to PASS 8.
- If a BLOCKING decision was produced: leave PASS 7 OPEN, list the
  blocking DRs, and set next allowed action to "Await human decisions on
  BLOCKING DRs from Pass 7."

Then stop. Do not begin Pass 8.

---

# Notes for the human reviewer

The most important question this pass answers is: **can an old Atlas
still be read ten years later?** If `VERSIONING.md` cannot answer that
question with confidence, the pass failed, regardless of how complete
the rest of the document looks.

The second most important question: **does adding new mathematics
require changing the schema?** If the extension mechanism requires a
schema bump for every new kind of mathematical object, the mechanism has
failed the growth invariant. The whole point of Doc III §17 is that
extension must be cheap.

Watch for a specific failure mode: an architect who defines versioning
but writes a migration policy that quietly depends on a specific storage
technology. "Migration is a SQL script" is not a versioning policy, it
is a storage choice. Versioning is a logical concern. If the policy
cannot be stated without naming a database, the policy is wrong.

Watch for the opposite failure mode: an architect who produces a
versioning policy so abstract that it commits to nothing. "Old data will
be preserved" is not a compatibility guarantee. "S_v data will be
readable by schema versions S_v through S_v+2 without migration" is.
The guarantees must be testable.

If the pass returns a `VERSIONING.md` longer than `MINIMAL_ARCHITECTURE.md`,
something is likely wrong. Versioning is a small contract. It should fit
in a few pages.