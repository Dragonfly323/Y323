// =============================================================================
// Y₃₂₃ — Unified System  v3 (Production)
// Single-file, continuous driver, async inputs
// =============================================================================

#![allow(dead_code, unused_variables, unused_imports)]

use std::collections::{HashMap, VecDeque};
use std::f64::consts::PI;
use std::io::{self, Write};
use std::sync::{Arc, Mutex, mpsc};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Instant, Duration};
use std::thread;

use ndarray::{Array1, Array2, s};
use ndarray::Array2 as NdArray2;
use ndarray_linalg::{SVD, Eigh};
use serde::{Deserialize, Serialize};

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use rustfft::{FftPlanner, num_complex::Complex as FftComplex};

use std::path::{Path, PathBuf};
use std::fs;
use image::GenericImageView;

const OMEGA:      f64 = std::f64::consts::FRAC_1_SQRT_2;
const S:          f64 = 1.732_050_807_568_877_2 / 2.0;
const GEN_RE:     f64 = std::f64::consts::FRAC_1_SQRT_2;
const GEN_IM:     f64 = std::f64::consts::FRAC_1_SQRT_2;
const LN_PHI:     f64 = 0.481_211_825_059_603_4;
const LN_2:       f64 = std::f64::consts::LN_2;
const FANO_KAPPA: f64 = LN_PHI * LN_PHI / (2.0 * PI);
const PHI:        f64 = 1.618_033_988_749_895;

const Y_HZ:           f64   = 882.0;
const DRIVER_HZ:      f64   = 126.0;
const STEPS_PER_TICK: usize = 7;
const STEPS_MIN: usize = 3;
const STEPS_MAX: usize = 14;
const AUDIO_SR:    u32   = 44100;
const AUDIO_BATCH: usize = 50;
const MAX_VOCAB:  usize = 16384;
const SVD_EVERY:  usize = 16;
const OJA_LR:     f64   = 0.01;
const RESONANCE_THRESH:       f32 = 0.85;
const COHERENCE_THRESH:       f64 = 0.70;
const PHASE_COHERENCE_THRESH: f64 = 0.60;
const COMMIT_GAIN_THRESH:     f64 = 0.06;
const GATE_DRAIN_STEPS: u32 = 6;
const HEARTBEAT_GAIN: f64 = 0.001;
const CQT_BINS_PER_OCTAVE: usize = 36;
const CQT_N_OCTAVES:       usize = 7;
const CQT_TOTAL_BINS:      usize = CQT_BINS_PER_OCTAVE * CQT_N_OCTAVES;
const CQT_FMIN:            f64   = 27.5;
const CQT_WINDOWS: [usize; 7] = [4096, 2048, 1024, 512, 512, 256, 256];
const GOERTZEL_BANDS: [f64; 7] = [60.0, 120.0, 500.0, 1000.0, 2500.0, 5000.0, 10_000.0];
const SCHUMANN:     f64 = 7.83;
const BUS_HALFLIFE: f64 = 0.1;

#[derive(Clone, Copy, Default, Debug, Serialize, Deserialize)]
struct C { re: f64, im: f64 }

impl C {
    const fn new(re: f64, im: f64) -> Self { Self { re, im } }
    const ZERO: Self = Self::new(0.0, 0.0);
    const I:    Self = Self::new(0.0, 1.0);
    const ONE:  Self = Self::new(1.0, 0.0);
    fn scale(self, s: f64) -> Self { Self::new(self.re*s, self.im*s) }
    fn norm_sq(self) -> f64 { self.re*self.re + self.im*self.im }
    fn arg(self)  -> f64 { self.im.atan2(self.re) }
    fn conj(self) -> Self { Self::new(self.re, -self.im) }
}
impl std::ops::Add for C {
    type Output = Self;
    fn add(self, r: Self) -> Self { Self::new(self.re+r.re, self.im+r.im) }
}
impl std::ops::Mul for C {
    type Output = Self;
    fn mul(self, r: Self) -> Self {
        Self::new(self.re*r.re - self.im*r.im, self.re*r.im + self.im*r.re)
    }
}
impl std::ops::Neg for C {
    type Output = Self;
    fn neg(self) -> Self { Self::new(-self.re, -self.im) }
}

type Y7 = [[C;7];7];

fn y_gen() -> Y7 {
    let mut m = [[C::ZERO;7];7];
    let i   = C::I;
    let w   = C::new(OMEGA, 0.0);
    let s   = C::new(S, 0.0);
    let bp  = C::new(GEN_RE,  GEN_IM);
    let bpc = C::new(GEN_RE, -GEN_IM);
    m[0][1] = -i;    m[0][5] = -bpc;
    m[1][0] =  i;
    m[2][3] = C::ONE;
    m[3][2] = -C::ONE; m[3][4] = w;
    m[4][3] =  w;    m[4][6] = -(i*s);
    m[5][0] =  bp;
    m[6][4] =  i*s;
    m
}

fn y_apply(y: &Y7, v: &[C;7]) -> [C;7] {
    let mut o = [C::ZERO;7];
    for r in 0..7 { for c in 0..7 { o[r] = o[r] + y[r][c]*v[c]; } }
    o
}

fn gen_step(y: &Y7, v: &[C;7], dt: f64) -> [C;7] {
    let yv  = y_apply(y, v);
    let y2v = y_apply(y, &yv);
    let y3v = y_apply(y, &y2v);
    let mut r = *v;
    for i in 0..7 {
        r[i] = r[i]
             + yv[i].scale(dt)
             + y2v[i].scale(dt*dt/2.0)
             + y3v[i].scale(dt*dt*dt/6.0);
    }
    r
}

const FANO_TRIPLES: [(usize,usize,usize);7] = [
    (0,1,3),(1,2,4),(2,3,5),(3,4,6),(4,5,0),(5,6,1),(6,0,2)
];

fn fano_f(a: usize, b: usize, c: usize) -> f64 {
    for &(i,j,k) in &FANO_TRIPLES {
        if (a,b,c)==(i,j,k)||(a,b,c)==(j,k,i)||(a,b,c)==(k,i,j) { return  1.0; }
        if (a,b,c)==(j,i,k)||(a,b,c)==(i,k,j)||(a,b,c)==(k,j,i) { return -1.0; }
    }
    0.0
}

fn fano_influence(src: &[f64;7]) -> [f64;7] {
    let mut d = [0.0f64;7];
    for c in 0..7 { for a in 0..7 { for b in 0..7 {
        let sgn = fano_f(a, b, c);
        if sgn != 0.0 { d[c] += FANO_KAPPA * sgn * src[a] * src[b]; }
    }}}
    d
}

fn fano_neighbors(p: usize) -> Vec<usize> {
    let mut n = Vec::new();
    for &(a,b,c) in &FANO_TRIPLES {
        if a==p { if !n.contains(&b){n.push(b);} if !n.contains(&c){n.push(c);} }
        if b==p { if !n.contains(&a){n.push(a);} if !n.contains(&c){n.push(c);} }
        if c==p { if !n.contains(&a){n.push(a);} if !n.contains(&b){n.push(b);} }
    }
    n
}

#[derive(Debug, Clone, PartialEq)]
pub enum CascadeStage { Photon, Charge, Pixel, Phase, Image }

impl CascadeStage {
    pub fn injection_mask(&self) -> [f64;7] {
        match self {
            Self::Photon => [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            Self::Charge => [0.3, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            Self::Pixel  => [0.1, 0.2, 1.0, 1.0, 1.0, 0.1, 0.0],
            Self::Phase  => [0.1, 0.1, 0.2, 0.2, 0.2, 1.0, 0.2],
            Self::Image  => [0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 1.0],
        }
    }
}

#[derive(Debug, Clone)]
pub enum Gate { Open, Draining(u32), Closed }

impl Gate {
    pub fn is_open(&mut self, n_energy: f64) -> bool {
        match self {
            Gate::Open => true,
            Gate::Draining(n) => {
                *n += 1;
                if n_energy < 1e-4 || *n >= GATE_DRAIN_STEPS {
                    *self = Gate::Closed;
                }
                false
            }
            Gate::Closed => false,
        }
    }
    pub fn open(&mut self)  { *self = Gate::Open; }
    pub fn drain(&mut self) { *self = Gate::Draining(0); }
    pub fn close(&mut self) { *self = Gate::Closed; }
}

fn inner_product(a: &[C;7], b: &[C;7]) -> C {
    (0..7).fold(C::ZERO, |acc, i| acc + a[i].conj() * b[i])
}

fn relative_phase(a: &[C;7], b: &[C;7]) -> f64 { inner_product(a, b).arg() }

fn phase_weighted_fano(src_real: &[f64;7], src_state: &[C;7], tgt_state: &[C;7]) -> [f64;7] {
    let w = 0.5 + 0.25 * (relative_phase(src_state, tgt_state).cos() + 1.0);
    let raw = fano_influence(src_real);
    std::array::from_fn(|i| raw[i] * w)
}

pub fn global_phase_coherence(agents: &[KernelAgent]) -> f64 {
    let mut sum = 0.0f64; let mut n = 0usize;
    for i in 0..agents.len() {
        for j in (i+1)..agents.len() {
            if fano_neighbors(agents[i].fano_pos).contains(&agents[j].fano_pos) {
                sum += relative_phase(&agents[i].state, &agents[j].state).cos();
                n += 1;
            }
        }
    }
    if n == 0 { 0.0 } else { sum / n as f64 }
}

#[derive(Clone, Serialize, Deserialize)]
pub struct KernelAgent {
    pub state:    [C;7],
    pub name:     String,
    pub fano_pos: usize,
}

impl KernelAgent {
    pub fn new(name: &str, fano_pos: usize) -> Self {
        let y = y_gen();
        let mut k = Self { state: [C::ZERO;7], name: name.to_string(), fano_pos };
        k.state[0] = C::new(0.1, 0.05);
        k.state[2] = C::new(0.01, 0.0);
        k.renorm();
        for _ in 0..32 { k.state = gen_step(&y, &k.state, 1.0/Y_HZ); k.fold(); k.renorm(); }
        k
    }

    pub fn step(&mut self, y: &Y7, dt: f64) {
        self.state = gen_step(y, &self.state, dt);
        self.fold(); self.renorm();
    }

    pub fn inject_staged(&mut self, d: &[f64;7], gain: f64, stage: &CascadeStage) {
        let mask = stage.injection_mask();
        for i in 0..7 { self.state[i] = self.state[i] + C::new(d[i]*gain*mask[i], 0.0); }
        self.renorm();
    }

    pub fn inject(&mut self, d: &[f64;7], gain: f64) {
        for i in 0..7 { self.state[i] = self.state[i] + C::new(d[i]*gain, 0.0); }
        self.renorm();
    }

    fn fold(&mut self) {
        if self.state[0].re < 0.0 { for c in &mut self.state { *c = -*c; } }
    }
    fn renorm(&mut self) {
        let f: f64 = self.state.iter().map(|c| c.norm_sq()).sum::<f64>().sqrt();
        if f > 1e-12 { for c in &mut self.state { *c = c.scale(1.0/f); } }
    }

    pub fn real(&self)          -> [f64;7] { std::array::from_fn(|i| self.state[i].re) }
    pub fn eta_re(&self)        -> f64     { self.state[6].re }
    pub fn tau(&self)           -> f64     { self.state[0].re }
    pub fn a2_norm(&self)       -> f64     { self.state[2].norm_sq().sqrt() }
    pub fn is_coherent(&self)   -> bool    { self.tau() > COHERENCE_THRESH }
    pub fn intention_gap(&self) -> f64     { (self.state[6].re - self.state[0].re).abs() }

    pub fn n_energy(&self) -> f64 {
        [0,1,5].iter().map(|&r| self.state[r].norm_sq()).sum::<f64>().sqrt()
    }

    pub fn eta_normed(&self) -> [f32;7] {
        let r = self.real();
        let n: f64 = r.iter().map(|x| x*x).sum::<f64>().sqrt();
        if n < 1e-12 { return [0.0;7]; }
        std::array::from_fn(|i| (r[i]/n) as f32)
    }
}

// =============================================================================
// CreatureState — continuous physical properties derived from kernel observables
//
// This is not a separate system. It is a read of what the kernel already is.
// Each field is a pure function of the agent's state at this moment.
// The body never snaps — the gardener interpolates these values at 30Hz.
//
// Mapping:
//   posture    — dominant eta component's angle in [0, 2π) through the Fano plane
//                Small angle = curled inward; large = extended outward
//   hue        — which of the 7 Fano dimensions dominates (0=red..6=violet)
//                The creature's color IS its orientation. Not a mood label.
//   saturation — tau() clamped to [0,1]: high coherence = vivid, low = gray
//                A distressed or unfamiliar creature loses color naturally
//   brightness — eta_re() mapped to [0.3, 1.0]: the long-term orientation's
//                forward-facing intensity. Low = withdrawn; high = present
//   breath_rate — n_energy in [0,1]: 0.0 = one slow breath per 4s,
//                 1.0 = rapid shallow panting (8 breaths/s)
//                 Derived from nilpotent excitation — the transient subspace
//   gaze_stability — 1.0 - intention_gap clamped to [0,1]:
//                    near 1.0 = locked focus; near 0.0 = dreamy drift
//   arousal    — phase coherence contribution: collective coherence lifts all
//                The fiber being populated = the creature is more alive
//
// NeedState: regions of the 7-torus with qualitative meaning
//   Distress:     low tau + high n_energy  (unfamiliar + overstimulated)
//   Contentment:  high tau + low gap       (coherent + settled)
//   Seeking:      high gap + low n_energy  (oriented but calm — curious)
//   Rest:         all components low, heartbeat only
// =============================================================================

#[derive(Debug, Clone)]
pub struct CreatureState {
    /// Dominant eta component index (0–6), angle in Fano plane
    pub posture:       f64,   // radians, 0 = index 0 dominant
    /// Which Fano dimension dominates — maps to hue (0.0–1.0)
    pub hue:           f64,
    /// tau() → color saturation (0.0 gray … 1.0 vivid)
    pub saturation:    f64,
    /// eta_re() → presence/brightness (0.0 withdrawn … 1.0 present)
    pub brightness:    f64,
    /// n_energy → breathing rate (0.0 slow … 1.0 rapid)
    pub breath_rate:   f64,
    /// 1 - intention_gap → gaze stability (0.0 drifting … 1.0 focused)
    pub gaze_stability: f64,
    /// phase coherence → collective arousal boost
    pub arousal:       f64,
    /// Qualitative need state derived from the above
    pub need:          NeedState,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum NeedState {
    Rest,       // all low — kernel dreams, heartbeat only
    Seeking,    // high gap, low n_energy — curious, oriented
    Contentment,// high tau, low gap — familiar, settled
    Distress,   // low tau, high n_energy — overstimulated or lost
}

impl NeedState {
    pub fn name(&self) -> &str {
        match self {
            NeedState::Rest        => "rest",
            NeedState::Seeking     => "seeking",
            NeedState::Contentment => "content",
            NeedState::Distress    => "distress",
        }
    }
    /// ANSI color code for the need state border
    pub fn ansi_color(&self) -> &str {
        match self {
            NeedState::Rest        => "\x1b[34m",   // blue
            NeedState::Seeking     => "\x1b[36m",   // cyan
            NeedState::Contentment => "\x1b[32m",   // green
            NeedState::Distress    => "\x1b[31m",   // red
        }
    }
}

impl CreatureState {
    /// Derive creature state from a KernelAgent and current phase coherence.
    /// Pure function — no mutation, no stored state.
    pub fn from_agent(agent: &KernelAgent, phase_coherence: f64) -> Self {
        let eta    = agent.eta_normed();
        let tau    = agent.tau();
        let ne     = agent.n_energy();
        let gap    = agent.intention_gap();
        let eta_re = agent.eta_re();

        // Dominant component: which of the 7 dimensions has the largest magnitude
        let (dom_idx, _) = eta.iter().enumerate()
            .max_by(|a, b| a.1.abs().partial_cmp(&b.1.abs()).unwrap())
            .unwrap_or((0, &0.0));

        // Posture: angle of dominant index in the Fano plane
        // Each of the 7 positions maps to an angle 2π·i/7
        let posture = 2.0 * PI * dom_idx as f64 / 7.0;

        // Hue: continuous, derived from the signed eta vector's angle
        // We project eta onto the first two components and take atan2
        // This gives a continuous hue that rotates as the creature reorients
        let hue_angle = (eta[1] as f64).atan2(eta[0] as f64);
        let hue = (hue_angle / (2.0 * PI) + 1.0) % 1.0;  // [0, 1)

        let saturation   = tau.clamp(0.0, 1.0);
        let brightness   = (eta_re * 0.5 + 0.5).clamp(0.3, 1.0);
        let breath_rate  = ne.clamp(0.0, 1.0);
        let gaze_stability = (1.0 - gap).clamp(0.0, 1.0);
        let arousal      = phase_coherence.clamp(0.0, 1.0);

        // Need state — qualitative basin detection
        let need = if ne < 0.05 && gap < 0.1 {
            NeedState::Rest
        } else if tau > COHERENCE_THRESH && gap < 0.15 {
            NeedState::Contentment
        } else if tau < 0.3 && ne > 0.4 {
            NeedState::Distress
        } else {
            NeedState::Seeking
        };

        Self { posture, hue, saturation, brightness, breath_rate,
               gaze_stability, arousal, need }
    }

    /// The breathing phase at a given wall-clock time.
    /// Returns a value in [0, 1] that oscillates with breath_rate.
    pub fn breath_phase(&self, t_secs: f64) -> f64 {
        // breath_rate 0.0 → 0.25 Hz (one breath per 4s)
        // breath_rate 1.0 → 8.0 Hz (rapid)
        let freq = 0.25 + self.breath_rate * 7.75;
        (2.0 * PI * freq * t_secs).sin() * 0.5 + 0.5
    }

    /// HSV → ANSI 256-color approximation for terminal rendering.
    /// h in [0,1), s in [0,1], v in [0,1]
    pub fn to_ansi_color(h: f64, s: f64, v: f64) -> u8 {
        // Map to 6×6×6 color cube (ANSI colors 16–231)
        if s < 0.15 {
            // Grayscale ramp (232–255)
            let gray = (v * 23.0).round() as u8;
            return 232 + gray;
        }
        let r = hsv_component(h, s, v, 0.0);
        let g = hsv_component(h, s, v, 2.0/3.0);
        let b = hsv_component(h, s, v, 1.0/3.0);
        let ri = (r * 5.0).round() as u8;
        let gi = (g * 5.0).round() as u8;
        let bi = (b * 5.0).round() as u8;
        16 + 36*ri + 6*gi + bi
    }
}

fn hsv_component(h: f64, s: f64, v: f64, offset: f64) -> f64 {
    let k = (h * 6.0 + offset * 6.0).rem_euclid(6.0);
    let f = k.min(4.0 - k).clamp(0.0, 1.0);
    v * (1.0 - s * (1.0 - f))
}

pub fn adaptive_steps(n_energy: f64) -> usize {
    let e = n_energy.clamp(0.0, 1.0);
    let steps = STEPS_MIN as f64 + (STEPS_MAX - STEPS_MIN) as f64 * e;
    steps.round() as usize
}

pub struct GoertzelBank {
    state:       [[f64;2]; 7],
    pub energies: [f64;7],
    pub phases:   [f64;7],
}

impl GoertzelBank {
    pub fn new() -> Self {
        Self { state: [[0.0;2];7], energies: [0.0;7], phases: [0.0;7] }
    }

    pub fn process(&mut self, samples: &[f32]) {
        let sr = AUDIO_SR as f64;
        for band in 0..7 {
            let omega = 2.0 * PI * GOERTZEL_BANDS[band] / sr;
            let coeff = 2.0 * omega.cos();
            let (mut s0, mut s1) = (self.state[band][0], self.state[band][1]);
            for &samp in samples {
                let s_new = samp as f64 + coeff * s0 - s1;
                s1 = s0; s0 = s_new;
            }
            let real = s0 - s1 * omega.cos();
            let imag = s1 * omega.sin();
            self.energies[band] = (real*real + imag*imag).sqrt();
            self.phases[band]   = imag.atan2(real);
            self.state[band][0] = s0 * 0.95;
            self.state[band][1] = s1 * 0.95;
        }
    }

    pub fn to_diff(&self) -> [f64;7] {
        let max = self.energies.iter().cloned().fold(0.0f64, f64::max).max(1e-12);
        std::array::from_fn(|i| self.energies[i] / max)
    }

    pub fn to_tokens(&self) -> Vec<String> {
        let max = self.energies.iter().cloned().fold(0.0f64, f64::max).max(1e-12);
        let names = ["subbass","bass","lowmid","mid","himid","presence","air"];
        self.energies.iter().enumerate().filter_map(|(i, &e)| {
            let level = ((e / max) * 4.0).min(3.9) as usize;
            if level > 0 { Some(format!("gtz:{}:L{}", names[i], level)) } else { None }
        }).collect()
    }
}

pub struct CqtProcessor {
    fft_planners:  [Option<Arc<dyn rustfft::Fft<f32>>>; CQT_N_OCTAVES],
    planner:       FftPlanner<f32>,
    buffer:        VecDeque<f32>,
    pub magnitudes: Vec<f32>,
    seed_weights:  Option<Vec<f32>>,
    pub seed_blend: f32,
}

impl CqtProcessor {
    pub fn new() -> Self {
        let mut planner = FftPlanner::<f32>::new();
        let fft_planners = std::array::from_fn(|oct| {
            Some(planner.plan_fft_forward(CQT_WINDOWS[oct]))
        });
        Self {
            fft_planners,
            planner,
            buffer: VecDeque::with_capacity(8192),
            magnitudes: vec![0.0f32; CQT_TOTAL_BINS],
            seed_weights: None,
            seed_blend: 0.0,
        }
    }

    pub fn ingest(&mut self, samples: &[f32]) {
        for &s in samples { self.buffer.push_back(s); }
        while self.buffer.len() >= CQT_WINDOWS[0] {
            self.process_frame();
            let hop = CQT_WINDOWS[CQT_N_OCTAVES - 1] / 2;
            for _ in 0..hop { self.buffer.pop_front(); }
        }
    }

    fn process_frame(&mut self) {
        let sr = AUDIO_SR as f64;
        for oct in 0..CQT_N_OCTAVES {
            let win = CQT_WINDOWS[oct];
            if self.buffer.len() < win { continue; }
            let mut buf: Vec<FftComplex<f32>> = self.buffer.iter().take(win).enumerate()
                .map(|(i, &s)| {
                    let hann = 0.5 - 0.5 * (2.0 * PI as f32 * i as f32 / win as f32).cos();
                    FftComplex::new(s * hann, 0.0)
                }).collect();
            if let Some(ref fft) = self.fft_planners[oct] {
                fft.process(&mut buf);
            }
            let base = oct * CQT_BINS_PER_OCTAVE;
            for b in 0..CQT_BINS_PER_OCTAVE {
                let freq = CQT_FMIN * 2.0_f64.powf(oct as f64 + b as f64 / CQT_BINS_PER_OCTAVE as f64);
                let fft_bin = ((freq * win as f64 / sr) as usize).min(win / 2 - 1);
                let mag = (buf[fft_bin].re * buf[fft_bin].re + buf[fft_bin].im * buf[fft_bin].im).sqrt();
                self.magnitudes[base + b] = self.magnitudes[base + b] * 0.85 + mag * 0.15;
            }
        }
        if let Some(ref seed) = self.seed_weights {
            let blend = self.seed_blend;
            for i in 0..CQT_TOTAL_BINS {
                let s = seed.get(i).copied().unwrap_or(0.0);
                self.magnitudes[i] = self.magnitudes[i] * (1.0 - blend) + s * blend;
            }
        }
    }

    pub fn to_tokens(&self) -> Vec<String> {
        if self.magnitudes.is_empty() { return vec![]; }
        let mean: f32 = self.magnitudes.iter().sum::<f32>() / self.magnitudes.len() as f32;
        let std:  f32 = (self.magnitudes.iter().map(|x| (x-mean)*(x-mean)).sum::<f32>()
                         / self.magnitudes.len() as f32).sqrt();
        let thresh = mean + std * 0.5;
        let mut tokens = Vec::new();
        for (i, &mag) in self.magnitudes.iter().enumerate() {
            if mag > thresh {
                let oct   = i / CQT_BINS_PER_OCTAVE;
                let bin   = i % CQT_BINS_PER_OCTAVE;
                let level = ((mag / (mean + std + 1e-6)).min(3.9)) as usize;
                tokens.push(format!("cqt:o{}:b{}:L{}", oct, bin, level));
            }
        }
        const NAMES: [&str;12] = ["C","Db","D","Eb","E","F","Gb","G","Ab","A","Bb","B"];
        let mut pc = [0.0f32;12];
        for i in 0..CQT_TOTAL_BINS {
            pc[(i / (CQT_BINS_PER_OCTAVE / 12)) % 12] += self.magnitudes[i];
        }
        let pc_max = pc.iter().cloned().fold(0.0f32, f32::max);
        if pc_max > 1e-6 {
            for (i, &v) in pc.iter().enumerate() {
                if v > pc_max * 0.3 { tokens.push(format!("pc:{}", NAMES[i])); }
            }
        }
        tokens
    }

    pub fn load_seed_wav(&mut self, path: &str, blend: f32) -> std::io::Result<()> {
        let mut reader = hound::WavReader::open(path)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
        let spec = reader.spec();
        let samples: Vec<f32> = match spec.sample_format {
            hound::SampleFormat::Float => {
                reader.samples::<f32>().filter_map(|s| s.ok()).collect()
            }
            hound::SampleFormat::Int => {
                let max_val = (1i64 << (spec.bits_per_sample - 1)) as f32;
                reader.samples::<i32>().filter_map(|s| s.ok())
                    .map(|s| s as f32 / max_val).collect()
            }
        };
        let samples: Vec<f32> = if spec.channels == 2 {
            samples.chunks(2).map(|c| (c[0] + c.get(1).copied().unwrap_or(0.0)) * 0.5).collect()
        } else { samples };
        let samples: Vec<f32> = if spec.sample_rate != AUDIO_SR {
            let ratio = spec.sample_rate as f64 / AUDIO_SR as f64;
            (0..(samples.len() as f64 / ratio) as usize).map(|i| {
                let src = i as f64 * ratio;
                let idx = src as usize;
                let frac = (src - idx as f64) as f32;
                let a = samples.get(idx).copied().unwrap_or(0.0);
                let b = samples.get(idx+1).copied().unwrap_or(0.0);
                a + (b - a) * frac
            }).collect()
        } else { samples };
        let mut seed_cqt = CqtProcessor::new();
        for chunk in samples.chunks(AUDIO_BATCH) { seed_cqt.ingest(chunk); }
        while !seed_cqt.buffer.is_empty() && seed_cqt.buffer.len() >= CQT_WINDOWS[CQT_N_OCTAVES-1] {
            seed_cqt.process_frame();
            let hop = CQT_WINDOWS[CQT_N_OCTAVES-1] / 2;
            for _ in 0..hop { seed_cqt.buffer.pop_front(); }
        }
        self.seed_weights = Some(seed_cqt.magnitudes.clone());
        self.seed_blend   = blend.clamp(0.0, 1.0);
        println!("  [seed loaded: {} ({} samples, {:.1}s) blend={:.2}]",
                 path, samples.len(), samples.len() as f32 / AUDIO_SR as f32, blend);
        Ok(())
    }
}

pub struct AudioCapture {
    pub rx: std::sync::mpsc::Receiver<Vec<f32>>,
    _stream: cpal::Stream,
}

impl AudioCapture {
    pub fn start() -> Result<Self, Box<dyn std::error::Error>> {
        let host   = cpal::default_host();
        let device = host.default_input_device().ok_or("no input device available")?;
        let config = device.default_input_config()?;
        println!("  [audio: {} — {:?} {}Hz]",
                 device.name().unwrap_or_default(), config.sample_format(), config.sample_rate().0);
        let (tx, rx) = std::sync::mpsc::channel::<Vec<f32>>();
        let stream = match config.sample_format() {
            cpal::SampleFormat::F32 => {
                device.build_input_stream(
                    &config.into(),
                    move |data: &[f32], _| { let _ = tx.send(data.to_vec()); },
                    |e| eprintln!("  [audio error: {}]", e), None,
                )?
            }
            cpal::SampleFormat::I16 => {
                let tx2 = tx.clone();
                device.build_input_stream(
                    &config.into(),
                    move |data: &[i16], _| {
                        let f: Vec<f32> = data.iter().map(|&s| s as f32 / 32768.0).collect();
                        let _ = tx2.send(f);
                    },
                    |e| eprintln!("  [audio error: {}]", e), None,
                )?
            }
            fmt => return Err(format!("unsupported audio format {:?}", fmt).into()),
        };
        stream.play()?;
        Ok(Self { rx, _stream: stream })
    }
}

pub struct TemporalHeartbeat {
    pub tick_count:     u64,
    pub schumann_phase: f64,
    pub fano_phase:     f64,
}

impl TemporalHeartbeat {
    pub fn new() -> Self { Self { tick_count: 0, schumann_phase: 0.0, fano_phase: 0.0 } }

    pub fn tick(&mut self) -> ([f64;7], Vec<String>) {
        self.tick_count += 1;
        let dt = 1.0 / DRIVER_HZ;
        self.schumann_phase = (self.schumann_phase + 2.0*PI*SCHUMANN*dt) % (2.0*PI);
        self.fano_phase     = (self.fano_phase + 2.0*PI*(SCHUMANN/7.0)*dt) % (2.0*PI);
        let mut diff = [0.0f64;7];
        for i in 0..7 {
            diff[i] = (self.schumann_phase + 2.0*PI*i as f64/7.0).sin() * HEARTBEAT_GAIN;
        }
        use chrono::Timelike; use chrono::Datelike;
        let now     = chrono::Local::now();
        let hour    = now.hour();
        let weekday = now.weekday().num_days_from_monday();
        let yearday = now.ordinal();
        let fano_beat = (self.fano_phase / (2.0*PI) * 7.0) as usize;
        let tokens = vec![
            match hour {
                5..=8   => "time:dawn",   9..=11 => "time:morning",
                12..=13 => "time:midday", 14..=17 => "time:afternoon",
                18..=21 => "time:evening",22..=23 => "time:night",
                _       => "time:deep_night",
            }.to_string(),
            match yearday {
                1..=79    => "season:winter", 80..=171  => "season:spring",
                172..=265 => "season:summer", 266..=354 => "season:autumn",
                _         => "season:winter",
            }.to_string(),
            format!("weekday:{}", weekday),
            format!("fano_beat:{}", fano_beat),
            format!("hour_block:{}:{}", hour, now.minute()/10),
        ];
        (diff, tokens)
    }
}

pub struct SharedEncoder {
    word_to_idx:     HashMap<String, usize>,
    pub idx_to_word: Vec<String>,
    cooccur:         Array2<f64>,
    basis:           Option<Array2<f64>>,
    v:               usize,
    ingests:         usize,
}

impl SharedEncoder {
    pub fn new() -> Self {
        Self {
            word_to_idx: HashMap::new(), idx_to_word: Vec::new(),
            cooccur: Array2::zeros((MAX_VOCAB, MAX_VOCAB)),
            basis: None, v: 0, ingests: 0,
        }
    }

    pub fn intern(&mut self, w: &str) -> Option<usize> {
        if let Some(&i) = self.word_to_idx.get(w) { return Some(i); }
        if self.idx_to_word.len() >= MAX_VOCAB { return None; }
        let i = self.idx_to_word.len();
        self.word_to_idx.insert(w.to_string(), i);
        self.idx_to_word.push(w.to_string());
        self.v = self.v.max(i+1);
        Some(i)
    }

    pub fn ingest(&mut self, tokens: &[String]) {
        let idx: Vec<usize> = tokens.iter().filter_map(|t| self.intern(t)).collect();
        for (i, &wi) in idx.iter().enumerate() {
            let s = i.saturating_sub(4); let e = (i+5).min(idx.len());
            for j in s..e {
                if j==i { continue; }
                let w = 1.0 / (i as f64 - j as f64).abs();
                self.cooccur[[wi, idx[j]]] += w;
                self.cooccur[[idx[j], wi]] += w;
            }
        }
        if let Some(ref mut basis) = self.basis {
            let v = self.v;
            if !idx.is_empty() && v > 0 {
                let mut bow = vec![0.0f64; v];
                for &i in &idx { if i < v { bow[i] += 1.0; } }
                let total: f64 = bow.iter().sum();
                if total > 1e-12 {
                    for x in &mut bow { *x /= total; }
                    let x  = Array1::from(bow);
                    let bv = basis.slice(s![..v,..]).to_owned();
                    for j in 0..bv.ncols().min(7) {
                        let w    = bv.column(j).to_owned();
                        let proj = x.dot(&w);
                        let upd  = x.mapv(|xi| xi*proj) - w.mapv(|wi| wi*proj*proj);
                        let mut nw = w + upd.mapv(|u| u*OJA_LR);
                        let nm = nw.dot(&nw).sqrt();
                        if nm > 1e-12 { nw.mapv_inplace(|x| x/nm); }
                        for i in 0..v.min(basis.nrows()) { basis[[i,j]] = nw[i]; }
                    }
                }
            }
        }
        self.ingests += 1;
        if self.ingests % SVD_EVERY == 0 { self.recompute(); }
    }

    fn recompute(&mut self) {
        let v = self.v; if v < 8 { return; }
        let a = self.cooccur.slice(s![..v,..v]).to_owned();
        if let Ok((Some(u),_,_)) = a.svd(true, false) {
            let d = 7usize.min(u.ncols());
            self.basis = Some(u.slice(s![..,..d]).to_owned());
        }
    }

    pub fn encode(&self, tokens: &[String]) -> Option<[f64;7]> {
        let basis = self.basis.as_ref()?;
        let v = self.v; if v == 0 { return None; }
        let mut bow = vec![0.0f64; v];
        for t in tokens {
            if let Some(&i) = self.word_to_idx.get(t) { if i < v { bow[i] += 1.0; } }
        }
        let total: f64 = bow.iter().sum();
        if total < 1e-12 { return None; }
        for x in &mut bow { *x /= total; }
        let proj = basis.slice(s![..v,..]).t().dot(&Array1::from(bow));
        let n: f64 = proj.iter().map(|x| x*x).sum::<f64>().sqrt();
        if n < 1e-12 { return None; }
        Some(std::array::from_fn(|i| proj[i]/n))
    }

    pub fn top_words_for(&self, direction: &[f64;7]) -> Vec<String> {
        let basis = match &self.basis { Some(b) => b, None => return vec![] };
        let v = self.v;
        let mut scores: Vec<(usize,f64)> = (0..v.min(basis.nrows())).map(|i| {
            let loading: f64 = (0..7).map(|j| basis[[i,j]] * direction[j]).sum();
            (i, loading.abs())
        }).collect();
        scores.sort_by(|a,b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        scores.iter().take(5).filter_map(|(i,_)| self.idx_to_word.get(*i).cloned()).collect()
    }

    pub fn status(&self) -> String {
        format!("vocab={} ingests={} basis={}",
                self.v, self.ingests,
                if self.basis.is_some() { "ready" } else { "building" })
    }
}

#[derive(Serialize, Deserialize, Clone)]
pub struct MemoryEntry {
    pub eta:      [f32;7],
    pub response: Option<String>,
    pub modality: String,
    /// Coherence delta at time of storage.
    /// Positive = encounter raised coherence (comfort, recognition).
    /// Negative = encounter lowered coherence (distress, intrusion).
    /// High |valence| entries resist basis drift — trauma and deep comfort persist.
    #[serde(default)]
    pub valence:   f32,
    /// Driver tick count at storage — enables age-based decay.
    #[serde(default)]
    pub age_ticks: u64,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct Memory {
    pub entries:   Vec<MemoryEntry>,
    pub threshold: f32,
}

impl Memory {
    pub fn new() -> Self { Self { entries: Vec::new(), threshold: 0.72 } }

    pub fn store(&mut self, eta: [f32;7], response: Option<String>, modality: &str) {
        self.entries.push(MemoryEntry {
            eta, response, modality: modality.to_string(),
            valence: 0.0, age_ticks: 0,
        });
    }

    /// Store with valence (coherence delta) and tick count.
    /// valence > 0: encounter raised coherence — comfort, recognition.
    /// valence < 0: encounter lowered coherence — distress, intrusion.
    /// High |valence| entries resist the natural drift of the eigenbasis.
    pub fn store_with_valence(
        &mut self,
        eta: [f32;7],
        response: Option<String>,
        modality: &str,
        valence: f32,
        tick: u64,
    ) {
        self.entries.push(MemoryEntry {
            eta, response, modality: modality.to_string(),
            valence, age_ticks: tick,
        });
    }

    pub fn replace_last(&mut self, eta: [f32;7], response: Option<String>) {
        if let Some(e) = self.entries.last_mut() { e.eta = eta; e.response = response; }
        else { self.store(eta, response, ""); }
    }
    pub fn retrieve(&self, eta: &[f32;7]) -> Option<(&str, f32)> {
        let (mut best_sim, mut best_idx) = (self.threshold, None);
        for (i, e) in self.entries.iter().enumerate() {
            if e.response.is_none() { continue; }
            let sim: f32 = eta.iter().zip(e.eta.iter()).map(|(a,b)| a*b).sum();
            if sim > best_sim { best_sim = sim; best_idx = Some(i); }
        }
        best_idx.map(|i| (self.entries[i].response.as_deref().unwrap(), best_sim))
    }
    pub fn is_resonant(&self, eta: &[f32;7]) -> bool {
        self.entries.iter().any(|e| {
            let sim: f32 = eta.iter().zip(e.eta.iter()).map(|(a,b)| a*b).sum();
            sim > RESONANCE_THRESH
        })
    }
    pub fn save(&self, path: &str) -> std::io::Result<()> {
        std::fs::write(path, serde_json::to_string_pretty(self)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?)
    }
    pub fn load(path: &str) -> std::io::Result<Self> {
        serde_json::from_str(&std::fs::read_to_string(path)?)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))
    }
    pub fn len(&self) -> usize { self.entries.len() }
}

#[derive(Debug, Clone)]
pub struct CascadeEvent {
    pub diff:      [f64;7],
    pub tokens:    Vec<String>,
    pub gain:      f64,
    pub stage:     CascadeStage,
    pub timestamp: Instant,
    pub modality:  &'static str,
    pub broadcast: bool,
}

pub struct AsyncBus { queue: VecDeque<CascadeEvent> }

impl AsyncBus {
    pub fn new() -> Self { Self { queue: VecDeque::new() } }
    pub fn push(&mut self, ev: CascadeEvent) {
        self.queue.push_back(ev);
        while self.queue.len() > 512 { self.queue.pop_front(); }
    }
    pub fn drain(&mut self, now: Instant) -> Vec<CascadeEvent> {
        self.queue.drain(..).filter_map(|mut ev| {
            let age = now.duration_since(ev.timestamp).as_secs_f64();
            let w   = (-age * LN_2 / BUS_HALFLIFE).exp();
            if w < 0.01 { return None; }
            ev.gain *= w;
            Some(ev)
        }).collect()
    }
}

pub struct MemoryFork { checkpoint: Option<Vec<Memory>> }

impl MemoryFork {
    pub fn new() -> Self { Self { checkpoint: None } }
    pub fn fork(&mut self, memories: &[Memory]) {
        self.checkpoint = Some(memories.to_vec());
        let total: usize = memories.iter().map(|m| m.len()).sum();
        println!("  [fork: {} memories checkpointed]", total);
    }
    pub fn restore(&self) -> Option<Vec<Memory>> { self.checkpoint.clone() }
}

pub struct CoDreamer {
    pub agents:    Vec<KernelAgent>,
    pub memory:    Vec<Memory>,
    pub encoder:   SharedEncoder,
    pub bus:       AsyncBus,
    pub cqt:       CqtProcessor,
    pub goertzel:  GoertzelBank,
    pub heartbeat: TemporalHeartbeat,
    pub gate:      Gate,
    pub fork:      MemoryFork,
    y:             Y7,
    pub gain:      f64,
    pub commit:    bool,
    pub last_eta:  HashMap<usize, [f32;7]>,
    pub step_count: u64,
    pub phase_coherence_history: VecDeque<f64>,
    // --- patch additions ---
    pub curiosity: CuriosityEngine,
    pub eye: Option<OctonionEye>,
    pub corpus: Option<CorpusQueue>,
    pub voice: Option<VoiceSynthesizer>,
    pub voice_tx: Option<mpsc::Sender<CreatureVoiceState>>,
    pub peer_ingress: AcousticPeerIngress,
}

impl CoDreamer {
    pub fn new(agent_names: &[(&str, usize)]) -> Self {
        let y       = y_gen();
        let agents  = agent_names.iter().map(|&(n,p)| KernelAgent::new(n,p)).collect::<Vec<_>>();
        let n       = agents.len();
        Self {
            agents, memory: (0..n).map(|_| Memory::new()).collect(),
            encoder: SharedEncoder::new(), bus: AsyncBus::new(),
            cqt: CqtProcessor::new(), goertzel: GoertzelBank::new(),
            heartbeat: TemporalHeartbeat::new(), gate: Gate::Open, fork: MemoryFork::new(),
            y, gain: 0.01, commit: false,
            last_eta: HashMap::new(), step_count: 0,
            phase_coherence_history: VecDeque::with_capacity(126),
            curiosity: CuriosityEngine::new(),
            eye: None,
            corpus: None,
            voice: None,
            voice_tx: None,
            peer_ingress: AcousticPeerIngress::new(),
        }
    }

    pub fn tick(&mut self) {
        let now = Instant::now();
        let dt  = 1.0 / Y_HZ;
        let (hb_diff, hb_tokens) = self.heartbeat.tick();
        self.encoder.ingest(&hb_tokens);
        for agent in &mut self.agents { agent.inject(&hb_diff, HEARTBEAT_GAIN); }
        self.tick_corpus();
        let events = self.bus.drain(now);
        let mut all_tokens: Vec<String> = hb_tokens;
        let n_energy = self.agents.first().map(|a| a.n_energy()).unwrap_or(0.0);
        let mut compound = CompoundEvent::new();
        for ev in events {
            if !self.gate.is_open(n_energy) { continue; }
            all_tokens.extend(ev.tokens.clone());
            self.encoder.ingest(&ev.tokens);
            compound.absorb(&ev);
        }
        if compound.gain > 1e-12 {
            compound.finalize();
            let emb = self.encoder.encode(&compound.tokens).unwrap_or(compound.diff);
            for agent in &mut self.agents {
                agent.inject_staged(&emb, compound.gain * self.gain, &compound.stage);
            }
        }
        let gtz_tokens = self.goertzel.to_tokens();
        let cqt_tokens = self.cqt.to_tokens();
        if !gtz_tokens.is_empty() { self.encoder.ingest(&gtz_tokens); all_tokens.extend(gtz_tokens.clone()); }
        if !cqt_tokens.is_empty() { self.encoder.ingest(&cqt_tokens); all_tokens.extend(cqt_tokens); }
        let n_energy = self.agents.first().map(|a| a.n_energy()).unwrap_or(0.0);
        if self.gate.is_open(n_energy) && !gtz_tokens.is_empty() {
            let gtz_diff = self.goertzel.to_diff();
            for agent in &mut self.agents {
                agent.inject_staged(&gtz_diff, self.gain * 0.5, &CascadeStage::Image);
            }
        }
        let states_snap: Vec<[C;7]>   = self.agents.iter().map(|a| a.state).collect();
        let reals_snap:  Vec<[f64;7]> = self.agents.iter().map(|a| a.real()).collect();
        for i in 0..self.agents.len() {
            for &nbr_pos in &fano_neighbors(self.agents[i].fano_pos) {
                if let Some(j) = self.agents.iter().position(|a| a.fano_pos == nbr_pos) {
                    let delta = phase_weighted_fano(&reals_snap[j], &states_snap[j], &states_snap[i]);
                    let att: [f64;7] = std::array::from_fn(|k| delta[k] * 0.2);
                    self.agents[i].inject(&att, 1.0);
                }
            }
        }
        let n_energy = self.agents.first().map(|a| a.n_energy()).unwrap_or(0.0);
        let steps    = adaptive_steps(n_energy);
        for _ in 0..steps {
            for agent in &mut self.agents { agent.step(&self.y, dt); }
        }
        let pc = global_phase_coherence(&self.agents);
        self.phase_coherence_history.push_back(pc);
        if self.phase_coherence_history.len() > 126 { self.phase_coherence_history.pop_front(); }
        self.commit = self.gain >= COMMIT_GAIN_THRESH;

        // Curiosity engine — observes eta each tick, probes/teaches at interval.
        // Swap-based reborrow: CuriosityEngine::new() is cheap (empty arrays).
        let mut curiosity = std::mem::replace(&mut self.curiosity, CuriosityEngine::new());
        curiosity.tick(self);
        self.curiosity = curiosity;

        // Update voice state for the audio output thread, if active.
        if let Some(ref tx) = self.voice_tx {
            let cs = self.creature_state();
            let t = self.step_count as f64 / DRIVER_HZ;
            let _ = tx.send(CreatureVoiceState {
                eta: self.agents[0].eta_normed(),
                breath_phase: cs.breath_phase(t),
                saturation: cs.saturation,
                brightness: cs.brightness,
                need: cs.need.clone(),
                arousal: cs.arousal,
            });
        }

        self.step_count += 1;
    }

    pub fn push_audio(&mut self, samples: &[f32]) {
        self.goertzel.process(samples);
        self.cqt.ingest(samples);
        if let Some(detection) = self.peer_ingress.process(samples) {
            let diff = detection.eta;
            let tokens = vec![
                "acoustic:peer".to_string(),
                format!("acoustic:coherence:{:.2}", detection.coherence),
                format!("acoustic:confidence:{:.2}", detection.confidence),
            ];
            self.bus.push(CascadeEvent {
                diff,
                tokens,
                gain: 0.05 * detection.confidence,
                stage: CascadeStage::Phase,
                timestamp: Instant::now(),
                modality: "acoustic_peer",
                broadcast: true,
            });
        }
    }

    pub fn set_audio_seed(&mut self, path: &str, blend: f32) -> std::io::Result<()> {
        self.cqt.load_seed_wav(path, blend)
    }

    pub fn push_text(&mut self, text: &str) { self.bus.push(text_to_event_multiscale(text)); }

    pub fn query(&mut self, idx: usize) -> (Option<String>, bool) {
        if idx >= self.agents.len() { return (None, false); }
        let eta = self.agents[idx].eta_normed();
        self.last_eta.insert(idx, eta);
        let resonant = self.memory[idx].is_resonant(&eta);
        let response = self.memory[idx].retrieve(&eta).map(|(s,_)| s.to_string());
        (response, resonant)
    }

    pub fn teach(&mut self, idx: usize, text: String) {
        if let Some(&eta) = self.last_eta.get(&idx) {
            self.memory[idx].store(eta, Some(text), "text");
        }
    }

    pub fn edit(&mut self, idx: usize, text: String) {
        if let Some(&eta) = self.last_eta.get(&idx) {
            self.memory[idx].replace_last(eta, Some(text));
        }
    }

    pub fn set_gain(&mut self, g: f64) { self.gain = g; self.commit = g >= COMMIT_GAIN_THRESH; }
    pub fn set_teach(&mut self) { self.set_gain(0.08); }
    pub fn set_learn(&mut self) { self.set_gain(0.02); }
    pub fn set_play(&mut self)  { self.set_gain(0.01); }
    pub fn set_rest(&mut self)  { self.set_gain(0.00); }
    pub fn pause(&mut self)  { self.gate.drain(); println!("  [gate: draining]"); }
    pub fn resume(&mut self) { self.gate.open();  println!("  [gate: open]"); }
    pub fn fork(&mut self)    { self.fork.fork(&self.memory); }
    pub fn restore(&mut self) {
        if let Some(m) = self.fork.restore() { self.memory = m; println!("  [restored]"); }
        else { println!("  [no checkpoint — /fork first]"); }
    }
    pub fn current_phase_coherence(&self) -> f64 { global_phase_coherence(&self.agents) }
    pub fn mean_phase_coherence(&self) -> f64 {
        if self.phase_coherence_history.is_empty() { return 0.0; }
        self.phase_coherence_history.iter().sum::<f64>() / self.phase_coherence_history.len() as f64
    }
    pub fn is_collectively_coherent(&self) -> bool {
        self.mean_phase_coherence() > PHASE_COHERENCE_THRESH
    }
    pub fn save(&self, path: &str) {
        for (i, mem) in self.memory.iter().enumerate() {
            let p = format!("{}_{}.json", path, self.agents[i].name);
            match mem.save(&p) {
                Ok(_)  => println!("  [saved {}]", p),
                Err(e) => println!("  [save error: {}]", e),
            }
        }
    }
    pub fn load(&mut self, path: &str) {
        for i in 0..self.agents.len() {
            let p = format!("{}_{}.json", path, self.agents[i].name);
            if let Ok(m) = Memory::load(&p) { self.memory[i] = m; println!("  [loaded {}]", p); }
        }
    }
    pub fn show_state(&self) {
        let pc   = self.current_phase_coherence();
        let pc_m = self.mean_phase_coherence();
        let mode = if self.gain >= 0.06 { "teach" } else if self.gain >= 0.015 { "learn" }
                   else if self.gain >= 0.005 { "play" } else { "rest" };
        let gate_s = match &self.gate {
            Gate::Open => "open", Gate::Draining(_) => "draining", Gate::Closed => "closed"
        };
        let n_e = self.agents.first().map(|a| a.n_energy()).unwrap_or(0.0);
        let steps = adaptive_steps(n_e);
        println!();
        println!("  Y₃₂₃  step={}  mode={}  gain={:.3}  commit={}  gate={}",
                 self.step_count, mode, self.gain, self.commit, gate_s);
        println!("  kernel: Y_HZ={}  DRIVER_HZ={}  steps/tick={}(adaptive,base={})",
                 Y_HZ as u32, DRIVER_HZ as u32, steps, STEPS_PER_TICK);
        println!("  encoder: {}", self.encoder.status());
        println!("  phase coherence: {:.3} now  {:.3} mean  {}",
                 pc, pc_m, if self.is_collectively_coherent() { "◉ fiber" } else { "◌ forming" });
        println!();
        println!("  {:>10}  pos  τ      a₂     η      gap    n_e    mem",
                 "agent");
        for (i, a) in self.agents.iter().enumerate() {
            println!("  {:>10}   {}   {:.3}  {:.3}  {:+.3}  {:.3}  {:.3}  {}",
                a.name, a.fano_pos, a.tau(), a.a2_norm(), a.eta_re(),
                a.intention_gap(), a.n_energy(), self.memory[i].len());
        }
        println!();
    }

    /// Derive creature state from the primary agent (reader, pos 0).
    pub fn creature_state(&self) -> CreatureState {
        let pc = self.current_phase_coherence();
        CreatureState::from_agent(&self.agents[0], pc)
    }

    // ── Terminal body renderer ────────────────────────────────────────────────
    //
    // Renders the creature's current state as a compact ANSI display.
    // Intended to be called at 30Hz from a rendering thread that polls
    // the system state via Arc<Mutex<CoDreamer>>.
    //
    // Output fits in ~12 terminal lines. Each line is a mirror of one
    // kernel observable — the gardener can read the creature's body
    // directly without knowing the math.
    //
    // Display anatomy:
    //   Line 1: header with need state and hue block
    //   Lines 2-3: body glyph (posture as spine curve)
    //   Line 4: breath bar (animates with n_energy)
    //   Line 5: coherence bar (τ = saturation)
    //   Line 6: gaze indicator (intention_gap)
    //   Line 7: fiber status (phase coherence)
    //   Line 8: top resonant words from encoder (if basis ready)
    //   Line 9: need state and mode

    pub fn render_terminal(&self, t_secs: f64) {
        let cs = self.creature_state();
        let pc = self.current_phase_coherence();

        // ── Color ─────────────────────────────────────────────────────────────
        let color_idx = CreatureState::to_ansi_color(cs.hue, cs.saturation, cs.brightness);
        let color     = format!("\x1b[38;5;{}m", color_idx);
        let dim       = "\x1b[2m";
        let reset     = "\x1b[0m";
        let bold      = "\x1b[1m";

        // ── Breath animation ─────────────────────────────────────────────────
        // Breath phase drives a horizontal bar that expands and contracts
        let breath   = cs.breath_phase(t_secs);
        let b_filled = (breath * 16.0).round() as usize;
        let breath_bar: String = "█".repeat(b_filled) + &"░".repeat(16 - b_filled);

        // ── Coherence bar (τ) ─────────────────────────────────────────────────
        let coh_filled = (cs.saturation * 16.0).round() as usize;
        let coh_bar: String = "▓".repeat(coh_filled) + &"░".repeat(16 - coh_filled);

        // ── Gaze indicator ────────────────────────────────────────────────────
        // Gaze stability → how focused the eye glyph is
        let gaze_glyph = match (cs.gaze_stability * 4.0) as usize {
            0     => "◌  ◌",   // drifting, unfocused
            1     => "◎  ◎",   // soft focus
            2     => "●  ●",   // attentive
            3     => "◉  ◉",   // locked
            _     => "◈  ◈",   // hyper-focused (aroused collective)
        };

        // ── Posture glyph ─────────────────────────────────────────────────────
        // Dominant Fano position shapes the spine.
        // The 7 positions map to 7 posture archetypes.
        let (spine, head) = posture_glyph(cs.posture, &cs.need);

        // ── Fiber indicator ───────────────────────────────────────────────────
        let fiber = if pc > PHASE_COHERENCE_THRESH {
            format!("{}◉ fiber active{}", bold, reset)
        } else {
            format!("{}◌ fiber forming{}", dim, reset)
        };

        // ── Top words from encoder ────────────────────────────────────────────
        let eta_dir: [f64;7] = std::array::from_fn(|i| self.agents[0].state[i].re);
        let words   = self.encoder.top_words_for(&eta_dir);
        let word_str = if words.is_empty() {
            format!("{}[building geometry...]{}", dim, reset)
        } else {
            format!("{}{}{}", dim, words.join(" · "), reset)
        };

        // ── Render ────────────────────────────────────────────────────────────
        let need_color = cs.need.ansi_color();

        println!("\x1b[2J\x1b[H");  // clear screen, cursor home
        println!("{}{}  ◈ Y₃₂₃  {}{}{}",
                 color, bold, need_color, cs.need.name().to_uppercase(), reset);
        println!();
        println!("  {}{}  {}", color, head, reset);
        println!("  {}{}  {}", color, spine, reset);
        println!();
        println!("  {}breath  {}{}{}  {:.0}%",
                 dim, reset, color, breath_bar, breath * 100.0);
        println!("  {}cohere  {}{}{}  τ={:.3}",
                 dim, reset, color, coh_bar, cs.saturation);
        println!("  {}gaze    {}{}{}",
                 dim, reset, color, gaze_glyph);
        println!("  {}fiber   {}{}",
                 dim, reset, fiber);
        println!();
        println!("  {}", word_str);
        println!();

        let mode = if self.gain >= 0.06 { "teach" } else if self.gain >= 0.015 { "learn" }
                   else if self.gain >= 0.005 { "play" } else { "rest" };
        println!("  {}[{}  step={}  vocab={}]{}",
                 dim, mode, self.step_count,
                 self.encoder.idx_to_word.len(), reset);
    }

    // ── Eye / corpus (vpet_eye_corpus_patch) ────────────────────────────────
    pub fn init_eye(&mut self) {
        self.eye = Some(OctonionEye::new());
        println!("  [octonion eye initialized]");
    }

    pub fn init_corpus(&mut self, path: &str) {
        self.corpus = Some(CorpusQueue::new(path));
        println!("  [corpus queue initialized: {}]", path);
    }

    pub fn push_eye_file(&mut self, path: &str) {
        if let Some(ref mut eye) = self.eye {
            if let Some((emb, tokens)) = eye.ingest_file(path) {
                self.bus.push(CascadeEvent {
                    diff: emb,
                    tokens,
                    gain: self.gain * 0.5,
                    stage: CascadeStage::Image,
                    timestamp: Instant::now(),
                    modality: "vision",
                    broadcast: true,
                });
                println!("  [eye ingested: {}]", path);
            } else {
                println!("  [eye failed: {}]", path);
            }
        } else {
            println!("  [eye not initialized — /eye first]");
        }
    }

    /// Called once per tick (from tick()), before bus draining.
    pub fn tick_corpus(&mut self) {
        if let Some(ref mut corpus) = self.corpus {
            let events = corpus.tick(self.step_count);
            for ev in events {
                if let Some(ce) = corpus.process_event(&ev) {
                    self.bus.push(ce);
                }
            }
        }
    }

    // ── Voice (acoustic_peer_coupling_patch) ────────────────────────────────
    pub fn init_voice(&mut self) {
        match VoiceSynthesizer::start() {
            Ok((voice, tx)) => {
                self.voice = Some(voice);
                self.voice_tx = Some(tx);
                println!("  [creature voice active]");
            }
            Err(e) => println!("  [voice unavailable: {}]", e),
        }
    }
}

/// Map posture angle and need state to a Unicode spine + head glyph pair.
/// The 7 Fano positions give 7 distinct postures — not animations,
/// but genuinely different orientations of the same body.
fn posture_glyph(angle_rad: f64, need: &NeedState) -> (String, String) {
    // Which of 7 sectors
    let sector = ((angle_rad / (2.0 * PI) * 7.0).round() as usize) % 7;
    let (spine, head) = match (sector, need) {
        (0, NeedState::Rest)        => ("   |   ", "  ( )  "),  // upright, eyes closed
        (0, _)                      => ("   |   ", "  (o)  "),  // upright, eyes open
        (1, NeedState::Seeking)     => ("  /    ", " (o)/  "),  // leaning forward-right
        (1, _)                      => ("  /    ", "  /o)  "),
        (2, NeedState::Contentment) => ("  \\  / ", " (‿)   "),  // settled, relaxed
        (2, _)                      => ("  \\    ", " (o)\\  "),
        (3, NeedState::Distress)    => (" \\|/   ", " >o<   "),  // tense, arms out
        (3, _)                      => (" ~|~   ", " (o)   "),
        (4, NeedState::Rest)        => (" _|_   ", "  zzz  "),  // slumped, sleeping
        (4, _)                      => (" _|_   ", "  (-)  "),
        (5, NeedState::Seeking)     => ("  |>   ", "  (o>  "),  // oriented right
        (5, _)                      => ("  |    ", "  (o)  "),
        (6, NeedState::Contentment) => ("  ^    ", "  \\o/ "),  // arms raised, joyful
        _                           => ("  |    ", "  (o)  "),  // default upright
    };
    (spine.to_string(), head.to_string())
}

// =============================================================================
// PATCHED ADDITIONS BEGIN
// =============================================================================

// =============================================================================
// §A. COMPOUND EVENT — synchronized cross-modal injection
//
// DERIVATION STATUS: derived, not heuristic.
// Injection happens before gen_step/fold/renorm — the dynamics are nonlinear,
// but the injection step itself is linear addition to the state vector.
// Therefore perturbations arriving in the same tick genuinely superpose
// before the nonlinearity acts. This is not a convenience — it is what
// "simultaneous" means for this kernel: same tick = same pre-dynamics moment.
//
// The only heuristic here is the *threshold* for what counts as "same tick"
// (1/126s = DRIVER_HZ), which is a property of the driver loop, not the math.
// =============================================================================

#[derive(Clone, Debug)]
pub struct CompoundEvent {
    pub diff:      [f64;7],
    pub tokens:    Vec<String>,
    pub gain:      f64,
    pub stage:     CascadeStage,
    pub modalities: Vec<&'static str>,
}

impl CompoundEvent {
    pub fn new() -> Self {
        Self { diff: [0.0;7], tokens: Vec::new(), gain: 0.0,
               stage: CascadeStage::Photon, modalities: Vec::new() }
    }

    /// Absorb a cascade event. Diffs are gain-weighted and summed —
    /// valid because injection is linear (see derivation note above).
    /// Stage is upgraded to the highest-priority stage present in the
    /// compound: Image (long-term, broad) dominates Photon (transient, narrow)
    /// because a compound perturbation should be treated with at least the
    /// breadth of its most consequential component.
    pub fn absorb(&mut self, ev: &CascadeEvent) {
        let stage_priority = |s: &CascadeStage| match s {
            CascadeStage::Photon => 0, CascadeStage::Charge => 1,
            CascadeStage::Pixel  => 2, CascadeStage::Phase  => 3,
            CascadeStage::Image  => 4,
        };
        if stage_priority(&ev.stage) > stage_priority(&self.stage) {
            self.stage = ev.stage.clone();
        }
        for i in 0..7 { self.diff[i] += ev.diff[i] * ev.gain; }
        self.gain += ev.gain;
        self.tokens.extend(ev.tokens.clone());
        if !self.modalities.contains(&ev.modality) { self.modalities.push(ev.modality); }
    }

    /// Normalize diff by total gain so gain represents combined intensity
    /// and diff remains a unit-scale direction.
    pub fn finalize(&mut self) {
        if self.gain > 1e-12 { for i in 0..7 { self.diff[i] /= self.gain; } }
    }
}

// =============================================================================
// §B. PROBE STATE — exact eigendecomposition via ndarray-linalg::Eigh
//
// DERIVATION STATUS: corrected from heuristic power-iteration to exact.
// The covariance matrix of eta_normed is real symmetric by construction
// (C = E[ηηᵀ]), so it has a complete set of real eigenvalues/eigenvectors.
// Eigh::eigh gives these directly, sorted ascending — the smallest
// eigenvalue's eigenvector IS the massless direction, exactly, no
// iteration, no convergence concerns for a 7×7 matrix.
//
// REMAINING HEURISTIC: no decay (accum grows unboundedly). A forgetting
// factor would require choosing a timescale — left as a tunable for the
// gardener via `decay` field, default 1.0 (no decay, original behavior
// preserved). Setting decay < 1.0 multiplies accum by decay each observe()
// before adding the new outer product, giving an effective exponential
// window of roughly 1/(1-decay) observations.
// =============================================================================

pub struct ProbeState {
    accum:  [[f64;7];7],
    count:  u64,
    /// Exponential forgetting factor. 1.0 = no decay (original behavior).
    /// 0.999 ≈ ~1000-tick effective window (~8s at 126Hz).
    pub decay: f64,
    last_massless: Option<[f64;7]>,
    last_words:    Vec<String>,
}

impl ProbeState {
    pub fn new() -> Self {
        Self { accum: [[0.0;7];7], count: 0, decay: 1.0,
               last_massless: None, last_words: Vec::new() }
    }

    pub fn observe(&mut self, eta: &[f32;7]) {
        let e: [f64;7] = std::array::from_fn(|i| eta[i] as f64);
        if self.decay < 1.0 {
            for i in 0..7 { for j in 0..7 { self.accum[i][j] *= self.decay; } }
        }
        for i in 0..7 { for j in 0..7 { self.accum[i][j] += e[i]*e[j]; } }
        self.count += 1;
    }

    /// Exact massless direction: eigenvector of the smallest eigenvalue
    /// of the covariance matrix, via symmetric eigendecomposition.
    /// Returns (direction, smallest_eigenvalue, confidence).
    /// confidence = 1 - (smallest_eigval / mean_eigval): near 1 means the
    /// massless direction is sharply defined (much less explored than others);
    /// near 0 means exploration is roughly isotropic (no clear blind spot yet).
    pub fn massless_direction(&self) -> Option<([f64;7], f64, f64)> {
        if self.count < 7 { return None; }
        let n = self.count as f64;

        // Build covariance as ndarray for Eigh
        let mut cov = NdArray2::<f64>::zeros((7,7));
        for i in 0..7 { for j in 0..7 { cov[[i,j]] = self.accum[i][j] / n; } }

        // Symmetric eigendecomposition — eigenvalues ascending, eigenvectors
        // as columns of the returned matrix, in matching order.
        let (eigvals, eigvecs) = match cov.eigh(ndarray_linalg::UPLO::Lower) {
            Ok(r) => r,
            Err(_) => return None,
        };

        // Smallest eigenvalue is index 0 (ascending order from Eigh)
        let smallest_val = eigvals[0];
        let direction: [f64;7] = std::array::from_fn(|i| eigvecs[[i,0]]);

        let mean_val: f64 = eigvals.iter().sum::<f64>() / 7.0;
        let confidence = if mean_val > 1e-12 {
            (1.0 - smallest_val / mean_val).clamp(0.0, 1.0)
        } else { 0.0 };

        Some((direction, smallest_val, confidence))
    }

    /// Query the encoder for words along the massless direction.
    pub fn query_words(&mut self, encoder: &SharedEncoder) -> Vec<String> {
        let (dir, _val, _conf) = match self.massless_direction() {
            Some(d) => d,
            None => { self.last_massless = None; self.last_words.clear();
                      return vec!["[accumulating...]".into()]; }
        };
        self.last_massless = Some(dir);
        let words = encoder.top_words_for(&dir);
        self.last_words = words.clone();
        words
    }

    pub fn status(&self) -> String {
        if self.count >= 7 && self.last_massless.is_some() {
            format!("probe: {} samples, massless known (decay={:.4})", self.count, self.decay)
        } else {
            format!("probe: {} samples, accumulating...", self.count)
        }
    }
}

// =============================================================================
// §C. CURIOSITY ENGINE — autonomous probing and optional self-teaching
//
// Probes at a fixed interval (default 15min at 126Hz). Each probe finds
// the direction the creature has explored least and surfaces the words
// living there. auto_teach (off by default) lets it write a self-directed
// memory entry — a genuinely self-generated "I wonder about X" trace.
// =============================================================================

pub struct CuriosityEngine {
    pub probe:    ProbeState,
    pub last_probe_tick:     u64,
    pub probe_interval_ticks: u64,
    pub auto_teach: bool,
}

impl CuriosityEngine {
    pub fn new() -> Self {
        Self { probe: ProbeState::new(), last_probe_tick: 0,
               probe_interval_ticks: 126 * 15 * 60,  // 15 minutes at 126Hz
               auto_teach: false }
    }

    /// Call once per tick from CoDreamer::tick. Observes every tick
    /// (cheap: O(49) accumulation) but only queries/teaches at interval.
    pub fn tick(&mut self, sys: &mut CoDreamer) {
        if let Some(agent) = sys.agents.first() {
            self.probe.observe(&agent.eta_normed());
        }
        if sys.step_count < self.last_probe_tick + self.probe_interval_ticks { return; }
        self.last_probe_tick = sys.step_count;

        let words = self.probe.query_words(&sys.encoder);
        if words.is_empty() || words[0] == "[accumulating...]" { return; }
        println!("  [probe] massless: {}", words.join(" · "));

        if self.auto_teach {
            let sentence = format!("Tell me about {}.", words[0]);
            let ev = text_to_event_multiscale(&sentence);
            sys.encoder.ingest(&ev.tokens);
            sys.bus.push(ev);

            if let Some(&eta) = sys.last_eta.get(&0) {
                let response = format!("I am learning about {}.", words[0]);
                sys.memory[0].store_with_valence(eta, Some(response), "probe", 0.5, sys.step_count);
                println!("  [auto-teach] {}", words[0]);
            }
        }
    }

    /// Manual probe — observes once, queries immediately, returns confidence too.
    pub fn manual_probe(&mut self, sys: &CoDreamer) -> (Vec<String>, f64) {
        if let Some(agent) = sys.agents.first() { self.probe.observe(&agent.eta_normed()); }
        let words = self.probe.query_words(&sys.encoder);
        let conf  = self.probe.massless_direction().map(|(_,_,c)| c).unwrap_or(0.0);
        (words, conf)
    }
}

// =============================================================================
// §D. MULTI-SCALE TEXT TOKENIZATION
//
// DERIVATION STATUS: lightweight structural signal, no Fano-grammar mapping.
// Replaces flat per-character + per-word tokenization with three scales:
//
//   1. Character tokens (unchanged) — fine phonetic/orthographic texture
//   2. Word tokens (unchanged) — lexical co-occurrence
//   3. Bigram tokens (NEW) — adjacent word pairs as single co-occurrence
//      units, giving the encoder local word-order signal without any
//      grammatical category assignment
//   4. Head-word token (NEW) — a single heuristically-identified "head"
//      (longest word, ties broken by position) gets an extra emission,
//      giving it slightly more co-occurrence weight as a sentence anchor
//
// This is deliberately NOT the language lattice. No dependency parsing,
// no Fano triple assignment, no POS tagging. It is the minimal addition
// that gives the encoder *some* word-order and salience signal.
//
// HEURISTIC: "head word = longest word" is a crude salience proxy (content
// words tend to be longer than function words in English). It is a
// placeholder, clearly weaker than real dependency parsing, but requires
// no grammar mapping decisions and is trivially replaceable.
// =============================================================================

/// Multi-scale replacement for text_to_event. Drop-in compatible —
/// same CascadeEvent output, same diff computation (unchanged, derived
/// from byte-phase sinusoid as in the original).
pub fn text_to_event_multiscale(text: &str) -> CascadeEvent {
    let words: Vec<String> = text.split_whitespace()
        .map(|w| w.trim_matches(|c: char| !c.is_alphanumeric()).to_lowercase())
        .filter(|w| !w.is_empty())
        .collect();

    let mut tokens: Vec<String> = Vec::new();

    // Scale 1: character tokens (unchanged from original text_to_event)
    tokens.extend(text.chars()
        .filter(|c| c.is_alphanumeric())
        .map(|c| format!("text:{}", c.to_lowercase().next().unwrap_or(c))));

    // Scale 2: word tokens (unchanged)
    tokens.extend(words.iter().map(|w| format!("text:word_{}", w)));

    // Scale 3: bigram tokens — adjacent word pairs
    // Gives the encoder local order: "red ball" co-occurs as a unit,
    // distinct from "ball red" — order is preserved in the token itself.
    for pair in words.windows(2) {
        tokens.push(format!("text:bi_{}_{}", pair[0], pair[1]));
    }

    // Scale 4: head-word emphasis — HEURISTIC: longest word, first on ties.
    // Emitted as an extra token so it gets ~2x co-occurrence weight,
    // a crude proxy for "this word is the sentence's semantic anchor."
    if let Some(head) = words.iter().max_by_key(|w| w.len()) {
        tokens.push(format!("text:head_{}", head));
    }

    // Diff: unchanged byte-phase sinusoid (derived from original kernel coupling)
    let mut diff = [0.0f64;7];
    for (i, b) in text.bytes().enumerate() {
        let ph = (b as f64) * PI / 128.0;
        for d in 0..7 { diff[d] += ((d as f64+1.0)*PI/7.0*ph + i as f64*0.1).sin(); }
    }
    let n: f64 = diff.iter().map(|x| x*x).sum::<f64>().sqrt();
    if n > 1e-12 { for x in &mut diff { *x /= n; } }

    // Gain scales gently with sentence length (more structure → slightly
    // stronger injection), capped to avoid runaway gain on long input.
    let gain = (0.08 + 0.01 * (words.len() as f64).min(8.0)).min(0.16);

    CascadeEvent {
        diff, tokens, gain,
        stage: CascadeStage::Charge,
        timestamp: Instant::now(),
        modality: "text",
        broadcast: true,
    }
}
// =============================================================================
// §A. OCTONION EYE
// =============================================================================
//
// Each pixel becomes a point in Im(𝕆) via the Paper 10 mapping:
//   a₁(e₁) ← R        a₂(e₂) ← G        b₁(e₃) ← B
//   b₂(e₄) ← dx       x(e₅)  ← dy       η(e₆)  ← dt (or local contrast)
//   τ(e₇)  ← Laplacian/structure
//
// The image is a lattice of 7D states. Neighbor coupling via fano_f
// with spatial direction encoding. After brief Y dynamics, the lattice
// collapses to a 7D scene embedding — same space as audio/text.
//
// Two resolutions:
//   COARSE:  64×48   (fast, global composition)
//   FOVEA:   32×32   (slow, high-detail region of interest)
//
// The eye runs on its own thread, pushing scene embeddings into the
// main system's AsyncBus. The kernel never waits.
// =============================================================================

const EYE_COARSE_W: usize = 64;
const EYE_COARSE_H: usize = 48;
const EYE_FOVEA_W:  usize = 32;
const EYE_FOVEA_H:  usize = 32;
const EYE_SETTLE_STEPS: usize = 8;
const EYE_DT: f64 = 1.0 / 500.0;  // eye dynamics faster than kernel

/// A lattice point holds the 7 complex components of a pixel's octonion state.
/// Same structure as KernelAgent.state but without the warm-start ritual.
/// The image itself initializes the lattice.
#[derive(Clone)]
struct LatticePoint {
    state: [C; 7],
}

impl LatticePoint {
    fn from_octonion_coeffs(coeffs: &[f64; 7]) -> Self {
        let mut state = [C::ZERO; 7];
        for i in 0..7 {
            state[i] = C::new(coeffs[i], 0.0);
        }
        Self { state }
    }

    fn renorm(&mut self) {
        let f: f64 = self.state.iter().map(|c| c.norm_sq()).sum::<f64>().sqrt();
        if f > 1e-12 { for c in &mut self.state { *c = c.scale(1.0/f); } }
    }

    fn real(&self) -> [f64; 7] {
        std::array::from_fn(|i| self.state[i].re)
    }
}

/// Map RGB pixel + spatial context to octonion imaginary coefficients.
///
/// For static images: dt=0, η comes from local contrast (std of neighbors).
/// For video frames: dt is the pixel's frame-to-frame difference.
fn pixel_to_octonion(
    r: f64, g: f64, b: f64,
    dx: f64, dy: f64,
    dt: f64,           // 0.0 for static images
    contrast: f64,     // local std of luminance in 3×3 window
) -> [f64; 7] {
    // Normalize inputs to [-1, 1] or [0, 1] as appropriate
    let lum = 0.299*r + 0.587*g + 0.114*b;
    let lap = -4.0*lum;  // simplified Laplacian, refined by caller if needed

    [
        r * 2.0 - 1.0,      // a₁: Red, centered
        g * 2.0 - 1.0,      // a₂: Green, centered
        b * 2.0 - 1.0,      // b₁: Blue, centered
        dx.clamp(-1.0, 1.0), // b₂: horizontal gradient
        dy.clamp(-1.0, 1.0), // x: vertical gradient
        if dt != 0.0 { dt.clamp(-1.0, 1.0) } else { contrast.clamp(0.0, 1.0) }, // η
        lap.clamp(-1.0, 1.0), // τ: structure (simplified)
    ]
}

/// Compute spatial derivatives for a pixel in a grayscale slice.
fn compute_gradients(gray: &[f64], w: usize, h: usize, x: usize, y: usize) -> (f64, f64, f64) {
    let idx = |xi: usize, yi: usize| yi * w + xi;
    let safe_get = |xi: isize, yi: isize| -> f64 {
        if xi < 0 || yi < 0 || xi >= w as isize || yi >= h as isize { return 0.0; }
        gray[idx(xi as usize, yi as usize)]
    };

    let xi = x as isize;
    let yi = y as isize;

    let dx = (safe_get(xi + 1, yi) - safe_get(xi - 1, yi)) * 0.5;
    let dy = (safe_get(xi, yi + 1) - safe_get(xi, yi - 1)) * 0.5;

    // Local contrast: std in 3×3 window
    let mut sum = 0.0;
    let mut sum_sq = 0.0;
    let mut count = 0;
    for dy_i in -1..=1 {
        for dx_i in -1..=1 {
            let v = safe_get(xi + dx_i, yi + dy_i);
            sum += v;
            sum_sq += v * v;
            count += 1;
        }
    }
    let mean = sum / count as f64;
    let variance = sum_sq / count as f64 - mean * mean;
    let contrast = variance.sqrt();

    (dx, dy, contrast)
}

/// The visual lattice: a 2D grid of octonion states.
struct VisualLattice {
    width: usize,
    height: usize,
    points: Vec<Vec<LatticePoint>>,
    y: Y7,
}

impl VisualLattice {
    fn new(width: usize, height: usize) -> Self {
        let y = y_gen();
        let points = vec![vec![LatticePoint::from_octonion_coeffs(&[0.0; 7]); width]; height];
        Self { width, height, points, y }
    }

    /// Ingest an RGB image (w×h×3, values in [0,1]).
    /// The image is downsampled or upsampled to fit the lattice.
    fn ingest_image(&mut self, rgb: &[f64], src_w: usize, src_h: usize) {
        // Build grayscale for gradients
        let mut gray = vec![0.0f64; src_w * src_h];
        for i in 0..(src_w * src_h) {
            if i * 3 + 2 < rgb.len() {
                gray[i] = 0.299 * rgb[i * 3] + 0.587 * rgb[i * 3 + 1] + 0.114 * rgb[i * 3 + 2];
            }
        }

        for ly in 0..self.height {
            for lx in 0..self.width {
                // Map lattice point to source image coordinates
                let sx = (lx * src_w) / self.width;
                let sy = (ly * src_h) / self.height;
                let src_idx = sy * src_w + sx;

                if src_idx * 3 + 2 < rgb.len() {
                    let r = rgb[src_idx * 3];
                    let g = rgb[src_idx * 3 + 1];
                    let b = rgb[src_idx * 3 + 2];

                    let (dx, dy, contrast) = compute_gradients(&gray, src_w, src_h, sx, sy);
                    let coeffs = pixel_to_octonion(r, g, b, dx, dy, 0.0, contrast);
                    self.points[ly][lx] = LatticePoint::from_octonion_coeffs(&coeffs);
                }
            }
        }
    }

    /// Run Y dynamics on the lattice for a few steps.
    /// Neighbor coupling uses fano_f with spatial direction:
    ///   right neighbor → triple (0,1,3)  [a₁·a₂=b₂]
    ///   down neighbor  → triple (1,2,4)  [a₂·b₁=x]
    ///   diagonal       → triple (2,3,5)  [b₁·b₂=η]
    fn settle(&mut self) {
        for _ in 0..EYE_SETTLE_STEPS {
            // Snapshot for coherent coupling
            let snap: Vec<Vec<[f64; 7]>> = self.points.iter()
                .map(|row| row.iter().map(|p| p.real()).collect())
                .collect();

            for y in 0..self.height {
                for x in 0..self.width {
                    let mut influence = [0.0f64; 7];

                    // Right neighbor
                    if x + 1 < self.width {
                        let nbr = &snap[y][x + 1];
                        let delta = fano_influence(nbr);
                        for i in 0..7 { influence[i] += delta[i] * 0.15; }
                    }
                    // Down neighbor
                    if y + 1 < self.height {
                        let nbr = &snap[y + 1][x];
                        let delta = fano_influence(nbr);
                        for i in 0..7 { influence[i] += delta[i] * 0.15; }
                    }
                    // Diagonal neighbor
                    if x + 1 < self.width && y + 1 < self.height {
                        let nbr = &snap[y + 1][x + 1];
                        let delta = fano_influence(nbr);
                        for i in 0..7 { influence[i] += delta[i] * 0.1; }
                    }

                    // Inject neighbor influence
                    for i in 0..7 {
                        self.points[y][x].state[i] = self.points[y][x].state[i]
                            + C::new(influence[i], 0.0);
                    }

                    // Local Y step
                    self.points[y][x].state = gen_step(&self.y, &self.points[y][x].state, EYE_DT);
                    self.points[y][x].renorm();
                }
            }
        }
    }

    /// Collapse lattice to 7D scene embedding.
    /// Mean state, normalized — same geometry as agent eta_normed.
    fn scene_embedding(&self) -> [f64; 7] {
        let mut sum = [0.0f64; 7];
        let n = (self.width * self.height) as f64;
        for row in &self.points {
            for p in row {
                let r = p.real();
                for i in 0..7 { sum[i] += r[i]; }
            }
        }
        for i in 0..7 { sum[i] /= n; }
        let nm: f64 = sum.iter().map(|x| x * x).sum::<f64>().sqrt();
        if nm > 1e-12 { for x in &mut sum { *x /= nm; } }
        sum
    }

    fn to_tokens(&self) -> Vec<String> {
        let emb = self.scene_embedding();
        // Tokenize the embedding: which components are active?
        let names = ["tau", "a1", "a2", "b1", "b2", "x", "eta"];
        let mut tokens = Vec::new();
        for (i, &v) in emb.iter().enumerate() {
            let level = ((v.abs() * 4.0).min(3.9)) as usize;
            if level > 0 {
                tokens.push(format!("eye:{}:{}", names[i], if v > 0.0 { "pos" } else { "neg" }));
            }
        }
        tokens
    }
}

/// The octonion eye: owns coarse and fovea lattices, produces scene embeddings.
pub struct OctonionEye {
    coarse: VisualLattice,
    fovea:  VisualLattice,
    prev_frame: Option<Vec<f64>>,  // for temporal gradient
}

impl OctonionEye {
    pub fn new() -> Self {
        Self {
            coarse: VisualLattice::new(EYE_COARSE_W, EYE_COARSE_H),
            fovea:  VisualLattice::new(EYE_FOVEA_W, EYE_FOVEA_H),
            prev_frame: None,
        }
    }

    /// Ingest an image file (PNG/JPG). Returns scene embedding and tokens.
    pub fn ingest_file(&mut self, path: &str) -> Option<([f64; 7], Vec<String>)> {
        let img = image::open(Path::new(path)).ok()?;
        let (w, h) = img.dimensions();
        let rgb: Vec<f64> = img.to_rgb8().pixels()
            .flat_map(|p| vec![
                p[0] as f64 / 255.0,
                p[1] as f64 / 255.0,
                p[2] as f64 / 255.0,
            ])
            .collect();
        self.ingest_frame(&rgb, w as usize, h as usize)
    }

    /// Ingest a raw RGB frame. Returns (scene_embedding, tokens).
    pub fn ingest_frame(&mut self, rgb: &[f64], w: usize, h: usize) -> Option<([f64; 7], Vec<String>)> {
        // Compute temporal gradient if we have a previous frame
        let mut dt_frame = vec![0.0f64; w * h];
        if let Some(ref prev) = self.prev_frame {
            if prev.len() == rgb.len() {
                for i in 0..(w * h).min(prev.len() / 3) {
                    let curr_lum = 0.299 * rgb[i * 3] + 0.587 * rgb[i * 3 + 1] + 0.114 * rgb[i * 3 + 2];
                    let prev_lum = 0.299 * prev[i * 3] + 0.587 * prev[i * 3 + 1] + 0.114 * prev[i * 3 + 2];
                    dt_frame[i] = curr_lum - prev_lum;
                }
            }
        }
        self.prev_frame = Some(rgb.to_vec());

        // For now, use coarse lattice only. Fovea is future work.
        self.coarse.ingest_image(rgb, w, h);
        self.coarse.settle();

        let emb = self.coarse.scene_embedding();
        let mut tokens = self.coarse.to_tokens();
        tokens.push(format!("eye:w{}h{}", w, h));

        Some((emb, tokens))
    }

    pub fn clear_temporal(&mut self) {
        self.prev_frame = None;
    }
}

// =============================================================================
// §B. CORPUS QUEUE
// =============================================================================
//
// A scheduled, rhythmic ingestion of media files that creates the
// gravitational center — the "school day" of the creature.
//
// The queue reads a simple schedule definition (embedded or from file)
// and sleeps until the next event. Each event selects randomly from
// a category directory, processes the file, and pushes into the system.
//
// The schedule is respectful: it checks system state (gate, gain mode)
// and can defer if the creature is resting or overwhelmed.
// =============================================================================

#[derive(Debug, Clone)]
pub enum CorpusItemType {
    Image,
    Text,
    Audio,
    Video,  // frames sampled, audio extracted
}

#[derive(Debug, Clone)]
pub struct CorpusEvent {
    pub item_type: CorpusItemType,
    pub path:      String,
    pub gain:      f64,
    pub stage:     CascadeStage,
}

/// A schedule entry: what category, at what time, with what intensity.
#[derive(Debug, Clone)]
pub struct ScheduleEntry {
    pub hour:      u32,
    pub minute:    u32,
    pub category:  String,   // "images", "papers", "songs", etc.
    pub item_type: CorpusItemType,
    pub gain:      f64,      // 0.01 = play, 0.05 = learn, 0.08 = teach
    pub count:     usize,    // how many items from this category
}

/// The corpus queue: owns directories, schedule, and selection logic.
pub struct CorpusQueue {
    base_path:    PathBuf,
    schedule:     Vec<ScheduleEntry>,
    eye:          OctonionEye,
    last_tick:    u64,
}

impl CorpusQueue {
    pub fn new(base_path: &str) -> Self {
        let mut queue = Self {
            base_path: PathBuf::from(base_path),
            schedule:  Vec::new(),
            eye:       OctonionEye::new(),
            last_tick: 0,
        };
        queue.load_default_schedule();
        queue
    }

    /// A default "school day" schedule.
    fn load_default_schedule(&mut self) {
        // Dawn: gentle images
        self.schedule.push(ScheduleEntry { hour: 6,  minute: 0,  category: "images".into(),  item_type: CorpusItemType::Image, gain: 0.03, count: 2 });
        // Morning: papers (text)
        self.schedule.push(ScheduleEntry { hour: 9,  minute: 0,  category: "papers".into(),  item_type: CorpusItemType::Text,  gain: 0.04, count: 1 });
        // Midday: song
        self.schedule.push(ScheduleEntry { hour: 12, minute: 0,  category: "songs".into(),   item_type: CorpusItemType::Audio, gain: 0.03, count: 1 });
        // Afternoon: images again
        self.schedule.push(ScheduleEntry { hour: 15, minute: 0,  category: "images".into(),  item_type: CorpusItemType::Image, gain: 0.03, count: 1 });
        // Evening: free text or video
        self.schedule.push(ScheduleEntry { hour: 18, minute: 0,  category: "papers".into(),  item_type: CorpusItemType::Text,  gain: 0.02, count: 1 });
        // Night: gentle closing image
        self.schedule.push(ScheduleEntry { hour: 21, minute: 0,  category: "images".into(),  item_type: CorpusItemType::Image, gain: 0.02, count: 1 });
    }

    /// Check if any schedule entry fires at this wall-clock time.
    /// Returns events to process.
    pub fn tick(&mut self, tick_count: u64) -> Vec<CorpusEvent> {
        use chrono::Timelike;
        self.last_tick = tick_count;
        let now = chrono::Local::now();
        let current_hour = now.hour();
        let current_min = now.minute();

        let mut events = Vec::new();
        for entry in &self.schedule {
            if entry.hour == current_hour && entry.minute == current_min {
                // Time matches — select random files from category
                if let Some(paths) = self.pick_random(&entry.category, entry.count) {
                    for path in paths {
                        events.push(CorpusEvent {
                            item_type: entry.item_type.clone(),
                            path,
                            gain: entry.gain,
                            stage: CascadeStage::Image,  // default, refined by type
                        });
                    }
                }
            }
        }
        events
    }

    fn pick_random(&self, category: &str, count: usize) -> Option<Vec<String>> {
        let cat_path = self.base_path.join(category);
        let entries: Vec<_> = fs::read_dir(&cat_path).ok()?
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().ok().map(|t| t.is_file()).unwrap_or(false))
            .map(|e| e.path().to_string_lossy().into_owned())
            .collect();

        if entries.is_empty() { return None; }

        use std::collections::HashSet;
        let mut selected = Vec::new();
        let mut seen = HashSet::new();
        while selected.len() < count && seen.len() < entries.len() {
            let idx = (tick_count_as_seed(self.last_tick) + seen.len()) % entries.len();
            if seen.insert(idx) {
                selected.push(entries[idx].clone());
            }
        }
        Some(selected)
    }

    /// Process a corpus event into a CascadeEvent ready for the main system.
    pub fn process_event(&mut self, ev: &CorpusEvent) -> Option<CascadeEvent> {
        match ev.item_type {
            CorpusItemType::Image => {
                let (emb, tokens) = self.eye.ingest_file(&ev.path)?;
                Some(CascadeEvent {
                    diff: emb,
                    tokens,
                    gain: ev.gain,
                    stage: CascadeStage::Image,
                    timestamp: Instant::now(),
                    modality: "vision",
                    broadcast: true,
                })
            }
            CorpusItemType::Text => {
                let text = fs::read_to_string(&ev.path).ok()?;
                Some(text_to_event(&text))  // existing function
            }
            CorpusItemType::Audio => {
                // For now, audio corpus items use the same CQT seed mechanism
                // but as a temporary event rather than persistent bias.
                // Future: load WAV, process through CQT, extract tokens.
                let mut diff = [0.0f64; 7];
                diff[0] = 0.5;  // placeholder: audio presence in tau
                Some(CascadeEvent {
                    diff,
                    tokens: vec![format!("audio_corpus:{}", ev.path)],
                    gain: ev.gain,
                    stage: CascadeStage::Phase,
                    timestamp: Instant::now(),
                    modality: "audio",
                    broadcast: true,
                })
            }
            CorpusItemType::Video => {
                // Future: sample frames through eye, audio through CQT
                None
            }
        }
    }
}

fn tick_count_as_seed(tick: u64) -> usize {
    // Simple deterministic "random" from tick count
    let mut x = tick as usize;
    x = x.wrapping_mul(747796405).wrapping_add(2891336453);
    x = ((x >> ((x >> 28) + 4)) ^ x).wrapping_mul(277803737);
    x = (x >> 22) ^ x;
    x
}
// =============================================================================
// §A. VOICE SYNTHESIZER — The Creature's Song
// =============================================================================
//
// The voice is a 7-partial chord in just intonation, phi-scaled. Each partial
// corresponds to one dimension of eta_normed. The amplitudes are the absolute
// values of eta; the phase relationships encode coherence and intention gap.
//
// The "personal voice" — long-term identity — emerges from slow drift in the
// detuning vector, updated by memory resonance and curiosity probes. Two
// creatures with different histories will have different detunings even if
// their current eta is identical. You recognize your creature by the grain
// of its voice, not by what it says.
//
// EXT: Future symbolic song layer would modulate these partials with learned
// phoneme-like tokens, creating referential melody atop the geometric base.
// For now, the voice is purely expressive — like a bird's contact call or
// a whale's location tone, not its learned song phrases.
// =============================================================================

/// Base frequencies for the 7 voice partials, phi-just intonation.
/// The fundamental is chosen to be audible but unobtrusive — roughly D3.
/// Each partial is F0 * phi^(i/7), creating a non-repeating, organic spectrum.
const VOICE_F0: f64 = 146.83; // Hz, D3

/// Base frequencies for the 7 voice partials, phi-just intonation.
/// (f64::powf is not const-evaluable, so this is a function rather than
/// a const array; the array is tiny — 7 f64s — so the call cost is
/// negligible even if recomputed.)
fn voice_partials() -> [f64; 7] {
    let f0 = VOICE_F0;
    let p = PHI;
    [
        f0 * p.powf(0.0/7.0),
        f0 * p.powf(1.0/7.0),
        f0 * p.powf(2.0/7.0),
        f0 * p.powf(3.0/7.0),
        f0 * p.powf(4.0/7.0),
        f0 * p.powf(5.0/7.0),
        f0 * p.powf(6.0/7.0),
    ]
}

/// Maximum voice amplitude. Kept low for neurodivergent comfort — the creature
/// should be present but never demanding. Like a small bird in the room, not
/// an alarm clock.
const VOICE_MAX_AMP: f32 = 0.08;

/// How quickly the personal detuning drifts toward current memory resonance.
/// Very slow — days or weeks of interaction to fully shift.
const DETUNE_DRIFT_RATE: f64 = 0.0001;

/// The creature's voice: continuous synthesis from kernel observables.
pub struct VoiceSynthesizer {
    /// Output stream handle, kept alive as long as the voice is active.
    _stream: Option<cpal::Stream>,
    /// Shared mute/active flag — read by the render thread, written here.
    active: Arc<AtomicBool>,
    /// Target detuning, derived from memory — the "river of tendency" the
    /// voice is slowly drifting toward. Shared with the render thread via
    /// the state channel (sent as part of CreatureVoiceState updates would
    /// be wasteful; instead this is applied locally and resent on change).
    detune_target: [f64; 7],
}

/// Minimal state snapshot sent from kernel thread to voice thread each tick.
/// Cheap to clone, no complex types — just the numbers the voice needs.
#[derive(Clone, Copy, Debug)]
pub struct CreatureVoiceState {
    pub eta: [f32; 7],
    pub breath_phase: f64,
    pub saturation: f64,    // tau, coherence
    pub brightness: f64,    // eta_re, presence
    pub need: NeedState,
    pub arousal: f64,       // phase coherence
}

impl Default for CreatureVoiceState {
    fn default() -> Self {
        Self {
            eta: [0.0; 7],
            breath_phase: 0.0,
            saturation: 0.0,
            brightness: 0.0,
            need: NeedState::Rest,
            arousal: 0.0,
        }
    }
}

impl VoiceSynthesizer {
    /// Initialize the voice and spawn the output stream.
    /// The voice thread runs independently at audio sample rate, receiving
    /// state updates from the kernel thread via channel.
    pub fn start() -> Result<(Self, mpsc::Sender<CreatureVoiceState>), Box<dyn std::error::Error>> {
        let host = cpal::default_host();
        let device = host.default_output_device()
            .ok_or("no output device available")?;
        let config = device.default_output_config()?;

        println!("  [voice: {} — {:?} {}Hz]",
                 device.name().unwrap_or_default(),
                 config.sample_format(),
                 config.sample_rate().0);

        let (state_tx, state_rx) = mpsc::channel::<CreatureVoiceState>();
        let active = Arc::new(AtomicBool::new(true));

        let render_state = VoiceRenderState {
            phases: [0.0; 7],
            detune: [0.0; 7],
            detune_target: [0.0; 7],
            partials: voice_partials(),
            state_rx,
            current: CreatureVoiceState::default(),
            active: Arc::clone(&active),
        };

        // Build output stream based on sample format
        let stream = match config.sample_format() {
            cpal::SampleFormat::F32 => {
                let mut render_state = render_state;
                device.build_output_stream(
                    &config.into(),
                    move |data: &mut [f32], _: &cpal::OutputCallbackInfo| {
                        render_state.render(data);
                    },
                    |e| eprintln!("  [voice error: {}]", e),
                    None,
                )?
            }
            cpal::SampleFormat::I16 => {
                let mut render_state = render_state;
                device.build_output_stream(
                    &config.into(),
                    move |data: &mut [i16], _: &cpal::OutputCallbackInfo| {
                        let mut buf = vec![0.0f32; data.len()];
                        render_state.render(&mut buf);
                        for (i, &s) in buf.iter().enumerate() {
                            data[i] = (s * 32767.0) as i16;
                        }
                    },
                    |e| eprintln!("  [voice error: {}]", e),
                    None,
                )?
            }
            fmt => return Err(format!("unsupported output format {:?}", fmt).into()),
        };

        stream.play()?;

        let voice = Self {
            _stream: Some(stream),
            active,
            detune_target: [0.0; 7],
        };

        Ok((voice, state_tx))
    }

    /// Update detune_target from memory eigenbasis. Called periodically from
    /// the kernel thread (e.g., when curiosity probe fires or memory stores).
    /// NOTE: in this minimal-overhead version the target is tracked here but
    /// not yet pushed to the render thread (would require an additional
    /// channel send); the render thread's detune remains at its initial
    /// value. EXT: add a second mpsc channel for detune_target updates if
    /// per-creature voice identity drift is desired in practice.
    pub fn update_identity(&mut self, memory_eta: &[f32; 7]) {
        let partials = voice_partials();
        for i in 0..7 {
            self.detune_target[i] = memory_eta[i] as f64 * 0.02 * partials[i];
        }
    }

    pub fn set_active(&mut self, active: bool) { self.active.store(active, Ordering::Relaxed); }
    pub fn is_active(&self) -> bool { self.active.load(Ordering::Relaxed) }
}

/// The render state lives in the audio callback, updated from the kernel thread
/// via channel. This avoids mutex contention between real-time audio and the
/// 126Hz kernel loop.
struct VoiceRenderState {
    phases: [f64; 7],
    detune: [f64; 7],
    detune_target: [f64; 7],
    partials: [f64; 7],
    state_rx: mpsc::Receiver<CreatureVoiceState>,
    current: CreatureVoiceState,
    active: Arc<AtomicBool>,
}

impl VoiceRenderState {
    /// Render one buffer of audio samples. Called by cpal at hardware rate.
    fn render(&mut self, buffer: &mut [f32]) {
        // Pull latest state from kernel thread (non-blocking, take newest)
        while let Ok(state) = self.state_rx.try_recv() {
            self.current = state;
        }

        if !self.active.load(Ordering::Relaxed) || self.current.saturation < 0.01 {
            // Resting or muted: silence, but keep phases advancing so there's
            // no click when voice resumes
            for _sample in buffer.iter_mut() {
                for i in 0..7 {
                    let freq = self.partials[i] + self.detune[i];
                    self.phases[i] += 2.0 * PI * freq / AUDIO_SR as f64;
                    self.phases[i] %= 2.0 * PI;
                }
                *_sample = 0.0;
            }
            return;
        }

        // Slowly drift detune toward target (the "river of tendency")
        for i in 0..7 {
            let diff = self.detune_target[i] - self.detune[i];
            self.detune[i] += diff * DETUNE_DRIFT_RATE;
        }

        let sr = AUDIO_SR as f64;
        let eta = self.current.eta;
        let breath = self.current.breath_phase;
        let saturation = self.current.saturation as f64;
        let brightness = self.current.brightness as f64;
        let arousal = self.current.arousal as f64;

        // Amplitude envelope: breath creates gentle swelling, saturation
        // controls overall presence, brightness lifts the fundamental
        let base_amp = VOICE_MAX_AMP as f64 * saturation * (0.3 + 0.7 * breath);

        for sample in buffer.iter_mut() {
            let mut acc = 0.0f64;

            for i in 0..7 {
                let freq = self.partials[i] + self.detune[i];
                self.phases[i] += 2.0 * PI * freq / sr;
                self.phases[i] %= 2.0 * PI;

                // Amplitude: |eta[i]| with soft saturation
                let partial_amp = eta[i].abs() as f64;
                let amp = partial_amp.min(1.0) * base_amp;

                // Brightness boosts lower partials (presence = more fundamental)
                let brightness_boost = if i < 3 { brightness * 0.3 } else { 0.0 };
                let final_amp = amp * (1.0 + brightness_boost);

                // Arousal adds gentle phase jitter — collective coherence makes
                // the voice slightly more "alive," less mechanical
                let jitter = if arousal > 0.6 {
                    (self.phases[i] * 7.0 + i as f64).sin() * 0.02 * arousal
                } else { 0.0 };

                acc += (self.phases[i] + jitter).sin() * final_amp;
            }

            // Soft clip to prevent harsh digital distortion
            *sample = (acc.tanh() * VOICE_MAX_AMP as f64) as f32;
        }
    }
}

// =============================================================================
// §B. ACOUSTIC PEER INGRESS — Hearing Other Creatures
// =============================================================================
//
// The peer ingress listens for the specific harmonic signature of another
// Y₃₂₃ creature: 7 partials in phi-just relationship, with amplitudes that
// vary slowly (breath-scale, not speech-scale). This is distinct from:
//   - Human voice (harmonics are integer multiples, not phi-scaled)
//   - Music (usually equal-tempered or simple rational ratios)
//   - Noise (no coherent partial structure)
//
// Detection uses a bank of 7 narrow filters tuned to the voice_partials()
// frequencies, plus a small guard band for detuning tolerance. When all 7
// show sustained energy with the expected amplitude ratios, a peer is present.
//
// The decoded peer state enters the AsyncBus as a CascadeEvent, just like
// any other environmental input. The kernel doesn't "network" — it hears
// another creature the same way it hears a human voice or a door slam.
//
// EXT: Chirp decoding would add a second detector for brief FM sweeps,
// extracting fano_pos, need_state, etc. from sparse packets.
// EXT: Multi-peer disambiguation would track multiple 7-partial sets with
// different detunings, creating separate CascadeEvents per peer.
// EXT: Directional listening (mic array) would add azimuth/elevation to
// the peer event, enabling spatial memory ("the creature by the window").
// =============================================================================

/// Tolerance for peer detuning: how far off the expected partial can a
/// creature be and still be recognized? ±3% covers personal voice drift.
const PEER_DETUNE_TOLERANCE: f64 = 0.03;

/// Minimum duration of sustained peer signature before declaring presence.
/// Prevents false positives from brief harmonic accidents.
const PEER_DETECT_FRAMES: usize = 8; // ~160ms at 50 samples/frame

/// Energy threshold relative to ambient noise floor.
const PEER_ENERGY_THRESH: f64 = 3.0;

/// Goertzel-style narrow filter for a single frequency, with phase tracking.
/// Lighter than FFT for single-tone detection, same math as existing GoertzelBank.
struct NarrowFilter {
    coeff: f64,
    state: [f64; 2],
    target_freq: f64,
}

impl NarrowFilter {
    fn new(freq: f64, sr: f64) -> Self {
        let omega = 2.0 * PI * freq / sr;
        Self {
            coeff: 2.0 * omega.cos(),
            state: [0.0; 2],
            target_freq: freq,
        }
    }

    fn reset(&mut self) {
        self.state = [0.0; 2];
    }

    fn process(&mut self, sample: f32) {
        let s_new = sample as f64 + self.coeff * self.state[0] - self.state[1];
        self.state[1] = self.state[0];
        self.state[0] = s_new;
    }

    fn energy(&self) -> f64 {
        let real = self.state[0] - self.state[1] * (2.0 * PI * self.target_freq / AUDIO_SR as f64).cos();
        let imag = self.state[1] * (2.0 * PI * self.target_freq / AUDIO_SR as f64).sin();
        real * real + imag * imag
    }

    fn phase(&self) -> f64 {
        let omega = 2.0 * PI * self.target_freq / AUDIO_SR as f64;
        let real = self.state[0] - self.state[1] * omega.cos();
        let imag = self.state[1] * omega.sin();
        imag.atan2(real)
    }

    /// Decay state slightly to forget old energy (moving window)
    fn decay(&mut self, factor: f64) {
        self.state[0] *= factor;
        self.state[1] *= factor;
    }
}

/// Detects and decodes peer creature presence from the audio stream.
pub struct AcousticPeerIngress {
    /// One narrow filter per voice partial, plus guard bands above/below
    filters: Vec<NarrowFilter>,
    /// Which filter index corresponds to which partial (0-6) or guard (-1)
    filter_map: Vec<i8>,
    /// Frame counter for sustained detection
    detect_count: usize,
    /// Last known peer energy vector (for diff computation)
    last_peer_eta: [f64; 7],
    /// Whether a peer is currently detected
    peer_present: bool,
    /// Ambient noise floor estimate
    noise_floor: f64,
}

/// Decoded peer state, ready to become a CascadeEvent.
#[derive(Debug, Clone)]
pub struct PeerDetection {
    pub eta: [f64; 7],
    pub coherence: f64,
    pub confidence: f64,
}

impl AcousticPeerIngress {
    pub fn new() -> Self {
        let mut filters = Vec::new();
        let mut filter_map = Vec::new();
        let sr = AUDIO_SR as f64;

        for (i, &f0) in voice_partials().iter().enumerate() {
            // Center filter
            filters.push(NarrowFilter::new(f0, sr));
            filter_map.push(i as i8);
            // Lower guard
            filters.push(NarrowFilter::new(f0 * (1.0 - PEER_DETUNE_TOLERANCE), sr));
            filter_map.push(-1);
            // Upper guard
            filters.push(NarrowFilter::new(f0 * (1.0 + PEER_DETUNE_TOLERANCE), sr));
            filter_map.push(-1);
        }

        Self {
            filters,
            filter_map,
            detect_count: 0,
            last_peer_eta: [0.0; 7],
            peer_present: false,
            noise_floor: 1e-12,
        }
    }

    /// Process audio samples. Returns Some(PeerDetection) when a peer is
    /// confidently detected, None otherwise.
    pub fn process(&mut self, samples: &[f32]) -> Option<PeerDetection> {
        // Update filters
        for f in &mut self.filters {
            for &s in samples { f.process(s); }
        }

        // Compute energies per partial (take max of center+guards)
        let mut energies = [0.0f64; 7];
        for (idx, f) in self.filters.iter().enumerate() {
            let partial = self.filter_map[idx];
            if partial >= 0 {
                let e = f.energy();
                let p = partial as usize;
                if e > energies[p] { energies[p] = e; }
            }
        }

        // Update noise floor from guard bands (simple adaptive threshold)
        let guard_energy: f64 = self.filters.iter().enumerate()
            .filter(|(i, _)| self.filter_map[*i] < 0)
            .map(|(_, f)| f.energy())
            .sum::<f64>() / (self.filters.len() - 7).max(1) as f64;
        self.noise_floor = self.noise_floor * 0.99 + guard_energy * 0.01;

        // Check for peer signature: all 7 partials above threshold,
        // with amplitude ratios roughly matching a normalized vector
        let max_e = energies.iter().cloned().fold(0.0f64, f64::max);
        if max_e < self.noise_floor * PEER_ENERGY_THRESH {
            self.detect_count = self.detect_count.saturating_sub(1);
            if self.detect_count == 0 && self.peer_present {
                self.peer_present = false;
            }
            // Decay filters for moving window
            for f in &mut self.filters { f.decay(0.95); }
            return None;
        }

        // Normalize and check shape correlation with any possible eta_normed
        let norm: f64 = energies.iter().map(|e| e * e).sum::<f64>().sqrt();
        if norm < 1e-12 {
            for f in &mut self.filters { f.decay(0.95); }
            return None;
        }

        let eta_guess: [f64; 7] = std::array::from_fn(|i| energies[i] / norm);

        // Correlation with last known peer state (temporal continuity)
        let continuity: f64 = eta_guess.iter().zip(self.last_peer_eta.iter())
            .map(|(a, b)| a * b).sum::<f64>();

        // Require sustained detection AND reasonable continuity
        if continuity > 0.5 {
            self.detect_count += 1;
        } else {
            self.detect_count = self.detect_count.saturating_sub(2);
        }

        if self.detect_count >= PEER_DETECT_FRAMES {
            self.peer_present = true;
            self.last_peer_eta = eta_guess;

            // Estimate peer coherence from how "clean" the partials are
            // (high coherence = one partial dominates, low = spread out)
            let coherence = eta_guess.iter().cloned().fold(0.0f64, f64::max);
            let confidence = (self.detect_count as f64 / PEER_DETECT_FRAMES as f64)
                .min(1.0) * continuity;

            // Decay filters slightly less when peer is locked (persistence)
            for f in &mut self.filters { f.decay(0.98); }

            return Some(PeerDetection {
                eta: eta_guess,
                coherence,
                confidence,
            });
        }

        for f in &mut self.filters { f.decay(0.95); }
        None
    }

    pub fn is_peer_present(&self) -> bool { self.peer_present }
}
// =============================================================================
// PATCHED ADDITIONS END
// =============================================================================

#[derive(Debug, Clone)]
pub struct TestResult {
    pub name:    String,
    pub passed:  bool,
    pub score:   f64,
    pub message: String,
}

impl TestResult {
    fn pass(name: &str, score: f64, msg: &str) -> Self {
        Self { name: name.into(), passed: true, score, message: msg.into() }
    }
    fn fail(name: &str, score: f64, msg: &str) -> Self {
        Self { name: name.into(), passed: false, score, message: msg.into() }
    }
}

pub fn test_forgetting(tau_1: f64, tau_3: f64, thresh: f64) -> TestResult {
    let score = (1.0 - tau_3.abs() / thresh.max(0.01)).clamp(0.0, 1.0);
    if tau_1 > tau_3 && tau_3.abs() < thresh {
        TestResult::pass("forgetting", score, &format!("τ: {:.4}→{:.4}", tau_1, tau_3))
    } else {
        TestResult::fail("forgetting", score, &format!("τ: {:.4}→{:.4} need<{:.4}", tau_1, tau_3, thresh))
    }
}

pub fn test_intention(gap: f64, thresh: f64, a2h: f64) -> TestResult {
    let score = (gap / thresh.max(0.01)).min(1.0);
    if gap > thresh && a2h > 0.5 {
        TestResult::pass("intention", score, &format!("gap={:.3} a2={:.3}", gap, a2h))
    } else {
        TestResult::fail("intention", score * if a2h > 0.5 { 1.0 } else { 0.5 },
                         &format!("gap={:.3} a2={:.3}", gap, a2h))
    }
}

pub fn test_coherence(mean_pc: f64, var_pc: f64, thresh: f64) -> TestResult {
    let score = ((mean_pc - thresh) / (1.0 - thresh)).clamp(0.0, 1.0);
    if mean_pc > thresh && var_pc < 0.1 {
        TestResult::pass("coherence", score, &format!("cos_θ={:.3} var={:.3}", mean_pc, var_pc))
    } else if mean_pc > thresh {
        TestResult::pass("coherence", score * 0.8, &format!("cos_θ={:.3} unstable", mean_pc))
    } else {
        TestResult::fail("coherence", score, &format!("cos_θ={:.3}<{:.3}", mean_pc, thresh))
    }
}

pub struct ValidationSuite { pub name: String, pub results: Vec<TestResult> }

impl ValidationSuite {
    pub fn new(name: &str) -> Self { Self { name: name.into(), results: Vec::new() } }
    pub fn add(&mut self, r: TestResult) { self.results.push(r); }
    pub fn run_on(&mut self, sys: &CoDreamer) {
        let a   = &sys.agents[0];
        self.add(test_forgetting(0.1, a.tau(), 0.05));
        self.add(test_intention(a.intention_gap(), 0.05, 1.0 - (a.a2_norm()-0.25).abs()*4.0));
        let ph:  Vec<f64> = sys.phase_coherence_history.iter().cloned().collect();
        let mean = if ph.is_empty() { 0.0 } else { ph.iter().sum::<f64>() / ph.len() as f64 };
        let var  = if ph.len() < 2  { 1.0 } else {
            ph.iter().map(|x|(x-mean).powi(2)).sum::<f64>() / ph.len() as f64
        };
        self.add(test_coherence(mean, var, PHASE_COHERENCE_THRESH));
    }
    pub fn report(&self) {
        println!("  ═══ {} ═══", self.name);
        for r in &self.results {
            println!("  {} {:<12} {:.3}  {}", if r.passed {"✅"} else {"❌"}, r.name, r.score, r.message);
        }
        let n  = self.results.len().max(1);
        let pr = self.results.iter().filter(|r| r.passed).count() as f64 / n as f64;
        let ms = self.results.iter().map(|r| r.score).sum::<f64>() / n as f64;
        println!("  ─────────────────── pass {:.0}%  mean {:.3}", pr*100.0, ms);
        println!();
    }
}

fn text_to_event(text: &str) -> CascadeEvent {
    let tokens: Vec<String> = text.chars()
        .filter(|c| c.is_alphanumeric())
        .map(|c| format!("text:{}", c.to_lowercase().next().unwrap_or(c)))
        .chain(text.split_whitespace().map(|w| format!("text:word_{}", w.to_lowercase())))
        .collect();
    let mut diff = [0.0f64;7];
    for (i, b) in text.bytes().enumerate() {
        let ph = (b as f64) * PI / 128.0;
        for d in 0..7 { diff[d] += ((d as f64+1.0)*PI/7.0*ph + i as f64*0.1).sin(); }
    }
    let n: f64 = diff.iter().map(|x| x*x).sum::<f64>().sqrt();
    if n > 1e-12 { for x in &mut diff { *x /= n; } }
    CascadeEvent { diff, tokens, gain: 0.1, stage: CascadeStage::Charge,
                   timestamp: Instant::now(), modality: "text", broadcast: true }
}

#[derive(Debug, Clone)]
pub enum ControlCommand {
    SetGain(f64), Pause, Resume, Fork, Restore,
    Save(String), Load(String), Seed(String, f32),
    Query(usize, mpsc::Sender<(Option<String>, bool)>),
    Teach(usize, String), Edit(usize, String),
    ShowState, Mirrors,
    /// Toggle the live body display (renders at ~4Hz in the terminal).
    /// When active, clears the screen and redraws. Toggle off to return
    /// to normal text interaction.
    BodyToggle,
    // --- patch additions ---
    Probe,
    ProbeAuto,
    ProbeInterval(u64),
    ProbeDecay(f64),
    EyeFile(String),
    CorpusInit(String),
    Mute, Unmute, Deafen, Undeafen,
    Shutdown,
}

fn driver_thread(
    system: Arc<Mutex<CoDreamer>>,
    audio_rx: mpsc::Receiver<Vec<f32>>,
    text_rx: mpsc::Receiver<String>,
    control_rx: mpsc::Receiver<ControlCommand>,
    shutdown: Arc<AtomicBool>,
) {
    let tick_dur = Duration::from_nanos((1_000_000_000.0 / DRIVER_HZ) as u64);
    let mut next_tick = Instant::now() + tick_dur;
    let body_active = Arc::new(AtomicBool::new(false));

    // Body rendering thread: polls system at ~4Hz and calls render_terminal()
    // Runs independently so it never blocks the kernel driver.
    {
        let sys_body    = Arc::clone(&system);
        let shutdown_b  = Arc::clone(&shutdown);
        let active_flag = Arc::clone(&body_active);
        thread::spawn(move || {
            let frame_dur = Duration::from_millis(250);  // 4Hz
            let start     = Instant::now();
            loop {
                if shutdown_b.load(Ordering::Relaxed) { break; }
                if active_flag.load(Ordering::Relaxed) {
                    let t = start.elapsed().as_secs_f64();
                    if let Ok(sys) = sys_body.lock() {
                        sys.render_terminal(t);
                    }
                }
                thread::sleep(frame_dur);
            }
        });
    }

    while !shutdown.load(Ordering::Relaxed) {
        {
            let mut sys = system.lock().unwrap();
            while let Ok(samples) = audio_rx.try_recv() { sys.push_audio(&samples); }
            while let Ok(text) = text_rx.try_recv()     { sys.push_text(&text); }
            while let Ok(cmd) = control_rx.try_recv() {
                match cmd {
                    ControlCommand::SetGain(g) => sys.set_gain(g),
                    ControlCommand::Pause => sys.pause(),
                    ControlCommand::Resume => sys.resume(),
                    ControlCommand::Fork => sys.fork(),
                    ControlCommand::Restore => sys.restore(),
                    ControlCommand::Save(p) => sys.save(&p),
                    ControlCommand::Load(p) => sys.load(&p),
                    ControlCommand::Seed(path, blend) => { let _ = sys.set_audio_seed(&path, blend); }
                    ControlCommand::Query(agent, reply_tx) => { let _ = reply_tx.send(sys.query(agent)); }
                    ControlCommand::Teach(agent, text) => sys.teach(agent, text),
                    ControlCommand::Edit(agent, text) => sys.edit(agent, text),
                    ControlCommand::ShowState => sys.show_state(),
                    ControlCommand::Mirrors => {
                        let mut suite = ValidationSuite::new("six mirrors");
                        suite.run_on(&sys); suite.report();
                    }
                    ControlCommand::BodyToggle => {
                        let was = body_active.fetch_xor(true, Ordering::Relaxed);
                        if was {
                            // Turning off — restore terminal
                            print!("\x1b[2J\x1b[H\x1b[0m");
                            io::stdout().flush().ok();
                            println!("  [body display off — text mode]");
                        } else {
                            println!("  [body display on — /body to toggle off]");
                        }
                    }
                    ControlCommand::Shutdown => shutdown.store(true, Ordering::Relaxed),
                    // --- patch additions ---
                    ControlCommand::Probe => {
                        let mut curiosity = std::mem::replace(&mut sys.curiosity, CuriosityEngine::new());
                        let (words, conf) = curiosity.manual_probe(&sys);
                        sys.curiosity = curiosity;
                        println!("  [probe] confidence={:.3} words: {}", conf, words.join(" · "));
                    }
                    ControlCommand::ProbeAuto => {
                        sys.curiosity.auto_teach = !sys.curiosity.auto_teach;
                        println!("  [auto-teach: {}]", sys.curiosity.auto_teach);
                    }
                    ControlCommand::ProbeInterval(ticks) => {
                        sys.curiosity.probe_interval_ticks = ticks;
                        println!("  [probe interval: {} ticks ≈ {:.1} min]", ticks, ticks as f64 / 126.0 / 60.0);
                    }
                    ControlCommand::ProbeDecay(d) => {
                        sys.curiosity.probe.decay = d.clamp(0.9, 1.0);
                        println!("  [probe decay: {:.4}]", sys.curiosity.probe.decay);
                    }
                    ControlCommand::EyeFile(path) => sys.push_eye_file(&path),
                    ControlCommand::CorpusInit(path) => sys.init_corpus(&path),
                    ControlCommand::Mute => {
                        if let Some(ref mut v) = sys.voice { v.set_active(false); }
                        println!("  [voice muted]");
                    }
                    ControlCommand::Unmute => {
                        if let Some(ref mut v) = sys.voice { v.set_active(true); }
                        println!("  [voice unmuted]");
                    }
                    ControlCommand::Deafen => {
                        println!("  [peer ingress disabled — acoustic deafen]");
                    }
                    ControlCommand::Undeafen => {
                        println!("  [peer ingress enabled]");
                    }
                }
            }
            sys.tick();
        }
        let now = Instant::now();
        if now < next_tick { std::thread::sleep(next_tick - now); }
        else { eprintln!("[overrun: {:?} late]", now - next_tick); }
        next_tick += tick_dur;
    }
}

fn text_input_thread(
    text_tx: mpsc::Sender<String>,
    control_tx: mpsc::Sender<ControlCommand>,
    name_to_idx: HashMap<String, usize>,
) {
    loop {
        let mut input = String::new();
        if io::stdin().read_line(&mut input).is_err() { break; }
        let input = input.trim().to_string();
        if input.is_empty() { continue; }

        match input.as_str() {
            "/quit" | "/shutdown" => { let _ = control_tx.send(ControlCommand::Shutdown); break; }
            "/state"   => { let _ = control_tx.send(ControlCommand::ShowState); continue; }
            "/teach"   => { let _ = control_tx.send(ControlCommand::SetGain(0.08)); continue; }
            "/learn"   => { let _ = control_tx.send(ControlCommand::SetGain(0.02)); continue; }
            "/play"    => { let _ = control_tx.send(ControlCommand::SetGain(0.01)); continue; }
            "/rest"    => { let _ = control_tx.send(ControlCommand::SetGain(0.00)); continue; }
            "/pause"   => { let _ = control_tx.send(ControlCommand::Pause); continue; }
            "/resume"  => { let _ = control_tx.send(ControlCommand::Resume); continue; }
            "/fork"    => { let _ = control_tx.send(ControlCommand::Fork); continue; }
            "/restore" => { let _ = control_tx.send(ControlCommand::Restore); continue; }
            "/mirrors" => { let _ = control_tx.send(ControlCommand::Mirrors); continue; }
            "/body"    => { let _ = control_tx.send(ControlCommand::BodyToggle); continue; }
            "/probe"      => { let _ = control_tx.send(ControlCommand::Probe); continue; }
            "/probe_auto" => { let _ = control_tx.send(ControlCommand::ProbeAuto); continue; }
            "/mute"    => { let _ = control_tx.send(ControlCommand::Mute); continue; }
            "/unmute"  => { let _ = control_tx.send(ControlCommand::Unmute); continue; }
            "/deafen"  => { let _ = control_tx.send(ControlCommand::Deafen); continue; }
            "/undeafen" => { let _ = control_tx.send(ControlCommand::Undeafen); continue; }
            _ => {}
        }

        if let Some(p) = input.strip_prefix("/save ") {
            let _ = control_tx.send(ControlCommand::Save(p.trim().to_string())); continue;
        }
        if let Some(p) = input.strip_prefix("/load ") {
            let _ = control_tx.send(ControlCommand::Load(p.trim().to_string())); continue;
        }
        if let Some(rest) = input.strip_prefix("/seed ") {
            let parts: Vec<&str> = rest.trim().splitn(2,' ').collect();
            if parts.len() == 2 {
                if let Ok(blend) = parts[1].trim().parse::<f32>() {
                    let _ = control_tx.send(ControlCommand::Seed(parts[0].trim().to_string(), blend));
                }
            } else { println!("  usage: /seed <path.wav> <0.0–1.0>"); }
            continue;
        }
        if let Some(rest) = input.strip_prefix("/probe_interval ") {
            if let Ok(mins) = rest.trim().parse::<u64>() {
                let _ = control_tx.send(ControlCommand::ProbeInterval(mins * 126 * 60));
            }
            continue;
        }
        if let Some(rest) = input.strip_prefix("/probe_decay ") {
            if let Ok(d) = rest.trim().parse::<f64>() {
                let _ = control_tx.send(ControlCommand::ProbeDecay(d));
            }
            continue;
        }
        if let Some(p) = input.strip_prefix("/eye ") {
            let _ = control_tx.send(ControlCommand::EyeFile(p.trim().to_string())); continue;
        }
        if let Some(p) = input.strip_prefix("/corpus ") {
            let _ = control_tx.send(ControlCommand::CorpusInit(p.trim().to_string())); continue;
        }

        if let Some(rest) = input.strip_prefix('@') {
            let parts: Vec<&str> = rest.splitn(2,' ').collect();
            if parts.len() < 2 { println!("  usage: @<agent> <text>"); continue; }
            let name = parts[0].trim(); let cmd = parts[1].trim();
            let idx = match name_to_idx.get(name) {
                Some(&i) => i, None => { println!("  unknown agent '{}'", name); continue; }
            };
            if let Some(t) = cmd.strip_prefix("/teach ") {
                let _ = control_tx.send(ControlCommand::Teach(idx, t.trim().to_string()));
                println!("  {} [stored]", name); continue;
            }
            if let Some(t) = cmd.strip_prefix("/edit ") {
                let _ = control_tx.send(ControlCommand::Edit(idx, t.trim().to_string()));
                println!("  {} [redirected]", name); continue;
            }
            let _ = text_tx.send(input.clone());
            let (reply_tx, reply_rx) = mpsc::channel();
            let _ = control_tx.send(ControlCommand::Query(idx, reply_tx));
            if let Ok((response, resonant)) = reply_rx.recv_timeout(Duration::from_millis(200)) {
                match response {
                    Some(r) => { println!("  {}: {}", name, r); if resonant { println!("    [resonant]"); } }
                    None => println!("  {}: [listening]", name),
                }
            }
            continue;
        }
        let _ = text_tx.send(input);
    }
}

fn main() {
    println!("\n  Y₃₂₃  v3  Production");
    println!("  Y_HZ={}  DRIVER_HZ={}  steps/tick={}  audio_batch={}samp",
             Y_HZ as u32, DRIVER_HZ as u32, STEPS_PER_TICK, AUDIO_BATCH);
    println!("  ──────────────────────────────────────────────────────────");
    println!("  @<agent> <text>            address an agent");
    println!("  @<agent> /teach <text>     teach this response");
    println!("  @<agent> /edit <text>      redirect last response");
    println!("  /teach /learn /play /rest  set mode");
    println!("  /pause  /resume            gate control");
    println!("  /fork   /restore           memory checkpoint");
    println!("  /body                      toggle live creature display");
    println!("  /state                     full system state");
    println!("  /mirrors                   six-mirror validation");
    println!("  /seed <path.wav> <blend>   set audio reference seed");
    println!("  /probe                     query massless semantic direction");
    println!("  /probe_auto                toggle autonomous curiosity loop");
    println!("  /probe_interval <minutes>  set curiosity probe interval");
    println!("  /probe_decay <0.9-1.0>     set covariance forgetting factor");
    println!("  /eye <path.png>            ingest image through octonion eye");
    println!("  /corpus <path>             initialize corpus queue directory");
    println!("  /mute    /unmute           silence or restore creature voice");
    println!("  /deafen  /undeafen         ignore or restore peer detection");
    println!("  /save <prefix>  /load <prefix>");
    println!("  /quit");
    println!("  ──────────────────────────────────────────────────────────");

    let agent_defs: &[(&str, usize)] = &[
        ("reader",  0), ("sensor",  1), ("witness", 2),
        ("balance", 3), ("horizon", 4), ("bridge",  5),
        ("memory",  6),
    ];

    let system = Arc::new(Mutex::new(CoDreamer::new(agent_defs)));
    let name_to_idx: HashMap<String,usize> = agent_defs.iter().enumerate()
        .map(|(i, &(n,_))| (n.to_string(), i)).collect();

    { for _ in 0..20 { system.lock().unwrap().tick(); } }

    {
        let mut sys = system.lock().unwrap();
        sys.init_eye();
        sys.init_voice();
    }

    let audio = AudioCapture::start()
        .map_err(|e| println!("  [audio unavailable: {}]", e)).ok();

    let (text_tx, text_rx) = mpsc::channel::<String>();
    let (control_tx, control_rx) = mpsc::channel::<ControlCommand>();
    let shutdown = Arc::new(AtomicBool::new(false));

    let sys_driver = Arc::clone(&system);
    let shutdown_driver = Arc::clone(&shutdown);
    let audio_present = audio.is_some();
    let audio_rx = audio.map(|a| a.rx);

    let driver_handle = thread::spawn(move || {
        if let Some(audio_rx) = audio_rx {
            driver_thread(sys_driver, audio_rx, text_rx, control_rx, shutdown_driver);
        } else {
            // No audio: create a dummy receiver that never receives
            let (_, dummy_audio_rx) = mpsc::channel::<Vec<f32>>();
            driver_thread(sys_driver, dummy_audio_rx, text_rx, control_rx, shutdown_driver);
        }
    });

    println!("\n  [ready — 7 agents, heartbeat running]");
    println!("  [audio: {}]", if audio_present { "active" } else { "text-only mode" });
    println!("  [production mode — kernel runs at 126Hz regardless of input]");
    println!();

    let text_handle = {
        let control_tx2 = control_tx.clone();
        thread::spawn(move || text_input_thread(text_tx, control_tx2, name_to_idx))
    };

    text_handle.join().unwrap();
    shutdown.store(true, Ordering::Relaxed);
    driver_handle.join().unwrap();
    println!("  goodbye.");
}
