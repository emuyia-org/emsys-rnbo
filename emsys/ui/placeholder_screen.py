# emsys/ui/placeholder_screen.py

import pygame
from emsys.ui.base_screen import BaseScreen
# Import necessary colors
from emsys.config.settings import WHITE, GREEN, YELLOW, RED, GREY #, SCREEN_WIDTH, SCREEN_HEIGHT

class PlaceholderScreen(BaseScreen):
    """
    A simple placeholder screen displaying basic info and a MIDI status indicator.
    """
    def __init__(self, app):
        # Initialize the BaseScreen (sets self.app and self.font)
        super().__init__(app)

        self.title_text = "emsys"
        self.title_font = pygame.font.Font(None, 64)
        # Render title surface once
        self.title_surf = self.title_font.render(self.title_text, True, WHITE)

        # Indicator properties
        self.indicator_radius = 8
        self.indicator_padding = 15 # Padding from screen edges

        # Add any other specific initializations for PlaceholderScreen
        print("PlaceholderScreen initialized")


    def draw(self, screen, midi_status=None):
        """Draw the placeholder content with a MIDI status indicator."""
        # Get screen dimensions dynamically
        screen_width = screen.get_width()
        screen_height = screen.get_height() # Not used currently, but good practice

        # --- Draw Title ---
        # Calculate title rect dynamically and draw
        title_rect = self.title_surf.get_rect(center=(screen_width // 2, screen_height // 3))
        screen.blit(self.title_surf, title_rect)

        # --- Draw MIDI Status Indicator ---
        indicator_color = GREY # Default color if no status
        if midi_status:
            # Determine color based on status string content
            status_lower = midi_status.lower()
            if "error" in status_lower or "disconnected" in status_lower:
                indicator_color = RED
            elif "searching" in status_lower:
                indicator_color = YELLOW
            elif "midi in:" in status_lower: # Assume connected if input is mentioned and no error/search
                indicator_color = GREEN
            # Add more specific checks if needed based on main.py's status strings

        # Calculate indicator position (top-right corner)
        indicator_pos = (screen_width - self.indicator_padding - self.indicator_radius,
                         self.indicator_padding + self.indicator_radius)

        # Draw the indicator circle
        pygame.draw.circle(screen, indicator_color, indicator_pos, self.indicator_radius)

        # Draw other elements as needed
        # ...

    # Implement other methods like handle_event, handle_midi, update if needed
    # ...

