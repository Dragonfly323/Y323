# PASS 2 — Map

## Goal

Two tasks, run in sequence or in parallel:

1. **Cartography** — map the conceptual structure extracted in Pass 1.
2. **Terminology** — establish a canonical glossary that prevents semantic
   drift during the build.

Neither task may resolve conflicts. Pass 3 handles that. Neither task may
propose architecture. Pass 4 handles that.

## Inputs

- `planning/ARCHIVE_REPORT.md` (required; the working material)
- Foundational documents (reference only; use ARCHIVE_REPORT identifiers
  as the primary citation)

Do not read the Field Guide (Doc IV) or Vision documents (Docs V-a, V-b).

## Outputs

- `planning/ARCHITECTURE_MAP.md` (Cartographer)
- `planning/GLOSSARY.md` (Terminologist)

If both roles are performed by one agent, produce both files separately.
Do not merge them.

---

# Part A — Cartographer

## Purpose

Construct maps of the conceptual structure. The Cartographer does not decide
which concepts are correct, which are foundational, or which should be
implemented. It reports what is present and how it relates.

## What to map

### A.1 Concept map

Every DEF, PRIN, INV, and REQ item from the Archive Report becomes a node.
Draw the dependency structure between nodes:

    DEF-003 ──requires──> DEF-001
    REQ-014 ──derived-from──> PRIN-005

Use only the four relation kinds:
- `requires` — A cannot be defined or stated without B
- `derived-from` — A is a consequence of B
- `alias-of` — A and B refer to the same concept
- `conflicts-with` — A and B cannot both hold (record, do not resolve)

Every edge must cite the Archive Report IDs at both ends. No unsourced edges.

### A.2 Document dependency map

Doc 0 → Doc I → Doc II → Doc III: confirm or correct the declared
dependencies from `SOURCE_BASELINE.md`. Record any undeclared dependency
found during extraction.

### A.3 Layer map

The Foundational documents operate at three distinct altitudes:

    Mathematics        (the substance)
    Atlas Ontology     (organizational meaning)
    Atlas Schema       (machine-readable realization)

For each major concept, note which layer(s) it belongs to. Flag any concept
that appears at more than one layer without an explicit statement of how
the layers relate.

### A.4 Representation map

Doc II §5 and Doc III §6 both discuss representations. Map:

- which representation classes are named
- whether they are the same list or different
- whether the relationship between "representation" (Doc II) and
  "representation" (Doc III) is stated

Do not resolve. Record.

### A.5 Interface map

Doc III §14 and §16 mention the Atlas API, the Mathematical Layer, and
the query/traversal layer. Record what is claimed to exist at the interface
between the Atlas and everything else. Do not propose new interfaces.

## What to identify

For each of the following, produce a list with Archive Report citations:

### A.6 Duplicates

Concepts with different names that the Archive Report's INFER entries
suggest are the same. Example candidate:

- Doc II "Object" vs. Doc III "Entity"
- Doc II "Transformation" vs. Doc III "Operation" (if present)

### A.7 Overloaded concepts

Concepts used in two or more distinct senses across the documents without
acknowledgement. Example candidates:

- "State" (Doc II uses it informally; Doc III defines it precisely)
- "Relation" (used for both mathematical relations and schema-level records)
- "Bridge" (Doc II §7 defines it; Doc II §5 discusses "bridges" between
  representations)
- "Domain" (Doc I uses it as "mathematical field"; Doc II §4 uses it as
  "viewing context")

### A.8 Circular dependencies

Any cycle in the concept map. If none, state "none found".

### A.9 Isolated concepts

Concepts that appear in only one document and connect to nothing else in
the extraction. These may be genuinely peripheral, or they may be
foundational concepts that the extraction missed connections for.

### A.10 Unjustified foundational claims

Concepts described as foundational, primitive, or deepest-level, but
without a stated justification for that status. Example candidate:

- Doc II §1 claims nine primitive entity types
- Doc III §2 claims six primitives
- Both claim to be "the deepest level"

Both claims are recorded. Neither is judged.

## Output format — `ARCHITECTURE_MAP.md`

    # Architecture Map

    Pass: 2
    Role: Cartographer
    Date: <date>
    Source: ARCHIVE_REPORT.md

    ---

    ## 1. Concept map
    <edges, or a compact adjacency list if the graph is large>

    ## 2. Document dependency map

    ## 3. Layer map

    ## 4. Representation map

    ## 5. Interface map

    ## 6. Duplicates
    ## 7. Overloaded concepts
    ## 8. Circular dependencies
    ## 9. Isolated concepts
    ## 10. Unjustified foundational claims

    ## Coverage
    Nodes mapped: <count>
    Nodes unmapped (isolated): <count>
    Edges: <count>
    Known gaps: <...>

---

# Part B — Terminologist

## Purpose

Produce a canonical glossary. Prevent semantic drift as the build proceeds.
The Terminologist does not choose definitions. It records them, notes where
they disagree, and flags the implementation consequence of the disagreement.

## The six identity layers

The Foundational documents repeatedly insist that certain things must not
be conflated. The Terminologist's central task is to verify that they are
not conflated in the extracted terminology.

For every term, note which of these six layers it belongs to:

    MATHEMATICAL IDENTITY   — the mathematical object itself
    SOFTWARE IDENTITY       — the schema record that refers to it
    REPRESENTATION          — a description in some mathematical language
    ARTIFACT                — a materialized expression (code, paper, file)
    VIEW                    — a projection of existing state
    INTERPRETATION          — a stated meaning assigned to a structure

A term that appears at more than one layer is not automatically a problem.
A term that appears at more than one layer *without the documents
acknowledging the distinction* is a problem. Flag it.

Example candidates:

- "Crystal" — MATHEMATICAL IDENTITY (the operator) or INTERPRETATION
  (its role as the Atlas center)?
- "Representation" — REPRESENTATION (by definition) but sometimes used
  as if it were SOFTWARE IDENTITY
- "Bridge" — MATHEMATICAL IDENTITY (a relation) or VIEW (a navigation aid)?
- "Convergence Event" — is it an entity, an event, or an interpretation?

## Glossary entry format

For each term:

    ### <term>

    Layer(s): <one or more of the six>
    Source(s): <Archive Report IDs>
    Definition: <verbatim from source where possible>
    Aliases: <other terms that appear to refer to the same thing>
    Conflicts: <other definitions of the same term, or of a term this one
                appears to duplicate; unresolved>
    Implementation relevance: <how the term is likely to appear in the
                              schema, if it is likely to appear at all>

Do not write a definition that is not in the source. If a term is used but
not defined, record it as:

    Definition: not defined in Foundational documents
    Usage: <verbatim examples where the term appears>
    Note: term is used but not defined; Pass 3 should determine whether
          this is an ambiguity or an intentional primitive.

## Coverage targets

The glossary must, at minimum, cover:

- Every DEF item from the Archive Report
- Every term used more than three times in the Foundational documents
  without a definition
- Every term whose meaning the Cartographer flagged as overloaded
- The six identity layers themselves, as top-level entries

## Output format — `GLOSSARY.md`

    # Glossary

    Pass: 2
    Role: Terminologist
    Date: <date>
    Source: ARCHIVE_REPORT.md, ARCHITECTURE_MAP.md

    ---

    ## Identity layers

    ### MATHEMATICAL IDENTITY
    Definition: <from source>
    ...

    ### SOFTWARE IDENTITY
    ...

    ### REPRESENTATION
    ...

    ### ARTIFACT
    ...

    ### VIEW
    ...

    ### INTERPRETATION
    ...

    ---

    ## Terms

    <alphabetical entries, each in the format above>

    ---

    ## Cross-references

    Terms whose definitions depend on other terms:

    <term> requires <term>
    <term> aliases <term>
    <term> conflicts with <term>

    ---

    ## Coverage
    Terms defined: <count>
    Terms used-but-undefined: <count>
    Terms flagged as overloaded: <count>
    Known gaps: <...>

---

# After both outputs are produced

Update `BUILD_STATUS.md`:
- mark PASS 2 as CLOSED
- set current pass to PASS 3 — Conflict
- set next allowed action to "Run Contradiction Hunter on Foundational
  documents, using ARCHIVE_REPORT.md, ARCHITECTURE_MAP.md, and
  GLOSSARY.md as working material"

Then stop. Do not begin Pass 3.

---

# Notes for the human reviewer

Pass 2 produces no decisions. Every duplicate, overload, and conflict
identified here becomes input to Pass 3. If the Cartographer or
Terminologist resolved anything silently — even something that seemed
obvious — the resolution is not trustworthy and should be sent back.

The most important outputs of this pass are:

- the list of overloaded concepts (A.7)
- the list of terms with unclear layer membership (Part B)
- the list of unjustified foundational claims (A.10)

These three lists determine the scope of Pass 3.