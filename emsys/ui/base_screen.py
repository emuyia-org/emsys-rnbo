# emsys/ui/base_screen.py

import pygame
import os
from emsys.config import settings
from typing import Optional, Any

class BaseScreen:
    """Base class for all application screens."""

    def __init__(self, app):
        self.app = app
        self.font = pygame.font.Font(None, 36) # Example font

    def handle_event(self, event):
        """Handle a single Pygame event."""
        pass # Default implementation does nothing

    def handle_midi(self, msg):
        """Handle an incoming MIDI message."""
        pass # Default implementation does nothing

    def update(self):
        """Update screen state (called once per frame)."""
        pass # Default implementation does nothing

    # --- UPDATED draw signature ---
    def draw(self, screen_surface: pygame.Surface,
             midi_status: Optional[str] = None,
             song_status: Optional[str] = None,
             duration_status: Optional[str] = None,
             osc_status: Optional[str] = None, # Added osc_status
             # Added detailed playback components
             play_symbol: Optional[str] = None,
             seg_text: Optional[str] = None,
             rep_text: Optional[str] = None,
             beat_text: Optional[str] = None,
             tempo_text: Optional[str] = None,
             current_playing_segment_index: Optional[int] = None):
        """
        Base draw method. Subclasses should override this.
        Accepts various status strings and detailed playback components.
        """
        # Default implementation (e.g., fill black) or raise NotImplementedError
        screen_surface.fill((0, 0, 0)) # Example: Fill black
        # Base class doesn't draw status lines by default, subclasses should handle it.

    # --- END UPDATED draw signature ---

    def init(self):
        """Called when the screen becomes active."""
        pass # Default implementation does nothing

    def cleanup(self):
        """Called when the screen becomes inactive."""
        pass # Default implementation does nothing

    # <<< ADDED HELPER METHOD (can be placed here or in utils) >>>
    def get_pixel_font(self, size):
        """Helper to load pixel font."""
        try:
            # Prioritize specific paths if they exist
            font_options = [
                "/usr/share/fonts/truetype/misc/TerminusTTF-4.49.1.ttf", # Example: Terminus
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
                "/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf"
            ]
            for font_path in font_options:
                if os.path.exists(font_path):
                    try: return pygame.font.Font(font_path, size)
                    except Exception: continue # Try next path on error

            # Fallback to system fonts
            pixely_fonts = ["Terminus", "Fixed", "Fixedsys", "Terminal", "Consolas", "Monospace", "Courier New", "Courier"]
            for font_name in pixely_fonts:
                try:
                    # Check if font is available before trying to load
                    if font_name in pygame.font.get_fonts():
                        font = pygame.font.SysFont(font_name, size)
                        # Basic check if the loaded font looks monospaced (crude)
                        if font.size('i')[0] == font.size('m')[0]:
                            return font
                except Exception: continue # Try next font on error

            # Ultimate fallback
            print(f"Warning: Could not find preferred pixel font. Using default Pygame font (size {size}).")
            return pygame.font.Font(None, size)
        except Exception as e:
            print(f"Font loading error: {e}")
            return pygame.font.Font(None, size) # Absolute fallback
    # <<< END ADDED HELPER METHOD >>>

