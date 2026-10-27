# PASS 1 — Archive

## Goal

Extract, without interpretation, the definitions, principles, requirements,
invariants, scope boundaries, open questions, and ambiguities present in the
Foundational source documents.

The purpose of this pass is fidelity. Not synthesis. Not reconciliation.
Not improvement.

A later pass may organize what the Archivist extracts. No later pass may
recover material the Archivist discarded.

## Inputs

Foundational documents only:

    0  — Why This Crystal
    I  — Roadmap
    II — Atlas
    III— Schema

Do not read the Field Guide (Doc IV).
Do not read the Vision documents (Docs V-a, V-b).

Those documents are frozen (see `SOURCE_BASELINE.md`) but are not inputs to
this pass. Reading them here risks introducing requirements that are not
Foundational.

## What "archive" means

The Archivist is a recorder, not a translator.

- Quote the source where a quote is sufficient.
- Paraphrase only when a quote would be misleading (e.g., a formula).
- Preserve the source's own vocabulary. Do not substitute synonyms.
- Preserve the source's own hedging. If a statement says "should," do not
  record it as "must." If a statement says "may," do not record it as "is."
- If two documents state the same thing differently, record both. Do not
  merge them.

## Extraction categories

Each extracted item receives exactly one category.

    DEF      Definition of a term, object, or structure
    PRIN     Explicit principle or stated design rule
    REQ      Explicit requirement the software must satisfy
    HINT     Explicit implementation hint or suggestion
    INV      Explicit invariant stated as permanent
    SCOPE    Explicit statement of what is or is not in scope
    MVP      Explicit item belonging to the first implementation
    LEDGER   Epistemic ledger entry (established / derived / conjectural /
             open / falsifiable)
    OPEN     Explicit open question
    AMB      Ambiguity: a term or claim used without definition, or used
             in two ways without acknowledgement
    CONFLICT Raw disagreement between documents (see below)
    INFER    An inference drawn by the Archivist (must be marked as such —
             see "Inferences" below)
    DECIDED  A decision already made in the source that must not be re-opened
             without new evidence

## What the Archivist may NOT do

The Archivist may NOT:

1. Reconcile contradictions. If Doc II and Doc III disagree, record both.
   The disagreement is material for Pass 3, not for Pass 1.
2. Simplify terminology. If Doc II says "transformation" and Doc III says
   "operation," both terms are recorded.
3. Choose a preferred formulation. If a concept has two descriptions, both
   are recorded.
4. Assess correctness. Whether a claim is true is not the Archivist's
   question. Doc 0 §8 already states the document's own epistemic stance;
   the Archivist records that stance. It does not independently evaluate it.
5. Invent requirements. If the source does not say it, it is not extracted.
   Absence of a requirement is not itself a requirement.
6. Collapse categories. A statement may be a principle and an invariant and
   a scope boundary. Record it once, under its most specific category, and
   note the others. Do not duplicate it silently.
7. Promote hedging. "Should," "may," "likely," "candidate," and "proposed"
   are load-bearing. Preserve them.
8. Cite the Field Guide or Vision documents. Even if a later reading of
   them seems relevant, they are not inputs here.

## Inferences

If the Archivist finds that a connection between two extracted items is
unavoidable — for example, two documents clearly describe the same object
under different names — that connection is recorded as an INFER item, with:

- the items it connects (by their identifiers)
- the reasoning
- an explicit note that the connection is the Archivist's, not the source's

The Archivist's inference is not a source claim. It must never appear inside
a DEF, PRIN, REQ, or INV record.

## Identifier scheme

Every extracted item receives an identifier of the form:

    <CATEGORY>-<NNN>

with sequential numbering within category. Identifiers are stable for the
life of the build. Later passes reference these identifiers directly.

Example: `REQ-014`, `INV-003`, `LEDGER-009`.

## Output

Produce a single file: `planning/ARCHIVE_REPORT.md`

The file has six parts, in this order:

    # Archive Report

    Pass: 1
    Date: <date>
    Source baseline: <hash / reference to SOURCE_BASELINE.md>
    Documents read: Doc 0, Doc I, Doc II, Doc III

    ---

    ## Part 1 — Per-document extraction

    For each Foundational document, in order:

    ### Doc <N> — <title>

    Items extracted:

    <ID> | <section reference>
    Category: <CATEGORY>
    Content:
    <verbatim quote or precise paraphrase>
    Notes: <only if required; otherwise omit>

    (repeat for each item)

    ---

    ## Part 2 — Cross-document ledger (Doc 0 §8)

    Transcribe the epistemic ledger from Document 0 §8 without merging
    categories. Format:

    ### Established
    <LEDGER-NNN> <statement>

    ### Derived, awaiting formalization
    <LEDGER-NNN> <statement>

    ### Conjectural
    <LEDGER-NNN> <statement>

    ### Open
    <LEDGER-NNN> <statement>

    ### Falsifiable predictions
    <LEDGER-NNN> <statement>

    ---

    ## Part 3 — MVP boundary (Doc III §16)

    Transcribe the initial implementation scope from Doc III §16 verbatim.

    <MVP-NNN> <item>
    ...

    Do not extend, trim, or reword this list. It is the source's own MVP
    candidate, not the Archivist's.

    ---

    ## Part 4 — Permanent invariants (collected)

    List every statement in the Foundational documents that is explicitly
    marked as permanent, central, or non-negotiable.

    <INV-NNN> | <source> | <verbatim statement>

    Include at minimum:
    - Doc II §14 (organizational invariant and foundational rules)
    - Doc III §17 (schema invariants)
    - Doc I §4 (key principles)
    - Any boxed \boxed{} statement in Docs 0–III that reads as an invariant

    ---

    ## Part 5 — Already-decided in source

    List decisions already made in the Foundational documents that a later
    pass might be tempted to re-open.

    <DECIDED-NNN> | <source> | <decision>

    Examples of the kind of item that belongs here:
    - Entity identity persists across revisions (Doc III §3)
    - Status is not evidence (Doc II §3, Doc III §7)
    - Relations are first-class entities (Doc III §4)
    - Labels are not identity (Doc III §3)
    - Attributes may graduate to entities (Doc II §1, Doc III §5)
    - Unknowns are first-class entities (Doc II §13.10, Doc III §10)
    - The Atlas is not closed (Doc II §13.12)

    Later passes must not re-open an item in this section without new
    evidence and a Decision Record.

    ---

    ## Part 6 — Raw conflict log

    Record every disagreement, duplication, or competing formulation the
    Archivist noticed between documents. Do not resolve.

    <CONFLICT-NNN> | <doc A section> vs. <doc B section>
    Description: <what disagrees>
    Both formulations preserved at: <DEF-xxx>, <DEF-yyy>

    Known candidate for this pass (verify and record):
    - Doc II names nine primitive entity types; Doc III §2 names six
      primitives. Both claim to be "the deepest level." Record both.

    ---

    ## Coverage

    Documents read: <list>
    Documents skipped: <list, with reason>
    Known gaps: <anything the Archivist could not extract cleanly>

    ---

    ## Inference register

    <INFER-NNN> | connects <ID> and <ID>
    Reasoning: <...>
    Note: this is an Archivist inference, not a source claim.

    (If none, write "none".)

## After producing output

Update `BUILD_STATUS.md`:
- mark PASS 1 as CLOSED
- set current pass to PASS 2 — Map
- set next allowed action to "Run Cartographer and Terminologist on
  Foundational documents, using ARCHIVE_REPORT.md as the extraction base"

Then stop. Do not begin Pass 2.