# emsys/ui/song_edit_screen.py
# -*- coding: utf-8 -*-
"""
Screen for viewing and editing Song objects. Includes renaming functionality via widget.
Uses column-based navigation (Segments <-> Parameters).
"""
import pygame
import time
from typing import List, Optional, Tuple, Any
from enum import Enum, auto

# Core components
from .base_screen import BaseScreen
from ..core.song import Song, Segment
from ..core.song import (MIN_TEMPO, MAX_TEMPO, MIN_RAMP, MAX_RAMP,
                         MIN_LOOP_LENGTH, MAX_LOOP_LENGTH, MIN_REPETITIONS,
                         MAX_REPETITIONS, MIN_PROGRAM_MSG, MAX_PROGRAM_MSG)
# Utilities and Config
from ..utils import file_io # Import the file I/O utilities
from ..config import settings, mappings

# --- Import the TextInputWidget ---
from .widgets import TextInputWidget, TextInputStatus
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
FOCUS_BORDER_COLOR = BLUE # Color for the border around the focused column

# Define layout constants
LEFT_MARGIN = 15
TOP_MARGIN = 15
LINE_HEIGHT = 25
PARAM_INDENT = 30
SEGMENT_LIST_WIDTH = 180 # Width for the segment list area
PARAM_AREA_X = LEFT_MARGIN + SEGMENT_LIST_WIDTH + 15 # Start X for parameter details
COLUMN_BORDER_WIDTH = 2 # Width of the focus border

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

# --- Define Focus Columns ---
class FocusColumn(Enum):
    SEGMENT_LIST = auto()
    PARAMETER_DETAILS = auto()
# ---------------------------

class SongEditScreen(BaseScreen):
    """Screen for editing song structure and segment parameters."""

    def __init__(self, app_ref):
        """Initialize the song editing screen."""
        super().__init__(app_ref)
        # Define additional fonts needed
        self.font_large = pygame.font.Font(None, 48)  # Larger font for titles
        self.font_small = pygame.font.Font(None, 24)  # Smaller font for detailed info

        self.current_song: Optional[Song] = None
        self.selected_segment_index: Optional[int] = None
        self.selected_parameter_key: Optional[str] = None
        self.feedback_message: Optional[Tuple[str, float, Tuple[int, int, int]]] = None # (message, timestamp, color) - Added color
        self.feedback_duration: float = 2.0 # seconds

        # --- Add instance of TextInputWidget ---
        self.text_input_widget = TextInputWidget(app_ref)
        # ---------------------------------------

        # --- Add state for column focus ---
        self.focused_column: FocusColumn = FocusColumn.SEGMENT_LIST
        # ---------------------------------

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
            # If no segment is selected or index is invalid, select the first one
            if self.selected_segment_index is None or self.selected_segment_index >= len(self.current_song.segments):
                self.selected_segment_index = 0
            # If no parameter is selected or invalid, select the first one
            if not self.parameter_keys:
                self.selected_parameter_key = None
            elif self.selected_parameter_key not in self.parameter_keys:
                self.selected_parameter_key = self.parameter_keys[0]
        else:
            self.selected_segment_index = None
            self.selected_parameter_key = None

        # --- Reset text input widget state on init ---
        self.text_input_widget.cancel()
        # ---------------------------------------------
        # --- Reset focus state on init ---
        self.focused_column = FocusColumn.SEGMENT_LIST
        # ---------------------------------
        self.clear_feedback() # Clear any old feedback

    def cleanup(self):
        """Called when the screen becomes inactive."""
        super().cleanup()
        print(f"{self.__class__.__name__} is being deactivated.")
        # --- Ensure text input widget is cleared on exit ---
        self.text_input_widget.cancel()
        # --------------------------------------------------
        # --- Reset focus state on cleanup ---
        self.focused_column = FocusColumn.SEGMENT_LIST
        # ----------------------------------
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
        print(f"SongEditScreen received CC: {cc} | Focus: {self.focused_column} | TextInput Active: {self.text_input_widget.is_active}")

        # --- Handle Text Input Mode FIRST ---
        if self.text_input_widget.is_active:
            status = self.text_input_widget.handle_input(cc)
            if status == TextInputStatus.CONFIRMED:
                self._confirm_song_rename() # Call the confirmation logic
            elif status == TextInputStatus.CANCELLED:
                self._cancel_song_rename() # Call the cancellation logic
            # If ACTIVE or ERROR, the widget handles drawing, we just wait
            return # Don't process other actions while text input is active
        # ----------------------------------

        # --- Normal Edit Mode Handling (Column-Based) ---

        # Navigation - Behavior depends on focused column
        if cc == mappings.DOWN_NAV_CC:
            if self.focused_column == FocusColumn.SEGMENT_LIST:
                self._change_selected_segment(1)
            elif self.focused_column == FocusColumn.PARAMETER_DETAILS:
                self._change_selected_parameter_vertically(1)
        elif cc == mappings.UP_NAV_CC:
            if self.focused_column == FocusColumn.SEGMENT_LIST:
                self._change_selected_segment(-1)
            elif self.focused_column == FocusColumn.PARAMETER_DETAILS:
                self._change_selected_parameter_vertically(-1)
        elif cc == mappings.RIGHT_NAV_CC:
            self._navigate_focus(1) # Move focus right
        elif cc == mappings.LEFT_NAV_CC:
            self._navigate_focus(-1) # Move focus left

        # Value Modification (Only if Parameter column is focused)
        elif cc == mappings.YES_NAV_CC: # Increment
            self._modify_selected_parameter(1)
        elif cc == mappings.NO_NAV_CC: # Decrement
            self._modify_selected_parameter(-1)

        # Actions (Generally independent of focus, but act on selection)
        elif cc == mappings.SAVE_SONG_CC:
            self._save_current_song()
        elif cc == mappings.ADD_SEGMENT_CC:
            self._add_new_segment()
        elif cc == mappings.DELETE_SEGMENT_CC:
            self._delete_selected_segment()
        elif cc == mappings.RENAME_SONG_CC: # CC 85
             self._start_song_rename()

    # --- NEW: Methods using TextInputWidget ---
    def _start_song_rename(self):
        """Initiates the song renaming process using the widget."""
        if self.current_song:
            self.text_input_widget.start(self.current_song.name, prompt="Rename Song")
            self.clear_feedback() # Clear other feedback
            print("Starting song rename mode via widget.")
            self.set_feedback("Renaming Song...", duration=1.0) # Brief indicator
        else:
            self.set_feedback("No song loaded to rename", is_error=True)

    def _confirm_song_rename(self):
        """Confirms the rename, updates the song, and saves."""
        if not self.text_input_widget.is_active or not self.current_song:
            self.text_input_widget.cancel() # Ensure widget is inactive
            return

        new_name = self.text_input_widget.get_text()
        if new_name is None: # Should not happen if CONFIRMED, but safety check
             self.set_feedback("Error getting new name from widget.", is_error=True)
             self.text_input_widget.cancel()
             return

        new_name = new_name.strip()
        old_name = self.current_song.name

        if not new_name:
            # Widget returned CONFIRMED but text is empty. Keep widget active? Or cancel?
            # Let's cancel and show error. User can try again.
            self.set_feedback("Song name cannot be empty. Rename cancelled.", is_error=True)
            self.text_input_widget.cancel()
            return

        if new_name == old_name:
            self.set_feedback("Name unchanged. Exiting rename.")
            self.text_input_widget.cancel()
            return

        print(f"Attempting to rename song from '{old_name}' to '{new_name}'")

        # --- File Renaming Logic ---
        if not hasattr(file_io, 'rename_song'):
             self.set_feedback("Error: File renaming function not implemented!", is_error=True)
             self.text_input_widget.cancel() # Cancel rename process
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
                # This is tricky - file renamed but content save failed.
                # The in-memory song has the new name. Attempting to save again might work.
                # Or should we try to rename back? Let's report error for now.
                self.set_feedback(f"Renamed file, but failed to save content for '{new_name}'", is_error=True)

            # Exit rename mode on successful rename
            self.text_input_widget.cancel()

        else:
            # file_io.rename_song failed (e.g., file exists, permissions)
            # file_io.rename_song should print the specific error
            self.set_feedback(f"Failed to rename file (see console)", is_error=True)
            # Keep the widget active so the user can try a different name or cancel.
            # No, let's cancel on failure to avoid inconsistent state. User can retry.
            self.text_input_widget.cancel()


    def _cancel_song_rename(self):
        """Cancels the renaming process initiated by the widget."""
        # The widget handles its own deactivation in handle_input -> cancel()
        # We just need to provide feedback.
        self.set_feedback("Rename cancelled.")
        print("Cancelled song rename mode.")
        # Ensure widget is inactive, though it should be already
        self.text_input_widget.cancel()

    # --- End of Renaming Methods ---


    # --- Internal Helper Methods for Actions (Modified for Focus) ---

    def _navigate_focus(self, direction: int):
        """Change the focused column."""
        if self.text_input_widget.is_active: return # Prevent action during text input

        if direction > 0: # Move Right
            if self.focused_column == FocusColumn.SEGMENT_LIST:
                # Check if navigation to parameters is possible
                if self.current_song and self.current_song.segments and self.selected_segment_index is not None and self.parameter_keys:
                    self.focused_column = FocusColumn.PARAMETER_DETAILS
                    # Ensure a parameter is selected (select first if needed)
                    if self.selected_parameter_key not in self.parameter_keys:
                        self.selected_parameter_key = self.parameter_keys[0]
                    self.clear_feedback()
                    print("Focus moved to Parameters")
                else:
                    self.set_feedback("Cannot focus parameters (no segment/params?)", is_error=True)
            # else: Already in the rightmost column

        elif direction < 0: # Move Left
            if self.focused_column == FocusColumn.PARAMETER_DETAILS:
                self.focused_column = FocusColumn.SEGMENT_LIST
                self.clear_feedback()
                print("Focus moved to Segments")
            # else: Already in the leftmost column

    def _change_selected_segment(self, direction: int):
        """Move segment selection up or down (only when segment list is focused)."""
        if self.text_input_widget.is_active: return # Prevent action during text input
        if self.focused_column != FocusColumn.SEGMENT_LIST: return # Only act if focused

        if not self.current_song or not self.current_song.segments:
            self.set_feedback("No segments to select", is_error=True)
            return

        num_segments = len(self.current_song.segments)
        if self.selected_segment_index is None:
            self.selected_segment_index = 0
        else:
            new_index = (self.selected_segment_index + direction) % num_segments
            # Handle wrap-around explicitly if needed, or rely on modulo
            self.selected_segment_index = new_index

        # Preserve the currently selected parameter when changing segments
        # Only reset if there's no selected parameter or it's not in the parameter list
        if not self.selected_parameter_key or (self.parameter_keys and self.selected_parameter_key not in self.parameter_keys):
            if self.parameter_keys:
                self.selected_parameter_key = self.parameter_keys[0]
            else:
                self.selected_parameter_key = None
        self.clear_feedback()


    def _change_selected_parameter_vertically(self, direction: int):
        """Move parameter selection up or down (only when parameter details are focused)."""
        if self.text_input_widget.is_active: return # Prevent action during text input
        if self.focused_column != FocusColumn.PARAMETER_DETAILS: return # Only act if focused

        if self.selected_segment_index is None or not self.parameter_keys:
            self.set_feedback("No parameters to select", is_error=True)
            return

        # Ensure a parameter is currently selected
        if self.selected_parameter_key is None:
             if self.parameter_keys:
                 self.selected_parameter_key = self.parameter_keys[0]
             else:
                 return # No parameters available

        try:
            current_param_index = self.parameter_keys.index(self.selected_parameter_key)
            next_param_index = (current_param_index + direction) % len(self.parameter_keys)
            self.selected_parameter_key = self.parameter_keys[next_param_index]
            self.clear_feedback()
        except (ValueError, AttributeError):
            # Fallback if current key isn't found (shouldn't happen ideally)
            self.selected_parameter_key = self.parameter_keys[0] if self.parameter_keys else None


    def _modify_selected_parameter(self, direction: int):
        """Increment or decrement the value of the selected parameter (only if parameter details are focused)."""
        if self.text_input_widget.is_active: return # Prevent action during text input
        # --- Add focus check ---
        if self.focused_column != FocusColumn.PARAMETER_DETAILS:
            self.set_feedback("Focus parameters to modify (Right Arrow)", is_error=True)
            return
        # -----------------------
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
                # Toggle boolean with either direction
                new_value = not current_value
            elif isinstance(current_value, int):
                new_value = current_value + direction * step
                # Apply constraints
                if key in ('program_message_1', 'program_message_2'):
                    new_value = max(MIN_PROGRAM_MSG, min(MAX_PROGRAM_MSG, new_value))
                elif key == 'loop_length':
                    new_value = max(MIN_LOOP_LENGTH, min(MAX_LOOP_LENGTH, new_value))
                elif key == 'repetitions':
                    new_value = max(MIN_REPETITIONS, min(MAX_REPETITIONS, new_value))
            elif isinstance(current_value, float):
                new_value = current_value + direction * step
                # Apply constraints
                if key == 'tempo':
                    new_value = max(MIN_TEMPO, min(MAX_TEMPO, new_value))
                elif key == 'tempo_ramp':
                    new_value = max(MIN_RAMP, min(MAX_RAMP, new_value))
                new_value = round(new_value, 2) # Keep precision reasonable
            else:
                self.set_feedback(f"Cannot modify type {type(current_value)}", is_error=True)
                return

            # Update the song data
            self.current_song.update_segment(self.selected_segment_index, **{key: new_value})

            # Provide feedback
            display_name = self.parameter_display_names.get(key, key)
            value_display = "YES" if isinstance(new_value, bool) and new_value else "NO" if isinstance(new_value, bool) else new_value
            self.set_feedback(f"{display_name}: {value_display}")

        except (IndexError, AttributeError, TypeError, ValueError) as e:
            self.set_feedback(f"Error modifying value: {e}", is_error=True)


    def _save_current_song(self):
        """Save the current song state to a file."""
        if self.text_input_widget.is_active: return # Prevent action during text input
        if self.current_song:
            if file_io.save_song(self.current_song):
                self.set_feedback(f"Song '{self.current_song.name}' saved.")
            else:
                self.set_feedback(f"Failed to save song '{self.current_song.name}'", is_error=True)
        else:
            self.set_feedback("No song loaded to save", is_error=True)


    def _add_new_segment(self):
        """Add a new segment with default values after the selected one."""
        if self.text_input_widget.is_active: return # Prevent action during text input
        if not self.current_song:
            self.set_feedback("Load a song first", is_error=True)
            return

        new_segment = Segment() # Create a default segment
        insert_index = (self.selected_segment_index + 1) if self.selected_segment_index is not None else len(self.current_song.segments)

        try:
            self.current_song.add_segment(new_segment, index=insert_index)
            # Select the newly added segment
            self.selected_segment_index = insert_index
            # Reset parameter selection for the new segment
            if self.parameter_keys:
                 self.selected_parameter_key = self.parameter_keys[0]
            else:
                 self.selected_parameter_key = None
            # Set focus back to segment list after adding
            self.focused_column = FocusColumn.SEGMENT_LIST
            self.set_feedback(f"Added segment {insert_index + 1}")
        except Exception as e:
            self.set_feedback(f"Error adding segment: {e}", is_error=True)


    def _delete_selected_segment(self):
        """Delete the currently selected segment."""
        if self.text_input_widget.is_active: return # Prevent action during text input
        # --- Allow deletion only if segment list is focused? Or based on selection? Let's allow based on selection ---
        # if self.focused_column != FocusColumn.SEGMENT_LIST:
        #     self.set_feedback("Focus segment list to delete (Left Arrow)", is_error=True)
        #     return
        # ----------------------------------------------------------------------------------------------------------
        if self.selected_segment_index is None or not self.current_song or not self.current_song.segments:
            self.set_feedback("No segment selected to delete", is_error=True)
            return
            
        # Check if this is the last segment and prevent deletion if it is
        if len(self.current_song.segments) <= 1:
            self.set_feedback("Cannot delete the last segment", is_error=True)
            return

        try:
            deleted_index_for_feedback = self.selected_segment_index + 1
            self.current_song.remove_segment(self.selected_segment_index)
            num_segments = len(self.current_song.segments)

            # Adjust selection after deletion
            if num_segments == 0:
                self.selected_segment_index = None
                self.selected_parameter_key = None
            elif self.selected_segment_index >= num_segments:
                # If last segment was deleted, select the new last one
                self.selected_segment_index = num_segments - 1
            # Else: index remains valid, keep it selected

            # Reset parameter selection if segment index changed or became invalid
            if self.selected_segment_index is not None and self.parameter_keys:
                 self.selected_parameter_key = self.parameter_keys[0]
            else:
                 self.selected_parameter_key = None

            # Ensure focus is on segment list after deletion
            self.focused_column = FocusColumn.SEGMENT_LIST
            self.set_feedback(f"Deleted segment {deleted_index_for_feedback}")

        except IndexError:
             self.set_feedback("Error deleting segment (index out of range?)", is_error=True)
             # Reset selection safely
             if self.current_song and self.current_song.segments:
                 self.selected_segment_index = 0
                 if self.parameter_keys: self.selected_parameter_key = self.parameter_keys[0]
                 else: self.selected_parameter_key = None
             else:
                 self.selected_segment_index = None
                 self.selected_parameter_key = None
             self.focused_column = FocusColumn.SEGMENT_LIST # Reset focus
        except Exception as e:
            self.set_feedback(f"Error deleting segment: {e}", is_error=True)


    # --- Drawing Methods (Modified for Focus) ---

    def draw(self, screen_surface, midi_status=None):
        """Draws the song editor interface or the text input interface."""
        # --- Draw Text Input Interface if active ---
        if self.text_input_widget.is_active:
            # Optionally clear background first if widget doesn't
            # screen_surface.fill(BLACK)
            self.text_input_widget.draw(screen_surface)
        # --- Draw Normal Edit Interface ---
        elif not self.current_song:
            # Display message if no song is loaded
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

            # Calculate available height for columns
            content_start_y = title_rect.bottom + 15
            content_height = screen_surface.get_height() - content_start_y - 40 # Reserve space for feedback

            # Draw Segment List
            self._draw_segment_list(screen_surface, content_start_y, content_height)

            # Draw Parameter Details
            self._draw_parameter_details(screen_surface, content_start_y, content_height)

        # --- Draw Feedback Message (Common to both modes) ---
        # Only draw feedback if text input is NOT active, or allow widget to draw its own?
        # Let's draw feedback always, it appears at the bottom anyway.
        self._draw_feedback(screen_surface)


    def _draw_segment_list(self, surface, start_y, height):
        """Draws the list of segments on the left, indicating focus."""
        list_rect = pygame.Rect(LEFT_MARGIN, start_y, SEGMENT_LIST_WIDTH, height)
        y_offset = list_rect.top + 5

        # --- Draw Focus Border ---
        is_focused = (self.focused_column == FocusColumn.SEGMENT_LIST)
        if is_focused:
            pygame.draw.rect(surface, FOCUS_BORDER_COLOR, list_rect, COLUMN_BORDER_WIDTH)
        # -------------------------

        header_color = FOCUS_BORDER_COLOR if is_focused else WHITE
        header_surf = self.font.render("Segments:", True, header_color)
        surface.blit(header_surf, (list_rect.left + 5, y_offset))
        y_offset += LINE_HEIGHT + 5

        if not self.current_song or not self.current_song.segments:
            no_segments_surf = self.font_small.render("No segments yet.", True, WHITE)
            surface.blit(no_segments_surf, (list_rect.left + 10, y_offset))
            return

        # Basic scrolling logic (can be enhanced later)
        max_items_to_display = (list_rect.height - (y_offset - list_rect.top)) // LINE_HEIGHT
        start_index = 0
        if self.selected_segment_index is not None and self.selected_segment_index >= max_items_to_display:
            start_index = self.selected_segment_index - max_items_to_display + 1

        for i, segment in enumerate(self.current_song.segments[start_index:]):
            current_y = y_offset + (i * LINE_HEIGHT)
            if current_y + LINE_HEIGHT > list_rect.bottom: # Stop drawing if exceeding bounds
                more_surf = self.font_small.render("...", True, WHITE)
                surface.blit(more_surf, (list_rect.left + 5, current_y))
                break

            display_index = start_index + i
            # Format segment info concisely
            seg_text = f"{display_index + 1}: T{segment.tempo:.0f} L{segment.loop_length} R{segment.repetitions}"
            is_selected = (display_index == self.selected_segment_index)
            color = HIGHLIGHT_COLOR if is_selected else WHITE

            seg_surf = self.font_small.render(seg_text, True, color)
            seg_rect = seg_surf.get_rect(topleft=(list_rect.left + 10, current_y))

            # Draw selection highlight for the item
            if is_selected:
                 # Use a slightly different highlight if the column is NOT focused? Optional.
                 sel_bg_color = (40, 80, 40) # Standard green highlight
                 sel_rect = pygame.Rect(list_rect.left + (COLUMN_BORDER_WIDTH if is_focused else 0), current_y - 2,
                                        list_rect.width - (2 * COLUMN_BORDER_WIDTH if is_focused else 0), LINE_HEIGHT)
                 pygame.draw.rect(surface, sel_bg_color, sel_rect)

            surface.blit(seg_surf, seg_rect)


    def _draw_parameter_details(self, surface, start_y, height):
        """Draws the parameters of the selected segment on the right, indicating focus."""
        param_rect = pygame.Rect(PARAM_AREA_X, start_y, surface.get_width() - PARAM_AREA_X - LEFT_MARGIN, height)
        y_offset = param_rect.top + 5

        # --- Draw Focus Border ---
        is_focused = (self.focused_column == FocusColumn.PARAMETER_DETAILS)
        if is_focused:
            pygame.draw.rect(surface, FOCUS_BORDER_COLOR, param_rect, COLUMN_BORDER_WIDTH)
        # -------------------------

        if self.selected_segment_index is None or not self.current_song:
            no_selection_surf = self.font.render("Select segment (<-)", True, WHITE)
            surface.blit(no_selection_surf, (param_rect.left + 5, y_offset))
            return

        try:
            segment = self.current_song.get_segment(self.selected_segment_index)
        except IndexError:
             no_selection_surf = self.font.render("Segment not found?", True, ERROR_COLOR)
             surface.blit(no_selection_surf, (param_rect.left + 5, y_offset))
             return

        header_color = FOCUS_BORDER_COLOR if is_focused else WHITE
        header_text = f"Segment {self.selected_segment_index + 1} Params:"
        header_surf = self.font.render(header_text, True, header_color)
        surface.blit(header_surf, (param_rect.left + 5, y_offset))
        y_offset += LINE_HEIGHT + 5

        # Basic scrolling for parameters (can be enhanced)
        max_items_to_display = (param_rect.height - (y_offset - param_rect.top)) // LINE_HEIGHT
        start_param_index = 0
        if self.selected_parameter_key and self.parameter_keys:
            try:
                current_param_idx = self.parameter_keys.index(self.selected_parameter_key)
                if current_param_idx >= max_items_to_display:
                    start_param_index = current_param_idx - max_items_to_display + 1
            except ValueError:
                pass # Keep start_index 0 if key not found

        for i, key in enumerate(self.parameter_keys[start_param_index:]):
            current_y = y_offset + (i * LINE_HEIGHT)
            if current_y + LINE_HEIGHT > param_rect.bottom: # Stop drawing if exceeding bounds
                more_surf = self.font_small.render("...", True, WHITE)
                surface.blit(more_surf, (param_rect.left + PARAM_INDENT, current_y))
                break

            display_name = self.parameter_display_names.get(key, key)
            try:
                value = getattr(segment, key)
                # Format value nicely
                if isinstance(value, bool): value_str = "YES" if value else "NO"
                elif isinstance(value, float): value_str = f"{value:.1f}" # Show one decimal for floats
                else: value_str = str(value)

                param_text = f"{display_name}: {value_str}"
                is_selected = (key == self.selected_parameter_key)
                color = HIGHLIGHT_COLOR if is_selected else PARAM_COLOR

                param_surf = self.font.render(param_text, True, color)
                param_draw_rect = param_surf.get_rect(topleft=(param_rect.left + PARAM_INDENT, current_y))

                # Draw selection highlight for the item
                if is_selected:
                    sel_bg_color = (40, 80, 40) # Standard green highlight
                    sel_rect = pygame.Rect(param_rect.left + (COLUMN_BORDER_WIDTH if is_focused else 0), current_y - 2,
                                           param_rect.width - (2 * COLUMN_BORDER_WIDTH if is_focused else 0), LINE_HEIGHT)
                    pygame.draw.rect(surface, sel_bg_color, sel_rect)

                surface.blit(param_surf, param_draw_rect)

            except AttributeError:
                error_surf = self.font_small.render(f"Error: Param '{key}' not found", True, ERROR_COLOR)
                surface.blit(error_surf, (param_rect.left + PARAM_INDENT, current_y))


    def _draw_feedback(self, surface):
        """Draws the feedback message at the bottom."""
        if self.feedback_message:
            message, timestamp, color = self.feedback_message
            feedback_surf = self.font.render(message, True, color)
            feedback_rect = feedback_surf.get_rect(center=(surface.get_width() // 2, surface.get_height() - 25))
            # Add a background for better visibility
            bg_rect = feedback_rect.inflate(10, 5)
            pygame.draw.rect(surface, BLACK, bg_rect) # Black background
            pygame.draw.rect(surface, color, bg_rect, 1) # Colored border matching text
            surface.blit(feedback_surf, feedback_rect)

    # --- REMOVED: _draw_rename_interface - Handled by widget ---

    # --- End of Drawing Methods ---
