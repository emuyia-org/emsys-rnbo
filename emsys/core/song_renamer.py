# emsys/ui/song_renamer.py
# -*- coding: utf-8 -*-
"""
Provides the SongRenamer class for handling the logic of
renaming song titles via MIDI controller input.
"""

import enum

# Define the virtual keyboard layout
KEYBOARD_LAYOUT = [
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
    "0123456789 .,!?-+",
    # Add more rows/symbols if needed
]

class RenameMode(enum.Enum):
    """Enumeration for the different renaming modes."""
    CARET = 1
    KEYBOARD = 2

class SongRenamer:
    """
    Manages the state and logic for renaming a song title using
    limited button inputs (yes, no, up, down, left, right).

    Operates in two modes:
    1. CARET: Navigate the title, backspace, or enter KEYBOARD mode.
    2. KEYBOARD: Select a character from the virtual keyboard to insert.
    """

    def __init__(self, initial_title: str = ""):
        """
        Initializes the SongRenamer.

        Args:
            initial_title: The starting title of the song.
        """
        self.title: str = initial_title
        # Start caret at the end by default
        self.caret_position: int = len(initial_title)
        self.mode: RenameMode = RenameMode.CARET
        self.keyboard_layout: list[str] = KEYBOARD_LAYOUT
        self.keyboard_cursor: tuple[int, int] = (0, 0) # (row, column)

    def handle_input(self, button: str) -> bool:
        """
        Processes a button press based on the current mode.

        Args:
            button: The name of the button pressed (e.g., 'yes', 'no',
                    'left', 'right', 'up', 'down'). Should be lowercase.

        Returns:
            bool: True if the state was changed, False otherwise.
        """
        button = button.lower()
        if self.mode == RenameMode.CARET:
            return self._handle_caret_mode(button)
        elif self.mode == RenameMode.KEYBOARD:
            return self._handle_keyboard_mode(button)
        return False # Should not happen

    def _handle_caret_mode(self, button: str) -> bool:
        """Handles input when in CARET mode."""
        initial_title = self.title
        initial_caret = self.caret_position

        if button == 'left':
            self.caret_position = max(0, self.caret_position - 1)
        elif button == 'right':
            self.caret_position = min(len(self.title), self.caret_position + 1)
        elif button == 'no': # Backspace
            if self.caret_position > 0:
                # Correct backspace logic: remove char *before* caret
                self.title = self.title[:self.caret_position - 1] + self.title[self.caret_position:]
                self.caret_position -= 1
        elif button == 'yes': # Enter Keyboard mode
            self.mode = RenameMode.KEYBOARD
            # Optional: Reset keyboard cursor to a default position (e.g., 'A')
            self.keyboard_cursor = (0, 0)
            return True # Mode changed
        # Ignore 'up' and 'down' in caret mode for now
        elif button in ('up', 'down'):
             return False

        # Return True if title or caret position changed
        return self.title != initial_title or self.caret_position != initial_caret

    def _handle_keyboard_mode(self, button: str) -> bool:
        """Handles input when in KEYBOARD mode."""
        rows = len(self.keyboard_layout)
        if rows == 0: return False # No keyboard defined

        current_row, current_col = self.keyboard_cursor
        # Ensure current_row is valid before accessing layout
        if not (0 <= current_row < rows):
            self.keyboard_cursor = (0,0) # Reset if invalid
            current_row, current_col = self.keyboard_cursor

        max_cols_current_row = len(self.keyboard_layout[current_row])
        if max_cols_current_row == 0: # Handle empty rows
             # Move to next/prev non-empty row? Or just stay? For now, stay.
             return False

        changed = False
        if button == 'left':
            new_col = (current_col - 1 + max_cols_current_row) % max_cols_current_row
            self.keyboard_cursor = (current_row, new_col)
            changed = True
        elif button == 'right':
            new_col = (current_col + 1) % max_cols_current_row
            self.keyboard_cursor = (current_row, new_col)
            changed = True
        elif button == 'up':
            new_row = (current_row - 1 + rows) % rows
            # Adjust column if new row is shorter/longer
            max_cols_new_row = len(self.keyboard_layout[new_row])
            new_col = min(current_col, max_cols_new_row - 1) if max_cols_new_row > 0 else 0
            self.keyboard_cursor = (new_row, new_col)
            changed = True
        elif button == 'down':
            new_row = (current_row + 1) % rows
            # Adjust column if new row is shorter/longer
            max_cols_new_row = len(self.keyboard_layout[new_row])
            new_col = min(current_col, max_cols_new_row - 1) if max_cols_new_row > 0 else 0
            self.keyboard_cursor = (new_row, new_col)
            changed = True
        elif button == 'yes': # Select character and return to Caret mode
            # Ensure cursor is valid before selecting
            if 0 <= current_row < rows and 0 <= current_col < len(self.keyboard_layout[current_row]):
                selected_char = self.keyboard_layout[current_row][current_col]
                # Insert character
                self.title = self.title[:self.caret_position] + selected_char + self.title[self.caret_position:]
                self.caret_position += 1
                # Switch back to caret mode
                self.mode = RenameMode.CARET
                changed = True
            else:
                # Cursor was somehow invalid, reset and don't insert
                self.keyboard_cursor = (0,0)
                self.mode = RenameMode.CARET
                changed = True # Mode changed
        elif button == 'no': # Cancel keyboard mode, return to Caret mode
            self.mode = RenameMode.CARET
            changed = True # Mode changed

        return changed

    def get_current_title(self) -> str:
        """Returns the current state of the song title being edited."""
        return self.title

    def get_display_info(self) -> dict:
        """
        Returns a dictionary containing information needed to display
        the current state to the user.
        """
        # Create a representation of the title with the caret
        # Using '|' as the caret symbol, adjust if needed
        display_title = (
            self.title[:self.caret_position] +
            '|' +
            self.title[self.caret_position:]
        )

        return {
            "mode": self.mode,
            "title_with_caret": display_title,
            "current_title": self.title,
            "caret_position": self.caret_position,
            "keyboard_layout": self.keyboard_layout,
            "keyboard_cursor": self.keyboard_cursor, # (row, col)
        }

    def set_keyboard_cursor(self, row: int, col: int) -> bool:
        """
        Directly sets the keyboard cursor position if the coordinates are valid.

        Args:
            row: The desired row index.
            col: The desired column index.

        Returns:
            bool: True if the cursor was successfully set, False otherwise.
        """
        rows = len(self.keyboard_layout)
        if not (0 <= row < rows):
            print(f"Error: Row index {row} out of bounds (0-{rows-1}).")
            return False

        cols_in_row = len(self.keyboard_layout[row])
        if not (0 <= col < cols_in_row):
            # Allow setting to col 0 even if row is empty? No, requires valid char index.
            print(f"Error: Column index {col} out of bounds (0-{cols_in_row-1}) for row {row}.")
            return False

        # Only allow setting if in keyboard mode? Or allow setting anytime?
        # Let's allow setting anytime, but it only visually matters in KEYBOARD mode.
        # The calling widget ensures it's called appropriately.
        self.keyboard_cursor = (row, col)
        print(f"Keyboard cursor set to ({row}, {col})")
        return True


# --- Example Usage (for testing this module directly) ---
if __name__ == "__main__":
    renamer = SongRenamer("My Song")

    def print_state(r):
        info = r.get_display_info()
        print("-" * 20)
        print(f"Mode: {info['mode'].name}")
        print(f"Title: {info['title_with_caret']}")
        if info['mode'] == RenameMode.KEYBOARD:
            print("Keyboard:")
            k_row, k_col = info['keyboard_cursor']
            for i, row_str in enumerate(info['keyboard_layout']):
                if i == k_row:
                    # Handle potential empty row or invalid col index gracefully
                    if row_str and 0 <= k_col < len(row_str):
                        print(f"  {row_str[:k_col]}[{row_str[k_col]}]{row_str[k_col+1:]}")
                    elif row_str: # Row exists but index is bad
                         print(f"  {row_str} [CURSOR ERROR]")
                    else: # Empty row
                         print(f"  [EMPTY ROW]")
                else:
                    print(f"  {row_str}")
        print("-" * 20)

    # Simulate button presses
    print_state(renamer)
    renamer.handle_input('left')
    renamer.handle_input('left')
    print_state(renamer)
    renamer.handle_input('no') # Backspace
    print_state(renamer)
    renamer.handle_input('yes') # Enter keyboard mode
    print_state(renamer)
    renamer.handle_input('down')
    renamer.handle_input('right'); renamer.handle_input('right')
    print_state(renamer)
    renamer.handle_input('yes') # Select 'c'
    print_state(renamer)
    print(f"\nFinal Title: {renamer.get_current_title()}")
