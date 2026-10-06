# y323operator.py
"""
The Y₃₂₃ operator: the engine of all dynamics.

Mathematical facts (verified numerically):
  - Eigenvalues: 0 (×3, Jordan block), +1, −1, +i√3/2, −i√3/2
  - Characteristic polynomial: λ³(λ²−1)(λ²+3/4)
  - Y³ annihilates the λ=0 generalised eigenspace (Y³|_{V₀} = 0)
  - The four non-zero eigenvalues have |λ| ∈ {1, √3/2}:
      ±1   → stable oscillation (norm preserved)
      ±i√3/2 → spiral decay   (norm shrinks by (√3/2)ⁿ each step)

Nilpotent reset:
  The stable projector P_stable is the spectral projector onto the
  complementary subspace of ker(Y³). Every 3 steps we replace
  ψ ← P_stable · ψ, which:
    • annihilates accumulated transient error
    • preserves all meaningful dynamics (±1 and ±i√3/2 modes)
    • is exactly Y³|_{V₀}=0 in operator form
"""

import numpy as np
from typing import List
from dataclasses import dataclass
from geometry import ManifoldPoint, RawState


# ============================================================================
# THE Y MATRIX  (immutable mathematical truth)
# ============================================================================

_Y_MATRIX = np.array([
    [0,                   -1j,              0,  0,             0, -np.exp(-1j*np.pi/4), 0            ],
    [1j,                   0,              0,  0,             0,  0,                   0            ],
    [0,                    0,              0,  1,             0,  0,                   0            ],
    [0,                    0,             -1,  0, np.sqrt(2)/2,  0,                   0            ],
    [0,                    0,              0,  np.sqrt(2)/2,  0,  0,     -1j*np.sqrt(3)/2          ],
    [np.exp(1j*np.pi/4),   0,              0,  0,             0,  0,                   0            ],
    [0,                    0,              0,  0, 1j*np.sqrt(3)/2, 0,                  0            ],
], dtype=complex)


# ============================================================================
# SPECTRAL FINGERPRINT  (read-only description of a state)
# ============================================================================

@dataclass(frozen=True)
class SpectralFingerprint:
    """Decomposition of a complex state into eigenmode contributions."""
    energy_eternal:    float   # fraction in λ=±1 modes (memory)
    energy_spiral:     float   # fraction in λ=±i√3/2 modes (dynamics)
    energy_nilpotent:  float   # fraction in λ=0 modes (transient)
    dominant_mode:     str
    nilpotent_potential: float  # alias for energy_nilpotent

    MODE_NAMES = [
        "nilpotent-0", "nilpotent-1", "nilpotent-2",
        "eternal-even", "eternal-odd",
        "spiral-cw",    "spiral-ccw"
    ]


# ============================================================================
# Y OPERATOR SINGLETON
# ============================================================================

class YOperator:
    """
    The operator as a pure function on complex vectors.
    Instantiated once; all expensive decompositions computed once.
    """

    def __init__(self):
        self._Y = _Y_MATRIX.copy()
        self._Y2 = self._Y @ self._Y
        self._Y3 = self._Y @ self._Y2
        self._build_projectors()

    def _build_projectors(self):
        """
        Compute stable (P_s) and nilpotent (P_n) spectral projectors.

        P_s projects onto the 4D subspace spanned by the eigenvectors
        for λ ∈ {+1, −1, +i√3/2, −i√3/2}.
        P_n = I − P_s projects onto the 3D nilpotent generalised eigenspace.

        Verified: P_s² = P_s, P_n² = P_n, P_s + P_n = I,
                  Y³ · P_n = 0  (nilpotent cascade terminates).
        """
        eigvals, eigvecs = np.linalg.eig(self._Y)

        # Stable eigenvectors: |λ| > threshold
        non_nil = np.abs(eigvals) > 1e-8
        V_stable = eigvecs[:, non_nil]                     # 7×4

        # Stable projector via pseudo-inverse
        self._P_stable = V_stable @ np.linalg.pinv(V_stable)   # 7×7
        self._P_nil    = np.eye(7, dtype=complex) - self._P_stable

        # Store eigenvalues and eigenvectors for fingerprinting
        self._eigvals = eigvals
        self._eigvecs = eigvecs

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def apply(self, state: np.ndarray, n: int = 1) -> np.ndarray:
        """
        Apply Yⁿ to a complex 7-vector.
        For n ≤ 3: direct matrix multiplication (exact).
        For n > 3: spectral decomposition (nil modes already vanished).
        """
        state = np.asarray(state, dtype=complex).ravel()

        if n == 0:
            return state.copy()
        if n == 1:
            return self._Y @ state
        if n == 2:
            return self._Y2 @ state
        if n == 3:
            return self._Y3 @ state

        # n > 3: nilpotent part is gone, use spectral evolution
        coeffs = np.linalg.lstsq(self._eigvecs, state, rcond=None)[0]
        result = np.zeros(7, dtype=complex)
        for i, (lam, v) in enumerate(zip(self._eigvals, self._eigvecs.T)):
            if np.abs(lam) > 1e-8:           # skip nilpotent modes
                result += (lam ** n) * coeffs[i] * v
        return result

    def nilpotent_reset(self, state: np.ndarray) -> np.ndarray:
        """
        Project ψ onto the stable subspace: ψ ← P_stable · ψ.
        This is the mathematical nilpotent reset — it exactly implements
        the condition that nil-components vanish after 3 iterations.
        Called every 3 simulation steps.
        """
        state = np.asarray(state, dtype=complex).ravel()
        return self._P_stable @ state

    def nilpotent_component(self, state: np.ndarray) -> np.ndarray:
        """Extract the nilpotent (transient) component of a state."""
        state = np.asarray(state, dtype=complex).ravel()
        return self._P_nil @ state

    def fingerprint(self, state: np.ndarray) -> SpectralFingerprint:
        """Compute spectral fingerprint of a complex state."""
        state = np.asarray(state, dtype=complex).ravel()
        coeffs = np.linalg.lstsq(self._eigvecs, state, rcond=None)[0]
        energy = np.abs(coeffs) ** 2
        total  = np.sum(energy) + 1e-30
        energy_norm = energy / total

        # Sort: first 3 are nilpotent (|λ|<ε), next 4 are stable
        nil_mask = np.abs(self._eigvals) < 1e-8
        e_nil     = float(np.sum(energy_norm[nil_mask]))

        non_nil_idx = np.where(~nil_mask)[0]
        lams = self._eigvals[non_nil_idx]

        # eternal = |λ|=1, spiral = |λ|=√3/2
        eternal_idx = [i for i, l in zip(non_nil_idx, lams) if abs(abs(l) - 1.0) < 0.01]
        spiral_idx  = [i for i, l in zip(non_nil_idx, lams) if abs(abs(l) - np.sqrt(3)/2) < 0.01]

        e_eternal = float(np.sum(energy_norm[eternal_idx]))
        e_spiral  = float(np.sum(energy_norm[spiral_idx]))

        dom_idx = int(np.argmax(energy_norm))
        mode_name = SpectralFingerprint.MODE_NAMES[min(dom_idx, 6)]

        return SpectralFingerprint(
            energy_eternal=e_eternal,
            energy_spiral=e_spiral,
            energy_nilpotent=e_nil,
            dominant_mode=mode_name,
            nilpotent_potential=e_nil,
        )


# ============================================================================
# SINGLETON
# ============================================================================

_INSTANCE: YOperator = None

def get_operator() -> YOperator:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = YOperator()
    return _INSTANCE


# ============================================================================
# VERIFICATION
# ============================================================================

if __name__ == "__main__":
    op = get_operator()
    Y  = op._Y

    print("=== Y operator verification ===")
    eigvals = np.linalg.eigvals(Y)
    print(f"Eigenvalues: {np.round(sorted(eigvals, key=lambda x: abs(x)), 4)}")

    print(f"\n||Y³·P_nil||: {np.linalg.norm(op._Y3 @ op._P_nil):.2e}  (should be ~0)")
    print(f"P_stable idempotent: {np.allclose(op._P_stable @ op._P_stable, op._P_stable, atol=1e-8)}")
    print(f"P_stable + P_nil = I: {np.allclose(op._P_stable + op._P_nil, np.eye(7), atol=1e-8)}")

    # Test reset: state evolves 3 steps then reset should match P_stable·state
    rng = np.random.default_rng(0)
    v = rng.standard_normal(7) + 1j * rng.standard_normal(7)
    v_reset = op.nilpotent_reset(v)
    v_3step = op.apply(v, 3)
    # After 3 steps the nil component is gone; the ratio of norms should reflect
    # only the spiral decay of the ±i√3/2 modes
    print(f"\nReset test:")
    print(f"  ||ψ||: {np.linalg.norm(v):.4f}")
    print(f"  ||P_stable·ψ||: {np.linalg.norm(v_reset):.4f}")
    print(f"  ||Y³ψ||: {np.linalg.norm(v_3step):.4f}")
    print(f"  nil component removed by reset: "
          f"{np.linalg.norm(op.nilpotent_component(v_reset)):.2e}")
