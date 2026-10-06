# main.py
"""
Simple entry point: run the simulation for N steps.
No rendering, no visualization — just the mathematics.
"""

import argparse
import time

from genesis import create_island_world
from dynamics import WorldDynamics, DynamicsConfig


def main():
    parser = argparse.ArgumentParser(description='Eigenspectral world simulation')
    parser.add_argument('--steps', type=int, default=100,
                       help='Number of steps to run')
    parser.add_argument('--seed', type=int, default=None,
                       help='Random seed')
    parser.add_argument('--threshold', type=float, default=0.92,
                       help='Emergence coherence threshold')
    args = parser.parse_args()

    print("=" * 60)
    print("EIGENSPECTRAL WORLD SIMULATION")
    print("=" * 60)

    # Create world
    print(f"\nCreating island world (seed={args.seed})...")
    world = create_island_world(seed=args.seed)
    print(f"Initial cell count: {world.cell_count}")

    # Configure dynamics
    config = DynamicsConfig(emergence_threshold=args.threshold)
    dynamics = WorldDynamics(world, config)

    # Run simulation
    print(f"\nRunning {args.steps} steps...")
    start = time.time()

    stats = dynamics.timestep(args.steps)

    elapsed = time.time() - start

    print("\n" + "=" * 60)
    print("SIMULATION COMPLETE")
    print("=" * 60)
    print(f"Steps:          {stats['steps']}")
    print(f"Final cells:    {stats['cells']}")
    print(f"Emergences:     {stats['emergences']}")
    print(f"Nilpotent resets: {stats['resets']}")
    print(f"Time elapsed:   {elapsed:.2f}s")
    print(f"Steps/second:   {args.steps / elapsed:.1f}")
    print("=" * 60)


if __name__ == "__main__":
    main()