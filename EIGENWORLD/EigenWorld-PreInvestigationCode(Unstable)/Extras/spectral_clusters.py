"""
spectral_clusters.py — Spectral clustering on the coherence graph.

The coherence matrix C is a weighted adjacency matrix on N cells.
Its graph Laplacian L = D - C (where D is the diagonal degree matrix)
encodes the natural cluster structure of the cell population.

The bottom-k eigenvectors of L (those with smallest eigenvalues) span
the k most coherent groups. Cells in the same eigenvector cluster are
in the same natural interaction family — they share a stable coherence
pattern that persists under Y evolution.

This replaces the ad-hoc distance-based "same archetype family" check
with a mathematically principled grouping derived directly from Y.

Key results used here:

  1. Fiedler vector (second eigenvector of L, eigenvalue lambda_2):
     The sign of each entry partitions cells into two maximally
     coherent groups. lambda_2 = 0 means the graph is disconnected.

  2. k-way spectral embedding:
     Stack bottom-k eigenvectors as rows -> (N, k) embedding.
     k-means in this space gives k natural clusters.
     Each cluster is a candidate hyperedge group.

  3. Y-spectral alignment:
     After clustering, we check each cluster against the Y operator's
     own eigenspaces. Clusters that align with a specific Y eigenmode
     (eternal +-1, spiral +-i*sqrt(3)/2, nilpotent 0) evolve predictably
     and can be batch-processed as a unit.

All eigendecompositions: jnp.linalg.eigh (symmetric, O(N^3) but
batched and GPU-resident). For N up to ~2000 this is comfortably fast.
For larger N, Lanczos iteration would replace full eigh.
"""

import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass

try:
    import jax.numpy as jnp
    from jax import jit
    JAX_AVAILABLE = True
except ImportError:
    JAX_AVAILABLE = False

from coherence_graph import CoherenceGraph, coherence_matrix, stable_coherence_matrix


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class SpectralPartition:
    """
    Result of spectral clustering on the coherence graph.

    cluster_ids[i] = k  means cell i belongs to cluster k.
    clusters[k]    = list of cell indices in cluster k.
    fiedler        = Fiedler vector (2nd eigenvector of Laplacian).
    lambda2        = Fiedler value. Near 0 = disconnected graph.
    embedding      = (N, n_clusters) spectral embedding coordinates.
    y_alignments   = for each cluster, which Y eigenmode dominates.
    """
    n_clusters:    int
    cluster_ids:   np.ndarray          # (N,) int
    clusters:      List[List[int]]     # n_clusters lists of cell indices
    fiedler:       np.ndarray          # (N,) float
    lambda2:       float               # Fiedler value
    embedding:     np.ndarray          # (N, k) float
    y_alignments:  List[str]           # per-cluster dominant Y mode


# ── Y eigenmode reference vectors ────────────────────────────────────────────
# Pre-computed from y323operator: the four non-nilpotent eigenvectors.
# Used to classify which Y mode each cluster aligns with.

def _get_Y_eigenvectors() -> Tuple[np.ndarray, np.ndarray]:
    """Returns (eigenvalues, eigenvectors) for the stable subspace of Y."""
    from jax_kernels import _Y_NP
    vals, vecs = np.linalg.eig(_Y_NP)
    # Keep only non-nilpotent modes
    mask = np.abs(vals) > 1e-8
    return vals[mask], vecs[:, mask]   # (4,), (7, 4)


# ── Graph Laplacian ───────────────────────────────────────────────────────────

def graph_laplacian(C: np.ndarray, normalized: bool = True) -> np.ndarray:
    """
    Build the (normalised) graph Laplacian from coherence matrix C.

    Normalized Laplacian: L = I - D^{-1/2} C D^{-1/2}
    where D = diag(row sums of C).

    The normalised form is preferred: it accounts for cells with very
    different total coherence (some cells are coherent with many neighbors,
    others with few) and gives better-conditioned eigenvectors.

    C: (N, N) float32 symmetric coherence matrix
    returns: (N, N) float64 Laplacian
    """
    C = C.astype(np.float64)
    np.fill_diagonal(C, 0.0)          # remove self-loops

    degrees = C.sum(axis=1)           # (N,)

    if normalized:
        # D^{-1/2}
        with np.errstate(divide='ignore', invalid='ignore'):
            d_inv_sqrt = np.where(degrees > 1e-12, 1.0 / np.sqrt(degrees), 0.0)
        D_inv_sqrt = np.diag(d_inv_sqrt)
        L = np.eye(len(C)) - D_inv_sqrt @ C @ D_inv_sqrt
    else:
        L = np.diag(degrees) - C

    return L


# ── Spectral embedding ────────────────────────────────────────────────────────

def spectral_embedding(
    C:          np.ndarray,
    n_clusters: int,
    use_stable: bool = True,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Compute spectral embedding of cells via graph Laplacian eigenvectors.

    If use_stable=True, uses the stable coherence matrix C_P instead of C
    so the embedding reflects only persistent (non-transient) connections.

    Returns:
      embedding: (N, n_clusters) float  — coordinates in spectral space
      eigenvals: (n_clusters,) float    — corresponding Laplacian eigenvalues
      lambda2:   float                  — Fiedler value
    """
    N = C.shape[0]
    k = min(n_clusters, N - 1)

    L = graph_laplacian(C, normalized=True)

    # Full eigendecomposition of symmetric L (eigh = exact, sorted ascending)
    eigenvals, eigenvecs = np.linalg.eigh(L)  # (N,), (N, N)

    # Skip eigenvector 0 (constant, eigenvalue ~0): take indices 1..k
    embedding  = eigenvecs[:, 1:k+1].astype(np.float32)   # (N, k)
    eigenvals  = eigenvals[1:k+1].astype(np.float32)       # (k,)
    lambda2    = float(eigenvals[0]) if len(eigenvals) > 0 else 0.0

    return embedding, eigenvals, lambda2


# ── K-means in spectral space ─────────────────────────────────────────────────

def kmeans_spectral(
    embedding:  np.ndarray,
    n_clusters: int,
    n_iter:     int = 20,
    seed:       int = 0,
) -> np.ndarray:
    """
    Simple k-means in spectral embedding space.
    Returns cluster_ids: (N,) int array.

    We implement k-means directly (no sklearn) to avoid the import overhead
    and to keep the loop vectorised with numpy.
    """
    N, k = embedding.shape
    rng  = np.random.default_rng(seed)

    # Initialise centroids by picking random rows (k-means++)
    centroids = embedding[rng.choice(N, size=min(n_clusters, N), replace=False)]

    for _ in range(n_iter):
        # Assign: (N, k) - (C, k) -> (N, C) distances
        diffs = embedding[:, None, :] - centroids[None, :, :]  # (N, C, k)
        dists = np.sum(diffs**2, axis=2)                        # (N, C)
        ids   = np.argmin(dists, axis=1)                        # (N,)

        # Update centroids
        new_centroids = np.zeros_like(centroids)
        counts        = np.zeros(len(centroids), dtype=np.int32)
        for c in range(len(centroids)):
            mask = (ids == c)
            if mask.any():
                new_centroids[c] = embedding[mask].mean(axis=0)
                counts[c]        = mask.sum()
            else:
                new_centroids[c] = centroids[c]  # keep old centroid

        if np.allclose(centroids, new_centroids, atol=1e-6):
            break
        centroids = new_centroids

    return ids.astype(np.int32)


# ── Y-mode alignment ──────────────────────────────────────────────────────────

def classify_cluster_y_mode(
    cluster_indices: List[int],
    states:          np.ndarray,
) -> str:
    """
    Given a cluster of cells, determine which Y eigenmode they collectively
    align with most strongly.

    Returns one of: 'eternal', 'spiral', 'nilpotent', 'mixed'

    Method: compute the mean state of the cluster, then decompose it into
    Y eigenmodes via least-squares projection onto the Y eigenvectors.
    The dominant mode determines the cluster's dynamic character.
    """
    from jax_kernels import _Y_NP
    eigvals, eigvecs = np.linalg.eig(_Y_NP)   # (7,), (7, 7)

    mean_state = np.mean(states[cluster_indices], axis=0)  # (7,) complex
    coeffs, _, _, _ = np.linalg.lstsq(eigvecs, mean_state, rcond=None)
    energy = np.abs(coeffs)**2

    # Classify by eigenvalue type
    nil_mask     = np.abs(eigvals) < 1e-8
    eternal_mask = np.abs(np.abs(eigvals) - 1.0) < 1e-4
    spiral_mask  = (~nil_mask) & (~eternal_mask)

    e_nil     = float(energy[nil_mask].sum())
    e_eternal = float(energy[eternal_mask].sum())
    e_spiral  = float(energy[spiral_mask].sum())
    total     = e_nil + e_eternal + e_spiral + 1e-30

    fracs = {
        'nilpotent': e_nil     / total,
        'eternal':   e_eternal / total,
        'spiral':    e_spiral  / total,
    }
    dominant = max(fracs, key=fracs.get)
    # Label 'mixed' if no mode dominates strongly
    return dominant if fracs[dominant] > 0.5 else 'mixed'


# ── Main partition function ───────────────────────────────────────────────────

def partition_cells(
    states:     np.ndarray,
    n_clusters: int  = 8,
    emergence_threshold: float = 0.92,
    stable_threshold:    float = 0.60,
) -> SpectralPartition:
    """
    Partition N cells into n_clusters natural groups using spectral clustering
    on the stable coherence matrix C_P.

    The stable coherence matrix strips nilpotent transients, so the resulting
    clusters reflect only the mathematically persistent interaction structure.

    states: (N, 7) complex64
    returns: SpectralPartition
    """
    N = len(states)

    if N < 3:
        ids = np.zeros(N, dtype=np.int32)
        return SpectralPartition(
            n_clusters   = 1,
            cluster_ids  = ids,
            clusters     = [list(range(N))],
            fiedler      = np.zeros(N),
            lambda2      = 0.0,
            embedding    = np.zeros((N, 1)),
            y_alignments = ['mixed'],
        )

    # Stable coherence matrix (one GPU call)
    C_P = stable_coherence_matrix(states)

    # Spectral embedding
    k         = min(n_clusters, N - 2)
    embedding, eigenvals, lambda2 = spectral_embedding(C_P, k)

    fiedler = embedding[:, 0] if embedding.shape[1] > 0 else np.zeros(N)

    # K-means in spectral space
    actual_k   = min(n_clusters, N)
    cluster_ids = kmeans_spectral(embedding, actual_k)

    # Build cluster lists
    from collections import defaultdict
    cluster_map = defaultdict(list)
    for i, c in enumerate(cluster_ids):
        cluster_map[int(c)].append(i)
    clusters = [cluster_map[k] for k in sorted(cluster_map.keys())]

    # Classify each cluster by dominant Y mode
    y_alignments = [
        classify_cluster_y_mode(cl, states) if len(cl) >= 2 else 'mixed'
        for cl in clusters
    ]

    return SpectralPartition(
        n_clusters   = len(clusters),
        cluster_ids  = cluster_ids,
        clusters     = clusters,
        fiedler      = fiedler.astype(np.float32),
        lambda2      = lambda2,
        embedding    = embedding,
        y_alignments = y_alignments,
    )


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import time

    rng    = np.random.default_rng(42)
    N      = 200
    states = (rng.standard_normal((N, 7)) +
              1j * rng.standard_normal((N, 7))).astype(np.complex64)

    t0 = time.perf_counter()
    for _ in range(5):
        P = partition_cells(states, n_clusters=8)
    t1 = time.perf_counter()

    print(f"partition_cells N={N} x5: {(t1-t0)*200:.1f}ms per call")
    print(f"  lambda2 (Fiedler value): {P.lambda2:.4f}")
    print(f"  clusters: {[len(c) for c in P.clusters]}")
    print(f"  Y alignments: {P.y_alignments}")
    print(f"  fiedler range: [{P.fiedler.min():.3f}, {P.fiedler.max():.3f}]")
