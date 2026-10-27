# Mathematical Crystal Atlas — Build Protocol

Protocol Version: 0.1
Status: Pre-Implementation
Authority: Governs all preparation of the first software implementation
Primary rule: DO NOT IMPLEMENT YET.

---

## 0. Purpose

This protocol governs how the Atlas documents become software.

It exists to prevent:
- premature implementation
- architectural drift
- taxonomy explosion
- version churn
- silent contradiction
- agents treating conversation as project state

The repository is the source of truth. Conversation is not.

The goal of this phase is not to build the Atlas.
It is to determine, with sufficient confidence:

- what the Atlas fundamentally is
- what the first implementation actually needs
- what must remain outside V1
- which concepts are foundational vs. extensions
- how the system evolves without destroying prior states
- what requires human approval

---

## I. Governing Principles

1. **Vision before implementation.** No implementation decision outranks the purpose of the Atlas.
2. **Mathematics before software.** Complexity enters because the mathematics demands it, not because the designer imagined it.
3. **Preserve uncertainty.** Unknowns, conjectures, and competing interpretations are legitimate states. Never silently promoted, never silently discarded.
4. **Separate objects from representations.** A mathematical object is not its visualization, code, proof, or artifact.
5. **Repository over conversation.** Every consequential decision exists in repository form.
6. **Small core, large graph.** Favor structural relationships over rigid taxonomies.

---

## II. Complexity Discipline

### The 3–7 Rule

At any single conceptual layer, prefer 3–7 primary concepts.

This applies to: domain concepts, top-level modules, navigation, lifecycle states, agent roles, API surfaces.

It is a **heuristic**, not a mathematical constraint.

- Exceeding 7 requires a Decision Record explaining why decomposition would be less coherent.
- Falling below 3 does not justify inventing abstractions to satisfy symmetry.

### Escalation Rule

Complexity may enter only when:
1. Existing mathematics requires it.
2. Existing data cannot be faithfully represented without it.
3. A demonstrated use case requires it.
4. A compatibility requirement requires it.
5. A repeated structural pattern justifies promotion.

Complexity may **not** enter because a framework supports it, an agent expects it might be useful, or a diagram would look more comprehensive.

### Preference Order

When representing something new, prefer in order:
1. an attribute on an existing entity
2. a typed relation
3. a derived value
4. an extension
5. a new entity

---

## III. Absolute Pre-Implementation Gate

**No agent may produce production code, database implementations, APIs, scaffolds, or feature implementation until the Implementation Readiness Record is explicitly approved by the Human Owner.**

Agents MAY:
- inspect documents
- create architectural diagrams
- create analysis files
- propose schemas
- write Decision Records
- produce throwaway prototypes *only when explicitly authorized for architectural investigation*

A prototype is not implementation. The distinction must be recorded.

---

## IV. Source Hierarchy

Documents are the primary source material. They must not be silently rewritten.

When documents disagree:
1. Identify the disagreement.
2. Preserve both formulations.
3. Record the conflict as a Decision Record.
4. Identify the architectural consequence.
5. Request human decision where necessary.

Agents must not silently choose whichever formulation is easiest to implement.

Conceptual hierarchy:

    Document I  — Roadmap     (Why? Where? How?)
    Document II — Atlas       (What exists? How organized?)
    Document III— Schema      (How does it become software?)
    Document IV — Field Guide (How do minds explore it?)
    Build Protocol            (What is the smallest coherent realization?)

---

## IV-b. Source Document Classes

The source documents are not a single flat set. They are classified by the
role they play in the build. This classification is fixed at freeze time and
recorded in `SOURCE_BASELINE.md`.

### Foundational

    Doc 0  — Why This Crystal
    Doc I  — Roadmap
    Doc II — Atlas
    Doc III— Schema

These four documents define the object, the vision, the ontology, and the
machine-readable realization. They are the direct inputs to Passes 1–9.
Every requirement, invariant, and MVP boundary extracted during the build
must be traceable to a Foundational document.

### Growth

    Doc IV — Field Guide

The Field Guide describes how the Atlas grows through exploration. It is
not a V1 requirement source. It constrains the evolution model only in that
the schema must not foreclose future exploration patterns (e.g., quests,
unknowns, branching states). Where the Field Guide and the Foundational
documents conflict, the Foundational documents win.

### Vision

    Doc V-a — Asimyth Game
    Doc V-b — Machine Resonance

These documents describe long-term applications and the human-facing
interface. They are context, not constraints. They are not inputs to any
pass. They must not be cited as justification for any V1 requirement,
capability, or architectural choice.

If an agent believes a Vision document contains a Foundational invariant
that the Foundational documents missed, the agent does not act on this
belief. It writes a Decision Record with `STATUS: OPEN` and requests human
review.

### Rule

A document's class is not a judgment of its importance. It is a statement
of the build phase in which it is actionable. Vision documents become
actionable only after the Implementation Gate is passed and the Foundational
substrate is stable.

---

## V. Agent Roles

Agents are specialized reviewers, not autonomous authorities. No agent may redefine the project vision.

| Role | Purpose | Output |
|---|---|---|
| **Archivist** | Extract definitions, principles, requirements, invariants, unresolved questions without interpretation | `ARCHIVE_REPORT.md` |
| **Cartographer** | Map concepts, dependencies, representations, interfaces; identify duplicates, circularity, overloaded concepts | `ARCHITECTURE_MAP.md` |
| **Terminologist** | Prevent semantic drift; produce canonical glossary distinguishing mathematical identity / software identity / representation / artifact / view / interpretation | `GLOSSARY.md` |
| **Contradiction Hunter** | Find inconsistencies before code makes them expensive; every conflict becomes a Decision Record | `CONFLICT_REPORT.md` + DRs |
| **Minimalist Architect** | Construct the smallest architecture satisfying actual requirements; explicitly empowered to remove proposed architecture | `MINIMAL_ARCHITECTURE.md` |
| **Complexity Auditor** | Prevent classification explosion; enforce the 3–7 rule | `COMPLEXITY_AUDIT.md` |
| **Version Architect** | Ensure evolution without destroying historical states | `VERSIONING.md` |
| **Boundary Architect** | Classify every capability as CORE / EXTENSION / VIEW / DERIVED / EXPERIMENTAL / DEFERRED / EXTERNAL | `SYSTEM_BOUNDARIES.md` |
| **Implementation Planner** | Translate approved architecture into plan; last pre-implementation role | `IMPLEMENTATION_BRIEF.md` |
| **Skeptic** | Attempt to break the architecture; must attempt to reduce the system | `PRE_IMPLEMENTATION_REVIEW.md` |

---

## VI. Pass Order

Agents operate in passes. A later pass may not silently invalidate an earlier pass. When it does, a new Decision Record is required.

    PASS 0 — Freeze          freeze source documents; record versions/hashes
    PASS 1 — Archive         run Archivist
    PASS 2 — Map             run Cartographer + Terminologist
    PASS 3 — Conflict        run Contradiction Hunter
    PASS 4 — Minimal Core    run Minimalist Architect
    PASS 5 — Complexity      run Complexity Auditor (3–7 rule)
    PASS 6 — Boundaries      run Boundary Architect
    PASS 7 — Evolution       run Version Architect
    PASS 8 — Adversarial     run Skeptic (may roll back to any prior pass)
    PASS 9 — Brief           run Implementation Planner

Pass 9 produces `IMPLEMENTATION_BRIEF.md`. No implementation begins here.

---

## VII. Core vs. Extension

Every proposed capability is classified as exactly one of:

- **CORE** — necessary to preserve the fundamental Atlas model
- **EXTENSION** — addable without changing the core
- **VIEW** — a projection of existing state
- **DERIVED** — computable from canonical information
- **EXPERIMENTAL** — not yet stable
- **DEFERRED** — desired but intentionally postponed
- **EXTERNAL** — belongs to another system; referenced, not absorbed

Promotion toward CORE requires repeated evidence that the core cannot remain coherent without it.

---

## VIII. Canonical vs. Experimental State

The system distinguishes:

    CANONICAL
    EXPERIMENTAL
    BRANCH
    HISTORICAL

Agents may freely experiment outside canonical state.
Agents may not silently modify canonical state.
A proposed transition requires explicit validation before entering canonical state.
Competing interpretations may coexist, merge, remain parallel, be refuted, or be abandoned. History is preserved.

---

## IX. Decision Records

Every consequential decision receives a Decision Record.

    DR-XXXX

    Title:
    Date:
    Status: proposed | accepted | rejected | superseded | OPEN

    Context:
    Question:
    Options: A / B / C
    Decision:
    Reason:
    Consequences (easier / harder):
    Alternatives rejected:
    Reversibility: easy | moderate | difficult
    Affected documents:
    Affected components:
    Review trigger:

An unresolved decision is not a defect. It is a recorded state. Use `STATUS: OPEN` rather than forcing an arbitrary choice.

---

## X. Versioning Rules

1. **Identity persists.** An entity retains identity across revisions while its mathematical identity remains meaningfully continuous.
2. **History is never silently destroyed.** Changes preserve prior state, new state, reason, provenance, timestamp, affected relationships.
3. **Data outlives interfaces.** UI, API, visualization may change. Underlying state remains recoverable.
4. **Schema evolution is explicit.** Every schema change receives version, migration description, compatibility statement, affected entities and relations.
5. **Prefer additive evolution.** Add relation / field / representation / extension over silent rename / delete / reinterpret.
6. **Major versions are rare.** Target: at most one major architectural revision per year.
7. **Old versions remain viable.** Where practical: read old, export old, migrate old, reference old.
8. **Version the protocol itself.** Changes to fundamental rules require a Decision Record.

---

## XI. Repository Structure During Pre-Build

    atlas/
    ├── docs/
    │   ├── source/
    │   ├── architecture/
    │   ├── decisions/
    │   ├── maps/
    │   └── reviews/
    ├── protocol/
    │   └── BUILD_PROTOCOL.md
    ├── planning/
    │   ├── ARCHIVE_REPORT.md
    │   ├── ARCHITECTURE_MAP.md
    │   ├── GLOSSARY.md
    │   ├── MINIMAL_ARCHITECTURE.md
    │   ├── COMPLEXITY_AUDIT.md
    │   ├── SYSTEM_BOUNDARIES.md
    │   ├── VERSIONING.md
    │   └── IMPLEMENTATION_BRIEF.md
    ├── AGENTS.md
    ├── BUILD_STATUS.md
    └── README.md

No production source tree is created until the gate passes.

---

## XII. Minimal First System

The initial candidate MVP boundary:

    entities
    + typed relations
    + metadata
    + provenance
    + versioning
    + basic search
    + basic traversal
    + artifact references

This list is **not** automatically final. The architecture process determines whether each element is genuinely required, representable by another primitive, or safely deferrable.

Nothing beyond this boundary enters V1 merely because it appears in the broader vision.

---

## XIII. No Premature Technology Commitment

Before architecture stabilizes, no commitment to:
specific database / frontend / agent framework / LLM provider / deployment platform / visualization library.

The logical Atlas model precedes its physical implementation.

---

## XIV. Architectural Tests

The implementation brief defines these before implementation begins. The eventual system must demonstrate:

- **Test A — Representation:** Can the existing Atlas corpus be represented faithfully?
- **Test B — Relationship:** Can meaningful relationships be represented without destroying identity?
- **Test C — Unknown:** Can the system preserve an unknown without forcing classification?
- **Test D — Provenance:** Can the origin of an object or relationship be recovered?
- **Test E — Version:** Can historical state be recovered after modification?
- **Test F — Traversal:** Can a researcher navigate from an object through its relationships?
- **Test G — Extension:** Can a genuinely new structure be added without redesigning the core?

---

## XV. Human Decision Boundary

Agents may analyze, compare, simplify, propose, challenge, prototype, document, test, organize.

The Human Owner retains authority over:
vision, fundamental mathematical interpretation, unresolved philosophical commitments, acceptance of architectural compromises, promotion into canonical state, major version changes, final implementation authorization.

When intervention is required:

    DECISION REQUIRED

    Question:
    Why it matters:
    Options: A / B / C
    Agent recommendation:
    Reversibility:
    Consequences:

Do not ask the human to reconstruct context.

---

## XVI. Completion Criteria

Pre-build is complete only when:

    [ ] Source documents frozen and indexed
    [ ] All major concepts mapped
    [ ] Canonical terminology established
    [ ] Contradictions recorded
    [ ] Open decisions recorded
    [ ] Core primitives identified
    [ ] 3–7 audit passed
    [ ] Core/extension boundaries established
    [ ] Canonical/experimental boundary established
    [ ] Versioning rules established
    [ ] Compatibility strategy established
    [ ] MVP explicitly bounded
    [ ] Deferred scope explicitly recorded
    [ ] Architectural tests defined
    [ ] Repository structure defined
    [ ] Implementation sequence defined
    [ ] Skeptical review completed
    [ ] Human Owner approves architecture

---

## XVII. Implementation Readiness Record

    IMPLEMENTATION READINESS

    Protocol version:
    Architecture version:

    Source baseline:
    Core model:
    Core primitives:
    Core relations:
    Canonical state model:
    Versioning model:
    Compatibility guarantees:

    MVP:
    Explicitly excluded from MVP:
    Known risks:
    Open questions:
    Decision Records:
    Architectural tests:
    Implementation order:

    Human approval: PENDING / APPROVED
    Approval date:
    Approved architecture version:

    IMPLEMENTATION AUTHORIZATION: PENDING

The final line remains PENDING until explicitly approved.

---

## XVIII. The Gate

One final decision is presented:

**Is the architecture sufficiently coherent, minimal, extensible, and purposeful to begin implementation?**

- NO — return to architecture
- YES — authorize implementation

No automatic transition.
No inference of approval from silence, enthusiasm, or agent confidence.

---

## XIX. After the Gate

    1. Archive final pre-build state
    2. Tag architecture version
    3. Preserve all Decision Records
    4. Create implementation branch
    5. Execute Implementation Brief
    6. Test each milestone
    7. Record deviations as Decision Records
    8. Never silently diverge from approved architecture
    9. Return to Build Protocol if foundational flaw revealed

Implementation is:

    Architecture → Authorization → Implementation → Test → Revision

Not:

    Idea → Code → Patch → Patch → Rewrite

---

## XX. Final Principle

> **Build the smallest system capable of becoming the Atlas.**

Not the smallest imaginable.
Not the most impressive.
Not the most feature-rich prototype.
Not the architecture an agent happens to prefer.

The smallest coherent substrate that can faithfully preserve what exists, accommodate what is discovered, and grow without destroying its history.

The Atlas is expected to teach us what it must eventually become.

Until then: **do not implement yet. Organize.**