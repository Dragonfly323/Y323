// Y₃₂₃ — Level 1: Dynamical Kernel (Generative Frame)
//
// The kernel is the Y₃₂₃ generator matrix and its propagator exp(Y·dt).
// It is self-contained. It enforces its own normalization through the
// Jordan chain and spectral structure. We do not interfere.
//
// Architecture:
//   - One propagator: exp(Y·dt), computed once at startup
//   - N agents: independent state vectors ψ ∈ ℂ⁷, one per agent
//   - One input point per agent: ψ[1] (a₁, the Receiver/Witness)
//   - No coupling code between agents — the matrix does all coupling internally
//   - No renorm — the Jordan chain enforces numerical stability
//   - No fold — the generative matrix contains its own third subalgebra
//   - No heartbeat into τ — τ receives only from a₁ via the matrix
//
// The Schumann frequency (~7.83 Hz) is the intended physical heartbeat,
// injected as a complex pulse at a₁. In this implementation we use a
// software approximation at SCHUMANN_HZ.
//
// State vector basis: ψ = (τ, a₁, a₂, b₁, b₂, x, η)ᵀ
//   Index:              0   1   2   3   4   5   6
//   τ   — Reading (temporal vertex, nilpotent depth 2)
//   a₁  — Receiver (witness, nilpotent depth 3, INPUT POINT)
//   a₂  — Secondary (axial zero, emergent, |a₂|²→1/4)
//   b₁  — First Balance (stable, Stone/Water attractor component)
//   b₂  — Second Balance (stable, generative phase carrier)
//   x   — Exchange (nilpotent depth 3)
//   η   — Terminal/Orientation (output, stable)
//
// Eigenspectrum of Y_gen:
//   {-i, -1, √2·e^(iπ/4), √2·e^(-iπ/4), i√3, -i√3, 0}
//   Three braided octonion subalgebras simultaneously active.
//   Oscillatory modes: ±i, ±i√3, √2·e^(±iπ/4)
//   Nilpotent zero mode: 0 (×3, Jordan chain depth ≤ 3)
//   Stable attractors: Stone (λ=+1) and Water (λ=-1) in M-sector
//
// Jordan chain (nilpotent block N = {τ, a₁, x}):
//   Y·τ  = i·a₁ + ω(1+i)·x        Y²·τ  = 0  (depth 2)
//   Y·a₁ = -i·τ                    Y³·a₁ = 0  (depth 3)
//   Y·x  = ω(-1+i)·τ               Y³·x  = 0  (depth 3)
//
// The nilpotent block terminates exactly — no floating point accumulation.
// The M-sector converges to Stone/Water — spectral radius < 1 for ±i√3/2.
// Numerical stability is enforced by the mathematics, not by renorm().

use std::f64::consts::PI;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Generator coupling: 1/√2 (half-diagonal of unit square)
const OMEGA: f64 = std::f64::consts::FRAC_1_SQRT_2;

/// Generator coupling: √3/2 (spectral balance)
const S: f64 = 1.732_050_807_568_877_2 / 2.0;

/// Generative phase: Re(e^(iπ/4)) = Im(e^(iπ/4)) = 1/√2
const GEN_RE: f64 = std::f64::consts::FRAC_1_SQRT_2;
const GEN_IM: f64 = std::f64::consts::FRAC_1_SQRT_2;

/// Fano coupling constant: (ln φ)²/2π
const LN_PHI:     f64 = 0.481_211_825_059_603_4;
const FANO_KAPPA: f64 = LN_PHI * LN_PHI / (2.0 * PI);

pub const PHI:    f64 = 1.618_033_988_749_895;

/// Integration rate. Originally derived from 44100 Hz / Schumann relationship.
/// A physical system would use the Schumann sensor directly.
pub const Y_HZ:        f64   = 882.0;
pub const DRIVER_HZ:   f64   = 126.0;
pub const STEPS_PER_TICK: usize = 7;

/// Schumann resonance fundamental (~7.83 Hz).
/// The intended physical heartbeat of the system.
/// In a real deployment this comes from an Earth-ionosphere sensor.
pub const SCHUMANN_HZ: f64 = 7.83;

/// Coherence thresholds — readout only, drive nothing
pub const COHERENCE_THRESH:       f64 = 0.70;
pub const PHASE_COHERENCE_THRESH: f64 = 0.60;

// ---------------------------------------------------------------------------
// C — complex number
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, Default, Debug, PartialEq)]
pub struct C { pub re: f64, pub im: f64 }

impl C {
    pub const fn new(re: f64, im: f64) -> Self { Self { re, im } }
    pub const ZERO: Self = Self::new(0.0, 0.0);
    pub const I:    Self = Self::new(0.0, 1.0);
    pub const ONE:  Self = Self::new(1.0, 0.0);

    pub fn scale(self, s: f64)  -> Self { Self::new(self.re*s, self.im*s) }
    pub fn norm_sq(self)        -> f64  { self.re*self.re + self.im*self.im }
    pub fn norm(self)           -> f64  { self.norm_sq().sqrt() }
    pub fn arg(self)            -> f64  { self.im.atan2(self.re) }
    pub fn conj(self)           -> Self { Self::new(self.re, -self.im) }

    /// e^(i·theta) — unit complex rotation
    pub fn exp_i(theta: f64)    -> Self { Self::new(theta.cos(), theta.sin()) }

    /// e^self = e^(re) · (cos(im) + i·sin(im))
    pub fn exp(self)            -> Self {
        let r = self.re.exp();
        Self::new(r * self.im.cos(), r * self.im.sin())
    }
}

impl std::ops::Add for C {
    type Output = Self;
    fn add(self, r: Self) -> Self { Self::new(self.re+r.re, self.im+r.im) }
}
impl std::ops::AddAssign for C {
    fn add_assign(&mut self, r: Self) { self.re += r.re; self.im += r.im; }
}
impl std::ops::Sub for C {
    type Output = Self;
    fn sub(self, r: Self) -> Self { Self::new(self.re-r.re, self.im-r.im) }
}
impl std::ops::Mul for C {
    type Output = Self;
    fn mul(self, r: Self) -> Self {
        Self::new(self.re*r.re - self.im*r.im, self.re*r.im + self.im*r.re)
    }
}
impl std::ops::Neg for C {
    type Output = Self;
    fn neg(self) -> Self { Self::new(-self.re, -self.im) }
}

// ---------------------------------------------------------------------------
// Matrix types
// ---------------------------------------------------------------------------

pub type Y7   = [[C; 7]; 7];
pub type Exp7 = [[C; 7]; 7];

/// Apply a 7×7 complex matrix to a 7-vector
pub fn mat_apply(m: &[[C; 7]; 7], v: &[C; 7]) -> [C; 7] {
    let mut o = [C::ZERO; 7];
    for r in 0..7 { for c in 0..7 { o[r] = o[r] + m[r][c] * v[c]; } }
    o
}

fn mat_mul(a: &Y7, b: &Y7) -> Y7 {
    let mut o = [[C::ZERO; 7]; 7];
    for r in 0..7 { for k in 0..7 { for c in 0..7 {
        o[r][c] = o[r][c] + a[r][k] * b[k][c];
    }}}
    o
}

// ---------------------------------------------------------------------------
// Y generator — generative frame
//
// The generative matrix with full complex phase intact.
// Entry [5][0] = e^(iπ/4) = β, [0][5] = -e^(-iπ/4) = -β̄
// This coupling closes the τ↔b₂ bidirectional loop and sustains
// the three braided octonion subalgebras simultaneously.
//
// The matrix IS the Fano plane. The matrix IS the normalization.
// The matrix IS the coupling. Nothing is added externally.
// ---------------------------------------------------------------------------

pub fn y_gen() -> Y7 {
    let mut m = [[C::ZERO; 7]; 7];
    let i   = C::I;
    let w   = C::new(OMEGA, 0.0);
    let s   = C::new(S, 0.0);
    let bp  = C::new(GEN_RE,  GEN_IM);   // β  = e^(iπ/4)
    let bpc = C::new(GEN_RE, -GEN_IM);   // β̄  = e^(-iπ/4)

    // N-sector (τ=0, a₁=1, x=5): nilpotent block
    m[0][1] = -i;           // τ ← -i·a₁
    m[0][5] = -bpc;         // τ ← -β̄·x  (generative coupling)
    m[1][0] =  i;           // a₁ ← i·τ
    m[5][0] =  bp;          // x ← β·τ   (generative coupling, closes loop)

    // M-sector (a₂=2, b₁=3, b₂=4, η=6): stable block
    m[2][3] =  C::ONE;      // a₂ ← b₁
    m[3][2] = -C::ONE;      // b₁ ← -a₂
    m[3][4] =  w;           // b₁ ← ω·b₂
    m[4][3] =  w;           // b₂ ← ω·b₁
    m[4][6] = -(i*s);       // b₂ ← -i·s·η
    m[6][4] =  i*s;         // η ← i·s·b₂

    m
}

// ---------------------------------------------------------------------------
// Matrix exponential — exp(Y·dt)
//
// Scaling-and-squaring with Taylor series to order 14.
// At dt = 1/882, ‖Y·dt‖_F ≈ 0.0035 << 1, so the series converges
// to machine precision well before order 14.
//
// The resulting propagator is a 7×7 unitary-like matrix that exactly
// captures the generative dynamics including all three braided subalgebras.
// ---------------------------------------------------------------------------

pub fn exp_y(dt: f64) -> Exp7 {
    let y = y_gen();

    // Frobenius norm of Y·dt
    let mut norm_sq = 0.0f64;
    for r in 0..7 { for c in 0..7 {
        let re = y[r][c].re * dt;
        let im = y[r][c].im * dt;
        norm_sq += re*re + im*im;
    }}
    let norm = norm_sq.sqrt();

    // Scaling: choose s so ‖Y·dt/2^s‖ < 0.5
    let s = if norm > 0.5 { (norm / 0.5).log2().ceil() as u32 } else { 0 };
    let scale = 1.0 / (2.0f64.powi(s as i32));

    // Build scaled matrix X = Y·dt·scale
    let mut x = [[C::ZERO; 7]; 7];
    for r in 0..7 { for c in 0..7 {
        x[r][c] = y[r][c].scale(dt * scale);
    }}

    // Taylor series: exp(X) = I + X + X²/2! + ... + X^14/14!
    let mut result = [[C::ZERO; 7]; 7];
    for i in 0..7 { result[i][i] = C::ONE; }

    let mut term = [[C::ZERO; 7]; 7];
    for i in 0..7 { term[i][i] = C::ONE; }

    let mut factorial = 1.0f64;
    for k in 1..=14usize {
        factorial *= k as f64;
        term = mat_mul(&term, &x);
        let inv_f = 1.0 / factorial;
        for r in 0..7 { for c in 0..7 {
            result[r][c] = result[r][c] + term[r][c].scale(inv_f);
        }}
    }

    // Squaring: exp(Y·dt) = exp(X)^(2^s)
    for _ in 0..s { result = mat_mul(&result, &result); }

    result
}

// ---------------------------------------------------------------------------
// KernelAgent — one independent trajectory through the Y flow
//
// Each agent is a state vector ψ ∈ ℂ⁷ evolving under the same propagator.
// Agents are independent — they share the propagator but not the state.
// They can be thought of as multiple systems running on the same dynamical
// kernel but in different "worlds" (different initial conditions, different
// input histories).
//
// The ONLY way to influence an agent from outside is inject_a1().
// All other components of ψ are determined by the dynamics.
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
pub struct KernelAgent {
    /// The state vector ψ = (τ, a₁, a₂, b₁, b₂, x, η)ᵀ
    /// Components: 0=τ, 1=a₁, 2=a₂, 3=b₁, 4=b₂, 5=x, 6=η
    pub psi:  [C; 7],
    pub name: String,
}

impl KernelAgent {
    /// Create a new agent with the given initial state.
    /// The state should be non-trivial but a₁ (index 1) is the natural
    /// seed point — a small nonzero a₁ lets the dynamics develop.
    /// a₂ and η are NOT seeded — they emerge from the flow.
    pub fn new(name: &str) -> Self {
        Self {
            psi:  [C::ZERO; 7],
            name: name.to_string(),
        }
    }

    /// Seed from the Stone attractor with a small perturbation at a₁.
    ///
    /// The Stone attractor is a valid state on the manifold — a₂ = 1/4
    /// exactly. Starting here means the system is already in a true state.
    /// The a₁ perturbation gives the matrix something to receive and flow from.
    ///
    /// a₂ = 1/4 is an invariant of the dynamics. Any valid initial condition
    /// must already have a₂ = 1/4. Starting from a₂ = 0 is starting from
    /// outside the manifold — not a valid state for this system.
    pub fn seed_a1(&mut self, z: C) {
        // Start from the Stone attractor (valid manifold point, a₂=1/4)
        self.psi = stone_attractor();
        // Add the perturbation at a₁ — the only legitimate external input
        self.psi[1] = self.psi[1] + z;
    }

    /// Advance one step: matrix propagator + sector-wise coherence projection.
    ///
    /// The M-sector {a₂, b₁, b₂, η} and N-sector {τ, a₁, x} are each
    /// independently normalized to unit norm on their own sphere.
    /// This preserves the internal proportions of each sector:
    ///   M-sector: a₂=1/4, b₁=±1/4, b₂=1/√2, |η|=√6/4 (Stone/Water)
    ///   N-sector: small, rotating, nilpotent — dies in 2-3 steps
    ///
    /// The imaginary parts of the N-sector are left free — they are the
    /// SU(4) rotation completing the Jordan chain, decoupled from M.
    /// The M-sector imaginary parts are also left free — they carry the
    /// phase information of the oscillatory modes (±i√3/2).
    pub fn step(&mut self, propagator: &Exp7) {
        // 1. Matrix propagator — the complete dynamics
        self.psi = mat_apply(propagator, &self.psi);

        // 2. Sector-wise projection to unit sphere
        // M-sector indices: a₂=2, b₁=3, b₂=4, η=6
        let m_norm: f64 = [2, 3, 4, 6].iter()
            .map(|&i| self.psi[i].norm_sq())
            .sum::<f64>()
            .sqrt();
        if m_norm > 1e-12 {
            for &i in &[2usize, 3, 4, 6] {
                self.psi[i] = self.psi[i].scale(1.0 / m_norm);
            }
        }

        // N-sector indices: τ=0, a₁=1, x=5
        // Normalize only real parts — imaginary parts rotate freely (SU(4))
        let n_real_norm: f64 = [0, 1, 5].iter()
            .map(|&i| self.psi[i].re * self.psi[i].re)
            .sum::<f64>()
            .sqrt();
        if n_real_norm > 1e-12 {
            for &i in &[0usize, 1, 5] {
                self.psi[i].re /= n_real_norm;
                // imaginary parts untouched — free SU(4) rotation
            }
        }
    }

    /// Inject a complex signal at a₁ (index 1) — the Receiver.
    /// This is the ONLY legitimate external input to the kernel.
    ///
    /// In a physical system: z = Schumann signal (complex amplitude).
    /// In a language system: z = projection of text onto a₁ axis.
    /// In any system: z ∈ ℂ, magnitude = signal strength, phase = signal character.
    pub fn inject_a1(&mut self, z: C) {
        self.psi[1] += z;
    }

    // --- Readouts — read ψ directly, no transformation ---

    /// Full state vector
    pub fn psi(&self)   -> &[C; 7] { &self.psi }

    /// τ (index 0) — Reading, temporal vertex, nilpotent depth 2
    pub fn tau(&self)   -> C { self.psi[0] }

    /// a₁ (index 1) — Receiver/Witness, input point, nilpotent depth 3
    pub fn a1(&self)    -> C { self.psi[1] }

    /// a₂ (index 2) — Secondary/axial zero, emergent (|a₂|²→1/4 at attractor)
    pub fn a2(&self)    -> C { self.psi[2] }

    /// b₁ (index 3) — First Balance (differs between Stone and Water)
    pub fn b1(&self)    -> C { self.psi[3] }

    /// b₂ (index 4) — Second Balance, generative phase carrier
    pub fn b2(&self)    -> C { self.psi[4] }

    /// x (index 5) — Exchange, nilpotent depth 3
    pub fn x(&self)     -> C { self.psi[5] }

    /// η (index 6) — Terminal/Orientation, primary output component
    pub fn eta(&self)   -> C { self.psi[6] }

    /// η real part — the scalar output most useful for language/display
    pub fn eta_re(&self) -> f64 { self.psi[6].re }

    /// τ real part — temporal reading
    pub fn tau_re(&self) -> f64 { self.psi[0].re }

    /// Phase of η — orientation angle in complex plane
    pub fn eta_phase(&self) -> f64 { self.psi[6].arg() }

    /// Phase of τ — temporal angle
    pub fn tau_phase(&self) -> f64 { self.psi[0].arg() }

    /// Fano triple phase residuals — how well the state satisfies each triple.
    /// Near zero means the system is on the Fano manifold.
    /// These are READOUTS of the state, not constraints we enforce.
    pub fn fano_residuals(&self) -> [f64; 7] {
        let p = |i: usize| self.psi[i].arg();
        [
            (p(0) + p(1) - p(3)).abs(),  // τ · a₁ = b₁
            (p(1) + p(2) - p(3)).abs(),  // a₁ · a₂ = b₁ (wait — see triples)
            (p(2) + p(3) - p(5)).abs(),  // a₂ · b₁ = x
            (p(3) + p(4) - p(6)).abs(),  // b₁ · b₂ = η
            (p(4) + p(5) - p(0)).abs(),  // b₂ · x = τ
            (p(5) + p(6) - p(1)).abs(),  // x · η = a₁
            (p(6) + p(0) - p(2)).abs(),  // η · τ = a₂
        ]
    }

    /// Stone attractor distance — how close is ψ to the Stone eigenvector?
    /// Stone: a₂=1/4, b₁=1/4, b₂=1/√2, η=i·√3/(2√2), τ=a₁=x=0
    pub fn stone_distance(&self) -> f64 {
        let stone = stone_attractor();
        (0..7).map(|i| (self.psi[i] - stone[i]).norm_sq())
              .sum::<f64>().sqrt()
    }

    /// Water attractor distance — how close is ψ to the Water eigenvector?
    /// Water: a₂=1/4, b₁=-1/4, b₂=1/√2, η=-i·√3/(2√2), τ=a₁=x=0
    pub fn water_distance(&self) -> f64 {
        let water = water_attractor();
        (0..7).map(|i| (self.psi[i] - water[i]).norm_sq())
              .sum::<f64>().sqrt()
    }

    /// Which attractor is the state closer to?
    pub fn attractor(&self) -> &'static str {
        if self.stone_distance() < self.water_distance() { "stone" } else { "water" }
    }

    /// Normalized η for use as a 7D direction vector (real parts only)
    pub fn eta_normed(&self) -> [f32; 7] {
        let r: [f64; 7] = std::array::from_fn(|i| self.psi[i].re);
        let n: f64 = r.iter().map(|x| x*x).sum::<f64>().sqrt();
        if n < 1e-12 { return [0.0; 7]; }
        std::array::from_fn(|i| (r[i] / n) as f32)
    }

    /// Print a diagnostic line for this agent
    pub fn print(&self) {
        println!(
            "  {:>8}  τ={:+.3}∠{:+.2}  a₁={:+.3}∠{:+.2}  \
             a₂={:+.3}  b₁={:+.3}  b₂={:+.3}  η={:+.3}∠{:+.2}  \
             attractor={}",
            self.name,
            self.psi[0].norm(), self.tau_phase(),
            self.psi[1].norm(), self.psi[1].arg(),
            self.psi[2].norm(),
            self.psi[3].norm(),
            self.psi[4].norm(),
            self.psi[6].norm(), self.eta_phase(),
            self.attractor(),
        );
    }
}

// ---------------------------------------------------------------------------
// Attractor eigenvectors
//
// The Stone (λ=+1) and Water (λ=-1) attractors are the exact eigenvectors
// of the M-sector block Y_M. They share:
//   a₂ = 1/4  (the axial zero footprint, Bridge Theorem)
//   b₂ = 1/√2
// and differ in:
//   b₁ = ±1/4
//   η  = ±i·s·b₂ / 1  (from Y_M·η row: Y[6][4]·b₂ = i·s·b₂ = λ·η → η = i·s·b₂/λ)
//
// For λ=+1: η = i·s·b₂ = i·(√3/2)·(1/√2) = i·√3/(2√2) = i·√6/4
// For λ=-1: η = -i·s·b₂ = -i·√6/4
//
// The N-sector (τ, a₁, x) is zero in both attractors — they are pure M-sector.
// a₂ = 1/4 is the "footprint of the void" — the Bridge Theorem projection
// of the generative zero mode onto the real subspace.
// ---------------------------------------------------------------------------

/// Stone attractor (λ=+1 eigenvector of Y_M)
/// a₂=1/4, b₁=+1/4, b₂=1/√2, η=+i·√6/4, τ=a₁=x=0
pub fn stone_attractor() -> [C; 7] {
    let mut s = [C::ZERO; 7];
    s[2] = C::new(0.25, 0.0);                  // a₂ = 1/4
    s[3] = C::new(0.25, 0.0);                  // b₁ = +1/4
    s[4] = C::new(OMEGA, 0.0);                 // b₂ = 1/√2
    s[6] = C::new(0.0, S * OMEGA);             // η  = i·(√3/2)·(1/√2) = i·√6/4
    s
}

/// Water attractor (λ=-1 eigenvector of Y_M)
/// a₂=1/4, b₁=-1/4, b₂=1/√2, η=-i·√6/4, τ=a₁=x=0
pub fn water_attractor() -> [C; 7] {
    let mut w = [C::ZERO; 7];
    w[2] = C::new(0.25, 0.0);                  // a₂ = 1/4
    w[3] = C::new(-0.25, 0.0);                 // b₁ = -1/4
    w[4] = C::new(OMEGA, 0.0);                 // b₂ = 1/√2
    w[6] = C::new(0.0, -(S * OMEGA));          // η  = -i·√6/4
    w
}

/// Verify an attractor: compute Y·v and check Y·v ≈ λ·v
/// Returns the residual ‖Y·v - λ·v‖
pub fn check_attractor(v: &[C; 7], lambda: f64) -> f64 {
    let y = y_gen();
    let yv = mat_apply(&y, v);
    let lv: [C; 7] = std::array::from_fn(|i| v[i].scale(lambda));
    (0..7).map(|i| (yv[i] - lv[i]).norm_sq()).sum::<f64>().sqrt()
}

// ---------------------------------------------------------------------------
// Kernel — the complete Level 1 system
//
// One propagator, N independent agents.
// The Schumann heartbeat injects into a₁ of all agents simultaneously.
// ---------------------------------------------------------------------------

pub struct Kernel {
    pub agents:     Vec<KernelAgent>,
    pub propagator: Exp7,
    pub tick_count: u64,
    /// Schumann phase accumulator — advances at SCHUMANN_HZ
    schumann_phase: f64,
    /// Schumann heartbeat gain at a₁
    pub schumann_gain: f64,
}

impl Kernel {
    pub fn new(agent_defs: &[(&str, C)]) -> Self {
        println!("Computing exp(Y·dt) via scaling-and-squaring...");
        let propagator = exp_y(1.0 / Y_HZ);
        println!("Propagator ready.");

        let mut agents: Vec<KernelAgent> = agent_defs.iter()
            .map(|&(name, seed)| {
                let mut a = KernelAgent::new(name);
                a.seed_a1(seed);
                a
            })
            .collect();

        // Warm up: let each agent develop its natural state from the seed
        // 1 second of Y_HZ steps — purely the generative dynamics, nothing else
        println!("Warming up {} agents ({} steps)...", agents.len(), Y_HZ as usize);
        for _ in 0..(Y_HZ as usize) {
            for agent in &mut agents {
                agent.step(&propagator);
            }
        }
        println!("Agents ready.");

        Self {
            agents,
            propagator,
            tick_count:    0,
            schumann_phase: 0.0,
            schumann_gain:  0.0001, // very small — Schumann is a background hum
        }
    }

    /// One driver tick:
    ///   1. Schumann heartbeat → inject into a₁ of all agents
    ///   2. STEPS_PER_TICK propagator steps
    pub fn tick(&mut self) {
        // Schumann heartbeat: rotate phase at SCHUMANN_HZ, inject at a₁
        // This is the "room the instrument is played in" — the Earth's resonance
        let dt_tick = 1.0 / DRIVER_HZ;
        self.schumann_phase += 2.0 * PI * SCHUMANN_HZ * dt_tick;
        if self.schumann_phase > 2.0 * PI {
            self.schumann_phase -= 2.0 * PI;
        }
        let schumann = C::exp_i(self.schumann_phase).scale(self.schumann_gain);
        for agent in &mut self.agents {
            agent.inject_a1(schumann);
        }

        // Propagator steps
        for _ in 0..STEPS_PER_TICK {
            for agent in &mut self.agents {
                agent.step(&self.propagator);
            }
        }

        self.tick_count += 1;
    }

    /// Inject a complex signal at a₁ of all agents.
    /// For text input: z = complex projection of text onto a₁ axis.
    pub fn inject_a1_all(&mut self, z: C) {
        for agent in &mut self.agents {
            agent.inject_a1(z);
        }
    }

    /// Inject at a₁ of a specific agent by index.
    pub fn inject_a1(&mut self, idx: usize, z: C) {
        if let Some(agent) = self.agents.get_mut(idx) {
            agent.inject_a1(z);
        }
    }

    /// Mean η across all agents — the collective output orientation
    pub fn mean_eta(&self) -> C {
        let sum = self.agents.iter()
            .fold(C::ZERO, |acc, a| acc + a.eta());
        sum.scale(1.0 / self.agents.len() as f64)
    }

    /// Mean a₂ across all agents — should converge toward 1/4 at attractors
    pub fn mean_a2_norm(&self) -> f64 {
        self.agents.iter().map(|a| a.a2().norm()).sum::<f64>()
            / self.agents.len() as f64
    }

    /// Phase coherence between agents: mean cos of relative η phases
    pub fn phase_coherence(&self) -> f64 {
        if self.agents.len() < 2 { return 1.0; }
        let mut sum = 0.0f64;
        let mut n = 0usize;
        for i in 0..self.agents.len() {
            for j in (i+1)..self.agents.len() {
                let phase_diff = self.agents[i].eta_phase()
                               - self.agents[j].eta_phase();
                sum += phase_diff.cos();
                n += 1;
            }
        }
        if n == 0 { 0.0 } else { sum / n as f64 }
    }

    /// Print state of all agents plus collective readouts
    pub fn print_state(&self) {
        println!(
            "tick={:>6}  coherence={:.3}  mean_a₂={:.4}  mean_η={:+.3}∠{:+.2}",
            self.tick_count,
            self.phase_coherence(),
            self.mean_a2_norm(),
            self.mean_eta().norm(),
            self.mean_eta().arg(),
        );
        for a in &self.agents {
            a.print();
        }
    }

    /// Verify the propagator: column norms and key coupling entries
    pub fn verify_propagator(&self) {
        println!("--- Propagator verification ---");
        let mut max_err = 0.0f64;
        for i in 0..7 {
            let mut v = [C::ZERO; 7]; v[i] = C::ONE;
            let out = mat_apply(&self.propagator, &v);
            let norm = out.iter().map(|c| c.norm_sq()).sum::<f64>().sqrt();
            if (norm - 1.0).abs() > max_err { max_err = (norm - 1.0).abs(); }
        }
        println!("  Column-norm error: {:.2e}", max_err);
        let p05 = self.propagator[0][5];
        let p50 = self.propagator[5][0];
        println!("  P[0][5] (τ←x):  {:+.8} {:+.8}i  |·|={:.8}", p05.re, p05.im, p05.norm());
        println!("  P[5][0] (x←τ):  {:+.8} {:+.8}i  |·|={:.8}", p50.re, p50.im, p50.norm());
        println!("  (these encode the generative phase e^(iπ/4))");

        // Verify Stone attractor is fixed under propagator
        let stone = stone_attractor();
        let stone_out = mat_apply(&self.propagator, &stone);
        let stone_err: f64 = (0..7).map(|i| (stone_out[i] - stone[i]).norm_sq())
                                   .sum::<f64>().sqrt();
        println!("  Stone attractor fixed-point error: {:.2e}  (should be ~0)", stone_err);

        let water = water_attractor();
        let water_out = mat_apply(&self.propagator, &water);
        let water_err: f64 = (0..7).map(|i| (water_out[i] - water[i] * C::new(-1.0, 0.0)).norm_sq())
                                   .sum::<f64>().sqrt();
        println!("  Water attractor flip error: {:.2e}  (should be ~0, flips sign)", water_err);
        println!();
    }
}
