import pygame

class BaseScreen:
    """Base class for all screens in the application."""
    def __init__(self, app_ref):
        self.app = app_ref  # Reference to the main App instance
        self.font = pygame.font.SysFont(None, 50)

    def handle_event(self, event):
        """Handles events passed to this screen."""
        pass

    def update(self):
        """Updates the screen state."""
        pass

    def draw(self, screen_surface):
        """Draws the screen content."""
        pass