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
        # Try loading a common monospaced font
        try:
            self.font_mono = pygame.font.SysFont('monospace', 28) # Use a system monospaced font
        except pygame.error:
            print("Warning: Monospace font not found, falling back to default.")
            self.font_mono = pygame.font.Font(None, 28) # Fallback

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

        # Check the current mode to handle buttons correctly
        if self.renamer_instance and hasattr(self.renamer_instance, 'get_display_info'):
            current_mode = self.renamer_instance.get_display_info()['mode']
        else:
            current_mode = None  # Fallback if we can't determine mode

        # Map CCs to renamer button names
        button_map = {
            mappings.YES_NAV_CC: 'yes',
            mappings.UP_NAV_CC: 'up',
            mappings.DOWN_NAV_CC: 'down',
            mappings.LEFT_NAV_CC: 'left',
            mappings.RIGHT_NAV_CC: 'right',
        }
        
        # Add DELETE_CC to button map only if not in keyboard mode
        if current_mode != RenameMode.KEYBOARD:
            button_map[mappings.DELETE_CC] = 'no'  # DELETE_CC acts as backspace ('no' button) only in caret mode
        
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
        # Use NO_NAV_CC differently based on mode
        elif cc == mappings.NO_NAV_CC:
             # If in keyboard mode, treat NO button like DELETE button (exit keyboard mode)
             if current_mode == RenameMode.KEYBOARD:
                 # Handle it like the DELETE button - send 'no' to exit keyboard mode
                 self.renamer_instance.handle_input('no')
                 return TextInputStatus.ACTIVE
             else:
                 # In caret mode, cancel the entire widget as before
                 self.cancel()  # Deactivates the widget
                 return TextInputStatus.CANCELLED
        # Ignore DELETE_CC in keyboard mode (it's already excluded from button_map above)
        elif cc == mappings.DELETE_CC and current_mode == RenameMode.KEYBOARD:
            # Do nothing in keyboard mode when DELETE is pressed
            return TextInputStatus.ACTIVE
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
        
        # Get button names from mappings instead of CC numbers
        yes_button = "YES"  # From YES_NAV_CC comment in mappings.py
        no_button = "NO"    # From NO_NAV_CC comment in mappings.py
        save_button = "SAVE"  # From SAVE_CC comment in mappings.py
        delete_button = "DELETE"  # From DELETE_CC comment in mappings.py

        if mode == RenameMode.CARET:
            instr_text = f"Insert: {yes_button} | Backspace: {delete_button}"
            instr2_text = f"Save: {save_button} | Exit: {no_button}"
        elif mode == RenameMode.KEYBOARD:
            instr_text = f"Insert: {yes_button} | Exit: {no_button}"
            instr2_text = f""
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
            keyboard_line_height = self.font_mono.get_linesize() # Use mono font line height

            for r_idx, row_str in enumerate(keyboard_layout):
                row_y = keyboard_y + (r_idx * keyboard_line_height)
                # Use the monospaced font for the keyboard
                row_width = self.font_mono.size(row_str)[0]
                row_start_x = (surface.get_width() - row_width) // 2

                if r_idx == k_row:
                    # Highlight selected character
                    if row_str and 0 <= k_col < len(row_str): # Check validity
                        pre_char = row_str[:k_col]
                        char = row_str[k_col]
                        post_char = row_str[k_col+1:]

                        pre_surf = self.font_mono.render(pre_char, True, WHITE)
                        char_surf = self.font_mono.render(char, True, BLACK) # Selected char text
                        post_surf = self.font_mono.render(post_char, True, WHITE)

                        pre_rect = pre_surf.get_rect(topleft=(row_start_x, row_y))
                        char_width, char_height = self.font_mono.size(char) # Use mono font size
                        # Use HIGHLIGHT_COLOR for the background block
                        # Adjust background rect slightly for mono font appearance
                        char_bg_rect = pygame.Rect(pre_rect.right, row_y, char_width, keyboard_line_height)
                        pygame.draw.rect(surface, HIGHLIGHT_COLOR, char_bg_rect)
                        # Center char vertically within the line height
                        char_rect = char_surf.get_rect(centerx=char_bg_rect.centerx, top=row_y + (keyboard_line_height - char_height) // 2)
                        post_rect = post_surf.get_rect(topleft=(char_bg_rect.right, row_y))

                        surface.blit(pre_surf, pre_rect)
                        surface.blit(char_surf, char_rect)
                        surface.blit(post_surf, post_rect)
                    else: # Draw row normally if cursor is invalid (e.g., empty row)
                         row_surf = self.font_mono.render(row_str, True, WHITE) # Just draw normally
                         row_rect = row_surf.get_rect(topleft=(row_start_x, row_y))
                         surface.blit(row_surf, row_rect)
                else:
                    # Draw normal row
                    row_surf = self.font_mono.render(row_str, True, WHITE)
                    row_rect = row_surf.get_rect(topleft=(row_start_x, row_y))
                    surface.blit(row_surf, row_rect)

