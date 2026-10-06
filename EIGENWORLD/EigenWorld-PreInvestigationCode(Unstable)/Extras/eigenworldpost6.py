"""
eigenworld.py — Eigenspectral World Renderer  v2

WHAT YOU ARE SEEING
===================
Each cell in this world is a TRIANGLE with three vertices:

    v_past    = τ        the past vertex — geological depth, stone sinks
    v_future₁ = φ₁       first branch of possibility
    v_future₂ = φ₂       second branch of possibility
    observer  = ξ        what connects observation to the future pair

The Y operator BREATHES this triangle each step:
  High |τ|  →  tall triangle   (past dominant)  →  stone, sinks
  Low  |τ|  →  flat triangle   (futures spread)  →  water, floats

Period-4 orbit = two breaths:  tall → flat → tall → flat → ...

The manifold constraint τ² + |φ₁|²|φ₂|² + |ξ|⁴(|φ₁|²−|φ₂|²)² = 1
is the triangle's energy conservation law.

EVERY VISUAL IS A COORDINATE READING:
  x, y position  =  Re/Im(φ₁·φ̄₂) × 4     future-vertex correlation
  depth z        =  −|τ| × 5               past-vertex height
  colour mode 0  =  material from |τ| thresholds
  water shimmer  =  θ = arg(φ₁φ̄₂)          triangle opening angle
  birth glow     =  warm gold for first 30 steps
  creation glow  =  teal pulse at θ ≈ −90°  (retrocausal creation phase)

TRIANGLE WIREFRAMES (T):
  Each voxel gains a wireframe showing its actual geometric shape.
  Stone = tall narrow triangle.  Water = wide flat triangle.
  Cells at θ ≈ −90° (the retrocausal creation corridor) glow teal.

ζ-θ PHASE PANEL (Z):
  Scatter of all cells in (θ, ζ) space:
    θ = arg(φ₁φ̄₂)              future phase relationship  [x-axis]
    ζ = (|φ₁|²−|φ₂|²)|ξ|²      future asymmetry           [y-axis]
  The creation corridor at θ = −π/2 is marked.

COLOUR MODES  (V cycles):
  0  material       stone/sand/water/air, spiral shimmer on water
  1  τ-gradient     vacuum blue → ancient amber
  2  spiral-phase   θ → full hue wheel, the opening angle made visible
  3  age            gold (newborn) → deep teal (ancient)
  4  triangle-arm   future spread mapped to hue, past depth to brightness
  5  living-Y       local Y-field strength: cold=soft ocean, hot=stiff stone

CONTROLS
========
  Arrows / WASD    pan
  Scroll / +−      zoom
  Q / E            rotate isometric view (4 cardinal angles)
  V                cycle colour mode
  T                toggle triangle wireframes
  Z                toggle ζ-θ phase panel
  G                toggle reference grid
  D                toggle crystal dome
  Space            pause / resume
  R                reset camera
  Click            inspect cell
  H                toggle help
  ESC              quit
"""

import time
import numpy as np
import pygame
from dataclasses import dataclass
from typing import Tuple, List, Optional

from pure_world import (
    PureWorld, RenderFrame, seed_from_island, step_world,
    MATERIAL_NAMES, TAU_STONE, TAU_SAND, TAU_WATER,
)


# ══════════════════════════════════════════════════════════════════════════════
# PALETTE
# ══════════════════════════════════════════════════════════════════════════════

BG = (5, 10, 20)  # deep vacuum

STONE_TOP   = (148, 136, 122)
STONE_LEFT  = (108,  98,  88)
STONE_RIGHT = ( 88,  80,  70)

SAND_TOP    = (238, 210, 140)
SAND_LEFT   = (198, 172, 100)
SAND_RIGHT  = (178, 152,  82)

WATER_TOP   = ( 48, 120, 210, 150)
WATER_LEFT  = ( 28,  85, 168, 110)
WATER_RIGHT = ( 18,  65, 148,  90)

AIR_TOP     = (190, 218, 248,  22)
AIR_LEFT    = (170, 200, 240,  14)
AIR_RIGHT   = (155, 188, 232,  10)

BIRTH_GLOW    = (255, 240, 160)   # warm gold — newborn cells
CREATION_GLOW = ( 55, 210, 190)   # teal — retrocausal creation phase

FOG_COLOR = np.array(BG, dtype=float)

DOME_RIM  = (140, 210, 255,  80)
DOME_FILL = (110, 185, 255,  28)

# Triangle wireframe colours per material (RGBA)
TRI_COLS = {
    0: (200, 188, 170, 130),  # stone  — pale warm
    1: (255, 228, 120, 150),  # sand   — gold
    2: ( 80, 185, 255, 110),  # water  — sky blue
    3: (160, 200, 240,  45),  # air    — ghost
}

# θ = −π/2 is the retrocausal creation corridor (Notes §8.2, θ = 3π/2)
CREATION_THETA     = -np.pi / 2
CREATION_THETA_TOL =  np.radians(22)


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RenderConfig:
    width:            int   = 1280
    height:           int   = 800
    target_fps:       int   = 30
    tile_w:           int   = 20
    tile_h:           int   = 10
    voxel_depth:      int   = 11
    show_grid:        bool  = False
    show_dome:        bool  = True
    show_fps:         bool  = True
    show_triangles:   bool  = False
    show_phase_panel: bool  = False
    show_witness:     bool  = True   # W — the silent geometric counterpoint
    fog_start:        float = 14.0
    fog_end:          float = 22.0
    zoom_min:         float = 0.3
    zoom_max:         float = 4.0
    colour_mode:      int   = 0   # 0=material 1=τ 2=spiral 3=age 4=tri-arm
    phase_panel_w:    int   = 210


# ══════════════════════════════════════════════════════════════════════════════
# COLOUR HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _hsv(h: float, s: float, v: float) -> Tuple[int, int, int]:
    h = h % 360
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c
    if   h < 60:  r, g, b = c, x, 0
    elif h < 120: r, g, b = x, c, 0
    elif h < 180: r, g, b = 0, c, x
    elif h < 240: r, g, b = 0, x, c
    elif h < 300: r, g, b = x, 0, c
    else:         r, g, b = c, 0, x
    return int((r+m)*255), int((g+m)*255), int((b+m)*255)


def _lerp(a, b, t: float):
    t = max(0.0, min(1.0, t))
    return (int(a[0] + (b[0]-a[0])*t),
            int(a[1] + (b[1]-a[1])*t),
            int(a[2] + (b[2]-a[2])*t))


def _rgba(c) -> tuple:
    return c if len(c) == 4 else (c[0], c[1], c[2], 255)


def _fog(color: tuple, t: float) -> tuple:
    f = 1.0 - t
    r = int(color[0]*f + FOG_COLOR[0]*t)
    g = int(color[1]*f + FOG_COLOR[1]*t)
    b = int(color[2]*f + FOG_COLOR[2]*t)
    a = int(color[3]*(1.0 - t*0.6)) if len(color) == 4 else 255
    return r, g, b, a


def _blend_glow(base: tuple, glow_rgb: tuple, t: float) -> tuple:
    """Blend glow colour over base top-face tuple."""
    if t < 0.01:
        return base
    r = int(base[0]*(1-t) + glow_rgb[0]*t)
    g = int(base[1]*(1-t) + glow_rgb[1]*t)
    b = int(base[2]*(1-t) + glow_rgb[2]*t)
    a = base[3] if len(base) == 4 else 255
    return r, g, b, a


# ══════════════════════════════════════════════════════════════════════════════
# TRIANGLE DATA  — extracted once per frame from world state
# ══════════════════════════════════════════════════════════════════════════════

class TriangleData:
    """
    Per-cell triangle geometry, extracted from the raw 7D state.

    S[i] = (τ, Re φ₁, Im φ₁, Re φ₂, Im φ₂, Re ξ, Im ξ)  complex64

    Triangle vertices:
      past     vertex = τ   (depth, sinks with memory)
      future₁  vertex = φ₁  (first possibility branch)
      future₂  vertex = φ₂  (second possibility branch)
    """
    __slots__ = ('tau', 'phi1_abs', 'phi2_abs', 'phi1_re', 'phi1_im',
                 'phi2_re', 'phi2_im', 'theta', 'zeta', 'arm_mean',
                 'tri_area', 'near_creation', 'N')

    def __init__(self, world: PureWorld):
        idx  = world.indices
        S    = world.S[idx]             # (N, 7) complex64
        self.N = len(idx)

        tau      = S[:, 0].real
        phi1_re  = S[:, 1].real
        phi1_im  = S[:, 2].real
        phi2_re  = S[:, 3].real
        phi2_im  = S[:, 4].real
        xi_re    = S[:, 5].real
        xi_im    = S[:, 6].real

        phi1_abs = np.sqrt(phi1_re**2 + phi1_im**2).astype(np.float32)
        phi2_abs = np.sqrt(phi2_re**2 + phi2_im**2).astype(np.float32)
        xi_abs2  = (xi_re**2 + xi_im**2).astype(np.float32)

        # θ = arg(φ₁ · φ̄₂) — the opening angle of the future pair
        # == spiral_phase in RenderFrame
        corr_re  = phi1_re * phi2_re + phi1_im * phi2_im
        corr_im  = phi1_im * phi2_re - phi1_re * phi2_im
        theta    = np.arctan2(corr_im, corr_re).astype(np.float32)

        # ζ = (|φ₁|² − |φ₂|²) · |ξ|²   — future asymmetry
        zeta     = ((phi1_abs**2 - phi2_abs**2) * xi_abs2).astype(np.float32)

        # Triangle area in the (φ₁, φ₂) plane
        area     = (0.5 * phi1_abs * phi2_abs *
                    np.abs(np.sin(theta))).astype(np.float32)

        self.tau          = tau.astype(np.float32)
        self.phi1_abs     = phi1_abs
        self.phi2_abs     = phi2_abs
        self.phi1_re      = phi1_re.astype(np.float32)
        self.phi1_im      = phi1_im.astype(np.float32)
        self.phi2_re      = phi2_re.astype(np.float32)
        self.phi2_im      = phi2_im.astype(np.float32)
        self.theta        = theta
        self.zeta         = zeta
        self.arm_mean     = ((phi1_abs + phi2_abs) * 0.5).astype(np.float32)
        self.tri_area     = area
        self.near_creation = (
            np.abs(theta - CREATION_THETA) < CREATION_THETA_TOL
        )


# ══════════════════════════════════════════════════════════════════════════════
# COLOUR ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class ColourEngine:

    def compute(self, frame: RenderFrame, tri: TriangleData,
                cfg: RenderConfig) -> List[Tuple[tuple, tuple, tuple, bool]]:
        mode = cfg.colour_mode
        out  = []
        for i in range(frame.N):
            tau   = float(frame.tau_abs[i])
            mat   = int(frame.materials[i])
            age   = int(frame.ages[i])
            sp    = float(frame.spiral_phase[i])
            arm   = float(tri.arm_mean[i])
            near  = bool(tri.near_creation[i])
            alpha = float(frame.local_alpha[i])

            top, left, right, transp = self._colour(tau, mat, age, sp, arm, near, mode, alpha)
            out.append((top, left, right, transp))
        return out

    # ------------------------------------------------------------------

    def _colour(self, tau, mat, age, sp, arm, near_creation, mode, alpha=0.0
                ) -> Tuple[tuple, tuple, tuple, bool]:

        birth_t  = max(0.0, 1.0 - age / 30.0)
        create_t = 0.40 if (near_creation and mat == 2) else 0.0

        # ── Mode 0: material ──────────────────────────────────────────────
        if mode == 0:
            if mat == 0:        # stone — crystalline grey, faint spiral shimmer
                sp_t  = (np.sin(sp) * 0.5 + 0.5) * 0.12
                top   = _lerp(STONE_TOP,   (200, 195, 190), sp_t)
                left  = _lerp(STONE_LEFT,  (155, 150, 145), sp_t)
                right = _lerp(STONE_RIGHT, (130, 126, 120), sp_t)
                transp = False

            elif mat == 1:      # sand — warm gold, tau shifts richness
                t_mod = np.clip((tau - TAU_SAND) / max(TAU_STONE - TAU_SAND, 1e-6), 0, 1)
                top   = _lerp(SAND_TOP,   (255, 235, 175), t_mod * 0.25)
                left  = _lerp(SAND_LEFT,  (215, 188, 128), t_mod * 0.25)
                right = _lerp(SAND_RIGHT, (192, 166, 108), t_mod * 0.25)
                transp = False

            elif mat == 2:      # water — cerulean, spiral-phase shimmer
                hue_shift = np.sin(sp) * 18
                r, g, b = _hsv(210 + hue_shift, 0.72, 0.78)
                top   = (r,           g,           b,           148)
                left  = (int(r*0.62), int(g*0.62), int(b*0.72), 108)
                right = (int(r*0.50), int(g*0.50), int(b*0.60),  88)
                transp = True

            else:               # air — barely-there blue breath
                top, left, right = AIR_TOP, AIR_LEFT, AIR_RIGHT
                transp = True

        # ── Mode 1: τ-gradient ────────────────────────────────────────────
        elif mode == 1:
            t = np.clip(tau / TAU_STONE, 0.0, 1.0)
            r, g, b = _hsv((220 - t * 160) % 360, 0.30 + t*0.55, 0.40 + t*0.45)
            al    = 255 if tau > TAU_WATER else 155
            top   = (r, g, b, al)
            left  = (int(r*0.72), int(g*0.72), int(b*0.72), al)
            right = (int(r*0.58), int(g*0.58), int(b*0.58), al)
            transp = tau <= TAU_WATER

        # ── Mode 2: spiral-phase θ → hue ──────────────────────────────────
        elif mode == 2:
            hue = (sp / np.pi * 180 + 180) % 360
            r, g, b = _hsv(hue, 0.65 + tau*0.25, 0.55 + tau*0.30)
            al    = 255 if tau > TAU_WATER else 130
            top   = (r, g, b, al)
            left  = (int(r*0.68), int(g*0.68), int(b*0.68), al)
            right = (int(r*0.52), int(g*0.52), int(b*0.52), al)
            transp = tau <= TAU_WATER

        # ── Mode 3: age ────────────────────────────────────────────────────
        elif mode == 3:
            age_t = min(1.0, age / 400.0)
            r, g, b = _hsv((50 - age_t * 170) % 360,
                           0.70 - age_t*0.20, 0.85 - age_t*0.15)
            al    = 255 if tau > TAU_WATER else 140
            top   = (r, g, b, al)
            left  = (int(r*0.70), int(g*0.70), int(b*0.70), al)
            right = (int(r*0.55), int(g*0.55), int(b*0.55), al)
            transp = tau <= TAU_WATER

        # ── Mode 4: triangle-arm geometry ─────────────────────────────────
        elif mode == 4:
            # Hue encodes future arm spread: narrow (orange) → wide (cyan)
            arm_t = np.clip(arm / 0.75, 0.0, 1.0)
            r, g, b = _hsv(28 + arm_t * 162, 0.78, 0.45 + tau*0.45)
            al    = 255 if tau > TAU_WATER else 140
            top   = (r, g, b, al)
            left  = (int(r*0.70), int(g*0.70), int(b*0.70), al)
            right = (int(r*0.55), int(g*0.55), int(b*0.55), al)
            transp = tau <= TAU_WATER

        # ── Mode 5: living Y field (local Y-strength α) ────────────────────
        else:
            # alpha < 0: soft ocean (cool blue-cyan)
            # alpha = 0: shoreline (teal)
            # alpha > 0: stiff stone (warm orange-red)
            # Normalise alpha to [-1, +1] using the theoretical max ALPHA_Y
            from pure_world import ALPHA_Y
            a_norm = np.clip(alpha / (ALPHA_Y + 1e-10), -1.0, 1.0)
            if a_norm >= 0:
                # positive: cool teal → hot orange-red
                hue = 160 - a_norm * 140   # 160 (teal) → 20 (red-orange)
                sat = 0.55 + a_norm * 0.35
                val = 0.55 + a_norm * 0.30
            else:
                # negative: teal → deep cold blue
                hue = 160 - a_norm * 60    # 160 (teal) → 220 (blue)
                sat = 0.55 + abs(a_norm) * 0.30
                val = 0.45 + abs(a_norm) * 0.15
            r, g, b = _hsv(hue % 360, sat, val)
            al    = 255 if tau > TAU_WATER else 140
            top   = (r, g, b, al)
            left  = (int(r*0.70), int(g*0.70), int(b*0.70), al)
            right = (int(r*0.55), int(g*0.55), int(b*0.55), al)
            transp = tau <= TAU_WATER

        # ── Glow pulses ────────────────────────────────────────────────────
        top = _rgba(top)
        if birth_t > 0.02:
            top = _blend_glow(top, BIRTH_GLOW, birth_t)
        if create_t > 0.0:
            top = _blend_glow(top, CREATION_GLOW, create_t)

        return top, _rgba(left), _rgba(right), transp


# ══════════════════════════════════════════════════════════════════════════════
# ISOMETRIC PROJECTION
# ══════════════════════════════════════════════════════════════════════════════

class IsoProjection:
    def __init__(self, cfg: RenderConfig):
        self.cfg    = cfg
        self.cx     = cfg.width  // 2
        self.cy     = cfg.height // 2
        self.zoom   = 1.0
        self.pan_x  = 0.0
        self.pan_y  = 0.0
        self.rotate = 0

    def project(self, x, y, z) -> Tuple[int, int]:
        rx, ry = self._rot(x, y)
        tw = self.cfg.tile_w      * self.zoom
        th = self.cfg.tile_h      * self.zoom
        vd = self.cfg.voxel_depth * self.zoom
        sx = self.cx + (rx - ry) * tw - self.pan_x * tw * 2
        sy = self.cy + (rx + ry) * th - z * vd - self.pan_y * th * 2
        return int(sx), int(sy)

    def depth_key(self, x, y, z) -> float:
        rx, ry = self._rot(x, y)
        return rx + ry - 2.0 * z

    def _rot(self, x, y):
        r = self.rotate % 4
        if r == 0: return  x,  y
        if r == 1: return -y,  x
        if r == 2: return -x, -y
        return              y, -x

    def tile_polygon(self, sx: int, sy: int) -> dict:
        tw = max(1, int(self.cfg.tile_w      * self.zoom))
        th = max(1, int(self.cfg.tile_h      * self.zoom))
        vd = max(1, int(self.cfg.voxel_depth * self.zoom))
        top   = [(sx,      sy),
                 (sx + tw, sy + th),
                 (sx,      sy + 2*th),
                 (sx - tw, sy + th)]
        left  = [(sx - tw, sy + th),
                 (sx,      sy + 2*th),
                 (sx,      sy + 2*th + vd),
                 (sx - tw, sy + th   + vd)]
        right = [(sx,      sy + 2*th),
                 (sx + tw, sy + th),
                 (sx + tw, sy + th   + vd),
                 (sx,      sy + 2*th + vd)]
        return {'top': top, 'left': left, 'right': right}


# ══════════════════════════════════════════════════════════════════════════════
# RENDERER
# ══════════════════════════════════════════════════════════════════════════════

class EigenRenderer:

    def __init__(self, world: PureWorld, config: Optional[RenderConfig] = None):
        self.world   = world
        self.cfg     = config or RenderConfig()
        self.proj    = IsoProjection(self.cfg)
        self.colours = ColourEngine()

        pygame.init()
        self.screen  = pygame.display.set_mode((self.cfg.width, self.cfg.height))
        self.overlay = pygame.Surface(
            (self.cfg.width, self.cfg.height), pygame.SRCALPHA)
        pygame.display.set_caption(
            "Eigenspectral World  ·  Triangle Manifold Dynamics")

        self.clock      = pygame.time.Clock()
        self.font       = pygame.font.Font(None, 22)
        self.small      = pygame.font.Font(None, 17)

        self.paused      = False
        self.show_help   = False
        self.fps         = 0
        self.frame_count = 0
        self.last_time   = time.time()
        self.selected_i  = None

        self._last_frame: Optional[RenderFrame]   = None
        self._last_tri:   Optional[TriangleData]  = None
        self._cell_colours: list = []

        self._mode_names = [
            'material', 'τ-gradient', 'spiral-phase θ', 'age', 'triangle-arm', 'living-Y α'
        ]

    # ── events ────────────────────────────────────────────────────────────────

    def handle_events(self) -> bool:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            if ev.type == pygame.KEYDOWN:
                k = ev.key
                if k == pygame.K_ESCAPE: return False
                if k == pygame.K_SPACE:
                    self.paused = not self.paused
                if k == pygame.K_h:
                    self.show_help = not self.show_help
                if k == pygame.K_g:
                    self.cfg.show_grid = not self.cfg.show_grid
                if k == pygame.K_d:
                    self.cfg.show_dome = not self.cfg.show_dome
                if k == pygame.K_t:
                    self.cfg.show_triangles = not self.cfg.show_triangles
                if k == pygame.K_z:
                    self.cfg.show_phase_panel = not self.cfg.show_phase_panel
                if k == pygame.K_w:
                    self.cfg.show_witness = not self.cfg.show_witness
                if k == pygame.K_v:
                    self.cfg.colour_mode = (self.cfg.colour_mode + 1) % 6
                if k == pygame.K_r:
                    self.proj.pan_x = self.proj.pan_y = 0.0
                    self.proj.zoom  = 1.0
                    self.proj.rotate = 0
                if k == pygame.K_q:
                    self.proj.rotate = (self.proj.rotate - 1) % 4
                if k == pygame.K_e:
                    self.proj.rotate = (self.proj.rotate + 1) % 4
            if ev.type == pygame.MOUSEWHEEL:
                f = 1.1 if ev.y > 0 else 0.9
                self.proj.zoom = float(
                    np.clip(self.proj.zoom * f,
                            self.cfg.zoom_min, self.cfg.zoom_max))
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                self._click_select(pygame.mouse.get_pos())

        keys  = pygame.key.get_pressed()
        speed = 0.12
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: self.proj.pan_x -= speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: self.proj.pan_x += speed
        if keys[pygame.K_UP]:                        self.proj.pan_y -= speed
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: self.proj.pan_y += speed
        if keys[pygame.K_EQUALS] or keys[pygame.K_PLUS]:
            self.proj.zoom = min(self.cfg.zoom_max, self.proj.zoom * 1.02)
        if keys[pygame.K_MINUS]:
            self.proj.zoom = max(self.cfg.zoom_min, self.proj.zoom * 0.98)
        return True

    def _click_select(self, mouse_pos):
        if self._last_frame is None:
            return
        mx, my = mouse_pos
        # Ignore clicks inside the phase panel area
        if (self.cfg.show_phase_panel and
                mx > self.cfg.width - self.cfg.phase_panel_w - 6):
            return
        best_d, best_i = 1600, None
        for i in range(self._last_frame.N):
            pos = self._last_frame.positions[i]
            sx, sy = self.proj.project(*pos)
            d = (sx - mx)**2 + (sy - my)**2
            if d < best_d:
                best_d = d
                best_i = i
        self.selected_i = best_i

    # ── main render ───────────────────────────────────────────────────────────

    def render(self, frame: RenderFrame, tri: TriangleData):
        self._last_frame = frame
        self._last_tri   = tri
        self.screen.fill(BG)
        self.overlay.fill((0, 0, 0, 0))

        cell_colours = self.colours.compute(frame, tri, self.cfg)
        self._cell_colours = cell_colours

        positions = frame.positions         # (N, 3)
        cx, cy    = self.proj.pan_x, self.proj.pan_y
        dists     = np.sqrt((positions[:, 0] - cx)**2 +
                            (positions[:, 1] - cy)**2)
        visible   = np.where(dists < self.cfg.fog_end + 2)[0]

        W, H      = self.cfg.width, self.cfg.height
        render_w  = (W - self.cfg.phase_panel_w - 6
                     if self.cfg.show_phase_panel else W)
        margin    = 140

        in_frustum = []
        for i in visible:
            sx, sy = self.proj.project(*positions[i])
            if -margin < sx < render_w + margin and -margin < sy < H + margin:
                in_frustum.append(i)

        in_frustum.sort(key=lambda i: self.proj.depth_key(*positions[i]))

        opaque, transp = [], []
        for i in in_frustum:
            top, left, right, is_t = cell_colours[i]
            (transp if is_t else opaque).append((i, top, left, right))

        if self.cfg.show_grid:
            self._draw_grid()

        for i, top, left, right in opaque:
            self._draw_voxel(self.screen, positions[i], top, left, right,
                             i == self.selected_i)
            if self.cfg.show_triangles:
                self._draw_tri_wire(self.screen, i, frame, tri)

        for i, top, left, right in transp:
            self._draw_voxel(self.overlay, positions[i], top, left, right,
                             i == self.selected_i)
            if self.cfg.show_triangles:
                self._draw_tri_wire(self.overlay, i, frame, tri)

        self.screen.blit(self.overlay, (0, 0))

        if self.cfg.show_dome:
            self._draw_dome()
        if self.cfg.show_phase_panel:
            self._draw_phase_panel(frame, tri)
        if self.cfg.show_witness:
            self._draw_witness(frame)

        self._draw_ui(frame, tri, len(in_frustum))

        pygame.display.flip()

        self.frame_count += 1
        now = time.time()
        if now - self.last_time >= 1.0:
            self.fps        = self.frame_count
            self.frame_count = 0
            self.last_time  = now

        self.clock.tick(self.cfg.target_fps)

    # ── triangle wireframe ────────────────────────────────────────────────────

    def _draw_tri_wire(self, surface, i: int,
                       frame: RenderFrame, tri: TriangleData):
        """
        Draw the actual triangle geometry for cell i, anchored at voxel top-face.

        Three vertices in screen space:
          past_pt    — below centre, depth proportional to |τ|
          future1_pt — offset in the φ₁ direction in the isometric plane
          future2_pt — offset in the φ₂ direction
        """
        pos    = frame.positions[i]
        sx, sy = self.proj.project(*pos)
        mat    = int(frame.materials[i])
        zoom   = self.proj.zoom
        tw     = self.cfg.tile_w      * zoom
        th     = self.cfg.tile_h      * zoom
        vd     = self.cfg.voxel_depth * zoom

        tau    = float(tri.tau[i])
        a1     = float(tri.phi1_abs[i])
        a2     = float(tri.phi2_abs[i])
        p1r    = float(tri.phi1_re[i])
        p1i    = float(tri.phi1_im[i])
        p2r    = float(tri.phi2_re[i])
        p2i    = float(tri.phi2_im[i])

        # Normalise direction vectors
        if a1 > 1e-8:
            d1r, d1i = p1r / a1, p1i / a1
        else:
            d1r, d1i = 1.0, 0.0
        if a2 > 1e-8:
            d2r, d2i = p2r / a2, p2i / a2
        else:
            d2r, d2i = -1.0, 0.0

        # Scale: arms at ≈2× tile_w, past depth at ≈0.85× voxel_depth
        arm_sc  = tw * 2.0
        past_sc = vd * 0.85

        # Centre on top face
        cx_v = sx
        cy_v = sy + int(th)

        # Past vertex: straight down in screen space (z-direction only)
        past_pt = (cx_v, int(cy_v + tau * past_sc))

        # Future vertices: project (d.re, d.im, 0) through isometric transform
        # (dx, dy) world → screen: Δsx = (dx−dy)*tw, Δsy = (dx+dy)*th*0.5
        def future_pt(dr, di, arm):
            dx = dr * arm * arm_sc
            dy = di * arm * arm_sc
            rdx, rdy = self.proj._rot(dx, dy)
            dsx = (rdx - rdy) * tw * 0.5
            dsy = (rdx + rdy) * th * 0.5
            return (int(cx_v + dsx), int(cy_v - dsy))

        f1_pt = future_pt(d1r, d1i, a1)
        f2_pt = future_pt(d2r, d2i, a2)

        col_rgba = TRI_COLS.get(mat, TRI_COLS[3])
        is_alpha = bool(surface.get_flags() & pygame.SRCALPHA)
        col      = col_rgba if is_alpha else col_rgba[:3]

        pygame.draw.line(surface, col, past_pt, f1_pt, 1)
        pygame.draw.line(surface, col, past_pt, f2_pt, 1)
        pygame.draw.line(surface, col, f1_pt,   f2_pt, 1)
        pygame.draw.circle(surface, col, past_pt, 2)

    # ── ζ-θ phase panel ───────────────────────────────────────────────────────

    def _draw_phase_panel(self, frame: RenderFrame, tri: TriangleData):
        """
        Right-side scatter: every cell at (θ, ζ).
          x-axis  θ = arg(φ₁φ̄₂)  ∈ [−π, +π]
          y-axis  ζ = (|φ₁|²−|φ₂|²)|ξ|²

        The retrocausal creation corridor θ = −π/2 is marked in teal.
        Stone/sand/water/air coloured as their material.
        """
        W, H   = self.cfg.width, self.cfg.height
        PW     = self.cfg.phase_panel_w
        px0    = W - PW - 4
        PAD    = 20
        ph     = H - 55 - 2*PAD   # plot height
        pw     = PW - 2*PAD        # plot width
        ox     = px0 + PAD         # left edge of plot
        oy_mid = PAD + ph // 2     # y = 0 line for ζ

        # Background
        bg = pygame.Surface((PW + 4, H - 50), pygame.SRCALPHA)
        bg.fill((8, 14, 28, 210))
        self.screen.blit(bg, (px0, 0))

        # Axes
        pygame.draw.line(self.screen, (25, 45, 75),
                         (ox,      PAD), (ox,      PAD + ph), 1)   # ζ = 0 axis
        pygame.draw.line(self.screen, (25, 45, 75),
                         (ox, oy_mid), (ox + pw, oy_mid), 1)       # θ = 0 axis

        # Creation corridor at θ = −π/2
        def theta_x(t):
            return int(ox + (t + np.pi) / (2 * np.pi) * pw)

        cx_line = theta_x(CREATION_THETA)
        pygame.draw.line(self.screen, (40, 180, 155),
                         (cx_line, PAD), (cx_line, PAD + ph), 1)
        lbl = self.small.render("−π/2", True, (50, 195, 170))
        self.screen.blit(lbl, (cx_line - 12, PAD + ph + 2))

        # Scatter
        theta_arr  = tri.theta
        zeta_arr   = tri.zeta
        mats       = frame.materials
        near_c     = tri.near_creation

        # Auto-scale ζ axis
        zmax = max(float(np.abs(zeta_arr).max()) * 1.1, 0.005)
        zeta_sc = (ph // 2) / zmax

        mat_rgb = {
            0: (148, 136, 122),
            1: (238, 210, 140),
            2: ( 48, 120, 210),
            3: ( 90, 115, 145),
        }

        for i in range(frame.N):
            t  = float(theta_arr[i])
            z  = float(zeta_arr[i])
            m  = int(mats[i])
            sx = theta_x(t)
            sy = int(oy_mid - z * zeta_sc)
            if ox <= sx <= ox + pw and PAD <= sy <= PAD + ph:
                col = mat_rgb.get(m, (80, 80, 80))
                r = 2 if bool(near_c[i]) else 1
                pygame.draw.circle(self.screen, col, (sx, sy), r)

        # Axis labels
        self.screen.blit(self.small.render("−π", True, (70, 95, 130)),
                         (ox - 6,      PAD + ph + 2))
        self.screen.blit(self.small.render("+π", True, (70, 95, 130)),
                         (ox + pw - 12, PAD + ph + 2))
        self.screen.blit(self.small.render("ζ-θ  phase space", True, (95, 135, 175)),
                         (ox, PAD - 15))

    # ── voxel draw ────────────────────────────────────────────────────────────

    def _fog_t(self, pos) -> float:
        d = np.sqrt((pos[0] - self.proj.pan_x)**2 +
                    (pos[1] - self.proj.pan_y)**2)
        return float(np.clip(
            (d - self.cfg.fog_start) /
            (self.cfg.fog_end - self.cfg.fog_start),
            0.0, 1.0))

    def _draw_voxel(self, surface, pos, top, left, right, selected=False):
        sx, sy = self.proj.project(*pos)
        polys  = self.proj.tile_polygon(sx, sy)
        ft     = self._fog_t(pos)
        top, left, right = _fog(top, ft), _fog(left, ft), _fog(right, ft)

        is_alpha = bool(surface.get_flags() & pygame.SRCALPHA)
        if is_alpha:
            pygame.draw.polygon(surface, top,   polys['top'])
            pygame.draw.polygon(surface, left,  polys['left'])
            pygame.draw.polygon(surface, right, polys['right'])
        else:
            pygame.draw.polygon(surface, top[:3],   polys['top'])
            pygame.draw.polygon(surface, left[:3],  polys['left'])
            pygame.draw.polygon(surface, right[:3], polys['right'])

        if selected:
            pygame.draw.polygon(surface, (255, 255, 200, 220),
                                polys['top'], 2)

    # ── witness ───────────────────────────────────────────────────────────────

    def _draw_witness(self, frame: RenderFrame):
        """
        Two witness poles: w1 (gold ⊙) and w2 (rose ⊕).
        Together they define the toroidal axis on S⁶.
        The equatorial saddle between them is where creation is most active.
        """
        W, H         = self.cfg.width, self.cfg.height
        panel_margin = self.cfg.phase_panel_w + 6 if self.cfg.show_phase_panel else 0
        s            = pygame.Surface((W, H), pygame.SRCALPHA)

        def _draw_pole(pos, coh, colour_rgb, symbol, label_offset=(1, -1)):
            sx, sy = self.proj.project(*pos)
            if not (-60 < sx < W - panel_margin + 60 and -60 < sy < H + 60):
                return
            alpha = max(40, min(220, int(coh * 220 + 40)))
            col   = colour_rgb + (alpha,)
            r     = max(6, int(8 * self.proj.zoom))
            pygame.draw.circle(s, col, (sx, sy), r, 1)
            pygame.draw.circle(s, col, (sx, sy), 2)
            arm = r + 4
            pygame.draw.line(s, col, (sx - arm, sy), (sx + arm, sy), 1)
            pygame.draw.line(s, col, (sx, sy - arm), (sx, sy + arm), 1)
            d = int(arm * 0.55)
            dim_col = colour_rgb + (alpha // 2,)
            for dx, dy in [(d, d), (-d, d), (d, -d), (-d, -d)]:
                pygame.draw.line(s, dim_col,
                                 (sx + dx - 2, sy + dy - 2),
                                 (sx + dx + 2, sy + dy + 2), 1)
            lbl_col = colour_rgb if alpha > 80 else tuple(c // 2 for c in colour_rgb)
            lbl = self.small.render(f"{symbol} {coh:.3f}", True, lbl_col)
            ox, oy = label_offset
            self.screen.blit(lbl, (sx + r * ox + 5, sy + r * oy - 8))

        # w1 — gold, the g₂-deviation witness
        from pure_world import states_to_positions
        pos1 = self.world.witness_position
        _draw_pole(pos1, self.world.witness_coherence,   (255, 215,   0), "⊙", (1, -1))

        # w2 — rose, the antipodal pole
        pos2 = states_to_positions(self.world.witness2[np.newaxis])[0]
        _draw_pole(pos2, self.world.witness2_coherence,  (255, 130, 180), "⊕", (1,  1))

        self.screen.blit(s, (0, 0))

    # ── grid, dome ────────────────────────────────────────────────────────────

    def _draw_grid(self):
        step, r = 1, 11   # 1-unit grid = ~1 cell spacing in genesis coords
        col = (22, 38, 58)
        for x in range(-r, r+1, step):
            pygame.draw.line(self.screen, col,
                             self.proj.project(float(x), float(-r), 0),
                             self.proj.project(float(x), float( r), 0), 1)
        for y in range(-r, r+1, step):
            pygame.draw.line(self.screen, col,
                             self.proj.project(float(-r), float(y), 0),
                             self.proj.project(float( r), float(y), 0), 1)

    def _draw_dome(self):
        cx, cy = self.cfg.width // 2, self.cfg.height // 2
        tw = self.cfg.tile_w      * self.proj.zoom
        th = self.cfg.tile_h      * self.proj.zoom
        vd = self.cfg.voxel_depth * self.proj.zoom
        R  = 13.0
        rx = int(R * tw * 1.42)
        ry = int(R * th * 1.42)
        rd = int(R * vd * 0.75)

        s = pygame.Surface((self.cfg.width, self.cfg.height), pygame.SRCALPHA)
        for t in range(3):
            a  = max(0, 55 - t*15)
            ex = max(1, rx - t*4)
            ey = max(1, ry - t*2)
            pygame.draw.ellipse(s, (*DOME_RIM[:3], a),
                                (cx-ex, cy-ey, ex*2, ey*2), 2)
        dome_h = ry + rd
        for t in range(4):
            a  = max(4, 35 - t*9)
            ew = max(1, rx - t*3)
            eh = max(1, dome_h - t*4)
            pygame.draw.arc(s, (*DOME_FILL[:3], a),
                            pygame.Rect(cx-ew, cy-eh, ew*2, eh*2),
                            0, np.pi, 2)
        pygame.draw.ellipse(s, DOME_RIM, (cx-rx, cy-ry, rx*2, ry*2), 1)
        self.screen.blit(s, (0, 0))

    # ── HUD ───────────────────────────────────────────────────────────────────

    def _draw_ui(self, frame: RenderFrame, tri: TriangleData, visible: int):
        self._draw_tau_strip(frame)

        mat_counts = [int((frame.materials == m).sum()) for m in range(4)]
        near_c     = int(tri.near_creation.sum())

        lines = []
        if self.cfg.show_fps:
            lines.append(f"FPS: {self.fps}  step: {frame.step}")
        lines.append(f"cells: {frame.N}  visible: {visible}")
        lines.append(f"mode: {self._mode_names[self.cfg.colour_mode]}  (V)")
        for m, name in enumerate(MATERIAL_NAMES):
            if mat_counts[m]:
                lines.append(f"  {name}: {mat_counts[m]}")
        if near_c:
            lines.append(f"  ∿ creation θ: {near_c}")
        if self.cfg.show_witness:
            wc  = self.world.witness_coherence
            wc2 = self.world.witness2_coherence
            sep = self.world.pole_separation
            lines.append(f"  ⊙ w1: {wc:.4f}  ⊕ w2: {wc2:.4f}")
            lines.append(f"  ∿ pole sep: {sep:.4f}")
        # Convergence scalar Psi
        from pure_world import compute_psi, psi_convergence_rate, is_converged
        psi  = compute_psi(self.world)
        rate = psi_convergence_rate(self.world)
        conv = is_converged(self.world)
        rate_str = f"{rate:.1e}" if rate != float('inf') else "···"
        conv_str = " ✓" if conv else ""
        lines.append(f"  Ψ: {psi:.4f}  dΨ/dt: {rate_str}{conv_str}")
        if self.paused:
            lines.append("── PAUSED ──")

        y = 10
        for line in lines:
            s = self.font.render(line, True, (145, 175, 210))
            self.screen.blit(s, (10, y))
            y += 21

        # Selected cell panel
        if (self.selected_i is not None and
                self._last_frame is not None and
                self.selected_i < frame.N):
            i    = self.selected_i
            mat  = MATERIAL_NAMES[int(frame.materials[i])]
            t_v  = float(frame.tau_abs[i])
            age  = int(frame.ages[i])
            sp   = float(frame.spiral_phase[i])
            pos  = frame.positions[i]
            mv   = float(frame.manifold_vals[i])
            a1   = float(tri.phi1_abs[i])
            a2   = float(tri.phi2_abs[i])
            zv   = float(tri.zeta[i])
            thv  = float(np.degrees(tri.theta[i]))
            area = float(tri.tri_area[i])
            nc   = bool(tri.near_creation[i])

            info = [
                f"▸ {mat}",
                f"  |τ|:     {t_v:.4f}",
                f"  age:     {age} steps",
                f"  θ:       {thv:.1f}°",
                f"  |φ₁|:    {a1:.4f}",
                f"  |φ₂|:    {a2:.4f}",
                f"  ζ:       {zv:.6f}",
                f"  area:    {area:.5f}",
                f"  M(ψ):    {mv:.4f}",
                f"  pos:     ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})",
            ]
            if nc:
                info.append("  ∿ creation corridor")

            y2  = self.cfg.height - 21*len(info) - 56
            bg  = pygame.Surface((230, 21*len(info) + 10), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 135))
            self.screen.blit(bg, (8, y2 - 4))
            for line in info:
                col = ((55, 215, 190) if nc and "∿" in line
                       else (210, 230, 255))
                s = self.small.render(line, True, col)
                self.screen.blit(s, (12, y2))
                y2 += 21

        if self.show_help:
            self._draw_help()

    def _draw_tau_strip(self, frame: RenderFrame):
        if frame.N == 0:
            return
        W, H = self.cfg.width, self.cfg.height
        BAR  = 42
        y0   = H - BAR - 2

        bg = pygame.Surface((W, BAR), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 90))
        self.screen.blit(bg, (0, y0))

        bins = 80
        hist = np.zeros(bins)
        for t in frame.tau_abs:
            b = int(t * bins)
            if b < bins:
                hist[b] += 1
        if hist.max() > 0:
            hist = hist / hist.max()

        bw = W / bins
        for b in range(bins):
            if hist[b] < 0.005:
                continue
            hue = (220 - (b + 0.5) / bins * 160) % 360
            r, g, c = _hsv(hue, 0.60, 0.70)
            h_px = max(1, int(hist[b] * (BAR - 6)))
            pygame.draw.rect(
                self.screen, (r, g, c),
                pygame.Rect(int(b * bw), y0 + BAR - h_px - 2,
                            max(1, int(bw) - 1), h_px))

        for thresh, label, col in [
            (TAU_STONE, 'stone', (148, 136, 122)),
            (TAU_SAND,  'sand',  (238, 210, 140)),
            (TAU_WATER, 'water', ( 48, 120, 210)),
        ]:
            x = int(thresh * W)
            pygame.draw.line(self.screen, col, (x, y0), (x, y0 + BAR), 1)
            self.screen.blit(
                self.small.render(label, True, col), (x + 2, y0 + 2))

    def _draw_help(self):
        lines = [
            "Arrows / WASD    pan",
            "Scroll / +−      zoom",
            "Q / E            rotate view",
            "V                cycle colour mode (5)",
            "T                triangle wireframes",
            "Z                ζ-θ phase panel",
            "W                witness point",
            "G                reference grid",
            "D                crystal dome",
            "Space            pause / resume",
            "R                reset camera",
            "Click            inspect cell",
            "H                this help",
            "ESC              quit",
        ]
        x = self.cfg.width - 260
        y = 10
        bg = pygame.Surface((256, len(lines)*19 + 10), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 130))
        self.screen.blit(bg, (x - 4, y - 4))
        for line in lines:
            s = self.small.render(line, True, (165, 195, 225))
            self.screen.blit(s, (x, y))
            y += 19

    # ── main loop ─────────────────────────────────────────────────────────────

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            if not self.paused:
                self.world = step_world(self.world)
            frame = RenderFrame(self.world)
            tri   = TriangleData(self.world)
            self.render(frame, tri)
        pygame.quit()


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("═══════════════════════════════════════════════════════")
    print("  Eigenspectral World  ·  Triangle Manifold Dynamics")
    print("═══════════════════════════════════════════════════════")
    print()
    print("  Each cell is a triangle on M (τ²+Φ+Ξ²=1):")
    print("    v_past   = τ        geological depth")
    print("    v_future = φ₁, φ₂   two branches of possibility")
    print("    Y breathes it:  tall (stone) ↔ flat (water)")
    print()

    world  = seed_from_island()
    frame0 = RenderFrame(world)
    tri0   = TriangleData(world)
    mats   = frame0.materials
    tau    = frame0.tau_abs

    for m, name in enumerate(MATERIAL_NAMES):
        c = int((mats == m).sum())
        if c:
            avg_tau = float(tau[mats == m].mean())
            avg_arm = float(tri0.arm_mean[mats == m].mean())
            avg_th  = float(np.degrees(tri0.theta[mats == m].mean()))
            print(f"  {name:6s}: {c:4d} cells  "
                  f"|τ|={avg_tau:.3f}  arm={avg_arm:.3f}  θ={avg_th:.0f}°")

    nc = int(tri0.near_creation.sum())
    print(f"\n  In creation corridor (θ ≈ −90°): {nc} cells")
    print()
    print("  Controls:  H = help   T = triangles   Z = phase panel")
    print()

    renderer = EigenRenderer(world)
    renderer.run()
