# Mathematical Crystal Atlas — Document II: Technical & Organizational Specification

**Status:** Draft 0.1 | **Role:** Authoritative organizational framework
**Depends on:** Doc I (Roadmap) | **Feeds:** Doc III (Schema), Doc IV (Field Guide)

---

## 0. Definition

The Atlas is a multi-relational mathematical knowledge system. An object may simultaneously belong to multiple domains, possess multiple representations, participate in multiple symmetry structures, depend on multiple results, and connect to multiple applications.

**Fundamental principle:** Object → many properties → many representations → many relations (not: Object → one category).

The Atlas is not a tree. It is:
$$\boxed{\text{a multilayer, typed, directed, evolving mathematical graph}}$$
with tree-like projections available when useful. The current root $\mathcal{C}_7$ is a navigation anchor, not an eternal ontological decree. Future discoveries may reveal more fundamental objects; re-centering must be possible without destruction.

**Organizational identity (one equation):**
$$\text{Atlas} = \mathcal{O} \cup \mathcal{D} \cup \mathcal{R} \cup \mathcal{S} \cup \mathcal{B} \cup \mathcal{P} \cup \mathcal{C} \cup \mathcal{A} \cup \mathcal{U}$$
(Object, Domain, Representation, Symmetry, Bridge, Proof, Computational, Application, Unknown structures — their intersection, not any one alone.)

---

## 1. Core Ontology

Nine primitive entity types; everything else is constructed from these:

1. **Object** — identifiable mathematical entity with stable Atlas identity even as interpretation changes
2. **Property** — attribute of an object; may become an Object when sufficiently complex ($\text{Object} \rightarrow \text{Property} \rightarrow \text{Object}$)
3. **Representation** — description of an object in a particular mathematical language ($R_i: O \mapsto \mathcal{L}_i$; note $O \neq R(O)$)
4. **Relation** — typed connection between objects (first-class entity with its own identity, evidence, status, proof)
5. **Transformation** — operation between states or representations
6. **Domain** — mathematical field used as viewing context (many-to-many membership; a domain is context, not ontological classification)
7. **Evidence** — pointer to computation, proof, experiment, or derivation supporting a claim (distinct from status)
8. **Artifact** — materialized expression: paper, code, proof file, dataset, simulation, visualization
9. **Investigation** — active exploration with explicit open/closed state

**Object identity:** $O = (\mathrm{ID},\ \mathrm{Definition},\ \mathrm{Properties},\ \mathrm{Relations},\ \mathrm{Representations},\ \mathrm{Status},\ \mathrm{Dependencies},\ \mathrm{Provenance})$

---

## 2. Relation Types

Minimum vocabulary (extensible):

| Type | Notation |
|---|---|
| Dependency | $A \rightarrow B$ |
| Equivalence | $A \cong B$ |
| Mapping | $A \xrightarrow{\Phi} B$ |
| Generalization | $A \subseteq B$ |
| Composition | $A \circ B = C$ |
| Emergence | $A \otimes B \rightarrow C$ |
| Contradiction | $A \not\leftrightarrow B$ (under stated assumptions) |
| Support | evidence for a conjectural relation |

**Three discovery classes** (explicit relation types in the Atlas):
- **Type I Recognition:** $A \cong B$
- **Type II Translation:** $A \xrightarrow{\Phi} B$
- **Type III Emergence:** $A \otimes B \rightarrow C$ ← most important; Atlas may generate mathematics not present in any individual region

---

## 3. Status and Evidence

Every important statement carries explicit status. Minimum vocabulary:

$D$ = Definition; $A$ = Axiom/assumption; $C$ = Computed result; $O$ = Observation; $Co$ = Conjecture; $P$ = Proved theorem; $I$ = Interpretation; $H$ = Hypothesis; $X$ = Cross-domain correspondence

**Critical invariant:** $\text{status} \neq \text{evidence}$. A conjecture may have strong computational evidence without being proved. A statement may be $\mathrm{status} = \text{conjectural}$ and simultaneously $\mathrm{evidence} = \text{extensive computational agreement}$. The Atlas never silently promotes hypothesis → fact.

---

## 4. Domain Registry (initial, extensible)

Foundations; linear algebra; matrix/operator theory; Sedenion/nonassociative algebra; spectral theory; group/Lie/representation theory; tensor/graded structures; dynamical systems; nonlinear dynamics; information geometry; topology; differential geometry; three-body dynamics; cascade/fractal structures; nonlinear harmonic analysis; interface mathematics; condensed matter; mathematical physics; information theory; computation; formal verification; applications.

Domain membership is many-to-many. Example: $\mathcal{C} \in \{\text{Linear Algebra}, \text{Spectral Theory}, \text{Symmetry}, \text{Dynamics}, \text{Geometry}, \text{Computation}, \ldots\}$.

---

## 5. Representation Architecture

Representation classes: matrix, operator, tensor, algebraic, group-theoretic, geometric, topological, spectral, dynamical, informational, computational.

**One object, many languages:** Every important object should be tested across at minimum $\{\text{matrix}, \text{operator}, \text{geometric}, \text{dynamical}, \text{informational}\}$. Coverage count $A_c \in \{0,\ldots,5\}$; $A_c = 5$ is maximal five-language convergence (investigative metric, not truth metric).

**Atlas Convergence Event:** When independent representations repeatedly reveal the same invariant or structure. Record: representations involved, observed invariant, degree of independence, computational evidence, formal status, remaining alternatives.

Convergence index (exploratory only): $\Gamma(X) = N_\text{rep} \times N_\text{ind. maps} \times N_\text{verified rel.}$

---

## 6. Specialized Registries

**$\mathcal{Y}_{64}$ Transformation Registry:** $\{Y^i_{jk}\}$ treated as a structured object family. Initial targets: multiplication table, inverses, order, conjugacy, commuting pairs, subalgebras, ideals, centers, automorphisms, orbit structures. Factorization $64 = 4^3$ and index structure $(i,j,k)$ receive their own structural representation; candidates include $\mathbb{Z}_4^3$, graded algebras, tensor products — all as *candidate* interpretations unless formally demonstrated.

**Spectral Registry:** For operator $A$: $\mathrm{Spec}(A)$, eigenvectors, eigenspaces, multiplicities, spectral gaps, invariants, decompositions. Candidate bridge to $(\zeta,\theta)$: $\mathfrak{D}: C(\zeta,\theta) \rightarrow \mathrm{Spec}(\mathcal{C})$, i.e., static spectrum $\leftrightarrow$ dynamic phase portrait (bridge to investigate, not presume).

**Dynamical Registry:** State space, variables, equations of motion, fixed points, stability, bifurcations, periodic orbits, conserved quantities, Hamiltonian/symplectic structure, Lyapunov data, invariant manifolds. The $(\zeta,\theta) \in [-1,1] \times S^1$ cylinder is the primary initial object.

**Geometry Registry:** $(M, g, \psi)$; interfaces $\Sigma \subset M$; curvature $R_{\mu\nu}$; information metrics; topological structures. Multiple geometries may be associated with one object without implying identity.

**Cascade/Scaling Registry:** $R^{(n+1)} = \lambda R^{(n)}$; scaling parameters $\lambda, \phi, \sqrt{3}, H, D, \alpha$ as nodes; relations as edges. Scaling network, not linear chain.

**Information/Interface Registry:** $I(x,t), J(x,t)$; candidate conservation $\partial_t I + \nabla \cdot J = S - D$; lattice/Bloch modes, band gaps, resonances, topological modes, transfer functions, mutual information. Sits at intersection of condensed matter, topology, information theory, geometry.

**Symmetry Observatory:** Groups, Lie algebras, discrete and continuous symmetries, automorphism groups, stabilizers, centralizers, commutants, orbit structures, symmetry-breaking. Candidates under investigation: $\mathbb{Z}_4, \mathbb{Z}_7, \mathbb{Z}_2, S^1, SU(4), G_2, \mathrm{Spin}(7), SO(7)$. No candidate privileged merely by early appearance.

**Unknown Registry:** $U_\text{inv}$ (unknown invariant), $U_\text{sym}$ (unknown symmetry), $U_\text{map}$ (unknown correspondence), $U_\text{alg}$ (unknown algebraic structure). An unknown may later become resolved, conjectured, refuted, reclassified, or remain open.

**Anomaly Registry:** Numerical coincidences, unexpected equivalences, unexplained computational behavior, structural irregularities — preserved before interpretation. An anomaly is *observed structure not yet assigned adequate explanation*. Many important bridges first appear as anomalies.

---

## 7. Bridge Registry

A Bridge is a persistent, named correspondence between two mathematical descriptions:
$$B: R_A(O) \longleftrightarrow R_B(O)$$

A bridge entry records: source/target objects, source/target representations, mapping, directionality, assumptions, evidence, status, computational realization, formal proof status, inverse if known, limitations, related bridges.

This is one of the Atlas's most important structures. The objective is navigable correspondence, not merely accumulated mathematics.

---

## 8. Proof Structure

Proof graph (directed dependency structure), not merely a document collection. Seven proof tiers: A (Definitions) → B (Algebraic identities) → C (Structural theorems) → D (Representation theorems) → E (Dynamical theorems) → F (Cross-domain theorems) → G (Deep structural theorems).

A theorem must be traceable backward to definitions → assumptions → lemmas → theorem, and forward to every structure depending on it.

---

## 9. Computational Architecture

Eventual reference implementation targets:

```
CrystalState(), CrystalOperator(), Y(i,j,k)
compose(), inverse(), spectrum(), eigenspaces()
orbit(), stabilizer(), project(), lift()
simulate(), visualize()
```

Every major object eventually possesses symbolic, numerical, visual, and formal-proof counterparts. Document III determines how this is represented in software.

---

## 10. Multiple Views on One Graph

Atlas graph $\mathfrak{G} = (V, E, \tau, \sigma, \pi)$ where $V$ = entities, $E$ = relations, $\tau$ = relation types, $\sigma$ = metadata, $\pi$ = provenance. Simultaneous projections:

- **Domain view:** Algebra → Geometry → Dynamics
- **Dependency view:** $D \rightarrow L_1 \rightarrow L_2 \rightarrow T$
- **Representation view:** $O \rightarrow R_1, R_2, R_3, R_4$
- **Symmetry view:** $O \rightarrow G \rightarrow \mathrm{Rep}(G)$
- **Temporal view:** discovery$_1$ → discovery$_2$ → revision$_3$
- **Exploration view:** $O \rightarrow \text{unknown} \rightarrow \text{investigation} \rightarrow \text{quest}$

The Atlas does not need to choose one.

---

## 11. Initial Directory Structure (navigation view, not ontology)

```
Crystal/
├── Foundations/    ├── Sedenion/      ├── Crystal7/
├── Yijk/           ├── Symmetry/      ├── Spectrum/
├── Dynamics/       ├── Geometry/      ├── Information/
├── Topology/       ├── ThreeBody/     ├── Cascades/
├── Timbre/         ├── Interfaces/    ├── Physics/
├── Computation/    ├── Formalization/ ├── Applications/
└── Atlas/          ← cross-domain correspondences and emergent structures
```

The same entity may appear in multiple directories without duplication. Directory is a view; the graph is the ontology.

---

## 12. Progress Architecture

Per-branch state vector $(F, P, K, C, X, G, Q)$ (formalization, proof depth, structural coherence, computational realization, cross-domain correspondence, generativity, compression). Scalar $\mathfrak{A} = \sum/7$ for summary only; vector is authoritative.

**Maturity gates** (proposals): initial: $F \geq 8, C \geq 7$; algebraic: $F \geq 8, P \geq 6, K \geq 8$; symmetry: $K \geq 8, X \geq 7$; dynamics: $C \geq 8, G \geq 7$; formalization: $P \geq 8$; Atlas: $X \geq 9, Q \geq 8$.

**Discovery frontier** $\partial\mathcal{A}$: structures that are incompletely formalized, weakly connected, computationally unexplored, conjectural, anomalous, or potentially generative. The frontier is *what appears sufficiently structured that further investigation may produce new Atlas structure*.

---

## 13. Foundational Rules

1. **Identity** — every persistent object has a stable identifier
2. **Provenance** — every important claim has traceable origin
3. **Status** — every mathematical assertion has explicit epistemic status
4. **Multiplicity** — objects may possess multiple representations and domain memberships
5. **Typed Relations** — different kinds of relationships are distinguished
6. **Independence** — representations are not conflated with objects
7. **Preservation** — exploratory material is preserved before compression
8. **Formalization** — formal proof is a distinct realization layer
9. **Computation** — computational results are evidence or artifacts, not silently promoted to theorem
10. **Unknowns** — unknown structures are first-class Atlas entities
11. **Evolution** — taxonomy may change when persistent structural evidence warrants it
12. **Non-closure** — the Atlas does not assume its own eventual completeness

---

## 14. The Organizational Loop

$$\text{Object} \rightarrow \text{Represent} \rightarrow \text{Relate} \rightarrow \text{Formalize} \rightarrow \text{Compute} \rightarrow \text{Compare} \rightarrow \text{Discover} \rightarrow \text{Extend Atlas} \circlearrowleft$$

**The Technical Stone:**
$$\boxed{\textbf{A typed, provenance-preserving, multi-representational, multi-domain, evolving mathematical graph.}}$$

Central purpose: make mathematical structure navigable without prematurely collapsing its multiplicity.
Central commitment: the map may grow indefinitely without requiring the organizational language to be reinvented from scratch.

**Mature Atlas** is measured by connectivity and reliability, not page count:
$$\text{high formalization} + \text{high structural connectivity} + \text{high computational accessibility} + \text{high cross-domain correspondence} + \text{high generativity}$$
while preserving: uncertainty + provenance + alternative interpretations.

**Central organizational invariant (permanent):**
$$\boxed{\text{Every important mathematical object can be entered, represented, related, investigated, and traced.}}$$
$$O \rightarrow \{\text{Definition, Properties, Representations, Symmetries, Relations, Proofs, Computations, Applications, Unknowns, Investigations}\}$$

That is the fundamental Atlas interface.
