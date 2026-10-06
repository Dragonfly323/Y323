// Y₃₂₃ — Level 2: Language (Full)
//
// Depends only on kernel.rs via `mod kernel` in main.rs.
// No external crates. No file I/O required to start.
//
// The language layer gives the kernel multiple "eyes" into language —
// each tokenization scale is a different vantage point from which the
// eigenbasis can observe structure. Like compositional rules in a painting:
// not constraints imposed on the math, but additional perspectives from
// which the math finds its own invariances.
//
// Tokenization scales (all co-occur in the same sliding window):
//   - Character tokens       — phonetic texture, sub-word patterns
//   - Word tokens            — lexical identity
//   - Bigram tokens          — local word order (grammar signal)
//   - Head-word token        — longest word as semantic anchor
//   - Sentence-break tokens  — where utterances end
//   - Paragraph tokens       — discourse-level boundaries and structure
//
// The eigenbasis learns to separate these scales naturally:
// structural tokens (para_start, sentence_end) load on different
// dimensions than content tokens (specific nouns, verbs).
// This is the AST intuition realized through the math's own eyes.

use std::collections::HashMap;
use std::f64::consts::PI;

use crate::kernel::{Kernel, C, Y_HZ, DRIVER_HZ};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

pub const MAX_VOCAB:      usize = 4096;
pub const SVD_EVERY:      usize = 16;
pub const OJA_LR:         f64   = 0.01;
pub const COOCCUR_WINDOW: usize = 4;
/// Maximum words the system can speak in one utterance.
/// Actual count is modulated by kernel state — see words_out_count().
pub const MAX_WORDS_OUT:  usize = 12;

// Gain constants (match original prototype)
pub const TEXT_GAIN_BASE:         f64 = 0.08;
pub const TEXT_GAIN_PER_WORD:     f64 = 0.01;
pub const TEXT_GAIN_MAX:          f64 = 0.16;
pub const PARA_GAIN_BASE:         f64 = 0.10;
pub const PARA_GAIN_PER_SENTENCE: f64 = 0.01;
pub const PARA_GAIN_MAX:          f64 = 0.14;

// Token prefixes — explicit namespacing so the eigenbasis can see the scale
const PFX_CHAR:     &str = "t:c_";      // character
const PFX_WORD:     &str = "t:w_";      // word
const PFX_BIGRAM:   &str = "t:b_";      // bigram
const PFX_HEAD:     &str = "t:h_";      // head word
const PFX_SENT:     &str = "t:s_";      // sentence marker
const PFX_PARA:     &str = "t:p_";      // paragraph marker
const PFX_STRUCT:   &str = "t:st_";     // structural (punctuation, caps)

// ---------------------------------------------------------------------------
// Sentence detection
//
// Detects sentence boundaries by punctuation.
// Returns a Vec of (sentence_text, sentence_index) pairs.
// ---------------------------------------------------------------------------

fn detect_sentences(text: &str) -> Vec<String> {
    let mut sentences = Vec::new();
    let mut current = String::new();
    let mut chars = text.chars().peekable();

    while let Some(c) = chars.next() {
        current.push(c);
        if matches!(c, '.' | '!' | '?') {
            // Check it's not an abbreviation (very simple heuristic:
            // followed by space or end of string)
            let next_is_space_or_end = chars.peek()
                .map(|&nc| nc == ' ' || nc == '\n')
                .unwrap_or(true);
            if next_is_space_or_end {
                let s = current.trim().to_string();
                if !s.is_empty() { sentences.push(s); }
                current = String::new();
            }
        }
    }
    // Remaining text without terminal punctuation
    let s = current.trim().to_string();
    if !s.is_empty() { sentences.push(s); }

    sentences
}

/// Paragraph length bucket — gives the eigenbasis a structural size signal
fn para_len_bucket(word_count: usize) -> &'static str {
    match word_count {
        0..=5   => "tiny",
        6..=15  => "short",
        16..=40 => "medium",
        41..=100 => "long",
        _        => "extended",
    }
}

// ---------------------------------------------------------------------------
// Tokenization — multi-scale
//
// This is the single-sentence tokenizer. Called by both text_to_tokens()
// and paragraphs_to_token_events(). Produces all scales except paragraph
// markers (those are added by the paragraph-aware path).
// ---------------------------------------------------------------------------

pub fn tokenize_sentence(text: &str, sentence_idx: usize) -> Vec<String> {
    let mut tokens = Vec::new();

    // Normalize words: lowercase, alphanumeric only
    let words: Vec<String> = text
        .split(|c: char| !c.is_alphanumeric())
        .filter(|w| !w.is_empty())
        .map(|w| w.to_lowercase())
        .collect();

    // --- Character tokens (phonetic texture) ---
    for w in &words {
        for c in w.chars() {
            tokens.push(format!("{}{}", PFX_CHAR, c));
        }
    }

    // --- Word tokens (lexical identity) ---
    for w in &words {
        tokens.push(format!("{}{}", PFX_WORD, w));
    }

    // --- Bigram tokens (local word order — grammar signal) ---
    // "red ball" and "ball red" become distinct tokens.
    // This lets the eigenbasis learn word-order regularities.
    for pair in words.windows(2) {
        tokens.push(format!("{}{}_{}", PFX_BIGRAM, pair[0], pair[1]));
    }

    // --- Head-word token (semantic anchor) ---
    // The longest word tends to be the most content-bearing.
    if let Some(head) = words.iter().max_by_key(|w| w.len()) {
        tokens.push(format!("{}{}", PFX_HEAD, head));
    }

    // --- Sentence-end marker ---
    // Co-occurs with words near the end of this sentence,
    // teaching the eigenbasis what "sentence ending" looks like.
    tokens.push(format!("{}sent_{}_end", PFX_SENT, sentence_idx));
    tokens.push(format!("{}sentence_break", PFX_STRUCT));

    // --- Structural signals ---
    // Capitalization of first word signals sentence-start
    if let Some(first_char) = text.chars().next() {
        if first_char.is_uppercase() {
            tokens.push(format!("{}caps_start", PFX_STRUCT));
        }
    }
    // Terminal punctuation type
    if let Some(last_char) = text.trim().chars().last() {
        match last_char {
            '.' => tokens.push(format!("{}punct_period", PFX_STRUCT)),
            '?' => tokens.push(format!("{}punct_question", PFX_STRUCT)),
            '!' => tokens.push(format!("{}punct_exclaim", PFX_STRUCT)),
            _   => {}
        }
    }

    tokens
}

/// Simple single-string tokenizer (no paragraph structure).
/// Used for short inputs: single words, phrases, brief exchanges.
pub fn tokenize(text: &str) -> Vec<String> {
    // Detect sentences within the text
    let sentences = detect_sentences(text);
    let mut all_tokens = Vec::new();
    for (i, sentence) in sentences.iter().enumerate() {
        all_tokens.extend(tokenize_sentence(sentence, i));
    }
    // If no sentences detected (no terminal punctuation), tokenize as-is
    if all_tokens.is_empty() {
        all_tokens.extend(tokenize_sentence(text, 0));
    }
    all_tokens
}

// ---------------------------------------------------------------------------
// Paragraph-aware tokenization
//
// Treats each paragraph as an atomic cognitive unit.
// Returns a Vec of (tokens, gain) pairs — one per paragraph.
// The paragraph tokens (para_start, para_end, para_len_*) create
// distance between paragraphs in the co-occurrence window, so words
// from different paragraphs cluster separately in the eigenbasis.
// ---------------------------------------------------------------------------

pub fn paragraphs_to_token_events(text: &str) -> Vec<(Vec<String>, f64)> {
    // Split on blank lines
    let paragraphs: Vec<&str> = text
        .split("\n\n")
        .map(|p| p.trim())
        .filter(|p| !p.is_empty())
        .collect();

    // If no paragraph breaks, treat whole text as one paragraph
    let paragraphs = if paragraphs.len() <= 1 {
        vec![text.trim()]
    } else {
        paragraphs
    };

    paragraphs.iter().map(|para| {
        let sentences = detect_sentences(para);
        let sentence_count = sentences.len().max(1);
        let word_count: usize = para.split_whitespace().count();

        let mut tokens = Vec::new();

        // Paragraph-level structural tokens
        // These co-occur with everything in the paragraph,
        // teaching the eigenbasis about discourse structure.
        tokens.push(format!("{}para_start", PFX_PARA));
        tokens.push(format!("{}para_len_{}", PFX_PARA, para_len_bucket(word_count)));
        tokens.push(format!("{}para_sentences_{}", PFX_PARA,
            sentence_count.min(5)));  // bucket: 1-5+

        // Interleave sentence tokens
        for (i, sentence) in sentences.iter().enumerate() {
            tokens.extend(tokenize_sentence(sentence, i));
        }

        tokens.push(format!("{}para_end", PFX_PARA));

        // Gain scales with sentence count: more structure = stronger signal
        let gain = (PARA_GAIN_BASE
            + PARA_GAIN_PER_SENTENCE * (sentence_count as f64).min(5.0))
            .min(PARA_GAIN_MAX);

        (tokens, gain)
    }).collect()
}

// ---------------------------------------------------------------------------
// text_to_diff — byte-phase sinusoid projection
//
// Maps any string deterministically to a unit [f64;7] vector.
// No vocabulary required. Gives the kernel an immediate signal
// for every string, even before the encoder has learned anything.
// ---------------------------------------------------------------------------

pub fn text_to_diff(text: &str) -> [f64; 7] {
    let mut diff = [0.0f64; 7];
    for (i, b) in text.bytes().enumerate() {
        let ph = (b as f64) * PI / 128.0;
        for d in 0..7 {
            diff[d] += ((d as f64 + 1.0) * PI / 7.0 * ph
                        + i as f64 * 0.1).sin();
        }
    }
    let norm: f64 = diff.iter().map(|x| x*x).sum::<f64>().sqrt();
    if norm > 1e-12 { for x in &mut diff { *x /= norm; } }
    diff
}

/// Gain for a plain text injection based on word count.
pub fn text_gain(word_count: usize) -> f64 {
    (TEXT_GAIN_BASE + TEXT_GAIN_PER_WORD * word_count.min(8) as f64)
        .min(TEXT_GAIN_MAX)
}

// ---------------------------------------------------------------------------
// SharedEncoder — co-occurrence learning + Oja eigenbasis
//
// The encoder learns a 7-dimensional eigenbasis from token co-occurrence.
// All tokenization scales feed into the same co-occurrence matrix —
// structural tokens, character tokens, word tokens, bigrams all co-occur
// in the same sliding window. The eigenbasis then discovers which
// dimensions capture structure and which capture content.
//
// This is the math finding compositional rules from raw co-occurrence,
// without being told what grammar is.
// ---------------------------------------------------------------------------

pub struct SharedEncoder {
    pub word_to_idx: HashMap<String, usize>,
    pub idx_to_word: Vec<String>,
    /// Flat co-occurrence matrix: cooccur[i * MAX_VOCAB + j]
    cooccur: Vec<f64>,
    /// Eigenbasis: basis[word_idx][dim] — word's coordinate in each dimension
    pub basis: Option<Vec<[f64; 7]>>,
    pub v:       usize,   // current vocabulary size
    pub ingests: usize,   // number of ingest() calls
}

impl SharedEncoder {
    pub fn new() -> Self {
        Self {
            word_to_idx: HashMap::new(),
            idx_to_word: Vec::new(),
            cooccur:     vec![0.0; MAX_VOCAB * MAX_VOCAB],
            basis:       None,
            v:           0,
            ingests:     0,
        }
    }

    fn get_or_add(&mut self, token: &str) -> Option<usize> {
        if let Some(&idx) = self.word_to_idx.get(token) { return Some(idx); }
        if self.v >= MAX_VOCAB { return None; }
        let idx = self.v;
        self.word_to_idx.insert(token.to_string(), idx);
        self.idx_to_word.push(token.to_string());
        self.v += 1;
        Some(idx)
    }

    /// Ingest a token list. Updates co-occurrence and Oja eigenbasis.
    pub fn ingest(&mut self, tokens: &[String]) {
        let indices: Vec<usize> = tokens.iter()
            .filter_map(|t| self.get_or_add(t))
            .collect();

        // Co-occurrence: distance-weighted within sliding window
        for (pos_i, &i) in indices.iter().enumerate() {
            let lo = pos_i.saturating_sub(COOCCUR_WINDOW);
            let hi = (pos_i + COOCCUR_WINDOW + 1).min(indices.len());
            for (pos_j, &j) in indices[lo..hi].iter().enumerate() {
                let actual_j = lo + pos_j;
                if actual_j == pos_i { continue; }
                let dist = (pos_i as isize - actual_j as isize).unsigned_abs();
                let weight = 1.0 / dist as f64;
                self.cooccur[i * MAX_VOCAB + j] += weight;
                self.cooccur[j * MAX_VOCAB + i] += weight;
            }
        }

        // Oja's rule: online eigenbasis update
        if let Some(ref mut basis) = self.basis {
            for &idx in &indices {
                if idx >= self.v { continue; }
                let row_start = idx * MAX_VOCAB;
                let row = &self.cooccur[row_start..row_start + self.v];
                let row_norm: f64 = row.iter().map(|x| x*x).sum::<f64>().sqrt();
                if row_norm < 1e-12 { continue; }

                for d in 0..7 {
                    let p: f64 = row.iter().zip(basis.iter())
                        .map(|(xi, brow)| (xi / row_norm) * brow[d])
                        .sum();
                    for (wi, brow) in basis.iter_mut().enumerate() {
                        if wi >= self.v { break; }
                        let xi = self.cooccur[wi * MAX_VOCAB + idx] / row_norm;
                        brow[d] += OJA_LR * (p * xi - p * p * brow[d]);
                    }
                    let bnorm: f64 = basis.iter().take(self.v)
                        .map(|b| b[d] * b[d]).sum::<f64>().sqrt();
                    if bnorm > 1e-12 {
                        for brow in basis.iter_mut().take(self.v) {
                            brow[d] /= bnorm;
                        }
                    }
                }
            }
        }

        self.ingests += 1;
        if self.ingests % SVD_EVERY == 0 && self.v >= 7 {
            self.recompute_basis();
        }
    }

    /// Power iteration to find the top-7 eigenvectors of the co-occurrence matrix.
    fn recompute_basis(&mut self) {
        let v = self.v;
        let mut b: Vec<[f64; 7]> = if let Some(ref existing) = self.basis {
            existing.clone()
        } else {
            let mut seed = vec![[0.0f64; 7]; MAX_VOCAB];
            for i in 0..v {
                for d in 0..7 {
                    let angle = 2.0 * PI * (i * 7 + d) as f64 / (v * 7) as f64;
                    seed[i][d] = angle.sin();
                }
            }
            seed
        };

        for _iter in 0..20 {
            for d in 0..7 {
                let mut new_col = vec![0.0f64; v];
                for i in 0..v {
                    for j in 0..v {
                        new_col[i] += self.cooccur[i * MAX_VOCAB + j] * b[j][d];
                    }
                }
                for d2 in 0..d {
                    let proj: f64 = new_col.iter().zip(b.iter())
                        .map(|(x, brow)| x * brow[d2]).sum();
                    for i in 0..v { new_col[i] -= proj * b[i][d2]; }
                }
                let norm: f64 = new_col.iter().map(|x| x*x).sum::<f64>().sqrt();
                if norm > 1e-12 {
                    for i in 0..v { b[i][d] = new_col[i] / norm; }
                }
            }
        }
        self.basis = Some(b);
    }

    /// Encode a token list as a unit 7-vector in the eigenbasis.
    pub fn encode(&self, tokens: &[String]) -> Option<[f64; 7]> {
        let basis = self.basis.as_ref()?;
        let mut bow = vec![0.0f64; self.v];
        for token in tokens {
            if let Some(&idx) = self.word_to_idx.get(token) {
                if idx < self.v { bow[idx] += 1.0; }
            }
        }
        let bow_norm: f64 = bow.iter().map(|x| x*x).sum::<f64>().sqrt();
        if bow_norm < 1e-12 { return None; }
        for x in &mut bow { *x /= bow_norm; }

        let mut proj = [0.0f64; 7];
        for d in 0..7 {
            proj[d] = bow.iter().zip(basis.iter())
                .map(|(xi, brow)| xi * brow[d]).sum();
        }
        let pnorm: f64 = proj.iter().map(|x| x*x).sum::<f64>().sqrt();
        if pnorm < 1e-12 { return None; }
        for x in &mut proj { *x /= pnorm; }
        Some(proj)
    }

    /// Find the top `n` word tokens most aligned with a 7D direction.
    ///
    /// `n` is supplied by the caller — typically derived from kernel state
    /// so that a more energetic or coherent system speaks more words.
    /// Filters to only PFX_WORD tokens for human-readable output;
    /// structural tokens still influence the geometry invisibly.
    pub fn top_words_for(&self, direction: &[f64; 7], n: usize) -> Vec<String> {
        let basis = match self.basis.as_ref() {
            Some(b) => b,
            None    => return vec!["...".to_string()],
        };

        let mut scores: Vec<(f64, usize)> = (0..self.v).filter_map(|i| {
            if !self.idx_to_word[i].starts_with(PFX_WORD) { return None; }
            let dot: f64 = (0..7).map(|d| basis[i][d] * direction[d]).sum();
            Some((dot, i))
        }).collect();

        scores.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap());
        scores.iter()
            .take(n.min(MAX_WORDS_OUT))
            .map(|(_, i)| self.idx_to_word[*i][PFX_WORD.len()..].to_string())
            .collect()
    }

    /// Top structural tokens for a direction — shows which discourse/syntactic
    /// dimension the kernel is currently oriented toward.
    pub fn top_structural_for(&self, direction: &[f64; 7]) -> Vec<String> {
        let basis = match self.basis.as_ref() {
            Some(b) => b,
            None    => return vec![],
        };

        let structural_prefixes = [PFX_PARA, PFX_SENT, PFX_STRUCT];
        let mut scores: Vec<(f64, usize)> = (0..self.v).filter_map(|i| {
            let tok = &self.idx_to_word[i];
            if !structural_prefixes.iter().any(|p| tok.starts_with(p)) {
                return None;
            }
            let dot: f64 = (0..7).map(|d| basis[i][d] * direction[d]).sum();
            Some((dot, i))
        }).collect();

        scores.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap());
        scores.iter()
            .take(3)
            .map(|(_, i)| self.idx_to_word[*i].clone())
            .collect()
    }

    pub fn status(&self) -> String {
        format!("vocab={} ingests={} basis={}",
            self.v, self.ingests,
            if self.basis.is_some() { "ready" } else { "forming" })
    }
}

// ---------------------------------------------------------------------------
// EtaDensity — implicit geometric memory
//
// Rather than storing discrete memory entries, EtaDensity maintains a
// running 7×7 covariance matrix of where the kernel's η vector has spent
// time. This is the geometric residue of all past experience — the integral
// of every η snapshot accumulated tick by tick.
//
// From this density matrix two directions emerge naturally:
//
//   dominant_direction()  — where η has spent most time (what is known)
//   massless_direction()  — where η has spent least time (what is unknown)
//
// These are the eigenvectors of the covariance matrix corresponding to its
// largest and smallest eigenvalues respectively. The "massless direction"
// name comes directly from the Y₃₂₃ math: the zero eigenvalue of Y_gen
// corresponds to infinite potential, the least-constrained direction.
//
// This is memory without storage — pure geometry, native to the math.
// ---------------------------------------------------------------------------

pub struct EtaDensity {
    /// Running covariance accumulator: sum of η·ηᵀ over all ticks
    cov:    [[f64; 7]; 7],
    /// Number of η snapshots accumulated
    count:  u64,
    /// Decay factor per tick (1.0 = no decay, 0.999 = slow forgetting)
    decay:  f64,
}

impl EtaDensity {
    pub fn new(decay: f64) -> Self {
        Self { cov: [[0.0; 7]; 7], count: 0, decay }
    }

    /// Accumulate one η snapshot into the covariance.
    /// Called every tick by LanguageKernel.
    pub fn update(&mut self, eta: &[f64; 7]) {
        // Optional exponential forgetting
        if self.decay < 1.0 {
            for row in &mut self.cov {
                for x in row.iter_mut() { *x *= self.decay; }
            }
        }
        // Accumulate outer product η·ηᵀ
        for i in 0..7 { for j in 0..7 {
            self.cov[i][j] += eta[i] * eta[j];
        }}
        self.count += 1;
    }

    /// The direction η has spent most time near — what the system knows.
    /// This is the eigenvector of the covariance matrix with the largest
    /// eigenvalue, found by power iteration.
    pub fn dominant_direction(&self) -> Option<[f64; 7]> {
        if self.count < 7 { return None; }
        let n = self.count as f64;
        // Normalize covariance
        let mut m = [[0.0f64; 7]; 7];
        for i in 0..7 { for j in 0..7 { m[i][j] = self.cov[i][j] / n; } }
        Some(power_iterate(&m, true))
    }

    /// The direction η has spent least time near — what the system is curious about.
    /// This is the eigenvector with the smallest eigenvalue, found by
    /// inverse power iteration (deflate the dominant directions first).
    pub fn massless_direction(&self) -> Option<[f64; 7]> {
        if self.count < 14 { return None; }  // Need more data for massless
        let n = self.count as f64;
        let mut m = [[0.0f64; 7]; 7];
        for i in 0..7 { for j in 0..7 { m[i][j] = self.cov[i][j] / n; } }
        // Deflate: subtract largest eigencomponent to expose smallest
        let dominant = power_iterate(&m, true);
        for i in 0..7 { for j in 0..7 {
            m[i][j] -= dominant[i] * dominant[j];  // subtract rank-1 component
        }}
        Some(power_iterate(&m, true))
    }

    /// How many ticks of experience have been accumulated.
    pub fn count(&self) -> u64 { self.count }
}

/// Power iteration: find the dominant eigenvector of a 7×7 symmetric matrix.
/// Used by EtaDensity for the M-sector expression record.
fn power_iterate(m: &[[f64; 7]; 7], positive: bool) -> [f64; 7] {
    let mut v = [1.0f64 / 7.0_f64.sqrt(); 7];
    for _ in 0..40 {
        let mut mv = [0.0f64; 7];
        for i in 0..7 { for j in 0..7 { mv[i] += m[i][j] * v[j]; } }
        let norm: f64 = mv.iter().map(|x| x*x).sum::<f64>().sqrt();
        if norm < 1e-14 { break; }
        for i in 0..7 { v[i] = mv[i] / norm; }
    }
    if positive {
        if let Some(first_nonzero) = v.iter().find(|&&x| x.abs() > 1e-10) {
            if *first_nonzero < 0.0 { for x in &mut v { *x = -*x; } }
        }
    }
    v
}

// ---------------------------------------------------------------------------
// NDensity — the void's working memory
//
// The N-sector {τ=0, a₁=1, x=5} is the gateway through which all experience
// enters. It is nilpotent — τ dies in 2 steps, a₁ and x in 3 — but before
// dying they leave residue in the M-sector through the Fano coupling.
//
// NDensity tracks the running covariance of the N-sector as complex values,
// accumulating the outer product of (τ, a₁, x) at each tick. This is the
// void's memory of what has passed through it — not where η has been
// (that is EtaDensity, the M-sector's expression record), but what the
// gateway itself has felt.
//
// The exact coupling constants from the matrix:
//   Y·a₁ = i·τ         (a₁ and τ in exact quadrature)
//   Y·τ  = -i·a₁ + ω(1+i)·x
//   Y·x  = β·τ          where β = e^(iπ/4)
//
// The dominant direction of the N-sector covariance is the pattern of
// N-sector excitation the system recognizes most — familiar inputs.
// The massless direction is the pattern it has never felt — novelty.
//
// Feedback: the dominant and massless directions modulate the gain of
// future a₁ injections through the exact coupling constant i — no
// synthetic parameters, only what the algebra gives.
// ---------------------------------------------------------------------------

pub struct NDensity {
    /// Running covariance of N-sector: 3×3 complex outer product accumulator
    /// Indices: 0=τ, 1=a₁, 2=x  (mapped from kernel indices 0,1,5)
    cov_re: [[f64; 3]; 3],  // real part of covariance
    cov_im: [[f64; 3]; 3],  // imaginary part of covariance
    /// Number of snapshots accumulated
    pub count: u64,
    /// Decay factor (1.0 = no forgetting)
    decay: f64,
}

impl NDensity {
    pub fn new(decay: f64) -> Self {
        Self {
            cov_re: [[0.0; 3]; 3],
            cov_im: [[0.0; 3]; 3],
            count:  0,
            decay,
        }
    }

    /// Accumulate one N-sector snapshot.
    /// Takes the three N-sector components as complex values.
    pub fn update(&mut self, tau: C, a1: C, x: C) {
        let v = [tau, a1, x];

        if self.decay < 1.0 {
            for i in 0..3 { for j in 0..3 {
                self.cov_re[i][j] *= self.decay;
                self.cov_im[i][j] *= self.decay;
            }}
        }

        // Accumulate Hermitian outer product: v[i] * conj(v[j])
        for i in 0..3 { for j in 0..3 {
            let p = v[i] * v[j].conj();
            self.cov_re[i][j] += p.re;
            self.cov_im[i][j] += p.im;
        }}

        self.count += 1;
    }

    /// The N-sector direction most repeatedly excited — what the void knows.
    /// Returns a 3-vector (τ, a₁, x) representing the dominant excitation pattern
    /// as a real projection (the shadow we can read from the covariance).
    pub fn dominant(&self) -> Option<[f64; 3]> {
        if self.count < 7 { return None; }
        let n = self.count as f64;
        // Use the real part of the Hermitian covariance (the observable shadow)
        let mut m = [[0.0f64; 3]; 3];
        for i in 0..3 { for j in 0..3 { m[i][j] = self.cov_re[i][j] / n; } }

        // Power iteration on the 3×3 real covariance
        let mut v = [1.0f64 / 3.0_f64.sqrt(); 3];
        for _ in 0..40 {
            let mut mv = [0.0f64; 3];
            for i in 0..3 { for j in 0..3 { mv[i] += m[i][j] * v[j]; } }
            let norm: f64 = mv.iter().map(|x| x*x).sum::<f64>().sqrt();
            if norm < 1e-14 { break; }
            for i in 0..3 { v[i] = mv[i] / norm; }
        }
        Some(v)
    }

    /// The N-sector direction least excited — what the void has never felt.
    pub fn massless(&self) -> Option<[f64; 3]> {
        if self.count < 14 { return None; }
        let n = self.count as f64;
        let mut m = [[0.0f64; 3]; 3];
        for i in 0..3 { for j in 0..3 { m[i][j] = self.cov_re[i][j] / n; } }

        // Deflate dominant direction
        if let Some(dom) = self.dominant() {
            for i in 0..3 { for j in 0..3 {
                m[i][j] -= dom[i] * dom[j];
            }}
        }

        let mut v = [1.0f64 / 3.0_f64.sqrt(); 3];
        for _ in 0..40 {
            let mut mv = [0.0f64; 3];
            for i in 0..3 { for j in 0..3 { mv[i] += m[i][j] * v[j]; } }
            let norm: f64 = mv.iter().map(|x| x*x).sum::<f64>().sqrt();
            if norm < 1e-14 { break; }
            for i in 0..3 { v[i] = mv[i] / norm; }
        }
        Some(v)
    }

    /// Modulate an incoming a₁ signal by the N-sector's history.
    ///
    /// The exact algebraic coupling Y·a₁ = i·τ means a₁ and τ are in
    /// quadrature. The dominant direction of N-history gives the τ component
    /// (index 0 in the 3-vector). Through the exact coupling i, this modulates
    /// the imaginary part of future a₁ injections.
    ///
    /// No tuning parameters. The modulation magnitude is the dominant
    /// eigenvector's τ-component — exactly what the Jordan chain gives.
    ///
    /// Familiar patterns (aligned with dominant) arrive with reinforced phase.
    /// Novel patterns (aligned with massless) are not suppressed — the system
    /// is equally open to novelty; it simply recognizes familiarity.
    pub fn modulate(&self, z: C) -> C {
        let Some(dom) = self.dominant() else { return z; };

        // The τ-component of the dominant direction (index 0)
        // Through Y·a₁ = i·τ, this becomes a pure imaginary modulation
        let tau_component = dom[0];  // real projection onto τ axis

        // The coupling constant is exactly i — multiply by i·tau_component
        // i·τ_component modulates the imaginary part of z
        // This is: z → z + i·tau_component·|z|  (additive, in the i direction)
        // Which preserves the real part and reinforces the imaginary quadrature
        let modulation = C::new(0.0, tau_component * z.norm());
        z + modulation
    }
}

// ---------------------------------------------------------------------------
// LanguageKernel — Level 1 + Level 2 combined
//
// The kernel receives language as a single complex number at a₁.
// Magnitude = signal strength (from text gain).
// Phase = signal character (from the byte-phase projection of text).
//
// Output is read from η (index 6) — the Terminal/Orientation component.
// The M-sector maintains its invariants (a₂=1/4, b₂=1/√2) throughout.
// The encoder's eigenbasis maps the η direction to words.
// ---------------------------------------------------------------------------

pub struct LanguageKernel {
    pub kernel:      Kernel,
    pub encoder:     SharedEncoder,
    pub density:     EtaDensity,   // M-sector expression record
    pub n_density:   NDensity,     // N-sector working memory (void's record)
    pub speech_active:   bool,
    pub speech_interval: u64,
}

impl LanguageKernel {
    pub fn new(agent_defs: &[(&str, C)]) -> Self {
        Self {
            kernel:          Kernel::new(agent_defs),
            encoder:         SharedEncoder::new(),
            density:         EtaDensity::new(0.9995),
            n_density:       NDensity::new(0.9990), // N-sector forgets faster
            speech_active:   false,
            speech_interval: 378,
        }
    }

    /// Map text to a complex number for injection at a₁.
    /// Public version — no modulation. NDensity is read-only for now.
    pub fn text_to_a1_public(&self, text: &str, _agent_idx: usize) -> C {
        let tokens = tokenize(text);
        let gain   = text_gain(text.split_whitespace().count());
        self.text_to_a1(text, &tokens, gain)
    }

    /// Map text to a complex number for injection at a₁.
    ///
    /// Y·a₁ = i·τ: τ and a₁ are in exact quadrature.
    /// C::new(re, im) injected at a₁ is a superposition of a₁ content (re)
    /// and τ content (im). The Jordan chain rotates them via -i and i.
    ///
    /// Re(z) = byte-phase sinusoid at index 1 (a₁ axis), refined by encoder
    /// Im(z) = byte-phase sinusoid at index 0 (τ axis), always raw
    ///
    /// Both are exact functions of the text's bytes. No hand-chosen weights.
    fn text_to_a1(&self, text: &str, tokens: &[String], gain: f64) -> C {
        let raw = text_to_diff(text);

        // Real part: a₁ axis — lexical character
        // Encoder's semantic projection at index 1 when available
        let lexical: f64 = if let Some(proj) = self.encoder.encode(tokens) {
            proj[1]
        } else {
            raw[1]
        };

        // Imaginary part: τ axis — temporal character
        // Raw byte-phase at index 0: exact function of text, no choices
        // Through Y·a₁ = i·τ this drives τ directly
        let temporal: f64 = raw[0];

        C::new(lexical * gain, temporal * gain)
    }

    /// How many words to speak, derived from η magnitude and phase coherence.
    /// η magnitude reflects how strongly the system is oriented.
    /// Phase coherence reflects inter-agent agreement.
    fn words_out_count(&self) -> usize {
        let eta_mag = self.kernel.mean_eta().norm().clamp(0.0, 2.0);
        let coh     = self.kernel.phase_coherence().max(0.0).clamp(0.0, 1.0);
        let count   = 2.0 + eta_mag * 3.0 + coh * 3.0;
        count.round() as usize
    }

    pub fn ingest(&mut self, text: &str) {
        let tokens = tokenize(text);
        self.encoder.ingest(&tokens);
        let gain = text_gain(text.split_whitespace().count());
        let z    = self.text_to_a1(text, &tokens, gain);
        self.kernel.inject_a1_all(z);
    }

    pub fn ingest_paragraph(&mut self, text: &str) {
        let events = paragraphs_to_token_events(text);
        for (tokens, gain) in events {
            self.encoder.ingest(&tokens);
            let z = self.text_to_a1(text, &tokens, gain);
            self.kernel.inject_a1_all(z);
        }
    }

    /// Advance one tick. Feeds both density accumulators. Emits speech if active.
    pub fn tick(&mut self) {
        self.kernel.tick();

        // Feed N-sector of reader agent into NDensity (working memory)
        // Reader is agent 0 — the language/text gateway
        {
            let a = &self.kernel.agents[0];
            self.n_density.update(a.tau(), a.a1(), a.x());
        }

        // Feed M-sector into EtaDensity (expression record)
        let eta_real: [f64; 7] = {
            let a = &self.kernel.agents[0];
            [a.tau().re, a.a1().re, a.a2().re,
             a.b1().re,  a.b2().re, a.x().re, a.eta().re]
        };
        let norm: f64 = eta_real.iter().map(|x| x*x).sum::<f64>().sqrt();
        if norm > 1e-12 {
            let normed = std::array::from_fn(|i| eta_real[i] / norm);
            self.density.update(&normed);
        }

        // Spontaneous speech
        if self.speech_active
            && self.kernel.tick_count % self.speech_interval == 0
            && self.encoder.basis.is_some()
        {
            let use_massless = (self.kernel.tick_count / self.speech_interval) % 2 == 1;
            let words = if use_massless {
                self.respond_curious()
            } else {
                self.respond()
            };
            let structural = self.respond_structural();
            if !words.is_empty() {
                let tag = if use_massless { "꩜?" } else { "꩜ " };
                if structural.is_empty() {
                    println!("  {} {}", tag, words.join(" · "));
                } else {
                    println!("  {} {}  [{}]", tag, words.join(" · "),
                             structural.join(", "));
                }
            }
        }
    }

    /// Current η direction for readout — real parts of all state components.
    fn eta_direction(&self) -> [f64; 7] {
        // Mean real parts across all agents, normalized
        let mut dir = [0.0f64; 7];
        for agent in &self.kernel.agents {
            let psi = agent.psi();
            for i in 0..7 { dir[i] += psi[i].re; }
        }
        let n = self.kernel.agents.len() as f64;
        for x in &mut dir { *x /= n; }
        let norm: f64 = dir.iter().map(|x| x*x).sum::<f64>().sqrt();
        if norm > 1e-12 { for x in &mut dir { *x /= norm; } }
        dir
    }

    /// Respond from current η direction.
    pub fn respond(&self) -> Vec<String> {
        let direction = self.eta_direction();
        let n = self.words_out_count();
        self.encoder.top_words_for(&direction, n)
    }

    /// Respond from massless direction (curiosity).
    pub fn respond_curious(&self) -> Vec<String> {
        let direction = self.density.massless_direction()
            .or_else(|| self.density.dominant_direction())
            .unwrap_or_else(|| self.eta_direction());
        let n = self.words_out_count();
        self.encoder.top_words_for(&direction, n)
    }

    /// Respond from dominant direction (what is known).
    pub fn respond_dominant(&self) -> Vec<String> {
        let direction = self.density.dominant_direction()
            .unwrap_or_else(|| self.eta_direction());
        let n = self.words_out_count();
        self.encoder.top_words_for(&direction, n)
    }

    /// Structural layer response.
    pub fn respond_structural(&self) -> Vec<String> {
        let direction = self.eta_direction();
        self.encoder.top_structural_for(&direction)
    }

    /// Ingest and respond in one call.
    pub fn ingest_and_respond(&mut self, text: &str) -> Vec<String> {
        self.ingest(text);
        self.tick();
        self.respond()
    }

    /// Full status line.
    pub fn print_status(&self) {
        let pc      = self.kernel.phase_coherence();
        let eta     = self.kernel.mean_eta();
        let words   = self.respond();
        let struc   = self.respond_structural();
        let struc_s = if struc.is_empty() { String::new() }
                      else { format!("  [{}]", struc.join(", ")) };
        let n_dom = if let Some(d) = self.n_density.dominant() {
            format!("N_dom=[{:.2},{:.2},{:.2}]", d[0], d[1], d[2])
        } else {
            "N_dom=forming".to_string()
        };
        println!(
            "tick={:>6}  a₂={:.4}  η={:+.3}∠{:+.2}  coh={:.3}  {}  {}  | {}{}",
            self.kernel.tick_count,
            self.kernel.mean_a2_norm(),
            eta.norm(), eta.arg(),
            pc,
            self.encoder.status(),
            n_dom,
            if words.is_empty() { "...".to_string() } else { words.join(" · ") },
            struc_s,
        );
    }
}
