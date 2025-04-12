# emsys/ui/placeholder_screen.py

import pygame
from emsys.ui.base_screen import BaseScreen
# Keep settings import for colors, but avoid using SCREEN_WIDTH/HEIGHT for positioning here
from emsys.config.settings import WHITE #, SCREEN_WIDTH, SCREEN_HEIGHT

class PlaceholderScreen(BaseScreen):
    """
    A simple placeholder screen displaying basic info.
    """
    def __init__(self, app):
        # Initialize the BaseScreen (sets self.app and self.font)
        super().__init__(app)

        self.title_text = "emsys"
        self.title_font = pygame.font.Font(None, 64)
        self.small_font = pygame.font.Font(None, 24)
        # Render surfaces once, but don't calculate final rects yet
        self.title_surf = self.title_font.render(self.title_text, True, WHITE)

        self.midi_placeholder_text = "MIDI Status Area"
        # Use the font inherited from BaseScreen for placeholder text
        self.midi_placeholder_surf = self.font.render(self.midi_placeholder_text, True, WHITE)

        # Add any other specific initializations for PlaceholderScreen
        print("PlaceholderScreen initialized")


    def draw(self, screen, midi_status=None):
        """Draw the placeholder content, centering dynamically."""
        # Optionally call the base draw method if it does something useful (like drawing status)
        # super().draw(screen, midi_status)

        # Get screen dimensions dynamically
        screen_width = screen.get_width()
        screen_height = screen.get_height()

        # Calculate title rect dynamically and draw
        title_rect = self.title_surf.get_rect(center=(screen_width // 2, screen_height // 3))
        screen.blit(self.title_surf, title_rect)

        # Update and draw the actual MIDI status if provided
        if midi_status:
            # Render status text using the small font
            status_surf = self.small_font.render(midi_status, True, WHITE)
            # Calculate status rect dynamically and draw
            status_rect = status_surf.get_rect(center=(screen_width // 2, screen_height // 2))
            screen.blit(status_surf, status_rect)
        else:
            # Fallback to placeholder text if no status is given
            # Calculate placeholder rect dynamically and draw
            midi_placeholder_rect = self.midi_placeholder_surf.get_rect(center=(screen_width // 2, screen_height // 2))
            screen.blit(self.midi_placeholder_surf, midi_placeholder_rect)

        # Draw other elements as needed

    # Implement other methods like handle_event, handle_midi, update if needed
    # ...

