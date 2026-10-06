"""
gbc_manifold.py
Build target and anti-target manifolds from GBC gameplay data.

M_target = winning trajectories (speedruns, expert play)
M_anti = death states, glitches, game overs

The dual-manifold framework lets us steer gameplay away from failure
and toward success by projecting onto the nilpotent subspace when
approaching M_anti and gently attracting toward M_target.
"""

import jax
import jax.numpy as jnp
import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, field
from pathlib import Path
import pickle
import json

from gbc_octonion import frame_to_octonion_field, octonion_field_to_T7, batch_frames_to_T7
from binding import observe
from atlas import AtlasVector
from sklearn.mixture import GaussianMixture


# -----------------------------------------------------------------------
# Data structures for gameplay trajectories
# -----------------------------------------------------------------------

@dataclass
class GameplayFrame:
    """One frame of gameplay with full context."""
    frame_data: jnp.ndarray          # (160, 144) of 15-bit colors
    inputs: jnp.ndarray               # Button states [A,B,Start,Select,Up,Down,Left,Right]
    timestamp: int                     # Frame number
    save_state: Optional[bytes] = None # Full savestate (if available)
    
    # Computed on demand
    _psi: Optional[jnp.ndarray] = None
    _atlas: Optional[AtlasVector] = None
    
    @property
    def psi(self) -> jnp.ndarray:
        """T' representation (7D complex) of this frame."""
        if self._psi is None:
            oct_field = frame_to_octonion_field(self.frame_data)
            self._psi = octonion_field_to_T7(oct_field)
        return self._psi
    
    @property
    def atlas(self) -> AtlasVector:
        """64D Atlas observation of this frame."""
        if self._atlas is None:
            # Observe from real part of psi
            real_7d = jnp.array([self.psi[0].real,
                                  self.psi[1].real, self.psi[2].real,
                                  self.psi[3].real, self.psi[4].real,
                                  self.psi[5].real, self.psi[6].real])
            atlas_vec = observe(real_7d)
            self._atlas = AtlasVector(atlas_vec)
        return self._atlas


@dataclass
class Trajectory:
    """A sequence of gameplay frames."""
    frames: List[GameplayFrame]
    game_name: str
    rom_hash: str
    outcome: str  # 'win', 'death', 'glitch', 'reset'
    
    def __len__(self) -> int:
        return len(self.frames)
    
    def to_psi_sequence(self) -> jnp.ndarray:
        """Return array of shape (len, 7) of complex psi states."""
        return jnp.array([f.psi for f in self.frames])
    
    def to_atlas_sequence(self) -> jnp.ndarray:
        """Return array of shape (len, 64) of Atlas vectors."""
        return jnp.array([f.atlas.to_array() for f in self.frames])


# -----------------------------------------------------------------------
# Manifold builders
# -----------------------------------------------------------------------

class GBCTrajectoryDatabase:
    """
    Collect and manage gameplay trajectories from multiple ROMs.
    """
    
    def __init__(self, data_dir: str = "gbc_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.trajectories: List[Trajectory] = []
        self.trajectory_index: Dict[str, List[int]] = {}  # game_name -> trajectory indices
        
    def add_trajectory(self, traj: Trajectory):
        """Add a trajectory to the database."""
        idx = len(self.trajectories)
        self.trajectories.append(traj)
        
        if traj.game_name not in self.trajectory_index:
            self.trajectory_index[traj.game_name] = []
        self.trajectory_index[traj.game_name].append(idx)
    
    def filter_by_outcome(self, outcome: str) -> List[Trajectory]:
        """Return all trajectories with given outcome."""
        return [t for t in self.trajectories if t.outcome == outcome]
    
    def filter_by_game(self, game_name: str) -> List[Trajectory]:
        """Return all trajectories for a specific game."""
        indices = self.trajectory_index.get(game_name, [])
        return [self.trajectories[i] for i in indices]
    
    def save(self, filename: str = "trajectory_db.pkl"):
        """Save database to disk."""
        # Convert JAX arrays to numpy for pickling
        serializable_trajs = []
        for traj in self.trajectories:
            frames = []
            for f in traj.frames:
                frames.append({
                    'frame_data': np.array(f.frame_data),
                    'inputs': np.array(f.inputs),
                    'timestamp': f.timestamp,
                    'save_state': f.save_state
                })
            serializable_trajs.append({
                'frames': frames,
                'game_name': traj.game_name,
                'rom_hash': traj.rom_hash,
                'outcome': traj.outcome
            })
        
        with open(self.data_dir / filename, 'wb') as f:
            pickle.dump(serializable_trajs, f)
    
    def load(self, filename: str = "trajectory_db.pkl"):
        """Load database from disk."""
        with open(self.data_dir / filename, 'rb') as f:
            serializable_trajs = pickle.load(f)
        
        self.trajectories = []
        for st in serializable_trajs:
            frames = []
            for sf in st['frames']:
                frames.append(GameplayFrame(
                    frame_data=jnp.array(sf['frame_data']),
                    inputs=jnp.array(sf['inputs']),
                    timestamp=sf['timestamp'],
                    save_state=sf.get('save_state')
                ))
            traj = Trajectory(
                frames=frames,
                game_name=st['game_name'],
                rom_hash=st['rom_hash'],
                outcome=st['outcome']
            )
            self.trajectories.append(traj)
        
        # Rebuild index
        self.trajectory_index = {}
        for i, traj in enumerate(self.trajectories):
            if traj.game_name not in self.trajectory_index:
                self.trajectory_index[traj.game_name] = []
            self.trajectory_index[traj.game_name].append(i)


class GBCOctonionManifold:
    """
    A manifold in T' space representing a class of gameplay states.
    
    Can be M_target (winning trajectories) or M_anti (death states).
    Fits a Gaussian Mixture Model to the psi states for distance queries.
    """
    
    def __init__(self, n_components: int = 10, covariance_type: str = 'full'):
        self.n_components = n_components
        self.covariance_type = covariance_type
        self.gmm = None
        self.psi_samples = None
        self.name = ""
        
    def fit(self, trajectories: List[Trajectory], name: str = ""):
        """
        Fit manifold to a collection of trajectories.
        
        Extracts all psi states and fits a GMM to their real parts.
        """
        self.name = name
        
        # Collect all psi states (complex)
        all_psi = []
        for traj in trajectories:
            psi_seq = traj.to_psi_sequence()
            all_psi.append(psi_seq)
        
        if not all_psi:
            print(f"Warning: No trajectories for manifold {name}")
            return
        
        self.psi_samples = jnp.concatenate(all_psi, axis=0)
        
        # GMM works on real vectors — take real part of psi
        psi_real = self.psi_samples.real  # shape (N, 7)
        
        # Fit GMM
        self.gmm = GaussianMixture(
            n_components=self.n_components,
            covariance_type=self.covariance_type,
            random_state=42
        )
        self.gmm.fit(np.array(psi_real))
        
        print(f"Fitted manifold '{name}' with {len(self.psi_samples)} states, "
              f"{self.n_components} components")
    
    def distance(self, psi: jnp.ndarray) -> float:
        """
        Distance from a psi state to this manifold.
        
        Returns negative log-likelihood under the GMM (lower = closer).
        """
        if self.gmm is None:
            return float('inf')
        
        # Take real part
        psi_real = psi.real.reshape(1, -1)
        
        # Negative log-likelihood as distance metric
        return -self.gmm.score(np.array(psi_real))
    
    def project(self, psi: jnp.ndarray) -> jnp.ndarray:
        """
        Project a psi state onto the manifold.
        
        Returns the closest point in the manifold (centroid of most likely component).
        """
        if self.gmm is None:
            return psi
        
        psi_real = psi.real.reshape(1, -1)
        
        # Find most likely component
        probs = self.gmm.predict_proba(np.array(psi_real))
        best_component = np.argmax(probs[0])
        
        # Return component mean
        mean_real = self.gmm.means_[best_component]
        
        # Reconstruct complex psi (imag parts from original)
        return jnp.array([
            mean_real[0] + 1j * psi[0].imag,
            mean_real[1] + 1j * psi[1].imag,
            mean_real[2] + 1j * psi[2].imag,
            mean_real[3] + 1j * psi[3].imag,
            mean_real[4] + 1j * psi[4].imag,
            mean_real[5] + 1j * psi[5].imag,
            mean_real[6] + 1j * psi[6].imag,
        ], dtype=jnp.complex64)
    
    def center(self) -> jnp.ndarray:
        """Return the center of the manifold (global mean)."""
        if self.psi_samples is None:
            return jnp.zeros(7, dtype=jnp.complex64)
        return jnp.mean(self.psi_samples, axis=0)
    
    def sample(self, n_samples: int = 1) -> jnp.ndarray:
        """Sample random psi states from the manifold."""
        if self.gmm is None:
            return jnp.zeros((n_samples, 7), dtype=jnp.complex64)
        
        samples_real, _ = self.gmm.sample(n_samples)
        # Add zero imaginary parts (could add noise later)
        samples = jnp.array([s + 0j for s in samples_real])
        return samples


# -----------------------------------------------------------------------
# Dual-manifold coordinator for GBC
# -----------------------------------------------------------------------

class GBCDualManifoldCoordinator:
    """
    Real-time gameplay steering using dual manifolds.
    
    Monitors current frame, computes distance to M_target and M_anti,
    and applies corrections to button inputs to steer away from death
    and toward winning trajectories.
    """
    
    def __init__(self, M_target: GBCOctonionManifold, M_anti: GBCOctonionManifold):
        self.M_target = M_target
        self.M_anti = M_anti
        
        # Import Y operator and nilpotent basis
        from y323operator import get_operator
        self.Y = get_operator()._Y  # 7x7 complex matrix
        self.nilpotent_basis = self._extract_nilpotent_basis()
        
        # Steering parameters
        self.danger_threshold = 0.1    # Distance to M_anti that triggers repulsion
        self.far_threshold = 0.3       # Distance to M_target that triggers attraction
        self.repulsion_strength = 10.0
        self.attraction_strength = 0.1
        
    def _extract_nilpotent_basis(self) -> List[jnp.ndarray]:
        """Extract basis vectors for λ=0 generalized eigenspace."""
        from y323operator import get_operator
        op = get_operator()
        
        # Get eigenvectors
        eigvals, eigvecs = np.linalg.eig(op._Y)
        
        # Find nilpotent eigenvectors (|λ| < 1e-8)
        nilpotent_vectors = []
        for i, val in enumerate(eigvals):
            if abs(val) < 1e-8:
                nilpotent_vectors.append(jnp.array(eigvecs[:, i], dtype=jnp.complex64))
        
        return nilpotent_vectors
    
    def project_to_nilpotent(self, vec: jnp.ndarray) -> jnp.ndarray:
        """Project a vector onto the nilpotent subspace."""
        projection = jnp.zeros_like(vec, dtype=jnp.complex64)
        for basis_vec in self.nilpotent_basis:
            coeff = jnp.vdot(vec, basis_vec) / jnp.vdot(basis_vec, basis_vec)
            projection += coeff * basis_vec
        return projection
    
    def psi_to_action_delta(self, psi: jnp.ndarray) -> jnp.ndarray:
        """
        Map a psi vector to an action correction.
        
        This is a learned mapping — for now, a simple heuristic.
        Returns an 8D vector to add to button logits.
        """
        # Simple heuristic: map psi components to buttons
        # This should be replaced with a learned model
        
        # τ (memory) -> A/B buttons (action timing)
        tau = psi[0].real
        
        # φ₁, φ₂ (futures) -> directional inputs
        phi1_mag = jnp.abs(psi[1] + 1j*psi[2])
        phi2_mag = jnp.abs(psi[3] + 1j*psi[4])
        
        # ξ (observation) -> Start/Select (menu actions)
        xi_mag = jnp.abs(psi[5] + 1j*psi[6])
        
        # Construct action delta
        # Order: [A, B, Start, Select, Up, Down, Left, Right]
        return jnp.array([
            tau * 0.5,                    # A
            (1.0 - tau) * 0.5,            # B
            xi_mag * 0.3,                  # Start
            xi_mag * 0.2,                  # Select
            phi1_mag * 0.5,                # Up
            phi2_mag * 0.5,                # Down
            (phi1_mag - phi2_mag) * 0.5,   # Left
            (phi2_mag - phi1_mag) * 0.5    # Right
        ], dtype=jnp.float32)
    
    def steer_frame(self, frame: GameplayFrame, action_logits: jnp.ndarray) -> jnp.ndarray:
        """
        Apply dual-manifold steering to button logits.
        
        Returns corrected action_logits.
        """
        psi = frame.psi
        
        # Compute distances
        d_target = self.M_target.distance(psi)
        d_anti = self.M_anti.distance(psi)
        
        # Check if approaching death/glitch
        if d_anti < self.danger_threshold:
            # Extract component heading toward M_anti
            closest_anti = self.M_anti.project(psi)
            deviation = psi - closest_anti
            
            # Project onto nilpotent subspace
            nil_component = self.project_to_nilpotent(deviation)
            
            # Apply cascade (annihilates in 3 steps)
            for _ in range(3):
                nil_component = self.Y @ nil_component
            
            # Map to action space
            action_correction = self.psi_to_action_delta(nil_component)
            
            # Strong repulsion
            return action_logits - action_correction * self.repulsion_strength
        
        # Check if too far from winning path
        elif d_target > self.far_threshold:
            # Gentle attraction toward target manifold
            target_center = self.M_target.center()
            attraction = (target_center - psi) * self.attraction_strength
            
            action_nudge = self.psi_to_action_delta(attraction)
            return action_logits + action_nudge
        
        # Safe zone — no intervention
        else:
            return action_logits


# -----------------------------------------------------------------------
# Example usage / testing
# -----------------------------------------------------------------------

if __name__ == "__main__":
    print("🧪 Testing GBC Manifold Building")
    print("=" * 50)
    
    # Create dummy trajectories for testing
    def create_dummy_trajectory(outcome: str, n_frames: int = 100) -> Trajectory:
        frames = []
        for i in range(n_frames):
            # Random frame data (simplified)
            frame_data = jnp.zeros((4, 4), dtype=jnp.int32)  # Tiny for testing
            frames.append(GameplayFrame(
                frame_data=frame_data,
                inputs=jnp.zeros(8, dtype=jnp.float32),
                timestamp=i
            ))
        return Trajectory(
            frames=frames,
            game_name="test_game",
            rom_hash="dummy_hash",
            outcome=outcome
        )
    
    # Create some winning trajectories
    winning_trajs = [create_dummy_trajectory('win') for _ in range(5)]
    
    # Create some death trajectories
    death_trajs = [create_dummy_trajectory('death') for _ in range(3)]
    
    # Build manifolds
    M_target = GBCOctonionManifold(n_components=3)
    M_target.fit(winning_trajs, name="target")
    
    M_anti = GBCOctonionManifold(n_components=2)
    M_anti.fit(death_trajs, name="anti")
    
    # Test a frame
    test_frame = create_dummy_trajectory('win').frames[0]
    
    # Dummy action logits
    action_logits = jnp.zeros(8, dtype=jnp.float32)
    
    # Create coordinator
    coord = GBCDualManifoldCoordinator(M_target, M_anti)
    
    # Test steering
    corrected = coord.steer_frame(test_frame, action_logits)
    
    print(f"\nAction logits before: {action_logits}")
    print(f"Action logits after:  {corrected}")
    print(f"\n✅ Manifold system ready")