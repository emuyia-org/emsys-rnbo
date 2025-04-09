# -*- coding: utf-8 -*-
"""
Base Screen class for the Emsys Application.
Provides common functionality for all screens.
"""

import pygame

class BaseScreen:
    """Base class for all application screens."""
    
    def __init__(self, app_ref):
        """Initialize the base screen."""
        self.app = app_ref
        # Set up common fonts that all screens can use
        self.font = pygame.font.SysFont(None, 36)  # Standard font
        self.font_large = pygame.font.SysFont(None, 48)  # Larger font
        self.font_small = pygame.font.SysFont(None, 24)  # Smaller font
    
    def handle_event(self, event):
        """Handle pygame events. To be implemented by subclasses."""
        pass
    
    def update(self):
        """Update screen state. To be implemented by subclasses."""
        pass
    
    def draw(self, screen_surface):
        """Draw the screen content. Must be implemented by subclasses."""
        raise NotImplementedError("Each screen must implement its own draw method")
    
    def init(self):
        """Optional initialization when screen becomes active."""
        pass