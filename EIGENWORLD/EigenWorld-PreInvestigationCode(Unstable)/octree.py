# octree.py
"""
OctreeWorld: a sparse spatial index for the simulation.

Space itself is not a grid — it's a record of where things are.
The octree expands gracefully as new matter emerges.
"""

import numpy as np
from typing import Optional, List, Tuple, Generator
import uuid


class OctreeNode:
    """
    A node in the octree — a cubic region of space that either:
    - Contains a single cell (leaf), or
    - Has eight children (branch), each covering a sub-octant
    """

    def __init__(self,
                 bounds: Tuple[float, float, float, float, float, float],
                 depth: int = 0,
                 max_depth: int = 16):
        self.bounds = bounds
        self.depth = depth
        self.max_depth = max_depth
        self.cell = None
        self.children = None
        self.id = str(uuid.uuid4())[:4]

    @property
    def center(self) -> Tuple[float, float, float]:
        min_x, max_x, min_y, max_y, min_z, max_z = self.bounds
        return ((min_x + max_x) / 2,
                (min_y + max_y) / 2,
                (min_z + max_z) / 2)

    @property
    def size(self) -> float:
        return self.bounds[1] - self.bounds[0]

    def contains(self, x: float, y: float, z: float) -> bool:
        min_x, max_x, min_y, max_y, min_z, max_z = self.bounds
        return (min_x <= x < max_x and
                min_y <= y < max_y and
                min_z <= z < max_z)

    def intersects(self, other_bounds) -> bool:
        min1, max1, min2, max2, min3, max3 = self.bounds
        omin1, omax1, omin2, omax2, omin3, omax3 = other_bounds
        return not (max1 <= omin1 or min1 >= omax1 or
                    max2 <= omin2 or min2 >= omax2 or
                    max3 <= omin3 or min3 >= omax3)

    def _subdivide(self):
        if self.depth >= self.max_depth:
            return

        min_x, max_x, min_y, max_y, min_z, max_z = self.bounds
        mid_x = (min_x + max_x) / 2
        mid_y = (min_y + max_y) / 2
        mid_z = (min_z + max_z) / 2

        self.children = [
            OctreeNode((min_x, mid_x, min_y, mid_y, min_z, mid_z), self.depth + 1, self.max_depth),
            OctreeNode((mid_x, max_x, min_y, mid_y, min_z, mid_z), self.depth + 1, self.max_depth),
            OctreeNode((min_x, mid_x, mid_y, max_y, min_z, mid_z), self.depth + 1, self.max_depth),
            OctreeNode((mid_x, max_x, mid_y, max_y, min_z, mid_z), self.depth + 1, self.max_depth),
            OctreeNode((min_x, mid_x, min_y, mid_y, mid_z, max_z), self.depth + 1, self.max_depth),
            OctreeNode((mid_x, max_x, min_y, mid_y, mid_z, max_z), self.depth + 1, self.max_depth),
            OctreeNode((min_x, mid_x, mid_y, max_y, mid_z, max_z), self.depth + 1, self.max_depth),
            OctreeNode((mid_x, max_x, mid_y, max_y, mid_z, max_z), self.depth + 1, self.max_depth),
        ]

        if self.cell is not None:
            cell = self.cell
            self.cell = None
            self.insert_cell(cell)

    def insert_cell(self, cell) -> bool:
        x, y, z = cell.position
        if not self.contains(x, y, z):
            return False

        if self.children is None and self.cell is None:
            self.cell = cell
            return True

        if self.children is None and self.cell is not None:
            if self.depth < self.max_depth and self.cell.position != (x, y, z):
                self._subdivide()
            else:
                self.cell = cell
                return True

        if self.children is not None:
            for child in self.children:
                if child.insert_cell(cell):
                    return True
        return False

    def remove_cell(self, x: float, y: float, z: float):
        if not self.contains(x, y, z):
            return None

        if self.cell is not None and self.cell.position == (x, y, z):
            cell = self.cell
            self.cell = None
            return cell

        if self.children is not None:
            for child in self.children:
                cell = child.remove_cell(x, y, z)
                if cell is not None:
                    return cell
        return None

    def get_cell(self, x: float, y: float, z: float):
        if not self.contains(x, y, z):
            return None

        if self.cell is not None and self.cell.position == (x, y, z):
            return self.cell

        if self.children is not None:
            for child in self.children:
                cell = child.get_cell(x, y, z)
                if cell is not None:
                    return cell
        return None

    def get_cells_in_sphere(self, center: Tuple[float, float, float], radius: float):
        cx, cy, cz = center
        radius_sq = radius * radius

        sphere_bounds = (cx - radius, cx + radius,
                         cy - radius, cy + radius,
                         cz - radius, cz + radius)

        if not self.intersects(sphere_bounds):
            return []

        cells = []
        if self.cell is not None:
            px, py, pz = self.cell.position
            if (px - cx)**2 + (py - cy)**2 + (pz - cz)**2 <= radius_sq:
                cells.append(self.cell)

        if self.children is not None:
            for child in self.children:
                cells.extend(child.get_cells_in_sphere(center, radius))
        return cells

    def expand_to_include(self, x: float, y: float, z: float):
        min_x, max_x, min_y, max_y, min_z, max_z = self.bounds

        new_min_x = min_x
        new_max_x = max_x
        new_min_y = min_y
        new_max_y = max_y
        new_min_z = min_z
        new_max_z = max_z

        if x < min_x:
            new_min_x = min_x - (max_x - min_x)
        elif x >= max_x:
            new_max_x = max_x + (max_x - min_x)

        if y < min_y:
            new_min_y = min_y - (max_y - min_y)
        elif y >= max_y:
            new_max_y = max_y + (max_y - min_y)

        if z < min_z:
            new_min_z = min_z - (max_z - min_z)
        elif z >= max_z:
            new_max_z = max_z + (max_z - min_z)

        new_root = OctreeNode(
            (new_min_x, new_max_x, new_min_y, new_max_y, new_min_z, new_max_z),
            depth=0,
            max_depth=self.max_depth
        )
        new_root._subdivide()

        cx, cy, cz = self.center
        for child in new_root.children:
            if child.contains(cx, cy, cz):
                child.children = [self] if self.children is None else self.children
                child.cell = self.cell
                break
        return new_root

    def all_cells(self):
        if self.cell is not None:
            yield self.cell
        if self.children is not None:
            for child in self.children:
                yield from child.all_cells()

    def count_cells(self) -> int:
        count = 1 if self.cell is not None else 0
        if self.children is not None:
            for child in self.children:
                count += child.count_cells()
        return count


class OctreeWorld:
    """
    The entire world — an octree that grows as needed.
    """

    def __init__(self,
                 initial_bounds: Tuple[float, float, float, float, float, float] = (-10, 10, -10, 10, -10, 10),
                 max_depth: int = 16):
        self.root = OctreeNode(initial_bounds, max_depth=max_depth)
        self.max_depth = max_depth
        self.cell_count = 0
        self.cells_by_id = {}

    def add_cell(self, cell) -> bool:
        x, y, z = cell.position
        if not self.root.contains(x, y, z):
            self.root = self.root.expand_to_include(x, y, z)

        success = self.root.insert_cell(cell)
        if success:
            self.cell_count += 1
            self.cells_by_id[cell.uid] = cell
        return success

    def remove_cell(self, x: float, y: float, z: float):
        cell = self.root.remove_cell(x, y, z)
        if cell:
            self.cell_count -= 1
            if cell.uid in self.cells_by_id:
                del self.cells_by_id[cell.uid]
        return cell

    def get_cell(self, x: float, y: float, z: float):
        return self.root.get_cell(x, y, z)

    def get_cell_by_id(self, uid: str):
        return self.cells_by_id.get(uid)

    def get_cells_in_sphere(self, center: Tuple[float, float, float], radius: float):
        return self.root.get_cells_in_sphere(center, radius)

    def all_cells(self):
        return list(self.cells_by_id.values())

    def print_stats(self):
        print(f"World Statistics:")
        print(f"  Cells: {self.cell_count}")
        print(f"  Root bounds: {self.root.bounds}")