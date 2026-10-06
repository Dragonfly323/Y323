# cell.py
"""
WorldCell: a resonance anchored to a position in R^3.

A cell is the fundamental unit of the simulation — a point in space
carrying a resonance state in C^7. The resonance evolves under Y,
and the cell's position determines its spatial relationships.
"""

import numpy as np
import uuid
from dataclasses import dataclass, field
from typing import Tuple, List, Optional

from resonance import Resonance
from geometry import ManifoldPoint
from atlas import AtlasVector


@dataclass
class WorldCell:
    """
    A resonance state anchored to a spatial position.

    position    : (x, y, z) in R^3
    resonance   : current state in C^7, evolves under Y
    atlas_vec   : optional 64D semantic identity on S^63
    archetype   : name of the initialization archetype (informational)
    uid         : unique identifier
    birth_step  : simulation step at which this cell was created
    parents     : uids of parent cells if born via emergence
    """
    position: Tuple[float, float, float]
    resonance: Resonance
    atlas_vec: Optional[AtlasVector] = None
    archetype: str = ""
    uid: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    birth_step: int = 0
    parents: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.position = tuple(float(p) for p in self.position)

    @property
    def point(self) -> ManifoldPoint:
        """
        Observed point on M.
        Projects the complex resonance state to the real manifold.
        This is the only view of the cell that should be used for rendering.
        """
        return self.resonance.point

    @property
    def tau(self) -> float:
        """Normalized tau coordinate from the observed point."""
        return self.resonance.tau

    @property
    def density(self) -> float:
        """
        Density proxy in [0,1] derived from resonance properties.
        Used for gravity and pressure calculations.
        """
        fp = self.resonance.fingerprint
        # High tau + high eternal fraction = dense
        return 0.6 * max(self.tau, 0.0) + 0.4 * fp.energy_eternal

    def coherence_with(self, other: 'WorldCell') -> float:
        """Coherence between two cells' resonances."""
        return self.resonance.coherence_with(other.resonance)

    def semantic_similarity(self, other: 'WorldCell') -> float:
        """
        Cosine similarity on S^63 (Atlas space).
        Returns 0 if either cell has no atlas_vec.
        """
        if self.atlas_vec is None or other.atlas_vec is None:
            return 0.0
        return self.atlas_vec.cosine_similarity(other.atlas_vec)

    def __repr__(self) -> str:
        arch = f", arch={self.archetype!r}" if self.archetype else ""
        return (f"WorldCell({self.uid[:4]}, "
                f"pos=({self.position[0]:.1f}, {self.position[1]:.1f}, {self.position[2]:.1f}), "
                f"τ={self.tau:.3f}{arch})")