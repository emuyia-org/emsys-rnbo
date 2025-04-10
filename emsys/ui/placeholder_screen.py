# emsys/ui/placeholder_screen.py

import pygame
from emsys.ui.base_screen import BaseScreen
from emsys.config.settings import WHITE, SCREEN_WIDTH, SCREEN_HEIGHT # Import necessary constants

class PlaceholderScreen(BaseScreen):
    """
    A simple placeholder screen displaying basic info.
    """
    def __init__(self, app):
        # Initialize the BaseScreen (sets self.app and self.font)
        super().__init__(app)
        
        self.title_text = "Emsys Controller"
        self.title_font = pygame.font.Font(None, 48)  # Define a specific title font
        self.title_surf = self.title_font.render(self.title_text, True, WHITE)
        self.title_rect = self.title_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3))

        self.midi_placeholder_text = "MIDI Status Area"
        # Use the font inherited from BaseScreen
        self.midi_placeholder_surf = self.font.render(self.midi_placeholder_text, True, WHITE)
        self.midi_placeholder_rect = self.midi_placeholder_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))

        # Add any other specific initializations for PlaceholderScreen
        print("PlaceholderScreen initialized")


    def draw(self, screen, midi_status=None):
        """Draw the placeholder content."""
        # Optionally call the base draw method if it does something useful (like drawing status)
        # super().draw(screen, midi_status)

        # Draw screen-specific elements
        screen.blit(self.title_surf, self.title_rect)

        # Update and draw the actual MIDI status if provided
        if midi_status:
            status_surf = self.font.render(midi_status, True, WHITE) # Use self.font
            status_rect = status_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            screen.blit(status_surf, status_rect)
        else:
            # Fallback to placeholder text if no status is given
            screen.blit(self.midi_placeholder_surf, self.midi_placeholder_rect)

        # Draw other elements as needed

    # Implement other methods like handle_event, handle_midi, update if needed
    # ...

