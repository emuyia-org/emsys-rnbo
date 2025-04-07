import pygame
from .base_screen import BaseScreen

class MainMenuScreen(BaseScreen):
    """Main menu screen for the Emsys application."""
    
    def __init__(self, app_ref):
        super().__init__(app_ref)
        # Create a text surface for the title
        self.title_text = self.font.render("Emsys Main Menu", True, (255, 255, 255))
        # Position the title in the center top of the screen
        self.title_rect = self.title_text.get_rect(center=(app_ref.screen.get_width() // 2, 50))

    def handle_event(self, event):
        """Handles events passed to this screen."""
        # Basic event handling - can be expanded later
        pass

    def update(self):
        """Updates the screen state."""
        # No dynamic content yet, so nothing to update
        pass

    def draw(self, screen_surface):
        """Draws the screen content."""
        # Draw the title
        screen_surface.blit(self.title_text, self.title_rect)