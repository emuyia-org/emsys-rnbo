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
import math # Needed for ceiling function and curve calculations

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
# --- Import the specific Fader CC ---
from ..config.mappings import FADER_SELECT_CC
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

# --- Define LED Curve Types ---
class CurveType(Enum):
    LINEAR = auto()
    LOG = auto()      # Moderate curve (e.g., for Tempo)
    STRONG_LOG = auto() # Harsher curve (e.g., for Ramp, Length, Repeats)
# ----------------------------

# --- Curve Scaling Functions ---
# These take a normalized value (0.0 to 1.0) and return a scaled normalized value (0.0 to 1.0)
def scale_linear(norm_val: float) -> float:
    """Linear scaling (no change)."""
    return norm_val

def scale_log(norm_val: float, exponent: float = 0.5) -> float:
    """Logarithmic-like scaling. Grows faster at the start. exponent < 1.0"""
    # Using power function: x^(1/N) where N > 1. Default is sqrt(x).
    if norm_val <= 0: return 0.0
    return norm_val ** exponent

def scale_strong_log(norm_val: float, exponent: float = 0.33) -> float:
    """Stronger logarithmic-like scaling. Grows even faster at the start. exponent << 1.0"""
    # Default is cube root(x).
    if norm_val <= 0: return 0.0
    return norm_val ** exponent
# -----------------------------

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

        # --- Map Parameters to LED Curve Types ---
        self.parameter_led_curves: Dict[str, CurveType] = {
            'program_message_1': CurveType.LINEAR,
            'program_message_2': CurveType.LINEAR,
            'tempo': CurveType.LOG, # Moderate curve for tempo
            'tempo_ramp': CurveType.STRONG_LOG, # Harsher curve
            'loop_length': CurveType.LOG, # Harsher curve
            'repetitions': CurveType.LOG, # Harsher curve
            'automatic_transport_interrupt': CurveType.LINEAR # Boolean is handled separately anyway
        }
        # -----------------------------------------

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
            # Select first parameter by default if available
            self.selected_parameter_key = self.parameter_keys[0] if self.parameter_keys else None
        else:
            self.selected_segment_index = None
            self.selected_parameter_key = None

        self.text_input_widget.cancel()
        self.focused_column = FocusColumn.SEGMENT_LIST
        self.clear_feedback()
        self._update_encoder_led() # <<< RE-ENABLED

    def cleanup(self):
        """Called when the screen becomes inactive."""
        super().cleanup()
        print(f"{self.__class__.__name__} is being deactivated.")
        self.text_input_widget.cancel()
        # Optionally turn off the LED when leaving the screen
        # if hasattr(self.app, 'send_midi_cc'):
        #     self.app.send_midi_cc(control=16, value=0, channel=15) # CC 16 (Knob 8), Value 0 (Off), Channel 16
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
        if msg.type != 'control_change':
             return

        cc = msg.control
        value = msg.value

        # <<< --- REMOVE VERY EARLY DEBUG PRINT FOR KNOB B8 --- >>>
        # if cc == mappings.KNOB_B8_CC:
        #     print(f"--- KNOB B8 (CC {cc}) RAW VALUE RECEIVED: {value} ---")
        # <<< --- END EARLY DEBUG PRINT REMOVAL --- >>>

        # --- Handle Text Input Mode FIRST ---
        if self.text_input_widget.is_active:
            # Text input only responds to button presses (value 127)
            if value != 127:
                return # Ignore non-presses during text input
            status = self.text_input_widget.handle_input(cc)
            if status == TextInputStatus.CONFIRMED:
                self._confirm_song_rename() # Call the confirmation logic
            elif status == TextInputStatus.CANCELLED:
                self._cancel_song_rename() # Call the cancellation logic
            # If ACTIVE or ERROR, the widget handles drawing, we just wait
            return # Don't process other actions while text input is active
        # ----------------------------------

        # --- Handle Universal Encoder Parameter Adjustment (KNOB_B8_CC) ---
        if cc == mappings.KNOB_B8_CC:
            direction = 0
            if 1 <= value <= 63:
                direction = 1
            elif 65 <= value <= 127:
                direction = -1

            if direction != 0:
                self._modify_parameter_via_encoder(direction)
            return # Encoder handled

        # --- Handle Fader Selection (CC 65) ---
        if cc == FADER_SELECT_CC:
            if not self.current_song: return # No song loaded

            reversed_value = 127 - value

            if self.focused_column == FocusColumn.SEGMENT_LIST:
                if not self.current_song.segments: return # No segments

                num_segments = len(self.current_song.segments)
                target_index = int((reversed_value / 128.0) * num_segments)
                target_index = max(0, min(num_segments - 1, target_index))

                current_selected = self.selected_segment_index
                # print(f"[Fader Debug Seg] Value={value} (Rev={reversed_value}), NumSeg={num_segments} -> TargetIdx={target_index}, CurrentSel={current_selected}")

                if target_index != current_selected:
                    # print(f"          Updating segment selection: {current_selected} -> {target_index}")
                    self.selected_segment_index = target_index
                    # Basic scroll handling (can be improved like in SongManagerScreen)
                    # This just ensures the first parameter is selected when segment changes via fader
                    if self.parameter_keys:
                        self.selected_parameter_key = self.parameter_keys[0]
                    else:
                        self.selected_parameter_key = None
                    self.clear_feedback()

            elif self.focused_column == FocusColumn.PARAMETER_DETAILS:
                if self.selected_segment_index is None or not self.parameter_keys:
                    return # No segment selected or no parameters defined

                num_params = len(self.parameter_keys)
                target_param_index = int((reversed_value / 128.0) * num_params)
                target_param_index = max(0, min(num_params - 1, target_param_index))

                target_key = self.parameter_keys[target_param_index]
                current_key = self.selected_parameter_key

                # print(f"[Fader Debug Param] Value={value} (Rev={reversed_value}), NumParam={num_params} -> TargetIdx={target_param_index} ('{target_key}'), CurrentKey='{current_key}'")

                if target_key != current_key:
                    # print(f"          Updating parameter selection: '{current_key}' -> '{target_key}'")
                    self.selected_parameter_key = target_key
                    self.clear_feedback()

            return # Fader handled, don't process as button press below
        # --- End Fader Handling ---

        # --- Normal Edit Mode Handling (Button Presses Only) ---
        # Process remaining CCs only if they are button presses (value 127)
        if value != 127:
            return

        # --- Now handle button presses based on focus ---
        # (Existing button logic follows, unchanged)
        # ...

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
        elif cc == mappings.SAVE_CC:
            self._save_current_song()
        elif cc == mappings.CREATE_CC:
            self._add_new_segment()
        elif cc == mappings.DELETE_CC:
            self._delete_selected_segment()
        elif cc == mappings.RENAME_CC: # CC 85
             self._start_song_rename()

    # --- Renaming Methods ---
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
        # Check if widget is active *now* - it should be if CONFIRMED was returned correctly
        if not self.text_input_widget.is_active or not self.current_song:
            # This path should ideally not be hit if CONFIRMED was returned correctly
            self.text_input_widget.cancel() # Ensure widget is inactive anyway
            return

        new_name = self.text_input_widget.get_text()
        if new_name is None: # Should not happen if CONFIRMED, but safety check
             self.set_feedback("Error getting new name from widget.", is_error=True)
             self.text_input_widget.cancel() # Cancel on error
             return

        new_name = new_name.strip()
        old_name = self.current_song.name

        if not new_name:
            self.set_feedback("Song name cannot be empty. Rename cancelled.", is_error=True)
            self.text_input_widget.cancel() # Cancel on validation failure
            return

        if new_name == old_name:
            self.set_feedback("Name unchanged. Exiting rename.")
            self.text_input_widget.cancel() # Cancel if name is the same
            return

        print(f"Attempting to rename song from '{old_name}' to '{new_name}'")

        # --- File Renaming Logic ---
        if not hasattr(file_io, 'rename_song'):
             self.set_feedback("Error: File renaming function not implemented!", is_error=True)
             self.text_input_widget.cancel() # Cancel on missing function
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
                # self.current_song.dirty should be False now due to save_song
            else:
                self.set_feedback(f"Renamed file, but failed to save content for '{new_name}'", is_error=True)
                # If save failed, the song might still be considered dirty if changes were made before rename
                # save_song doesn't reset the flag on failure.

            # Exit rename mode on successful rename (or save failure after rename)
            self.text_input_widget.cancel() # Cancel after attempting save

        else:
            # file_io.rename_song failed
            self.set_feedback(f"Failed to rename file (see console)", is_error=True)
            # Cancel on rename failure
            self.text_input_widget.cancel()

    def _cancel_song_rename(self):
        """Cancels the renaming process initiated by the widget."""
        # Widget should already be inactive if CANCELLED status was returned,
        # but call cancel() again for safety.
        self.set_feedback("Rename cancelled.")
        print("Cancelled song rename mode.")
        self.text_input_widget.cancel()

    # --- Internal Helper Methods ---

    def _navigate_focus(self, direction: int):
        """Change the focused column."""
        if self.text_input_widget.is_active: return # Prevent action during text input

        old_focus = self.focused_column # Store old focus for feedback LED update

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

        if old_focus != self.focused_column:
            self.clear_feedback()
            self._update_encoder_led() # <<< RE-ENABLED

    def _change_selected_segment(self, direction: int):
        """Move segment selection up or down."""
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
        self._update_encoder_led() # <<< RE-ENABLED

    def _change_selected_parameter_vertically(self, direction: int):
        """Move parameter selection up or down."""
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
            new_key = self.parameter_keys[next_param_index]

            if new_key != self.selected_parameter_key:
                self.selected_parameter_key = new_key
                self.clear_feedback()
                self._update_encoder_led() # <<< RE-ENABLED

        except (ValueError, AttributeError):
            # Fallback if current key isn't found (shouldn't happen ideally)
            self.selected_parameter_key = self.parameter_keys[0] if self.parameter_keys else None
            self.clear_feedback()
            self._update_encoder_led() # <<< RE-ENABLED (fallback)

    def _modify_selected_parameter(self, direction: int):
        """Increment or decrement the value of the selected parameter (only if parameter details are focused)."""
        if self.text_input_widget.is_active: return # Prevent action during text input
        # --- Add focus check ---
        if self.focused_column != FocusColumn.PARAMETER_DETAILS:
            self.set_feedback("Focus parameters to modify (Right Arrow)", is_error=True)
            return
        # -----------------------
        if self.selected_segment_index is None or self.selected_parameter_key is None:
            # <<< --- ADDED DETAIL --- >>>
            print("Debug: Modification aborted - No segment or parameter selected.")
            self.set_feedback("Select segment and parameter first", is_error=True)
            return
        if not self.current_song:
            # <<< --- ADDED DETAIL --- >>>
            print("Debug: Modification aborted - No current song.")
            return

        try:
            segment = self.current_song.get_segment(self.selected_segment_index)
            key = self.selected_parameter_key
            current_value = getattr(segment, key)
            step = PARAM_STEPS.get(key, 1)
            original_value = current_value

            # <<< --- ADD DEBUG PRINT 5 --- >>>
            print(f"Debug: Modifying '{key}'. Current={current_value}, Step={step}")

            new_value: Any
            min_val, max_val = None, None # Define min/max constraints
            if key == 'program_message_1' or key == 'program_message_2':
                min_val, max_val = MIN_PROGRAM_MSG, MAX_PROGRAM_MSG
            elif key == 'tempo':
                min_val, max_val = MIN_TEMPO, MAX_TEMPO
            elif key == 'tempo_ramp':
                min_val, max_val = MIN_RAMP, MAX_RAMP
            elif key == 'loop_length':
                min_val, max_val = MIN_LOOP_LENGTH, MAX_LOOP_LENGTH
            elif key == 'repetitions':
                min_val, max_val = MIN_REPETITIONS, MAX_REPETITIONS

            # Calculate new value based on type
            if isinstance(current_value, bool):
                new_value = not current_value if direction != 0 else current_value
            elif isinstance(current_value, (int, float)): # Combine int and float logic
                new_value = current_value + (direction * step)
                # Clamp integer/float value
                if min_val is not None: new_value = max(min_val, new_value)
                if max_val is not None: new_value = min(max_val, new_value)
                if isinstance(new_value, float):
                    new_value = round(new_value, 2) # Round floats
            else:
                self.set_feedback(f"Cannot modify type {type(current_value)}", is_error=True)
                return

            # <<< --- ADD DEBUG PRINT 6 --- >>>
            print(f"Debug: Calculated New Value={new_value} (Original={original_value})")

            # <<< --- CRITICAL CHANGE: Track if we hit minimum/maximum bounds --- >>>
            hit_boundary = False
            if direction < 0 and min_val is not None and new_value == min_val:
                hit_boundary = True
                print(f"Debug: Hit minimum bound ({min_val})")
            elif direction > 0 and max_val is not None and new_value == max_val:
                hit_boundary = True
                print(f"Debug: Hit maximum bound ({max_val})")

            if new_value != original_value:
                # Value did change, update as normal
                print("Debug: Value changed. Updating song object.")
                setattr(segment, key, new_value)
                self.current_song.dirty = True
                display_name = self.parameter_display_names.get(key, key)
                self.set_feedback(f"{display_name}: {new_value}", duration=0.75)
                self._update_encoder_led()  # Update LED for changed value
            else:
                # Value didn't change, but we might need to refresh the LED
                print("Debug: Value did not change (e.g., at limit or step issue).")
                
                # <<< --- CRITICAL CHANGE: Always update LED when at limits --- >>>
                if hit_boundary:
                    # Ensure LED is updated when we hit a boundary, even if value didn't change
                    print("Debug: Updating LED even though value didn't change (at boundary)")
                    self._update_encoder_led()
                    # Optional: Show brief feedback that we've hit the limit
                    display_name = self.parameter_display_names.get(key, key)
                    limit_type = "min" if direction < 0 else "max"
                    self.set_feedback(f"{display_name}: at {limit_type}", duration=0.5)

        except (IndexError, AttributeError, TypeError, ValueError) as e:
            print(f"Debug: Error during modification: {e}")
            self.set_feedback(f"Error modifying value: {e}", is_error=True)
            print(f"Error in _perform_parameter_modification: {e}")


    def _save_current_song(self):
        """Save the current song state to a file."""
        if self.text_input_widget.is_active: return # Prevent action during text input
        if self.current_song:
            if file_io.save_song(self.current_song):
                self.set_feedback(f"Song '{self.current_song.name}' saved.")
                # self.current_song.dirty is reset by save_song
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
            # self.current_song.dirty is set by add_segment
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
            # self.current_song.dirty is set by remove_segment
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


    # --- Drawing Methods ---

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
            no_song_text = "No Song Loaded."
            no_song_surf = self.font_large.render(no_song_text, True, WHITE)
            no_song_rect = no_song_surf.get_rect(center=(screen_surface.get_width() // 2, screen_surface.get_height() // 2))
            screen_surface.blit(no_song_surf, no_song_rect)
        else:
            # Draw Song Title
            title_text = f"Editing: {self.current_song.name}"
            # Replace CC number with button name
            title_text += ""

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

    # --- UPDATED: Method for LED Feedback ---
    def _update_encoder_led(self):
        """Calculates and sends MIDI CC to update KNOB_B8_CC LED ring (1-13 LEDs). Applies scaling curves."""
        # Check if the app has the send method and output port is ready
        if not hasattr(self.app, 'send_midi_cc') or not self.app.midi_output_port:
            return # MIDI output not ready

        led_value = 1  # Default to first LED

        # Determine the value only if a valid segment and parameter are selected
        if self.selected_segment_index is not None and self.selected_parameter_key is not None and self.current_song:
            try:
                segment = self.current_song.get_segment(self.selected_segment_index)
                key = self.selected_parameter_key
                current_value = getattr(segment, key)

                min_val, max_val = None, None
                # Get min/max for normalization
                if key == 'program_message_1' or key == 'program_message_2':
                    min_val, max_val = MIN_PROGRAM_MSG, MAX_PROGRAM_MSG
                elif key == 'tempo':
                    min_val, max_val = MIN_TEMPO, MAX_TEMPO
                elif key == 'tempo_ramp':
                    min_val, max_val = MIN_RAMP, MAX_RAMP
                elif key == 'loop_length':
                    min_val, max_val = MIN_LOOP_LENGTH, MAX_LOOP_LENGTH
                elif key == 'repetitions':
                    min_val, max_val = MIN_REPETITIONS, MAX_REPETITIONS
                elif key == 'automatic_transport_interrupt':
                    # Use LED 1 and 13 for boolean (never completely off)
                    led_value = 13 if current_value else 1
                    min_val, max_val = 0, 1  # Set dummy range to skip normalization/scaling

                # Normalize and scale if we have a valid range
                if min_val is not None and max_val is not None and max_val > min_val:
                    # Normalize current_value to 0.0 - 1.0
                    normalized = (current_value - min_val) / (max_val - min_val)
                    # Clamp just in case value is slightly outside range
                    normalized = max(0.0, min(1.0, normalized))

                    # --- Apply Scaling Curve ---
                    curve_type = self.parameter_led_curves.get(key, CurveType.LINEAR) # Default to linear
                    scaled_normalized = normalized # Start with linear assumption

                    if curve_type == CurveType.LOG:
                        scaled_normalized = scale_log(normalized)
                    elif curve_type == CurveType.STRONG_LOG:
                        scaled_normalized = scale_strong_log(normalized)
                    # No need for explicit linear case, it's the default

                    # --- Map Scaled Value to 1-13 LED Range ---
                    # Use the scaled_normalized value now
                    if scaled_normalized <= 0.001: # Handle floating point near zero
                        led_value = 1  # Always show at least LED 1
                    else:
                        # Map 0.0-1.0 to 1-13 range (1 + scaled_normalized*12)
                        led_value = 1 + math.floor(scaled_normalized * 12)
                        # Ensure max value is 13, accounting for potential float imprecision near 1.0
                        if scaled_normalized >= 0.999:
                            led_value = 13

            except (IndexError, AttributeError, TypeError, ValueError) as e:
                print(f"Error calculating LED value for {self.selected_parameter_key}: {e}")
                led_value = 1  # Default to first LED on error

        # Send the MIDI CC message for Knob 8 LED
        # Knob 8 LED is CC 16 (9 + 7)
        # Channel is 16 (index 15)
        # Value is 1-13 (never 0)
        self.app.send_midi_cc(control=16, value=int(led_value), channel=15)

    def _modify_parameter_via_encoder(self, direction: int):
        """
        Increment/decrement selected parameter value (used by ENCODER).
        Works regardless of focus.
        """
        # <<< --- REMOVE DEBUG PRINT 3 --- >>>
        # print(f"Debug: _modify_parameter_via_encoder called with direction: {direction}")
        if self.text_input_widget.is_active: return
        self._perform_parameter_modification(direction)

    def _perform_parameter_modification(self, direction: int):
        """Core logic to modify the selected parameter's value."""
        # <<< --- REMOVE DEBUG PRINT --- >>>
        # print(f"Debug: _perform_parameter_modification: Dir={direction}, SegIdx={self.selected_segment_index}, ParamKey={self.selected_parameter_key}")

        if self.selected_segment_index is None or self.selected_parameter_key is None:
            # print("Debug: Modification aborted - No segment or parameter selected.") # REMOVE
            self.set_feedback("Select segment and parameter first", is_error=True)
            return
        if not self.current_song:
            # print("Debug: Modification aborted - No current song.") # REMOVE
            return

        try:
            segment = self.current_song.get_segment(self.selected_segment_index)
            key = self.selected_parameter_key
            current_value = getattr(segment, key)
            step = PARAM_STEPS.get(key, 1)
            original_value = current_value

            # <<< --- REMOVE DEBUG PRINT --- >>>
            # print(f"Debug: Modifying '{key}'. Current={current_value}, Step={step}")

            new_value: Any
            min_val, max_val = None, None # Define min/max constraints
            # Get min/max constraints for this parameter
            if key == 'program_message_1' or key == 'program_message_2':
                min_val, max_val = MIN_PROGRAM_MSG, MAX_PROGRAM_MSG
            elif key == 'tempo':
                min_val, max_val = MIN_TEMPO, MAX_TEMPO
            elif key == 'tempo_ramp':
                min_val, max_val = MIN_RAMP, MAX_RAMP
            elif key == 'loop_length':
                min_val, max_val = MIN_LOOP_LENGTH, MAX_LOOP_LENGTH
            elif key == 'repetitions':
                min_val, max_val = MIN_REPETITIONS, MAX_REPETITIONS

            # Calculate new value based on type
            if isinstance(current_value, bool):
                new_value = not current_value if direction != 0 else current_value
            elif isinstance(current_value, (int, float)): # Combine int and float logic
                new_value = current_value + (direction * step)
                # Clamp integer/float value
                if min_val is not None: new_value = max(min_val, new_value)
                if max_val is not None: new_value = min(max_val, new_value)
                if isinstance(new_value, float):
                    new_value = round(new_value, 2) # Round floats
            else:
                self.set_feedback(f"Cannot modify type {type(current_value)}", is_error=True)
                return

            # <<< --- REMOVE DEBUG PRINT --- >>>
            # print(f"Debug: Calculated New Value={new_value} (Original={original_value})")

            hit_boundary = False
            if direction < 0 and min_val is not None and new_value == min_val:
                hit_boundary = True
                # print(f"Debug: Hit minimum bound ({min_val})") # REMOVE
            elif direction > 0 and max_val is not None and new_value == max_val:
                hit_boundary = True
                # print(f"Debug: Hit maximum bound ({max_val})") # REMOVE

            if new_value != original_value:
                # print("Debug: Value changed. Updating song object.") # REMOVE
                setattr(segment, key, new_value)
                self.current_song.dirty = True
                display_name = self.parameter_display_names.get(key, key)
                self.set_feedback(f"{display_name}: {new_value}", duration=0.75)
                self._update_encoder_led()
            else:
                # print("Debug: Value did not change (e.g., at limit or step issue).") # REMOVE
                if hit_boundary:
                    # print("Debug: Updating LED even though value didn't change (at boundary)") # REMOVE
                    self._update_encoder_led()
                    display_name = self.parameter_display_names.get(key, key)
                    limit_type = "min" if direction < 0 else "max"
                    self.set_feedback(f"{display_name}: at {limit_type}", duration=0.5)

        except (IndexError, AttributeError, TypeError, ValueError) as e:
            # print(f"Debug: Error during modification: {e}") # REMOVE
            self.set_feedback(f"Error modifying value: {e}", is_error=True)
            print(f"Error in _perform_parameter_modification: {e}") # Keep this one? Optional.


# ... rest of the file ...
