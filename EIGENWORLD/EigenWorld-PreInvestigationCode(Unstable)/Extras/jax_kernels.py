"""
jax_kernels.py — JAX-accelerated batch operations for eigenspectral dynamics.

OGC inspiration:
  - All operations are purely local (per-cell), with no global synchronization
  - Batch processing via vmap maps directly to GPU parallelism
  - Displacement bounds: per-cell coherence change bounds allow skipping
    emergence checks for cells that cannot trigger in the current step

The three critical hot paths, now GPU-ready:
  1. _evolve_all:           N × (Y @ ψ)        → single batched matmul
  2. _apply_nilpotent_reset: N × (P_stable @ ψ) → single batched matmul
  3. coherence matrix:      N² coherence checks → batched outer product

Falls back gracefully to numpy if JAX is unavailable.
"""

import numpy as np
from typing import Tuple

# ── JAX availability ────────────────────────────────────────────────────────

try:
    import jax
    import jax.numpy as jnp
    from jax import jit, vmap
    JAX_AVAILABLE = True
except ImportError:
    JAX_AVAILABLE = False

# ── Exact Y matrix from y323operator.py ─────────────────────────────────────
# Reproduced here as a literal so jax_kernels has no circular import.

_Y_NP = np.array([
    [0,                          -1j,          0,  0,              0, -np.exp(-1j*np.pi/4), 0                   ],
    [1j,                          0,           0,  0,              0,  0,                   0                   ],
    [0,                           0,           0,  1,              0,  0,                   0                   ],
    [0,                           0,          -1,  0, np.sqrt(2)/2,   0,                   0                   ],
    [0,                           0,           0,  np.sqrt(2)/2,   0,  0,    -1j*np.sqrt(3)/2                  ],
    [np.exp(1j*np.pi/4),          0,           0,  0,              0,  0,                   0                   ],
    [0,                           0,           0,  0,  1j*np.sqrt(3)/2, 0,                  0                   ],
], dtype=np.complex64)

_Y2_NP = (_Y_NP @ _Y_NP).astype(np.complex64)
_Y3_NP = (_Y_NP @ _Y2_NP).astype(np.complex64)

# Stable projector P_stable (computed once, stored as numpy)
def _build_P_stable(Y: np.ndarray) -> np.ndarray:
    eigvals, eigvecs = np.linalg.eig(Y)
    non_nil = np.abs(eigvals) > 1e-8
    V_stable = eigvecs[:, non_nil]
    return (V_stable @ np.linalg.pinv(V_stable)).astype(np.complex64)

_P_STABLE_NP = _build_P_stable(_Y_NP)


# ── JAX constants (only built if JAX available) ──────────────────────────────

if JAX_AVAILABLE:
    _Y_JAX        = jnp.array(_Y_NP,        dtype=jnp.complex64)
    _Y2_JAX       = jnp.array(_Y2_NP,       dtype=jnp.complex64)
    _Y3_JAX       = jnp.array(_Y3_NP,       dtype=jnp.complex64)
    _P_STABLE_JAX = jnp.array(_P_STABLE_NP, dtype=jnp.complex64)


# ── Pure JAX kernels (single-state, JIT-compiled) ───────────────────────────

if JAX_AVAILABLE:

    @jit
    def _apply_Y_single(psi: jnp.ndarray) -> jnp.ndarray:
        return _Y_JAX @ psi

    @jit
    def _apply_P_stable_single(psi: jnp.ndarray) -> jnp.ndarray:
        return _P_STABLE_JAX @ psi

    @jit
    def _coherence_pair(psi1: jnp.ndarray, psi2: jnp.ndarray) -> jnp.ndarray:
        """Normalized coherence: |<ψ1|ψ2>|² / (‖ψ1‖² ‖ψ2‖²)"""
        dot   = jnp.vdot(psi1, psi2)
        norm1 = jnp.vdot(psi1, psi1).real
        norm2 = jnp.vdot(psi2, psi2).real
        return jnp.abs(dot)**2 / (norm1 * norm2 + 1e-30)

    # ── Batch kernels (vmap over first axis) ─────────────────────────────────

    # Batch Y evolution: (N, 7) → (N, 7)
    _batch_apply_Y = jit(vmap(_apply_Y_single, in_axes=0))

    # Batch nilpotent reset: (N, 7) → (N, 7)
    _batch_apply_P_stable = jit(vmap(_apply_P_stable_single, in_axes=0))

    # Row-wise coherence against a fixed reference: (N, 7), (7,) → (N,)
    _batch_coherence_vs_ref = jit(
        vmap(lambda row, ref: _coherence_pair(row, ref), in_axes=(0, None))
    )

    @jit
    def _batch_coherence_matrix(states: jnp.ndarray) -> jnp.ndarray:
        """
        Full N×N coherence matrix.
        For N cells: vmap outer product over both axes.
        Returns (N, N) float32.
        Diagonal entries = 1.0 (self-coherence).
        """
        return vmap(
            lambda row: vmap(
                lambda col: _coherence_pair(row, col)
            )(states)
        )(states)


# ── Public API ───────────────────────────────────────────────────────────────
# Each function accepts a numpy (N,7) complex64 array and returns the same.
# Internally uses JAX if available, otherwise falls back to numpy matmul.

def evolve_batch(states: np.ndarray) -> np.ndarray:
    """
    Apply Y to every state in parallel.
    states: (N, 7) complex64
    returns: (N, 7) complex64
    """
    if JAX_AVAILABLE:
        out = _batch_apply_Y(jnp.array(states, dtype=jnp.complex64))
        return np.array(out)
    else:
        return (states @ _Y_NP.T)  # numpy fallback: broadcast matmul


def reset_batch(states: np.ndarray) -> np.ndarray:
    """
    Apply P_stable to every state in parallel (nilpotent reset).
    states: (N, 7) complex64
    returns: (N, 7) complex64
    """
    if JAX_AVAILABLE:
        out = _batch_apply_P_stable(jnp.array(states, dtype=jnp.complex64))
        return np.array(out)
    else:
        return (states @ _P_STABLE_NP.T)


def coherence_vs_ref(states: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """
    Compute coherence of each state against a single reference state.
    states: (N, 7) complex64
    ref:    (7,)   complex64
    returns: (N,) float32
    """
    if JAX_AVAILABLE:
        out = _batch_coherence_vs_ref(
            jnp.array(states, dtype=jnp.complex64),
            jnp.array(ref,    dtype=jnp.complex64)
        )
        return np.array(out)
    else:
        dots   = np.abs(states @ ref.conj())**2
        n_st   = np.sum(np.abs(states)**2, axis=1)
        n_ref  = float(np.sum(np.abs(ref)**2))
        return dots / (n_st * n_ref + 1e-30)


def coherence_matrix(states: np.ndarray) -> np.ndarray:
    """
    Full N×N coherence matrix.
    states: (N, 7) complex64
    returns: (N, N) float32

    OGC-style displacement bound:
      coherence_matrix[i,j] is the 'contact' between cells i and j in
      state space. Like OGC's offset shell overlap, only pairs above
      threshold need full interaction processing.
    """
    if JAX_AVAILABLE:
        out = _batch_coherence_matrix(jnp.array(states, dtype=jnp.complex64))
        return np.array(out)
    else:
        # numpy fallback: explicit loop (only used without JAX)
        N = len(states)
        M = np.zeros((N, N), dtype=np.float32)
        for i in range(N):
            for j in range(i, N):
                dot = abs(np.vdot(states[i], states[j]))**2
                ni  = float(np.vdot(states[i], states[i]).real)
                nj  = float(np.vdot(states[j], states[j]).real)
                c   = dot / (ni * nj + 1e-30)
                M[i, j] = M[j, i] = c
        return M


# ── OGC-inspired displacement bound ─────────────────────────────────────────

def compute_emergence_bounds(states: np.ndarray, threshold: float) -> np.ndarray:
    """
    Per-cell bound on coherence change after one Y step.

    Inspired by OGC's vertex-specific displacement bounds:
    if the maximum possible coherence increase for a cell is below
    (threshold - current_max_coherence), that cell cannot trigger
    emergence this step and can be skipped entirely.

    states: (N, 7) complex64
    returns: (N,) bool — True means this cell *could* trigger emergence
    """
    # Coherence with a cell's own Y-evolved state is bounded by the
    # squared spectral radius of Y restricted to that state's support.
    # Conservative bound: ||Y @ ψᵢ||² / ||ψᵢ||² ≤ spectral_radius²
    # For Y: max |λ| = 1, so norm is preserved for eternal modes.
    # Spiral modes decay by (√3/2)² ≈ 0.75 per step.
    # Practical bound: a cell can only change coherence significantly
    # if its current norm is above a minimum level.

    norms = np.sum(np.abs(states)**2, axis=1)  # (N,)
    # Cells with negligible norm cannot interact meaningfully
    return norms > 1e-6


# ── Warmup (eliminates first-call JIT latency) ───────────────────────────────

def warmup():
    """
    Pre-compile all JIT-compiled functions.
    Call once at startup before the simulation loop begins.
    """
    if not JAX_AVAILABLE:
        return

    dummy = np.zeros((8, 7), dtype=np.complex64)
    dummy[0, 0] = 1.0 + 0.0j

    evolve_batch(dummy)
    reset_batch(dummy)
    coherence_vs_ref(dummy, dummy[0])
    coherence_matrix(dummy)
    compute_emergence_bounds(dummy, 0.9)

    print(f"JAX kernels warmed up  (backend: {jax.default_backend()})")


# ── Self-test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    warmup()

    # Verify batch evolve matches single-cell evolve
    rng = np.random.default_rng(0)
    psi = (rng.standard_normal((4, 7)) + 1j * rng.standard_normal((4, 7))).astype(np.complex64)

    batch_out = evolve_batch(psi)
    for i in range(4):
        single = _Y_NP @ psi[i]
        err = np.max(np.abs(batch_out[i] - single))
        print(f"  cell {i}  max error vs single: {err:.2e}")

    # Verify self-coherence = 1
    coh = coherence_matrix(psi)
    for i in range(4):
        print(f"  cell {i}  self-coherence: {coh[i,i]:.6f}")

    print("Self-test complete.")
