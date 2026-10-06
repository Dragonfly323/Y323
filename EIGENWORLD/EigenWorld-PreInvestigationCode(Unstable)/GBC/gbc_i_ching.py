"""
gbc_i_ching.py
I Ching hexagram encoding for the 64-channel Atlas.

The 64 hexagrams of the I Ching form a complete basis for a 64D space.
Each hexagram is a 6-bit binary pattern (yin/yang lines) that can be mapped
to an Atlas channel. This provides a natural, interpretable basis with
3000 years of accumulated wisdom.

The structure:
- 8 trigrams (3 lines each) → 64 hexagrams (6 lines each)
- Upper trigram = Heaven/Earth/etc., Lower trigram = same
- Each hexagram has a meaning, an image, a judgment
- Mutual gua (interacting hexagram) reveals hidden dynamics between futures

We map each Atlas channel to a hexagram, so every 64D vector becomes
a weighted combination of hexagrams. This is not metaphor — it's
literally the same mathematics as any other orthonormal basis.
"""

import jax
import jax.numpy as jnp
import numpy as np
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass, field
import json
from pathlib import Path


# -----------------------------------------------------------------------
# The 8 trigrams (bagua)
# -----------------------------------------------------------------------

@dataclass
class Trigram:
    """A 3-line trigram (ba gua)."""
    name: str                    # English name
    chinese: str                 # Chinese character
    pinyin: str                  # Pronunciation
    binary: Tuple[int, int, int] # 3-bit pattern (0=yin, 1=yang)
    element: str                 # Associated element
    direction: str               # Associated direction
    meaning: str                  # Core meaning

TRIGRAMS = [
    Trigram("Heaven", "乾", "qián", (1, 1, 1), "metal", "northwest", "creative, strong"),
    Trigram("Earth", "坤", "kūn", (0, 0, 0), "earth", "southwest", "receptive, yielding"),
    Trigram("Thunder", "震", "zhèn", (0, 0, 1), "wood", "east", "arousing, movement"),
    Trigram("Wind/Wood", "巽", "xùn", (1, 1, 0), "wood", "southeast", "gentle, penetrating"),
    Trigram("Water", "坎", "kǎn", (0, 1, 0), "water", "north", "dangerous, abysmal"),
    Trigram("Fire", "離", "lí", (1, 0, 1), "fire", "south", "clinging, bright"),
    Trigram("Mountain", "艮", "gèn", (1, 0, 0), "earth", "northeast", "still, immovable"),
    Trigram("Lake", "兌", "duì", (0, 1, 1), "metal", "west", "joyous, reflective"),
]

# Index trigrams by binary pattern
TRIGRAM_BY_BINARY = {t.binary: t for t in TRIGRAMS}


# -----------------------------------------------------------------------
# The 64 hexagrams
# -----------------------------------------------------------------------

@dataclass
class Hexagram:
    """A 6-line hexagram (gua)."""
    number: int                   # King Wen order (1-64)
    name: str                     # English name
    chinese: str                  # Chinese characters
    pinyin: str                   # Pronunciation
    upper_trigram: Trigram        # Upper 3 lines
    lower_trigram: Trigram        # Lower 3 lines
    binary: Tuple[int, ...]       # 6-bit pattern (line1..line6)
    judgment: str                  # Core judgment
    image: str = ""                # The image (from the wings)
    
    @property
    def binary_string(self) -> str:
        """Binary as string (1=yang, 0=yin)."""
        return ''.join(str(b) for b in self.binary)
    
    @property
    def lines_yang(self) -> int:
        """Number of yang lines."""
        return sum(self.binary)
    
    @property
    def changing_lines(self) -> List[int]:
        """Lines that would change in a moving hexagram."""
        # In practice, this would be computed from context
        return []
    
    @property
    def nuclear_lower(self) -> Tuple[int, int, int]:
        """Lower trigram of the nuclear (mutual) hexagram: lines 2,3,4."""
        return self.binary[1:4]
    
    @property
    def nuclear_upper(self) -> Tuple[int, int, int]:
        """Upper trigram of the nuclear (mutual) hexagram: lines 3,4,5."""
        return self.binary[2:5]


def build_hexagrams() -> Dict[int, Hexagram]:
    """
    Build the 64 hexagrams with their traditional meanings.
    
    This is the King Wen sequence (文王卦序), the most common ordering.
    Each hexagram is built from upper and lower trigrams.
    """
    hexagrams = {}
    
    # Precompute all 64 combinations
    for i, upper in enumerate(TRIGRAMS):
        for j, lower in enumerate(TRIGRAMS):
            number = i * 8 + j + 1
            binary = upper.binary + lower.binary
            
            # Traditional names (simplified — would need full list)
            # This is a placeholder — in practice, we'd load from a JSON file
            name_map = {
                1: ("The Creative", "乾", "qián", "Great indeed is the sublimity of the Creative"),
                2: ("The Receptive", "坤", "kūn", "Great indeed is the sublimity of the Receptive"),
                3: ("Difficulty at the Beginning", "屯", "zhūn", "Difficulty at the Beginning works supreme success"),
                4: ("Youthful Folly", "蒙", "méng", "Youthful Folly has success"),
                5: ("Waiting", "需", "xū", "Waiting brings about success"),
                6: ("Conflict", "訟", "sòng", "Conflict brings about success"),
                7: ("The Army", "師", "shī", "The Army needs perseverance"),
                8: ("Holding Together", "比", "bǐ", "Holding Together brings good fortune"),
                9: ("Small Taming", "小畜", "xiǎo chù", "Small Taming works"),
                10: ("Treading", "履", "lǚ", "Treading brings success"),
                11: ("Peace", "泰", "tài", "Peace brings small departures"),
                12: ("Standstill", "否", "pǐ", "Standstill brings evil"),
                13: ("Fellowship", "同人", "tóng rén", "Fellowship brings success"),
                14: ("Great Possession", "大有", "dà yǒu", "Great Possession brings success"),
                15: ("Modesty", "謙", "qiān", "Modesty brings success"),
                16: ("Enthusiasm", "豫", "yù", "Enthusiasm brings success"),
                17: ("Following", "隨", "suí", "Following brings supreme success"),
                18: ("Work on Decay", "蠱", "gǔ", "Work on Decay brings success"),
                19: ("Approach", "臨", "lín", "Approach brings supreme success"),
                20: ("Contemplation", "觀", "guān", "Contemplation brings success"),
                21: ("Biting Through", "噬嗑", "shì kè", "Biting Through brings success"),
                22: ("Grace", "賁", "bì", "Grace brings success"),
                23: ("Splitting Apart", "剝", "bō", "Splitting Apart brings misfortune"),
                24: ("Return", "復", "fù", "Return brings success"),
                25: ("Innocence", "無妄", "wú wàng", "Innocence brings supreme success"),
                26: ("Great Taming", "大畜", "dà chù", "Great Taming brings success"),
                27: ("Mouth Corners", "頤", "yí", "Mouth Corners brings good fortune"),
                28: ("Great Exceeding", "大過", "dà guò", "Great Exceeding brings success"),
                29: ("The Abysmal", "坎", "kǎn", "The Abysmal brings success"),
                30: ("The Clinging", "離", "lí", "The Clinging brings success"),
                31: ("Influence", "咸", "xián", "Influence brings success"),
                32: ("Duration", "恆", "héng", "Duration brings success"),
                33: ("Retreat", "遯", "dùn", "Retreat brings success"),
                34: ("Great Power", "大壯", "dà zhuàng", "Great Power brings success"),
                35: ("Progress", "晉", "jìn", "Progress brings success"),
                36: ("Darkening of Light", "明夷", "míng yí", "Darkening of Light brings success"),
                37: ("The Family", "家人", "jiā rén", "The Family brings success"),
                38: ("Opposition", "睽", "kuí", "Opposition brings success"),
                39: ("Obstruction", "蹇", "jiǎn", "Obstruction brings success"),
                40: ("Deliverance", "解", "xiè", "Deliverance brings success"),
                41: ("Decrease", "損", "sǔn", "Decrease brings success"),
                42: ("Increase", "益", "yì", "Increase brings success"),
                43: ("Breakthrough", "夬", "guài", "Breakthrough brings success"),
                44: ("Coming to Meet", "姤", "gòu", "Coming to Meet brings success"),
                45: ("Gathering Together", "萃", "cuì", "Gathering Together brings success"),
                46: ("Pushing Upward", "升", "shēng", "Pushing Upward brings success"),
                47: ("Oppression", "困", "kùn", "Oppression brings success"),
                48: ("The Well", "井", "jǐng", "The Well brings success"),
                49: ("Revolution", "革", "gé", "Revolution brings success"),
                50: ("The Cauldron", "鼎", "dǐng", "The Cauldron brings success"),
                51: ("The Arousing", "震", "zhèn", "The Arousing brings success"),
                52: ("The Still", "艮", "gèn", "The Still brings success"),
                53: ("Development", "漸", "jiàn", "Development brings success"),
                54: ("The Marrying Maiden", "歸妹", "guī mèi", "The Marrying Maiden brings misfortune"),
                55: ("Abundance", "豐", "fēng", "Abundance brings success"),
                56: ("The Wanderer", "旅", "lǚ", "The Wanderer brings success"),
                57: ("The Gentle", "巽", "xùn", "The Gentle brings success"),
                58: ("The Joyous", "兌", "duì", "The Joyous brings success"),
                59: ("Dispersion", "渙", "huàn", "Dispersion brings success"),
                60: ("Limitation", "節", "jié", "Limitation brings success"),
                61: ("Inner Truth", "中孚", "zhōng fú", "Inner Truth brings success"),
                62: ("Small Exceeding", "小過", "xiǎo guò", "Small Exceeding brings success"),
                63: ("After Completion", "既濟", "jì jì", "After Completion brings success"),
                64: ("Before Completion", "未濟", "wèi jì", "Before Completion brings success"),
            }
            
            if number in name_map:
                name, chinese, pinyin, judgment = name_map[number]
            else:
                name = f"Hexagram {number}"
                chinese = ""
                pinyin = ""
                judgment = f"Judgment for {name}"
            
            # Image would come from the Wings
            image = f"The image of {name}"
            
            hexagrams[number] = Hexagram(
                number=number,
                name=name,
                chinese=chinese,
                pinyin=pinyin,
                upper_trigram=upper,
                lower_trigram=lower,
                binary=binary,
                judgment=judgment,
                image=image
            )
    
    return hexagrams


# -----------------------------------------------------------------------
# Mutual Gua (Nuclear Hexagram) — The Hidden Dynamic
# -----------------------------------------------------------------------

class MutualGua:
    """
    The mutual gua (互卦, hù guà) — the interacting or nuclear hexagram.
    
    Every hexagram contains within itself a second hidden hexagram,
    formed by its inner lines:
    - Lower mutual = lines 2,3,4
    - Upper mutual = lines 3,4,5
    
    The mutual gua reveals the hidden dynamic, the underlying process,
    the "why" behind the surface appearance.
    
    In our framework, this is exactly the coherence Φ between two futures:
    φ₁ and φ₂ interact to produce a third thing — the mutual gua.
    """
    
    def __init__(self, basis: 'IChingBasis'):
        self.basis = basis
        self.cache = {}  # Cache computed mutual guas
    
    def of_hexagram(self, hexagram: Hexagram) -> Hexagram:
        """
        Compute the mutual gua of a single hexagram.
        
        The mutual gua uses:
        - Lower mutual = lines 2,3,4 of original
        - Upper mutual = lines 3,4,5 of original
        """
        # Check cache
        if hexagram.number in self.cache:
            return self.cache[hexagram.number]
        
        # Extract nuclear trigrams
        lower_nuclear = hexagram.nuclear_lower
        upper_nuclear = hexagram.nuclear_upper
        
        # Find corresponding trigrams
        lower_trigram = TRIGRAM_BY_BINARY[lower_nuclear]
        upper_trigram = TRIGRAM_BY_BINARY[upper_nuclear]
        
        # Find hexagram with these trigrams
        for h in self.basis.hexagram_list:
            if h.upper_trigram == upper_trigram and h.lower_trigram == lower_trigram:
                self.cache[hexagram.number] = h
                return h
        
        # Fallback (should never happen with valid hexagrams)
        return hexagram
    
    def of_pair(self, hex1: Hexagram, hex2: Hexagram, 
                weight1: float = 0.5, weight2: float = 0.5) -> Hexagram:
        """
        Compute the mutual gua of a pair of hexagrams.
        
        This represents the hidden dynamic between two interacting forces.
        In our framework, this is the coherence Φ between two futures.
        
        The lines of the mutual gua are determined by the weighted
        combination of the two hexagrams' nuclear trigrams.
        """
        # Get nuclear trigrams of both
        lower1 = hex1.nuclear_lower
        upper1 = hex1.nuclear_upper
        lower2 = hex2.nuclear_lower
        upper2 = hex2.nuclear_upper
        
        # Weighted combination of lines
        combined_lower = []
        combined_upper = []
        
        for i in range(3):
            # Weighted average of the two trigrams' lines
            val_lower = weight1 * lower1[i] + weight2 * lower2[i]
            val_upper = weight1 * upper1[i] + weight2 * upper2[i]
            
            combined_lower.append(1 if val_lower > 0.5 else 0)
            combined_upper.append(1 if val_upper > 0.5 else 0)
        
        # Convert to tuples for lookup
        lower_tuple = tuple(combined_lower)
        upper_tuple = tuple(combined_upper)
        
        # Find corresponding trigrams
        lower_trigram = TRIGRAM_BY_BINARY[lower_tuple]
        upper_trigram = TRIGRAM_BY_BINARY[upper_tuple]
        
        # Find hexagram with these trigrams
        for h in self.basis.hexagram_list:
            if h.upper_trigram == upper_trigram and h.lower_trigram == lower_trigram:
                return h
        
        # Fallback
        return hex1
    
    def from_futures(self, phi1_atlas: jnp.ndarray, phi2_atlas: jnp.ndarray,
                     coherence: Optional[float] = None) -> Tuple[Hexagram, float]:
        """
        Compute the mutual gua from two future Atlas vectors.
        
        This is the hidden dynamic between φ₁ and φ₂ — exactly the coherence Φ.
        
        Returns:
            (mutual_hexagram, interaction_strength)
        """
        # Get dominant hexagram of each future
        h1, w1 = self.basis.dominant_hexagram(phi1_atlas)
        h2, w2 = self.basis.dominant_hexagram(phi2_atlas)
        
        # Normalize weights
        total = w1 + w2
        w1_norm = w1 / total
        w2_norm = w2 / total
        
        # Compute mutual gua from the pair
        mutual = self.of_pair(h1, h2, w1_norm, w2_norm)
        
        # Interaction strength (if coherence provided, use it)
        strength = coherence if coherence is not None else (w1_norm * w2_norm)
        
        return mutual, strength
    
    def interpret(self, primary: Hexagram, mutual: Hexagram, 
                 strength: float) -> str:
        """
        Interpret the relationship between primary and mutual hexagrams.
        
        The primary is the surface appearance; the mutual is the hidden dynamic.
        Together, they tell the complete story.
        """
        return f"""
╔══════════════════════════════════════════════════════════╗
║                 MUTUAL GUA INTERPRETATION                ║
╚══════════════════════════════════════════════════════════╝

Primary Hexagram: {primary.number}. {primary.name}
  Surface appearance: {primary.judgment}
  {primary.image}

Mutual Hexagram: {mutual.number}. {mutual.name}
  Hidden dynamic: {mutual.judgment}
  {mutual.image}

Interaction strength: {strength:.3f}

The mutual gua reveals what is happening beneath the surface.
{'The futures are strongly coupled — their interaction dominates' if strength > 0.7 else
 'The futures interact moderately' if strength > 0.3 else
 'The futures are nearly independent — the hidden dynamic is weak'}
"""
    
    def coherence_reading(self, phi1_atlas: jnp.ndarray, phi2_atlas: jnp.ndarray,
                          coherence_value: float) -> str:
        """
        Full reading of coherence as mutual gua.
        """
        mutual, strength = self.from_futures(phi1_atlas, phi2_atlas, coherence_value)
        
        # Get primary hexagrams of the two futures
        h1, w1 = self.basis.dominant_hexagram(phi1_atlas)
        h2, w2 = self.basis.dominant_hexagram(phi2_atlas)
        
        return f"""
╔══════════════════════════════════════════════════════════╗
║                 COHERENCE AS MUTUAL GUA                  ║
╚══════════════════════════════════════════════════════════╝

First Future (φ₁):
  {h1.number}. {h1.name} (weight: {w1:.3f})
  {h1.judgment}

Second Future (φ₂):
  {h2.number}. {h2.name} (weight: {w2:.3f})
  {h2.judgment}

Coherence Φ = {coherence_value:.3f}

The hidden dynamic between these futures:
  → {mutual.number}. {mutual.name}
  {mutual.judgment}
  {mutual.image}

Interpretation:
{'Strong coupling — the futures are intertwined' if coherence_value > 0.7 else
 'Moderate interaction' if coherence_value > 0.3 else
 'Weak coupling — the futures evolve independently'}
"""


# -----------------------------------------------------------------------
# Hexagram basis for Atlas
# -----------------------------------------------------------------------

class IChingBasis:
    """
    Maps between Atlas 64D vectors and I Ching hexagram space.
    
    Each Atlas channel corresponds to a hexagram. The value in that channel
    is the "weight" of that hexagram in the current state.
    
    This is a linear basis: any 64D vector v can be written as
    v = sum_i w_i * h_i, where h_i are the hexagram basis vectors.
    """
    
    def __init__(self):
        self.hexagrams = build_hexagrams()
        self.hexagram_list = [self.hexagrams[i] for i in range(1, 65)]
        
        # Build basis vectors (one-hot encoding of hexagrams)
        self.basis_vectors = jnp.eye(64, dtype=jnp.float32)
        
        # Cache binary patterns for fast lookup
        self.binary_patterns = jnp.array([
            [float(b) for b in h.binary] for h in self.hexagram_list
        ], dtype=jnp.float32)  # (64, 6)
        
        # Initialize mutual gua calculator
        self.mutual = MutualGua(self)
    
    def hexagram_to_channel(self, hexagram_number: int) -> int:
        """Map hexagram number (1-64) to Atlas channel index (0-63)."""
        return hexagram_number - 1
    
    def channel_to_hexagram(self, channel: int) -> Hexagram:
        """Map Atlas channel index to hexagram."""
        return self.hexagram_list[channel]
    
    def atlas_to_hexagram_weights(self, atlas_vec: jnp.ndarray) -> Dict[Hexagram, float]:
        """
        Convert Atlas vector to dictionary of hexagram weights.
        
        Args:
            atlas_vec: (64,) float array (AtlasVector.to_array())
        
        Returns:
            Dict mapping Hexagram objects to their weights
        """
        weights = {}
        for i, weight in enumerate(atlas_vec):
            if abs(weight) > 1e-6:  # Only non-zero weights
                weights[self.hexagram_list[i]] = float(weight)
        return weights
    
    def hexagram_weights_to_atlas(self, weights: Dict[Hexagram, float]) -> jnp.ndarray:
        """
        Convert hexagram weights back to Atlas vector.
        """
        vec = jnp.zeros(64, dtype=jnp.float32)
        for hexagram, weight in weights.items():
            idx = self.hexagram_to_channel(hexagram.number)
            vec = vec.at[idx].set(weight)
        return vec
    
    def dominant_hexagram(self, atlas_vec: jnp.ndarray) -> Tuple[Hexagram, float]:
        """
        Return the hexagram with highest weight.
        """
        idx = jnp.argmax(jnp.abs(atlas_vec))
        return self.hexagram_list[idx], float(atlas_vec[idx])
    
    def top_hexagrams(self, atlas_vec: jnp.ndarray, k: int = 5) -> List[Tuple[Hexagram, float]]:
        """
        Return the k hexagrams with highest absolute weights.
        """
        abs_weights = jnp.abs(atlas_vec)
        top_indices = jnp.argsort(abs_weights)[-k:][::-1]
        
        result = []
        for idx in top_indices:
            result.append((self.hexagram_list[idx], float(atlas_vec[idx])))
        return result
    
    def binary_decomposition(self, atlas_vec: jnp.ndarray) -> jnp.ndarray:
        """
        Decompose Atlas vector into hexagram binary patterns.
        
        Returns:
            (64, 6) array where each row is the binary pattern of a hexagram,
            weighted by the Atlas value.
        """
        # atlas_vec: (64,)
        # binary_patterns: (64, 6)
        # Result: (64, 6) with each row = atlas_vec[i] * binary_patterns[i]
        return atlas_vec[:, None] * self.binary_patterns
    
    def reconstruct_from_binary(self, binary_weights: jnp.ndarray) -> jnp.ndarray:
        """
        Reconstruct Atlas vector from weighted binary patterns.
        
        Args:
            binary_weights: (64, 6) array of weighted binary patterns
        
        Returns:
            (64,) Atlas vector
        """
        # Sum along binary dimension to recover weights
        return jnp.sum(binary_weights, axis=1)
    
    def to_reading(self, atlas_vec: jnp.ndarray, 
                   include_mutual: bool = True,
                   moving_lines: Optional[List[int]] = None) -> str:
        """
        Generate an I Ching reading from an Atlas vector.
        
        This is where the mathematics meets meaning. The weights determine
        which hexagrams are present, and moving lines indicate change.
        
        If include_mutual is True, also show the mutual gua (hidden dynamic).
        """
        dominant, weight = self.dominant_hexagram(atlas_vec)
        top = self.top_hexagrams(atlas_vec, 3)
        
        lines = []
        for h, w in top:
            lines.append(f"  {h.number:2d}. {h.name:20s} ({h.chinese:4s}): {w:+.3f}")
        
        reading = f"""
╔══════════════════════════════════════════════════════════╗
║                    I CHING READING                       ║
╚══════════════════════════════════════════════════════════╝

Primary Hexagram: {dominant.number}. {dominant.name} ({dominant.chinese})
  {dominant.judgment}
  {dominant.image}

Supporting influences:
{chr(10).join(lines)}

Binary pattern: {dominant.binary_string}
Upper trigram: {dominant.upper_trigram.name} ({dominant.upper_trigram.meaning})
Lower trigram: {dominant.lower_trigram.name} ({dominant.lower_trigram.meaning})

The weight {weight:.3f} indicates the strength of this influence.
"""
        
        if include_mutual:
            # Compute mutual gua of the dominant hexagram
            mutual = self.mutual.of_hexagram(dominant)
            
            # Interaction strength from the spread of weights
            strength = 1.0 - (jnp.std(atlas_vec) / jnp.mean(jnp.abs(atlas_vec) + 1e-8))
            
            reading += f"""
Hidden Dynamic (Mutual Gua):
  {mutual.number}. {mutual.name} ({mutual.chinese})
  {mutual.judgment}
  {mutual.image}
  
The mutual gua reveals what is happening beneath the surface.
"""
        
        return reading


# -----------------------------------------------------------------------
# Agentic Atlas with I Ching
# -----------------------------------------------------------------------

class IChingAgent:
    """
    An agent whose identity is a weighted combination of hexagrams.
    
    The agent's decisions are interpreted through the I Ching:
    - State = current Atlas vector (hexagram weights)
    - Action = changing lines → new hexagram
    - Memory = past hexagrams
    - Culture = shared hexagram patterns across agents
    
    The mutual gua reveals the hidden dynamics of the agent's situation.
    """
    
    def __init__(self, name: str, initial_weights: Optional[Dict[Hexagram, float]] = None):
        self.name = name
        self.basis = IChingBasis()
        
        if initial_weights is None:
            # Default: all hexagrams equally
            self.atlas = jnp.ones(64, dtype=jnp.float32) / 64.0
        else:
            self.atlas = self.basis.hexagram_weights_to_atlas(initial_weights)
        
        self.history = []  # List of past Atlas vectors
        self.memory = []   # List of significant hexagrams
    
    @property
    def dominant(self) -> Tuple[Hexagram, float]:
        """Current dominant hexagram."""
        return self.basis.dominant_hexagram(self.atlas)
    
    @property
    def mutual(self) -> Hexagram:
        """The mutual gua of the current state — hidden dynamic."""
        dom, _ = self.dominant
        return self.basis.mutual.of_hexagram(dom)
    
    def update(self, delta: jnp.ndarray):
        """
        Update agent state by adding delta to Atlas vector.
        """
        self.history.append(self.atlas.copy())
        self.atlas = self.atlas + delta
        # Normalize to unit sphere
        self.atlas = self.atlas / jnp.linalg.norm(self.atlas)
    
    def consult(self, question: str) -> str:
        """
        Consult the I Ching about a question.
        
        The answer is generated from the current Atlas state,
        including the mutual gua for hidden dynamics.
        """
        reading = self.basis.to_reading(self.atlas, include_mutual=True)
        
        return f"""
Question: {question}

{reading}

The response emerges from the weighted interplay of hexagrams in your current state.
The mutual gua shows the hidden forces at work.
"""
    
    def changing_line(self, line_idx: int, new_value: float):
        """
        Change a specific line (hexagram channel) in the Atlas.
        This represents a transformation in the agent's identity.
        """
        old = self.atlas[line_idx]
        self.atlas = self.atlas.at[line_idx].set(new_value)
        self.memory.append({
            'line': line_idx,
            'old': float(old),
            'new': new_value,
            'hexagram': self.basis.channel_to_hexagram(line_idx),
            'mutual': self.basis.mutual.of_hexagram(
                self.basis.channel_to_hexagram(line_idx)
            )
        })
    
    def __repr__(self) -> str:
        h, w = self.dominant
        m = self.mutual
        return (f"IChingAgent(name={self.name}, "
                f"dominant={h.name} ({h.chinese}), weight={w:.3f}, "
                f"mutual={m.name})")


# -----------------------------------------------------------------------
# SU(4) connection
# -----------------------------------------------------------------------

def hexagram_to_su4_operator(hexagram: Hexagram) -> jnp.ndarray:
    """
    Map a hexagram to an SU(4) generator.
    
    SU(4) has 15 generators (Gell-Mann matrices). The 64 hexagrams
    correspond to compositions of these generators, forming a basis
    for the Lie algebra su(4) ⊗ su(4).
    
    The mapping:
    - Upper trigram → first SU(4) index
    - Lower trigram → second SU(4) index
    - Binary pattern → specific generator combination
    
    This is a placeholder — actual mapping would use the full theory.
    """
    # Map trigrams to indices 0-7
    trigram_to_index = {t: i for i, t in enumerate(TRIGRAMS)}
    
    i = trigram_to_index[hexagram.upper_trigram]
    j = trigram_to_index[hexagram.lower_trigram]
    
    # 4x4 complex matrix (simplified — would be actual SU(4) generator)
    result = jnp.zeros((4, 4), dtype=jnp.complex64)
    result = result.at[i % 4, j % 4].set(1.0)
    
    return result


# -----------------------------------------------------------------------
# GBC frame to hexagram interpretation
# -----------------------------------------------------------------------

def gbc_frame_to_hexagram_reading(frame_psi: jnp.ndarray) -> str:
    """
    Interpret a GBC frame's T' state as an I Ching reading.
    
    This is where the pixel space meets ancient wisdom:
    - τ (memory) → stability of the situation
    - φ₁, φ₂ (futures) → possible outcomes
    - ξ (observation) → current perspective
    
    The mutual gua of φ₁ and φ₂ reveals the hidden game dynamics.
    """
    from binding import observe
    from atlas import AtlasVector
    
    # Get Atlas vector from psi
    real_7d = frame_psi.real
    atlas_vec = observe(real_7d)
    
    # Create I Ching basis
    basis = IChingBasis()
    
    # Get futures as separate Atlas vectors
    # This is simplified — in reality, φ₁ and φ₂ are embedded in the state
    # We'd need to project them separately
    phi1_atlas = atlas_vec * 0.5 + jnp.random.randn(64) * 0.1
    phi2_atlas = atlas_vec * 0.5 - jnp.random.randn(64) * 0.1
    
    # Normalize
    phi1_atlas = phi1_atlas / jnp.linalg.norm(phi1_atlas)
    phi2_atlas = phi2_atlas / jnp.linalg.norm(phi2_atlas)
    
    # Compute coherence
    from gbc_jax import coherence
    # Convert to 7D (simplified)
    phi1_7d = jnp.array([1.0, 0.3, 0.2, 0.2, 0.3, 0.1, 0.1], dtype=jnp.complex64)
    phi2_7d = jnp.array([1.0, 0.2, 0.3, 0.3, 0.2, 0.1, 0.1], dtype=jnp.complex64)
    coh = coherence(phi1_7d, phi2_7d)
    
    # Generate readings
    primary_reading = basis.to_reading(atlas_vec, include_mutual=False)
    coherence_reading = basis.mutual.coherence_reading(phi1_atlas, phi2_atlas, coh)
    
    # Add GBC-specific interpretation
    tau = frame_psi[0].real
    phi1_mag = jnp.abs(frame_psi[1] + 1j*frame_psi[2])
    phi2_mag = jnp.abs(frame_psi[3] + 1j*frame_psi[4])
    xi_mag = jnp.abs(frame_psi[5] + 1j*frame_psi[6])
    
    gbc_context = f"""
╔══════════════════════════════════════════════════════════╗
║                    GAME STATE SUMMARY                    ║
╚══════════════════════════════════════════════════════════╝

τ (memory strength): {tau:.3f}
  {'Stable pattern — repeating elements' if tau > 0.7 else 'Flux — rapid change'}

φ₁ (future 1 magnitude): {phi1_mag:.3f}
φ₂ (future 2 magnitude): {phi2_mag:.3f}
  {'Futures balanced' if abs(phi1_mag - phi2_mag) < 0.2 else 'One future dominates'}

ξ (observation strength): {xi_mag:.3f}
  {'Focused attention' if xi_mag > 0.5 else 'Diffuse awareness'}

Coherence Φ: {coh:.3f}
  {'Futures strongly interfere — multiple possibilities' if coh > 0.7 else
   'Futures moderately coupled' if coh > 0.3 else
   'Futures nearly independent — deterministic'}
"""
    
    return primary_reading + coherence_reading + gbc_context


# -----------------------------------------------------------------------
# Test
# -----------------------------------------------------------------------

if __name__ == "__main__":
    print("☯️ Testing I Ching Integration with Mutual Gua")
    print("=" * 60)
    
    # Build hexagrams
    hexagrams = build_hexagrams()
    print(f"Loaded {len(hexagrams)} hexagrams")
    
    # Test hexagram 1 (The Creative)
    h1 = hexagrams[1]
    print(f"\nHexagram 1: {h1.name} ({h1.chinese})")
    print(f"Binary: {h1.binary_string}")
    print(f"Upper: {h1.upper_trigram.name}, Lower: {h1.lower_trigram.name}")
    
    # Test mutual gua
    basis = IChingBasis()
    mutual_h1 = basis.mutual.of_hexagram(h1)
    print(f"\nMutual gua of Hexagram 1: {mutual_h1.number}. {mutual_h1.name}")