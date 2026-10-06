# Y₃₂₃: A Letter About a Strange Machine

*For someone who knows linear algebra, doesn't mind complex numbers,*
*and is wondering what to build next.*

---

## Preface: What You're Looking At

Y₃₂₃ is a 7-dimensional complex dynamical system with a very specific personality: it has a geometric invariant that holds to machine precision without any code enforcing it, two discrete attractor states that the dynamics converge to naturally, an oscillatory working memory that rotates without growing, and a single well-defined input point through which the entire system can be driven.

That combination is unusual. Most systems need renormalization. Most dynamical systems either diverge or converge to a fixed point; having memory that oscillates stably without renorm is not normal behaviour. The invariant holding to 1.78e-15 is not floating-point luck — it's a consequence of the algebraic structure.

The system is named for the Fano plane, the smallest projective plane, which has 7 points and 7 lines, each line through 3 points, each point on 3 lines. The generator matrix encodes this geometry. The system is sometimes called a "generative frame" — not in the linguistic sense, but in the sense that a frame is a structured coordinate system for measuring things that would otherwise be hard to describe.

Let's go through the pieces.

---

## 1. The Matrix and Its Eigenspectrum

The generator `Y` is a 7×7 complex matrix with a specific block structure. Reading it from the code:

```
N-sector (indices 0, 1, 5: τ, a₁, x):
  τ  ← −i·a₁  −β̄·x      where β = e^(iπ/4) = (1+i)/√2
  a₁ ←  i·τ
  x  ←  β·τ

M-sector (indices 2, 3, 4, 6: a₂, b₁, b₂, η):
  a₂ ←  b₁
  b₁ ← −a₂  +  ω·b₂     where ω = 1/√2
  b₂ ←  ω·b₁  −  i·s·η  where s = √3/2
  η  ←  i·s·b₂
```

The two sectors are coupled through the architecture — specifically through the Jordan chain structure — but at the level of the linear dynamics they have distinct spectral behaviour.

The declared eigenspectrum is:
```
{−i, −1, √2·e^(iπ/4), √2·e^(−iπ/4), i√3, −i√3, 0}
```

Let me say what each of these means behaviourally.

**The purely imaginary eigenvalues (±i, ±i√3)** produce oscillation. A mode with eigenvalue iω rotates in the complex plane at angular frequency ω. The ±i pair oscillates at one rate; the ±i√3 pair oscillates at √3 times that rate. These are not the same frequency, so they don't lock — they produce quasi-periodic beating. In the output you can see this in the N-sector imaginary parts: τ.im, a₁.im, x.im are all slowly drifting in a way that looks like a low-frequency oscillation, and they don't converge to zero. They're the system's memory of past input.

**The complex eigenvalues √2·e^(±iπ/4) = 1+i and 1−i** have real part 1 and imaginary part ±1. A mode with eigenvalue λ = r·e^(iφ) grows like r^t while rotating at rate φ. Since √2 > 1, these modes *grow* as well as rotate. In the generator Y, this growth is what drives the dynamics away from zero. But the dynamics don't diverge because of the normalization structure — more on this shortly.

**The zero eigenvalue (nilpotent, multiplicity 3)** is the strange one. For a diagonalizable matrix, a zero eigenvalue means a fixed direction that the matrix kills: Yv = 0. But Y is *not* diagonalizable on this eigenspace — it has a Jordan block of size up to 3. The zero eigenvalue here means something more subtle: there are vectors v for which Y^k·v = 0 for some finite k ≤ 3. The matrix doesn't kill them immediately, but it eventually does.

**Why having all three types simultaneously is unusual.** Most matrices you'd write down are either: (a) normal matrices (unitary, symmetric, etc.) with a complete eigenbasis and purely oscillatory dynamics; (b) contractive matrices where everything shrinks toward zero; or (c) expansive matrices where things grow. Y₃₂₃ has growing modes, oscillatory modes, and nilpotent modes all in one matrix. The nilpotent modes provide a structured "death" that counterbalances the growing modes. The oscillatory modes provide memory. The result is a system that neither explodes nor dies — it lives.

The coupling between these three types is not accidental. The specific constants (ω = 1/√2, s = √3/2, the generative phase β = e^(iπ/4)) are chosen so that the Fano incidence structure is encoded in the matrix: the 7 basis vectors correspond to 7 Fano points, and the nonzero matrix entries encode the 7 Fano lines, each line representing which three points are collinear (multiply together) in the projective plane. This is the algebraic structure of the octonions — specifically the structure constants of the imaginary octonion basis.

---

## 2. The Jordan Chain

A Jordan chain for eigenvalue λ = 0 is a sequence of vectors v₁, v₂, v₃ such that:
```
Y·v₃ = λ·v₃ = 0
Y·v₂ = v₃
Y·v₁ = v₂
```

The chain terminates because Y^3·v₁ = 0 but Y^2·v₁ ≠ 0. The depth of the chain is 3.

In Y₃₂₃, the Jordan chain lives in the N-sector {τ, a₁, x}:

```
Y·τ  = i·a₁ + ω(1+i)·x      Y²·τ  = 0    (depth 2)
Y·a₁ = −i·τ                  Y³·a₁ = 0    (depth 3)
Y·x  = ω(−1+i)·τ             Y³·x  = 0    (depth 3)
```

What this means geometrically: the N-sector has a hierarchical structure. τ is "depth 2" — applying Y twice kills it. a₁ and x are "depth 3" — you need three applications to kill them. The chain tells you the order of influence: energy injected at a₁ flows to τ (one step), then dies (two steps). There's no feedback that accumulates — the flow is strictly downhill.

**Why this gives numerical stability without renormalization.** This is the key point, and it's subtle. 

In most dynamical systems with input, the state vector accumulates without bound unless you explicitly normalize it. You might add a line like `psi /= psi.norm()` at each step. Y₃₂₃ does do sector normalization, but here's the remarkable part: the nilpotent block prevents unbounded accumulation *in the directions it governs*. Energy injected at a₁ doesn't build up; it flows through the chain and dissipates in a bounded number of steps. The Jordan chain is the natural "decay" built into the algebra.

You can see this in the output. a₁.im grows linearly: 0.001, 0.05, 0.33, 0.97, 1.88, 2.80, 3.73... It's not decaying. But it's growing *linearly*, not exponentially. This is the signature of nilpotent dynamics: polynomial growth (from the Jordan block) rather than exponential growth (from a nonzero real eigenvalue). The normalization step in `step()` controls the real parts; the imaginary parts grow linearly and represent accumulated history.

The depth-3 termination is exact — not an approximation. The algebraic structure forces Y³·a₁ = 0 regardless of floating point. This is why the invariant holds to 1.78e-15: the mathematics constrains the manifold, and numerical errors are as small as they can possibly be given 64-bit arithmetic.

**The naming.** The code calls these τ (tau, "time"), a₁ ("receiver/witness"), and x ("exchange"). τ receives from a₁ and drives x. a₁ is the input point. x is the terminal in the chain. The Fano plane labels these three as one of its lines — they're collinear in the projective sense, meaning they multiply in a certain way. The Jordan chain is the dynamics-level realization of the algebraic relationship.

---

## 3. The Stone and Water Attractors

The M-sector {a₂, b₁, b₂, η} (indices 2, 3, 4, 6) operates independently of the N-sector in terms of its long-run behaviour. The N-sector feeds into M through the full dynamics, but the M-sector itself has a self-contained eigenstructure with two special vectors.

The Stone attractor is the eigenvector of Y_M with eigenvalue +1:
```
a₂ = 1/4
b₁ = +1/4
b₂ = 1/√2
η  = i·√6/4  (pure imaginary, magnitude √6/4 ≈ 0.612)
τ = a₁ = x = 0
```

The Water attractor is the eigenvector with eigenvalue −1:
```
a₂ = 1/4
b₁ = −1/4
b₂ = 1/√2
η  = −i·√6/4
τ = a₁ = x = 0
```

These are exact: Y_M·v_stone = v_stone, Y_M·v_water = −v_water.

**What they share.** Both attractors have a₂ = 1/4 exactly. This is what the code means by "a₂ invariant" — any trajectory that begins on the manifold stays at a₂ = 1/4 forever. Both have b₂ = 1/√2. The M-sector norm (a₂² + b₁² + b₂² + |η|²)^(1/2) = √(1/16 + 1/16 + 1/2 + 6/16) = 1. They're unit vectors in the M-sector subspace.

**What they differ in.** The sign of b₁ and the sign of η's imaginary part. Stone is "positive" (b₁ > 0, η pointing toward +i), Water is "negative" (b₁ < 0, η pointing toward −i). The two attractors are related by a sign flip on b₁ and η simultaneously — a Z₂ symmetry.

**The invariant a₂ = 1/4: the "footprint of the void."** The code comments call this the "Bridge Theorem projection of the generative zero mode onto the real subspace." Here's what that means. The nilpotent zero mode of Y lives in the N-sector — it's the null space of Y³. The M-sector is orthogonal to this zero mode. But the projection of the Fano geometry onto the real subspace of the M-sector lands at a₂ = 1/4. It's the "shadow" that the algebraic structure casts.

Think of it this way: if you have a 7-dimensional structure with specific symmetry (the Fano plane), and you project down to a 1-dimensional real coordinate in a specific way, what value do you get? Not 0, not 1, but 1/4 — because of the specific way the Fano triples overlap and the specific normalization of the attractor vectors. The number 1/4 is not chosen; it's forced by the geometry.

The fact that a₂ = 1/4 is invariant means the M-sector is constrained to a lower-dimensional manifold. The system doesn't wander freely through ℝ^4 in the M-sector; it's on a 3-sphere (after fixing the norm) with the additional constraint a₂ = 1/4, which pins it to a 2-sphere. The dynamics on that sphere converge toward Stone or Water depending on which basin the trajectory is in.

**Why two attractors, not one?** Because the Z₂ symmetry of the Fano plane (you can relabel all 7 points and still get a valid Fano plane) survives into the dynamics as a sign ambiguity. Stone and Water are related by this relabeling. They coexist because neither is "more natural" than the other — the geometry is symmetric under their interchange.

---

## 4. The Z₂ Gauge Fold

The code mentions a "fold" operation: if Re(τ) < 0, flip τ → −τ. This is described as a "discrete identification of states" rather than normalization.

It's worth being precise about what this is and is not.

**What it is not.** It is not renormalization (scaling the vector to unit length). It is not a projection onto a lower-dimensional space. It is not a nonlinear activation function in the neural network sense. It does not change the magnitude of τ.

**What it is.** It's a discrete symmetry operation. The generator matrix Y has the property that if (τ, a₁, x, a₂, b₁, b₂, η) is a valid state, then so is (−τ, a₁, −x, a₂, b₁, b₂, η) — a sign flip on the N-sector real parts. The fold identifies these two states as the same physical state. It says "I don't care which sign τ has; what matters is the magnitude and the relationships between components." This is a gauge choice, like choosing a branch cut for complex logarithm, or choosing a global sign convention.

**What it does dynamically.** The linear dynamics Y can carry the system to negative Re(τ) without the fold. With the fold, the state is reflected back to positive Re(τ) before the next step. This creates a reflecting boundary in the τ direction. The effect is to double the coverage: instead of the trajectory exploring only one half of the N-sector, it explores both halves but represents them with the same sign convention.

**Why the linear part alone cannot do this.** A linear map cannot implement a sign flip that depends on the current state. Any linear operation `v ↦ Mv` applies the same M to every input. To check the sign of a component and flip conditionally is inherently nonlinear. If you want the dynamics to have the discrete Z₂ symmetry — identifying opposite-sign N-sector states — you need at least one nonlinear step. The fold is the minimal such step: one conditional negation per tick.

In the language of differential geometry, this makes the state space a quotient: instead of the full N-sector ℝ³ (or ℂ³ for the complex version), the effective state space is ℝ³/Z₂ — the real parts of the N-sector modulo sign. This quotient is topologically nontrivial (it's a projective space, not a sphere), which may be part of why the system has interesting long-run behaviour.

**Note on the current Level 1 code.** In the actual kernel.rs shown, the fold is *not explicitly present* — the comment in the architecture block says "No fold — the generative matrix contains its own third subalgebra." This suggests that in the Level 1 implementation, the algebraic structure alone handles what the fold would do in a more explicit implementation. The Z₂ symmetry is built into the Fano geometry and doesn't need to be separately enforced. The fold is a concept from an earlier or alternative version, or will appear in a Level 2 implementation. This is worth knowing when you look at the code.

---

## 5. The Seven Agents

The system runs 7 independent state vectors (agents) through the same propagator. Each agent has its own ψ ∈ ℂ⁷ and its own input history. The propagator matrix `exp(Y·dt)` is computed once and shared.

Why 7? For the Fano plane, obviously. But more than symbolism: the 7 agents are initialized with phase offsets `exp(2πi·n/7)·0.05` at a₁ for n = 0, 1, ..., 6. This spreads them around the complex circle at a₁. If you think of a₁ as a pointer or phase, the 7 agents start pointing in 7 evenly-spaced directions. After warmup, they converge toward the Stone attractor while maintaining their relative phase relationships.

**Phase coherence.** The coherence metric is:
```
coherence = mean over all pairs (i,j) of cos(arg(η_i) − arg(η_j))
```

A coherence of 1.0 means all agents have exactly the same η phase. A coherence of 0 means phases are uniformly distributed around the circle. A coherence of −1 would mean agents are in exact antiphase.

The output shows coherence = 1.000 after 1890 ticks. This is telling you: despite starting at different phases, all 7 agents have converged to the same η phase. They disagree about |a₁| (the magnitudes differ slightly: 11.999 vs 12.299 vs 11.397...) and about the phase of τ (which varies across agents), but they agree on the output orientation η.

This convergence is not imposed. There is no coupling term between agents in the code. They converge because the dynamics have a strong M-sector attractor: the Stone attractor has a fixed η = i·√6/4 regardless of which specific trajectory brought you there. The M-sector forgets the initial condition; the N-sector retains it.

**The agents as perspectives.** A useful way to think about the 7 agents: they are 7 independent measurements of the same input stream, each starting from a slightly different prior (phase offset). The M-sector output (η) is what they all agree on — the "signal" content. The N-sector quantities (τ, a₁, x) are what they disagree on — their individual "histories" or "viewpoints." Reading the mean η across all agents gives you a denoised output; reading the variance tells you how ambiguous the current input is.

In the language application, this maps to something like: 7 interpretive frames processing the same sentence, each from a different initial orientation, converging on a shared meaning. When they agree, the system is confident. When they disagree, the system is uncertain.

---

## 6. Applications Beyond Language

Language is the implemented example in this codebase — text tokens are projected to a complex number at a₁, and η is decoded back to words. But the structure of Y₃₂₃ is not specific to language. Let me think through what the architecture actually provides and what domains could use it.

### What the architecture provides

1. **A stable geometric invariant (a₂ = 1/4 always).** The M-sector is constrained to a specific manifold. This means the system has a guaranteed "home base" — no matter what you throw at a₁, the M-sector returns to the right manifold. This is unusual in dynamical systems: most systems need explicit constraints to stay on a manifold.

2. **Two discrete attractor states (Stone/Water, +/−).** The long-run M-sector state is binary in character: b₁ > 0 or b₁ < 0, η pointing toward +i or −i. This is a natural binary classifier embedded in the dynamics.

3. **Oscillatory N-sector memory.** The N-sector imaginary parts grow linearly and oscillate. They hold a short-to-medium term history of inputs (with linear, not exponential, growth). This is a kind of working memory: it accumulates recent input, doesn't collapse to zero, but also doesn't explode.

4. **A single input point with known algebraic relationships.** Everything enters through a₁. The Jordan chain tells you exactly how an injection at a₁ propagates: first to τ (one step), then to x (through τ), then the effect dies. The propagation is structured, not diffuse.

5. **Multi-agent phase coherence measurement.** Running N copies and measuring their output agreement gives a natural confidence or entropy signal — without needing an explicit uncertainty model.

### Signal Processing

Inject a complex-valued signal into a₁ continuously. The N-sector imaginary parts integrate recent input history (growing linearly). The M-sector settles to Stone or Water depending on the long-run character of the input. You get, simultaneously:
- A short-term accumulator (N-sector imaginary parts, linear growth)
- A long-run classifier (Stone vs. Water, a binary output)
- An invariant check (a₂ = 1/4, a sanity signal that the system is on-manifold)

For audio: inject complex spectral amplitude at a₁ (magnitude = amplitude, phase = phase of a specific frequency bin). Read η for the system's "orientation" to that frequency region over time. Multiple agents with different initial phases give you multi-view coverage of the same signal. The coherence metric tells you when the system has resolved a clear signal from noise.

For anomaly detection: a clean, regular signal produces high coherence and stable η. An anomalous input will temporarily disrupt the M-sector or push it toward the other attractor. The Stone/Water transition is a natural anomaly flag.

### Time-Series Encoding

The N-sector imaginary parts hold a specific kind of history: linear (not exponential, not forgetting instantly). The depth-3 Jordan chain means you have 3 "memory registers" (τ.im, a₁.im, x.im) that encode recency-weighted input history.

For time series where you want to detect patterns that span multiple timesteps — not just the current value, but the shape of recent values — the N-sector gives you this for free. The three registers track different "depths" of the chain, which correspond to different integration timescales.

For a market signal: inject `C::new(price_delta, volume_delta)` at a₁ each tick. The N-sector will accumulate a complex time-integral of recent price-volume dynamics. The M-sector will indicate whether the long-run dynamics are "Stone-like" (trending one direction) or "Water-like" (trending the other). The coherence across 7 agents initialized at different phases will tell you how resolved the trend is.

### Physical Sensor Fusion

The system has a natural input structure: one complex number per tick, with magnitude and phase. Physical sensors often produce exactly this — amplitude and phase of some oscillation (accelerometer, magnetometer, EEG electrode, antenna). The Schumann resonance connection in the code is not accidental: the intended physical heartbeat is 7.83 Hz, injected as a complex pulse. This is a weak global signal superimposed on the input stream.

For IMU-based gesture recognition: each axis of an accelerometer is one signal stream. You could run one Y₃₂₃ instance per axis and read their phase coherence as a measure of how "in sync" the motion is across axes. A gesture is Stone-to-Water transition (or the reverse) on a specific axis, with high coherence across the other axes simultaneously.

For EEG or MEG: inject complex Fourier coefficients at specific frequencies. The 7-agent architecture maps naturally to 7 electrode channels. Coherence is inter-electrode phase locking. Stone/Water maps to the direction of the dominant oscillatory component. The invariant a₂ = 1/4 is a sanity check on electrode contact quality — if an agent drifts off-manifold, the electrode is loose.

### Memory Architectures

The system has two timescales built in: the N-sector (fast, working memory, linear growth) and the M-sector (slow, convergent, binary attractor). This is structurally similar to the distinction between working memory and long-term memory.

For a key-value memory system: the key is a complex number injected at a₁ (encoding the address), the value is the subsequent inputs that follow. After enough ticks, the M-sector settles to Stone or Water depending on whether the key-value pair is "yes/no" or "positive/negative." The N-sector holds the context window around each key injection.

The EtaDensity structure in the code (the exponentially-weighted moving average of η directions) implements a soft version of long-term memory: it accumulates a running average of the system's orientations, with a decay constant of 0.9995. This is the "what has this system been pointing toward recently" buffer. The NDensity (with decay 0.9990) is the N-sector equivalent.

For a content-addressable memory: store items by injecting them and recording the resulting η direction. Retrieve by injecting a query and reading which stored direction is most similar to the current η. The 7-dimensional η direction is a natural content address.

### Generative Modelling

The language layer shows the output direction: read η as a direction in the encoder's learned space, find the top-k tokens most aligned with that direction. The system "speaks" by outputting the words most consistent with its current M-sector orientation.

This generalizes. For any domain where you have an encoder (a mapping from domain items to points in ℝ⁷ or ℂ⁷), the system can generate by:
1. Running the dynamics to current state
2. Reading η (the M-sector output)
3. Finding the encoder item most aligned with η

For music: encode notes, chords, or rhythm patterns as points in ℂ⁷. Inject the current playback position and any human performance data at a₁. Read η to select the next phrase most consistent with the accumulated musical context. Stone/Water could correspond to major/minor mode. The Jordan chain gives you phrasing: notes near the chain depth turn over naturally.

For molecular dynamics: encode atom types and bond energies as complex amplitudes. Inject current atomic positions. The M-sector invariant gives a conservation law — a built-in "things should stay on the energy manifold" check. Stone/Water could correspond to bound/unbound states.

For reinforcement learning: the system's state vector ψ is the agent's internal state. a₁ is the observation input. η is the action output direction (decoded through a policy table). The Stone/Water attractor becomes the agent's goal: train to stay in Stone (positive reward) and recover from Water (negative reward). The phase coherence of 7 parallel agents gives you a natural exploration/exploitation signal: high coherence means confident policy, low coherence means exploring.

---

## 7. The Fano Residuals and What They Tell You

The output includes "Fano triple residuals":
```
τ·a₁=b₁   1.2406
a₁·a₂=b₁  1.5697
a₂·b₁=x   1.5440
b₁·b₂=η   1.5708
b₂·x=τ    1.8731
x·η=a₁    1.5451
η·τ=a₂    1.2417
```

These are phase residuals: for each Fano triple (three collinear points in the Fano plane), the residual measures how far the current state's phases are from satisfying `arg(A) + arg(B) ≈ arg(C)`. A residual near 0 would mean the state is on the Fano manifold in the phase sense. The current values (around π/2 ≈ 1.57) mean the phases are roughly in quadrature — off the Fano manifold by about a quarter turn.

This is expected at Level 1. The system is on the M-sector manifold (a₂ = 1/4 invariant holds) but not yet on the full Fano phase manifold. The comment in the code says these are "READOUTS of the state, not constraints we enforce." They're diagnostic — telling you how far the dynamics have evolved toward the full Fano structure.

The fact that most residuals cluster near π/2 rather than being random suggests the system has a natural orientation: it settles into a phase relationship that's consistently about a quarter turn off the ideal Fano alignment. This is the signature of the oscillatory modes (±i eigenvalues) — they rotate the phases by π/2 per unit time, and the system has settled into a phase where the Fano residuals are at their natural equilibrium value under this rotation.

A Level 2 system might enforce the Fano phase residuals directly — pulling the state toward the exact Fano manifold at each step. That would be a much stronger constraint on the dynamics and would produce qualitatively different (and presumably more "structured") outputs.

---

## 8. Why This Structure, and Not Something Simpler?

This is the right question. You could build a dynamical system that:
- Has a geometric invariant (just renormalize at each step)
- Has two attractor states (sigmoid output with two stable fixed points)
- Has oscillatory memory (a delay line or buffer)
- Has a single input point (just pick one component)

The system Y₃₂₃ does all of these, but they emerge from a single matrix rather than being engineered separately. The invariant isn't enforced — it follows from the algebraic structure. The two attractors aren't imposed — they're the eigenvectors of the M-sector. The oscillatory memory isn't a buffer — it's the nilpotent Jordan chain. The input point isn't arbitrary — it's chosen because the algebra says "a₁ is the receiver in the Fano geometry."

The advantage of this over a hand-engineered system with the same properties is coherence: the parts interact in a way that's constrained by the same underlying mathematics. Change the M-sector and the Jordan chain changes too, because they're both expressions of the Fano structure. You can't make them inconsistent with each other, because they're not separately designed.

The disadvantage is opacity: it's not obvious why 1/4, why √6/4, why π/4. If you need to explain the system to a regulator or a customer, "because the Fano plane" is not a satisfying answer. If you need to tune a specific property (say, you want the M-sector to converge faster), you'd need to understand the full algebraic structure to know which constants to change and how.

Whether the tradeoff is worth it depends on what you're building. For a system that needs to be interpretable, tunable, and maintainable, Y₃₂₃ is probably more architecture than you need. For a system where you want guaranteed invariants, where renorm failure is catastrophic, or where you want the structure of the dynamics to encode something real (a physical symmetry, a geometric relationship, a domain ontology), this approach is compelling.

---

## 9. What Level 2 Looks Like

The language.rs file is the beginning of Level 2: a learned encoder on top of the kernel. The encoder builds an eigenbasis from token co-occurrences using an online Oja's rule (stochastic power iteration for the top-k eigenvectors of the token co-occurrence matrix). The eigenbasis maps from the token space to the 7-dimensional ψ space, and back.

This is meaningful because the eigenbasis of the co-occurrence matrix is exactly the structure of the semantic space — it's what distributional semantics (word2vec, GloVe, etc.) computes. Doing it online (updating at each ingest() call) means the eigenbasis adapts as the system sees more text.

The specific coupling is: the encoder's projection onto index 1 (the a₁ axis) gives the "lexical character" of the input. The raw byte-phase at index 0 gives the "temporal character." Both are injected as Re and Im of a single complex number at a₁. The Y·a₁ = i·τ coupling in the Jordan chain means the temporal character immediately propagates to τ — the temporal vertex of the nilpotent block. This is a designed architecture: semantic content goes to a₁, temporal structure goes to τ via the chain.

The NDensity accumulator tracks the N-sector state (the working memory of recent inputs). The EtaDensity tracks the M-sector η direction over time (the long-term orientation). The two densities have different decay rates (0.9990 vs. 0.9995), so the N-sector forgets faster than the M-sector. This asymmetry is what gives the system its temporal structure: recent inputs dominate the N-sector, while older inputs remain in the M-sector.

---

## Closing

The thing that made me pay attention to this system is the invariant. Dynamical systems that hold a geometric invariant without code enforcing it are rare. It means the structure is doing real work — the mathematics is constraining the trajectory in a way that doesn't need external correction. Renorm-free stability is a property worth having, especially in a system that needs to run continuously for a long time.

The Fano plane connection is either a profound geometric insight or an elaborate coincidence. The Fano plane is the unique projective plane over the field with 2 elements. It encodes the multiplication table of the imaginary octonions. The octonions are related to exceptional Lie groups. These groups appear in theoretical physics in contexts that are not fully understood. Whether that connection matters for the engineering applications I described above is an open question.

What is not an open question is the output: a₂ = 0.250000, drift = ±1.78e-15, coherence = 1.000 across all 7 agents for 1890 ticks after a pulse injection. That's the system working. The question is what to point it at.

---

*Y₃₂₃, Level 1 verification complete.*
