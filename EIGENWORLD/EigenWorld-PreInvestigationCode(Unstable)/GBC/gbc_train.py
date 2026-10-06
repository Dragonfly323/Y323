# gbc_geometric.py
"""
Even more optimized: Workers just send raw frames, main process does JAX.
Includes standard geometric training and novelty-seeking variants.
"""

import jax
import jax.numpy as jnp
from jax import jit, vmap
import numpy as np
from pathlib import Path
import pickle
import time
import multiprocessing as mp
from functools import partial
from typing import Tuple, List, Optional
import struct

# Import our mathematical core
from y323operator import get_operator

# Optional: enable to see JIT compilation messages
# jax.config.update('jax_log_compiles', True)


# =======================================================================
# WORKER PROCESS FUNCTION (CPU ONLY, NO JAX)
# =======================================================================

def emulator_worker(rom_path: str, action_queue, frame_queue, worker_id: int):
    """
    Each emulator runs in its own process.
    NO JAX — just sends raw frames back to main process.
    """
    # Disable GPU for this process completely
    import os
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    
    # NO JAX IMPORTS HERE — just numpy and the emulator
    import numpy as np
    from gbc_pokemon_crystal import PokemonEnvironment
    import time
    
    print(f"Worker {worker_id} starting (CPU only, frame sender)")
    
    # Create environment
    env = PokemonEnvironment(rom_path, headless=True)
    
    while True:
        try:
            # Wait for command
            cmd = action_queue.get()
            
            if cmd == 'RESET':
                # Reset environment
                env.reset()
                frame = env._get_frame()
                
                # Send raw frame data back to main process
                if isinstance(frame, np.ndarray):
                    if frame.ndim == 3:
                        # Convert to grayscale in worker (simple)
                        gray = np.mean(frame, axis=2).astype(np.uint8)
                    else:
                        gray = frame.astype(np.uint8)
                else:
                    gray = np.array(frame).astype(np.uint8)
                
                frame_queue.put(('FRAME', worker_id, gray.tobytes()))
                
            elif isinstance(cmd, tuple) and cmd[0] == 'STEP':
                # Step with action
                action = cmd[1]
                env.step(action)
                
                # Get frame
                frame = env._get_frame()
                if isinstance(frame, np.ndarray):
                    if frame.ndim == 3:
                        gray = np.mean(frame, axis=2).astype(np.uint8)
                    else:
                        gray = frame.astype(np.uint8)
                else:
                    gray = np.array(frame).astype(np.uint8)
                
                frame_queue.put(('FRAME', worker_id, gray.tobytes()))
                
            elif cmd == 'STOP':
                print(f"Worker {worker_id} stopping")
                break
                
        except Exception as e:
            print(f"Worker {worker_id} error: {e}")
            break


# =======================================================================
# JAX-BASED FRAME PROCESSOR (MAIN PROCESS ONLY)
# =======================================================================

@jit
def process_frame_batch(frame_batch: jnp.ndarray) -> jnp.ndarray:
    """
    Convert a batch of grayscale frames to psi states.
    All JAX, all GPU.
    
    Args:
        frame_batch: (num_frames, 144, 160) uint8 array
    
    Returns:
        (num_frames, 7) complex64 psi states
    """
    from gbc_octonion import frame_to_octonion_field, octonion_field_to_T7
    
    def frame_to_psi(frame):
        oct_field = frame_to_octonion_field(frame)
        return octonion_field_to_T7(oct_field)
    
    return vmap(frame_to_psi)(frame_batch)


class ParallelGeometricEnvironment:
    """
    Manages multiple emulators — workers send raw frames, main process does JAX.
    """
    
    def __init__(self, rom_path: str, num_envs: int = 32):
        self.num_envs = num_envs
        self.rom_path = rom_path
        
        print(f"Launching {num_envs} parallel frame-sending processes...")
        
        # Create queues
        self.action_queues = []
        self.frame_queue = mp.Queue(maxsize=1000)
        self.processes = []
        
        for i in range(num_envs):
            action_queue = mp.Queue()
            self.action_queues.append(action_queue)
            
            p = mp.Process(
                target=emulator_worker,
                args=(rom_path, action_queue, self.frame_queue, i)
            )
            p.daemon = True
            p.start()
            self.processes.append(p)
        
        # Pre-allocate frame buffer
        self.frame_buffer = np.zeros((num_envs, 144, 160), dtype=np.uint8)
        
        # Get Y operator
        self.Y = get_operator()._Y
        
        # Warm up JIT
        print("Warming up JAX compilation...")
        dummy_frames = jnp.zeros((1, 144, 160), dtype=jnp.uint8)
        _ = process_frame_batch(dummy_frames)
        print(f"✅ {num_envs} processes ready, JAX warm")
    
    def reset_all_psi(self) -> jnp.ndarray:
        """Reset all environments, return psi states."""
        # Send reset commands
        for q in self.action_queues:
            q.put('RESET')
        
        # Collect frames
        received = 0
        while received < self.num_envs:
            msg = self.frame_queue.get()
            if msg[0] == 'FRAME':
                _, worker_id, frame_bytes = msg
                frame = np.frombuffer(frame_bytes, dtype=np.uint8).reshape(144, 160)
                self.frame_buffer[worker_id] = frame
                received += 1
        
        # Process all frames at once on GPU
        frame_batch = jnp.array(self.frame_buffer)
        psi_batch = process_frame_batch(frame_batch)
        
        return psi_batch
    
    def step_all_psi(self, actions: jnp.ndarray) -> jnp.ndarray:
        """
        Step all environments, return next psi states.
        Actions: (num_envs,) integer actions
        """
        # Send step commands
        for i, q in enumerate(self.action_queues):
            q.put(('STEP', int(actions[i])))
        
        # Collect frames
        received = 0
        while received < self.num_envs:
            msg = self.frame_queue.get()
            if msg[0] == 'FRAME':
                _, worker_id, frame_bytes = msg
                frame = np.frombuffer(frame_bytes, dtype=np.uint8).reshape(144, 160)
                self.frame_buffer[worker_id] = frame
                received += 1
        
        # Process all frames at once on GPU
        frame_batch = jnp.array(self.frame_buffer)
        psi_batch = process_frame_batch(frame_batch)
        
        return psi_batch
    
    def cleanup(self):
        """Stop all processes."""
        for q in self.action_queues:
            q.put('STOP')
        for p in self.processes:
            p.join(timeout=1.0)


# =======================================================================
# OPTIMIZED EVOLUTION FUNCTIONS (Pre-compiled, no recompilation)
# =======================================================================

@jit
def evolve_one_step(psi_batch: jnp.ndarray, Y: jnp.ndarray) -> jnp.ndarray:
    """Apply Y once to entire batch. Pre-compiled, constant step count."""
    return vmap(lambda psi: Y @ psi)(psi_batch)

@jit
def evolve_three_steps(psi_batch: jnp.ndarray, Y: jnp.ndarray) -> jnp.ndarray:
    """Apply Y three times (nilpotent cascade). Pre-compiled, constant step count."""
    psi = vmap(lambda psi: Y @ psi)(psi_batch)
    psi = vmap(lambda psi: Y @ psi)(psi)
    psi = vmap(lambda psi: Y @ psi)(psi)
    return psi

# =======================================================================
# GEOMETRIC NOVELTY — No Python loops, just manifold density
# =======================================================================

class JaxGeometricNovelty:
    """
    GPU-accelerated novelty using JAX for nearest neighbors.
    """
    
    def __init__(self, dim: int = 14, memory_size: int = 10000):  # 14 = 7 real + 7 imag
        self.dim = dim
        self.memory_size = memory_size
        
        # Archive on GPU
        self.archive = jnp.zeros((memory_size, dim), dtype=jnp.float32)
        self.archive_idx = 0
        self.archive_count = 0
    
    def add_points(self, points: np.ndarray):
        """Add points to archive (numpy array)."""
        batch_size = points.shape[0]
        p_jax = jnp.array(points, dtype=jnp.float32)
        
        if self.archive_count + batch_size <= self.memory_size:
            # Still filling
            self.archive = self.archive.at[self.archive_count:self.archive_count+batch_size].set(p_jax)
            self.archive_count += batch_size
        else:
            # Overwrite oldest
            indices = (jnp.arange(batch_size) + self.archive_idx) % self.memory_size
            self.archive = self.archive.at[indices].set(p_jax)
            self.archive_idx = (self.archive_idx + batch_size) % self.memory_size
            self.archive_count = self.memory_size
    
    @partial(jit, static_argnums=(0, 2))
    def novelty(self, points: jnp.ndarray, k: int = 50) -> jnp.ndarray:
        """
        Compute novelty using brute-force nearest neighbors on GPU.
        """
        # Use only valid entries
        if self.archive_count < self.memory_size:
            archive = self.archive[:self.archive_count]
        else:
            archive = self.archive
        
        # Compute all pairwise distances
        points_sq = jnp.sum(points**2, axis=1, keepdims=True)
        archive_sq = jnp.sum(archive**2, axis=1, keepdims=True).T
        cross = jnp.dot(points, archive.T)
        distances_sq = points_sq + archive_sq - 2 * cross
        
        # Get k smallest distances
        k = min(k, archive.shape[0])
        top_k = jnp.sort(distances_sq, axis=1)[:, :k]
        
        # Mean distance to k neighbors
        mean_dist = jnp.sqrt(jnp.mean(top_k, axis=1))
        
        # Novelty score (0 = familiar, 1 = novel)
        novelty = 1.0 - jnp.exp(-mean_dist)
        
        return novelty


# =======================================================================
# GEOMETRIC REWARD FUNCTIONS (GPU)
# =======================================================================

@jit
def geometric_intrinsic_reward(psi_before: jnp.ndarray, psi_after: jnp.ndarray) -> float:
    """Pure geometric reward based on manifold properties."""
    # Information content
    def info(psi):
        mags = jnp.abs(psi)
        probs = mags / (jnp.sum(mags) + 1e-8)
        return -jnp.sum(probs * jnp.log(probs + 1e-8))
    
    I_before = info(psi_before)
    I_after = info(psi_after)
    
    # Coherence between futures
    phi1 = psi_after[1] + 1j*psi_after[2]
    phi2 = psi_after[3] + 1j*psi_after[4]
    coh = jnp.abs(jnp.vdot(phi1, phi2))**2
    
    # Diversity
    diversity = 1.0 - jnp.max(jnp.abs(psi_after) / (jnp.linalg.norm(psi_after) + 1e-8))
    
    # Movement
    movement = jnp.linalg.norm(psi_after - psi_before)
    
    return (I_after - I_before) * 10.0 + coh * 2.0 + diversity * 5.0 + movement * 1.0


@jit
def batch_geometric_reward(psi_before: jnp.ndarray, psi_after: jnp.ndarray) -> jnp.ndarray:
    """Batch reward computation on GPU."""
    return vmap(geometric_intrinsic_reward)(psi_before, psi_after)


# =======================================================================
# GEOMETRIC AGENT (GPU)
# =======================================================================

class GeometricAgent:
    """Agents live entirely on GPU."""
    
    def __init__(self, num_agents: int = 32):
        self.num_agents = num_agents
        
        key = jax.random.PRNGKey(int(time.time()))
        
        # Random complex states
        real_parts = jax.random.normal(key, (num_agents, 7))
        imag_parts = jax.random.normal(key, (num_agents, 7))
        self.psi_states = real_parts + 1j * imag_parts
        self.psi_states = self.psi_states / jnp.linalg.norm(
            self.psi_states, axis=1, keepdims=True
        )
        
        # Policy tensors
        self.policy_tensors = jax.random.normal(key, (num_agents, 7, 8)) * 0.1
        
        # Fitness
        self.fitness = jnp.zeros(num_agents)
        
        # Get Y operator
        self.Y = get_operator()._Y
    
    @partial(jit, static_argnums=(0,))
    def act_batch(self, psi_batch: jnp.ndarray) -> jnp.ndarray:
        """Actions from geometry."""
        action_logits = jnp.einsum('ij,ijk->ik', psi_batch.real, self.policy_tensors)
        return jnp.argmax(action_logits, axis=-1)
    
    def update_fitness(self, rewards: jnp.ndarray):
        self.fitness += rewards
    
    def get_stats(self) -> Tuple[float, float, float]:
        best = float(jnp.max(self.fitness))
        avg = float(jnp.mean(self.fitness))
        std = float(jnp.std(self.fitness))
        return best, avg, std


# =======================================================================
# GEOMETRIC TRAINER (Standard)
# =======================================================================

class GeometricTrainer:
    """Pure geometric exploration with frame-sending workers."""
    
    def __init__(
        self,
        rom_path: str,
        num_agents: int = 32,
        steps_per_episode: int = 5000
    ):
        self.num_agents = num_agents
        self.steps_per_episode = steps_per_episode
        
        # Parallel environments (CPU processes, send frames)
        self.env = ParallelGeometricEnvironment(rom_path, num_agents)
        
        # GPU agents
        self.agents = GeometricAgent(num_agents)
        
        # Get Y operator
        self.Y = get_operator()._Y
        
        # Tracking
        self.generation = 0
        self.history = []
        self.step_count = 0
    
    def run_geometric_episode(self):
        """One episode of pure geometric exploration."""
        print(f"\n🌀 Generation {self.generation} — Geometric Exploration")
        
        # Reset all environments, get initial psi states
        psi_states = self.env.reset_all_psi()
        self.agents.psi_states = psi_states
        
        episode_rewards = jnp.zeros(self.num_agents)
        start_time = time.time()
        last_report = start_time
        
        for step in range(self.steps_per_episode):
            # Get actions from GPU
            actions = self.agents.act_batch(psi_states)
            
            # Step environments, get next psi states
            next_psi = self.env.step_all_psi(actions)
            
            # OPTIMIZED: Use pre-compiled evolution functions
            next_psi = evolve_one_step(next_psi, self.Y)
            
            # Nilpotent reset every 3 steps
            if step % 3 == 2:
                next_psi = evolve_three_steps(next_psi, self.Y)
            
            # Compute rewards
            rewards = batch_geometric_reward(psi_states, next_psi)
            episode_rewards += rewards
            
            # Update state
            psi_states = next_psi
            self.step_count += 1
            
            # Progress
            now = time.time()
            if now - last_report > 2.0:
                elapsed = now - start_time
                steps_per_sec = (step + 1) * self.num_agents / elapsed
                print(f"   Step {step:4d}: {steps_per_sec:6.0f} steps/sec, "
                      f"reward: {float(jnp.mean(episode_rewards)):6.2f}", end='\r')
                last_report = now
        
        # Update fitness
        self.agents.update_fitness(episode_rewards)
        
        # Stats
        best, avg, std = self.agents.get_stats()
        elapsed = time.time() - start_time
        steps_per_sec = self.steps_per_episode * self.num_agents / elapsed
        
        print(f"\n   ✅ Episode complete in {elapsed:.1f}s ({steps_per_sec:.0f} steps/sec)")
        print(f"   ⭐ Best: {best:.2f} | Avg: {avg:.2f} | Std: {std:.2f}")
        
        self.history.append((self.generation, best, avg))
        return best
    
    def evolve_population(self, mutation_rate: float = 0.1):
        """Create next generation via mutation."""
        indices = jnp.argsort(self.agents.fitness)[::-1]
        num_elite = max(1, self.num_agents // 5)
        elite_indices = indices[:num_elite]
        
        key = jax.random.PRNGKey(self.generation + 42)
        new_policies = []
        
        # Keep elites
        for idx in elite_indices:
            new_policies.append(self.agents.policy_tensors[idx])
        
        # Fill with mutants
        while len(new_policies) < self.num_agents:
            parent_idx = elite_indices[len(new_policies) % num_elite]
            noise = jax.random.normal(key, (7, 8)) * mutation_rate
            key = jax.random.split(key)[0]
            new_policies.append(self.agents.policy_tensors[parent_idx] + noise)
        
        self.agents.policy_tensors = jnp.stack(new_policies)
        self.agents.fitness = jnp.zeros(self.num_agents)
        self.generation += 1
    
    def train(self, num_generations: int = 20):
        """Main loop."""
        print("\n" + "=" * 70)
        print("🌀 GEOMETRIC TRAINING — Frame-Sending Parallel Workers")
        print(f"   {self.num_agents} agents in {self.num_agents} parallel processes")
        print(f"   Each episode: {self.steps_per_episode} steps")
        print("=" * 70)
        
        try:
            for gen in range(num_generations):
                self.run_geometric_episode()
                self.evolve_population(mutation_rate=0.1 * (0.95 ** gen))
        finally:
            self.env.cleanup()
        
        return self.agents


# =======================================================================
# NOVELTY-SEEKING TRAINER (extends GeometricTrainer)
# =======================================================================

class NoveltyGeometricTrainer(GeometricTrainer):
    """
    Novelty seeking via pure geometry — no Python loops.
    """
    
    def __init__(
        self,
        rom_path: str,
        num_agents: int = 32,
        steps_per_episode: int = 5000,
        novelty_weight: float = 1.0,
        archive_size: int = 10000,
    ):
        # Call parent init
        super().__init__(rom_path, num_agents, steps_per_episode)
        
        # Same agent type (no memory needed)
        self.agents = GeometricAgent(num_agents)
        self.novelty_weight = novelty_weight
        
        # Geometric novelty system (14D = 7 real + 7 imag)
        self.novelty = JaxGeometricNovelty(dim=14, memory_size=archive_size)
    
    def psi_to_vector(self, psi: jnp.ndarray) -> jnp.ndarray:
        """Convert complex psi to real vector for geometry."""
        return jnp.concatenate([psi.real, psi.imag])
    
    def run_geometric_episode(self):
        """One episode of geometric novelty seeking."""
        print(f"\n🌀 Generation {self.generation} — Geometric Novelty")
        
        # Reset all environments
        psi_states = self.env.reset_all_psi()
        self.agents.psi_states = psi_states
        
        # Convert to real vectors for geometry
        state_vectors = jnp.array([self.psi_to_vector(psi) for psi in psi_states])
        
        # Add to archive (first states)
        self.novelty.add_points(np.array(state_vectors))
        
        episode_rewards = jnp.zeros(self.num_agents)
        start_time = time.time()
        last_report = start_time
        
        for step in range(self.steps_per_episode):
            # Get actions
            actions = self.agents.act_batch(psi_states)
            
            # Step environments
            next_psi = self.env.step_all_psi(actions)
            
            # Evolve
            next_psi = evolve_one_step(next_psi, self.Y)
            if step % 3 == 2:
                next_psi = evolve_three_steps(next_psi, self.Y)
            
            # Convert to real vectors
            next_vectors = jnp.array([self.psi_to_vector(psi) for psi in next_psi])
            
            # Compute novelty in batch on GPU
            novelty_scores = self.novelty.novelty(next_vectors)
            
            # Movement reward
            movement = jnp.linalg.norm(
                (next_psi - psi_states).real, axis=1
            ) + jnp.linalg.norm(
                (next_psi - psi_states).imag, axis=1
            )
            
            # Combined reward (all vectorized, no Python loop)
            rewards = self.novelty_weight * novelty_scores + movement * 0.1
            episode_rewards += rewards
            
            # Add to archive (periodically)
            if step % 10 == 0:
                self.novelty.add_points(np.array(next_vectors))
            
            # Simple frame grabber
            if step % 100 == 0:  # or whenever you want
                # Save first agent's current frame
                frame_data = self.env.frame_buffer[0]  # first agent
                import matplotlib.pyplot as plt
                plt.imsave(f"frame_gen{self.generation}_step{step}.png", frame_data, cmap='gray')
                print(f"📸 Captured frame_{self.generation}_{step}.png")

            # Update state
            psi_states = next_psi
            self.step_count += 1
            
            # Progress
            now = time.time()
            if now - last_report > 2.0:
                elapsed = now - start_time
                steps_per_sec = (step + 1) * self.num_agents / elapsed
                avg_reward = float(jnp.mean(episode_rewards))
                avg_novelty = float(jnp.mean(novelty_scores))
                print(f"   Step {step:4d}: {steps_per_sec:6.0f} steps/sec, "
                      f"novelty: {avg_novelty:.3f}, reward: {avg_reward:6.2f}", end='\r')
                last_report = now
        
        # Update fitness
        self.agents.update_fitness(episode_rewards)
        
        # Stats
        best, avg, std = self.agents.get_stats()
        elapsed = time.time() - start_time
        steps_per_sec = self.steps_per_episode * self.num_agents / elapsed
        
        print(f"\n   ✅ Episode complete in {elapsed:.1f}s ({steps_per_sec:.0f} steps/sec)")
        print(f"   ⭐ Best: {best:.2f} | Avg: {avg:.2f} | Std: {std:.2f}")
        print(f"   📊 Archive size: {self.novelty.archive_count}")
        
        self.history.append((self.generation, best, avg))
        return best
    
    # evolve_population and train are inherited from GeometricTrainer


# =======================================================================
# MAIN — Interactive selection
# =======================================================================

if __name__ == "__main__":
    import sys
    
    print("🌀 NOVELTY-SEEKING GEOMETRIC AGENT")
    print("=" * 60)
    print("1. Standard geometric training")
    print("2. Novelty-seeking training")
    print("=" * 60)
    
    choice = input("Choose (1/2): ").strip()
    
    rom_path = Path("roms/pokemon_crystal.gbc")
    if not rom_path.exists():
        print(f"❌ ROM not found at {rom_path}")
        exit(1)
    
    if choice == "2":
        trainer = NoveltyGeometricTrainer(
            rom_path=str(rom_path),
            num_agents=16,
            steps_per_episode=2000,
            novelty_weight=1.0
        )
    else:
        trainer = GeometricTrainer(
            rom_path=str(rom_path),
            num_agents=16,
            steps_per_episode=2000
        )
    
    trainer.train(num_generations=3)
    
    print("\n✅ Exploration complete!")