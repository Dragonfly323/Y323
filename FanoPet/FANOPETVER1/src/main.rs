// Y₃₂₃ — Level 1: S⁶ coherence hyperplane projection
mod kernel;

use kernel::{Kernel, C, Y_HZ, DRIVER_HZ, stone_attractor, check_attractor};
use std::f64::consts::PI;

fn main() {
    println!("Y₃₂₃ — Level 1 Kernel (S⁶ coherence hyperplane)");
    println!("Y_HZ={}  DRIVER_HZ={}  input=a₁ only", Y_HZ, DRIVER_HZ);
    println!();

    // Attractor verification
    let stone = stone_attractor();
    println!("--- Attractor check ---");
    println!("  Stone ‖Y·v - v‖ = {:.2e}", check_attractor(&stone, 1.0));
    println!("  Stone a₂={:.6}  b₂={:.6}  |η|={:.6}",
        stone[2].re, stone[4].re, stone[6].norm());
    println!();

    // Seed: Stone attractor + small phase-spread a₁ perturbation
    let agent_defs: Vec<(&str, C)> = (0..7).map(|n| {
        let names = ["reader","sensor","witness","balance","horizon","bridge","memory"];
        let theta  = 2.0 * PI * n as f64 / 7.0;
        (names[n], C::exp_i(theta).scale(0.05))
    }).collect();

    let mut kernel = Kernel::new(&agent_defs);
    println!();

    // Header: track a₂ real part (invariant=1/4), N-sector imaginary parts
    // (should rotate and die), and M-sector real parts (should be stable)
    println!("=== Dynamics: a₂ invariant + N-sector imaginary rotation ===");
    println!("  {:>6}  {:>8}  {:>8}  {:>8}  {:>8}  {:>8}  {:>8}",
             "tick", "a₂.re", "b₂.re", "|η|",
             "τ.im", "a₁.im", "x.im");

    let print_row = |tick: u64, k: &Kernel| {
        let a = &k.agents[0];
        println!("  {:>6}  {:>8.5}  {:>8.5}  {:>8.5}  {:>8.5}  {:>8.5}  {:>8.5}",
                 tick,
                 a.a2().re,      // a₂ real — should stay ~0.25
                 a.b2().re,      // b₂ real — should stay ~0.707
                 a.eta().norm(), // |η| — output magnitude
                 a.tau().im,     // τ imaginary — N-sector rotation
                 a.a1().im,      // a₁ imaginary — N-sector rotation
                 a.x().im,       // x imaginary — N-sector rotation
        );
    };

    print_row(0, &kernel);

    for s in 1..=10 {
        for _ in 0..126 { kernel.tick(); }
        print_row(kernel.tick_count, &kernel);
    }
    println!();

    // Pulse and observe
    println!("=== Pulse at a₁ (z=0.1·e^(iπ/4)) ===");
    kernel.inject_a1_all(C::exp_i(PI / 4.0).scale(0.1));
    for s in 1..=5 {
        for _ in 0..126 { kernel.tick(); }
        print_row(kernel.tick_count, &kernel);
    }
    println!();

    // Final state — all agents
    println!("--- Final state (all agents) ---");
    kernel.print_state();
    println!();

    // a₂ across all agents
    println!("--- a₂ invariant across all agents ---");
    for a in &kernel.agents {
        println!("  {:>8}  a₂.re={:.6}  (target: 0.250000)  drift={:+.2e}",
                 a.name, a.a2().re, a.a2().re - 0.25);
    }
    println!();

    // Fano residuals
    println!("--- Fano triple residuals (reader) ---");
    let res   = kernel.agents[0].fano_residuals();
    let names = ["τ·a₁=b₁","a₁·a₂=b₁","a₂·b₁=x","b₁·b₂=η","b₂·x=τ","x·η=a₁","η·τ=a₂"];
    for (name, r) in names.iter().zip(res.iter()) {
        println!("  {}  {:.4}", name, r);
    }

    println!();
    println!("Level 1 verification complete.");
}
