# -*- coding: utf-8 -*-
"""
Main Menu Screen for the Emsys Application.
Serves as the primary navigation screen.
"""

import pygame
from .base_screen import BaseScreen

class MainMenuScreen(BaseScreen):
    """Main menu screen for the application."""
    
    def __init__(self, app_ref):
        super().__init__(app_ref)
        self.title = "MAIN MENU"
        self.title_surf = self.font_large.render(self.title, True, (255, 255, 255))
        self.title_rect = self.title_surf.get_rect(center=(self.app.screen.get_width() // 2, 50))
        
        # Menu options
        self.menu_options = [
            "Status",
            "Settings",
            "About",
            "Exit"
        ]
        
        # Pre-render menu options
        self.option_surfs = []
        for i, option in enumerate(self.menu_options):
            surf = self.font.render(option, True, (220, 220, 220))
            rect = surf.get_rect(center=(self.app.screen.get_width() // 2, 120 + i * 45))
            self.option_surfs.append((surf, rect))
            
        # Navigation hint
        self.nav_text = "Use CC 32 (next) / CC 40 (prev) to navigate screens"
        self.nav_surf = self.font_small.render(self.nav_text, True, (150, 150, 150))
        self.nav_rect = self.nav_surf.get_rect(center=(self.app.screen.get_width() // 2, 
                                                      self.app.screen.get_height() - 30))

    def handle_event(self, event):
        """Handles events passed to this screen."""
        # Basic event handling - can be expanded later
        pass

    def update(self):
        """Updates the screen state."""
        # No dynamic content yet, so nothing to update
        pass

    def draw(self, screen_surface):
        """Draw the main menu content."""
        # Draw background
        pygame.draw.rect(screen_surface, (30, 30, 30), 
                         (0, 0, screen_surface.get_width(), screen_surface.get_height()))
        
        # Draw title
        screen_surface.blit(self.title_surf, self.title_rect)
        
        # Draw menu options
        for surf, rect in self.option_surfs:
            screen_surface.blit(surf, rect)
            
        # Draw navigation hint
        screen_surface.blit(self.nav_surf, self.nav_rect)