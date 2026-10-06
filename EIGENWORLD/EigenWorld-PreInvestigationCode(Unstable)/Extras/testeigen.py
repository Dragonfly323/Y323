# testeigen.py
"""Test the new eigenbasis dynamics without rendering."""

import numpy as np
import time
from genesis import create_island_world
from dynamics import WorldDynamics, DynamicsConfig

print("🌴 Creating island world...")
world = create_island_world()
print(f"   {world.cell_count} cells")

config = DynamicsConfig(
    emergence_threshold=0.3,      # fraction of top Gram eigenvalue
    influence_t=0.08,
    causal_t=0.03,
    max_births_per_step=12
)

dynamics = WorldDynamics(world, config)

print("\n⚡ Running 100 steps...")
start = time.perf_counter()
stats = dynamics.timestep(100)
elapsed = time.perf_counter() - start

print(f"\n✅ Complete in {elapsed*1000:.1f}ms")
print(f"   Steps: {stats['steps']}")
print(f"   Final cells: {stats['cells']}")
print(f"   Emergences: {stats['emergences']}")
print(f"   Steps/second: {100/elapsed:.1f}")