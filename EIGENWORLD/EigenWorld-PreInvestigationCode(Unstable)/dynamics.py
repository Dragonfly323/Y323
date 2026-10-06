"""
dynamics.py — Five laws. Five matrix operations. 458 steps/second at N=1287.

One simulation step, five operations in eigenbasis ℂ⁴:

  basis   = evolve(basis)                   Law 1: Y evolution     O(4N)
  basis   = nilpotent_reset(basis)          Law 2: reset           O(56N) [every 3 steps]
  basis   = symmetric_diffusion(basis, t)   Law 3a: sym diffusion  O(8N)
  basis   = causal_diffusion(basis, t)      Law 3b: causal diffuse O(8N)
  cells  += births(emergence_modes(basis))  Law 4: eigenmode birth O(64) + O(8N)

All five are O(N) or O(N²→64) in the eigenbasis.
The octree is kept only for the renderer's spatial queries.
Gravity and pressure are kept as spatial/physical forces.
"""

import numpy as np
from typing import List, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from archetypes import get_archetypes
from resonance import Resonance
from cell import WorldCell
from octree import OctreeWorld
import jax_kernels as K
from eigenbasis_dynamics import (
    WorldBasis, EmergenceMode,
    encode, decode, decode_one,
    evolve, nilpotent_reset,
    symmetric_diffusion, causal_diffusion,
    emergence_modes, coherence_vs_archetype,
)
from spectral_clusters import partition_cells, SpectralPartition


@dataclass
class DynamicsConfig:
    emergence_threshold:      float = 0.3    # fraction of top Gram eigenvalue
    influence_t:              float = 0.08   # symmetric diffusion step size
    causal_t:                 float = 0.03   # causal diffusion step size
    evolve_cells:             bool  = True
    nilpotent_reset_every:    int   = 3
    new_cell_placement_noise: float = 0.15
    push_apart_strength:      float = 0.10
    cluster_every:            int   = 10
    n_clusters:               int   = 8
    stable_threshold:         float = 0.60
    max_births_per_step:      int   = 12


class WorldDynamics:
    """
    Laws of motion for the eigenspectral world.
    Hot path: five eigenbasis operations, no Python loops over cells or edges.
    """

    def __init__(self, world: OctreeWorld, config: Optional[DynamicsConfig] = None):
        self.world  = world
        self.config = config or DynamicsConfig()
        self.step   = 0
        self.emergence_count = 0
        self.reset_count     = 0
        self._last_partition: Optional[SpectralPartition] = None

        # Cache archetype states in eigenbasis (projected once, used every step)
        self._arch_cache: dict = {}
        K.warmup()

    # ── Public ───────────────────────────────────────────────────────────────

    def timestep(self, steps: int = 1) -> dict:
        stats: dict = defaultdict(int)
        for _ in range(steps):
            self._single_step()
            stats['steps']      += 1
            self.step           += 1
        stats['cells']      = self.world.cell_count
        stats['emergences'] = self.emergence_count
        stats['resets']     = self.reset_count
        return dict(stats)

    # ── Single step — five operations ────────────────────────────────────────

    def _single_step(self):
        cells = self.world.all_cells()
        if not cells:
            return

        # Extract (N,7) → encode to (N,4) eigenbasis
        states_7d = self._extract_states(cells)
        basis     = encode(states_7d)

        # ── Law 1: Y evolution — O(4N) elementwise ────────────────────────
        if self.config.evolve_cells:
            basis = evolve(basis)

        # ── Law 2: Nilpotent reset — O(56N), every 3 steps ───────────────
        if self.step % self.config.nilpotent_reset_every == 0:
            basis = nilpotent_reset(basis)
            self.reset_count += 1

        # ── Law 3a: Symmetric diffusion — O(8N) ───────────────────────────
        basis = symmetric_diffusion(basis, self.config.influence_t)

        # ── Law 3b: Causal diffusion — O(8N) ──────────────────────────────
        basis = causal_diffusion(basis, self.config.causal_t)

        # Write evolved states back to cells
        self._write_basis_back(cells, basis)

        # ── Law 4: Eigenmode births — O(64) + O(8N) ───────────────────────
        # Threshold is adaptive: fraction of the dominant Gram eigenvalue
        from eigenbasis_dynamics import gram_matrix
        G, _ = gram_matrix(basis)
        top_eigenval = float(np.linalg.eigvalsh(G).real[-1])
        threshold    = max(1.0, top_eigenval * self.config.emergence_threshold)

        modes     = emergence_modes(basis, emergence_threshold=threshold)
        new_cells = self._births_from_modes(cells, basis, modes)
        for nc in new_cells:
            self.world.add_cell(nc)

        # ── Spectral partition (background, every N steps) ────────────────
        if self.step % self.config.cluster_every == 0 and len(cells) >= 4:
            self._update_partition(basis, cells)

        # ── Physical forces (spatial, intentionally kept) ─────────────────
        # self._apply_gravity()
        # self._apply_pressure(cells, basis)

    # ── Law 4: Births ─────────────────────────────────────────────────────────

    def _births_from_modes(
        self,
        cells:  List[WorldCell],
        basis:  WorldBasis,
        modes:  List[EmergenceMode],
    ) -> List[WorldCell]:
        new_cells = []
        cap       = self.config.max_births_per_step

        for mode in modes[:cap]:
            nc = self._birth_from_mode(cells, basis, mode)
            if nc:
                new_cells.append(nc)
                self.emergence_count += 1

        return new_cells

    def _birth_from_mode(
        self,
        cells:  List[WorldCell],
        basis:  WorldBasis,
        mode:   EmergenceMode,
    ) -> Optional[WorldCell]:
        pos_mask = mode.cell_weights > 0.01
        if pos_mask.sum() < 2:
            return None

        # Position: participation-weighted centroid
        positions = np.array([cells[i].position
                               for i in range(len(cells)) if pos_mask[i]])
        weights   = mode.cell_weights[pos_mask]
        weights   = weights / weights.sum()
        centroid  = (weights[:, None] * positions).sum(axis=0)
        noise     = np.random.randn(3) * self.config.new_cell_placement_noise
        new_pos   = centroid + noise

        # OGC contact response: push participating cells slightly outward
        s = self.config.push_apart_strength * 0.4
        for idx, i in enumerate(np.where(pos_mask)[0]):
            p  = np.array(cells[i].position)
            d  = p - centroid
            dn = np.linalg.norm(d)
            if dn > 0.01:
                cells[i].position = tuple(p + d / dn * s * float(weights[idx]))

        # Reconstruct full ℂ⁷ state for the new cell
        state_7d = decode_one(mode.state_4d)

        return WorldCell(
            position   = tuple(new_pos.tolist()),
            resonance  = Resonance(state_7d.astype(complex)),
            parents    = [cells[i].uid for i in np.where(pos_mask)[0][:8].tolist()],
            birth_step = self.step,
        )

    # ── Spectral partition ────────────────────────────────────────────────────

    def _update_partition(self, basis: WorldBasis, cells: List[WorldCell]):
        try:
            states_7d = decode(basis)
            self._last_partition = partition_cells(
                states_7d,
                n_clusters       = self.config.n_clusters,
                stable_threshold = self.config.stable_threshold,
            )
        except Exception:
            pass

    @property
    def partition(self) -> Optional[SpectralPartition]:
        return self._last_partition

    # ── Physical forces ───────────────────────────────────────────────────────

    def _apply_gravity(self):
        cells = self.world.all_cells()
        cells.sort(key=lambda c: c.position[2])
        for cell in cells:
            if cell.position[2] <= self.world.root.bounds[4]:
                continue
            below = self.world.get_cell(
                cell.position[0], cell.position[1], cell.position[2] - 1.0)
            if below and cell.density > below.density:
                cell.position, below.position = below.position, cell.position

    def _apply_pressure(self, cells: List[WorldCell], basis: WorldBasis):
        from archetypes import get_archetypes
        lib = get_archetypes()

        # Use eigenbasis archetype coherence — O(4N) per archetype
        sand_7d  = lib.get('sand').point.to_array().astype(np.complex64)
        stone_7d = lib.get('sandstone').point.to_array().astype(np.complex64)
        coh_sand  = coherence_vs_archetype(basis, sand_7d)
        coh_stone = coherence_vs_archetype(basis, stone_7d)
        stone_pt  = lib.get('sandstone')

        for i, cell in enumerate(cells):
            if float(coh_sand[i]) < 0.55 or float(coh_stone[i]) > 0.75:
                continue
            pressure = self._pressure_at(cell)
            if pressure < 3.0:
                continue
            t = min(0.4, pressure / 10.0)
            cell.resonance = cell.resonance.perturb(stone_pt, t)

    def _pressure_at(self, cell: WorldCell) -> float:
        x, y, z = cell.position
        pressure = 0.0
        check_z  = z + 1.0
        while check_z < self.world.root.bounds[5]:
            above = self.world.get_cell(x, y, check_z)
            if above:
                pressure += above.density
            check_z += 1.0
        return pressure

    # ── State helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _extract_states(cells: List[WorldCell]) -> np.ndarray:
        out = np.empty((len(cells), 7), dtype=np.complex64)
        for i, cell in enumerate(cells):
            out[i] = cell.resonance.state.astype(np.complex64)
        return out

    @staticmethod
    def _write_basis_back(cells: List[WorldCell], basis: WorldBasis):
        states_7d = decode(basis)
        for i, cell in enumerate(cells):
            cell.resonance = Resonance(states_7d[i].astype(complex))
