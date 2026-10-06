# core/atlas.py
"""
The 64-channel Atlas.

Each channel is a scalar temperature of tendency, normalized to a canonical
range. Together they form a coordinate system in which any physical,
biological, social, cultural, economic, environmental, or cognitive entity
can be represented as a point on S^63 (the unit sphere in R^64).

Channel ordering is fixed (indices 0..63). Do not reorder.
Groups are for human readability only; the engine treats them as a flat vector.

Canonical ranges:
  signed:   [-1, +1]  stored as float32, quantized to int8 for storage
  unsigned: [ 0,  1]  stored as float32, quantized to uint8 for storage

Similarity between two entity vectors uses cosine similarity (dot product of
L2-normalized vectors). This is the primary metric for all retrieval,
emergence, and interaction decisions operating in 64D space.
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional


# ---------------------------------------------------------------------------
# Channel descriptor
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Channel:
    index: int
    name: str
    symbol: str
    signed: bool          # True -> range [-1,1]; False -> range [0,1]
    description: str
    group: str

    @property
    def range(self) -> Tuple[float, float]:
        return (-1.0, 1.0) if self.signed else (0.0, 1.0)

    def clamp(self, value: float) -> float:
        lo, hi = self.range
        return float(np.clip(value, lo, hi))

    def to_int8(self, value: float) -> int:
        """Quantize to 8-bit integer for storage."""
        v = self.clamp(value)
        if self.signed:
            return int(np.round((v + 1.0) / 2.0 * 255)) - 128
        else:
            return int(np.round(v * 255))

    def from_int8(self, q: int) -> float:
        """Reconstruct float from 8-bit integer."""
        if self.signed:
            return ((q + 128) / 255.0) * 2.0 - 1.0
        else:
            return q / 255.0


# ---------------------------------------------------------------------------
# Full channel table  (64 entries, indices 0..63)
# ---------------------------------------------------------------------------

_CHANNEL_DEFS: List[Tuple] = [
    # --- Physical / meta (0-9) ---
    (0,  "Energy",              "E",    True,  "Available or flowing energy. Deficit to surplus.",                          "physical"),
    (1,  "TemporalBias",        "tau",  True,  "Planning horizon. -1 impulsive, +1 far-sighted.",                          "physical"),
    (2,  "Entropy",             "S",    False, "Disorder. 0 ordered, 1 chaotic.",                                          "physical"),
    (3,  "Frequency",           "f",    False, "Cyclicity / periodic strength, normalized.",                               "physical"),
    (4,  "Recognition",         "Psi",  True,  "Pattern coherence / identity. -1 camouflaged, +1 self-consistent.",        "physical"),
    (5,  "ConservationFlux",    "Phi",  True,  "Conserved quantity flow. Transport strength.",                             "physical"),
    (6,  "Stability",           "R",    True,  "Mechanical or behavioral stiffness / rigidity.",                           "physical"),
    (7,  "Dissipation",         "D",    False, "Energy loss rate. Viscous, metabolic waste.",                              "physical"),
    (8,  "Coupling",            "K",    False, "Cross-channel interaction strength.",                                      "physical"),
    (9,  "Scale",               "Sig",  True,  "Characteristic scale, log10(m) normalized.",                               "physical"),

    # --- Biological / embodied (10-19) ---
    (10, "Metabolism",          "M",    True,  "Biochemical throughput. Slow to hyper.",                                   "biological"),
    (11, "Reproduction",        "Re",   True,  "Fertility / reproductive drive.",                                          "biological"),
    (12, "Locomotion",          "L",    False, "Mobility bias / agility.",                                                 "biological"),
    (13, "Sensation",           "Se",   False, "Sensory acuity weighting.",                                                "biological"),
    (14, "Immunity",            "Im",   False, "Resilience to perturbation.",                                              "biological"),
    (15, "Homeostasis",         "Ho",   False, "Internal regulation efficacy.",                                            "biological"),
    (16, "GrowthRate",          "Gr",   True,  "Physical growth / development speed.",                                     "biological"),
    (17, "MorphologyBias",      "Mb",   True,  "Shape affinity. -1 elongated, +1 compact.",                                "biological"),
    (18, "Lifespan",            "Lp",   False, "Expected lifetime, normalized.",                                           "biological"),
    (19, "Reactivity",          "Rea",  False, "Reflexive quickness, normalized.",                                         "biological"),

    # --- Social / relational (20-29) ---
    (20, "Affinity",            "A",    True,  "Attraction / liking.",                                                     "social"),
    (21, "Trust",               "T",    True,  "Trustworthiness / belief alignment.",                                      "social"),
    (22, "Status",              "St",   True,  "Social rank / prestige.",                                                  "social"),
    (23, "Cooperation",         "Cr",   False, "Cooperative bias / reciprocity.",                                          "social"),
    (24, "Conflict",            "X",    False, "Antagonistic tendency.",                                                   "social"),
    (25, "LanguageBandwidth",   "Lg",   False, "Communicative complexity.",                                                "social"),
    (26, "MemoryCapacity",      "Mem",  False, "Store and recall strength.",                                               "social"),
    (27, "GroupConformity",     "Gc",   False, "Susceptibility to social norms.",                                          "social"),
    (28, "AllianceFlexibility", "Af",   False, "Willingness to shift group membership.",                                   "social"),
    (29, "GossipFlow",          "Gp",   False, "Rate of social information propagation.",                                  "social"),

    # --- Cultural / symbolic (30-39) ---
    (30, "RitualDensity",       "rho",  False, "Ritual frequency and strength.",                                           "cultural"),
    (31, "MythicAlignment",     "mu",   True,  "Archetypal salience. Signed axis.",                                        "cultural"),
    (32, "TabooStrength",       "th",   False, "Strength of prohibitions.",                                                "cultural"),
    (33, "AestheticBias",       "alp",  True,  "Taste. -1 minimal, +1 ornate.",                                           "cultural"),
    (34, "SymbolicComplexity",  "Sc",   False, "Richness of symbolic systems.",                                            "cultural"),
    (35, "CeremonyCost",        "Cc",   False, "Resource cost of ritual participation.",                                   "cultural"),
    (36, "CulturalMemory",      "Cm",   False, "Shared historical fidelity.",                                              "cultural"),
    (37, "MythicPropagation",   "Mp",   False, "Rate of myth spread and mutation.",                                        "cultural"),
    (38, "Sacrality",           "Sv",   False, "Degree to which environment or objects are sacred.",                       "cultural"),
    (39, "NarrativeMomentum",   "Nm",   False, "Tendency for narratives to drive action.",                                 "cultural"),

    # --- Economic / technological (40-49) ---
    (40, "ResourceAbundance",   "Ra",   False, "Per-area resource richness.",                                              "economic"),
    (41, "Production",          "Pe",   False, "Goods and services per unit input.",                                       "economic"),
    (42, "TradeConnectivity",   "Tc",   False, "Network connectivity for exchange.",                                       "economic"),
    (43, "ToolAffinity",        "Ta",   False, "Tendency to innovate with tools.",                                         "economic"),
    (44, "CraftSkill",          "Crf",  False, "Material skill level.",                                                    "economic"),
    (45, "EnergyInfrastructure","Ei",   False, "Energy distribution capacity.",                                            "economic"),
    (46, "InformationFidelity", "Ifd",  False, "Reliability of records and communication.",                                "economic"),
    (47, "MarketVolatility",    "Mv",   False, "Economic fluctuation amplitude.",                                          "economic"),
    (48, "LaborMobility",       "Lm",   False, "Ease of workforce movement.",                                              "economic"),
    (49, "WealthDisparity",     "Wd",   False, "Gini-normalized wealth concentration.",                                    "economic"),

    # --- Environment / geology / materials (50-59) ---
    (50, "TerrainRugosity",     "Trg",  False, "Roughness / walkability.",                                                 "environment"),
    (51, "Hydrology",           "Hy",   False, "Water flow and availability.",                                             "environment"),
    (52, "SoilFertility",       "Fert", False, "Plant support capacity.",                                                  "environment"),
    (53, "SeismicStress",       "Q",    False, "Tectonic tension.",                                                        "environment"),
    (54, "ErosionRate",         "Er",   False, "Landscape change rate.",                                                   "environment"),
    (55, "MineralConductivity", "Mc",   True,  "Electrical and thermal conduction, normalized.",                           "environment"),
    (56, "Corrosion",           "Co",   False, "Chemical weathering susceptibility.",                                      "environment"),
    (57, "Porosity",            "Pr",   False, "Fluid storage capacity.",                                                  "environment"),
    (58, "VegetationComplexity","Vc",   False, "Local biodiversity index.",                                                "environment"),
    (59, "MicrostructureScale", "Ms",   True,  "Characteristic grain size, log10(m) normalized.",                          "environment"),

    # --- Cognitive / collective (60-63) ---
    (60, "Creativity",          "Crv",  False, "Propensity to generate novel forms.",                                      "cognitive"),
    (61, "CollectiveAwareness", "Ca",   False, "Shared situational awareness.",                                            "cognitive"),
    (62, "Autonomy",            "Au",   False, "Independence from external control.",                                      "cognitive"),
    (63, "RetrocausalBias",     "Rc",   True,  "Degree to which expected futures influence present state.",                "cognitive"),
]

DIM = 64  # canonical dimensionality

# Build lookup structures
CHANNELS: List[Channel] = []
BY_INDEX: Dict[int, Channel] = {}
BY_NAME:  Dict[str, Channel] = {}
BY_SYMBOL: Dict[str, Channel] = {}
GROUPS: Dict[str, List[int]] = {}

for _row in _CHANNEL_DEFS:
    _ch = Channel(index=_row[0], name=_row[1], symbol=_row[2],
                  signed=_row[3], description=_row[4], group=_row[5])
    CHANNELS.append(_ch)
    BY_INDEX[_ch.index] = _ch
    BY_NAME[_ch.name]   = _ch
    BY_SYMBOL[_ch.symbol] = _ch
    GROUPS.setdefault(_ch.group, []).append(_ch.index)

assert len(CHANNELS) == DIM, f"Expected {DIM} channels, got {len(CHANNELS)}"


# ---------------------------------------------------------------------------
# AtlasVector: a point in R^64 representing one entity's semantic state
# ---------------------------------------------------------------------------

class AtlasVector:
    """
    A 64-dimensional real vector representing an entity's semantic identity.

    Internal representation: float32 array of length 64, each component
    in its channel's canonical range.

    For similarity operations, use normalized() which returns the L2-unit
    vector on S^63. Raw channel values are preserved for editing and
    display; the normalized form is used for dot-product similarity.
    """

    __slots__ = ("_data",)

    def __init__(self, data: Optional[np.ndarray] = None):
        if data is None:
            self._data = np.zeros(DIM, dtype=np.float32)
        else:
            arr = np.asarray(data, dtype=np.float32)
            if arr.shape != (DIM,):
                raise ValueError(f"AtlasVector requires shape ({DIM},), got {arr.shape}")
            self._data = arr.copy()

    # ------------------------------------------------------------------
    # Channel access
    # ------------------------------------------------------------------

    def get(self, index: int) -> float:
        return float(self._data[index])

    def set(self, index: int, value: float) -> None:
        ch = BY_INDEX[index]
        self._data[index] = ch.clamp(value)

    def set_by_name(self, name: str, value: float) -> None:
        self.set(BY_NAME[name].index, value)

    def get_by_name(self, name: str) -> float:
        return self.get(BY_NAME[name].index)

    def set_group(self, group: str, values: np.ndarray) -> None:
        """Set all channels in a group from a values array."""
        indices = GROUPS[group]
        for i, idx in enumerate(indices):
            self.set(idx, float(values[i]))

    # ------------------------------------------------------------------
    # Arithmetic and similarity
    # ------------------------------------------------------------------

    def normalized(self) -> np.ndarray:
        """L2-normalized unit vector on S^63."""
        norm = np.linalg.norm(self._data)
        if norm < 1e-12:
            v = np.zeros(DIM, dtype=np.float32)
            v[0] = 1.0
            return v
        return self._data / norm

    def cosine_similarity(self, other: "AtlasVector") -> float:
        """Cosine similarity in [-1, 1]. Primary semantic distance metric."""
        return float(np.dot(self.normalized(), other.normalized()))

    def geodesic_to(self, other: "AtlasVector", t: float) -> "AtlasVector":
        """
        SLERP on S^63 between self and other.
        t=0 -> self, t=1 -> other.
        """
        v1 = self.normalized()
        v2 = other.normalized()
        dot = np.clip(np.dot(v1, v2), -1.0, 1.0)
        omega = np.arccos(dot)
        if abs(omega) < 1e-10:
            return AtlasVector(self._data)
        result = (np.sin((1 - t) * omega) * v1 +
                  np.sin(t * omega) * v2) / np.sin(omega)
        # Scale back to original magnitude range
        mag = (1 - t) * np.linalg.norm(self._data) + t * np.linalg.norm(other._data)
        return AtlasVector(result * mag)

    def slerp(self, other: "AtlasVector", t: float) -> "AtlasVector":
        """Alias for geodesic_to()."""
        return self.geodesic_to(other, t)

    def blend(self, other: "AtlasVector", t: float) -> "AtlasVector":
        """Linear interpolation (flat blend, not spherical)."""
        return AtlasVector((1 - t) * self._data + t * other._data)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_array(self) -> np.ndarray:
        return self._data.copy()

    def to_int8(self) -> np.ndarray:
        """64-byte quantized representation."""
        result = np.zeros(DIM, dtype=np.int8)
        for ch in CHANNELS:
            result[ch.index] = ch.to_int8(float(self._data[ch.index]))
        return result

    @classmethod
    def from_int8(cls, arr: np.ndarray) -> "AtlasVector":
        data = np.zeros(DIM, dtype=np.float32)
        for ch in CHANNELS:
            data[ch.index] = ch.from_int8(int(arr[ch.index]))
        return cls(data)

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "AtlasVector":
        """Construct from {channel_name: value} dict. Missing channels = 0."""
        v = cls()
        for name, val in d.items():
            if name in BY_NAME:
                v.set(BY_NAME[name].index, val)
        return v

    def to_dict(self) -> Dict[str, float]:
        return {ch.name: float(self._data[ch.index]) for ch in CHANNELS}

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def summary(self, top_n: int = 8) -> str:
        """Return the top_n channels by absolute magnitude."""
        items = [(abs(float(self._data[ch.index])), ch.name, ch.symbol, float(self._data[ch.index])) 
                 for ch in CHANNELS]
        items.sort(reverse=True, key=lambda x: x[0])  # Sort by magnitude
        lines = []
        for mag, name, sym, val in items[:top_n]:
            lines.append(f"  {name:22s} ({sym:4s}) = {val:+.4f}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        norm = np.linalg.norm(self._data)
        return f"AtlasVector(norm={norm:.4f}, nonzero={int(np.sum(self._data != 0))})"


# ---------------------------------------------------------------------------
# Aggregation operations on collections of AtlasVectors
# ---------------------------------------------------------------------------

def aggregate(vectors: List[AtlasVector],
              weights: Optional[np.ndarray] = None) -> AtlasVector:
    """
    Weighted mean of a list of AtlasVectors.
    Default weights are uniform. Result is NOT normalized (preserves magnitude).
    """
    if not vectors:
        return AtlasVector()
    n = len(vectors)
    if weights is None:
        weights = np.ones(n, dtype=np.float32) / n
    else:
        weights = np.asarray(weights, dtype=np.float32)
        weights = weights / (weights.sum() + 1e-12)

    result = np.zeros(DIM, dtype=np.float32)
    for w, v in zip(weights, vectors):
        result += w * v.to_array()
    return AtlasVector(result)


def diffuse(field: Dict[int, AtlasVector],
            adjacency: Dict[int, List[int]],
            alpha: float = 0.1) -> Dict[int, AtlasVector]:
    """
    One step of cultural diffusion over a field of AtlasVectors.

    field:     {node_id: AtlasVector}
    adjacency: {node_id: [neighbor_ids]}
    alpha:     diffusion coefficient in (0, 1)

    Each node's vector moves alpha fraction toward the mean of its neighbors.
    This implements the culture aggregation formula from the Atlas specification.
    """
    new_field = {}
    for node_id, vec in field.items():
        neighbors = adjacency.get(node_id, [])
        if not neighbors:
            new_field[node_id] = AtlasVector(vec.to_array())
            continue
        neighbor_vecs = [field[n] for n in neighbors if n in field]
        if not neighbor_vecs:
            new_field[node_id] = AtlasVector(vec.to_array())
            continue
        mean_neighbor = aggregate(neighbor_vecs)
        blended = vec.blend(mean_neighbor, alpha)
        new_field[node_id] = blended
    return new_field


def nearest(query: AtlasVector,
            library: Dict[str, AtlasVector],
            top_k: int = 3) -> List[Tuple[str, float]]:
    """
    Find the top_k nearest vectors in library to query by cosine similarity.
    Returns [(name, similarity), ...] sorted descending.
    """
    q = query.normalized()
    scores = []
    for name, vec in library.items():
        sim = float(np.dot(q, vec.normalized()))
        scores.append((name, sim))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]
