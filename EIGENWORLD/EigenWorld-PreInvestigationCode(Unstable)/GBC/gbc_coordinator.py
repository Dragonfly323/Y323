"""
gbc_coordinator.py
Real-time Game Boy Color emulator integration with eigenspectral steering.

This module connects to a GBC emulator (via PyBoy or similar), captures frames,
and applies dual-manifold corrections to button inputs in real-time.

The coordinator runs in its own thread, observes the game state,
and intervenes only when necessary to steer away from death/glitches
and toward winning trajectories.
"""

import jax
import jax.numpy as jnp
import numpy as np
import time
import threading
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Callable
from enum import Enum
import queue

# Try to import PyBoy (emulator interface)
try:
    from pyboy import PyBoy
    from pyboy.utils import WindowEvent
    PYBOY_AVAILABLE = True
except ImportError:
    PYBOY_AVAILABLE = False
    print("Warning: PyBoy not installed. Running in mock mode.")

from gbc_octonion import frame_to_octonion_field, octonion_field_to_T7
from gbc_manifold import GBCDualManifoldCoordinator, GBCOctonionManifold, GameplayFrame


# -----------------------------------------------------------------------
# Button mapping
# -----------------------------------------------------------------------

class GBCButton(Enum):
    """Game Boy Color buttons."""
    A = 0
    B = 1
    START = 2
    SELECT = 3
    UP = 4
    DOWN = 5
    LEFT = 6
    RIGHT = 7
    
    @classmethod
    def to_pyboy_event(cls, button: 'GBCButton', pressed: bool) -> int:
        """Convert to PyBoy WindowEvent."""
        mapping = {
            cls.A: (WindowEvent.PRESS_BUTTON_A, WindowEvent.RELEASE_BUTTON_A),
            cls.B: (WindowEvent.PRESS_BUTTON_B, WindowEvent.RELEASE_BUTTON_B),
            cls.START: (WindowEvent.PRESS_BUTTON_START, WindowEvent.RELEASE_BUTTON_START),
            cls.SELECT: (WindowEvent.PRESS_BUTTON_SELECT, WindowEvent.RELEASE_BUTTON_SELECT),
            cls.UP: (WindowEvent.PRESS_ARROW_UP, WindowEvent.RELEASE_ARROW_UP),
            cls.DOWN: (WindowEvent.PRESS_ARROW_DOWN, WindowEvent.RELEASE_ARROW_DOWN),
            cls.LEFT: (WindowEvent.PRESS_ARROW_LEFT, WindowEvent.RELEASE_ARROW_LEFT),
            cls.RIGHT: (WindowEvent.PRESS_ARROW_RIGHT, WindowEvent.RELEASE_ARROW_RIGHT),
        }
        return mapping[button][0] if pressed else mapping[button][1]


# -----------------------------------------------------------------------
# Emulator interface
# -----------------------------------------------------------------------

class GBCEmulatorInterface:
    """
    Abstract interface to a GBC emulator.
    Supports both real PyBoy and mock mode for testing.
    """
    
    def __init__(self, rom_path: str, headless: bool = False):
        self.rom_path = rom_path
        self.headless = headless
        self.emulator = None
        self.frame_count = 0
        
        if PYBOY_AVAILABLE and not headless:
            self.emulator = PyBoy(rom_path, window="SDL2" if not headless else "null")
            self.emulator.set_emulation_speed(1.0)  # Real-time
    
    def step(self) -> bool:
        """Advance one frame. Returns True if successful."""
        if self.emulator:
            return self.emulator.tick()
        else:
            # Mock mode: just increment counter
            self.frame_count += 1
            time.sleep(1/60)  # Simulate 60 FPS
            return True
    
    def get_frame(self) -> np.ndarray:
        """Get current frame as (160, 144) array of 15-bit colors."""
        if self.emulator:
            # PyBoy returns RGB array — convert to 15-bit GBC palette
            rgb_array = self.emulator.screen.ndarray  # (144, 160, 3)
            # Convert RGB to 15-bit (simplified — just use first 5 bits of each)
            r = (rgb_array[:, :, 0] >> 3) & 0x1F
            g = (rgb_array[:, :, 1] >> 3) & 0x1F
            b = (rgb_array[:, :, 2] >> 3) & 0x1F
            frame_15bit = (r) | (g << 5) | (b << 10)
            return frame_15bit.astype(np.int32)
        else:
            # Mock mode: return blank frame
            return np.zeros((144, 160), dtype=np.int32)
    
    def get_memory(self) -> dict:
        """Get memory state (for savestates)."""
        if self.emulator:
            # This would need PyBoy's memory API
            return {}
        return {}
    
    def press_button(self, button: GBCButton):
        """Press a button."""
        if self.emulator:
            self.emulator.send_input(GBCButton.to_pyboy_event(button, True))
    
    def release_button(self, button: GBCButton):
        """Release a button."""
        if self.emulator:
            self.emulator.send_input(GBCButton.to_pyboy_event(button, False))
    
    def set_buttons(self, button_states: jnp.ndarray):
        """
        Set all button states at once.
        button_states: (8,) array of floats in [-1, 1] where >0 means pressed.
        """
        # Convert to binary press/release
        for i, button in enumerate(GBCButton):
            if button_states[i] > 0:
                self.press_button(button)
            else:
                self.release_button(button)
    
    def save_state(self) -> bytes:
        """Save current emulator state."""
        if self.emulator and hasattr(self.emulator, 'save_state'):
            return self.emulator.save_state()
        return b""
    
    def load_state(self, state: bytes):
        """Load emulator state."""
        if self.emulator and hasattr(self.emulator, 'load_state'):
            self.emulator.load_state(state)


# -----------------------------------------------------------------------
# Input recorder for trajectory collection
# -----------------------------------------------------------------------

class InputRecorder:
    """
    Records player inputs for trajectory collection.
    Used to build training data for manifolds.
    """
    
    def __init__(self):
        self.history = []  # List of (timestamp, button_states)
        self.recording = False
    
    def start(self):
        """Start recording."""
        self.history = []
        self.recording = True
    
    def stop(self) -> List[Tuple[int, jnp.ndarray]]:
        """Stop recording and return history."""
        self.recording = False
        return self.history
    
    def record(self, timestamp: int, button_states: jnp.ndarray):
        """Record a frame's button states."""
        if self.recording:
            self.history.append((timestamp, button_states.copy()))


# -----------------------------------------------------------------------
# Main coordinator
# -----------------------------------------------------------------------

class GBCEigenspectralCoordinator:
    """
    Main coordinator that runs the emulator and applies steering.
    
    Runs in its own thread, capturing frames and correcting inputs
    based on dual-manifold steering.
    """
    
    def __init__(self,
                 rom_path: str,
                 M_target: GBCOctonionManifold,
                 M_anti: GBCOctonionManifold,
                 headless: bool = False,
                 record_inputs: bool = False,
                 intervention_callback: Optional[Callable] = None):
        
        self.rom_path = rom_path
        self.emulator = GBCEmulatorInterface(rom_path, headless)
        self.coordinator = GBCDualManifoldCoordinator(M_target, M_anti)
        self.recorder = InputRecorder() if record_inputs else None
        
        self.intervention_callback = intervention_callback
        self.running = False
        self.thread = None
        self.frame_queue = queue.Queue(maxsize=10)
        self.command_queue = queue.Queue()
        
        # Statistics
        self.frames_processed = 0
        self.interventions = 0
        self.current_psi = None
        self.current_atlas = None
        
    def start(self):
        """Start the coordinator thread."""
        self.running = True
        self.thread = threading.Thread(target=self._run_loop)
        self.thread.daemon = True
        self.thread.start()
        print(f"🎮 Coordinator started for {self.rom_path}")
    
    def stop(self):
        """Stop the coordinator thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        print(f"🎮 Coordinator stopped. Frames: {self.frames_processed}, Interventions: {self.interventions}")
    
    def _run_loop(self):
        """Main emulation loop with steering."""
        
        # Initial button states
        current_buttons = jnp.zeros(8, dtype=jnp.float32)
        
        while self.running and self.emulator.step():
            frame_num = self.frames_processed
            
            # Get current frame
            frame_data = self.emulator.get_frame()
            
            # Convert to GameplayFrame
            gameplay_frame = GameplayFrame(
                frame_data=jnp.array(frame_data),
                inputs=current_buttons,
                timestamp=frame_num
            )
            
            # Store for monitoring
            self.current_psi = gameplay_frame.psi
            self.current_atlas = gameplay_frame.atlas
            
            # Get button logits (could come from external policy)
            # For now, use current buttons as baseline
            action_logits = current_buttons.copy()
            
            # Apply dual-manifold steering
            corrected_buttons = self.coordinator.steer_frame(gameplay_frame, action_logits)
            
            # Check if intervention occurred
            if not jnp.array_equal(corrected_buttons, action_logits):
                self.interventions += 1
                if self.intervention_callback:
                    self.intervention_callback(frame_num, action_logits, corrected_buttons)
            
            # Send to emulator
            self.emulator.set_buttons(corrected_buttons)
            current_buttons = corrected_buttons
            
            # Record if enabled
            if self.recorder:
                self.recorder.record(frame_num, corrected_buttons)
            
            # Put frame in queue for UI
            if not self.frame_queue.full():
                self.frame_queue.put({
                    'frame': frame_data,
                    'psi': self.current_psi,
                    'atlas': self.current_atlas,
                    'buttons': corrected_buttons,
                    'intervened': not jnp.array_equal(corrected_buttons, action_logits)
                })
            
            self.frames_processed += 1
            
            # Check for commands
            self._process_commands()
    
    def _process_commands(self):
        """Process commands from the command queue."""
        try:
            while True:
                cmd = self.command_queue.get_nowait()
                if cmd['type'] == 'save_state':
                    state = self.emulator.save_state()
                    if 'callback' in cmd:
                        cmd['callback'](state)
                elif cmd['type'] == 'load_state':
                    self.emulator.load_state(cmd['state'])
                elif cmd['type'] == 'set_thresholds':
                    self.coordinator.danger_threshold = cmd.get('danger', self.coordinator.danger_threshold)
                    self.coordinator.far_threshold = cmd.get('far', self.coordinator.far_threshold)
        except queue.Empty:
            pass
    
    def get_latest_frame(self) -> Optional[dict]:
        """Get the most recent frame from the queue."""
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None
    
    def save_state_async(self, callback: Callable):
        """Save emulator state asynchronously."""
        self.command_queue.put({'type': 'save_state', 'callback': callback})
    
    def load_state(self, state: bytes):
        """Load emulator state."""
        self.command_queue.put({'type': 'load_state', 'state': state})
    
    def set_thresholds(self, danger: Optional[float] = None, far: Optional[float] = None):
        """Adjust steering thresholds dynamically."""
        self.command_queue.put({'type': 'set_thresholds', 'danger': danger, 'far': far})


# -----------------------------------------------------------------------
# Real-time visualization (optional)
# -----------------------------------------------------------------------

class GBCVisualizer:
    """
    Simple real-time visualizer for the coordinator.
    Displays frame, T' state, and intervention status.
    """
    
    def __init__(self, coordinator: GBCEigenspectralCoordinator):
        self.coordinator = coordinator
        self.running = False
        
    def start(self):
        """Start visualization in its own thread."""
        self.running = True
        self.thread = threading.Thread(target=self._viz_loop)
        self.thread.daemon = True
        self.thread.start()
    
    def _viz_loop(self):
        """Visualization loop."""
        try:
            import matplotlib.pyplot as plt
            import matplotlib.animation as animation
            
            fig, axes = plt.subplots(2, 2, figsize=(12, 8))
            
            def animate(frame):
                # Get latest frame data
                data = self.coordinator.get_latest_frame()
                if data is None:
                    return
                
                # Clear axes
                for ax in axes.flat:
                    ax.clear()
                
                # Show GBC frame
                axes[0, 0].imshow(data['frame'], cmap='gray')
                axes[0, 0].set_title('GBC Frame')
                
                # Show T' state (real parts)
                psi_real = data['psi'].real
                axes[0, 1].bar(range(7), psi_real)
                axes[0, 1].set_title('T\' State (real)')
                axes[0, 1].set_xticks(range(7))
                axes[0, 1].set_xticklabels(['τ', 'φ₁ᵣ', 'φ₁ᵢ', 'φ₂ᵣ', 'φ₂ᵢ', 'ξᵣ', 'ξᵢ'])
                
                # Show button states
                axes[1, 0].bar(range(8), data['buttons'])
                axes[1, 0].set_title('Button States')
                axes[1, 0].set_xticks(range(8))
                axes[1, 0].set_xticklabels(['A','B','Start','Select','Up','Down','Left','Right'])
                
                # Show intervention status
                axes[1, 1].text(0.5, 0.5, 
                               f"Intervened: {data['intervened']}\n"
                               f"Frames: {self.coordinator.frames_processed}\n"
                               f"Interventions: {self.coordinator.interventions}",
                               ha='center', va='center', fontsize=14)
                axes[1, 1].set_title('Status')
                
            ani = animation.FuncAnimation(fig, animate, interval=100)
            plt.tight_layout()
            plt.show()
            
        except ImportError:
            print("Matplotlib not available for visualization")
    
    def stop(self):
        self.running = False


# -----------------------------------------------------------------------
# Main entry point
# -----------------------------------------------------------------------

def main():
    """Run the coordinator with pre-trained manifolds."""
    print("🎮 GBC Eigenspectral Coordinator")
    print("=" * 50)
    
    # Load pre-trained manifolds (from gbc_manifold.py)
    # For now, create dummy manifolds
    from gbc_manifold import GBCOctonionManifold
    
    M_target = GBCOctonionManifold(n_components=5)
    M_target.name = "target"
    
    M_anti = GBCOctonionManifold(n_components=3)
    M_anti.name = "anti"
    
    # Note: In practice, you'd load fitted manifolds:
    # import pickle
    # with open('M_target.pkl', 'rb') as f:
    #     M_target = pickle.load(f)
    
    # ROM path (update this to your ROM)
    rom_path = "roms/pokemon_crystal.gbc"  # Example
    
    # Create coordinator
    coord = GBCEigenspectralCoordinator(
        rom_path=rom_path,
        M_target=M_target,
        M_anti=M_anti,
        headless=False,
        record_inputs=True,
        intervention_callback=lambda frame, before, after: print(f"⚡ Intervention at frame {frame}")
    )
    
    # Start visualization
    viz = GBCVisualizer(coord)
    viz.start()
    
    # Start coordinator
    coord.start()
    
    try:
        # Let it run
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping...")
        coord.stop()
        viz.stop()
    
    print("👋 Goodbye!")


if __name__ == "__main__":
    main()