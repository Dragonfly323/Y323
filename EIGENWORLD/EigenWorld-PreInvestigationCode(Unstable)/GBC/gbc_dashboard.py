"""
gbc_dashboard.py
Eigenspectral Training Dashboard with frame capture.
Watch agents evolve on the manifold in real-time.
"""

import curses
import time
import pickle
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import argparse
import sys

# Import our modules
try:
    from gbc_i_ching import IChingBasis
    from atlas import AtlasVector
except ImportError:
    print("⚠️  Warning: Could not import IChing modules. Hexagram display disabled.")
    IChingBasis = None
    AtlasVector = None


class EigenspectralDashboard:
    """
    Terminal-based dashboard for monitoring training progress.
    Minimal overhead — just reads checkpoint files.
    """
    
    def __init__(self, checkpoint_dir: str = "pokemon_checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.basis = IChingBasis() if IChingBasis else None
        self.latest_checkpoint = None
        self.history: List[Tuple[int, float]] = []  # (generation, fitness)
        
        # Verify checkpoint directory exists
        if not self.checkpoint_dir.exists():
            print(f"⚠️  Checkpoint directory not found: {checkpoint_dir}")
            print(f"   Creating: {checkpoint_dir}")
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def get_latest_checkpoint(self) -> Optional[Dict]:
        """Load the most recent checkpoint."""
        checkpoints = sorted(self.checkpoint_dir.glob("*.pkl"))
        if not checkpoints:
            return None
        
        latest = checkpoints[-1]
        if latest == self.latest_checkpoint:
            return None  # No update
        
        self.latest_checkpoint = latest
        try:
            with open(latest, 'rb') as f:
                data = pickle.load(f)
            
            # Extract generation number from filename
            gen_str = latest.stem.split('_')[1]
            data['generation'] = int(gen_str)
            data['filename'] = str(latest)
            
            return data
        except Exception as e:
            print(f"Error loading checkpoint: {e}")
            return None
    
    def draw_manifold_heatmap(self, win, population_data):
        """Draw a heatmap of agent positions on the manifold."""
        try:
            height, width = win.getmaxyx()
            if height < 3 or width < 10:
                return
            
            win.clear()
            win.box()
            win.addstr(0, 2, " Manifold Heatmap ")
            
            if not population_data:
                win.addstr(2, 2, "No data")
                win.refresh()
                return
            
            # Create heatmap of agent fitness by channel
            channels = np.zeros(64)
            counts = np.zeros(64)
            
            for policy, timing, fitness in population_data[:50]:  # Limit for speed
                for i in range(64):
                    channels[i] += abs(policy[i]) * (fitness / 100.0)
                    counts[i] += 1
            
            avg_channels = channels / (counts + 1e-8)
            
            # Normalize for display
            max_val = np.max(avg_channels) + 1e-8
            norm = avg_channels / max_val
            
            # Draw as ASCII bars
            plot_height = height - 4
            plot_width = min(width - 4, 64)
            
            for i in range(plot_width):
                bar_height = int(norm[i] * plot_height)
                for y in range(bar_height):
                    try:
                        win.addch(height - 3 - y, i + 2, '█')
                    except:
                        pass
            
            win.refresh()
        except:
            pass  # Silently ignore drawing errors
    
    def draw_hexagram_display(self, win, best_agent_data):
        """Show the dominant hexagram of the best agent."""
        try:
            height, width = win.getmaxyx()
            if height < 10 or width < 25:
                return
            
            win.clear()
            win.box()
            win.addstr(0, 2, " Best Agent ")
            
            if not best_agent_data or not self.basis:
                win.addstr(2, 2, "No data")
                win.refresh()
                return
            
            policy, timing, fitness = best_agent_data
            
            # Convert to Atlas vector
            atlas_vec = AtlasVector(policy)
            
            # Get dominant hexagram
            dominant, weight = self.basis.dominant_hexagram(atlas_vec.to_array())
            
            # Display info
            win.addstr(2, 2, f"Fitness: {fitness:.1f}")
            win.addstr(3, 2, f"Hex: {dominant.number}. {dominant.name[:15]}")
            win.addstr(4, 2, f"Binary: {dominant.binary_string}")
            win.addstr(5, 2, f"Weight: {weight:.3f}")
            
            # Draw hexagram as lines
            for i, line in enumerate(dominant.binary[:6]):
                y = 7 + i
                if line == 1:  # Yang
                    win.addstr(y, 4, "———   ———")
                else:  # Yin
                    win.addstr(y, 4, "—  —  —  —")
            
            win.refresh()
        except:
            pass
    
    def draw_fitness_graph(self, win):
        """Plot fitness over generations."""
        try:
            height, width = win.getmaxyx()
            if height < 10 or width < 20 or len(self.history) < 2:
                return
            
            win.clear()
            win.box()
            win.addstr(0, 2, " Fitness Progress ")
            
            plot_height = height - 4
            plot_width = width - 4
            
            # Get recent history
            recent = self.history[-plot_width:]
            gens = [g for g, _ in recent]
            fits = [f for _, f in recent]
            
            if not fits:
                return
            
            # Normalize
            min_f = min(fits)
            max_f = max(fits) + 1.0
            
            # Draw axes
            for x in range(plot_width):
                try:
                    win.addch(height - 3, x + 2, '─')
                except:
                    pass
            
            # Plot points
            for i, (gen, fit) in enumerate(recent):
                x = i + 2
                y_norm = (fit - min_f) / (max_f - min_f + 1e-8)
                y = height - 4 - int(y_norm * (plot_height - 1))
                try:
                    win.addch(y, x, '●')
                except:
                    pass
            
            # Labels
            try:
                win.addstr(2, width - 10, f"max:{max_f:.0f}")
                win.addstr(height - 4, 2, f"min:{min_f:.0f}")
            except:
                pass
            
            win.refresh()
        except:
            pass
    
    def draw_stats(self, win, data):
        """Draw basic statistics."""
        try:
            height, width = win.getmaxyx()
            if height < 8 or width < 20:
                return
            
            win.clear()
            win.box()
            win.addstr(0, 2, " Statistics ")
            
            if not data:
                win.addstr(2, 2, "No data")
                win.refresh()
                return
            
            gen = data['generation']
            pop_size = len(data['population'])
            best_fit = data['best_fitness']
            
            win.addstr(2, 2, f"Generation: {gen}")
            win.addstr(3, 2, f"Population: {pop_size}")
            win.addstr(4, 2, f"Best fitness: {best_fit:.2f}")
            
            # Calculate diversity
            policies = [p for p, _, _ in data['population']]
            if len(policies) > 1:
                # Sample pairwise distances
                diversity = 0
                samples = min(10, len(policies))
                for i in range(samples):
                    for j in range(i+1, samples):
                        dist = np.linalg.norm(policies[i] - policies[j])
                        diversity += dist
                diversity /= (samples * (samples-1) / 2)
                win.addstr(5, 2, f"Diversity: {diversity:.3f}")
            
            win.addstr(6, 2, f"Checkpoint: {Path(data['filename']).name[:15]}")
            win.refresh()
        except:
            pass
    
    def capture_frame(self, data, filename: str = None):
        """Capture current manifold state as an image."""
        if not filename:
            filename = f"frame_gen{data['generation']}_{time.strftime('%Y%m%d_%H%M%S')}.png"
        
        try:
            import matplotlib.pyplot as plt
            from sklearn.decomposition import PCA
            
            # Create visualization
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            fig.suptitle(f'Eigenspectral Training - Generation {data["generation"]}', fontsize=16)
            
            # 1. Fitness history
            if self.history:
                gens, fits = zip(*self.history)
                axes[0, 0].plot(gens, fits, 'b-', linewidth=2)
                axes[0, 0].set_title('Fitness over Generations')
                axes[0, 0].set_xlabel('Generation')
                axes[0, 0].set_ylabel('Fitness')
                axes[0, 0].grid(True, alpha=0.3)
            
            # 2. Population distribution (PCA)
            if 'population' in data:
                policies = np.array([p for p, _, _ in data['population']])
                if len(policies) > 1:
                    pca = PCA(n_components=2)
                    reduced = pca.fit_transform(policies)
                    
                    # Color by fitness
                    fitnesses = [f for _, _, f in data['population']]
                    scatter = axes[0, 1].scatter(reduced[:, 0], reduced[:, 1], 
                                                c=fitnesses, cmap='viridis', 
                                                alpha=0.6, s=50)
                    axes[0, 1].set_title('Population on Manifold (PCA)')
                    axes[0, 1].set_xlabel('PC1')
                    axes[0, 1].set_ylabel('PC2')
                    plt.colorbar(scatter, ax=axes[0, 1], label='Fitness')
            
            # 3. Best agent info
            if data['best_agent'] and self.basis:
                policy, timing = data['best_agent']
                atlas_vec = AtlasVector(policy)
                dominant, weight = self.basis.dominant_hexagram(atlas_vec.to_array())
                
                axes[1, 0].axis('off')
                info_text = f"""Best Agent (Fitness: {data['best_fitness']:.1f})
                
Hexagram: {dominant.number}. {dominant.name}
Chinese: {dominant.chinese}
Binary: {dominant.binary_string}
Upper: {dominant.upper_trigram.name}
Lower: {dominant.lower_trigram.name}
Weight: {weight:.3f}

Policy Array Stats:
Mean: {np.mean(policy):.3f}
Std:  {np.std(policy):.3f}
Max:  {np.max(policy):.3f}
Min:  {np.min(policy):.3f}"""
                
                axes[1, 0].text(0.1, 0.5, info_text, fontsize=10,
                               verticalalignment='center',
                               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            
            # 4. Correlation heatmap
            if 'population' in data:
                policies = np.array([p for p, _, _ in data['population'][:20]])
                if len(policies) > 1:
                    corr = np.corrcoef(policies)
                    im = axes[1, 1].imshow(corr, cmap='coolwarm', aspect='auto', vmin=-1, vmax=1)
                    axes[1, 1].set_title('Agent Correlation (top 20)')
                    plt.colorbar(im, ax=axes[1, 1])
            
            plt.tight_layout()
            plt.savefig(filename, dpi=120, bbox_inches='tight')
            plt.close()
            
            return filename
        except ImportError as e:
            print(f"📸  Frame capture requires matplotlib: pip install matplotlib")
            return None
        except Exception as e:
            print(f"📸  Frame capture failed: {e}")
            return None
    
    def run(self, stdscr):
        """Main dashboard loop."""
        # Setup
        curses.curs_set(0)
        stdscr.nodelay(1)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
        
        # Get terminal size
        height, width = stdscr.getmaxyx()
        
        # Minimum size check
        if height < 24 or width < 80:
            stdscr.clear()
            stdscr.addstr(0, 0, "⚠️  Terminal too small! Please resize to at least 80x24")
            stdscr.addstr(2, 0, f"Current size: {width}x{height}")
            stdscr.addstr(4, 0, "Press any key to exit...")
            stdscr.refresh()
            stdscr.getch()
            return
        
        # Calculate window sizes
        stats_height = 8
        stats_width = 30
        fitness_width = 45
        hexagram_width = 35
        manifold_height = max(3, height - stats_height - 2)
        
        # Create windows
        try:
            stats_win = curses.newwin(stats_height, stats_width, 0, 0)
            fitness_win = curses.newwin(stats_height, fitness_width, 0, stats_width)
            hexagram_win = curses.newwin(stats_height, hexagram_width, 0, stats_width + fitness_width)
            manifold_win = curses.newwin(manifold_height, width, stats_height + 1, 0)
            status_win = curses.newwin(1, width, height - 1, 0)
        except:
            stdscr.clear()
            stdscr.addstr(0, 0, "Failed to create windows. Try a larger terminal.")
            stdscr.refresh()
            stdscr.getch()
            return
        
        last_update = time.time()
        status_message = " Dashboard running. Press 'q' to quit, 'c' to capture frame "
        
        while True:
            # Check for input
            key = stdscr.getch()
            if key == ord('q') or key == ord('Q'):
                break
            elif key == ord('c') or key == ord('C'):
                # Capture frame
                data = self.get_latest_checkpoint()
                if data:
                    filename = self.capture_frame(data)
                    if filename:
                        status_message = f"📸  Frame captured: {filename} "
                    else:
                        status_message = "❌  Frame capture failed "
                else:
                    status_message = "⚠️  No checkpoint data available "
            
            # Update display every 0.5 seconds
            if time.time() - last_update < 0.5:
                continue
            
            last_update = time.time()
            
            # Get latest data
            data = self.get_latest_checkpoint()
            if data:
                self.history.append((data['generation'], data['best_fitness']))
                
                # Update windows
                self.draw_stats(stats_win, data)
                self.draw_fitness_graph(fitness_win)
                
                if data['best_agent']:
                    policy, timing = data['best_agent']
                    best_data = (policy, timing, data['best_fitness'])
                    self.draw_hexagram_display(hexagram_win, best_data)
                
                self.draw_manifold_heatmap(manifold_win, data['population'])
            
            # Update title and status
            try:
                stdscr.addstr(0, 0, "━" * width, curses.A_REVERSE)
                stdscr.addstr(0, 2, " EIGENSPECTRAL TRAINING DASHBOARD ", curses.A_REVERSE)
                
                status_win.clear()
                status_win.addstr(0, 0, status_message[:width-1])
                status_win.refresh()
            except:
                pass
            
            stdscr.refresh()


def main():
    parser = argparse.ArgumentParser(description='Eigenspectral Training Dashboard')
    parser.add_argument('--checkpoint-dir', type=str, default='pokemon_checkpoints',
                       help='Directory containing checkpoints')
    parser.add_argument('--check-frequency', type=float, default=0.5,
                       help='How often to check for updates (seconds)')
    args = parser.parse_args()
    
    dashboard = EigenspectralDashboard(args.checkpoint_dir)
    
    try:
        curses.wrapper(dashboard.run)
    except KeyboardInterrupt:
        print("\n👋  Dashboard closed")
    except Exception as e:
        print(f"\n❌  Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()