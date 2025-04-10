# emsys/ui/song_edit_screen.py
# -*- coding: utf-8 -*-
"""
Screen for viewing and editing Song objects. Includes renaming functionality.
"""
import pygame
import time
from typing import List, Optional, Tuple, Any

# Core components
from .base_screen import BaseScreen
from ..core.song import Song, Segment
from ..core.song import (MIN_TEMPO, MAX_TEMPO, MIN_RAMP, MAX_RAMP,
                         MIN_LOOP_LENGTH, MAX_LOOP_LENGTH, MIN_REPETITIONS,
                         MAX_REPETITIONS, MIN_PROGRAM_MSG, MAX_PROGRAM_MSG)
# Utilities and Config
from ..utils import file_io # Import the file I/O utilities
from ..config import settings, mappings

# --- Import the actual SongRenamer ---
from ..core.song_renamer import SongRenamer, RenameMode
# ------------------------------------

# Define colors (can also be imported from settings)
WHITE = settings.WHITE
BLACK = settings.BLACK
GREEN = settings.GREEN
RED = settings.RED
BLUE = settings.BLUE
HIGHLIGHT_COLOR = GREEN # Color for selected items
PARAM_COLOR = WHITE     # Color for parameter names/values
VALUE_COLOR = WHITE     # Color for parameter values (can be different)
FEEDBACK_COLOR = BLUE   # Color for feedback messages
ERROR_COLOR = RED       # Color for error messages

# Define layout constants
LEFT_MARGIN = 15
TOP_MARGIN = 15
LINE_HEIGHT = 25
PARAM_INDENT = 30
SEGMENT_LIST_WIDTH = 180 # Width for the segment list area
PARAM_AREA_X = LEFT_MARGIN + SEGMENT_LIST_WIDTH + 15 # Start X for parameter details

# Define parameter editing steps
PARAM_STEPS = {
    'program_message_1': 1,
    'program_message_2': 1,
    'tempo': 1.0, # Edit tempo in increments of 1 BPM
    'tempo_ramp': 0.5, # Edit ramp in 0.5 second increments
    'loop_length': 1,
    'repetitions': 1,
    'automatic_transport_interrupt': 1, # Special handling for bool
}

class SongEditScreen(BaseScreen):
    """Screen for editing song structure and segment parameters."""
    """Screen for editing song structure and segment parameters."""

    def __init__(self, app_ref):
        """Initialize the song editing screen."""
        super().__init__(app_ref)
        # Define additional fonts needed
        self.font_large = pygame.font.Font(None, 36)  # Larger font for titles
        self.font_small = pygame.font.Font(None, 18)  # Smaller font for detailed info
        
        self.current_song: Optional[Song] = None
        self.selected_segment_index: Optional[int] = None
        self.selected_parameter_key: Optional[str] = None
        self.feedback_message: Optional[Tuple[str, float, Tuple[int, int, int]]] = None # (message, timestamp, color) - Added color
        self.feedback_duration: float = 2.0 # seconds

        # --- Add state for renaming ---
        self.is_renaming_song: bool = False
        self.song_renamer_instance: Optional[SongRenamer] = None
        # -----------------------------

        # Define the order and names of editable parameters
        self.parameter_keys: List[str] = [
            'program_message_1',
            'program_message_2',
            'tempo',
            'tempo_ramp',
            'loop_length',
            'repetitions',
            'automatic_transport_interrupt'
        ]
        # Friendlier display names for parameters
        self.parameter_display_names: dict[str, str] = {
            'program_message_1': "Prog Ch 1",
            'program_message_2': "Prog Ch 2",
            'tempo': "Tempo (BPM)",
            'tempo_ramp': "Ramp (Sec)",
            'loop_length': "Length (Beats)",
            'repetitions': "Repeats",
            'automatic_transport_interrupt': "Auto Pause"
        }

    def init(self):
        """Called when the screen becomes active. Load the current song."""
        super().init()
        print(f"{self.__class__.__name__} is now active.")
        # Attempt to get the current song from the main app
        if hasattr(self.app, 'current_song'):
            self.current_song = self.app.current_song
        else:
            self.current_song = None
            print("Warning: No 'current_song' attribute found in app reference.")
            self.set_feedback("No song loaded!", is_error=True, duration=5.0)

        # Initialize selection state
        if self.current_song and self.current_song.segments:
            self.selected_segment_index = 0
            if self.parameter_keys: # Ensure parameter keys exist
                self.selected_parameter_key = self.parameter_keys[0]
            else:
                self.selected_parameter_key = None
        else:
            self.selected_segment_index = None
            self.selected_parameter_key = None

        # --- Reset renaming state on init ---
        self.is_renaming_song = False
        self.song_renamer_instance = None
        # ------------------------------------
        self.clear_feedback() # Clear any old feedback

    def cleanup(self):
        """Called when the screen becomes inactive."""
        super().cleanup()
        print(f"{self.__class__.__name__} is being deactivated.")
        # --- Ensure renaming state is cleared on exit ---
        self.is_renaming_song = False
        self.song_renamer_instance = None
        # ---------------------------------------------
        self.clear_feedback()

    def set_feedback(self, message: str, is_error: bool = False, duration: Optional[float] = None):
        """Display a feedback message for a limited time."""
        print(f"Feedback: {message}")
        color = ERROR_COLOR if is_error else FEEDBACK_COLOR
        self.feedback_message = (message, time.time(), color)
        self.feedback_duration = duration if duration is not None else 2.0

    def clear_feedback(self):
        """Clear the feedback message."""
        self.feedback_message = None

    def update(self):
        """Update screen state, like clearing timed feedback."""
        super().update()
        if self.feedback_message and (time.time() - self.feedback_message[1] > self.feedback_duration):
            self.clear_feedback()

    def handle_midi(self, msg):
        """Handle MIDI messages delegated from the main app."""
        if msg.type != 'control_change' or msg.value != 127: # Process only CC on messages
            return

        cc = msg.control
        print(f"SongEditScreen received CC: {cc}")

        # --- Handle Renaming Mode FIRST ---
        if self.is_renaming_song:
            self._handle_rename_input(cc)
            return # Don't process other actions while renaming
        # ----------------------------------

        # --- Normal Edit Mode Handling ---
        # Navigation
        if cc == mappings.DOWN_NAV_CC:
            self._change_selected_segment(1)
        elif cc == mappings.UP_NAV_CC:
            self._change_selected_segment(-1)
        elif cc == mappings.RIGHT_NAV_CC:
            self._change_selected_parameter(1)
        elif cc == mappings.LEFT_NAV_CC:
            self._change_selected_parameter(-1)

        # Value Modification
        elif cc == mappings.YES_NAV_CC: # Increment
            self._modify_selected_parameter(1)
        elif cc == mappings.NO_NAV_CC: # Decrement
            self._modify_selected_parameter(-1)

        # Actions
        elif cc == mappings.SAVE_SONG_CC:
            self._save_current_song()
        elif cc == mappings.ADD_SEGMENT_CC:
            self._add_new_segment()
        elif cc == mappings.DELETE_SEGMENT_CC:
            self._delete_selected_segment()
        # --- Add a trigger for renaming ---
        elif cc == mappings.RENAME_SONG_CC: # CC 85
             self._start_song_rename()
        # ----------------------------------

    # --- NEW: Methods for Renaming ---

    def _start_song_rename(self):
        """Initiates the song renaming process."""
        if self.current_song:
            self.is_renaming_song = True
            # Initialize the renamer with the current song name
            self.song_renamer_instance = SongRenamer(self.current_song.name)
            self.clear_feedback() # Clear other feedback
            print("Starting song rename mode.")
            self.set_feedback("Renaming Song...", duration=1.0) # Brief indicator
        else:
            self.set_feedback("No song loaded to rename", is_error=True)

    def _handle_rename_input(self, cc: int):
        """Processes MIDI CC input specifically for the SongRenamer."""
        if not self.song_renamer_instance:
            # Should not happen if is_renaming_song is True, but safety check
            self.is_renaming_song = False
            return

        # Map CCs to renamer button names
        button_map = {
            mappings.YES_NAV_CC: 'yes',
            mappings.NO_NAV_CC: 'no',
            mappings.UP_NAV_CC: 'up',
            mappings.DOWN_NAV_CC: 'down',
            mappings.LEFT_NAV_CC: 'left',
            mappings.RIGHT_NAV_CC: 'right',
        }
        button_name = button_map.get(cc)

        if button_name:
            state_changed = self.song_renamer_instance.handle_input(button_name)
            if state_changed:
                self.clear_feedback() # Clear feedback on valid input that changes state

        # Use SAVE_SONG_CC to confirm the rename
        elif cc == mappings.SAVE_SONG_CC:
            self._confirm_song_rename()

        # Use DELETE_SEGMENT_CC to cancel rename
        elif cc == mappings.DELETE_SEGMENT_CC:
             self._cancel_song_rename()

        else:
            # Optional: Provide feedback for unmapped buttons in this mode
            # self.set_feedback("Unknown command in rename mode", is_error=True)
            pass

    def _confirm_song_rename(self):
        """Confirms the rename, updates the song, and saves."""
        if not self.is_renaming_song or not self.song_renamer_instance or not self.current_song:
            return # Should not happen

        new_name = self.song_renamer_instance.get_current_title().strip()
        old_name = self.current_song.name

        if not new_name:
            self.set_feedback("Song name cannot be empty.", is_error=True)
            return # Stay in rename mode

        if new_name == old_name:
            self.set_feedback("Name unchanged. Exiting rename.")
            self.is_renaming_song = False
            self.song_renamer_instance = None
            return

        print(f"Attempting to rename song from '{old_name}' to '{new_name}'")

        # --- File Renaming Logic ---
        if not hasattr(file_io, 'rename_song'):
             self.set_feedback("Error: File renaming function not implemented!", is_error=True)
             return

        # Use the rename_song function from file_io
        if file_io.rename_song(old_name, new_name):
            # Update the in-memory song object's name
            self.current_song.name = new_name
            self.set_feedback(f"Renamed to '{new_name}'. Saving...")
            pygame.display.flip() # Show feedback immediately

            # Save the song content with the new name
            if file_io.save_song(self.current_song):
                self.set_feedback(f"Song renamed and saved as '{new_name}'")
            else:
                self.set_feedback(f"Renamed file, but failed to save content for '{new_name}'", is_error=True)

            # Exit rename mode on successful rename
            self.is_renaming_song = False
            self.song_renamer_instance = None

        else:
            # file_io.rename_song failed (e.g., file exists, permissions)
            # file_io.rename_song should print the specific error
            self.set_feedback(f"Failed to rename file (see console)", is_error=True)
            # Stay in rename mode so the user can try a different name or cancel.

    def _cancel_song_rename(self):
        """Cancels the renaming process without saving changes."""
        if self.is_renaming_song:
            self.is_renaming_song = False
            self.song_renamer_instance = None
            self.set_feedback("Rename cancelled.")
            print("Cancelled song rename mode.")

    # --- End of Renaming Methods ---


    # --- Internal Helper Methods for Actions (Existing - with guards) ---

    def _change_selected_segment(self, direction: int):
        """Move segment selection up or down."""
        if self.is_renaming_song: return # Prevent action during rename
        if not self.current_song or not self.current_song.segments:
            self.set_feedback("No segments to select", is_error=True)
            return

        num_segments = len(self.current_song.segments)
        if self.selected_segment_index is None:
            self.selected_segment_index = 0
        else:
            self.selected_segment_index = (self.selected_segment_index + direction) % num_segments

        if self.parameter_keys:
            self.selected_parameter_key = self.parameter_keys[0]
        self.clear_feedback()


    def _change_selected_parameter(self, direction: int):
        """Move parameter selection left or right."""
        if self.is_renaming_song: return # Prevent action during rename
        if self.selected_segment_index is None or not self.parameter_keys:
            self.set_feedback("Select a segment first", is_error=True)
            return

        try:
            current_param_index = self.parameter_keys.index(self.selected_parameter_key)
            next_param_index = (current_param_index + direction) % len(self.parameter_keys)
            self.selected_parameter_key = self.parameter_keys[next_param_index]
            self.clear_feedback()
        except (ValueError, AttributeError):
            self.selected_parameter_key = self.parameter_keys[0] if self.parameter_keys else None


    def _modify_selected_parameter(self, direction: int):
        """Increment or decrement the value of the selected parameter."""
        if self.is_renaming_song: return # Prevent action during rename
        if self.selected_segment_index is None or self.selected_parameter_key is None:
            self.set_feedback("Select segment and parameter first", is_error=True)
            return
        if not self.current_song: return

        try:
            segment = self.current_song.get_segment(self.selected_segment_index)
            key = self.selected_parameter_key
            current_value = getattr(segment, key)
            step = PARAM_STEPS.get(key, 1)

            new_value: Any

            if isinstance(current_value, bool):
                new_value = not current_value
            elif isinstance(current_value, int):
                new_value = current_value + direction * step
                if key in ('program_message_1', 'program_message_2'):
                    new_value = max(MIN_PROGRAM_MSG, min(MAX_PROGRAM_MSG, new_value))
                elif key == 'loop_length':
                    new_value = max(MIN_LOOP_LENGTH, min(MAX_LOOP_LENGTH, new_value))
                elif key == 'repetitions':
                    new_value = max(MIN_REPETITIONS, min(MAX_REPETITIONS, new_value))
            elif isinstance(current_value, float):
                new_value = current_value + direction * step
                if key == 'tempo':
                    new_value = max(MIN_TEMPO, min(MAX_TEMPO, new_value))
                elif key == 'tempo_ramp':
                    new_value = max(MIN_RAMP, min(MAX_RAMP, new_value))
                new_value = round(new_value, 2)
            else:
                self.set_feedback(f"Cannot modify type {type(current_value)}", is_error=True)
                return

            self.current_song.update_segment(self.selected_segment_index, **{key: new_value})
            display_name = self.parameter_display_names.get(key, key)
            value_display = "YES" if isinstance(new_value, bool) and new_value else "NO" if isinstance(new_value, bool) else new_value
            self.set_feedback(f"{display_name}: {value_display}")

        except (IndexError, AttributeError, TypeError, ValueError) as e:
            self.set_feedback(f"Error modifying value: {e}", is_error=True)


    def _save_current_song(self):
        """Save the current song state to a file."""
        if self.is_renaming_song: return # Prevent action during rename
        if self.current_song:
            if file_io.save_song(self.current_song):
                self.set_feedback(f"Song '{self.current_song.name}' saved.")
            else:
                self.set_feedback(f"Failed to save song '{self.current_song.name}'", is_error=True)
        else:
            self.set_feedback("No song loaded to save", is_error=True)


    def _add_new_segment(self):
        """Add a new segment with default values after the selected one."""
        if self.is_renaming_song: return # Prevent action during rename
        if not self.current_song:
            self.set_feedback("Load a song first", is_error=True)
            return

        new_segment = Segment()
        insert_index = (self.selected_segment_index + 1) if self.selected_segment_index is not None else len(self.current_song.segments)

        try:
            self.current_song.add_segment(new_segment, index=insert_index)
            self.selected_segment_index = insert_index
            if self.parameter_keys:
                 self.selected_parameter_key = self.parameter_keys[0]
            self.set_feedback(f"Added new segment at position {insert_index + 1}")
        except Exception as e:
            self.set_feedback(f"Error adding segment: {e}", is_error=True)


    def _delete_selected_segment(self):
        """Delete the currently selected segment."""
        if self.is_renaming_song: return # Prevent action during rename
        if self.selected_segment_index is None or not self.current_song or not self.current_song.segments:
            self.set_feedback("No segment selected to delete", is_error=True)
            return

        try:
            deleted_index_for_feedback = self.selected_segment_index + 1
            self.current_song.remove_segment(self.selected_segment_index)
            num_segments = len(self.current_song.segments)

            if num_segments == 0:
                self.selected_segment_index = None
                self.selected_parameter_key = None
            elif self.selected_segment_index >= num_segments:
                self.selected_segment_index = num_segments - 1
            # Else: index remains valid

            self.set_feedback(f"Deleted segment {deleted_index_for_feedback}")

        except IndexError:
             self.set_feedback("Error deleting segment (index out of range?)", is_error=True)
             if self.current_song and self.current_song.segments:
                 self.selected_segment_index = 0
             else:
                 self.selected_segment_index = None
                 self.selected_parameter_key = None
        except Exception as e:
            self.set_feedback(f"Error deleting segment: {e}", is_error=True)


    # --- Drawing Methods ---

    def draw(self, screen_surface, midi_status=None):
        """Draws the song editor interface or the rename interface."""
        # --- Draw Rename Interface if active ---
        if self.is_renaming_song:
            self._draw_rename_interface(screen_surface)
        # --- Draw Normal Edit Interface ---
        elif not self.current_song:
            no_song_text = "No Song Loaded. Use File Manager."
            no_song_surf = self.font_large.render(no_song_text, True, WHITE)
            no_song_rect = no_song_surf.get_rect(center=(screen_surface.get_width() // 2, screen_surface.get_height() // 2))
            screen_surface.blit(no_song_surf, no_song_rect)
        else:
            # Draw Song Title
            title_text = f"Editing: {self.current_song.name}"
            rename_cc = getattr(mappings, 'RENAME_SONG_CC', None)
            if rename_cc:
                 title_text += f" (Rename: CC {rename_cc})"

            title_surf = self.font_large.render(title_text, True, WHITE)
            title_rect = title_surf.get_rect(midtop=(screen_surface.get_width() // 2, TOP_MARGIN))
            screen_surface.blit(title_surf, title_rect)

            # Draw Segment List
            self._draw_segment_list(screen_surface, title_rect.bottom + 15)

            # Draw Parameter Details
            self._draw_parameter_details(screen_surface, title_rect.bottom + 15)

        # --- Draw Feedback Message (Common to both modes) ---
        self._draw_feedback(screen_surface)


    def _draw_segment_list(self, surface, start_y):
        """Draws the list of segments on the left."""
        list_rect = pygame.Rect(LEFT_MARGIN, start_y, SEGMENT_LIST_WIDTH, surface.get_height() - start_y - 40)
        y_offset = list_rect.top + 5

        header_surf = self.font.render("Segments:", True, WHITE)
        surface.blit(header_surf, (list_rect.left + 5, y_offset))
        y_offset += LINE_HEIGHT + 5

        if not self.current_song or not self.current_song.segments:
            no_segments_surf = self.font_small.render("No segments yet.", True, WHITE)
            surface.blit(no_segments_surf, (list_rect.left + 10, y_offset))
            return

        max_items_to_display = list_rect.height // LINE_HEIGHT
        start_index = 0 # TODO: Implement scrolling

        for i, segment in enumerate(self.current_song.segments[start_index:]):
            if i >= max_items_to_display:
                more_surf = self.font_small.render("...", True, WHITE)
                surface.blit(more_surf, (list_rect.left + 5, y_offset))
                break

            display_index = start_index + i
            seg_text = f"{display_index + 1}: T={segment.tempo:.0f} L={segment.loop_length} R={segment.repetitions}"
            is_selected = (display_index == self.selected_segment_index)
            color = HIGHLIGHT_COLOR if is_selected else WHITE

            seg_surf = self.font_small.render(seg_text, True, color)
            seg_rect = seg_surf.get_rect(topleft=(list_rect.left + 10, y_offset))

            if is_selected:
                 sel_rect = pygame.Rect(list_rect.left, y_offset - 2, list_rect.width, LINE_HEIGHT)
                 pygame.draw.rect(surface, (40, 80, 40), sel_rect)

            surface.blit(seg_surf, seg_rect)
            y_offset += LINE_HEIGHT


    def _draw_parameter_details(self, surface, start_y):
        """Draws the parameters of the selected segment on the right."""
        param_rect = pygame.Rect(PARAM_AREA_X, start_y, surface.get_width() - PARAM_AREA_X - LEFT_MARGIN, surface.get_height() - start_y - 40)
        y_offset = param_rect.top + 5

        if self.selected_segment_index is None or not self.current_song:
            no_selection_surf = self.font.render("Select a segment", True, WHITE)
            surface.blit(no_selection_surf, (param_rect.left + 5, y_offset))
            return

        try:
            segment = self.current_song.get_segment(self.selected_segment_index)
        except IndexError:
             no_selection_surf = self.font.render("Segment not found?", True, ERROR_COLOR)
             surface.blit(no_selection_surf, (param_rect.left + 5, y_offset))
             return

        header_text = f"Segment {self.selected_segment_index + 1} Parameters:"
        header_surf = self.font.render(header_text, True, WHITE)
        surface.blit(header_surf, (param_rect.left + 5, y_offset))
        y_offset += LINE_HEIGHT + 5

        for key in self.parameter_keys:
            display_name = self.parameter_display_names.get(key, key)
            try:
                value = getattr(segment, key)
                if isinstance(value, bool): value_str = "YES" if value else "NO"
                elif isinstance(value, float): value_str = f"{value:.1f}"
                else: value_str = str(value)

                param_text = f"{display_name}: {value_str}"
                is_selected = (key == self.selected_parameter_key)
                color = HIGHLIGHT_COLOR if is_selected else PARAM_COLOR

                param_surf = self.font.render(param_text, True, color)
                param_draw_rect = param_surf.get_rect(topleft=(param_rect.left + PARAM_INDENT, y_offset))

                if is_selected:
                    sel_rect = pygame.Rect(param_rect.left, y_offset - 2, param_rect.width, LINE_HEIGHT)
                    pygame.draw.rect(surface, (40, 80, 40), sel_rect)

                surface.blit(param_surf, param_draw_rect)
                y_offset += LINE_HEIGHT

            except AttributeError:
                error_surf = self.font_small.render(f"Error: Param '{key}' not found", True, ERROR_COLOR)
                surface.blit(error_surf, (param_rect.left + PARAM_INDENT, y_offset))
                y_offset += LINE_HEIGHT


    def _draw_feedback(self, surface):
        """Draws the feedback message at the bottom."""
        if self.feedback_message:
            message, timestamp, color = self.feedback_message
            feedback_surf = self.font.render(message, True, color)
            feedback_rect = feedback_surf.get_rect(center=(surface.get_width() // 2, surface.get_height() - 25))
            bg_rect = feedback_rect.inflate(10, 5)
            pygame.draw.rect(surface, BLACK, bg_rect)
            pygame.draw.rect(surface, color, bg_rect, 1)
            surface.blit(feedback_surf, feedback_rect)

    # --- NEW: Drawing method for Rename Interface ---
    def _draw_rename_interface(self, surface):
        """Draws the dedicated interface for renaming the song."""
        if not self.song_renamer_instance: return

        rename_info = self.song_renamer_instance.get_display_info()
        mode = rename_info['mode']
        title_with_caret = rename_info['title_with_caret']
        keyboard_layout = rename_info['keyboard_layout']
        k_row, k_col = rename_info['keyboard_cursor']

        # Draw Title Being Edited
        title_text = f"Rename: {title_with_caret}"
        title_surf = self.font_large.render(title_text, True, WHITE)
        title_rect = title_surf.get_rect(midtop=(surface.get_width() // 2, TOP_MARGIN + 10))
        if title_rect.width > surface.get_width() - 20: # Basic clipping
             title_rect.width = surface.get_width() - 20
             title_rect.centerx = surface.get_width() // 2
        surface.blit(title_surf, title_rect)

        # Draw Instructions
        instr_y = title_rect.bottom + 10
        yes_cc = getattr(mappings, 'YES_NAV_CC', '?')
        no_cc = getattr(mappings, 'NO_NAV_CC', '?')
        save_cc = getattr(mappings, 'SAVE_SONG_CC', '?')
        cancel_cc = getattr(mappings, 'DELETE_SEGMENT_CC', '?') # Using DELETE as cancel

        if mode == RenameMode.CARET:
            instr_text = f"Arrows: Move | {no_cc}: Backspace | {yes_cc}: Keyboard"
            instr2_text = f"{save_cc}: Confirm | {cancel_cc}: Cancel"
        elif mode == RenameMode.KEYBOARD:
            instr_text = f"Arrows: Select | {yes_cc}: Insert Char"
            instr2_text = f"{no_cc}: Back to Caret"

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
            keyboard_line_height = LINE_HEIGHT

            for r_idx, row_str in enumerate(keyboard_layout):
                row_y = keyboard_y + (r_idx * keyboard_line_height)
                row_width = self.font.size(row_str)[0]
                row_start_x = (surface.get_width() - row_width) // 2

                if r_idx == k_row:
                    # Highlight selected character
                    if row_str and 0 <= k_col < len(row_str): # Check validity
                        pre_char = row_str[:k_col]
                        char = row_str[k_col]
                        post_char = row_str[k_col+1:]

                        pre_surf = self.font.render(pre_char, True, WHITE)
                        char_surf = self.font.render(char, True, BLACK)
                        post_surf = self.font.render(post_char, True, WHITE)

                        pre_rect = pre_surf.get_rect(topleft=(row_start_x, row_y))
                        char_width, char_height = self.font.size(char)
                        char_bg_rect = pygame.Rect(pre_rect.right, row_y - 2, char_width + 4, keyboard_line_height)
                        pygame.draw.rect(surface, HIGHLIGHT_COLOR, char_bg_rect)
                        char_rect = char_surf.get_rect(center=char_bg_rect.center)
                        post_rect = post_surf.get_rect(topleft=(char_bg_rect.right, row_y))

                        surface.blit(pre_surf, pre_rect)
                        surface.blit(char_surf, char_rect)
                        surface.blit(post_surf, post_rect)
                    else: # Draw row normally if cursor is invalid
                         row_surf = self.font.render(row_str, True, RED) # Indicate error
                         row_rect = row_surf.get_rect(topleft=(row_start_x, row_y))
                         surface.blit(row_surf, row_rect)
                else:
                    # Draw normal row
                    row_surf = self.font.render(row_str, True, WHITE)
                    row_rect = row_surf.get_rect(topleft=(row_start_x, row_y))
                    surface.blit(row_surf, row_rect)

    # --- End of Drawing Methods ---

