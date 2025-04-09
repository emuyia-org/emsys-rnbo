# -*- coding: utf-8 -*-
"""
Placeholder Screen for Song Editing.
"""
import pygame
from .base_screen import BaseScreen

# Define colors if needed, or import from a central constants file
WHITE = (255, 255, 255)
BLACK = (0, 0, 0) # Example background color

class SongEditScreen(BaseScreen):
    """A placeholder screen for editing songs."""

    def __init__(self, app_ref):
        """Initialize the song editing screen."""
        super().__init__(app_ref)
        self.title_text = "Song Editor"
        self.title_surf = self.font_large.render(self.title_text, True, WHITE)
        self.title_rect = self.title_surf.get_rect(center=(self.app.screen.get_width() // 2, 50))

        self.placeholder_text = "Song editing interface will be here."
        self.placeholder_surf = self.font.render(self.placeholder_text, True, WHITE)
        self.placeholder_rect = self.placeholder_surf.get_rect(center=(self.app.screen.get_width() // 2, self.app.screen.get_height() // 2))

    def draw(self, screen_surface):
        """Draws the screen content."""
        # Optional: Fill background
        # screen_surface.fill(BLACK)

        # Draw the title and placeholder text
        screen_surface.blit(self.title_surf, self.title_rect)
        screen_surface.blit(self.placeholder_surf, self.placeholder_rect)

    # Optional: Implement other methods if needed, otherwise base class pass is fine
    # def handle_event(self, event):
    #     super().handle_event(event)
    #     pass
    #
    # def update(self):
    #     super().update()
    #     pass
    #
    # def init(self):
    #     super().init()
    #     print(f"{self.__class__.__name__} is now active.")
    #
    # def cleanup(self):
    #     super().cleanup()
    #     print(f"{self.__class__.__name__} is being deactivated.")

