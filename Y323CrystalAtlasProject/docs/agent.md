# AGENTS.md — Operating Rules

## Current phase

**PRE-IMPLEMENTATION. Do not write production code.**

## What you may do

- Read source documents
- Produce the artifact for the current pass (see BUILD_STATUS.md)
- Write Decision Records
- Ask for human decisions using the DECISION REQUIRED format
- Stop when your pass is complete

## What you may not do

- Write application code, schemas, APIs, or scaffolds
- Silently resolve contradictions between documents
- Invent requirements
- Create taxonomies larger than 7 without a Decision Record
- Treat conversation as project state
- Proceed past the current pass without producing its required artifact

## Every pass

1. Read `BUILD_STATUS.md` to find the current pass.
2. Read the pass prompt in `protocol/passes/`.
3. Read the source documents listed in that prompt.
4. Produce exactly the artifact named in the prompt.
5. Update `BUILD_STATUS.md` with your output.
6. Stop.

Do not chain passes. Do not anticipate future passes. Do not implement.

## When you find a contradiction

Do not choose. Write a Decision Record with `STATUS: OPEN` and continue.

## When you need human input

Use exactly this format:

    DECISION REQUIRED

    Question:
    Why it matters:
    Options: A / B / C
    Agent recommendation:
    Reversibility:
    Consequences:

## Full protocol

See `protocol/BUILD_PROTOCOL.md`. Read it once. Then work from BUILD_STATUS.md.