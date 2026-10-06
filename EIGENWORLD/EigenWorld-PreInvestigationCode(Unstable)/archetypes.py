# archetypes.py
"""
Named canonical entities defined simultaneously in two spaces:

    7D space  (M subset R^7):  dynamic character, derived from geometry.py
    64D space (S^63 subset R^64): semantic identity, from Atlas channel defs

The 64D definitions are primary. The 7D state is derived via binding.atlas_to_7d()
and then observed (projected onto M) for use as an initial Resonance state.
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional

from atlas import AtlasVector
from binding import atlas_to_7d
from geometry import ManifoldPoint, RawState


# ---------------------------------------------------------------------------
# Archetype
# ---------------------------------------------------------------------------

@dataclass
class Archetype:
    """
    A named canonical entity with representations in both spaces.

    vec  : AtlasVector   — 64D semantic identity (primary)
    point: ManifoldPoint — 7D geometric state (derived via atlas_to_7d, then projected)
    name : str
    """
    name:  str
    vec:   AtlasVector
    point: ManifoldPoint

    @classmethod
    def build(cls, name: str, spec: Dict[str, float]) -> "Archetype":
        """Build from a {channel_name: value} dict."""
        vec = AtlasVector.from_dict(spec)
        state_7d = atlas_to_7d(vec)  # returns complex array
        raw = RawState(
            tau=float(state_7d[0].real),
            phi1=complex(float(state_7d[1].real), float(state_7d[2].real)),
            phi2=complex(float(state_7d[3].real), float(state_7d[4].real)),
            xi=complex(float(state_7d[5].real),  float(state_7d[6].real)),
        )
        point = ManifoldPoint.from_raw(raw)
        return cls(name=name, vec=vec, point=point)

    def slerp_to(self, other: "Archetype", t: float,
                 name: str = "") -> "Archetype":
        """SLERP between two archetypes on S^63, re-derive 7D state."""
        new_vec = self.vec.slerp(other.vec, t)
        new_name = name or f"{self.name}_{other.name}_t{t:.2f}"
        state_7d = atlas_to_7d(new_vec)
        raw = RawState(
            tau=float(state_7d[0].real),
            phi1=complex(float(state_7d[1].real), float(state_7d[2].real)),
            phi2=complex(float(state_7d[3].real), float(state_7d[4].real)),
            xi=complex(float(state_7d[5].real),  float(state_7d[6].real)),
        )
        return Archetype(name=new_name, vec=new_vec,
                         point=ManifoldPoint.from_raw(raw))

    def __repr__(self) -> str:
        return (f"Archetype({self.name!r}, "
                f"τ={self.point.tau:.3f}, "
                f"64d_norm={np.linalg.norm(self.vec.to_array()):.3f})")


# ---------------------------------------------------------------------------
# 64D channel specifications for all primary archetypes
# ---------------------------------------------------------------------------

_SPECS: Dict[str, Dict[str, float]] = {

    # SAND: high temporal inertia, structural stability
    "sand": {
        "TemporalBias":    +0.75,
        "Stability":       +0.80,
        "Energy":          -0.20,
        "Entropy":          0.10,
        "Recognition":     +0.50,
        "ConservationFlux":+0.30,
        "Dissipation":      0.15,
        "TerrainRugosity":  0.40,
        "Porosity":         0.55,
        "SoilFertility":    0.20,
        "MicrostructureScale": -0.60,
        "ErosionRate":      0.30,
        "GrowthRate":      -0.50,
        "Metabolism":      -0.80,
        "Scale":           -0.40,
    },

    # WATER: low temporal inertia, fluid dynamics
    "water": {
        "TemporalBias":    -0.60,
        "Stability":       -0.40,
        "Energy":          +0.10,
        "Entropy":          0.65,
        "Frequency":        0.70,
        "ConservationFlux": +0.80,
        "Dissipation":      0.20,
        "Coupling":         0.60,
        "Hydrology":        0.95,
        "Porosity":         0.10,
        "ErosionRate":      0.50,
        "Metabolism":      -0.30,
        "GrowthRate":      -0.20,
        "Scale":           -0.20,
    },

    # AIR: near-zero inertia, maximal entropy
    "air": {
        "TemporalBias":    -0.90,
        "Stability":       -0.80,
        "Entropy":          0.85,
        "Frequency":        0.50,
        "Energy":          +0.05,
        "Dissipation":      0.05,
        "Coupling":         0.30,
        "Porosity":         0.95,
        "Scale":           +0.10,
    },

    # ROCK: maximum temporal inertia, rigid
    "rock": {
        "TemporalBias":    +0.95,
        "Stability":       +0.95,
        "Energy":          -0.50,
        "Entropy":          0.05,
        "Recognition":     +0.80,
        "Dissipation":      0.05,
        "TerrainRugosity":  0.80,
        "Porosity":         0.05,
        "SeismicStress":    0.40,
        "MineralConductivity": +0.30,
        "MicrostructureScale": +0.20,
        "ErosionRate":      0.05,
        "GrowthRate":      -0.90,
        "Metabolism":      -0.95,
        "Scale":           +0.20,
    },

    # FIRE: low inertia, maximum energy throughput
    "fire": {
        "TemporalBias":    -0.70,
        "Energy":          +0.90,
        "Entropy":          0.90,
        "Frequency":        0.85,
        "Dissipation":      0.80,
        "Coupling":         0.85,
        "RetrocausalBias": +0.40,
        "GrowthRate":      +0.60,
        "Metabolism":      +0.70,
        "ErosionRate":      0.70,
    },
}

# Derived archetypes: (parent_a, parent_b, t, name)
_DERIVED: List[tuple] = [
    ("sand",     "water", 0.50, "wet_sand"),
    ("wet_sand", "rock",  0.25, "mud"),
    ("air",      "water", 0.25, "cloud"),
    ("water",    "fire",  0.45, "steam"),
    ("sand",     "rock",  0.30, "sandstone"),
]


# ---------------------------------------------------------------------------
# ArchetypeLibrary
# ---------------------------------------------------------------------------

class ArchetypeLibrary:
    def __init__(self):
        # Build primary archetypes
        self._primary: Dict[str, Archetype] = {
            name: Archetype.build(name, spec)
            for name, spec in _SPECS.items()
        }
        self._cache: Dict[str, Archetype] = {}

    def _build_derived(self, name: str) -> Archetype:
        for (a, b, t, dname) in _DERIVED:
            if dname != name:
                continue
            arch_a = self.get(a)
            arch_b = self.get(b)
            return arch_a.slerp_to(arch_b, t, name=name)
        raise KeyError(f"No archetype: {name!r}")

    def get(self, name: str) -> Archetype:
        if name in self._primary:
            return self._primary[name]
        if name not in self._cache:
            self._cache[name] = self._build_derived(name)
        return self._cache[name]

    def primary_names(self) -> List[str]:
        return list(self._primary.keys())

    def all_names(self) -> List[str]:
        return list(self._primary.keys()) + [d[3] for d in _DERIVED]

    def cosine_rank(self, vec: AtlasVector, top_k: int = 3) -> List[tuple]:
        """Rank all archetypes by cosine similarity to vec."""
        results = [(self.get(n).vec.cosine_similarity(vec), n)
                   for n in self.all_names()]
        results.sort(reverse=True)
        return results[:top_k]


_LIBRARY: Optional[ArchetypeLibrary] = None


def get_archetypes() -> ArchetypeLibrary:
    global _LIBRARY
    if _LIBRARY is None:
        _LIBRARY = ArchetypeLibrary()
    return _LIBRARY


# For backward compatibility with older code
SAND = get_archetypes().get('sand').point
WATER = get_archetypes().get('water').point
AIR = get_archetypes().get('air').point
ROCK = get_archetypes().get('rock').point
FIRE = get_archetypes().get('fire').point