# gbc_pokemon_crystal.py (fixed)
"""
Pokémon Crystal specific implementation for eigenspectral training.
Uses real ROM with PyBoy — JAX imports are LAZY (only in main process).
"""

import numpy as np  # NumPy is fine — no CUDA
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import time
import pickle
from pathlib import Path
import io

# NO JAX IMPORTS AT TOP LEVEL!

# Try to import PyBoy
try:
    from pyboy import PyBoy
    from pyboy.utils import WindowEvent
    PYBOY_AVAILABLE = True
except ImportError:
    PYBOY_AVAILABLE = False
    print("⚠️ PyBoy not installed. Run: pip install pyboy")


# =======================================================================
# COMPLETE POKÉMON CRYSTAL MEMORY MAP
# =======================================================================

@dataclass
class PokemonCrystalMemoryMap:
    """Memory map for Pokémon Crystal."""
    
    # Player position
    MAP_GROUP: int = 0xD35E
    MAP_NUMBER: int = 0xD35F
    PLAYER_X: int = 0xD362
    PLAYER_Y: int = 0xD361
    PLAYER_DIR: int = 0xD363
    
    # Player status
    MONEY: int = 0xD347
    COINS: int = 0xD7E0
    PLAYER_ID: int = 0xD355
    
    # Time
    HOURS: int = 0xD34C
    DAYS: int = 0xD34D
    TIME_FRAME: int = 0xD34E
    
    # Badges
    BADGES: int = 0xD35C
    
    # Party Pokémon
    PARTY_COUNT: int = 0xD163
    PARTY_SPECIES: int = 0xD164
    PARTY_HP: int = 0xD16C
    PARTY_MAX_HP: int = 0xD23C
    PARTY_LEVEL: int = 0xD18C
    PARTY_STATUS: int = 0xD180
    
    # Battle
    BATTLE_TYPE: int = 0xD057
    ENEMY_SPECIES: int = 0xCFE5
    ENEMY_HP: int = 0xCFE6
    ENEMY_LEVEL: int = 0xCFE8
    PLAYER_HP: int = 0xCFE7


# =======================================================================
# POKÉMON ENVIRONMENT — NO JAX IN WORKERS!
# =======================================================================

class PokemonEnvironment:
    """
    Pokémon environment with real ROM via PyBoy.
    USES NUMPY, NOT JAX — workers stay on CPU.
    """
    
    def __init__(self, rom_path: str, headless: bool = True):
        self.rom_path = Path(rom_path)
        self.map = PokemonCrystalMemoryMap()
        
        if not self.rom_path.exists():
            raise FileNotFoundError(f"ROM not found: {rom_path}")
        
        # Initialize PyBoy
        self.emulator = PyBoy(
            str(self.rom_path),
            window="null" if headless else "SDL2",
            sound=False
        )
        
        # Save initial state as bytes
        self.initial_state = self._save_state_bytes()
        
        # Button mapping
        self.buttons = [
            WindowEvent.PRESS_BUTTON_A,
            WindowEvent.PRESS_BUTTON_B,
            WindowEvent.PRESS_BUTTON_START,
            WindowEvent.PRESS_BUTTON_SELECT,
            WindowEvent.PRESS_ARROW_UP,
            WindowEvent.PRESS_ARROW_DOWN,
            WindowEvent.PRESS_ARROW_LEFT,
            WindowEvent.PRESS_ARROW_RIGHT,
        ]
        
        self.release_events = [
            WindowEvent.RELEASE_BUTTON_A,
            WindowEvent.RELEASE_BUTTON_B,
            WindowEvent.RELEASE_BUTTON_START,
            WindowEvent.RELEASE_BUTTON_SELECT,
            WindowEvent.RELEASE_ARROW_UP,
            WindowEvent.RELEASE_ARROW_DOWN,
            WindowEvent.RELEASE_ARROW_LEFT,
            WindowEvent.RELEASE_ARROW_RIGHT,
        ]
        
        # State tracking
        self.step_count = 0
        self.total_reward = 0.0
    
    def _save_state_bytes(self) -> bytes:
        """Save emulator state to bytes."""
        state_file = io.BytesIO()
        self.emulator.save_state(state_file)
        state_file.seek(0)
        return state_file.read()
    
    def _load_state_bytes(self, state_bytes: bytes):
        """Load emulator state from bytes."""
        state_file = io.BytesIO(state_bytes)
        state_file.seek(0)
        self.emulator.load_state(state_file)
    
    def reset(self):
        """Reset to initial state — returns frame, not JAX array."""
        self._load_state_bytes(self.initial_state)
        self.step_count = 0
        self.total_reward = 0.0
        return self._get_frame()  # Return raw frame
    
    def step(self, action: int):
        """
        Take an action — returns (frame, reward, done).
        ALL NUMPY, NO JAX.
        """
        # Press button
        if action >= 0:
            self.emulator.send_input(self.buttons[action])
        
        # Run 4 frames (for stability)
        for _ in range(4):
            self.emulator.tick()
        
        # Release button
        if action >= 0:
            self.emulator.send_input(self.release_events[action])
        
        # Get reward (simple for now)
        reward = self._get_reward_numpy()
        self.total_reward += reward
        self.step_count += 1
        
        # Check if done (game over or max steps)
        done = self._check_done_numpy()
        
        return self._get_frame(), reward, done
    
    def _get_frame(self) -> np.ndarray:
        """Get current frame as numpy array — shape (144, 160, 3)."""
        if self.emulator:
            return np.array(self.emulator.screen.ndarray, dtype=np.uint8)
        return np.zeros((144, 160, 3), dtype=np.uint8)
    
    def _get_memory_value(self, address: int) -> int:
        """Safely read memory."""
        try:
            return self.emulator.get_memory_value(address)
        except:
            return 0
    
    def _get_reward_numpy(self) -> float:
        """Reward function using numpy (no JAX)."""
        reward = 0.1  # Small step reward
        
        # Check for battle victory
        enemy_hp_high = self._get_memory_value(self.map.ENEMY_HP)
        enemy_hp_low = self._get_memory_value(self.map.ENEMY_HP + 1)
        enemy_hp = (enemy_hp_high << 8) | enemy_hp_low
        
        if enemy_hp == 0 and self._get_memory_value(self.map.BATTLE_TYPE) > 0:
            reward += 5.0
        
        return reward
    
    def _check_done_numpy(self) -> bool:
        """Check if episode should end."""
        # Max steps
        if self.step_count > 10000:
            return True
        return False
    
    def get_state_summary(self) -> Dict:
        """Get human-readable state."""
        return {
            'position': (
                self._get_memory_value(self.map.MAP_GROUP),
                self._get_memory_value(self.map.MAP_NUMBER),
                self._get_memory_value(self.map.PLAYER_X),
                self._get_memory_value(self.map.PLAYER_Y)
            ),
            'badges': bin(self._get_memory_value(self.map.BADGES)).count('1'),
            'party_count': self._get_memory_value(self.map.PARTY_COUNT),
            'in_battle': self._get_memory_value(self.map.BATTLE_TYPE) > 0,
            'steps': self.step_count,
            'total_reward': self.total_reward
        }
    def _get_frame(self) -> np.ndarray:
        """
        Get current frame as RGB array.
        Returns shape (144, 160, 3) for GBC resolution.
        """
        if self.emulator:
            return self.emulator.screen.ndarray
        return np.zeros((144, 160, 3), dtype=np.uint8)


# =======================================================================
# SIMPLE TEST
# =======================================================================

if __name__ == "__main__":
    print("🎮 Pokémon Crystal Environment Test")
    print("=" * 50)
    
    # Path to your ROM
    rom_path = Path("roms/pokemon_crystal.gbc")
    
    if not rom_path.exists():
        print(f"❌ ROM not found at {rom_path}")
        print("Please place your Pokémon Crystal ROM at:", rom_path.absolute())
        exit(1)
    
    # Create environment
    print(f"\nLoading ROM from: {rom_path.absolute()}")
    env = PokemonEnvironment(str(rom_path), headless=True)
    
    # Test reset
    print("\nResetting...")
    atlas = env.reset()
    print(f"Initial Atlas norm: {jnp.linalg.norm(atlas):.3f}")
    
    # Take some random steps
    print("\nTaking 20 random steps:")
    for i in range(20):
        action = i % 8
        atlas, reward, done = env.step(action)
        print(f"  Step {i:2d}: action={action}, reward={reward:5.2f}, done={done}")
        
        if i % 5 == 0:
            summary = env.get_state_summary()
            print(f"    State: {summary}")
        
        if done:
            break
    
    print(f"\n✅ Test complete. Total reward: {env.total_reward:.2f}")