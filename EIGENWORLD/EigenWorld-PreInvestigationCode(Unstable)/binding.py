# core/binding.py
"""
Observation operator A: R^7 → R^64 (Atlas space).

A maps the observed real state (τ, a₁, a₂, b₁, b₂, x, y) to a 64-channel
Atlas vector. This is a linear map, hand-designed based on the semantic
meaning of each channel.

The pseudoinverse A⁺ is used for initialization: given a desired Atlas
vector v, we find the minimum-norm real state ψ such that A·ψ ≈ v,
then embed as a complex state with zero imaginary part and project onto M.
"""

import numpy as np
from atlas import CHANNELS, DIM, AtlasVector


def build_A() -> np.ndarray:
    """
    Construct the 64×7 observation matrix A.
    
    Each row corresponds to one Atlas channel.
    Columns: [τ, a₁, a₂, b₁, b₂, x, y]
    
    Weights are chosen heuristically based on channel meaning.
    All weights in [-1, 1]. Rows are not normalized — the resulting
    Atlas vector will be L2-normalized later if needed.
    """
    A = np.zeros((DIM, 7), dtype=np.float64)
    
    for ch in CHANNELS:
        i = ch.index
        name = ch.name
        
        # --- Physical / meta channels (0-9) ---
        if name == "Energy":
            A[i, 1] = 0.5   # a₁ (future activity)
            A[i, 3] = 0.5   # b₁ (future activity)
        elif name == "TemporalBias":
            A[i, 0] = 1.0   # τ (memory strength)
        elif name == "Entropy":
            A[i, 2] = 0.4   # a₂ (phase spread)
            A[i, 4] = 0.4   # b₂ (phase spread)
            A[i, 6] = 0.2   # y (observation phase)
        elif name == "Frequency":
            A[i, 2] = 0.3   # a₂
            A[i, 4] = 0.3   # b₂
            A[i, 6] = 0.4   # y
        elif name == "Recognition":
            A[i, 1] = 0.4   # a₁
            A[i, 3] = 0.4   # b₁
            A[i, 5] = 0.2   # x
        elif name == "ConservationFlux":
            A[i, 1] = 0.3
            A[i, 3] = 0.3
            A[i, 5] = 0.4
        elif name == "Stability":
            A[i, 0] = 0.8   # τ
            A[i, 1] = 0.2   # a₁ (ordered future)
        elif name == "Dissipation":
            A[i, 2] = 0.3
            A[i, 4] = 0.3
            A[i, 6] = 0.4
        elif name == "Coupling":
            A[i, 1] = 0.3
            A[i, 3] = 0.3
            A[i, 5] = 0.4
        elif name == "Scale":
            A[i, 0] = 0.5
            A[i, 5] = 0.5
        
        # --- Biological / embodied (10-19) ---
        elif name == "Metabolism":
            A[i, 1] = 0.3
            A[i, 3] = 0.3
            A[i, 5] = 0.4
        elif name == "Reproduction":
            A[i, 2] = 0.2
            A[i, 4] = 0.2
            A[i, 6] = 0.6
        elif name == "Locomotion":
            A[i, 1] = 0.4
            A[i, 3] = 0.4
            A[i, 2] = 0.2
        elif name == "Sensation":
            A[i, 5] = 0.3
            A[i, 6] = 0.7
        elif name == "Immunity":
            A[i, 0] = 0.3
            A[i, 5] = 0.7
        elif name == "Homeostasis":
            A[i, 0] = 0.6
            A[i, 5] = 0.4
        elif name == "GrowthRate":
            A[i, 1] = 0.4
            A[i, 3] = 0.4
            A[i, 2] = 0.2
        elif name == "MorphologyBias":
            A[i, 1] = 0.3
            A[i, 2] = 0.3
            A[i, 3] = 0.2
            A[i, 4] = 0.2
        elif name == "Lifespan":
            A[i, 0] = 1.0
        elif name == "Reactivity":
            A[i, 2] = 0.3
            A[i, 4] = 0.3
            A[i, 6] = 0.4
        
        # --- Social / relational (20-29) ---
        elif name == "Affinity":
            A[i, 1] = 0.3
            A[i, 3] = 0.3
            A[i, 5] = 0.4
        elif name == "Trust":
            A[i, 5] = 0.5
            A[i, 6] = 0.5
        elif name == "Status":
            A[i, 0] = 0.2
            A[i, 1] = 0.4
            A[i, 3] = 0.4
        elif name == "Cooperation":
            A[i, 1] = 0.3
            A[i, 3] = 0.3
            A[i, 5] = 0.4
        elif name == "Conflict":
            A[i, 2] = 0.5
            A[i, 4] = 0.5
        elif name == "LanguageBandwidth":
            A[i, 5] = 0.3
            A[i, 6] = 0.7
        elif name == "MemoryCapacity":
            A[i, 0] = 0.8
            A[i, 5] = 0.2
        elif name == "GroupConformity":
            A[i, 0] = 0.3
            A[i, 1] = 0.3
            A[i, 3] = 0.4
        elif name == "AllianceFlexibility":
            A[i, 2] = 0.3
            A[i, 4] = 0.3
            A[i, 6] = 0.4
        elif name == "GossipFlow":
            A[i, 6] = 1.0
        
        # --- Cultural / symbolic (30-39) ---
        elif name == "RitualDensity":
            A[i, 1] = 0.3
            A[i, 3] = 0.3
            A[i, 5] = 0.4
        elif name == "MythicAlignment":
            A[i, 1] = 0.2
            A[i, 3] = 0.2
            A[i, 6] = 0.6
        elif name == "TabooStrength":
            A[i, 0] = 0.7
            A[i, 2] = 0.3
        elif name == "AestheticBias":
            A[i, 2] = 0.4
            A[i, 4] = 0.4
            A[i, 6] = 0.2
        elif name == "SymbolicComplexity":
            A[i, 2] = 0.3
            A[i, 4] = 0.3
            A[i, 6] = 0.4
        elif name == "CeremonyCost":
            A[i, 0] = 0.2
            A[i, 5] = 0.8
        elif name == "CulturalMemory":
            A[i, 0] = 0.9
            A[i, 5] = 0.1
        elif name == "MythicPropagation":
            A[i, 6] = 1.0
        elif name == "Sacrality":
            A[i, 0] = 0.3
            A[i, 5] = 0.7
        elif name == "NarrativeMomentum":
            A[i, 2] = 0.2
            A[i, 4] = 0.2
            A[i, 6] = 0.6
        
        # --- Economic / technological (40-49) ---
        elif name == "ResourceAbundance":
            A[i, 1] = 0.4
            A[i, 3] = 0.4
            A[i, 5] = 0.2
        elif name == "Production":
            A[i, 1] = 0.3
            A[i, 3] = 0.3
            A[i, 5] = 0.4
        elif name == "TradeConnectivity":
            A[i, 5] = 0.5
            A[i, 6] = 0.5
        elif name == "ToolAffinity":
            A[i, 1] = 0.4
            A[i, 3] = 0.4
            A[i, 5] = 0.2
        elif name == "CraftSkill":
            A[i, 1] = 0.3
            A[i, 3] = 0.3
            A[i, 5] = 0.4
        elif name == "EnergyInfrastructure":
            A[i, 1] = 0.2
            A[i, 3] = 0.2
            A[i, 5] = 0.6
        elif name == "InformationFidelity":
            A[i, 0] = 0.2
            A[i, 5] = 0.8
        elif name == "MarketVolatility":
            A[i, 2] = 0.4
            A[i, 4] = 0.4
            A[i, 6] = 0.2
        elif name == "LaborMobility":
            A[i, 1] = 0.3
            A[i, 3] = 0.3
            A[i, 6] = 0.4
        elif name == "WealthDisparity":
            A[i, 0] = 0.2
            A[i, 1] = 0.4
            A[i, 3] = 0.4
        
        # --- Environment / geology / materials (50-59) ---
        elif name == "TerrainRugosity":
            A[i, 2] = 0.4
            A[i, 4] = 0.4
            A[i, 6] = 0.2
        elif name == "Hydrology":
            A[i, 1] = 0.2
            A[i, 3] = 0.2
            A[i, 6] = 0.6
        elif name == "SoilFertility":
            A[i, 1] = 0.4
            A[i, 3] = 0.4
            A[i, 5] = 0.2
        elif name == "SeismicStress":
            A[i, 2] = 0.5
            A[i, 4] = 0.5
        elif name == "ErosionRate":
            A[i, 2] = 0.3
            A[i, 4] = 0.3
            A[i, 6] = 0.4
        elif name == "MineralConductivity":
            A[i, 1] = 0.2
            A[i, 3] = 0.2
            A[i, 5] = 0.6
        elif name == "Corrosion":
            A[i, 2] = 0.3
            A[i, 4] = 0.3
            A[i, 6] = 0.4
        elif name == "Porosity":
            A[i, 5] = 0.5
            A[i, 6] = 0.5
        elif name == "VegetationComplexity":
            A[i, 2] = 0.2
            A[i, 4] = 0.2
            A[i, 5] = 0.6
        elif name == "MicrostructureScale":
            A[i, 0] = 0.2
            A[i, 5] = 0.8
        
        # --- Cognitive / collective (60-63) ---
        elif name == "Creativity":
            A[i, 2] = 0.3
            A[i, 4] = 0.3
            A[i, 6] = 0.4
        elif name == "CollectiveAwareness":
            A[i, 5] = 0.3
            A[i, 6] = 0.7
        elif name == "Autonomy":
            A[i, 0] = 0.2
            A[i, 1] = 0.2
            A[i, 3] = 0.2
            A[i, 5] = 0.4
        elif name == "RetrocausalBias":
            A[i, 6] = 1.0
    
    return A


# Build once, use everywhere
A = build_A()
A_pinv = np.linalg.pinv(A)  # 7×64, for initialization


def atlas_to_7d(vec: AtlasVector) -> np.ndarray:
    """
    Convenience wrapper: convert an AtlasVector to a 7D complex state.
    Equivalent to initialize(vec.to_array()) but returns complex array.
    """
    real_7d = A_pinv @ vec.to_array()
    return real_7d.astype(complex)

def observe(state_7d: np.ndarray) -> np.ndarray:
    """
    Observe a 7D real state (from ManifoldPoint) as a 64D Atlas vector.
    
    Args:
        state_7d: shape (7,) real array [τ, a₁, a₂, b₁, b₂, x, y]
    
    Returns:
        shape (64,) real array, not normalized
    """
    return A @ state_7d


def initialize(atlas_target: np.ndarray) -> np.ndarray:
    """
    Find the minimum-norm 7D real state whose observed Atlas vector
    is closest to the target.
    
    Args:
        atlas_target: shape (64,) desired Atlas vector (not necessarily normalized)
    
    Returns:
        shape (7,) real array
    """
    return A_pinv @ atlas_target