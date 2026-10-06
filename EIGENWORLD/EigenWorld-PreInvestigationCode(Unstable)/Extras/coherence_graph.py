"""
coherence_graph.py — Coherence matrices, diffusion operators, and emergence modes.

Every loop in dynamics maps onto a matrix operation over the state array.
This module provides all of them.

THREE COHERENCE MATRICES (computed once per step, each one GPU call):

  C[i,j]   = |<psi_i | psi_j>|^2 / (||psi_i||^2 ||psi_j||^2)
              Symmetric. Self-coherence = 1. Interaction graph.

  C_Y[i,j] = |<psi_i | Y psi_j>|^2 / (||psi_i||^2 ||Y psi_j||^2)
              Asymmetric. Causal: j's future overlaps i's present.

  C_P[i,j] = |<psi_i | P_stable psi_j>|^2 / ...
              Symmetric. Nilpotent transients removed. Persistent structure.

TWO DIFFUSION OPERATORS (derived from the matrices, no new computation):

  D_sym[i,j]  = delta_ij - t * L_C[i,j]   where L_C = normalised Laplacian of C
                Applied as:  new_states = D_sym @ states
                Replaces the symmetric influence edge loop exactly.

  D_causal[i,j] = delta_ij - t * A_Y_thresh[i,j]
                Applied as:  new_states = D_causal @ states
                Replaces the causal edge loop exactly.
                A_Y_thresh is C_Y with diagonal zeroed and entries below
                causal_threshold set to zero.

EMERGENCE MODES (eigendecomposition of C, replaces birth loop):

  The coherence matrix C has eigenvectors v_k with eigenvalues lambda_k.
  Each v_k with lambda_k > emergence_threshold is a natural emergence mode:
  a collective pattern the population is already expressing.
  New cells are born directly from these eigenvectors — one per mode.
  This replaces O(E) individual birth checks with O(N^2) + O(k) where
  k is the number of above-threshold modes (typically 2-10).

COMPOSITION:
  Because C, L_C, C_Y, and Y all act on the same space C^7, we can
  compose: D_sym @ Y @ states in one expression, fusing evolution and
  diffusion into a single operation. The stable subspace of Y is exactly
  the subspace where coherence is preserved — so the composition respects
  the manifold structure automatically.
"""

import numpy as np
from typing import Tuple, List, NamedTuple, Optional
from dataclasses import dataclass

try:
    import jax
    import jax.numpy as jnp
    from jax import jit, vmap
    JAX_AVAILABLE = True
except ImportError:
    JAX_AVAILABLE = False

import jax_kernels as K


# ── Data structures ──────────────────────────────────────────────────────────

class EdgeList(NamedTuple):
    i:       np.ndarray   # (E,) int32
    j:       np.ndarray   # (E,) int32
    weights: np.ndarray   # (E,) float32


@dataclass
class EmergenceMode:
    """
    A collective emergence pattern extracted from the coherence spectrum.
    Replaces individual pairwise birth decisions.
    """
    eigenvalue:  float        # coherence eigenvalue (strength of this mode)
    eigenvector: np.ndarray   # (N,) float — participation of each cell
    state:       np.ndarray   # (7,) complex — the mode's state in C^7
                              # = weighted average of cell states by eigenvector


@dataclass
class CoherenceGraph:
    """Complete interaction structure for one simulation step."""
    N:                int
    C:                np.ndarray      # (N,N) symmetric coherence
    C_Y:              np.ndarray      # (N,N) asymmetric future-coherence
    C_P:              np.ndarray      # (N,N) stable-subspace coherence
    D_sym:            np.ndarray      # (N,N) symmetric diffusion operator
    D_causal:         np.ndarray      # (N,N) causal diffusion operator
    emergence_modes:  List[EmergenceMode]
    hyperedges:       List[List[int]]
    # Kept for renderer / diagnostics only — not used in dynamics loop
    emergence_edges:  EdgeList
    influence_edges:  EdgeList


# ── JAX kernels ──────────────────────────────────────────────────────────────

if JAX_AVAILABLE:

    @jit
    def _coherence_matrix_jax(states: jnp.ndarray) -> jnp.ndarray:
        def row(psi_i):
            def pair(psi_j):
                d  = jnp.vdot(psi_i, psi_j)
                ni = jnp.vdot(psi_i, psi_i).real
                nj = jnp.vdot(psi_j, psi_j).real
                return jnp.abs(d)**2 / (ni * nj + 1e-30)
            return vmap(pair)(states)
        return vmap(row)(states)

    @jit
    def _future_coherence_matrix_jax(states, Y):
        Ys = vmap(lambda p: Y @ p)(states)
        def row(psi_i):
            def pair(Ypsi_j):
                d  = jnp.vdot(psi_i, Ypsi_j)
                ni = jnp.vdot(psi_i,  psi_i ).real
                nj = jnp.vdot(Ypsi_j, Ypsi_j).real
                return jnp.abs(d)**2 / (ni * nj + 1e-30)
            return vmap(pair)(Ys)
        return vmap(row)(states)

    @jit
    def _stable_coherence_matrix_jax(states, P):
        Ps = vmap(lambda p: P @ p)(states)
        def row(psi_i):
            def pair(Ppsi_j):
                d  = jnp.vdot(psi_i, Ppsi_j)
                ni = jnp.vdot(psi_i,  psi_i ).real
                nj = jnp.vdot(Ppsi_j, Ppsi_j).real
                return jnp.abs(d)**2 / (ni * nj + 1e-30)
            return vmap(row)(states)
        return vmap(row)(states)

    @jit
    def _apply_diffusion_jax(D: jnp.ndarray, states: jnp.ndarray) -> jnp.ndarray:
        """states: (N,7) complex64.  D: (N,N) float32.  Returns (N,7)."""
        # D is real, states complex — split and recombine
        Dr = D.astype(jnp.complex64)
        return Dr @ states


# ── Numpy fallbacks ───────────────────────────────────────────────────────────

def _coherence_matrix_np(states):
    norms = np.sum(np.abs(states)**2, axis=1)
    dots  = np.abs(states @ states.conj().T)**2
    return (dots / (np.outer(norms, norms) + 1e-30)).astype(np.float32)

def _future_coherence_matrix_np(states, Y):
    Ys    = states @ Y.T
    ni    = np.sum(np.abs(states)**2, axis=1)
    nj    = np.sum(np.abs(Ys   )**2, axis=1)
    dots  = np.abs(states @ Ys.conj().T)**2
    return (dots / (np.outer(ni, nj) + 1e-30)).astype(np.float32)

def _stable_coherence_matrix_np(states, P):
    Ps    = states @ P.T
    ni    = np.sum(np.abs(states)**2, axis=1)
    nj    = np.sum(np.abs(Ps   )**2, axis=1)
    dots  = np.abs(states @ Ps.conj().T)**2
    return (dots / (np.outer(ni, nj) + 1e-30)).astype(np.float32)


# ── Cached operator references ────────────────────────────────────────────────

_Y_NP = K._Y_NP
_P_NP = K._P_STABLE_NP

if JAX_AVAILABLE:
    _Y_JAX = jnp.array(_Y_NP, dtype=jnp.complex64)
    _P_JAX = jnp.array(_P_NP, dtype=jnp.complex64)


# ── Matrix builders ───────────────────────────────────────────────────────────

def coherence_matrix(states: np.ndarray) -> np.ndarray:
    if JAX_AVAILABLE:
        return np.array(_coherence_matrix_jax(
            jnp.array(states, dtype=jnp.complex64)))
    return _coherence_matrix_np(states)

def future_coherence_matrix(states: np.ndarray) -> np.ndarray:
    if JAX_AVAILABLE:
        return np.array(_future_coherence_matrix_jax(
            jnp.array(states, dtype=jnp.complex64), _Y_JAX))
    return _future_coherence_matrix_np(states, _Y_NP)

def stable_coherence_matrix(states: np.ndarray) -> np.ndarray:
    if JAX_AVAILABLE:
        return np.array(_stable_coherence_matrix_jax(
            jnp.array(states, dtype=jnp.complex64), _P_JAX))
    return _stable_coherence_matrix_np(states, _P_NP)


# ── Diffusion operators ───────────────────────────────────────────────────────

def laplacian_diffusion_matrix(C: np.ndarray, t: float) -> np.ndarray:
    """
    Build symmetric diffusion operator D_sym = I - t * L_C.

    L_C is the normalised graph Laplacian of C.
    Applying D_sym to the state matrix performs one step of
    coherence-weighted diffusion across all cells simultaneously:

        new_states = D_sym @ states

    This is exactly what the influence edge loop computes,
    expressed as a single matrix multiplication.

    t: influence_strength * dt (should be small, e.g. 0.05-0.15)
    """
    C = C.astype(np.float64).copy()
    np.fill_diagonal(C, 0.0)
    degrees = C.sum(axis=1)
    with np.errstate(divide='ignore', invalid='ignore'):
        d_inv_sqrt = np.where(degrees > 1e-12, 1.0 / np.sqrt(degrees), 0.0)
    D_inv_sqrt = np.diag(d_inv_sqrt)
    L = np.eye(len(C)) - D_inv_sqrt @ C @ D_inv_sqrt   # normalised Laplacian
    D = np.eye(len(C)) - t * L
    return D.astype(np.float32)


def causal_diffusion_matrix(C_Y: np.ndarray, t: float,
                             causal_threshold: float) -> np.ndarray:
    """
    Build causal diffusion operator D_causal = I - t * A_Y.

    A_Y is the thresholded, diagonal-zeroed C_Y matrix.
    Entries below causal_threshold are set to zero (sparse).
    Applying D_causal performs directed influence in one matmul:

        new_states = D_causal @ states

    The asymmetry of C_Y means cell j can influence cell i
    without i influencing j — causal propagation follows the
    direction of Y evolution.

    t: causal_influence_strength (smaller than symmetric t, e.g. 0.02-0.06)
    """
    A = C_Y.astype(np.float64).copy()
    np.fill_diagonal(A, 0.0)
    A[A < causal_threshold] = 0.0
    D = np.eye(len(A)) - t * A
    return D.astype(np.float32)


def apply_diffusion(D: np.ndarray, states: np.ndarray) -> np.ndarray:
    """
    Apply diffusion operator D to state matrix.

    D:      (N, N) float32
    states: (N, 7) complex64
    returns: (N, 7) complex64

    D is real-valued (coherence weights are real).
    For complex states: D @ states.real + i * D @ states.imag
    This is handled automatically by numpy/JAX complex arithmetic.
    """
    if JAX_AVAILABLE:
        out = _apply_diffusion_jax(
            jnp.array(D,      dtype=jnp.complex64),
            jnp.array(states, dtype=jnp.complex64)
        )
        return np.array(out, dtype=np.complex64)
    # numpy: matmul handles complex correctly
    return (D.astype(np.complex64) @ states).astype(np.complex64)


# ── Emergence modes ───────────────────────────────────────────────────────────

def extract_emergence_modes(
    C:                   np.ndarray,
    states:              np.ndarray,
    emergence_threshold: float,
) -> List[EmergenceMode]:
    """
    Replace the O(E) pairwise birth loop with an eigendecomposition.

    The coherence matrix C has eigenvectors v_k with eigenvalues lambda_k.
    Interpretation: lambda_k is the "coherence strength" of mode k.
    v_k[i] is cell i's participation in that mode.

    A mode with lambda_k > emergence_threshold represents a collective
    pattern strong enough to birth a new cell. The new cell's state is
    the participation-weighted average of contributing cells' states:

        new_state = sum_i (v_k[i] * states[i]) / ||...||

    This replaces N*(N-1)/2 individual coherence checks with:
      - One eigendecomposition of C (already computed)
      - One weighted sum per above-threshold mode

    Because C is symmetric real (coherence values are real),
    np.linalg.eigh gives exact real eigenvalues in O(N^3) — same
    complexity as building C itself.

    Returns list of EmergenceModes, one per above-threshold eigenvalue.
    Typically 2-15 modes even for N=1000+.
    """
    # C is symmetric float32 — use eigh (exact, sorted ascending)
    # Zero the diagonal first (self-coherence = 1 is not informative here)
    C_offdiag = C.astype(np.float64).copy()
    np.fill_diagonal(C_offdiag, 0.0)

    eigenvals, eigenvecs = np.linalg.eigh(C_offdiag)   # (N,), (N, N)

    # eigh returns ascending order — reverse to get strongest modes first
    eigenvals = eigenvals[::-1]
    eigenvecs = eigenvecs[:, ::-1]

    modes = []
    for k in range(len(eigenvals)):
        lam = float(eigenvals[k])
        if lam < emergence_threshold:
            break   # sorted descending, so all remaining are below threshold

        v = eigenvecs[:, k].astype(np.float64)   # (N,) participation weights

        # Only cells with positive participation contribute
        pos_mask = v > 0
        if pos_mask.sum() < 2:
            continue

        # Weighted average state in C^7
        weights    = v[pos_mask, None]                     # (k, 1)
        substates  = states[pos_mask].astype(np.complex128)  # (k, 7)
        mean_state = (weights * substates).sum(axis=0)
        norm       = np.linalg.norm(mean_state)
        if norm < 1e-30:
            continue

        # Normalise to mean input norm (preserve scale)
        mean_input_norm = np.mean(np.linalg.norm(substates, axis=1))
        mean_state      = mean_state / norm * mean_input_norm

        modes.append(EmergenceMode(
            eigenvalue  = lam,
            eigenvector = v.astype(np.float32),
            state       = mean_state.astype(np.complex64),
        ))

    return modes


# ── Hyperedge extraction (union-find) ────────────────────────────────────────

def _extract_hyperedges(C_P: np.ndarray, threshold: float) -> List[List[int]]:
    N      = C_P.shape[0]
    parent = list(range(N))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    rows, cols = np.where(
        (C_P > threshold) & (np.triu(np.ones((N,N), dtype=bool), k=1))
    )
    for r, c in zip(rows, cols):
        union(int(r), int(c))

    from collections import defaultdict
    groups: dict = defaultdict(list)
    for i in range(N):
        groups[find(i)].append(i)

    return [m for m in groups.values() if len(m) >= 3]


def threshold_to_edges(C: np.ndarray, thresh: float,
                        upper_only: bool = True) -> EdgeList:
    if upper_only:
        mask = (C > thresh) & np.triu(np.ones(C.shape, dtype=bool), k=1)
    else:
        mask = C > thresh
        np.fill_diagonal(mask, False)
    rows, cols = np.where(mask)
    return EdgeList(rows.astype(np.int32), cols.astype(np.int32),
                    C[rows, cols].astype(np.float32))


# ── Main graph builder ────────────────────────────────────────────────────────

def build_coherence_graph(
    states:                np.ndarray,
    emergence_threshold:   float = 0.92,
    interaction_threshold: float = 0.50,
    causal_threshold:      float = 0.40,
    stable_threshold:      float = 0.60,
    influence_t:           float = 0.08,
    causal_t:              float = 0.03,
) -> CoherenceGraph:
    """
    Build the complete interaction structure for N cells.

    Three matrix computations (GPU calls), then pure numpy algebra
    to derive diffusion operators and emergence modes.
    No Python loops over cells or edges.

    states: (N, 7) complex64
    """
    N = len(states)
    if N == 0:
        empty_el = EdgeList(np.array([], np.int32),
                            np.array([], np.int32),
                            np.array([], np.float32))
        I = np.eye(0, dtype=np.float32)
        return CoherenceGraph(0, I, I, I, I, I, [], [], empty_el, empty_el)

    # ── Three coherence matrices (one GPU call each) ──────────────────────
    C   = coherence_matrix(states)
    C_Y = future_coherence_matrix(states)
    C_P = stable_coherence_matrix(states)

    # ── Diffusion operators (pure numpy, O(N^2)) ──────────────────────────
    D_sym    = laplacian_diffusion_matrix(C,   influence_t)
    D_causal = causal_diffusion_matrix(C_Y, causal_t, causal_threshold)

    # ── Emergence modes (eigendecomposition of C) ─────────────────────────
    emergence_modes = extract_emergence_modes(C, states, emergence_threshold)

    # ── Hyperedges (union-find on C_P) ────────────────────────────────────
    hyperedges = _extract_hyperedges(C_P, stable_threshold)

    # ── Edge lists (for renderer / diagnostics only) ──────────────────────
    emergence_edges = threshold_to_edges(C,   emergence_threshold,  True)
    all_edges       = threshold_to_edges(C,   interaction_threshold, True)
    below           = all_edges.weights < emergence_threshold
    influence_edges = EdgeList(all_edges.i[below], all_edges.j[below],
                               all_edges.weights[below])

    return CoherenceGraph(
        N                = N,
        C                = C,
        C_Y              = C_Y,
        C_P              = C_P,
        D_sym            = D_sym,
        D_causal         = D_causal,
        emergence_modes  = emergence_modes,
        hyperedges       = hyperedges,
        emergence_edges  = emergence_edges,
        influence_edges  = influence_edges,
    )


# ── Warmup ────────────────────────────────────────────────────────────────────

def warmup():
    if not JAX_AVAILABLE:
        return
    dummy = np.zeros((8, 7), dtype=np.complex64)
    dummy[0, 0] = 1.0
    coherence_matrix(dummy)
    future_coherence_matrix(dummy)
    stable_coherence_matrix(dummy)
    print(f"coherence_graph kernels warmed up")


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import time
    warmup()

    rng = np.random.default_rng(0)
    N   = 300
    states = (rng.standard_normal((N,7)) +
              1j*rng.standard_normal((N,7))).astype(np.complex64)
    # Plant coherent pairs
    for i in range(0, 30, 3):
        states[i+1] = states[i] + rng.standard_normal(7).astype(np.float32)*0.05
        states[i+2] = states[i] + rng.standard_normal(7).astype(np.float32)*0.08

    t0 = time.perf_counter()
    for _ in range(10):
        G = build_coherence_graph(states)
    t1 = time.perf_counter()
    print(f"N={N}: build x10 = {(t1-t0)*100:.1f}ms avg")
    print(f"  emergence modes : {len(G.emergence_modes)}")
    print(f"  hyperedges      : {len(G.hyperedges)}")
    print(f"  D_sym  shape    : {G.D_sym.shape}")
    print(f"  D_causal shape  : {G.D_causal.shape}")
    if G.emergence_modes:
        evs = [m.eigenvalue for m in G.emergence_modes]
        print(f"  mode eigenvalues: {[f'{e:.3f}' for e in evs[:5]]}")

    # Verify diffusion conserves mean state (approximately)
    new_states = apply_diffusion(G.D_sym, states)
    print(f"  ||states|| mean before: {np.mean(np.linalg.norm(states, axis=1)):.4f}")
    print(f"  ||states|| mean after : {np.mean(np.linalg.norm(new_states, axis=1)):.4f}")
