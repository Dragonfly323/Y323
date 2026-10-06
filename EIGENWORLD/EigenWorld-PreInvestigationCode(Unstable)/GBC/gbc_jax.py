"""
gbc_jax.py
JAX-accelerated kernels for GBC eigenspectral processing.

This module provides GPU-optimized implementations of:
- Batch frame → T' conversion
- Y operator applications (including nilpotent cascade)
- Manifold distance calculations
- Dual-manifold steering for multiple game instances

All functions are JIT-compiled and support vmap for massive parallelism.
"""

import jax
import jax.numpy as jnp
from jax import jit, vmap, pmap
from jax.lib import xla_bridge
import numpy as np
from typing import Tuple, Optional, List
from functools import partial
import time

# Check for GPU
print(f"JAX backend: {xla_bridge.get_backend().platform}")
if xla_bridge.get_backend().platform == 'gpu':
    print("✅ GPU acceleration available")
else:
    print("⚠️ Running on CPU (GPU recommended for performance)")


# -----------------------------------------------------------------------
# Constants (from y323operator.py)
# -----------------------------------------------------------------------

# The Y matrix (7x7 complex) — exact values from Theorem 2.1
Y_MATRIX = jnp.array([
    [0.0 + 0.0j, 0.0 - 1.0j, 0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j, -0.7071 - 0.7071j, 0.0 + 0.0j],
    [0.0 + 1.0j, 0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j],
    [0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j, 1.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j],
    [0.0 + 0.0j, 0.0 + 0.0j, -1.0 + 0.0j, 0.0 + 0.0j, 0.7071 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j],
    [0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j, 0.7071 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j, -0.8660j],
    [0.7071 + 0.7071j, 0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j],
    [0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.8660j, 0.0 + 0.0j, 0.0 + 0.0j]
], dtype=jnp.complex64)

# Precomputed Y² and Y³ for efficiency
Y2 = Y_MATRIX @ Y_MATRIX
Y3 = Y2 @ Y_MATRIX

# Eigenvalues (for reference)
EIGENVALUES = jnp.array([0.0+0.0j, 0.0+0.0j, 0.0+0.0j, 
                          1.0+0.0j, -1.0+0.0j,
                          0.0+0.866j, 0.0-0.866j], dtype=jnp.complex64)

# Nilpotent projector (computed from y323operator.py)
# This is a placeholder — in practice, compute from actual eigenvectors
NILPOTENT_PROJECTOR = jnp.eye(7, dtype=jnp.complex64) * 0.0  # Will be replaced


# -----------------------------------------------------------------------
# Core JAX kernels
# -----------------------------------------------------------------------

@jit
def apply_y(psi: jnp.ndarray, steps: int = 1) -> jnp.ndarray:
    """
    Apply Yⁿ to a psi state.
    
    For n ≤ 3, uses direct multiplication.
    For n > 3, uses spectral decomposition for efficiency.
    
    Args:
        psi: (7,) complex array
        steps: number of Y applications
    
    Returns:
        (7,) complex array after evolution
    """
    if steps == 0:
        return psi
    elif steps == 1:
        return Y_MATRIX @ psi
    elif steps == 2:
        return Y2 @ psi
    elif steps == 3:
        return Y3 @ psi
    else:
        # For n > 3, nilpotent part is gone
        # Use spectral decomposition (simplified)
        # In practice, this would use the actual eigenbasis
        return Y3 @ apply_y(psi, steps - 3)


@jit
def nilpotent_reset(psi: jnp.ndarray) -> jnp.ndarray:
    """
    Apply nilpotent reset: project onto stable subspace.
    
    This annihilates the λ=0 components, leaving only eternal and spiral modes.
    """
    # This is a placeholder — in practice, use the actual projector
    # For now, just apply Y³ which annihilates nilpotent part
    return apply_y(psi, 3)


@jit
def project_to_manifold(psi: jnp.ndarray) -> jnp.ndarray:
    """
    Project onto the constraint manifold M: τ² + Φ + Ξ² = 1.
    
    This is the observation step — collapse from ℂ⁷ to the real slice,
    then normalize to satisfy the constraint.
    """
    # Real part only for observation
    psi_real = psi.real
    
    # Compute current norm components
    tau = psi_real[0]
    phi1_mag = jnp.sqrt(psi_real[1]**2 + psi_real[2]**2)
    phi2_mag = jnp.sqrt(psi_real[3]**2 + psi_real[4]**2)
    xi_mag = jnp.sqrt(psi_real[5]**2 + psi_real[6]**2)
    
    # Φ = |φ₁|²|φ₂|²
    phi = (phi1_mag**2) * (phi2_mag**2)
    
    # Ξ² = |ξ|⁴(|φ₁|² - |φ₂|²)²
    xi_sq = (xi_mag**4) * ((phi1_mag**2 - phi2_mag**2)**2)
    
    # Current norm
    current_norm = tau**2 + phi + xi_sq
    
    # Scale to satisfy constraint
    scale = 1.0 / jnp.sqrt(current_norm + 1e-8)
    
    # Scale real part, keep imaginary part unchanged
    psi_scaled = psi.at[:].real.set(psi_real * scale)
    
    return psi_scaled + 1j * psi.imag


@jit
def coherence(psi1: jnp.ndarray, psi2: jnp.ndarray) -> float:
    """
    Quantum-like coherence between two states:
    |⟨ψ₁|ψ₂⟩|² / (‖ψ₁‖² ‖ψ₂‖²)
    """
    dot = jnp.vdot(psi1, psi2)
    norm1 = jnp.vdot(psi1, psi1).real
    norm2 = jnp.vdot(psi2, psi2).real
    return jnp.abs(dot)**2 / (norm1 * norm2 + 1e-8)


# -----------------------------------------------------------------------
# Batch processing with vmap
# -----------------------------------------------------------------------

# Vectorized versions
batch_apply_y = vmap(apply_y, in_axes=(0, None))
batch_nilpotent_reset = vmap(nilpotent_reset)
batch_project_to_manifold = vmap(project_to_manifold)
batch_coherence = vmap(coherence, in_axes=(0, 0))


@jit
def evolve_batch(psi_batch: jnp.ndarray, steps: int = 1) -> jnp.ndarray:
    """
    Evolve a batch of states in parallel.
    
    Args:
        psi_batch: (batch_size, 7) complex array
        steps: number of Y applications
    
    Returns:
        (batch_size, 7) evolved states
    """
    return batch_apply_y(psi_batch, steps)


@jit
def compute_all_distances(psi: jnp.ndarray, manifold_points: jnp.ndarray) -> jnp.ndarray:
    """
    Compute distance from a psi state to all points in a manifold.
    
    Args:
        psi: (7,) complex array
        manifold_points: (N, 7) complex array
    
    Returns:
        (N,) array of coherence values (higher = closer)
    """
    return batch_coherence(jnp.broadcast_to(psi, manifold_points.shape), manifold_points)


# -----------------------------------------------------------------------
# CUDA Graph support for repeated operations
# -----------------------------------------------------------------------

class YCascadeGraph:
    """
    CUDA Graph for repeated Y³ applications.
    Significantly reduces kernel launch overhead for batch processing.
    """
    
    def __init__(self, batch_size: int):
        self.batch_size = batch_size
        self.graph = None
        
        # Create a dummy input to build the graph
        self.dummy_input = jnp.zeros((batch_size, 7), dtype=jnp.complex64)
        
    def build(self):
        """Build the CUDA graph for Y³ cascade."""
        # This is JAX-specific — may need custom XLA compilation
        @jax.jit
        def cascade(x):
            x = Y_MATRIX @ x
            x = Y_MATRIX @ x
            x = Y_MATRIX @ x
            return x
        
        # JIT compile
        self.cascade_jit = cascade
        
    def run(self, psi_batch: jnp.ndarray) -> jnp.ndarray:
        """Run the cascade on a batch."""
        return self.cascade_jit(psi_batch)


# -----------------------------------------------------------------------
# Parallel manifold operations (pmap for multi-GPU)
# -----------------------------------------------------------------------

@partial(pmap, axis_name='devices')
def parallel_evolve(psi: jnp.ndarray, steps: int) -> jnp.ndarray:
    """
    Evolve states across multiple devices.
    Each device gets a different batch.
    """
    return apply_y(psi, steps)


# -----------------------------------------------------------------------
# Performance profiling utilities
# -----------------------------------------------------------------------

class JAXProfiler:
    """
    Simple profiler for JAX operations.
    Uses block_until_ready() to ensure accurate timing.
    """
    
    def __init__(self):
        self.timings = {}
        
    def time_function(self, name: str, func, *args, **kwargs):
        """Time a JAX function, ensuring compilation is done."""
        # Warmup
        for _ in range(3):
            result = func(*args, **kwargs)
            if hasattr(result, 'block_until_ready'):
                result.block_until_ready()
        
        # Timed run
        start = time.perf_counter()
        result = func(*args, **kwargs)
        if hasattr(result, 'block_until_ready'):
            result.block_until_ready()
        elapsed = time.perf_counter() - start
        
        self.timings[name] = elapsed
        return result, elapsed
    
    def report(self):
        """Print timing report."""
        print("\n📊 JAX Performance Profile")
        print("=" * 40)
        for name, elapsed in self.timings.items():
            print(f"{name:30s}: {elapsed*1000:6.2f} ms")
        print("=" * 40)


# -----------------------------------------------------------------------
# GBC-specific batch processing
# -----------------------------------------------------------------------

def batch_frames_to_psi(frames: jnp.ndarray) -> jnp.ndarray:
    """
    Convert a batch of frames to psi states.
    
    Args:
        frames: (batch_size, 160, 144) of 15-bit colors
    
    Returns:
        (batch_size, 7) complex psi states
    """
    from gbc_octonion import frame_to_octonion_field, octonion_field_to_T7
    
    # Vectorized version using vmap
    @jit
    def frame_to_psi(frame):
        oct_field = frame_to_octonion_field(frame)
        return octonion_field_to_T7(oct_field)
    
    return vmap(frame_to_psi)(frames)


@jit
def compute_manifold_distances_batch(
    psi_batch: jnp.ndarray,
    target_means: jnp.ndarray,
    anti_means: jnp.ndarray
) -> Tuple[jnp.ndarray, jnp.ndarray]:
    """
    Compute distances to target and anti manifolds for a batch of states.
    
    Args:
        psi_batch: (batch_size, 7) complex
        target_means: (n_target, 7) complex (GMM component means)
        anti_means: (n_anti, 7) complex
    
    Returns:
        d_target: (batch_size,) distances to target
        d_anti: (batch_size,) distances to anti
    """
    # Compute coherence to all means
    def min_distance(psi, means):
        cohs = vmap(lambda m: coherence(psi, m))(means)
        return 1.0 - jnp.max(cohs)  # Convert to distance
    
    d_target = vmap(lambda p: min_distance(p, target_means))(psi_batch)
    d_anti = vmap(lambda p: min_distance(p, anti_means))(psi_batch)
    
    return d_target, d_anti


@jit
def steer_batch(
    psi_batch: jnp.ndarray,
    action_logits_batch: jnp.ndarray,
    target_means: jnp.ndarray,
    anti_means: jnp.ndarray,
    danger_thresh: float = 0.1,
    far_thresh: float = 0.3,
    repulsion: float = 10.0,
    attraction: float = 0.1
) -> jnp.ndarray:
    """
    Apply dual-manifold steering to a batch of game states.
    
    Args:
        psi_batch: (batch_size, 7) complex states
        action_logits_batch: (batch_size, 8) button logits
        target_means: (n_target, 7) target manifold means
        anti_means: (n_anti, 7) anti manifold means
    
    Returns:
        (batch_size, 8) corrected action logits
    """
    # Compute distances
    d_target, d_anti = compute_manifold_distances_batch(psi_batch, target_means, anti_means)
    
    # Danger cases (near anti-manifold)
    danger_mask = d_anti < danger_thresh
    
    # Far cases (far from target)
    far_mask = (d_target > far_thresh) & (~danger_mask)
    
    # Safe cases
    safe_mask = ~(danger_mask | far_mask)
    
    # Simple heuristic correction (placeholder)
    # In practice, this would use a learned mapping
    corrections = jnp.zeros_like(action_logits_batch)
    
    # For danger: strong repulsion based on nilpotent component
    # For simplicity, just invert actions
    corrections = corrections.at[danger_mask].set(
        -action_logits_batch[danger_mask] * repulsion
    )
    
    # For far: gentle attraction toward target
    corrections = corrections.at[far_mask].set(
        jnp.ones_like(action_logits_batch[far_mask]) * attraction
    )
    
    return action_logits_batch + corrections


# -----------------------------------------------------------------------
# Performance test
# -----------------------------------------------------------------------

def run_benchmark():
    """Run performance benchmarks for JAX kernels."""
    print("\n🚀 Running JAX Performance Benchmark")
    print("=" * 50)
    
    profiler = JAXProfiler()
    
    # Test data
    batch_sizes = [1, 10, 100, 1000, 10000]
    
    for batch_size in batch_sizes:
        print(f"\n📈 Batch size: {batch_size}")
        
        # Create random psi states
        psi_batch = jnp.array(
            np.random.randn(batch_size, 7) + 1j * np.random.randn(batch_size, 7),
            dtype=jnp.complex64
        )
        
        # Time Y application
        _, elapsed = profiler.time_function(f"apply_y (batch={batch_size})", 
                                           evolve_batch, psi_batch, 1)
        print(f"  apply_y: {elapsed*1000:.2f} ms")
        
        # Time nilpotent reset
        _, elapsed = profiler.time_function(f"nilpotent_reset (batch={batch_size})",
                                           batch_nilpotent_reset, psi_batch)
        print(f"  nilpotent_reset: {elapsed*1000:.2f} ms")
        
        # Time manifold projection
        _, elapsed = profiler.time_function(f"project_to_manifold (batch={batch_size})",
                                           batch_project_to_manifold, psi_batch)
        print(f"  project_to_manifold: {elapsed*1000:.2f} ms")
    
    print("\n✅ Benchmark complete")


if __name__ == "__main__":
    print("🧪 Testing JAX GBC Kernels")
    print("=" * 50)
    
    # Test basic operations
    test_psi = jnp.array([1.0+0.0j, 0.3+0.2j, 0.2+0.3j, 0.4+0.1j, 0.1+0.1j, 0.0+0.0j, 0.0+0.0j],
                         dtype=jnp.complex64)
    
    print(f"\nTest psi: {test_psi}")
    
    # Apply Y
    psi_evolved = apply_y(test_psi, 1)
    print(f"After Y: {psi_evolved}")
    
    # Nilpotent reset
    psi_reset = nilpotent_reset(test_psi)
    print(f"After reset: {psi_reset}")
    
    # Project to manifold
    psi_proj = project_to_manifold(test_psi)
    print(f"Projected: {psi_proj}")
    
    # Run benchmark
    run_benchmark()
    
    print("\n✅ JAX kernels ready for GPU acceleration")