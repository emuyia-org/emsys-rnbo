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
        """Activate the widget to edit the given text, starting in keyboard mode."""
        print(f"TextInputWidget activated with text: '{initial_text}'")
        self.is_active = True
        self.initial_text = initial_text
        self.prompt = prompt
        self.renamer_instance = SongRenamer(initial_text)

        # --- Start and Force Keyboard Mode ---
        if self.renamer_instance:
            # Ensure we are in a state where 'yes' enters keyboard mode.
            # If the initial text is empty, 'yes' should work directly.
            # If not empty, move to end first.
            current_len = len(self.renamer_instance.get_current_title())
            if current_len > 0:
                 # Move caret to end - assumes 'right' works in initial caret mode
                 current_mode_info = self.renamer_instance.get_display_info()
                 if current_mode_info['mode'] == RenameMode.CARET:
                     for _ in range(current_len):
                         self.renamer_instance.handle_input('right')

            # Enter keyboard mode
            self.renamer_instance.handle_input('yes')
            print(f"TextInputWidget forced to Keyboard Mode. Current state: {self.renamer_instance.get_display_info()}")
        # --- End Start and Force Keyboard Mode ---


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
        Unified mode: Always presents keyboard, simulates caret actions,
        and preserves keyboard cursor position using set_keyboard_cursor.
        """
        if not self.is_active or not self.renamer_instance:
            return TextInputStatus.INACTIVE

        action_taken = False # Flag to track if any action was performed
        restore_kbd_cursor = False # Flag to indicate if cursor needs restoration
        saved_k_row, saved_k_col = 0, 0 # Initialize saved cursor position

        # --- Unified CC Mapping ---
        if cc == mappings.UP_NAV_CC:
            self.renamer_instance.handle_input('up') # Keyboard nav
            action_taken = True
        elif cc == mappings.DOWN_NAV_CC:
            self.renamer_instance.handle_input('down') # Keyboard nav
            action_taken = True
        elif cc == mappings.LEFT_NAV_CC:
            self.renamer_instance.handle_input('left') # Keyboard nav
            action_taken = True
        elif cc == mappings.RIGHT_NAV_CC:
            self.renamer_instance.handle_input('right') # Keyboard nav
            action_taken = True
        elif cc == mappings.YES_NAV_CC:
            print("Inserting character...")
            # Save cursor before exiting keyboard mode
            current_info = self.renamer_instance.get_display_info()
            if current_info['mode'] == RenameMode.KEYBOARD: # Should always be true here
                 saved_k_row, saved_k_col = current_info['keyboard_cursor']
                 restore_kbd_cursor = True
            else:
                 print("Warning: Tried to save kbd cursor when not in KEYBOARD mode.")
            # Perform action
            self.renamer_instance.handle_input('yes') # Insert character (switches renamer to CARET)
            self.renamer_instance.handle_input('yes') # Immediately re-enter KEYBOARD mode
            action_taken = True
            print("...Insertion done, back in KEYBOARD mode.")
        elif cc == mappings.PREV_CC: # Move Caret Left (Simulation)
            print("Simulating Caret Left...")
            # Save cursor before exiting keyboard mode
            current_info = self.renamer_instance.get_display_info()
            if current_info['mode'] == RenameMode.KEYBOARD:
                 saved_k_row, saved_k_col = current_info['keyboard_cursor']
                 restore_kbd_cursor = True
            else:
                 print("Warning: Tried to save kbd cursor when not in KEYBOARD mode.")
            # Perform action
            self.renamer_instance.handle_input('no')   # Exit keyboard
            self.renamer_instance.handle_input('left') # Move caret left
            self.renamer_instance.handle_input('yes')  # Re-enter keyboard
            action_taken = True
            print("...Simulation done.")
        elif cc == mappings.NEXT_CC: # Move Caret Right (Simulation)
            print("Simulating Caret Right...")
            # Save cursor before exiting keyboard mode
            current_info = self.renamer_instance.get_display_info()
            if current_info['mode'] == RenameMode.KEYBOARD:
                 saved_k_row, saved_k_col = current_info['keyboard_cursor']
                 restore_kbd_cursor = True
            else:
                 print("Warning: Tried to save kbd cursor when not in KEYBOARD mode.")
            # Perform action
            self.renamer_instance.handle_input('no')   # Exit keyboard
            self.renamer_instance.handle_input('right')# Move caret right
            self.renamer_instance.handle_input('yes')  # Re-enter keyboard
            action_taken = True
            print("...Simulation done.")
        elif cc == mappings.DELETE_CC: # Backspace (Simulation)
            print("Simulating Backspace...")
            # Save cursor before exiting keyboard mode
            current_info = self.renamer_instance.get_display_info()
            if current_info['mode'] == RenameMode.KEYBOARD:
                 saved_k_row, saved_k_col = current_info['keyboard_cursor']
                 restore_kbd_cursor = True
            else:
                 print("Warning: Tried to save kbd cursor when not in KEYBOARD mode.")
            # Perform action
            self.renamer_instance.handle_input('no')   # Exit keyboard
            self.renamer_instance.handle_input('no')   # Backspace (in caret mode)
            self.renamer_instance.handle_input('yes')  # Re-enter keyboard
            action_taken = True
            print("...Simulation done.")
        elif cc == mappings.SAVE_CC:
            # Confirm action
            final_text = self.renamer_instance.get_current_title().strip()
            if not final_text:
                 print("TextInputWidget: Confirmation attempted with empty text.")
                 # Return CONFIRMED and let caller validate.
                 # DO NOT deactivate here. Let the caller handle it.
                 return TextInputStatus.CONFIRMED
            else:
                 print(f"TextInputWidget confirmed with text: '{final_text}'")
                 # DO NOT deactivate here. Let the caller handle it.
                 return TextInputStatus.CONFIRMED
        elif cc == mappings.NO_NAV_CC:
            # Cancel action
            self.cancel()
            return TextInputStatus.CANCELLED

        # --- Restore Keyboard Cursor Position ---
        if restore_kbd_cursor and self.renamer_instance:
            print(f"Attempting to restore keyboard cursor to ({saved_k_row}, {saved_k_col}) using set_keyboard_cursor...")
            # Ensure we are back in keyboard mode before setting
            current_mode = self.renamer_instance.get_display_info()['mode']
            if current_mode == RenameMode.KEYBOARD:
                success = self.renamer_instance.set_keyboard_cursor(saved_k_row, saved_k_col)
                if success:
                    final_k_row, final_k_col = self.renamer_instance.get_display_info()['keyboard_cursor']
                    print(f"...Cursor restored to: ({final_k_row}, {final_k_col})")
                else:
                    print(f"...Failed to restore cursor to ({saved_k_row}, {saved_k_col}). Coordinates might be invalid now.")
            else:
                print(f"Warning: Could not restore cursor, not in KEYBOARD mode (current mode: {current_mode}).")


        # If any action was taken (or ignored), remain active
        if action_taken:
            return TextInputStatus.ACTIVE
        else:
            # Ignore unmapped buttons
            return TextInputStatus.ACTIVE


    def draw(self, surface: pygame.Surface):
        """Draws the text input interface (always showing keyboard)."""
        if not self.is_active or not self.renamer_instance:
            return

        # Clear background or draw over existing screen content
        # For simplicity, let's assume the calling screen cleared the background
        # surface.fill(BLACK) # Optional: Fill background if needed

        rename_info = self.renamer_instance.get_display_info()
        # We ignore rename_info['mode'] for drawing decisions now, assume keyboard always shown
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

        # Draw Instructions for Unified Mode
        instr_y = title_rect.bottom + 10

        # Get button names from mappings
        yes_button = "YES"
        no_button = "NO"
        save_button = "SAVE"
        delete_button = "DELETE"
        up_button = "UP"
        down_button = "DOWN"
        left_button = "LEFT"
        right_button = "RIGHT"
        prev_button = "PREV" # Now used for caret left
        next_button = "NEXT" # Now used for caret right

        instr_text = f"Kbd Nav: {up_button}/{down_button}/{left_button}/{right_button} | Insert: {yes_button}"
        instr2_text = f"Move Caret: {prev_button}/{next_button} | Backspace: {delete_button}"
        instr3_text = f"Save: {save_button} | Cancel: {no_button}"


        instr_surf = self.font_small.render(instr_text, True, WHITE)
        instr_rect = instr_surf.get_rect(centerx=surface.get_width() // 2, top=instr_y)
        surface.blit(instr_surf, instr_rect)

        instr2_surf = self.font_small.render(instr2_text, True, WHITE)
        instr2_rect = instr2_surf.get_rect(centerx=surface.get_width() // 2, top=instr_rect.bottom + 2)
        surface.blit(instr2_surf, instr2_rect)

        instr3_surf = self.font_small.render(instr3_text, True, WHITE)
        instr3_rect = instr3_surf.get_rect(centerx=surface.get_width() // 2, top=instr2_rect.bottom + 2)
        surface.blit(instr3_surf, instr3_rect)


        instr_y = instr3_rect.bottom # Update bottom y coordinate

        # Draw Keyboard (Always)
        keyboard_y = instr_y + 15 # Position below instructions
        keyboard_line_height = self.font_mono.get_linesize()

        # Calculate grid properties based on monospaced font
        if not keyboard_layout: # Handle empty layout case
            return

        # Use width of a common character like space for cell width in monospaced font
        char_width = self.font_mono.size(' ')[0]
        if char_width == 0: # Fallback if space width is zero
             char_width = self.font_mono.size('M')[0] # Use a wide character

        max_row_len = max(len(row) for row in keyboard_layout) if keyboard_layout else 0
        keyboard_block_width = max_row_len * char_width
        keyboard_start_x = (surface.get_width() - keyboard_block_width) // 2

        for r_idx, row_str in enumerate(keyboard_layout):
            row_y = keyboard_y + (r_idx * keyboard_line_height)

            for c_idx, char in enumerate(row_str):
                char_x = keyboard_start_x + (c_idx * char_width)
                char_render_width, char_render_height = self.font_mono.size(char)

                # Center character horizontally and vertically within its cell
                char_render_x = char_x + (char_width - char_render_width) // 2
                char_render_y = row_y + (keyboard_line_height - char_render_height) // 2

                if r_idx == k_row and c_idx == k_col:
                    # Highlight selected character's cell
                    char_bg_rect = pygame.Rect(char_x, row_y, char_width, keyboard_line_height)
                    pygame.draw.rect(surface, HIGHLIGHT_COLOR, char_bg_rect)
                    # Render selected character text
                    char_surf = self.font_mono.render(char, True, BLACK)
                    surface.blit(char_surf, (char_render_x, char_render_y))
                else:
                    # Render normal character text
                    char_surf = self.font_mono.render(char, True, WHITE)
                    surface.blit(char_surf, (char_render_x, char_render_y))

