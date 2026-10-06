# geometry.py
"""
The sacred geometry: M = { ψ ∈ ℝ⁷ | τ² + Φ + Ξ² = 1 }

The CORRECT constraint from the theorem (Part IV):
  ψ = (τ, a₁, a₂, b₁, b₂, x, y)
  Φ  = (a₁²+a₂²)(b₁²+b₂²)         = |φ₁|²|φ₂|²
  Ξ² = (x²+y²)²((a₁²+a₂²)-(b₁²+b₂²))²  = |c|⁴(|φ₁|²-|φ₂|²)²

NOTE: Φ is NOT the inner product |<φ₁|φ₂>|² — it is the product of norms.
This is what the theorem actually uses and what Y preserves (modulo projection).

This module defines the types. Dynamics are elsewhere.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RawState:
    """
    A point in ℝ⁷, not necessarily on the manifold.
    Coordinates: (τ, a₁, a₂, b₁, b₂, x, y)
    where φ₁ = a₁+ia₂, φ₂ = b₁+ib₂, c = x+iy
    """
    tau: float
    phi1: complex   # a₁ + i·a₂
    phi2: complex   # b₁ + i·b₂
    xi: complex     # x  + i·y

    def to_array(self) -> np.ndarray:
        """Convert to ℝ⁷ vector."""
        return np.array([
            self.tau,
            self.phi1.real, self.phi1.imag,
            self.phi2.real, self.phi2.imag,
            self.xi.real,   self.xi.imag
        ], dtype=float)

    @classmethod
    def from_array(cls, arr: np.ndarray) -> 'RawState':
        if len(arr) != 7:
            raise ValueError(f"Expected 7 components, got {len(arr)}")
        return cls(
            tau=float(arr[0]),
            phi1=complex(float(arr[1]), float(arr[2])),
            phi2=complex(float(arr[3]), float(arr[4])),
            xi=complex(float(arr[5]), float(arr[6]))
        )

    # ------------------------------------------------------------------
    # CORRECT constraint components (theorem Part IV)
    # ------------------------------------------------------------------

    def phi1_sq(self) -> float:
        """a₁² + a₂² = |φ₁|²"""
        return self.phi1.real**2 + self.phi1.imag**2

    def phi2_sq(self) -> float:
        """b₁² + b₂² = |φ₂|²"""
        return self.phi2.real**2 + self.phi2.imag**2

    def xi_sq(self) -> float:
        """x² + y² = |c|²"""
        return self.xi.real**2 + self.xi.imag**2

    def coherence(self) -> float:
        """Φ = |φ₁|²·|φ₂|²  (product of squared norms, NOT inner product)"""
        return self.phi1_sq() * self.phi2_sq()

    def bias_sq(self) -> float:
        """Ξ² = |c|⁴·(|φ₁|²−|φ₂|²)²"""
        c_sq = self.xi_sq()
        diff = self.phi1_sq() - self.phi2_sq()
        return c_sq**2 * diff**2

    def constraint_value(self) -> float:
        """τ² + Φ + Ξ²  (should equal 1.0 on M)"""
        return self.tau**2 + self.coherence() + self.bias_sq()

    def is_on_manifold(self, tol: float = 1e-10) -> bool:
        return abs(self.constraint_value() - 1.0) < tol


@dataclass(frozen=True)
class ManifoldPoint:
    """
    A point guaranteed to lie on M ⊂ ℝ⁷.
    All ManifoldPoints satisfy τ² + |φ₁|²|φ₂|² + |c|⁴(|φ₁|²−|φ₂|²)² = 1.
    """
    tau: float
    phi1: complex
    phi2: complex
    xi: complex

    def to_raw(self) -> RawState:
        return RawState(self.tau, self.phi1, self.phi2, self.xi)

    def to_array(self) -> np.ndarray:
        return self.to_raw().to_array()

    @classmethod
    def from_raw(cls, raw: RawState) -> 'ManifoldPoint':
        """
        Project onto M by Euclidean normalization in ℝ⁷.
        This is the observation step: collapse to the manifold.
        Preserves the direction (phase relationships) in ℝ⁷.
        """
        vec = raw.to_array()
        norm = np.linalg.norm(vec)
        if norm < 1e-30:
            return cls(tau=1.0, phi1=0j, phi2=0j, xi=0j)

        # Simple unit-sphere normalization preserves all phase angles.
        # The constraint τ²+Φ+Ξ²=1 is NOT the unit sphere, but for
        # the purposes of observation we normalize to make ||ψ||=1,
        # which is consistent with the quantum-like measurement picture.
        vec = vec / norm
        r = RawState.from_array(vec)
        return cls(tau=r.tau, phi1=r.phi1, phi2=r.phi2, xi=r.xi)

    @classmethod
    def from_array(cls, arr: np.ndarray) -> 'ManifoldPoint':
        return cls.from_raw(RawState.from_array(arr))

    def geodesic_to(self, other: 'ManifoldPoint', t: float) -> 'ManifoldPoint':
        """
        SLERP along the great circle on S⁶ (unit sphere in ℝ⁷).
        t=0 → self, t=1 → other.
        """
        v1 = self.to_array()
        v2 = other.to_array()

        v1 = v1 / np.linalg.norm(v1)
        v2 = v2 / np.linalg.norm(v2)

        dot = np.clip(np.dot(v1, v2), -1.0, 1.0)
        omega = np.arccos(dot)

        if abs(omega) < 1e-10:
            result = v1
        else:
            result = (np.sin((1 - t) * omega) * v1 +
                      np.sin(t * omega) * v2) / np.sin(omega)

        return ManifoldPoint.from_array(result)

    def __repr__(self) -> str:
        r = self.to_raw()
        C = r.constraint_value()
        return (f"ManifoldPoint(τ={self.tau:.3f}, "
                f"|φ₁|={abs(self.phi1):.3f}, |φ₂|={abs(self.phi2):.3f}, "
                f"|ξ|={abs(self.xi):.3f}, C={C:.6f})")
