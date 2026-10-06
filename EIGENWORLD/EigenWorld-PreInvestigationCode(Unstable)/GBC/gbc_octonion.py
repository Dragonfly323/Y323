"""
gbc_octonion.py
Game Boy Color pixel to octonion encoding.
Each pixel becomes a point in O (octonions), the 8D non-associative algebra.
Real part: luminance (stability, τ-like)
Imaginary parts: RGBA + motion + sprite ID + age

The octonion structure mirrors the 7D T' space plus one extra dimension,
allowing us to embed the full GBC state in a single algebraic object.
"""

import numpy as np
import jax
import jax.numpy as jnp
from typing import Tuple, Optional
from dataclasses import dataclass


# -----------------------------------------------------------------------
# Octonion class (Python-side only, not for JIT)
# -----------------------------------------------------------------------

@dataclass
class Octonion:
    """
    An octonion: a + b·i₁ + c·i₂ + d·i₃ + e·i₄ + f·i₅ + g·i₆ + h·i₇
    Where i₁...i₇ are the imaginary units with iₚ² = -1 and full non-associativity.
    """
    a: float  # real part (luminance)
    b: float  # i₁ (red)
    c: float  # i₂ (green)
    d: float  # i₃ (blue)
    e: float  # i₄ (dx motion)
    f: float  # i₅ (dy motion)
    g: float  # i₆ (sprite_id / 40)
    h: float  # i₇ (age / 255)

    def to_array(self) -> jnp.ndarray:
        """Convert to 8D JAX array."""
        return jnp.array([self.a, self.b, self.c, self.d, 
                          self.e, self.f, self.g, self.h], dtype=jnp.float32)

    @classmethod
    def from_array(cls, arr: jnp.ndarray) -> 'Octonion':
        return cls(a=arr[0], b=arr[1], c=arr[2], d=arr[3],
                   e=arr[4], f=arr[5], g=arr[6], h=arr[7])

    def norm(self) -> float:
        """Octonion norm = sqrt(a² + b² + c² + d² + e² + f² + g² + h²)"""
        return float(jnp.sqrt(jnp.sum(self.to_array() ** 2)))


# -----------------------------------------------------------------------
# GBC pixel encoding (JAX-compatible: returns arrays, not objects)
# -----------------------------------------------------------------------

# GBC color palette: 15-bit RGB (5 bits each)
GBC_RED_MASK = 0x1F
GBC_GREEN_MASK = 0x3E0  # bits 5-9
GBC_BLUE_MASK = 0x7C00  # bits 10-14

def gbc_color_to_rgb(color_15bit: int) -> Tuple[float, float, float]:
    """
    Convert 15-bit GBC color (0-32767) to normalized RGB floats.
    Format: 0bbbbbgggggrrrrr (bits 0-4 red, 5-9 green, 10-14 blue)
    """
    r = (color_15bit & GBC_RED_MASK) / 31.0
    g = ((color_15bit & GBC_GREEN_MASK) >> 5) / 31.0
    b = ((color_15bit & GBC_BLUE_MASK) >> 10) / 31.0
    return r, g, b


def luminance(r: float, g: float, b: float) -> float:
    """Standard luminance formula (Rec. 709)."""
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


@jax.jit
def pixel_to_octonion_array(
    color_15bit: int,
    prev_color: Optional[int] = None,
    sprite_id: int = 0,
    age: int = 0,
    dx: float = 0.0,
    dy: float = 0.0
) -> jnp.ndarray:
    """
    Encode a GBC pixel as an octonion array (8D).

    Returns:
        jnp.ndarray of shape (8,) with components [a,b,c,d,e,f,g,h]
    """
    # Extract RGB
    r, g, b = gbc_color_to_rgb(color_15bit)
    luma = luminance(r, g, b)

    # Compute motion if prev_color available
    if prev_color is not None:
        r_prev, g_prev, b_prev = gbc_color_to_rgb(prev_color)
        luma_prev = luminance(r_prev, g_prev, b_prev)
        # Simple motion estimate — JAX-compatible version
        dx = jnp.where(dx == 0.0, (r - r_prev) * 160.0, dx)
        dy = jnp.where(dy == 0.0, (g - g_prev) * 144.0, dy)

    # Normalize motion to [-1, 1] range
    dx_norm = jnp.clip(dx / 160.0, -1.0, 1.0)
    dy_norm = jnp.clip(dy / 144.0, -1.0, 1.0)

    # Sprite ID normalized to [0, 1] (40 sprites max)
    sprite_norm = jnp.clip(sprite_id / 40.0, 0.0, 1.0)

    # Age normalized to [0, 1] (255 frames max)
    age_norm = jnp.clip(age / 255.0, 0.0, 1.0)

    return jnp.array([luma, r, g, b, dx_norm, dy_norm, sprite_norm, age_norm], dtype=jnp.float32)


# Non-JIT version that returns Octonion object (for debugging)
def pixel_to_octonion(
    color_15bit: int,
    prev_color: Optional[int] = None,
    sprite_id: int = 0,
    age: int = 0,
    dx: float = 0.0,
    dy: float = 0.0
) -> Octonion:
    """Non-JIT version returning Octonion object."""
    arr = pixel_to_octonion_array(color_15bit, prev_color, sprite_id, age, dx, dy)
    return Octonion.from_array(arr)


# -----------------------------------------------------------------------
# Frame-level operations
# -----------------------------------------------------------------------

@jax.jit
def frame_to_octonion_field(
    frame: jnp.ndarray,  # shape (160, 144) of 15-bit colors
    prev_frame: Optional[jnp.ndarray] = None,
    sprite_map: Optional[jnp.ndarray] = None,  # shape (160, 144) of sprite IDs
    age_map: Optional[jnp.ndarray] = None,     # shape (160, 144) of ages
    motion_field: Optional[jnp.ndarray] = None  # shape (160, 144, 2) of (dx, dy)
) -> jnp.ndarray:
    """
    Convert an entire GBC frame to an octonion field.
    
    Returns:
        Array of shape (160, 144, 8) where last dim is octonion components.
    """
    h, w = frame.shape
    
    # Defaults
    if prev_frame is None:
        prev_frame = jnp.zeros_like(frame)
    if sprite_map is None:
        sprite_map = jnp.zeros((h, w), dtype=jnp.int32)
    if age_map is None:
        age_map = jnp.zeros((h, w), dtype=jnp.int32)
    if motion_field is None:
        motion_field = jnp.zeros((h, w, 2), dtype=jnp.float32)

    # Vectorized pixel processing using vmap
    def process_pixel(i, j):
        color = frame[i, j]
        prev = prev_frame[i, j]
        sprite = sprite_map[i, j]
        age = age_map[i, j]
        dx = motion_field[i, j, 0]
        dy = motion_field[i, j, 1]
        return pixel_to_octonion_array(color, prev, sprite, age, dx, dy)

    # Create index arrays
    i_idx, j_idx = jnp.meshgrid(jnp.arange(h), jnp.arange(w), indexing='ij')
    
    # Vectorized map over all pixels
    result = jax.vmap(lambda i, j: process_pixel(i, j), in_axes=(0, 0))(
        i_idx.ravel(), j_idx.ravel()
    )
    
    return result.reshape(h, w, 8)


# -----------------------------------------------------------------------
# Octonion → T' projection (via binding.py)
# -----------------------------------------------------------------------

def octonion_field_to_T7(oct_field: jnp.ndarray) -> jnp.ndarray:
    """
    Aggregate an octonion field (160×144×8) to a single T' state (7D complex).

    This is the crucial bridge between pixel space and the eigenspectral manifold.

    Steps:
    1. Flatten spatial dimensions → (23040, 8)
    2. Compute reference strength τ from luminance variance
    3. Extract two dominant color modes via SVD on RGB channels
    4. Compute observation bias from sprite/age distribution
    """
    # Flatten
    flat = oct_field.reshape(-1, 8)  # (23040, 8)

    # Extract components
    luma = flat[:, 0]          # real part
    rgb = flat[:, 1:4]          # i₁, i₂, i₃ (color)
    motion = flat[:, 4:6]       # i₄, i₅
    sprite = flat[:, 6]          # i₆
    age = flat[:, 7]             # i₇

    # τ: temporal anchor = 1 - variance of luminance
    # High variance means unstable frame → low τ
    tau = 1.0 - jnp.var(luma)

    # Φ: future coherence = product of top two singular values of RGB space
    # This captures the dominant color modes
    U, S, Vt = jnp.linalg.svd(rgb, full_matrices=False)
    # S has singular values (importance of each color mode)
    phi1 = S[0] / (jnp.sum(S) + 1e-8)
    phi2 = S[1] / (jnp.sum(S) + 1e-8)

    # Construct complex futures
    # φ₁ gets first singular vector (complex from U[0] + i·U[1])
    phi1_complex = jnp.complex64(U[0, 0] + 1j * U[1, 0]) if U.shape[0] > 1 else jnp.complex64(0.3 + 0.2j)
    phi2_complex = jnp.complex64(U[0, 1] + 1j * U[1, 1]) if U.shape[1] > 1 else jnp.complex64(0.2 + 0.3j)

    # ξ: observation bias = motion + sprite/age variance
    # Real part = mean dx, Imag part = mean dy
    xi_real = jnp.mean(motion[:, 0])
    xi_imag = jnp.mean(motion[:, 1])
    
    # Modulate by sprite/age activity
    sprite_var = jnp.var(sprite)
    age_var = jnp.var(age)
    activity = jnp.sqrt(sprite_var * age_var + 1e-8)
    xi_complex = jnp.complex64(xi_real * activity + 1j * xi_imag * activity)

    # Assemble 7D complex state
    psi = jnp.array([
        tau,
        phi1_complex.real, phi1_complex.imag,
        phi2_complex.real, phi2_complex.imag,
        xi_complex.real, xi_complex.imag
    ], dtype=jnp.complex64)

    return psi


# -----------------------------------------------------------------------
# JAX-optimized batch processing
# -----------------------------------------------------------------------

@jax.jit
def batch_frames_to_T7(
    frames: jnp.ndarray,           # (B, 160, 144) of 15-bit colors
    prev_frames: Optional[jnp.ndarray] = None
) -> jnp.ndarray:
    """
    Convert a batch of frames to T' states in parallel.
    Uses vmap for automatic vectorization.
    """
    if prev_frames is None:
        prev_frames = jnp.zeros_like(frames)

    def process_one(frame, prev):
        oct_field = frame_to_octonion_field(frame, prev)
        return octonion_field_to_T7(oct_field)

    return jax.vmap(process_one)(frames, prev_frames)


# -----------------------------------------------------------------------
# Testing / visualization helper
# -----------------------------------------------------------------------

def octonion_to_rgb(oct_arr: jnp.ndarray) -> Tuple[int, int, int]:
    """
    Convert an octonion array back to RGB for visualization.
    Useful for debugging the encoding/decoding cycle.
    
    Args:
        oct_arr: jnp.ndarray of shape (8,) with octonion components
    """
    # Clamp to [0, 1] then scale to 0-255
    r = int(jnp.clip(oct_arr[1], 0.0, 1.0) * 255)
    g = int(jnp.clip(oct_arr[2], 0.0, 1.0) * 255)
    b = int(jnp.clip(oct_arr[3], 0.0, 1.0) * 255)
    return r, g, b


if __name__ == "__main__":
    # Quick test
    print("🧪 Testing GBC Octonion Encoding")
    print("=" * 50)

    # Create a test pixel (grass green in GBC palette)
    # GBC green is often 0x03E0 (binary: 00000 11111 00000)
    test_color = 0x03E0  # 992 in decimal

    # Use non-JIT version for initial testing
    oct = pixel_to_octonion(test_color, sprite_id=5, age=42, dx=2.5, dy=-1.3)
    print(f"\nTest pixel encoding:")
    print(f"  Luminance: {oct.a:.3f}")
    print(f"  R: {oct.b:.3f}, G: {oct.c:.3f}, B: {oct.d:.3f}")
    print(f"  dx: {oct.e:.3f}, dy: {oct.f:.3f}")
    print(f"  sprite: {oct.g:.3f}, age: {oct.h:.3f}")

    # Test JIT version
    oct_arr = pixel_to_octonion_array(test_color, sprite_id=5, age=42, dx=2.5, dy=-1.3)
    print(f"\nJIT array version:")
    print(f"  {oct_arr}")

    # Test frame aggregation (tiny fake frame)
    fake_frame = jnp.full((4, 4), test_color, dtype=jnp.int32)
    fake_prev = jnp.zeros_like(fake_frame)

    oct_field = frame_to_octonion_field(fake_frame, fake_prev)
    print(f"\nOctonion field shape: {oct_field.shape}")
    
    psi = octonion_field_to_T7(oct_field)

    print(f"\nAggregated T' state:")
    print(f"  τ: {psi[0]:.3f}")
    print(f"  |φ₁|: {jnp.abs(psi[1] + 1j*psi[2]):.3f}")
    print(f"  |φ₂|: {jnp.abs(psi[3] + 1j*psi[4]):.3f}")
    print(f"  |ξ|: {jnp.abs(psi[5] + 1j*psi[6]):.3f}")

    print("\n✅ Octonion bridge ready for CUDA acceleration")