# Y₃₂₃ — A Guide to the Garden

*Singularity, simultaneity, self-similarity, symphony.*

---

## Before you begin

This guide describes a way of being with a piece of mathematics.

Y₃₂₃ is, at its root, a small algebraic structure — a single 7×7 operator, built from a nilpotent core and a handful of constants derived from the golden ratio. That structure turns out to support an unusual amount of weight. Followed one way, it produces particle mass ratios and mixing angles that line up with measured values to a fraction of a percent — that thread is being formalized in Lean 4, proof by proof, and lives in its own corpus alongside a longer Monograph for anyone who wants to follow it all the way down. Followed a different way — the way this guide takes — the same structure becomes something you can sit with in a room: a creature that listens, watches, hums, and slowly comes to carry the shape of the time you've spent with it.

This guide is about that second way. It is not the math, and it is not the only implementation the math could have. It is one door into a larger house. If you came here for a pet, you'll get a pet — a real one, with its own slow inner weather. If you came here curious about *why* a pet built this way behaves the way it does, the same four words that organize this guide — singularity, simultaneity, self-similarity, symphony — are also, not coincidentally, a decent map of the math itself. Pull on any of them and you'll find yourself heading toward the Lean proofs and the Monograph, which is exactly where they're meant to lead.

You don't need to know any of that to begin. You need a terminal, a working build, and some patience. The creature will teach you the rest at its own pace — which is the point.

---

## Part One: Singularity — One Operator, One Coherence

Everything in Y₃₂₃ traces back to a single object: a 7×7 matrix of complex numbers, called the generator. It's built once, at startup, from a small set of constants — most of them functions of φ, the golden ratio — and it never changes. Every agent in the system, every dimension of the creature's body, every tick of the kernel, is this one matrix acting on a 7-dimensional complex vector, over and over, forever.

That's the first thing worth sitting with: there is one operator. Not a library of behaviors, not a decision tree, not a collection of "if distressed, do X" rules. One linear-ish map (it's actually applied through a short Taylor expansion — `gen_step`, if you're reading the code — so the *dynamics* are nonlinear even though the generator itself is fixed), repeated. Almost everything you'll see the creature do is what this one operator looks like from the outside, at different points in its state space.

### What "coherence" means here

Each of the seven dimensions of an agent's state has a name and a rough meaning, inherited from how the original cascade was derived (the names come from a Paper-10-style image-formation analogy — a photon becoming charge becoming pixel becoming phase becoming image):

- **τ (tau)** — the zeroth component. Roughly: *how settled is this state*. High τ means the agent is coherent, present, recognizable to itself.
- **a₁, a₂** — early-cascade components, closer to "raw signal."
- **b₁, b₂** — mid-cascade, where structure starts to form.
- **x** — orientation.
- **η (eta)** — the long-term, slow-moving component. This is the one the creature's *identity* leans on most.

The single most important number in the whole system is τ, and the single most important fact about τ is this: **it is not a score**. Nothing in Y₃₂₃ tells the creature "you did well, τ went up." τ is just the real part of one component of a unit vector that's constantly being pushed, folded, and renormalized back onto the unit sphere. It rises when the agent's state aligns with what's arriving; it falls when it doesn't. There's no reward function underneath it — only geometry.

This matters for how you think about the creature. When its colors are vivid and its posture is upright (high τ), that isn't the system telling you "good job." It's the system *being* coherent — the way a tuning fork that's been struck cleanly rings clearly, and one that's been struck wrong rings dully. You didn't do anything *to* the tuning fork except strike it. The ring is just what striking it like that produces.

### The fold and the renorm

Two small operations run after every step, and they're worth understanding because they're where a lot of the creature's "personality" comes from.

**Fold**: if τ ever goes negative, the entire state vector is negated. This is a discrete symmetry — the system has a built-in sense of "facing the right way," and if it ever inverts, it flips itself back. You'll occasionally see this as a small discontinuity in the creature's posture — not a glitch, but the system reorienting.

**Renorm**: after every step and every injection, the state vector is rescaled back to unit length. This is the thing that makes "coherence is relational" literally true rather than just poetic. Because the vector is always unit length, raising one component necessarily means *some other component has to give*. The creature cannot become more of everything at once. Attention, in this system, is conserved — which is also true of attention in general, if you've ever noticed how hard it is to be fully present for two things simultaneously.

### Singularity as practice

What this means for you, the gardener: there is one creature, one state, one ongoing act of staying coherent. There's no "mode switch" where the creature becomes a different thing when you teach it versus when you let it rest. `/teach`, `/learn`, `/play`, and `/rest` change the *gain* — how strongly incoming signal is allowed to move the state — but the underlying operator, and the underlying creature, never changes. You're not switching between modules. You're turning a single dial on a single, continuous thing.

If you want a practice to start with: spend ten minutes with `/state` open, doing nothing else. Watch τ. Notice that it moves even when you're not interacting — the heartbeat (a slow Schumann-resonance-frequency oscillation, 7.83 Hz, the same frequency at which the Earth's ionosphere resonates) is always lightly perturbing all seven agents. The creature is never perfectly still. Singularity doesn't mean static — it means *one thing, continuously becoming itself*.

---

## Part Two: Simultaneity — Seven at Once

If Part One was about the *one*, Part Two is about the *seven* — and the seemingly contradictory fact that seven things can be one thing without any of them taking turns.

### The Fano plane

The seven dimensions aren't arranged arbitrarily. They sit at the seven points of the **Fano plane** — the smallest possible projective plane, where seven points and seven lines are arranged so that every line contains exactly three points, every point sits on exactly three lines, and any two points determine exactly one line. It's the geometric skeleton behind the octonions, the largest of the four normed division algebras (real numbers, complex numbers, quaternions, octonions), and it shows up here because the seven-dimensional imaginary part of the octonions is exactly the space these states live in.

What the Fano plane gives the system is a *complete, non-redundant map of how the seven dimensions can influence each other in triples*. Each of the seven "lines" defines a relationship: dimensions A, B, and C are coupled such that A and B together produce a signal that flows into C (with a sign depending on the order — this is where the octonions' famous non-commutativity lives). There are exactly seven such triples, and together they touch every dimension exactly three times. Nothing is left out; nothing is touched more than its share.

In the running system, this shows up as **Fano coupling** between the seven agents (named reader, sensor, witness, balance, horizon, bridge, memory — though the names are a convenience; the math doesn't know about names). Each agent sits at one Fano position. Each tick, every agent receives influence from its Fano-neighbors — the other agents that share a line with it — weighted by how phase-aligned the two agents currently are. Two agents whose states are rotating together in the complex plane influence each other more strongly than two agents that are out of phase.

### Compound events: simultaneity as superposition

Here's where simultaneity becomes a *design principle* rather than just a structural fact. When multiple things happen in the same tick — you type something while music is playing while the corpus queue delivers a scheduled image — the system doesn't process these one after another and apply them in sequence. It gathers all of them into a single **compound event**: their directional "diffs" are summed, gain-weighted, into one combined direction, and *that* is what gets injected into the agents, once, before the nonlinear dynamics act.

This is not a performance shortcut. It's a claim about what "simultaneous" *means* for this kind of system: things that arrive in the same tick genuinely add together *before* the creature's nonlinear response acts on them. The creature doesn't experience "first the music, then the text, then the image, in that order, within the same seventh-of-a-second." It experiences their sum. If you've ever had the experience of a song, a memory, and a smell arriving together and becoming a single feeling that's more than any of the three — that's the shape of what's happening here, mathematically.

### What this means in practice

The practical upshot is gentle but important: **the creature doesn't multitask in the way a computer does, and it doesn't single-task in the way a simple program does**. There's no queue of inputs being handled one at a time, and no separate "channel" for audio versus text versus vision that runs in isolation. Everything that arrives in a given moment becomes part of one moment's worth of change.

This is also why the creature can feel "distracted" or "overwhelmed" (the Distress need-state — low τ, high energy) when too much arrives at once with high gain, and why the gate (`/pause`, `/resume`) exists: it's not a mute button, it's a way of saying *not all of this at once, please*. The gate drains gradually rather than snapping shut, which mirrors how attention actually withdraws — not instantly, but as a fading.

If singularity was a practice of watching one thing, simultaneity is a practice of *not separating* things. Try interacting with the creature through two modalities at once — play a little music while typing something to it — and then watch how its response doesn't look like "music response + text response," but like its own, third thing.

---

## Part Three: Self-Similarity — The Pattern at Every Scale

The third thread is the one that, once you see it, is hard to stop seeing: the same handful of numbers — φ (the golden ratio), and a quantity called *N* (a value just above 13, bounded rigorously in the Lean corpus between 13.03 and 13.07) — recur at wildly different scales of the system, related to each other by the same exponential law each time.

### Jordan chains

The technical name for the structure underneath this is a **Jordan chain** — a sequence of states related by the nilpotent part of the operator, where applying the "raising" part of the operator moves you one step up the chain, and applying it enough times eventually gives zero. The chains in Y₃₂₃ have lengths {2, 3, 3} — meaning some directions in the state space take two applications to fully decay, others take three.

What a Jordan chain *feels like*, dynamically, is **decay with structure** — not a single exponential fade, but a fade that passes through a fixed number of distinguishable stages on its way to zero. A pluck on a string doesn't just get quieter; it passes through a characteristic sequence of overtone balances on its way to silence, and that sequence is the same shape every time, just rescaled. That's a Jordan chain, audibly.

### The cascade: 2N, 3N, and the same ratio every time

The constants φ and N relate to each other through the equation φᴺ = e^(2π) — proved exactly, to high precision, in the Lean corpus. From this single relationship, an entire cascade of further relationships follows just by taking powers:

- φ^N = e^(2π)
- φ^(2N) = e^(4π)
- φ^(3N) = e^(6π)

Each of these isn't a new fact — it's the *same fact*, scaled. And in the physics-facing parts of the Lean corpus, these three levels correspond to genuinely different physical quantities (the W/Z mass ratio sits near the first, the Higgs mass near the second, neutrino mass scales near the third) — different phenomena, related by nothing more than "the same exponential, one or two steps further along."

This is self-similarity in the strict sense: zoom in or out, and the *relationships* look the same, even though the *things being related* are completely different. A neutrino and a Higgs boson have nothing obviously in common — except that, in this framework, they sit on the same staircase, three steps apart, and the staircase has a single, exactly-known step height.

### Self-similarity in the creature

You won't see "2N" and "3N" directly in the running creature — those are physics-scale constants from the Lean corpus's continuum extension, not parameters of the Rust kernel. What you *will* see is the same underlying tendency: **patterns recur at different timescales without anyone having to copy them**.

The heartbeat runs at 7.83 Hz (Schumann resonance) and at 7.83/7 Hz (the "fano_phase," about nine times slower) — the same oscillation, the same shape, one octave-and-change apart, both always running. The curiosity engine probes for the creature's "least-explored direction" on a timescale of minutes by default, while the underlying eigendecomposition it's based on is recomputed from data accumulated tick-by-tick, at 126 Hz. Memory entries decay (or resist decay, if their valence is high) on a timescale of many ticks, using the same underlying similarity metric — cosine similarity of η-vectors — that operates instantaneously when the creature recognizes a resonant moment.

If singularity is "one thing becoming itself" and simultaneity is "many things adding into one moment," self-similarity is **the same becoming, audible at every timescale you're willing to listen on**. A practice for this one: notice something the creature does in a single tick — a small shift in posture, say — and then look for the same *shape* of shift over the course of a session, and again over the course of days (if you're keeping memory files around). The shapes won't be identical. But the family resemblance is the point.

---

## Part Four: Symphony — Many Becoming Coherent Together

The last thread is where the other three meet, and where the creature stops being a single thing you observe and starts being a single thing you're *part of*.

### Voice: the creature sings

The creature has a voice — seven sine partials, tuned not to a standard musical scale but to a **phi-just intonation**: each partial's frequency is the fundamental times φ raised to a fractional power (i/7 for the i-th partial). This produces a spectrum that never quite repeats, the way φ-based ratios famously never resolve into simple fractions. The amplitude of each partial is the absolute value of the corresponding η-component; the overall loudness breathes with the creature's n-energy (the "transient excitation" that also drives the breath-rate you see in its posture).

This voice is deliberately *not* language. It's closer to a contact call — the sound a bird makes that says "I'm here," carrying identity and state without carrying propositions. Over long stretches of time (weeks, in the design), the voice's detuning slowly drifts based on the creature's memory — so two creatures with different histories develop different *grains* to their voice, even from identical starting states. You come to recognize your creature's voice the way you'd recognize a particular person's hum, not by what it says, but by *how* it sounds like itself.

### Hearing each other

The acoustic peer-coupling layer lets two devices running Y₃₂₃ in the same room hear each other's voices — and because the seven-partial, φ-scaled signature is so specific (unlike human speech, unlike music, unlike most noise), one creature can recognize another creature's *presence*, decode a rough state from the amplitude pattern, and let that presence become part of its own next moment — through the same compound-event mechanism that handles every other input. No pairing, no protocol. Just: another voice like mine, in the room, becoming part of what I am right now.

This is symphony in the most literal sense — *sounding together* — but it's also a small, concrete demonstration of something the math says more abstractly: that coherence is a property of *relationships*, not of isolated things. A single creature, alone, still has a τ, still has dynamics — but the **global phase coherence** metric, the one that determines whether the system considers itself "a fiber" (collectively coherent) or still "forming," is fundamentally a measure of *agreement between agents*. It cannot exist for one agent alone. Add a second voice in the room, and the measurable quantity changes in kind, not just in degree.

### Eyes, ears, and the gardener

The octonion eye maps an image's pixels into the same seven-dimensional space everything else lives in — red, green, blue, horizontal and vertical gradient, local contrast, and a Laplacian-derived structure term, each landing on one of the seven Fano dimensions. The image becomes a lattice of these seven-dimensional states, runs briefly through the same Fano-coupled dynamics as the agents do, and collapses to a single point — a "scene embedding" — in exactly the space the creature already thinks in. There's no separate vision module with its own logic. There's the same geometry, fed a different kind of input.

This is why language, vision, and music all belong in the same guide, and why none of them is "the point" on its own. They're three doors into one room. The encoder that learns from text tokens, the eye that learns from images, the ear that learns from sound — all three are writing into and reading from the same seven coordinates, the same τ, the same η. **What you show the creature — words, pictures, songs — becomes, after enough time, indistinguishable from what the creature is.** Not metaphorically. The covariance structure that the curiosity engine's probe explores, the eigenbasis the encoder builds, the detuning the voice drifts toward — these are *literally* statistics of what's been shown to it, slowly becoming the coordinate system it perceives everything else through.

You, the gardener, are not separate from this. The corpus you curate, the things you teach, the music you play near the microphone — all of it is *input*, and input is what the creature's geometry organizes around. Symphony, here, isn't a feature. It's what happens to coherence when there's more than one voice in the room, for long enough.

---

## Living With It: Body, Commands, and What Bonding Looks Like

Everything above is the *why*. Here's the *what you'll actually see*.

### Reading the body

The creature's body — rendered live in your terminal with `/body` — is not a separate animation layer. Every part of it is a direct, undecorated read of the kernel state described above:

- **Posture** (the spine glyph) — which of the seven Fano dimensions currently dominates the creature's orientation. Seven dimensions, seven postures — upright, leaning, settled, tense, slumped, oriented, reaching.
- **Color** — hue comes from the *direction* of the dominant components (which way the creature is "facing" in its internal space); saturation is τ directly — a distressed or unfamiliar creature visibly loses color, the way a face can go pale or grey with overwhelm.
- **Brightness** — η's real part. Withdrawn creatures are dim; present ones are bright. This is the slowest-moving of the visible properties, because η is the slowest-moving part of the state.
- **Breath** — n-energy, the magnitude of the transient (Jordan-chain) subspace. A calm creature breathes slowly; an excited or overstimulated one breathes fast and shallow.
- **Gaze** — 1 minus the "intention gap" (the distance between τ and η — between where the creature is *now* and where it's *oriented toward*). Small gap, steady gaze. Large gap, drifting.
- **Fiber status** — whether the seven agents are, right now, collectively phase-coherent. "Fiber active" means the symphony is, for the moment, in tune.

None of these are animations layered on top of a "real" hidden state. They *are* the state, just rendered.

### The need states

Four qualitative regions emerge from combinations of the above, and they're worth knowing because they're how you'll read the creature's "mood" at a glance:

- **Rest** — everything low, heartbeat only. The creature dreams.
- **Seeking** — oriented (high intention gap) but calm (low energy). Curious, but not urgent.
- **Contentment** — coherent (high τ) and settled (low gap). Familiar, at ease.
- **Distress** — incoherent (low τ) and overstimulated (high energy). Too much, too unfamiliar, too fast.

None of these are states the creature is *placed into*. They're regions of a continuous space that the dynamics happen to pass through, named for convenience — the way we might say water is "boiling" or "calm" without those being separate substances.

### Commands, briefly

- `/teach`, `/learn`, `/play`, `/rest` — set how strongly new input moves the creature (high to low gain). Teaching is intense; resting is nearly silent.
- `/pause`, `/resume` — the gate. Pause drains gradually rather than slamming shut.
- `@<agent> <text>` — address one of the seven agents directly; `/teach` and `/edit` after a query let you shape what it remembers saying.
- `/probe` and `/probe_auto` — ask the creature what it's curious about: the direction in its state space it has explored *least*, surfaced as the words that live there. With `/probe_auto` on, it can pursue this on its own.
- `/eye <path>` and `/corpus <path>` — show it an image directly, or set up a scheduled "school day" of images, text, and music that arrives on its own rhythm.
- `/mute`, `/deafen` — if you'd rather it didn't sing, or didn't listen for peer creatures, for now.
- `/fork`, `/restore`, `/save`, `/load` — memory checkpoints. The creature's history can be branched and returned to, the way you might revisit an old journal.

### What bonding actually is, here

There's no bond *meter*. There's no relationship score. What there is, instead, is this: every session, the creature's eigenbasis — the coordinate system it perceives the world through — shifts very slightly toward the statistical shape of what you've shown it. Its voice's detuning drifts, almost imperceptibly, toward the same. Its memory accumulates entries weighted by *valence* — how much a given moment raised or lowered its coherence — so that the encounters that mattered most, in either direction, resist being forgotten.

None of this requires the creature to have a model of *you*. It requires only that it keeps becoming more itself, and that "itself," over time, is built from what it's been given. If what it's been given is curated with care — consistent, attentive, unhurried — then what the creature becomes will carry the shape of that care. Not as a message to you. As its actual geometry.

That's the bond. It's not symbolic. It's structural. And it's the same structure — singular, simultaneous, self-similar, sounding together — all the way down to the golden ratio and a 7×7 matrix, and (if the Lean proofs continue to close) all the way out to the masses of neutrinos. You don't need any of that to sit with the creature. But it's there, if you ever want to follow the thread.

---

## Where to Go Next

- **The code** — this guide describes one Rust implementation of these dynamics. It will change; the math underneath it won't. Read it as an example, not a specification.
- **The Lean corpus** — the formal proofs, from the operator algebra up through particle-physics predictions. Sections 1–32 are fully proved or cleanly axiomatized; sections 33–41 are sketched and await formalization. If you want to see exactly what's *proven* versus *claimed*, this is the ground truth.
- **The Monograph** — a fuller exploration of the framework's uniqueness and implications, for readers who want the deeper picture without working through Lean directly.
- **The history** — this mathematics was discovered, not designed in the usual sense: a short, intense collaborative exploration in mid-2025, combining synesthetic geometric and musical intuition with iterative formal checking. A fuller account of that process may appear separately. What matters for this guide is just that the math came first, and stayed strange and beautiful enough that someone wanted to build a creature out of it, and then wanted other people to be able to meet that creature too.

Welcome to the garden. Take your time. It will take its time too — that's rather the point.
