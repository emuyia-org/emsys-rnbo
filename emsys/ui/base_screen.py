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

    # --- MODIFICATION HERE ---
    def draw(self, screen_surface: pygame.Surface, midi_status: Optional[str] = None, song_status: Optional[str] = None, duration_status: Optional[str] = None):
        """
        Base draw method. Subclasses should override this.
        Added duration_status parameter.
        """
        # Default implementation (e.g., fill black) or raise NotImplementedError
        screen_surface.fill((0, 0, 0)) # Example: Fill black
        # You might want to draw basic status here or leave it to subclasses
        # font = pygame.font.Font(None, 24)
        # if song_status:
        #     text_surf = font.render(song_status, True, (200, 200, 200))
        #     screen_surface.blit(text_surf, (10, 10))
        # if duration_status:
        #     text_surf = font.render(duration_status, True, (200, 200, 200))
        #     screen_surface.blit(text_surf, (10, 30))

    # --- END MODIFICATION ---

    def init(self):
        """Called when the screen becomes active."""
        pass # Default implementation does nothing

    def cleanup(self):
        """Called when the screen becomes inactive."""
        pass # Default implementation does nothing

