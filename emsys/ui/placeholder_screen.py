# Corrected imports
from emsys.ui.base_screen import BaseScreen  # Use absolute import
from emsys.config.settings import SCREEN_WIDTH, SCREEN_HEIGHT, WHITE  # Import WHITE color

# --- Minimal Placeholder Screen ---
class PlaceholderScreen(BaseScreen):
    # ... rest of the class remains the same ...
    def __init__(self, app_ref):
        super().__init__(app_ref)
        self.title_text = "emsys Running!"
        self.title_surf = self.font.render(self.title_text, True, WHITE)
        self.title_rect = self.title_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20)) # Move title up slightly

        # Pre-render placeholder for MIDI message area
        self.midi_placeholder_text = "Waiting for MIDI..."
        self.midi_placeholder_surf = self.font_small.render(self.midi_placeholder_text, True, WHITE)
        self.midi_placeholder_rect = self.midi_placeholder_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20)) # Position below title

    def draw(self, screen_surface):
        """Draws the screen content."""
        # Draw main title
        screen_surface.blit(self.title_surf, self.title_rect)

        # Get the last MIDI message string from the App instance
        last_midi_msg = self.app.last_midi_message_str # Read from App

        # Render and draw the last MIDI message or placeholder
        if last_midi_msg:
            # Render the actual last message
            midi_surf = self.font_small.render(last_midi_msg, True, WHITE)
            midi_rect = midi_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20)) # Same position as placeholder
            screen_surface.blit(midi_surf, midi_rect)
        else:
            # Draw the "Waiting for MIDI..." placeholder
            screen_surface.blit(self.midi_placeholder_surf, self.midi_placeholder_rect)

