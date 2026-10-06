"""
genesis.py - Initial spatial configuration of the world.

Cell placement is a purely artistic/physical decision layered on top of the
mathematics. The math does not know what an island is. We decide:
  - which archetype goes where in 3D space
  - the density and shape of the initial arrangement
  - the spherical birth boundary

None of this touches the mathematical files.
"""

import numpy as np
from typing import Tuple, Optional
import random

from archetypes import get_archetypes, SAND, WATER, AIR, ROCK, FIRE
from resonance import Resonance
from geometry import ManifoldPoint, RawState
from cell import WorldCell
from octree import OctreeWorld


# ============================================================================
# WORLD PARAMETERS
# ============================================================================

WORLD_RADIUS = 12.0
WORLD_BOUNDS = (-WORLD_RADIUS, WORLD_RADIUS,
                -WORLD_RADIUS, WORLD_RADIUS,
                -WORLD_RADIUS, WORLD_RADIUS)

ISLAND_RADIUS  = 4.5
ISLAND_HEIGHT  = 2.2
ISLAND_SIGMA   = 2.0

WATER_Z        = -0.3
WATER_DEPTH_Z  = -1.2
WATER_OUTER    = WORLD_RADIUS * 0.85

CELL_SPACING   = 0.8


# ============================================================================
# FACTORY
# ============================================================================

def create_cell_from_archetype(
    archetype_name: str,
    position: Tuple[float, float, float],
    variation: float = 0.05,
    seed: int = 0
) -> WorldCell:
    lib = get_archetypes()
    archetype = lib.get(archetype_name)

    if variation <= 0:
        # Pure archetype — get its 7D point and convert to complex state
        state = archetype.point.to_array().astype(complex)
        return WorldCell(position, Resonance(state), archetype=archetype_name)

    # Add variation
    raw = archetype.point.to_raw()
    rng = np.random.RandomState(seed)

    state = np.array([
        raw.tau       + rng.normal(0, variation),
        raw.phi1.real + rng.normal(0, variation),
        raw.phi1.imag + rng.normal(0, variation),
        raw.phi2.real + rng.normal(0, variation),
        raw.phi2.imag + rng.normal(0, variation),
        raw.xi.real   + rng.normal(0, variation),
        raw.xi.imag   + rng.normal(0, variation),
    ], dtype=complex)

    return WorldCell(position, Resonance(state), archetype=archetype_name)


def _in_sphere(x, y, z, r=WORLD_RADIUS):
    return x*x + y*y + z*z <= r*r


def _island_height(x, y):
    """Gaussian height profile with subtle noise. Returns None outside island."""
    r = np.sqrt(x*x + y*y)
    if r > ISLAND_RADIUS:
        return None
    h = ISLAND_HEIGHT * np.exp(-(r**2) / (2 * ISLAND_SIGMA**2))
    noise = 0.12 * np.sin(x * 1.3) * np.cos(y * 1.1) + 0.08 * np.cos(x * 2.1 + y)
    return h + noise


# ============================================================================
# ISLAND SCENE
# ============================================================================

def create_island_world() -> OctreeWorld:
    """
    Island scene:
      - Sand disc with gaussian height profile
      - Rock outcroppings near island edge
      - Shallow + deep water surrounding island
      - Air hemisphere above
      - Hexagonal grid packing at CELL_SPACING
      - Spherical birth constraint radius WORLD_RADIUS
    """
    world = OctreeWorld(initial_bounds=WORLD_BOUNDS)
    rng = np.random.RandomState(42)
    counts = {k: 0 for k in ['sand', 'rock', 'water', 'air']}

    s = CELL_SPACING
    xs = np.arange(-WATER_OUTER, WATER_OUTER + s, s)
    ys = np.arange(-WATER_OUTER, WATER_OUTER + s * np.sqrt(3)/2, s * np.sqrt(3)/2)

    for row_idx, y in enumerate(ys):
        x_offset = (s / 2) if row_idx % 2 else 0.0
        for x in xs + x_offset:
            r_xy = np.sqrt(x*x + y*y)
            if r_xy > WATER_OUTER:
                continue

            h = _island_height(x, y)

            if h is not None:
                for dz in [0.0, -s * 0.6]:
                    z = h + dz
                    if not _in_sphere(x, y, z):
                        continue
                    seed = int(abs(x * 1000 + y * 100 + dz * 10)) % 99991
                    edge_factor = max(0, (r_xy - 3.0) / 1.5)
                    is_rock = (edge_factor > 0.4 and
                               rng.random() < edge_factor * 0.5 and
                               dz == 0.0)
                    arch = 'rock' if is_rock else 'sand'
                    var  = 0.02   if is_rock else 0.04
                    cell = create_cell_from_archetype(arch, (x, y, z), variation=var, seed=seed)
                    cell.birth_step = 0
                    world.add_cell(cell)
                    counts[arch] += 1
            else:
                z_surf = WATER_Z + 0.1 * rng.normal()
                if _in_sphere(x, y, z_surf):
                    seed = int(abs(x * 1000 + y * 100)) % 99991
                    cell = create_cell_from_archetype('water', (x, y, z_surf),
                                                      variation=0.06, seed=seed)
                    cell.birth_step = 0
                    world.add_cell(cell)
                    counts['water'] += 1

                if rng.random() < 0.5:
                    z_deep = WATER_DEPTH_Z + 0.15 * rng.normal()
                    if _in_sphere(x, y, z_deep):
                        seed = int(abs(x * 997 + y * 101 + 1)) % 99991
                        cell = create_cell_from_archetype('water', (x, y, z_deep),
                                                          variation=0.10, seed=seed)
                        cell.birth_step = 0
                        world.add_cell(cell)
                        counts['water'] += 1

    # Air hemisphere
    air_spacing = s * 1.6
    for z in np.arange(ISLAND_HEIGHT + 0.6, WORLD_RADIUS * 0.72, air_spacing):
        r_max_at_z = np.sqrt(max(0, (WORLD_RADIUS * 0.7)**2 - z*z))
        axs = np.arange(-r_max_at_z, r_max_at_z + air_spacing, air_spacing)
        for row_i, ay in enumerate(axs):
            ax_offset = (air_spacing / 2) if row_i % 2 else 0.0
            for ax in axs + ax_offset:
                if ax*ax + ay*ay > r_max_at_z**2:
                    continue
                if not _in_sphere(ax, ay, z):
                    continue
                seed = int(abs(ax * 997 + ay * 101 + z * 13)) % 99991
                cell = create_cell_from_archetype('air', (ax, ay, z),
                                                  variation=0.15, seed=seed)
                cell.birth_step = 0
                world.add_cell(cell)
                counts['air'] += 1

    total = sum(counts.values())
    print(f"Island world: {total} cells")
    for k, v in counts.items():
        print(f"  {k:8s}: {v}")
    return world


def create_classical_world() -> OctreeWorld:
    world = OctreeWorld(initial_bounds=(-8, 8, -8, 8, -5, 5))
    for x in range(-3, 4):
        for y in range(-3, 4):
            if np.sqrt(x*x + y*y) < 3:
                cell = create_cell_from_archetype('sand', (float(x), float(y), 0.0),
                                                  variation=0.05,
                                                  seed=hash((x, y, 0)) % 10000)
                cell.birth_step = 0
                world.add_cell(cell)
    for x in range(-4, 5):
        for y in range(-4, 5):
            if world.get_cell(float(x), float(y), 0) is None:
                cell = create_cell_from_archetype('water', (float(x), float(y), 0.0),
                                                  variation=0.1,
                                                  seed=hash((x, y, 1)) % 10000)
                cell.birth_step = 0
                world.add_cell(cell)
    for x in range(-4, 5):
        for y in range(-4, 5):
            cell = create_cell_from_archetype('air', (float(x), float(y), 1.0),
                                              variation=0.2,
                                              seed=hash((x, y, 2)) % 10000)
            cell.birth_step = 0
            world.add_cell(cell)
    print(f"Classical world: {world.cell_count} cells")
    return world


def create_seed_world(seed_type='sand', position=(0, 0, 0)):
    world = OctreeWorld(initial_bounds=WORLD_BOUNDS)
    cell = create_cell_from_archetype(seed_type, position, variation=0.02, seed=42)
    cell.birth_step = 0
    world.add_cell(cell)
    return world


if __name__ == "__main__":
    w = create_island_world()
