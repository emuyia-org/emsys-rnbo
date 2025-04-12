# emsys/ui/widgets.py
# -*- coding: utf-8 -*-
"""
Reusable UI widgets for the emsys application.
"""
import pygame
import time
from typing import Optional, Dict, Tuple
from enum import Enum, auto

# Core components (relative imports within the same package level)
from ..core.song_renamer import SongRenamer, RenameMode
from ..config import settings, mappings

# Define colors (can also be imported from settings)
WHITE = settings.WHITE
BLACK = settings.BLACK
GREEN = settings.GREEN
RED = settings.RED
BLUE = settings.BLUE
HIGHLIGHT_COLOR = GREEN # Color for selected items
FOCUS_BORDER_COLOR = BLUE # Color for the border around the focused column - reusing for consistency
ERROR_COLOR = RED

# Define layout constants (can be adjusted or passed in)
TOP_MARGIN = 15
LINE_HEIGHT = 25

class TextInputStatus(Enum):
    """Status codes returned by the TextInputWidget's handle_input."""
    INACTIVE = auto()
    ACTIVE = auto()
    CONFIRMED = auto()
    CANCELLED = auto()
    ERROR = auto()

class TextInputWidget:
    """
    A widget for handling text input using MIDI CC navigation,
    leveraging the SongRenamer logic.
    """
    def __init__(self, app_ref):
        """Initialize the text input widget."""
        self.app = app_ref # Reference to the main application for screen access, fonts etc.
        self.font_large = pygame.font.Font(None, 48)
        self.font = pygame.font.Font(None, 32) # Standard font
        self.font_small = pygame.font.Font(None, 24)

        self.is_active: bool = False
        self.renamer_instance: Optional[SongRenamer] = None
        self.initial_text: str = ""
        self.prompt: str = "Enter Text" # Default prompt

    def start(self, initial_text: str, prompt: str = "Rename"):
        """Activate the widget to edit the given text."""
        print(f"TextInputWidget activated with text: '{initial_text}'")
        self.is_active = True
        self.initial_text = initial_text
        self.prompt = prompt
        self.renamer_instance = SongRenamer(initial_text)

    def cancel(self):
        """Deactivate the widget without confirming changes."""
        print("TextInputWidget cancelled.")
        self.is_active = False
        self.renamer_instance = None

    def get_text(self) -> Optional[str]:
        """Return the currently edited text if active."""
        if self.renamer_instance:
            return self.renamer_instance.get_current_title()
        return None

    def handle_input(self, cc: int) -> TextInputStatus:
        """
        Processes MIDI CC input when the widget is active.
        Returns the status after handling the input.
        """
        if not self.is_active or not self.renamer_instance:
            return TextInputStatus.INACTIVE

        # Map CCs to renamer button names
        button_map = {
            mappings.YES_NAV_CC: 'yes',
            mappings.DELETE_CC: 'no',  # Changed: DELETE_CC now acts as backspace ('no' button)
            mappings.UP_NAV_CC: 'up',
            mappings.DOWN_NAV_CC: 'down',
            mappings.LEFT_NAV_CC: 'left',
            mappings.RIGHT_NAV_CC: 'right',
        }
        button_name = button_map.get(cc)

        if button_name:
            state_changed = self.renamer_instance.handle_input(button_name)
            # We just need to know it's still active after valid input
            return TextInputStatus.ACTIVE

        # Use SAVE_CC (or a dedicated confirm CC) to confirm
        elif cc == mappings.SAVE_CC:
            final_text = self.renamer_instance.get_current_title().strip()
            if not final_text:
                 # Optionally provide feedback via app_ref or return ERROR?
                 # For now, let the calling screen handle empty validation
                 print("TextInputWidget: Confirmation attempted with empty text.")
                 # Keep active? Or return ERROR? Let's return CONFIRMED and let caller validate.
                 # self.is_active = False # Deactivate on confirm
                 # self.renamer_instance = None
                 return TextInputStatus.CONFIRMED # Caller must check if empty
            else:
                 print(f"TextInputWidget confirmed with text: '{final_text}'")
                 # self.is_active = False # Deactivate on confirm
                 # self.renamer_instance = None
                 return TextInputStatus.CONFIRMED

        # Use NO_NAV_CC (or a dedicated cancel CC) to cancel - changed from DELETE_CC
        elif cc == mappings.NO_NAV_CC:
             self.cancel() # Deactivates the widget
             return TextInputStatus.CANCELLED

        else:
            # Ignore unmapped buttons while active
            return TextInputStatus.ACTIVE

    def draw(self, surface: pygame.Surface):
        """Draws the text input interface."""
        if not self.is_active or not self.renamer_instance:
            return

        # Clear background or draw over existing screen content
        # For simplicity, let's assume the calling screen cleared the background
        # surface.fill(BLACK) # Optional: Fill background if needed

        rename_info = self.renamer_instance.get_display_info()
        mode = rename_info['mode']
        title_with_caret = rename_info['title_with_caret']
        keyboard_layout = rename_info['keyboard_layout']
        k_row, k_col = rename_info['keyboard_cursor']

        # Draw Prompt and Title Being Edited
        prompt_text = f"{self.prompt}: {title_with_caret}"
        title_surf = self.font_large.render(prompt_text, True, WHITE)
        title_rect = title_surf.get_rect(midtop=(surface.get_width() // 2, TOP_MARGIN + 10))
        # Basic clipping if text is too long
        if title_rect.width > surface.get_width() - 20:
             title_rect.width = surface.get_width() - 20
             title_rect.centerx = surface.get_width() // 2
        surface.blit(title_surf, title_rect)

        # Draw Instructions
        instr_y = title_rect.bottom + 10
        yes_cc = getattr(mappings, 'YES_NAV_CC', '?')
        no_cc = getattr(mappings, 'NO_NAV_CC', '?') 
        save_cc = getattr(mappings, 'SAVE_CC', '?')
        delete_cc = getattr(mappings, 'DELETE_CC', '?') 

        if mode == RenameMode.CARET:
            instr_text = f"Arrows: Move | {delete_cc}: Backspace | {yes_cc}: Keyboard"  # Changed: DELETE_CC for backspace
            instr2_text = f"{save_cc}: Confirm | {no_cc}: Cancel"  # Changed: NO_NAV_CC for cancel
        elif mode == RenameMode.KEYBOARD:
            instr_text = f"Arrows: Select | {yes_cc}: Insert Char"
            instr2_text = f"{delete_cc}: Back to Caret"  # Changed: DELETE_CC for back to caret
        else: # Should not happen
            instr_text = "Unknown Mode"
            instr2_text = ""


        instr_surf = self.font_small.render(instr_text, True, WHITE)
        instr_rect = instr_surf.get_rect(centerx=surface.get_width() // 2, top=instr_y)
        surface.blit(instr_surf, instr_rect)

        instr2_surf = self.font_small.render(instr2_text, True, WHITE)
        instr2_rect = instr2_surf.get_rect(centerx=surface.get_width() // 2, top=instr_rect.bottom + 2)
        surface.blit(instr2_surf, instr2_rect)

        instr_y = instr2_rect.bottom

        # Draw Keyboard (if in Keyboard mode)
        if mode == RenameMode.KEYBOARD:
            keyboard_y = instr_y + 15
            keyboard_line_height = LINE_HEIGHT # Use widget's line height

            for r_idx, row_str in enumerate(keyboard_layout):
                row_y = keyboard_y + (r_idx * keyboard_line_height)
                # Use the widget's standard font for the keyboard
                row_width = self.font.size(row_str)[0]
                row_start_x = (surface.get_width() - row_width) // 2

                if r_idx == k_row:
                    # Highlight selected character
                    if row_str and 0 <= k_col < len(row_str): # Check validity
                        pre_char = row_str[:k_col]
                        char = row_str[k_col]
                        post_char = row_str[k_col+1:]

                        pre_surf = self.font.render(pre_char, True, WHITE)
                        char_surf = self.font.render(char, True, BLACK) # Selected char text
                        post_surf = self.font.render(post_char, True, WHITE)

                        pre_rect = pre_surf.get_rect(topleft=(row_start_x, row_y))
                        char_width, char_height = self.font.size(char)
                        # Use HIGHLIGHT_COLOR for the background block
                        char_bg_rect = pygame.Rect(pre_rect.right, row_y - 2, char_width + 4, keyboard_line_height)
                        pygame.draw.rect(surface, HIGHLIGHT_COLOR, char_bg_rect)
                        char_rect = char_surf.get_rect(center=char_bg_rect.center)
                        post_rect = post_surf.get_rect(topleft=(char_bg_rect.right, row_y))

                        surface.blit(pre_surf, pre_rect)
                        surface.blit(char_surf, char_rect)
                        surface.blit(post_surf, post_rect)
                    else: # Draw row normally if cursor is invalid (e.g., empty row)
                         row_surf = self.font.render(row_str, True, WHITE) # Just draw normally
                         row_rect = row_surf.get_rect(topleft=(row_start_x, row_y))
                         surface.blit(row_surf, row_rect)
                else:
                    # Draw normal row
                    row_surf = self.font.render(row_str, True, WHITE)
                    row_rect = row_surf.get_rect(topleft=(row_start_x, row_y))
                    surface.blit(row_surf, row_rect)

