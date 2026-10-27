# Mathematical Crystal Atlas — Document III: Atlas Schema

**Status:** Draft 0.1 | **Role:** Technical schema specification
**Depends on:** Doc I (Roadmap), Doc II (Atlas) | **Feeds:** Doc IV (Field Guide)

---

## 0. Foundational Statement

The Atlas Schema is the machine-readable instantiation of the Atlas. It exists so that mathematical structure can become: addressable + searchable + relational + computable + visualizable + extensible — without requiring us to decide beforehand what information will prove useful.

The schema does not define the mathematics. It does not predict the final ontology. It does not impose a hierarchy. It does not make the Atlas complete.

**Governing principle:** $\boxed{\textbf{Small footprint. Deep roots.}}$

The Atlas may become enormous. Its fundamental schema should not need to grow correspondingly complex.

**Three-layer separation** (do not conflate):
$$\text{Mathematics} \rightarrow \text{Atlas Ontology (Doc II)} \rightarrow \text{Atlas Schema (Doc III)}$$

Mathematics supplies substance. Ontology supplies organizational meaning. Schema supplies machine-readable realization.

---

## 1. Atlas State

The complete represented Atlas at version $t$:
$$\mathcal{A}_t = (V_t,\ E_t,\ M_t,\ P_t,\ A_t,\ H_t)$$

where: $V_t$ = entities; $E_t$ = typed relations; $M_t$ = mathematical metadata and representations; $P_t$ = provenance; $A_t$ = artifacts and computational realizations; $H_t$ = history and evolution.

Atlas evolution: $\mathcal{A}_t \xrightarrow{\Delta} \mathcal{A}_{t+1}$ where $\Delta$ may contain a new object, relation, representation, proof, conjecture, computation, correction, refutation, reclassification, new domain, new application, or entirely new structural category. The schema must represent these changes without requiring the whole system to be rebuilt.

---

## 2. Minimal Schema Primitives

At its deepest level, the Atlas requires only:
$$\boxed{\text{Entity} + \text{Relation} + \text{Attribute} + \text{Artifact} + \text{Provenance} + \text{State}}$$

Everything more elaborate should be constructed only when demanded by actual Atlas content. This is intentional. Complexity should enter because the mathematics demands it, not because the software designer imagined it.

---

## 3. Entity

$$E = (id,\ type,\ label,\ content,\ metadata)$$

Entity types (extensible — type is data, not sacred infrastructure): mathematical object, equation, definition, domain, representation, invariant, symmetry, transformation, theorem, conjecture, computation, dataset, visualization, experiment, investigation, application, unknown, anomaly, bridge.

**Identity:** Every persistent entity receives a stable $\mathrm{ID}(E)$ across all revisions. The ID identifies the entity, not a particular version. An entity $E$ may have versions $E^{(1)}, E^{(2)}, \ldots$ while retaining the same identity. This preserves history.

**Labels are not identity.** An entity may simultaneously have: canonical name, aliases, symbols, human-readable labels, machine-readable names, historical names. Changing a label must not destroy identity.

**Content vs. identity:** A mathematical object may acquire additional knowledge over time (more representations, more relations, more properties) without its identity changing.

---

## 4. Relation

$$R = (source,\ type,\ target,\ metadata)$$

Relations are **first-class entities** — not invisible database links. A relationship may itself have evidence, provenance, status, equations, proof, competing interpretations, computational tests, revisions, and therefore deserves its own identity.

**Initial relation vocabulary** (small by design):

```
contains      part-of       depends-on    represents
maps-to       equivalent-to  generalizes   specializes
derived-from  supports      contradicts   emerges-from
```

Additional types emerge when recurring structures demonstrate they deserve explicit representation.

**Direction:** Some relations are naturally directional ($A \xrightarrow{\text{derived-from}} B$); others symmetric ($A \leftrightarrow B$). Directionality belongs to the relation definition, not assumed globally.

**N-ary relations:** Not every mathematical relationship is binary. The schema permits $R(A_1, \ldots, A_n)$, avoiding artificial pairwise decomposition of genuinely multi-object structures.

---

## 5. Attributes

Entities and relations may carry lightweight attributes: `dimension=7`, `rank=r`, `status=conjecture`, `domain=spectral_theory`. When an attribute becomes complex enough to need its own relationships, it graduates to an entity (attribute → entity is always possible).

---

## 6. Mathematical Content

Mathematical statements may be stored as: symbolic text, structured expression tree, LaTeX, executable symbolic form, formal theorem representation, or numerical representation. The schema records *representations of mathematics*, not a single canonical form.

**Equation entity:**
$$E_q = (ID,\ LHS,\ RHS,\ variables,\ assumptions,\ domain,\ status,\ provenance)$$

---

## 7. Status and Evidence

**Status vocabulary** (extensible): `definition`, `assumption`, `computed`, `observed`, `conjecture`, `theorem`, `interpretation`, `hypothesis`, `refuted`, `unknown`.

**Critical:** Status $\neq$ confidence. A conjecture can be extremely compelling; a computation extremely reproducible; neither automatically becomes a theorem. A theorem can be completely established without being important to the larger Atlas. These dimensions remain independent.

**Evidence entity:** Points toward a computation, dataset, proof, symbolic derivation, experiment, independent reproduction, or visualization. $E \xrightarrow{\text{supports}} C$ where $C$ is a conjecture — the schema records the relationship without changing $C$'s status.

---

## 8. Provenance

Every important entity and relation has provenance: $\text{origin} + \text{author/source} + \text{date/state}$.

Possible sources: Atlas document, researcher, computation, formal system, external reference, experiment, generated search, derived object.

Provenance is what allows the Atlas to remain trustworthy as it grows.

---

## 9. Artifacts

An artifact is an externally or internally materialized expression of an Atlas entity or investigation. Types: source code, notebook, proof file, dataset, matrix file, simulation, image, visualization, audio, 3D structure, paper, formalization.

$O \rightarrow A$ (attached), but $A \neq O$: a visualization of the crystal is not the crystal; a Python implementation of a transformation is not the transformation; a Lean proof file is not the theorem itself.

**Computational realizations:** $O \rightarrow \{C_\text{symbolic}, C_\text{numeric}, C_\text{visual}, C_\text{formal}\}$.

**Formal proof bindings:** $T \xrightarrow{\text{formalized-by}} F$. Proof tier structure is inherited from Doc II (Tiers A–G). The schema records bindings without requiring a full theorem prover in the initial implementation.

---

## 10. Specialized Entity Types

**Investigations:** Active exploration with explicit status. May ask $Q: A \cong B?$ or $Q: \text{what invariant distinguishes } A, B?$. Produces: result | conjecture | counterexample | unknown. May remain open indefinitely.

**Questions:** Persistent nodes connected to relevant objects, evidence, investigations, conjectures, results, and related questions. Creates an open-problem graph from the same substrate.

**Unknowns:** $U_\text{sym}$ (unknown symmetry), $U_\text{map}$ (unknown correspondence), $U_\text{inv}$ (suspected but undiscovered invariant). The system never requires an unknown to become known before it can be recorded.

**Anomalies:** Unexpected numerical coincidences, unexplained degeneracy, unusual orbits, failures of presumed correspondences. Preserved before interpretation. An anomaly can later become: theorem, conjecture, error, or new object. This is precisely why it must be preserved.

**Cross-domain bridges:** Relations with enough structure to become objects in their own right. $B: R_A(O) \longleftrightarrow R_B(O)$. Physical projection template: Crystal representation → physical variables → equations → observables → simulation.

**Convergence events:** $K = (R_1, R_2, \ldots, R_n,\ I,\ E)$ where $R_i$ are representations, $I$ is the shared structure, $E$ contains evidence. Events are searchable. Integration metric $\Gamma(X) = N_\text{rep} \times N_\text{ind.maps} \times N_\text{verified}$ is a derived value, not a truth measure.

---

## 11. Versioning and Evolution

**Entity versioning:** $E^{(0)} \rightarrow E^{(1)} \rightarrow E^{(2)}$. Each revision preserves: previous state, new state, reason, provenance, affected relationships. System supports both current Atlas and historical Atlas states.

**Reclassification:** When an object's classification changes, use $E \xrightarrow{\text{reclassified-as}} E'$ rather than deletion. History remains accessible.

**Schema versioning:** $S_0, S_1, S_2, \ldots$ Goal is not to prevent evolution but to make it coherent. $S_t(\mathcal{A}_t)$ remains meaningful even as $S_{t+1}$ introduces new capabilities.

**New entity/relation types** emerge when recurring Atlas structure demonstrates necessity. Process: recurring structure → candidate type → definition → schema extension. Prevents both premature abstraction and permanent structural ambiguity. The Atlas learns its own vocabulary through use.

**Schema reflection:** Eventually, the Atlas should represent entities describing Atlas entities, and potentially entities describing schema structures themselves.

---

## 12. Canonical Logical Model

```
ENTITIES        id, type, label, content, status, version
RELATIONS       id, type, source, target, metadata, status
ATTRIBUTES      entity, key, value
ARTIFACTS       id, type, location, provenance
PROVENANCE      source, author, timestamp, operation
STATES          atlas_version, entity_version, relation_version
```

This is intentionally boring. Boring is good at the root. The interesting mathematics lives in the things it can represent.

**Runtime graph:** $G_t = (V_t, E_t)$ with additional information attached to both. Around it: $G_t + D_t + P_t + A_t + H_t$ (graph + mathematical data + provenance + artifacts + history). That is the actual machine-readable Atlas state.

---

## 13. Query and Traversal Layer

**Core queries:**
```
Neighbors(O)           Representations(O)    Domains(O)
Symmetries(O)          Dependencies(O)       Evidence(X)
UnknownRelations(O)
```

**Traversal example:** $\mathcal{C} \rightarrow \mathrm{Spec}(\mathcal{C}) \rightarrow \lambda_i \rightarrow R_i \rightarrow \text{dynamical behavior}$. This is where the Atlas becomes navigable mathematics rather than an archive.

**Search levels** (schema must not prevent any of these; need not implement all on day one): lexical, semantic, structural, mathematical (shared invariants/spectra/symmetries), provenance, historical state.

**Structural search** (future): $\mathrm{Spec}(A) \stackrel{?}{\sim} \mathrm{Spec}(B)$; $\mathrm{Comm}(A) \stackrel{?}{\sim} \mathrm{Comm}(B)$; $\mathrm{Orbit}(A) \stackrel{?}{\sim} \mathrm{Orbit}(B)$. These are the basis of an eventual automated conjecture engine. The schema's responsibility: make the required structures available.

---

## 14. Programmatic Interface

**Atlas API** (exposes information):
```
get(id)  create(entity)  update(id, revision)  relate(source, type, target)
search(query)  neighbors(id)  representations(id)  domains(id)
evidence(id)  history(id)  snapshot(version)
```

**Mathematical layer** (computes mathematics, communicates through schema):
```
spectrum(id)  orbit(id)  stabilizer(id)  compose(a,b)
simulate(id, parameters)  visualize(id)
```

Atlas API $\neq$ Mathematical Engine. The first exposes information. The second computes mathematics.

**Research interface:** Selecting $\mathcal{C}$ could reveal $\mathrm{Spec}(\mathcal{C})$, $\ker(\mathcal{C})$, associated $Y^i_{jk}$, candidate symmetries, representations, geometric structures, dynamical structures, formal proofs, computational artifacts, open questions, and unresolved bridges. The schema is what makes that possible.

---

## 15. Storage, Visualization, and Integration

**Storage:** Schema does not prescribe storage technology. Possible realizations: graph database, relational database, document store, object store, file-based archive, hybrid. Requirement: physical storage must preserve logical Atlas relationships, not the reverse.

**Visualization:** Multiple projections — network, tree, matrix, lattice, geometric manifold, timeline, dependency graph, spectral plot, phase space — all as views $V_i(\mathcal{A}_t)$. No visualization is canonical.

**Directories as views:**
```
Crystal/
├── Foundations/  ├── Sedenion/    ├── Crystal7/    ├── Yijk/
├── Symmetry/     ├── Dynamics/    ├── Geometry/    ├── Computation/
└── Applications/
```
Navigation view, not ontology. Same entity may appear in multiple views without duplication.

**Game integration (Doc IV):** Game → $\mathcal{A}_t$. The Field Guide does not maintain a duplicate mathematical database; it consumes the same Atlas state. Exploration → Atlas modification → new exploration.

**Agent integration:** Agents may $\mathrm{Query}(\mathcal{A}_t)$, $\mathrm{Investigate}(Q)$, $\mathrm{Generate}(H)$, $\mathrm{Compute}(X)$, $\mathrm{Propose}(\Delta)$. Proposed state transitions $\mathcal{A}_t \rightarrow \mathcal{A}_t + \Delta$ require human or formal validation before entering canonical state. This supports branching: $\mathcal{A}_t^{(1)}, \mathcal{A}_t^{(2)}, \ldots$ for competing conjectures or alternative interpretations, which may later merge, remain parallel, or collapse through refutation.

**Atlas as Archive vs. Interface:**
- Archive: what the Atlas currently contains
- Interface: $\mathcal{A}_t \rightarrow \{\text{research, visualization, simulation, formalization, game, agent}\}$

A pile of documents is an archive. A relationally navigable archive is an Atlas.

---

## 16. Initial Implementation Scope

The first implementation need only support:
$$\text{entities} + \text{typed relations} + \text{metadata} + \text{provenance} + \text{versioning} + \text{basic search} + \text{basic traversal} + \text{artifact references}$$

Everything else grows on top. That is enough to begin.

**Initial corpus** (already established by Doc I): $\mathcal{Z}_0, \mathcal{C}, \mathcal{Y}_{64}$, symmetry candidates, spectral structures, $(\zeta,\theta)$, geometric structures, information structures, cascade structures, timbre structures, three-body structures, interfaces, physical projections, computational artifacts, formalization plans.

---

## 17. Schema Invariants (permanent)

**Schema invariant:**
$$\boxed{\textbf{Every meaningful Atlas relationship should be representable without destroying its mathematical identity.}}$$
Not every relationship needs to be understood, proved, or useful. But if it becomes meaningful, the machine must have somewhere to put it.

**Growth invariant:**
$$\boxed{\textbf{New mathematics should extend the Atlas before it forces a redesign of the Atlas.}}$$

**Complexity invariant:**
$$\boxed{\textbf{Complexity should enter because the mathematics demands it, not because the software designer imagined it.}}$$

**Two test questions** sufficient for the first implementation:
1. Can the schema faithfully represent what we currently know?
2. Can it absorb what we discover next?

---

## 18. The Complete Loop

$$\boxed{\text{Roadmap} \rightarrow \text{Organization} \rightarrow \text{Schema} \rightarrow \text{Exploration} \rightarrow \text{Discovery} \rightarrow \text{Atlas}}$$
$$\mathcal{A}_t \rightarrow \text{new knowledge} \rightarrow \mathcal{A}_{t+1}$$

The schema is not meant to be impressive. It is meant to be quietly capable — sitting beneath the mathematics and allowing it to become: stored → connected → queried → computed → visualized → explored, without requiring the Atlas to know in advance what it will eventually become.

$$\boxed{\text{Atlas} \neq \text{database of mathematical facts}}$$
$$\boxed{\text{Atlas} = \text{evolving relational mathematical state}}$$
$$\boxed{\text{Schema} = \text{machine-readable embodiment of that state}}$$

And perhaps the most important phrase in the document: $\boxed{\textbf{For now.}}$ — because the whole point is that the Atlas gets to teach us what its eventual schema needs to be.
