"""
pygame_renderer.py - Visual interpretation of the eigenspectral world.

This file is entirely a display layer. It reads cell states and positions
and converts them to pixels. No mathematics here — only geometry of drawing.

Design:
  - Isometric voxel rendering (top + left + right faces per cell)
  - Painter's algorithm: cells sorted back-to-front by isometric depth
  - Color mapped from normalized coherence against archetypes
  - Water cells rendered last with alpha compositing (translucency)
  - Crystal dome overlay in screen space
  - Depth fog toward background color
  - Camera: pan with arrow keys, zoom with +/-, rotate with Q/E
"""

import pygame
import numpy as np
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass
import time

from octree import OctreeWorld
from cell import WorldCell
from archetypes import get_archetypes


# ============================================================================
# PALETTE
# ============================================================================

BG_COLOR       = (8, 14, 26)          # Deep ocean night

SAND_TOP       = (235, 215, 155)
SAND_LEFT      = (195, 172, 112)
SAND_RIGHT     = (175, 152,  95)

ROCK_TOP       = (130, 118, 105)
ROCK_LEFT      = ( 95,  86,  76)
ROCK_RIGHT     = ( 78,  70,  62)

WATER_TOP      = ( 55, 130, 200, 160)  # RGBA — transparent
WATER_LEFT     = ( 35,  95, 160, 120)
WATER_RIGHT    = ( 25,  75, 140, 100)

AIR_TOP        = (200, 225, 245,  30)
AIR_LEFT       = (180, 210, 240,  20)
AIR_RIGHT      = (170, 200, 235,  15)

MIXED_TOP      = (160, 155, 165)
MIXED_LEFT     = (120, 116, 124)
MIXED_RIGHT    = (100,  96, 104)

DOME_COLOR     = (120, 200, 255, 45)   # Crystal dome ring
DOME_RIM_COLOR = (160, 230, 255, 90)

FOG_COLOR      = np.array(BG_COLOR, dtype=float)


# ============================================================================
# CONFIG
# ============================================================================

@dataclass
class RenderConfig:
    width:          int   = 1280
    height:         int   = 800
    target_fps:     int   = 30
    tile_w:         int   = 18       # Isometric tile half-width
    tile_h:         int   = 9        # Isometric tile half-height  (= tile_w/2)
    voxel_depth:    int   = 10       # Face height for top-of-voxel -> bottom
    show_grid:      bool  = False
    show_fps:       bool  = True
    show_dome:      bool  = True
    render_radius:  float = 18.0
    fog_start:      float = 10.0
    fog_end:        float = 18.0
    zoom_min:       float = 0.4
    zoom_max:       float = 3.0


# ============================================================================
# COLOR MAPPER
# ============================================================================

class ColorMapper:
    """
    Maps a cell's state to face colors (top, left, right).
    Coherence is normalized by cell norm so evolved cells color correctly.
    Returns (top_rgba, left_rgba, right_rgba, is_transparent).
    """

    def __init__(self):
        self.archetypes = get_archetypes()
        self._cache: Dict[str, tuple] = {}

    def clear(self):
        self._cache.clear()

    def _coherence(self, cell_state: np.ndarray, arch_state: np.ndarray) -> float:
        """Normalized coherence: |<ψ_cell|ψ_arch>|² / (||ψ_cell||² ||ψ_arch||²)"""
        dot = np.vdot(cell_state, arch_state)
        norm_cell = np.vdot(cell_state, cell_state).real
        norm_arch = np.vdot(arch_state, arch_state).real
        denom = norm_cell * norm_arch
        if denom < 1e-30:
            return 0.0
        return (abs(dot)**2) / denom

    def classify(self, cell: WorldCell) -> str:
        state = cell.resonance.state
        best_name = 'mixed'
        best_coh  = 0.0
        for name in self.archetypes.all_names():
            arch = self.archetypes.get(name).point.to_array().astype(complex)
            c = self._coherence(state, arch)
            if c > best_coh:
                best_coh = c
                best_name = name
        return best_name if best_coh >= 0.25 else 'mixed'

    def __call__(self, cell: WorldCell) -> Tuple[tuple, tuple, tuple, bool]:
        """Returns (top_color, left_color, right_color, transparent)."""
        if cell.uid in self._cache:
            return self._cache[cell.uid]

        name = self.classify(cell)

        # Base face colors by archetype family
        if name in ('sand', 'wet_sand', 'sandstone', 'mud'):
            top, left, right = SAND_TOP, SAND_LEFT, SAND_RIGHT
            transparent = False
            # Modulate sand hue slightly by tau
            t = cell.tau
            top   = _tint(top,   (255, 235, 180), t * 0.3)
            left  = _tint(left,  (210, 190, 130), t * 0.3)
            right = _tint(right, (190, 170, 110), t * 0.3)

        elif name == 'rock':
            top, left, right = ROCK_TOP, ROCK_LEFT, ROCK_RIGHT
            transparent = False

        elif name in ('water', 'steam'):
            top, left, right = WATER_TOP, WATER_LEFT, WATER_RIGHT
            transparent = True
            # Deeper water = darker blue
            z = cell.position[2]
            depth_factor = max(0, min(1, (-z + 0.3) / 1.5))
            top   = _darken_rgba(top,   depth_factor * 0.4)
            left  = _darken_rgba(left,  depth_factor * 0.4)
            right = _darken_rgba(right, depth_factor * 0.4)

        elif name in ('air', 'cloud'):
            top, left, right = AIR_TOP, AIR_LEFT, AIR_RIGHT
            transparent = True

        elif name == 'fire':
            top   = (255, 160,  40, 200)
            left  = (220, 100,  20, 180)
            right = (200,  80,  10, 160)
            transparent = True

        else:  # mixed
            top, left, right = MIXED_TOP, MIXED_LEFT, MIXED_RIGHT
            transparent = False
            # Tint mixed cells by phi1 magnitude (from observed point)
            phi1 = abs(cell.point.phi1)
            top  = _tint(top,  (100, 150, 200), phi1 * 0.5)

        result = (_ensure_rgba(top), _ensure_rgba(left), _ensure_rgba(right), transparent)
        self._cache[cell.uid] = result
        return result


def _ensure_rgba(c) -> tuple:
    if len(c) == 3:
        return (c[0], c[1], c[2], 255)
    return c

def _tint(base: tuple, target: tuple, t: float) -> tuple:
    t = max(0, min(1, t))
    r = int(base[0] * (1-t) + target[0] * t)
    g = int(base[1] * (1-t) + target[1] * t)
    b = int(base[2] * (1-t) + target[2] * t)
    a = base[3] if len(base) == 4 else 255
    return (r, g, b, a)

def _darken_rgba(c: tuple, amount: float) -> tuple:
    f = 1.0 - amount
    return (int(c[0]*f), int(c[1]*f), int(c[2]*f), c[3] if len(c)==4 else 255)

def _fog_blend(color: tuple, fog_t: float) -> tuple:
    """Blend color toward fog color by fog_t in [0, 1]."""
    r = int(color[0] * (1 - fog_t) + FOG_COLOR[0] * fog_t)
    g = int(color[1] * (1 - fog_t) + FOG_COLOR[1] * fog_t)
    b = int(color[2] * (1 - fog_t) + FOG_COLOR[2] * fog_t)
    a = int(color[3] * (1 - fog_t)) if len(color) == 4 else 255
    return (r, g, b, a)


# ============================================================================
# ISOMETRIC PROJECTION
# ============================================================================

class IsoProjection:
    """
    Standard isometric projection with zoom and pan.

    World (x, y, z) -> screen (sx, sy):
      sx = cx + (x - y) * tw * zoom
      sy = cy + (x + y) * th * zoom - z * vd * zoom

    Painter depth key (back-to-front): x + y - 2*z  (smaller = further back)
    """

    def __init__(self, config: RenderConfig):
        self.config = config
        self.cx = config.width  // 2
        self.cy = config.height // 2
        self.zoom   = 1.0
        self.pan_x  = 0.0
        self.pan_y  = 0.0
        self.rotate = 0   # 0, 1, 2, 3 = 0°, 90°, 180°, 270° (swaps x/y axes)

    def project(self, x: float, y: float, z: float) -> Tuple[int, int]:
        # Apply rotation (swap/flip x,y for cardinal views)
        rx, ry = self._rotate_xy(x, y)
        tw = self.config.tile_w * self.zoom
        th = self.config.tile_h * self.zoom
        vd = self.config.voxel_depth * self.zoom
        sx = self.cx + (rx - ry) * tw - self.pan_x * tw * 2
        sy = self.cy + (rx + ry) * th - z * vd - self.pan_y * th * 2
        return int(sx), int(sy)

    def depth_key(self, x: float, y: float, z: float) -> float:
        rx, ry = self._rotate_xy(x, y)
        return rx + ry - 2.0 * z

    def _rotate_xy(self, x, y):
        r = self.rotate % 4
        if r == 0: return  x,  y
        if r == 1: return -y,  x
        if r == 2: return -x, -y
        if r == 3: return  y, -x

    def tile_polygon(self, sx: int, sy: int) -> Dict[str, List[Tuple[int,int]]]:
        """
        Return the three face polygons for a voxel drawn at screen (sx, sy).
        sx, sy is the top-center of the voxel.
        """
        tw = max(1, int(self.config.tile_w * self.zoom))
        th = max(1, int(self.config.tile_h * self.zoom))
        vd = max(1, int(self.config.voxel_depth * self.zoom))

        # Top face (diamond)
        top = [
            (sx,      sy),
            (sx + tw, sy + th),
            (sx,      sy + 2*th),
            (sx - tw, sy + th),
        ]
        # Left face
        left = [
            (sx - tw, sy + th),
            (sx,      sy + 2*th),
            (sx,      sy + 2*th + vd),
            (sx - tw, sy + th   + vd),
        ]
        # Right face
        right = [
            (sx,      sy + 2*th),
            (sx + tw, sy + th),
            (sx + tw, sy + th   + vd),
            (sx,      sy + 2*th + vd),
        ]
        return {'top': top, 'left': left, 'right': right}


# ============================================================================
# RENDERER
# ============================================================================

class PygameRenderer:

    def __init__(self, world: OctreeWorld, config: Optional[RenderConfig] = None):
        self.world  = world
        self.config = config or RenderConfig()
        self.proj   = IsoProjection(self.config)
        self.colors = ColorMapper()

        pygame.init()
        flags = 0
        self.screen = pygame.display.set_mode(
            (self.config.width, self.config.height), flags)
        pygame.display.set_caption("Eigenspectral World")

        # Offscreen surface for alpha compositing (water, air)
        self.overlay = pygame.Surface(
            (self.config.width, self.config.height), pygame.SRCALPHA)

        self.clock      = pygame.time.Clock()
        self.font       = pygame.font.Font(None, 22)
        self.small_font = pygame.font.Font(None, 17)

        self.paused         = False
        self.selected_cell  = None
        self.show_help      = False
        self.frame_count    = 0
        self.last_time      = time.time()
        self.fps            = 0
        self.visible_count  = 0
        self.total_count    = 0
        self._key_repeat    = {}

    # ------------------------------------------------------------------ events

    def handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: return False
                if event.key == pygame.K_h:      self.show_help = not self.show_help
                if event.key == pygame.K_SPACE:  self.paused    = not self.paused
                if event.key == pygame.K_r:
                    self.proj.pan_x = self.proj.pan_y = 0.0
                    self.proj.zoom  = 1.0
                    self.proj.rotate = 0
                if event.key == pygame.K_q:
                    self.proj.rotate = (self.proj.rotate - 1) % 4
                if event.key == pygame.K_e:
                    self.proj.rotate = (self.proj.rotate + 1) % 4
                if event.key == pygame.K_g:
                    self.config.show_grid = not self.config.show_grid
                if event.key == pygame.K_d:
                    self.config.show_dome = not self.config.show_dome
            if event.type == pygame.MOUSEWHEEL:
                self.proj.zoom = max(self.config.zoom_min,
                                     min(self.config.zoom_max,
                                         self.proj.zoom * (1.1 if event.y > 0 else 0.9)))
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._select_at_mouse()

        keys = pygame.key.get_pressed()
        speed = 0.12
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: self.proj.pan_x -= speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: self.proj.pan_x += speed
        if keys[pygame.K_UP]    or keys[pygame.K_w]: self.proj.pan_y -= speed
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: self.proj.pan_y += speed
        if keys[pygame.K_EQUALS] or keys[pygame.K_PLUS]:
            self.proj.zoom = min(self.config.zoom_max, self.proj.zoom * 1.02)
        if keys[pygame.K_MINUS]:
            self.proj.zoom = max(self.config.zoom_min, self.proj.zoom * 0.98)

        return True

    def _select_at_mouse(self):
        mx, my = pygame.mouse.get_pos()
        best_dist = 400   # pixels squared
        best_cell = None
        for cell in self._visible_cells():
            sx, sy = self.proj.project(*cell.position)
            d = (sx - mx)**2 + (sy - my)**2
            if d < best_dist:
                best_dist = d
                best_cell = cell
        self.selected_cell = best_cell

    # ------------------------------------------------------------------ cells

    def _visible_cells(self) -> List[WorldCell]:
        """All cells within render_radius of (pan_x, pan_y, 0)."""
        center = (self.proj.pan_x, self.proj.pan_y, 0.0)
        cells = self.world.get_cells_in_sphere(center, self.config.render_radius)
        # Filter to screen frustum
        W, H = self.config.width, self.config.height
        margin = 120
        visible = []
        for c in cells:
            sx, sy = self.proj.project(*c.position)
            if -margin < sx < W + margin and -margin < sy < H + margin:
                visible.append(c)
        return visible

    # ------------------------------------------------------------------ render

    def render(self):
        self.colors.clear()
        self.screen.fill(BG_COLOR)
        self.overlay.fill((0, 0, 0, 0))

        cells = self._visible_cells()
        self.visible_count = len(cells)
        self.total_count   = self.world.cell_count

        # Sort back-to-front (painter's algorithm)
        cells.sort(key=lambda c: self.proj.depth_key(*c.position))

        opaque_cells      = []
        transparent_cells = []

        for cell in cells:
            top, left, right, transparent = self.colors(cell)
            if transparent:
                transparent_cells.append((cell, top, left, right))
            else:
                opaque_cells.append((cell, top, left, right))

        # 1. Grid
        if self.config.show_grid:
            self._draw_grid()

        # 2. Opaque cells onto screen
        for cell, top, left, right in opaque_cells:
            self._draw_voxel(self.screen, cell, top, left, right)

        # 3. Transparent cells onto overlay
        for cell, top, left, right in transparent_cells:
            self._draw_voxel(self.overlay, cell, top, left, right)

        # 4. Composite overlay
        self.screen.blit(self.overlay, (0, 0))

        # 5. Crystal dome
        if self.config.show_dome:
            self._draw_dome()

        # 6. UI
        self._draw_ui()

        pygame.display.flip()

        self.frame_count += 1
        now = time.time()
        if now - self.last_time >= 1.0:
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_time   = now

        self.clock.tick(self.config.target_fps)

    def _fog_t(self, x, y, z) -> float:
        dist = np.sqrt((x - self.proj.pan_x)**2 +
                       (y - self.proj.pan_y)**2 + z*z)
        t = (dist - self.config.fog_start) / (self.config.fog_end - self.config.fog_start)
        return float(np.clip(t, 0, 1))

    def _draw_voxel(self, surface: pygame.Surface,
                    cell: WorldCell,
                    top: tuple, left: tuple, right: tuple):
        sx, sy = self.proj.project(*cell.position)
        polys = self.proj.tile_polygon(sx, sy)

        fog_t = self._fog_t(*cell.position)

        top   = _fog_blend(top,   fog_t)
        left  = _fog_blend(left,  fog_t)
        right = _fog_blend(right, fog_t)

        # Draw faces (alpha-aware)
        if surface.get_flags() & pygame.SRCALPHA:
            pygame.draw.polygon(surface, top,   polys['top'])
            pygame.draw.polygon(surface, left,  polys['left'])
            pygame.draw.polygon(surface, right, polys['right'])
        else:
            pygame.draw.polygon(surface, top[:3],   polys['top'])
            pygame.draw.polygon(surface, left[:3],  polys['left'])
            pygame.draw.polygon(surface, right[:3], polys['right'])

        # Selection highlight
        if cell is self.selected_cell:
            pygame.draw.polygon(surface, (255, 255, 255, 200), polys['top'], 2)

    def _draw_grid(self):
        """Ground-plane reference grid."""
        step = 2
        grid_r = 12
        color = (30, 45, 65)
        for x in range(-grid_r, grid_r + 1, step):
            p0 = self.proj.project(float(x), float(-grid_r), 0)
            p1 = self.proj.project(float(x), float( grid_r), 0)
            pygame.draw.line(self.screen, color, p0, p1, 1)
        for y in range(-grid_r, grid_r + 1, step):
            p0 = self.proj.project(float(-grid_r), float(y), 0)
            p1 = self.proj.project(float( grid_r), float(y), 0)
            pygame.draw.line(self.screen, color, p0, p1, 1)

    def _draw_dome(self):
        """
        Crystal dome overlay. Drawn in screen space as a series of
        concentric ellipses, fading inward, representing the spherical
        boundary of the simulation volume.
        """
        cx = self.config.width  // 2
        cy = self.config.height // 2

        tw = self.config.tile_w * self.proj.zoom
        th = self.config.tile_h * self.proj.zoom
        vd = self.config.voxel_depth * self.proj.zoom

        # World sphere radius 12 -> screen ellipse
        from genesis import WORLD_RADIUS
        rx = int(WORLD_RADIUS * tw * 1.42)  # sqrt(2) * tw * R
        ry_base = int(WORLD_RADIUS * th * 1.42)
        ry_dome = int(WORLD_RADIUS * vd * 0.85)

        dome_surf = pygame.Surface((self.config.width, self.config.height),
                                   pygame.SRCALPHA)

        # Base ellipse (water horizon)
        for t in range(3):
            alpha = 60 - t * 15
            ex = rx - t * 4
            ey = ry_base - t * 2
            if ex > 0 and ey > 0:
                pygame.draw.ellipse(dome_surf, (*DOME_RIM_COLOR[:3], alpha),
                                    (cx - ex, cy - ey, ex*2, ey*2), 2)

        # Upper dome arc (hemisphere) — approximate with scaled ellipse
        dome_ry = ry_base + ry_dome
        for t in range(4):
            alpha = max(5, 40 - t * 10)
            ew = rx - t * 3
            eh = dome_ry - t * 4
            if ew > 0 and eh > 0:
                # Only draw upper half
                rect = pygame.Rect(cx - ew, cy - eh, ew*2, eh*2)
                pygame.draw.arc(dome_surf, (*DOME_COLOR[:3], alpha),
                                rect, 0, np.pi, 2)

        # Rim glow
        pygame.draw.ellipse(dome_surf, DOME_RIM_COLOR,
                            (cx - rx, cy - ry_base, rx*2, ry_base*2), 1)

        self.screen.blit(dome_surf, (0, 0))

    # ------------------------------------------------------------------ UI

    def _draw_ui(self):
        lines = []
        if self.config.show_fps:
            lines.append(f"FPS: {self.fps}")
        lines.append(f"Cells: {self.visible_count} / {self.total_count} visible")
        lines.append(f"Zoom: {self.proj.zoom:.2f}  Rot: {self.proj.rotate * 90}deg")
        if self.paused:
            lines.append("PAUSED")

        y = 10
        for line in lines:
            surf = self.font.render(line, True, (160, 185, 210))
            self.screen.blit(surf, (10, y))
            y += 20

        if self.selected_cell:
            c = self.selected_cell
            name = self.colors.classify(c)
            info = [
                f"ID: {c.uid}",
                f"Type: {name}",
                f"tau: {c.tau:.3f}",
                f"pos: ({c.position[0]:.1f}, {c.position[1]:.1f}, {c.position[2]:.1f})",
            ]
            y2 = self.config.height - 20 * len(info) - 10
            for line in info:
                surf = self.small_font.render(line, True, (200, 220, 240))
                self.screen.blit(surf, (10, y2))
                y2 += 20

        if self.show_help:
            self._draw_help()

    def _draw_help(self):
        lines = [
            "Arrows / WASD: pan",
            "+/-: zoom",
            "Scroll wheel: zoom",
            "Q/E: rotate view",
            "G: toggle grid",
            "D: toggle dome",
            "Space: pause sim",
            "R: reset camera",
            "Click: select cell",
            "H: toggle help",
            "ESC: quit",
        ]
        x = self.config.width - 220
        y = 10
        for line in lines:
            surf = self.small_font.render(line, True, (160, 185, 210))
            self.screen.blit(surf, (x, y))
            y += 18

    # ------------------------------------------------------------------ loop

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.render()
        pygame.quit()
