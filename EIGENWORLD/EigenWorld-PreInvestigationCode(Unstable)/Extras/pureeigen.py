# test_pure_math.py
import time
import numpy as np
from eigenbasis_dynamics import encode, evolve, nilpotent_reset, symmetric_diffusion, causal_diffusion, emergence_modes
from genesis import create_island_world
from dynamics import WorldDynamics, DynamicsConfig

world = create_island_world()
cells = world.all_cells()
states = np.array([c.resonance.state for c in cells], dtype=np.complex64)
basis = encode(states)

print(f"Testing pure math on {len(cells)} cells...")
t0 = time.perf_counter()
for _ in range(100):
    b = evolve(basis)
    b = nilpotent_reset(b)
    b = symmetric_diffusion(b, 0.08)
    b = causal_diffusion(b, 0.03)
    modes = emergence_modes(b, emergence_threshold=100.0)
t1 = time.perf_counter()

print(f"100 steps pure math: {(t1-t0)*1000:.2f}ms")
print(f"Per step: {(t1-t0)*10:.2f}ms")
print(f"Steps/second: {100/(t1-t0):.1f}")