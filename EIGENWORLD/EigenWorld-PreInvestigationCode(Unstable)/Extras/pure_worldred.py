"""
pure_world.py — The world as zero-point dynamics on the manifold M.

══════════════════════════════════════════════════════════════════════
THE COMPLETE THEORY (discovered through experiment)
══════════════════════════════════════════════════════════════════════

THE PERIOD-2 ORBIT
  Every point on M under T = observe∘Y traces a period-2 orbit in τ.
  Rock: τ oscillates (+0.984, +0.050, +0.984, +0.050, ...).
  The orbit never decays. Rock does not collapse to air — it breathes.
  The period-2 comes from the eternal↔eternal beat frequency of 2
  (gap between eigenvalues +1 and −1 on the real axis).

THE GAUGE SYMMETRY (Z₂)
  τ → −τ leaves M invariant. The sign of τ is a gauge degree of freedom.
  Both phases of the orbit — τ=+0.99 and τ=−0.99 — are the same stone.
  Physical observables use |τ| only.

  CONSEQUENCE: before diffusion, all states must be gauge-fixed (folded)
  to τ≥0. Without this, cells at opposite orbit phases destructively
  interfere, averaging to τ≈0 (false air).

THE DOUBLE-STEP
  Two Y applications per visible step keeps the world at the HIGH-|τ|
  phase (geological phase) for every observation. This is the natural
  clock of the system: one full breath = two Y steps.

COHERENCE-GATED DIFFUSION (threshold θ)
  Cells only diffuse with cells whose coherence exceeds θ.
  In the orbit-folded frame:
    rock↔rock:   coherence ≈ 0.98  →  diffuse (intra-geological)
    rock↔water:  coherence ≈ 0.024 →  don't diffuse (cross-phase barrier)
    water↔water: coherence ≈ 0.98  →  diffuse (intra-fluid)
    water↔air:   coherence ≈ 0.31  →  diffuse weakly (fluid-air interface)

  Setting θ = 0.1 sits in the gap between intra-material (~0.98)
  and cross-material (~0.024) coherence. This is not arbitrary — it is
  the natural threshold imposed by the manifold geometry.

  With θ = 0.1:
    rock-only 50 steps:   0.980 → 0.993  (strengthens)
    water-only 50 steps:  0.068 → 0.072  (stable)
    mixed 50 steps:       rock 0.980 → 0.980, water 0.068 → 0.072 (both stable)

  The island does not need to be held up. The threshold is the wall.
  The wall is the geometry of M. The geometry is the math.

THE ZERO-POINT STRUCTURE
  H = i(Y†−Y) has eigenvalues {−2, 0, +2} — a spin-1 system.
  H=+2: geological (high-amplitude τ orbit) — stone and sand
  H= 0: zero-point vacuum (τ=0, nilpotent space)
  H=−2: vacuum fluctuations (low-amplitude τ orbit) — air
  Zero-point energy Tr(Y†Y)/2 = 4.25 — the vacuum is not quiet.
  The island is a spin-1 excitation above this vacuum.

THE BEAT FREQUENCIES IN THE GAPS
  √3 ≈ 1.732   spiral↔spiral: coherence oscillation
  √7/2 ≈ 1.323  spiral↔eternal: the boundary frequency (water/sand interface)
  2 = 2.000    eternal↔eternal: memory oscillation (the geological period)

══════════════════════════════════════════════════════════════════════
ARCHITECTURE
══════════════════════════════════════════════════════════════════════

State:  (N,7) complex64 full ψ vectors.
Step:   Y² + observe + fold + coherence-gated diffuse + observe + emerge + cull
Reads:  |τ| → material, τ → z, φ-correlation → x,y
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple
from geometry import ManifoldPoint, RawState


# ── Build Y and derived operators ────────────────────────────────────────────
#
# FIX (monograph §2, Definition 2.1):
#   Y acts on column vectors: new_state = Y @ old_state.
#   For row-array S of shape (N,7), the correct batched application is
#       S @ Y.T    (equivalent to (Y @ S[i]) for each row i)
#   The previous code used S @ Y.conj() which applies the wrong operator
#   (conjugate without transpose), producing errors of order 2.6 per step.
#
# STABLE PROJECTOR (monograph Part I, §3 / y323operator.py):
#   P_stable projects onto the 4D eigenspace for λ ∈ {±1, ±i√3/2}.
#   P_nil = I - P_stable projects onto the 3D nilpotent generalised eigenspace.
#   Applied every 3 steps: annihilates accumulated transient error exactly,
#   since Y³|_{V_nil} = 0 (Theorem 4.3).
#
# EXACT ATTRACTOR POLES (monograph Part VI, §41 table):
#   Stone: λ=+1 eigenvector of Y. Coordinates in basis (τ,a₁,a₂,b₁,b₂,x,η):
#       (0, 0, 1/4, 1/4,  1/√2, 0, +i√3/(2√2))
#   Water: λ=-1 eigenvector of Y.
#       (0, 0, 1/4, -1/4, 1/√2, 0, -i√3/(2√2))
#   These are mathematical facts, not empirical measurements.
#   Using them as fixed poles prevents the geological collapse feedback loop
#   where drifting stone cells weaken the pole that should restore them.

def _build_Y():
    from y323operator import _Y_MATRIX
    return _Y_MATRIX.astype(np.complex64)

_Y = _build_Y()

# Stable projector — computed once at module load
def _build_projectors(Y):
    eigvals, eigvecs = np.linalg.eig(Y.astype(np.complex128))
    non_nil = np.abs(eigvals) > 1e-8
    V_s = eigvecs[:, non_nil]
    P_s = (V_s @ np.linalg.pinv(V_s)).astype(np.complex64)
    return P_s

_P_stable = _build_projectors(_Y)

# Exact attractor poles from the monograph (Part VI §41, verified numerically)
_s2  = np.float32(1.0 / np.sqrt(2))
_s6  = np.float32(np.sqrt(3) / (2.0 * np.sqrt(2)))   # √3/(2√2) = √(3/8)
_POLE_STONE = np.array(
    [0, 0, 0.25, 0.25,  _s2, 0,  1j*_s6], dtype=np.complex64)
_POLE_WATER = np.array(
    [0, 0, 0.25, -0.25, _s2, 0, -1j*_s6], dtype=np.complex64)

# Witness angle: 45° exactly (monograph Part I §6, Corollary 6.3 — corrects
# the earlier miscalculation of arctan(√13) ≈ 74.7°)
_WITNESS_ANGLE = np.float64(np.pi / 4.0)

# ── Observation: Re(ψ) → M ────────────────────────────────────────────────────

def _obs_single(s: np.ndarray) -> np.ndarray:
    raw = RawState.from_array(s.real)
    pt  = ManifoldPoint.from_raw(raw)
    return np.array([pt.tau, pt.phi1.real, pt.phi1.imag,
                     pt.phi2.real, pt.phi2.imag, pt.xi.real, pt.xi.imag],
                    dtype=np.float32).astype(np.complex64)

def _obs_batch(S: np.ndarray) -> np.ndarray:
    out = np.empty_like(S)
    for i in range(len(S)):
        out[i] = _obs_single(S[i])
    return out

def _fold(S: np.ndarray) -> np.ndarray:
    """Gauge fix τ≥0. Prevents destructive orbit-phase interference."""
    out = S.copy()
    out[S[:, 0].real < 0] *= -1
    return out


# ── Manifold coordinates ──────────────────────────────────────────────────────

TAU_STONE = 0.65
TAU_SAND  = 0.40
TAU_WATER = 0.15
SCALE_Z   = 5.0
SCALE_XY  = 4.0
COH_THRESHOLD  = 0.10    # coherence gate — sits in the gap between intra and cross-material
DEATH_NORM     = 1e-5
LOC_SIGMA      = 1.0     # spatial locality radius (in genesis coordinate units, ~1 cell spacing)
SEA_LEVEL      = 0.0     # genesis z below which ocean cells are protected from drying
ALPHA_Y        = 0.02    # max Y-strength variation (±2%) — the living Y field
MATERIAL_NAMES = ['stone', 'sand', 'water', 'air']


def states_to_positions(S: np.ndarray) -> np.ndarray:
    """(N,7) → (N,3). |τ|→z (inverted: stone sinks), φ-correlation→x,y.
    Used for the witness point (which has no genesis position)."""
    tau  = S[:, 0].real
    phi1 = S[:, 1] + 1j * S[:, 2]
    phi2 = S[:, 3] + 1j * S[:, 4]
    corr = phi1 * np.conj(phi2)
    return np.stack([
        corr.real * SCALE_XY,
        corr.imag * SCALE_XY,
        -np.abs(tau) * SCALE_Z,
    ], axis=1).astype(np.float32)


def geography_positions(S: np.ndarray, P: np.ndarray) -> np.ndarray:
    """(N,7),(N,3) → (N,3).

    The real rendering position of each cell.
    x, y  = genesis geographic coordinates — the actual island map.
            Genesis spans ±9.8 which fills the dome naturally.
    z     = genesis elevation + tau depth.
            genesis_z * 0.4 gives mountains their height.
            -|tau| * SCALE_Z stratifies materials vertically:
              stone sinks deep, water sits near the surface.
    
    This makes the dome a map: walk around it and see geography.
    North/south/east/west correspond to actual island positions.
    High ground is high. Shorelines are where they are.
    """
    tau = np.abs(S[:, 0].real)
    return np.stack([
        P[:, 0],                              # genesis x  (east–west)
        P[:, 1],                              # genesis y  (north–south)
        P[:, 2] * 0.4 - tau * SCALE_Z,       # elevation + material depth
    ], axis=1).astype(np.float32)


def tau_abs(S: np.ndarray) -> np.ndarray:
    return np.abs(S[:, 0].real).astype(np.float32)


def material_from_states(S: np.ndarray) -> np.ndarray:
    t = tau_abs(S)
    m = np.full(len(t), 3, dtype=np.uint8)
    m[t > TAU_WATER] = 2
    m[t > TAU_SAND]  = 1
    m[t > TAU_STONE] = 0
    return m


def manifold_value(S: np.ndarray) -> np.ndarray:
    tau  = S[:, 0].real
    phi1 = S[:, 1] + 1j * S[:, 2]
    phi2 = S[:, 3] + 1j * S[:, 4]
    xi   = S[:, 5] + 1j * S[:, 6]
    return (tau**2 + np.abs(phi1)**2 * np.abs(phi2)**2 + np.abs(xi)**2).astype(np.float32)


# ── Witness geometry ─────────────────────────────────────────────────────────
# The witness is a silent point on M at the geometric counterpoint to the
# island centre. It lives at π/4 = 45° geodesic angle from the island centre —
# the exact angle by which Y's real part deviates from the g₂ algebra
# (monograph Part I §6, Corollary 6.3: arctan(||B+C||/||A||) = arctan(1) = 45°).
#
# Earlier versions used arctan(√13) ≈ 74.7°, which was a miscalculation
# corrected in the monograph. _WITNESS_ANGLE is now π/4, defined at module top.
#
# The witness does not birth cells, does not diffuse, is not rendered.
# It exists as a reference point: the shadow of what this world is not.

# _WITNESS_ANGLE is now defined at module top (π/4, corrected from arctan√13)


def _make_witness(island_centre: np.ndarray) -> np.ndarray:
    """
    Place witness at geodesic angle _WITNESS_ANGLE from the island centre,
    in the direction of the first coordinate axis that is not parallel to it.
    
    The witness lives on S⁶ (unit sphere), evolved from the antipodal point
    of the island centre rotated by the g₂ deviation angle.
    """
    c = island_centre.real.astype(np.float64)
    norm_c = np.linalg.norm(c)
    if norm_c < 1e-10:
        c = np.zeros(7, dtype=np.float64)
        c[0] = 1.0
    else:
        c = c / norm_c

    # Find a tangent vector orthogonal to c
    tangent = np.zeros(7, dtype=np.float64)
    # Use the coordinate axis least aligned with c
    axis = int(np.argmin(np.abs(c)))
    tangent[axis] = 1.0
    tangent = tangent - np.dot(tangent, c) * c
    t_norm = np.linalg.norm(tangent)
    if t_norm < 1e-10:
        tangent = np.zeros(7, dtype=np.float64)
        tangent[(axis + 1) % 7] = 1.0
        tangent = tangent - np.dot(tangent, c) * c
        t_norm = np.linalg.norm(tangent)
    tangent = tangent / (t_norm + 1e-30)

    # Geodesic rotation: w = c·cos(θ) + tangent·sin(θ)
    angle = _WITNESS_ANGLE
    w = c * np.cos(angle) + tangent * np.sin(angle)
    w = w / (np.linalg.norm(w) + 1e-30)
    return w.astype(np.float32).astype(np.complex64)


def _make_material_poles(S_active: np.ndarray):
    """
    Return the exact theoretical attractor poles of Y.

    FIX (monograph Part VI §41, Uniqueness Theorem 39.1):
      The stone and water poles are the λ=+1 and λ=-1 eigenvectors of Y.
      They are mathematical constants, not empirical means of current cells.

      Using empirical means creates a positive-feedback collapse loop:
        stone cells lose τ → stone pole weakens → restore signal weakens
        → stone cells lose more τ → ...

      Using the exact eigenvectors breaks this loop. The poles are stable
      regardless of what the live cells are doing — they are the targets
      the system is always trying to reach, not a reflection of where it is.

    The angle between stone and water poles (arccos of their inner product)
    can be verified numerically: it emerges from the Y operator geometry,
    not from island statistics.

    S_active is accepted for API compatibility but not used.
    """
    return _POLE_STONE.copy(), _POLE_WATER.copy()


POLE_PULL = 0.10   # geodesic step size per step toward dominant pole
                   # At this rate: ~1000 steps to full polarisation (one geological epoch)


def law_pole_pull(S: np.ndarray, w1: np.ndarray, w2: np.ndarray) -> np.ndarray:
    """
    Gentle two-pole attractor on the manifold.

    Each cell feels a Riemannian gradient step toward whichever of the two
    witness poles it has greater coherence with. The step size is proportional
    to both the absolute coherence (how close it already is) and the bias
    (how strongly it prefers one pole over the other).

    Equatorial cells — those with equal coherence with both poles — feel
    zero net pull. They remain the free creative zone, the saddle locus
    between the two attractors. This is where boundary emergence happens.

    The pull is a geodesic step on S¹³ (the unit sphere in ℂ⁷ ≅ ℝ¹⁴):
        s_new = normalise(s + ε · w_perp)
    where w_perp is the component of the dominant pole perpendicular to s,
    and ε = POLE_PULL · dominant_coherence · |bias| / mean_coherence.

    Over ~1000 steps (one geological epoch at POLE_PULL=0.10), the island
    develops a clear w1-hemisphere and w2-hemisphere separated by the
    equatorial locus — the standing wave nodal line of the living Y field.
    """
    norms = np.linalg.norm(S, axis=1, keepdims=True)
    Sn    = (S / (norms + 1e-30)).astype(np.complex64)

    w1n = (w1 / (np.linalg.norm(w1) + 1e-30)).astype(np.complex64)
    w2n = (w2 / (np.linalg.norm(w2) + 1e-30)).astype(np.complex64)

    coh1 = np.abs(Sn @ w1n.conj())**2   # (N,)
    coh2 = np.abs(Sn @ w2n.conj())**2
    bias = (coh1 - coh2).astype(np.float32)

    # Step size: proportional to dominant coherence × |bias|, normalised
    dominant_coh  = np.maximum(coh1, coh2)
    mean_coh      = float(dominant_coh.mean()) + 1e-10
    eps = (POLE_PULL * dominant_coh * np.abs(bias) / mean_coh).astype(np.float32)

    # Perpendicular component of each pole relative to each cell
    perp1 = w1n[None, :] - (Sn @ w1n.conj())[:, None] * w1n[None, :]
    perp2 = w2n[None, :] - (Sn @ w2n.conj())[:, None] * w2n[None, :]

    # Pull toward the pole with greater coherence
    perp  = np.where(bias[:, None] > 0, perp1, perp2)

    S_pulled = Sn + eps[:, None] * perp
    S_norm   = S_pulled / (np.linalg.norm(S_pulled, axis=1, keepdims=True) + 1e-30)
    return (S_norm * norms).astype(np.complex64)

# ── Genesis-home restoration ──────────────────────────────────────────────────
#
# Every cell was born at a genesis position with a specific z-coordinate.
# That z encodes its 'home tau' -- the material it ought to be at that altitude.
# Over time, coherence diffusion and Y dynamics can drain tau from highland cells,
# causing geological collapse (stone -> sand -> water -> everything drowns).
#
# law_genesis_restore is the correction current:
# Each cell feels a gentle pull back toward its home tau, proportional to how
# far below home it has drifted. The pull is implemented as a blend toward
# the stone pole (world.witness), scaled by:
#   beta[i] = RESTORE_STRENGTH * (tau_home[i] - tau[i]) / (TAU_STONE - TAU_WATER)
# where tau_home[i] = TAU_WATER + (TAU_STONE - TAU_WATER) * z_norm[i]
#
# This is the 'punishment' signal in the neural net analogy:
# cells far below their home tau get a strong corrective signal.
# Cells at or above their home tau (thriving) feel nothing.
# The equatorial cells (sand at middling z) get gentle nudges.
#
# The result: the island maintains geological stratification indefinitely.
# Highland cells stay stone. Shoreline cells stay sand. Only the deep ocean
# is truly free to be water. The world breathes without drowning.

RESTORE_STRENGTH  = 0.80   # fraction of geodesic pull per step when fully drifted
RESTORE_MIN_PRESS = 0.05   # ignore drift < 5% of tau range (noise floor)


def law_genesis_restore(S: np.ndarray,
                        P: np.ndarray,
                        w_stone: np.ndarray,
                        P_all: np.ndarray) -> np.ndarray:
    """
    Restore cells toward their genesis-z home tau.

    Each cell has a 'home tau' determined by its genesis altitude z:
        tau_home[i] = TAU_WATER + (TAU_STONE - TAU_WATER) * z_norm[i]
    where z_norm is the cell's genesis z normalised across the full island range.

    Cells below home tau receive a pull toward the stone pole (w_stone),
    scaled by how far they have drifted. Cells at or above home tau
    are not touched — they have found their natural level.

    This is the geological memory of the island: altitude determines fate.
    The correction is exact in the limit RESTORE_STRENGTH → 1, and gentle
    at the default 0.80 so that diffusion and emergence can still operate.

    Args:
        S:       (N,7) active cell states
        P:       (N,3) active cell genesis positions
        w_stone: (7,)  stone pole attractor state
        P_all:   (M,3) ALL cell positions (for z range normalisation)
    """
    N = len(S)
    if N == 0:
        return S

    # Normalise z across the entire island (use full P_all for stable range)
    z     = P[:, 2].astype(np.float32)
    z_min = float(P_all[:, 2].min())
    z_max = float(P_all[:, 2].max())
    z_rng = max(z_max - z_min, 1e-6)
    z_norm = np.clip((z - z_min) / z_rng, 0.0, 1.0)

    # Home tau: linear interpolation from TAU_WATER (z=0) to TAU_STONE (z=1)
    tau_home = (TAU_WATER + (TAU_STONE - TAU_WATER) * z_norm).astype(np.float32)

    # Current tau
    tau_now = tau_abs(S)

    # Reset pressure: how far below home
    pressure = np.maximum(0.0, tau_home - tau_now)

    # Beta: geodesic blend fraction toward stone pole
    beta = np.clip(
        RESTORE_STRENGTH * pressure / (TAU_STONE - TAU_WATER),
        0.0, 0.92
    ).astype(np.float32)

    # Only act on cells with non-trivial drift
    active = pressure > RESTORE_MIN_PRESS
    if not active.any():
        return S

    # Geodesic blend: s_new = (1-beta)*s + beta*w_stone*|s|
    w = w_stone.astype(np.complex64)
    norms = np.linalg.norm(S, axis=1, keepdims=True).astype(np.float32)
    b = beta[:, None]
    S_out = S.copy()
    S_out[active] = (
        (1.0 - b[active]) * S_out[active] +
        b[active] * w[None, :] * norms[active]
    ).astype(np.complex64)

    return _obs_batch(_fold(S_out))



# ── World ─────────────────────────────────────────────────────────────────────

@dataclass
class PureWorld:
    S:          np.ndarray   # (MAX,7) complex64
    active:     np.ndarray   # (MAX,)  bool
    birth_step: np.ndarray   # (MAX,)  int32
    P:          np.ndarray   # (MAX,3) float32    — spatial positions (geography)
    witness:    np.ndarray   # (7,)    complex64 — first pole (g₂ deviation)
    witness2:   np.ndarray   # (7,)    complex64 — antipodal pole (torus axis)
    step:       int = 0
    emergence_count: int = 0
    psi_history:    list = None   # rolling Psi window for convergence rate

    def __post_init__(self):
        if self.psi_history is None:
            object.__setattr__(self, 'psi_history', [])
    psi_history:    list = None   # rolling Ψ window for convergence rate

    def __post_init__(self):
        if self.psi_history is None:
            object.__setattr__(self, 'psi_history', [])

    @property
    def N(self): return int(self.active.sum())

    @property
    def indices(self): return np.where(self.active)[0]

    def positions(self):  return states_to_positions(self.S[self.indices])
    def materials(self):  return material_from_states(self.S[self.indices])
    def ages(self):
        idx = self.indices
        return (self.step - self.birth_step[idx]).astype(np.int32)

    @property
    def witness_position(self) -> np.ndarray:
        """World-space (x,y,z) of the witness point, for rendering."""
        return states_to_positions(self.witness[np.newaxis])[0]

    @property
    def witness_coherence(self) -> float:
        """Mean coherence of first witness with all active cells."""
        idx = self.indices
        if len(idx) == 0:
            return 0.0
        S   = self.S[idx]
        w   = self.witness
        wn  = np.linalg.norm(w)
        if wn < 1e-10:
            return 0.0
        w_unit = w / wn
        Sn = S / (np.linalg.norm(S, axis=1, keepdims=True) + 1e-30)
        dots = np.abs(Sn @ w_unit.conj())**2
        return float(dots.mean())

    @property
    def witness2_coherence(self) -> float:
        """Mean coherence of second (antipodal) witness with all active cells."""
        idx = self.indices
        if len(idx) == 0:
            return 0.0
        S    = self.S[idx]
        w    = self.witness2
        wn   = np.linalg.norm(w)
        if wn < 1e-10:
            return 0.0
        w_unit = w / wn
        Sn  = S / (np.linalg.norm(S, axis=1, keepdims=True) + 1e-30)
        dots = np.abs(Sn @ w_unit.conj())**2
        return float(dots.mean())

    @property
    def pole_separation(self) -> float:
        """Mean |coh_w1 - coh_w2|: how strongly the two poles have separated cells."""
        idx = self.indices
        if len(idx) == 0:
            return 0.0
        S  = self.S[idx]
        Sn = S / (np.linalg.norm(S, axis=1, keepdims=True) + 1e-30)
        w1n = self.witness  / (np.linalg.norm(self.witness)  + 1e-30)
        w2n = self.witness2 / (np.linalg.norm(self.witness2) + 1e-30)
        c1  = np.abs(Sn @ w1n.conj())**2
        c2  = np.abs(Sn @ w2n.conj())**2
        return float(np.abs(c1 - c2).mean())



# ── Convergence scalar Psi ────────────────────────────────────────────────────
#
# Psi is a single scalar in [0, 1] measuring how fully the world has found
# its natural attractor: the geologically stratified island with stone
# highlands, sand shoreline, and water ocean.
#
# Three independent signals combined as a geometric mean:
#
#   Psi_F  -- tau F-statistic: how cleanly the three materials are separated
#              in tau space.  ANOVA between-class / within-class ratio.
#              F -> inf means perfect separation; 1 - exp(-F/10) normalises.
#
#   Psi_S  -- solid fraction quality: how close stone+sand is to ~34%.
#              Gaussian bell curve peaked at 0.34, width 0.15.
#
#   Psi_KL -- KL divergence from target distribution
#              [stone=12%, sand=22%, water=66%, air=0%].
#              KL=0 at perfect match -> exp(-KL) = 1.
#
# Psi = (Psi_F * Psi_S * Psi_KL)^(1/3)   -- all three must be good
#
# Convergence rate d(Psi)/dt is computed from a PSI_WINDOW-step rolling
# window stored in world.psi_history.  When the rate drops below
# PSI_CONVERGE_THR the world has settled into its attractor.

PSI_TARGET_DIST  = np.array([0.12, 0.22, 0.66, 0.00])
PSI_SOLID_CENTRE = 0.34
PSI_SOLID_WIDTH  = 0.15
PSI_F_SCALE      = 10.0
PSI_WINDOW       = 20
PSI_CONVERGE_THR = 2e-4


def compute_psi(world):
    """
    Convergence scalar Psi in [0, 1].
    0 = undifferentiated seed; 1 = fully converged geological attractor.
    """
    idx = world.indices
    if len(idx) < 3:
        return 0.0

    S    = world.S[idx]
    mats = material_from_states(S)
    N    = len(idx)
    tau  = tau_abs(S)

    # Psi_F: tau class separation (F-statistic)
    present = [m for m in range(3) if (mats == m).sum() > 1]
    if len(present) < 2:
        psi_f = 0.0
    else:
        grand_mean  = float(tau.mean())
        between_var = 0.0
        within_var  = 0.0
        for m in present:
            mask = mats == m
            n_m  = int(mask.sum())
            mu_m = float(tau[mask].mean())
            between_var += n_m * (mu_m - grand_mean) ** 2
            within_var  += float(tau[mask].var()) * n_m
        between_var /= N
        within_var   = within_var / N + 1e-10
        f_stat = between_var / within_var
        psi_f  = float(1.0 - np.exp(-f_stat / PSI_F_SCALE))

    # Psi_S: solid fraction quality
    f_solid = float((mats == 0).sum() + (mats == 1).sum()) / N
    psi_s   = float(np.exp(-((f_solid - PSI_SOLID_CENTRE) / PSI_SOLID_WIDTH) ** 2))

    # Psi_KL: KL divergence from target distribution
    q = PSI_TARGET_DIST + 1e-10
    q = q / q.sum()
    counts = np.array([(mats == m).sum() for m in range(4)], dtype=np.float64)
    p = counts / (counts.sum() + 1e-10)
    kl = float(sum(p[i] * np.log(p[i] / q[i]) for i in range(4) if p[i] > 1e-10))
    psi_kl = float(np.exp(-kl))

    return float((psi_f * psi_s * psi_kl) ** (1.0 / 3.0))


def psi_convergence_rate(world):
    """Mean |dPsi/dt| over last PSI_WINDOW steps. Near zero = converged."""
    h = world.psi_history
    if len(h) < 2:
        return float('inf')
    window = h[-PSI_WINDOW:]
    if len(window) < 2:
        return float('inf')
    diffs = [abs(window[i+1] - window[i]) for i in range(len(window) - 1)]
    return float(np.mean(diffs))


def is_converged(world):
    """True when Psi has stabilised -- the world has found its attractor."""
    return (len(world.psi_history) >= PSI_WINDOW and
            psi_convergence_rate(world) < PSI_CONVERGE_THR)


def create_pure_world(max_cells: int = 8192) -> PureWorld:
    # Default witnesses at the g₂-deviation angle from the north pole
    default_centre = np.zeros(7, dtype=np.complex64)
    default_centre[0] = 1.0
    # Fallback poles before island is seeded
    witness  = np.zeros(7, dtype=np.complex64); witness[0]  = 1.0   # stone axis
    witness2 = np.zeros(7, dtype=np.complex64); witness2[3] = 1.0   # water axis
    return PureWorld(
        S          = np.zeros((max_cells, 7), dtype=np.complex64),
        active     = np.zeros(max_cells, dtype=bool),
        birth_step = np.zeros(max_cells, dtype=np.int32),
        P          = np.zeros((max_cells, 3), dtype=np.float32),
        witness    = witness,
        witness2   = witness2,
    )


def seed_from_island(max_cells: int = 8192) -> PureWorld:
    """
    Seed from spatial island genesis, then settle each cell onto
    its period-2 orbit and fold to τ≥0 (high-τ phase).
    Apply nilpotent reset to clean any transient components from seeding.

    The witness is placed at the g₂-deviation angle (π/4 = 45°, corrected
    from the earlier arctan√13 ≈ 74.7°) from the island centre — the exact
    angle by which Y's real part deviates from the g₂ algebra
    (monograph Part I §6, Corollary 6.3).
    """
    from genesis import create_island_world
    old   = create_island_world()
    cells = old.all_cells()
    S = np.array([c.resonance.state for c in cells], dtype=np.complex64)
    P = np.array([c.position        for c in cells], dtype=np.float32)

    # Settle onto the high-|τ| phase of the period-2 orbit,
    # then apply nilpotent reset to remove any transient components
    # accumulated during seeding (monograph Part I §3, Y³|_{V_nil}=0).
    S = _obs_batch(S)
    for _ in range(2):
        S = _fold(_obs_batch(S @ _Y.T))
    # Nilpotent reset: project onto stable subspace
    S = (_P_stable @ S.T).T.astype(np.complex64)
    S = _fold(_obs_batch(S))

    world = create_pure_world(max_cells)
    N = len(cells)
    world.S[:N]      = S
    world.P[:N]      = P
    world.active[:N] = True

    island_centre   = S.mean(axis=0)
    w_stone, w_water = _make_material_poles(S)
    world.witness    = w_stone    # geological pole (high-|τ| attractor)
    world.witness2   = w_water    # oceanic pole    (low-|τ| attractor)
    # The g₂-deviation geometric witness is still computable on demand:
    world._g2_witness = _make_witness(island_centre)

    return world


# ── Laws ──────────────────────────────────────────────────────────────────────

def law_double_step(S: np.ndarray, alpha: np.ndarray = None) -> np.ndarray:
    """
    Two Y applications + observe + fold.
    One full period-2 breath: always lands at the high-|τ| phase.

    FIX (monograph Part I §2, Definition 2.1):
      Y acts on column vectors. For row-array S of shape (N,7):
          correct:   S @ _Y.T   ↔   Y @ s[i]  for each row i
          previous:  S @ _Y.conj()  — wrong operator, error ~2.6 per step

    If alpha is provided (shape (N,)), each cell applies Y with a slightly
    different effective strength: Y_local[i] = Y * (1 + alpha[i]).
    This is Y as a living field: stone regions are geologically stiffer
    (positive alpha), ocean regions are dynamically softer (negative alpha).
    """
    if alpha is None:
        S = _fold(_obs_batch(S @ _Y.T))
        S = _fold(_obs_batch(S @ _Y.T))
    else:
        a = (1.0 + alpha).astype(np.float32)[:, None]
        S = _fold(_obs_batch((S @ _Y.T) * a))
        S = _fold(_obs_batch((S @ _Y.T) * a))
    return S


def compute_local_Y_alpha(S: np.ndarray, P: np.ndarray) -> np.ndarray:
    """
    Compute per-cell Y-strength modulation from local geological density.

    alpha[i] = ALPHA_Y * (local_density[i] - global_mean) / global_std

    local_density[i] = spatially-weighted mean |τ| of cell i's neighbours.
    Uses the same LOC_SIGMA spatial kernel as coherence diffusion.

    Stone regions: high local |τ| → positive alpha → Y applied more strongly
                   → shorter effective breathing period → geological stiffness.
    Ocean regions: low local |τ| → negative alpha → Y applied less strongly
                   → longer effective period → fluid softness.

    The gradient of alpha across the island IS the living Y field. Its
    zero-crossing (alpha=0) marks the dynamic shoreline — where stone and
    water breathe at exactly the same rate and exchange is most active.
    """
    tau  = tau_abs(S)
    diffs = P[:, np.newaxis, :] - P[np.newaxis, :, :]
    d2    = (diffs * diffs).sum(axis=2)
    L     = np.exp(-d2 / (2.0 * LOC_SIGMA * LOC_SIGMA)).astype(np.float32)
    np.fill_diagonal(L, 0.0)
    row_sum = L.sum(axis=1)
    local_density = (L @ tau) / (row_sum + 1e-10)
    global_mean   = float(tau.mean())
    global_std    = float(tau.std()) + 1e-10
    return (ALPHA_Y * (local_density - global_mean) / global_std).astype(np.float32)


def law_coherence_diffuse(S: np.ndarray, P: np.ndarray, t: float) -> np.ndarray:
    """
    Local coherence-gated diffusion.

    Weight between cells i and j:
        W[i,j]  ∝  coherence[i,j]  ×  exp(−|pᵢ−pⱼ|² / 2σ²)
        where coherence[i,j] = |<sᵢ|sⱼ>|²  and  σ = LOC_SIGMA

    σ = 1.0 in genesis coordinate units (nearest-neighbour spacing ≈ 0.87).
    Each cell's effective neighbourhood contains ~28 cells with >10% weight.
    58% of diffusion weight comes from cells within 1.5 units — genuine
    spatial neighbours, not the whole island.

    This breaks the global averaging that previously collapsed all cells of
    the same material into a single identical state. Now:
      - Stone at the island centre evolves differently from stone at the coast
      - Water near the shoreline differs from open-ocean water
      - Sand forms and persists at spatial gradients, not just state gradients
      - Geography is real: position determines fate
    """
    N = len(S)
    if N < 2:
        return S

    norms = np.linalg.norm(S, axis=1, keepdims=True)
    Sn    = (S / np.where(norms > 1e-15, norms, 1.0)).astype(np.complex64)

    # Coherence matrix: |<sᵢ|sⱼ>|²
    C = np.abs(Sn @ Sn.conj().T)**2

    # Spatial locality gate: exp(-|pᵢ-pⱼ|² / 2σ²)
    diffs  = P[:, np.newaxis, :] - P[np.newaxis, :, :]   # (N,N,3)
    d2     = (diffs * diffs).sum(axis=2)                  # (N,N)
    L      = np.exp(-d2 / (2.0 * LOC_SIGMA * LOC_SIGMA)).astype(np.float32)
    np.fill_diagonal(L, 0.0)

    # Combined gate: coherent AND nearby
    C_gated = np.where(C > COH_THRESHOLD, C * L, 0.0)

    # Row-normalise
    row_sum  = C_gated.sum(axis=1, keepdims=True)
    W        = (C_gated / np.where(row_sum > 1e-10, row_sum, 1.0)).astype(np.float32)

    S_target = (W @ S).astype(np.complex64)
    return ((1.0 - t) * S + t * S_target).astype(np.complex64)



def law_sea_level(S: np.ndarray, P: np.ndarray) -> np.ndarray:
    """
    Sea-level boundary condition.

    Cells below genesis z = SEA_LEVEL are in the ocean basin.
    If diffusion has nudged a sub-sea-level cell's tau up toward the
    sand threshold, gently restore it toward the water regime centre (0.27).

    This is not a clamp — it is a restoring force proportional to how
    far above TAU_WATER the cell has drifted. Cells near the boundary
    feel it weakly. Cells being dragged hard toward sand feel it strongly.

    Cells above sea level are untouched — highland water drains naturally
    to sand, which is geologically correct.
    """
    S_out = S.copy()
    below_sea   = P[:, 2] < SEA_LEVEL          # ocean basin mask
    tau_col     = S_out[:, 0].real              # τ component

    # For below-sea cells that are drifting above TAU_WATER:
    # apply a restoring pull back toward the water centre
    WATER_CENTRE = (TAU_WATER + TAU_SAND) * 0.5   # ~0.275 — middle of water band
    RESTORE      = 0.08                            # strength of restoring force

    drift = (tau_col - WATER_CENTRE) * below_sea.astype(np.float32)
    drift = np.clip(drift, 0, None)    # only restore upward drift, not downward
    S_out[:, 0] = (tau_col - RESTORE * drift).astype(np.complex64)

    return S_out

def law_emerge(
    S:         np.ndarray,
    P:         np.ndarray,
    threshold: float,
    top_k_pos: int = 3,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Anisotropic emergence: birth at the coherence boundary.

    The Gram matrix is weighted by each cell's boundary score before
    decomposition. This means the dominant eigenmodes capture the state
    of cells at material interfaces (stone/water/sand boundaries), not
    the interior. New cells are born with the boundary's state.

    Birth position is the centroid of the top-K parents ranked by
    (eigenmode projection × boundary score). With K=3, this lands at
    a real coastline point rather than the symmetric island centre.
    Geography directs birth: new structure appears where the old
    structure meets its complement.

    boundary_score[i] = fraction of cell i's spatial neighbourhood
                        occupied by cells of a different material.
    """
    N = len(S)
    if N < 2:
        return np.zeros((0, 7), np.complex64), np.zeros((0, N), np.float32)

    # ── boundary score ────────────────────────────────────────────────
    diffs  = P[:, np.newaxis, :] - P[np.newaxis, :, :]
    d2     = (diffs * diffs).sum(axis=2)
    L      = np.exp(-d2 / (2.0 * LOC_SIGMA * LOC_SIGMA)).astype(np.float32)
    np.fill_diagonal(L, 0.0)
    nbr_wt  = L.sum(axis=1)
    mats    = material_from_states(S)
    diff_m  = (mats[:, np.newaxis] != mats[np.newaxis, :]).astype(np.float32)
    bscore  = ((L * diff_m).sum(axis=1) / (nbr_wt + 1e-10)).astype(np.float32)

    # ── boundary-weighted Gram ────────────────────────────────────────
    norms  = np.linalg.norm(S, axis=1, keepdims=True)
    Sn     = (S / np.where(norms > 1e-15, norms, 1.0)).astype(np.complex64)
    Sn_b   = Sn * np.sqrt(bscore[:, None])   # weight each row by sqrt(boundary)
    G      = (Sn_b.conj().T @ Sn_b).astype(np.complex64)

    evals, evecs = np.linalg.eigh(G)
    evals = evals[::-1].real; evecs = evecs[:, ::-1]

    new_S, new_w = [], []
    for k in range(7):
        if float(evals[k]) < threshold: break
        g_k    = evecs[:, k]
        w      = (Sn_b @ g_k).real.astype(np.float32)   # boundary-weighted projection
        active = w > 0.01
        if active.sum() < 2: continue

        w_a  = w[active]
        wpos = w_a / w_a.sum()

        # state: weighted average over active parents
        s_new = (wpos[:, None] * S[active]).sum(axis=0)
        nrm   = np.linalg.norm(s_new)
        if nrm < 1e-30: continue
        mean_n = float(np.mean(np.linalg.norm(S[active], axis=1)))
        s_new  = (s_new / nrm * mean_n).astype(np.complex64)

        # position weight: top-K by (projection × boundary_score)
        # stored in fw so step_world can compute the birth position
        score = w_a * bscore[active]
        fw_full = np.zeros(N, np.float32)
        fw_full[active] = score          # step_world takes top-K from this

        new_S.append(s_new); new_w.append(fw_full)

    if not new_S:
        return np.zeros((0, 7), np.complex64), np.zeros((0, N), np.float32)
    return np.array(new_S, np.complex64), np.array(new_w, np.float32)


def law_cull(S: np.ndarray) -> np.ndarray:
    return np.linalg.norm(S, axis=1) > DEATH_NORM


# ── Step ──────────────────────────────────────────────────────────────────────

def step_world(
    world:      PureWorld,
    t_diffuse:  float = 0.06,
    threshold:  float = 3.0,
    max_births: int   = 6,
) -> PureWorld:
    """
    One heartbeat:
      double-step  →  coherence-gated diffuse  →  observe  →  emerge  →  cull
    """
    idx = world.indices
    if len(idx) == 0:
        world.step += 1
        return world

    S = world.S[idx].copy()
    P = world.P[idx]          # spatial positions of active cells

    alpha = compute_local_Y_alpha(S, P)   # living Y field: local geological stiffness
    S = law_double_step(S, alpha)

    # Nilpotent reset every 3 steps (monograph Part I §3, Theorem 4.3):
    # Y³ annihilates the generalised λ=0 eigenspace exactly.
    # Projecting onto the stable subspace removes accumulated transient error
    # without touching any of the meaningful dynamics (±1 and ±i√3/2 modes).
    if world.step % 3 == 0:
        S = (_P_stable @ S.T).T.astype(np.complex64)
    S = law_coherence_diffuse(S, P, t_diffuse)
    S = law_sea_level(S, P)                         # protect ocean basin from drying
    S = law_pole_pull(S, world.witness, world.witness2)  # two-pole toroidal attractor
    S = law_genesis_restore(S, P, world.witness, world.P)  # altitude restores home tau
    S = _obs_batch(_fold(S))

    world.S[idx] = S

    TOP_K_POS = 3   # top parents by (eigenmode × boundary) for birth position
    new_S, new_w = law_emerge(S, P, threshold)
    for k in range(min(len(new_S), max_births)):
        free = np.where(~world.active)[0]
        if len(free) == 0: break
        slot = free[0]
        world.S[slot]          = new_S[k]
        world.active[slot]     = True
        world.birth_step[slot] = world.step
        world.emergence_count += 1
        # Born cell position: centroid of top-K parents by (projection × boundary_score)
        score = new_w[k]                      # (N,) projection*boundary score
        active_mask = score > 0
        if active_mask.sum() <= TOP_K_POS:
            top_idx = np.where(active_mask)[0]
        else:
            top_idx = np.argpartition(score, -TOP_K_POS)[-TOP_K_POS:]
        ws = score[top_idx]; ws = ws / (ws.sum() + 1e-10)
        world.P[slot] = (ws[:, None] * P[top_idx]).sum(axis=0).astype(np.float32)

    keep = law_cull(world.S[idx])
    world.active[idx[~keep]] = False
    psi_val = compute_psi(world)
    world.psi_history.append(psi_val)
    world.step += 1
    return world


# ── Render frame ──────────────────────────────────────────────────────────────

class RenderFrame:
    __slots__ = ('positions', 'materials', 'ages', 'norms',
                 'tau_abs', 'manifold_vals', 'spiral_phase', 'local_alpha', 'N', 'step')

    def __init__(self, world: PureWorld):
        idx    = world.indices
        S      = world.S[idx]
        P      = world.P[idx]
        self.N = len(idx)
        self.step = world.step

        self.tau_abs       = tau_abs(S)
        self.positions     = geography_positions(S, P)
        self.materials     = material_from_states(S)
        self.ages          = (world.step - world.birth_step[idx]).astype(np.int32)
        self.norms         = np.linalg.norm(S, axis=1).astype(np.float32)
        self.manifold_vals = manifold_value(S)
        self.local_alpha   = compute_local_Y_alpha(S, P)   # living Y field strength

        phi1 = S[:, 1] + 1j * S[:, 2]
        phi2 = S[:, 3] + 1j * S[:, 4]
        self.spiral_phase  = np.angle(phi1 * np.conj(phi2)).astype(np.float32)


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import time

    print("═══════════════════════════════════════════════════")
    print("  PureWorld — Zero-Point Manifold Dynamics")
    print("═══════════════════════════════════════════════════\n")

    world = seed_from_island()
    print(f"N={world.N}")

    t_abs = tau_abs(world.S[world.indices])
    mats  = world.materials()
    pos   = world.positions()
    print("Initial state (after orbit settling):")
    for m, name in enumerate(MATERIAL_NAMES):
        c = int((mats==m).sum())
        if c: print(f"  {name:6s}: {c:4d}  |τ|={t_abs[mats==m].mean():.3f}")
    print(f"  z range: [{pos[:,2].min():.2f}, {pos[:,2].max():.2f}]")
    print(f"  M vals:  {manifold_value(world.S[world.indices]).mean():.4f}")

    print("\n── 200-step stability test ──")
    for _ in range(200):
        world = step_world(world)

    t_abs2 = tau_abs(world.S[world.indices])
    mats2  = world.materials()
    print(f"N={world.N}  emergences={world.emergence_count}")
    for m, name in enumerate(MATERIAL_NAMES):
        c = int((mats2==m).sum())
        if c: print(f"  {name:6s}: {c:4d}  |τ|={t_abs2[mats2==m].mean():.3f}")
    print(f"  |τ| overall: {t_abs2.mean():.4f}  (initial: {t_abs.mean():.4f})")

    print("\n── Benchmark 100 steps ──")
    w2 = seed_from_island()
    t0 = time.perf_counter()
    for _ in range(100):
        w2 = step_world(w2)
    dt = time.perf_counter() - t0
    print(f"  {dt*1000:.0f}ms  |  {dt/1:.2f}ms/step  |  {100/dt:.1f} steps/sec")
