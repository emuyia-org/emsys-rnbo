# emsys/ui/base_screen.py

import pygame
from emsys.config import settings

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
    def draw(self, screen, midi_status=None):
        """
        Draw the screen content.

        Args:
            screen: The Pygame surface to draw onto.
            midi_status (str, optional): A string describing the current MIDI connection status. Defaults to None.
        """
        # Base implementation could potentially draw the status, or do nothing
        # Example: Draw status at the top
        if midi_status:
            status_surface = self.font.render(midi_status, True, settings.WHITE)
            screen.blit(status_surface, (10, 10))
        # --- END MODIFICATION ---

        # Existing base draw logic (if any) or leave it to subclasses
        pass

    def init(self):
        """Called when the screen becomes active."""
        pass # Default implementation does nothing

    def cleanup(self):
        """Called when the screen becomes inactive."""
        pass # Default implementation does nothing

