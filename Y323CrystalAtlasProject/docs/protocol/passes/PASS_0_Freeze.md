# PASS 0 — Freeze

## Goal

Establish the source baseline. No interpretation. No modification.

## Inputs

- All files in `docs/source/`

## Source document classes

Documents are frozen regardless of class, but only Foundational documents
are inputs to downstream passes. See BUILD_PROTOCOL.md §Source Document Classes.

    FOUNDATIONAL (inputs to Passes 1–9)
      0  — Why This Crystal
      I  — Roadmap
      II — Atlas
      III— Schema

    GROWTH (informs evolution model, not V1)
      IV — Field Guide

    VISION (context only; not a pass input)
      V-a — Asimyth Game
      V-b — Machine Resonance

## Instructions

1. List every source document by class and name.
2. Record version, date, and any stated status for each.
3. Compute a SHA-256 hash of each file.
4. Record declared dependencies between documents.
5. Record any document naming collisions
   (e.g., two documents both titled "V").
6. Do not summarize, interpret, or reconcile.
7. Do not edit any source file.

## Output

`planning/SOURCE_BASELINE.md` in this format:

    # Source Baseline

    Frozen: <date>

    ## Foundational

    | File | Version | Date | Hash | Depends on |
    |------|---------|------|------|------------|

    ## Growth

    | File | Version | Date | Hash | Depends on |
    |------|---------|------|------|------------|

    ## Vision

    | File | Version | Date | Hash | Depends on |
    |------|---------|------|------|------------|

    ## Naming collisions

    (record any two documents sharing a numeral, title, or filename)

    ## Notes

    (anything explicitly stated about document status)

## After producing output

Update `BUILD_STATUS.md`:
- mark PASS 0 as CLOSED
- set current pass to PASS 1 — Archive
- set next allowed action to "Run Archivist on Foundational documents only"

Then stop.