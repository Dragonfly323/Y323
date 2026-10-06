# resonance.py
"""
Resonance: a living state in ℂ⁷.

The full dynamics happen here, in ℂ⁷, under the action of Y.
The real manifold M is the observable slice — accessed only at observation time.

Architecture:
  • state   ∈ ℂ⁷   — the full complex state (evolves under Y)
  • point   ∈ M    — Re(state) projected onto M (computed on demand)
  • evolve()       — applies Y exactly in ℂ⁷
  • reset()        — applies P_stable (nilpotent reset, called every 3 steps)
  • observe()      — projects Re(state) onto M
  • coherence_with — |⟨ψ₁|ψ₂⟩|² / (‖ψ₁‖·‖ψ₂‖)  in ℂ⁷ (correct quantum inner product)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from geometry import ManifoldPoint, RawState
from y323operator import get_operator, SpectralFingerprint


@dataclass
class Resonance:
    """
    A living state in ℂ⁷.
    Immutable pattern: every operation returns a NEW Resonance.
    """
    state: np.ndarray       # complex ℂ⁷ vector
    iteration: int = 0
    cascade_count: int = 0  # how many nilpotent resets have occurred

    def __post_init__(self):
        self.state = np.asarray(self.state, dtype=complex).ravel()
        if len(self.state) != 7:
            raise ValueError(f"State must be length 7, got {len(self.state)}")

    # ------------------------------------------------------------------
    # Observation (collapse to M)
    # ------------------------------------------------------------------

    @property
    def point(self) -> ManifoldPoint:
        """
        Observe the state: project Re(ψ) onto M.
        This is the measurement step — the collapse from ℂ⁷ to experience.
        """
        raw = RawState.from_array(self.state.real)
        return ManifoldPoint.from_raw(raw)

    @property
    def tau(self) -> float:
        """τ of the observed (projected) point."""
        return float(self.state.real[0]) / (np.linalg.norm(self.state.real) + 1e-30)

    @property
    def coherence(self) -> float:
        """Φ = |φ₁|²·|φ₂|² of the observed point."""
        return self.point.to_raw().coherence()

    @property
    def bias_sq(self) -> float:
        """Ξ² of the observed point."""
        return self.point.to_raw().bias_sq()

    @property
    def norm(self) -> float:
        """‖ψ‖ in ℂ⁷."""
        return float(np.linalg.norm(self.state))

    @property
    def fingerprint(self) -> SpectralFingerprint:
        """Spectral decomposition of the full complex state."""
        return get_operator().fingerprint(self.state)

    @property
    def dominant_mode(self) -> str:
        return self.fingerprint.dominant_mode

    @property
    def nilpotent_potential(self) -> float:
        return self.fingerprint.nilpotent_potential

    # ------------------------------------------------------------------
    # Dynamics
    # ------------------------------------------------------------------

    def evolve(self, steps: int = 1) -> 'Resonance':
        """
        Apply Y exactly in ℂ⁷, one step at a time.
        Returns a new Resonance — the original is unchanged.
        """
        if steps == 0:
            return self

        op = get_operator()
        new_state = op.apply(self.state, steps)
        new_iter   = self.iteration + steps

        return Resonance(
            state=new_state,
            iteration=new_iter,
            cascade_count=self.cascade_count,
        )

    def reset(self) -> 'Resonance':
        """
        Apply the nilpotent reset: ψ ← P_stable · ψ.
        Annihilates transient (λ=0) components.
        Called by the world every 3 simulation steps.
        """
        op = get_operator()
        new_state = op.nilpotent_reset(self.state)
        return Resonance(
            state=new_state,
            iteration=self.iteration,
            cascade_count=self.cascade_count + 1,
        )

    def perturb(self, stimulus: ManifoldPoint, blend: float = 0.3) -> 'Resonance':
        """
        Blend in a stimulus from the real manifold.
        The stimulus is lifted to ℂ⁷ as a real vector, then blended.
        """
        stim_vec = stimulus.to_array().astype(complex)
        # Normalise stimulus to same norm as current state
        stim_norm = np.linalg.norm(stim_vec)
        self_norm = np.linalg.norm(self.state)
        if stim_norm > 1e-30:
            stim_vec = stim_vec * (self_norm / stim_norm)

        new_state = (1 - blend) * self.state + blend * stim_vec
        return Resonance(
            state=new_state,
            iteration=self.iteration,
            cascade_count=self.cascade_count,
        )

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def coherence_with(self, other: 'Resonance') -> float:
        """
        Quantum-like coherence between two complex states:
          |⟨ψ₁|ψ₂⟩|² / (‖ψ₁‖² · ‖ψ₂‖²)
        Range [0, 1].  1 = identical direction in ℂ⁷.
        """
        n1 = np.linalg.norm(self.state)
        n2 = np.linalg.norm(other.state)
        if n1 < 1e-30 or n2 < 1e-30:
            return 0.0
        dot = np.vdot(self.state, other.state)   # conjugate-linear in first arg
        return float(abs(dot)**2 / (n1**2 * n2**2))

    def distance_to(self, other: 'Resonance') -> float:
        """Geodesic distance between the two observed (projected) points."""
        v1 = self.point.to_array()
        v2 = other.point.to_array()
        v1 /= np.linalg.norm(v1) + 1e-30
        v2 /= np.linalg.norm(v2) + 1e-30
        return float(np.arccos(np.clip(np.dot(v1, v2), -1.0, 1.0)))

    def __repr__(self) -> str:
        fp = self.fingerprint
        return (f"Resonance(τ={self.tau:.3f}, "
                f"eternal={fp.energy_eternal:.2f}, "
                f"spiral={fp.energy_spiral:.2f}, "
                f"nil={fp.energy_nilpotent:.2f}, "
                f"iter={self.iteration}, resets={self.cascade_count})")
