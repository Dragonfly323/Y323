# total_space.py
"""
The Total Space: every entity in the universe is a single point in R^93.

This is the geometric unification:
- Position (3) + Complex state (14) + Atlas (64) + Fingerprint (7) + Velocity (3) + Age (1) + Potential (1)
- All operations are geometric: nearest neighbors, geodesics, curvature
- No special cases. No separate data structures. Just points on a manifold.

Inspired by Offset Geometric Contact (SIGGRAPH 2025):
    Precompute the geometry. Then let it run.
"""

import numpy as np
from scipy.spatial import KDTree
from scipy.sparse.csgraph import shortest_path
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass, field
import uuid
from collections import defaultdict

from resonance import Resonance
from cell import WorldCell
from atlas import AtlasVector
from y323operator import get_operator


# ---------------------------------------------------------------------------
# Constants: The 93 dimensions
# ---------------------------------------------------------------------------

DIM_POS = 3        # x, y, z
DIM_RE  = 7        # real part of complex state
DIM_IM  = 7        # imaginary part
DIM_ATLAS = 64     # semantic vector
DIM_FP = 7         # spectral fingerprint
DIM_VEL = 3        # velocity/momentum
DIM_AGE = 1        # timesteps since birth
DIM_POT = 1        # emergence potential (precomputed)

# Offsets for each section
OFFSET_POS = 0
OFFSET_RE  = OFFSET_POS + DIM_POS
OFFSET_IM  = OFFSET_RE + DIM_RE
OFFSET_ATLAS = OFFSET_IM + DIM_IM
OFFSET_FP    = OFFSET_ATLAS + DIM_ATLAS
OFFSET_VEL   = OFFSET_FP + DIM_FP
OFFSET_AGE   = OFFSET_VEL + DIM_VEL
OFFSET_POT   = OFFSET_AGE + DIM_AGE
TOTAL_DIMS   = OFFSET_POT + DIM_POT  # = 93

assert TOTAL_DIMS == 93, f"Expected 93 dimensions, got {TOTAL_DIMS}"


# ---------------------------------------------------------------------------
# Point in Total Space
# ---------------------------------------------------------------------------

@dataclass
class TotalPoint:
    """
    One point in the total space, representing a complete local state.
    
    The point is stored as a flat 93D vector, but we provide properties
    to access each semantic section.
    """
    data: np.ndarray                    # shape (93,), float64
    cell_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    archetype: str = ""
    timestamp: int = 0                  # simulation step when created
    
    def __post_init__(self):
        if len(self.data) != TOTAL_DIMS:
            raise ValueError(f"Data must be {TOTAL_DIMS}D, got {len(self.data)}")
    
    # -----------------------------------------------------------------------
    # Property accessors (view into the flat array)
    # -----------------------------------------------------------------------
    
    @property
    def position(self) -> np.ndarray:
        """3D spatial position [x, y, z]."""
        return self.data[OFFSET_POS:OFFSET_POS + DIM_POS]
    
    @position.setter
    def position(self, value: np.ndarray):
        self.data[OFFSET_POS:OFFSET_POS + DIM_POS] = value
    
    @property
    def state_re(self) -> np.ndarray:
        """Real part of complex 7D state."""
        return self.data[OFFSET_RE:OFFSET_RE + DIM_RE]
    
    @state_re.setter
    def state_re(self, value: np.ndarray):
        self.data[OFFSET_RE:OFFSET_RE + DIM_RE] = value
    
    @property
    def state_im(self) -> np.ndarray:
        """Imaginary part of complex 7D state."""
        return self.data[OFFSET_IM:OFFSET_IM + DIM_IM]
    
    @state_im.setter
    def state_im(self, value: np.ndarray):
        self.data[OFFSET_IM:OFFSET_IM + DIM_IM] = value
    
    @property
    def atlas(self) -> np.ndarray:
        """64D semantic vector."""
        return self.data[OFFSET_ATLAS:OFFSET_ATLAS + DIM_ATLAS]
    
    @atlas.setter
    def atlas(self, value: np.ndarray):
        self.data[OFFSET_ATLAS:OFFSET_ATLAS + DIM_ATLAS] = value
    
    @property
    def fingerprint(self) -> np.ndarray:
        """7D spectral fingerprint [eternal, spiral, nilpotent, tau, ...]."""
        return self.data[OFFSET_FP:OFFSET_FP + DIM_FP]
    
    @fingerprint.setter
    def fingerprint(self, value: np.ndarray):
        self.data[OFFSET_FP:OFFSET_FP + DIM_FP] = value
    
    @property
    def velocity(self) -> np.ndarray:
        """3D velocity/momentum."""
        return self.data[OFFSET_VEL:OFFSET_VEL + DIM_VEL]
    
    @velocity.setter
    def velocity(self, value: np.ndarray):
        self.data[OFFSET_VEL:OFFSET_VEL + DIM_VEL] = value
    
    @property
    def age(self) -> float:
        """Timesteps since birth."""
        return float(self.data[OFFSET_AGE])
    
    @age.setter
    def age(self, value: float):
        self.data[OFFSET_AGE] = value
    
    @property
    def emergence_potential(self) -> float:
        """Precomputed likelihood of emergence (0-1)."""
        return float(self.data[OFFSET_POT])
    
    @emergence_potential.setter
    def emergence_potential(self, value: float):
        self.data[OFFSET_POT] = value
    
    # -----------------------------------------------------------------------
    # Complex state reconstruction
    # -----------------------------------------------------------------------
    
    def get_complex_state(self) -> np.ndarray:
        """Reconstruct the complex 7D state from real/imag parts."""
        return self.state_re + 1j * self.state_im
    
    def set_complex_state(self, state: np.ndarray):
        """Set both real and imag parts from a complex array."""
        self.state_re = state.real
        self.state_im = state.imag
    
    # -----------------------------------------------------------------------
    # Lifting from WorldCell
    # -----------------------------------------------------------------------
    
    @classmethod
    def from_cell(cls, cell: WorldCell, step: int) -> 'TotalPoint':
        """
        Lift a WorldCell into the total space.
        This is the canonical embedding.
        """
        data = np.zeros(TOTAL_DIMS)
        
        # Position
        data[OFFSET_POS:OFFSET_POS + DIM_POS] = cell.position
        
        # Complex state
        state = cell.resonance.state
        data[OFFSET_RE:OFFSET_RE + DIM_RE] = state.real
        data[OFFSET_IM:OFFSET_IM + DIM_IM] = state.imag
        
        # Atlas (if present)
        if cell.atlas_vec is not None:
            data[OFFSET_ATLAS:OFFSET_ATLAS + DIM_ATLAS] = cell.atlas_vec.to_array()
        
        # Spectral fingerprint
        fp = cell.resonance.fingerprint
        data[OFFSET_FP] = fp.energy_eternal
        data[OFFSET_FP + 1] = fp.energy_spiral
        data[OFFSET_FP + 2] = fp.energy_nilpotent
        data[OFFSET_FP + 3] = cell.tau
        data[OFFSET_FP + 4] = cell.resonance.coherence
        # 5-6 reserved
        
        # Age
        data[OFFSET_AGE] = step - cell.birth_step
        
        # Emergence potential (to be filled later)
        data[OFFSET_POT] = 0.0
        
        return cls(
            data=data,
            cell_id=cell.uid,
            archetype=cell.archetype,
            timestamp=step
        )
    
    # -----------------------------------------------------------------------
    # Geometry
    # -----------------------------------------------------------------------
    
    def distance_to(self, other: 'TotalPoint', metric: str = 'euclidean') -> float:
        """
        Distance in total space.
        Different metrics can be used for different purposes.
        """
        if metric == 'euclidean':
            return float(np.linalg.norm(self.data - other.data))
        elif metric == 'physical':
            # Only spatial dimensions
            return float(np.linalg.norm(self.position - other.position))
        elif metric == 'state':
            # Only state dimensions (complex + atlas)
            state_self = np.concatenate([self.state_re, self.state_im, self.atlas])
            state_other = np.concatenate([other.state_re, other.state_im, other.atlas])
            return float(np.linalg.norm(state_self - state_other))
        else:
            raise ValueError(f"Unknown metric: {metric}")
    
    def __repr__(self) -> str:
        return (f"TotalPoint({self.cell_id[:4]}, "
                f"pos=({self.position[0]:.1f}, {self.position[1]:.1f}, {self.position[2]:.1f}), "
                f"age={self.age:.0f})")


# ---------------------------------------------------------------------------
# The Total Space: a point cloud with geometric operations
# ---------------------------------------------------------------------------

class TotalSpace:
    """
    The entire universe as a single point cloud in R^93.
    
    All operations are geometric:
    - Nearest neighbors (for interaction)
    - Geodesic distances (for memory transport)
    - Local density (for emergence)
    - Tangent spaces (for dynamics)
    """
    
    def __init__(self):
        self.points: List[TotalPoint] = []
        self.index: Dict[str, int] = {}          # cell_id -> index
        self.kdtree: Optional[KDTree] = None
        self.adjacency: Optional[np.ndarray] = None
        self.geodesic_distances: Optional[np.ndarray] = None
        
        # For incremental updates
        self._dirty = True
        self._point_array: Optional[np.ndarray] = None
    
    def add_point(self, point: TotalPoint) -> int:
        """Add a point, return its index."""
        idx = len(self.points)
        self.points.append(point)
        self.index[point.cell_id] = idx
        self._dirty = True
        return idx
    
    def remove_point(self, cell_id: str) -> Optional[TotalPoint]:
        """Remove a point by ID. Returns the point if found."""
        if cell_id not in self.index:
            return None
        idx = self.index[cell_id]
        point = self.points.pop(idx)
        
        # Update indices
        del self.index[cell_id]
        for i, p in enumerate(self.points[idx:], start=idx):
            self.index[p.cell_id] = i
        
        self._dirty = True
        return point
    
    def get_point(self, cell_id: str) -> Optional[TotalPoint]:
        """Get point by ID."""
        if cell_id not in self.index:
            return None
        return self.points[self.index[cell_id]]
    
    def update_point(self, cell_id: str, **kwargs) -> bool:
        """
        Update a point's data.
        kwargs can be any property: position, state_re, etc.
        """
        if cell_id not in self.index:
            return False
        point = self.points[self.index[cell_id]]
        for key, value in kwargs.items():
            if hasattr(point, key):
                setattr(point, key, value)
            else:
                # Assume it's a direct data index
                point.data[key] = value
        self._dirty = True
        return True
    
    # -----------------------------------------------------------------------
    # Index building
    # -----------------------------------------------------------------------
    
    def _build_point_array(self) -> np.ndarray:
        """Build the full point array for KD-tree."""
        if self._point_array is None or self._dirty:
            self._point_array = np.array([p.data for p in self.points])
            self._dirty = False
        return self._point_array
    
    def build_kdtree(self):
        """Build or rebuild KD-tree for spatial queries."""
        points = self._build_point_array()
        self.kdtree = KDTree(points)
    
    def neighbors(self, point: TotalPoint, radius: float, 
                  metric: str = 'euclidean') -> List[TotalPoint]:
        """
        Find all points within radius in total space.
        """
        if self.kdtree is None or self._dirty:
            self.build_kdtree()
        
        if metric == 'euclidean':
            indices = self.kdtree.query_ball_point(point.data, radius)
        else:
            # For other metrics, we need to do brute force
            # This is slow but accurate
            indices = []
            for i, p in enumerate(self.points):
                if point.distance_to(p, metric) <= radius:
                    indices.append(i)
        
        return [self.points[i] for i in indices if self.points[i].cell_id != point.cell_id]
    
    def k_nearest(self, point: TotalPoint, k: int, 
                  metric: str = 'euclidean') -> List[TotalPoint]:
        """Find k nearest neighbors."""
        if self.kdtree is None or self._dirty:
            self.build_kdtree()
        
        if metric == 'euclidean':
            distances, indices = self.kdtree.query(point.data, k=k+1)
            # Skip self (first neighbor)
            return [self.points[i] for i in indices[1:] if i < len(self.points)]
        else:
            # Brute force for other metrics
            dists = [(point.distance_to(p, metric), i) 
                     for i, p in enumerate(self.points) if p.cell_id != point.cell_id]
            dists.sort()
            return [self.points[i] for _, i in dists[:k]]
    
    # -----------------------------------------------------------------------
    # Graph operations
    # -----------------------------------------------------------------------
    
    def build_adjacency(self, radius: float, metric: str = 'euclidean'):
        """
        Build adjacency graph based on distance threshold.
        Each point connected to others within radius.
        """
        n = len(self.points)
        self.adjacency = np.zeros((n, n))
        
        if metric == 'euclidean' and self.kdtree is not None:
            # Fast method using KD-tree
            for i, point in enumerate(self.points):
                indices = self.kdtree.query_ball_point(point.data, radius)
                for j in indices:
                    if i != j:
                        dist = np.linalg.norm(point.data - self.points[j].data)
                        self.adjacency[i, j] = dist
                        self.adjacency[j, i] = dist
        else:
            # Brute force
            for i in range(n):
                for j in range(i+1, n):
                    dist = self.points[i].distance_to(self.points[j], metric)
                    if dist <= radius:
                        self.adjacency[i, j] = dist
                        self.adjacency[j, i] = dist
    
    def compute_geodesics(self):
        """Compute all-pairs geodesic distances on the adjacency graph."""
        if self.adjacency is None:
            raise ValueError("Build adjacency first with build_adjacency()")
        self.geodesic_distances = shortest_path(self.adjacency, directed=False)
    
    # -----------------------------------------------------------------------
    # Differential geometry
    # -----------------------------------------------------------------------
    
    def tangent_space(self, point: TotalPoint, radius: float) -> np.ndarray:
        """
        Compute the tangent space at a point via local PCA.
        Returns basis vectors for the tangent space (d x D).
        """
        neighbors = self.neighbors(point, radius)
        if len(neighbors) < 3:
            return np.eye(TOTAL_DIMS)  # fallback to Euclidean
        
        # Collect neighbor points
        X = np.array([n.data for n in neighbors])
        # Center at point
        X_centered = X - point.data
        
        # PCA
        U, s, Vt = np.linalg.svd(X_centered, full_matrices=False)
        
        # Number of significant dimensions (where singular value > threshold)
        rank = np.sum(s > s[0] * 0.1)
        rank = max(1, min(rank, 10))  # cap at 10
        
        # Tangent basis = first rank right singular vectors
        return Vt[:rank]
    
    def curvature(self, point: TotalPoint, radius: float) -> float:
        """
        Estimate scalar curvature at a point.
        Higher curvature = more "bent" manifold.
        """
        tangent = self.tangent_space(point, radius)
        # Rough estimate: 1 - (explained variance ratio of tangent space)
        # This is simplistic but works for relative comparisons
        return 1.0 - (tangent.shape[0] / TOTAL_DIMS)
    
    # -----------------------------------------------------------------------
    # Density and emergence
    # -----------------------------------------------------------------------
    
    def local_density(self, point: TotalPoint, radius: float) -> float:
        """Number of neighbors within radius, normalized."""
        neighbors = self.neighbors(point, radius)
        max_possible = len(self.points) - 1
        if max_possible == 0:
            return 0.0
        return len(neighbors) / max_possible
    
    def emergence_region(self, threshold: float = 0.1) -> np.ndarray:
        """
        Return boolean mask of points in high-density regions.
        Emergence happens where density exceeds threshold.
        """
        if self.kdtree is None:
            self.build_kdtree()
        
        densities = []
        for point in self.points:
            # Count neighbors within small radius
            indices = self.kdtree.query_ball_point(point.data, r=0.5)
            densities.append(len(indices) - 1)  # exclude self
        
        densities = np.array(densities)
        return densities > threshold * np.max(densities)
    
    # -----------------------------------------------------------------------
    # Serialization
    # -----------------------------------------------------------------------
    
    def to_dict(self) -> dict:
        """Serialize to dictionary (for saving)."""
        return {
            'points': [{
                'data': p.data.tolist(),
                'cell_id': p.cell_id,
                'archetype': p.archetype,
                'timestamp': p.timestamp
            } for p in self.points]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TotalSpace':
        """Load from dictionary."""
        space = cls()
        for p_data in data['points']:
            point = TotalPoint(
                data=np.array(p_data['data']),
                cell_id=p_data['cell_id'],
                archetype=p_data.get('archetype', ''),
                timestamp=p_data.get('timestamp', 0)
            )
            space.add_point(point)
        return space
    
    # -----------------------------------------------------------------------
    # Statistics
    # -----------------------------------------------------------------------
    
    @property
    def num_points(self) -> int:
        return len(self.points)
    
    def stats(self) -> dict:
        """Return statistics about the total space."""
        if not self.points:
            return {}
        
        data = self._build_point_array()
        return {
            'num_points': len(self.points),
            'mean_position': np.mean(data[:, OFFSET_POS:OFFSET_POS+DIM_POS], axis=0).tolist(),
            'mean_age': np.mean(data[:, OFFSET_AGE]),
            'mean_emergence_potential': np.mean(data[:, OFFSET_POT]),
            'bounds': {
                'x': (float(np.min(data[:, OFFSET_POS])), 
                      float(np.max(data[:, OFFSET_POS]))),
                'y': (float(np.min(data[:, OFFSET_POS+1])), 
                      float(np.max(data[:, OFFSET_POS+1]))),
                'z': (float(np.min(data[:, OFFSET_POS+2])), 
                      float(np.max(data[:, OFFSET_POS+2]))),
            }
        }
    
    def __repr__(self) -> str:
        return f"TotalSpace({len(self.points)} points, dim={TOTAL_DIMS})"


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Total space dimension: {TOTAL_DIMS}")
    print(f"  Position:     {DIM_POS}")
    print(f"  State (re):   {DIM_RE}")
    print(f"  State (im):   {DIM_IM}")
    print(f"  Atlas:        {DIM_ATLAS}")
    print(f"  Fingerprint:  {DIM_FP}")
    print(f"  Velocity:     {DIM_VEL}")
    print(f"  Age:          {DIM_AGE}")
    print(f"  Potential:    {DIM_POT}")
    
    # Create a test point
    test_data = np.random.randn(TOTAL_DIMS) * 0.1
    point = TotalPoint(data=test_data, archetype='test')
    
    print(f"\nTest point: {point}")
    print(f"  position: {point.position}")
    print(f"  age: {point.age}")
    
    # Test space
    space = TotalSpace()
    space.add_point(point)
    print(f"\n{space}")