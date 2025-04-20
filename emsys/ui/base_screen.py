# emsys/ui/base_screen.py

import pygame
from emsys.config import settings
from typing import Optional

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

    # --- REVERTED MODIFICATION ---
    def draw(self, screen_surface: pygame.Surface,
             midi_status: Optional[str] = None,
             song_status: Optional[str] = None,
             duration_status: Optional[str] = None):
        """
        Base draw method. Subclasses should override this.
        Accepts midi_status, song_status, duration_status.
        """
        # Default implementation (e.g., fill black) or raise NotImplementedError
        screen_surface.fill((0, 0, 0)) # Example: Fill black
        # Base class doesn't draw status lines by default, subclasses should handle it.

    # --- END REVERTED MODIFICATION ---

    def init(self):
        """Called when the screen becomes active."""
        pass # Default implementation does nothing

    def cleanup(self):
        """Called when the screen becomes inactive."""
        pass # Default implementation does nothing

