# emsys/ui/song_edit_screen.py
# -*- coding: utf-8 -*-
"""
Screen for viewing and editing Song objects. Includes renaming functionality via widget.
Uses column-based navigation (Segments <-> Parameters).
"""
import pygame # Ensure pygame is imported if not already
import time # Ensure time is imported if not already
from typing import List, Optional, Tuple, Any, Dict
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
import math # <<< ADD THIS LINE if not already present

# --- Import the TextInputWidget and FocusColumn ---
from .widgets import TextInputWidget, TextInputStatus, FocusColumn # <<< Added FocusColumn
# ------------------------------------
from emsys.core.song import Segment # <<< Added for default values
from emsys.config.mappings import FADER_SELECT_CC, DELETE_CC # <<< Added DELETE_CC etc.
# --- Import colors from settings ---
from emsys.config.settings import ERROR_COLOR, FEEDBACK_COLOR, HIGHLIGHT_COLOR, BLACK, WHITE, GREY, FOCUS_BORDER_COLOR # <<< Use settings
# -----------------------------------

# Define layout constants
LEFT_MARGIN = 15
TOP_MARGIN = 15
LINE_HEIGHT = 36 # <<< Increased line height for larger fonts
PARAM_INDENT = 30
SEGMENT_LIST_WIDTH = 180 # Width for the segment list area
PARAM_AREA_X = LEFT_MARGIN + SEGMENT_LIST_WIDTH + 15 # Start X for parameter details
COLUMN_BORDER_WIDTH = 2 # Width of the focus border
LIST_TOP_PADDING = 10 # Padding above lists
FEEDBACK_AREA_HEIGHT = 40 # Space at the bottom for feedback

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

# --- Define LED Curve Types ---
# (Defined locally for now)
class CurveType(Enum):
    LINEAR = auto()
    LOG = auto()      # Moderate curve (e.g., for Tempo)
    STRONG_LOG = auto() # Harsher curve (e.g., for Ramp, Length, Repeats)
# ----------------------------

# --- Curve Scaling Function ---
# (Defined locally for now)
# --- REMOVED NEW scale_value_to_led ---
# def scale_value_to_led(value, min_val, max_val, curve: CurveType = CurveType.LINEAR) -> int:
#    ...

# --- ADDED OLD Curve Scaling Functions ---
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
        self.font_large = pygame.font.Font(None, 48)  # Larger font for titles (unchanged)
        self.font_small = pygame.font.Font(None, 32)  # <<< Increased font size for lists
        self.font = pygame.font.Font(None, 36) # <<< Increased standard font size

        self.current_song: Optional[Song] = None
        self.selected_segment_index: Optional[int] = None
        self.selected_parameter_key: Optional[str] = None
        self.feedback_message: Optional[Tuple[str, float, Tuple[int, int, int]]] = None
        self.feedback_duration: float = 2.0

        # --- Add instance of TextInputWidget ---
        self.text_input_widget = TextInputWidget(app_ref)
        # ---------------------------------------

        # --- Add state for column focus ---
        self.focused_column: FocusColumn = FocusColumn.SEGMENT_LIST
        # ---------------------------------

        # --- Add state for exit confirmation prompt ---
        self.exit_prompt_active: bool = False
        # ------------------------------------------

        # --- Add scroll offsets ---
        self.segment_scroll_offset: int = 0
        self.parameter_scroll_offset: int = 0
        # --------------------------

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
        # --- Reset exit prompt state ---
        self.exit_prompt_active = False
        # -----------------------------
        # --- Reset scroll offsets ---
        self.segment_scroll_offset = 0
        self.parameter_scroll_offset = 0
        # --------------------------
        self.clear_feedback()
        self._update_encoder_led()

    def cleanup(self):
        """Called when the screen becomes inactive."""
        super().cleanup()
        print(f"{self.__class__.__name__} is being deactivated.")
        self.text_input_widget.cancel()
        self.exit_prompt_active = False # Ensure prompt is cleared
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
             return # <<< Added return

        cc = msg.control
        value = msg.value

        # --- Handle Text Input Mode FIRST ---
        if self.text_input_widget.is_active:
            # Text input only responds to button presses (value 127)
            if value != 127:
                return # Ignore non-presses during text input
            status = self.text_input_widget.handle_input(cc)
            if status == TextInputStatus.CONFIRMED:
                # Renaming is handled by SongManagerScreen, this screen doesn't confirm renames
                # self._confirm_song_rename() # <<< REMOVED
                pass
            elif status == TextInputStatus.CANCELLED:
                # self._cancel_song_rename() # <<< REMOVED
                self.text_input_widget.cancel() # Just ensure it's cancelled
            # If ACTIVE or ERROR, the widget handles drawing, we just wait
            return # Don't process other actions while text input is active
        # ----------------------------------

        # --- ADDED: Handle Exit Confirmation Prompt ---
        if self.exit_prompt_active:
            if value == 127: # Button press
                if cc == mappings.SAVE_CC: # Save & Exit
                    self._save_and_exit()
                elif cc == mappings.DELETE_CC: # Discard & Exit
                    self._discard_and_exit()
                elif cc == mappings.NO_NAV_CC: # Cancel Exit
                    self._cancel_exit()
            return # <<< Prevent further processing
        # --------------------------------------------

        # --- Handle Universal Encoder Parameter Adjustment (KNOB_B8_CC) ---
        if cc == mappings.KNOB_B8_CC:
            direction = 0
            if 1 <= value <= 63:
                direction = 1
            elif 65 <= value <= 127:
                direction = -1

            if direction != 0:
                self._modify_parameter_via_encoder(direction)
            return # <<< Added return

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
                    # --- ADDED: Scroll Handling for Segments ---
                    max_visible = self._get_max_visible_segments()
                    if self.selected_segment_index >= self.segment_scroll_offset + max_visible:
                        print(f"          [Fader Scroll Seg] Scrolling DOWN: Offset {self.segment_scroll_offset} -> {self.selected_segment_index - max_visible + 1}") # DEBUG
                        self.segment_scroll_offset = self.selected_segment_index - max_visible + 1
                    elif self.selected_segment_index < self.segment_scroll_offset:
                        print(f"          [Fader Scroll Seg] Scrolling UP: Offset {self.segment_scroll_offset} -> {self.selected_segment_index}") # DEBUG
                        self.segment_scroll_offset = self.selected_segment_index
                    # --- END ADDED ---
                    # --- MODIFIED: Preserve parameter selection when segment changes via fader ---
                    # Only reset if there's no selected parameter or it's not in the parameter list
                    if not self.selected_parameter_key or (self.parameter_keys and self.selected_parameter_key not in self.parameter_keys):
                        if self.parameter_keys:
                            self.selected_parameter_key = self.parameter_keys[0]
                            self.parameter_scroll_offset = 0 # Reset scroll if parameter is reset
                        else:
                            self.selected_parameter_key = None
                            self.parameter_scroll_offset = 0
                    # --- END MODIFICATION ---
                    self.clear_feedback()
                    self._update_encoder_led() # Update LED as focus might implicitly change

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
                    # --- ADDED: Scroll Handling for Parameters ---
                    max_visible = self._get_max_visible_parameters()
                    current_param_index = self.parameter_keys.index(self.selected_parameter_key) # Get index of the new key
                    if current_param_index >= self.parameter_scroll_offset + max_visible:
                        print(f"          [Fader Scroll Param] Scrolling DOWN: Offset {self.parameter_scroll_offset} -> {current_param_index - max_visible + 1}") # DEBUG
                        self.parameter_scroll_offset = current_param_index - max_visible + 1
                    elif current_param_index < self.parameter_scroll_offset:
                        print(f"          [Fader Scroll Param] Scrolling UP: Offset {self.parameter_scroll_offset} -> {current_param_index}") # DEBUG
                        self.parameter_scroll_offset = current_param_index
                    # --- END ADDED ---
                    self.clear_feedback()
                    self._update_encoder_led() # Update LED for new parameter

            return # Fader handled, don't process as button press below
        # --- End Fader Handling ---

        # --- Normal Edit Mode Handling (Button Presses Only) ---
        # Process remaining CCs only if they are button presses (value 127)
        if value != 127:
            return # <<< Added return

        # --- REMOVE RENAME_CC Handling ---
        # if cc == mappings.RENAME_CC:
        #     # Renaming is handled by SongManagerScreen
        #     return
        # --- End RENAME_CC Removal ---

        # --- Handle DELETE_CC based on focus ---
        if cc == DELETE_CC:
            if self.focused_column == FocusColumn.SEGMENT_LIST:
                self._delete_current_segment() # Direct delete for segments
            elif self.focused_column == FocusColumn.PARAMETER_DETAILS:
                # Maybe implement parameter reset here later?
                self.set_feedback("DELETE not implemented for parameters yet.") # <<< Keep this or change to reset?
                # self._reset_or_copy_parameter() # <<< Or use DELETE to reset?
            return # <<< Prevent further processing of DELETE
        # ---------------------------------------

        # --- Now handle other button presses based on focus ---
        # Navigation
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

        # --- MODIFIED: YES/NO for value modification OR boolean toggle ---
        elif cc == mappings.YES_NAV_CC:
            if self.focused_column == FocusColumn.PARAMETER_DETAILS:
                if self.selected_parameter_key == 'automatic_transport_interrupt':
                    self._toggle_boolean_parameter() # Toggle boolean with YES
                else:
                    self._modify_selected_parameter(1) # Increment other params with YES
            else:
                 self.set_feedback("YES action not defined here.")
        elif cc == mappings.NO_NAV_CC:
            if self.focused_column == FocusColumn.PARAMETER_DETAILS:
                 if self.selected_parameter_key == 'automatic_transport_interrupt':
                     self._toggle_boolean_parameter() # Also allow toggle with NO? Or just YES? Let's keep NO for decrement/reset
                     # self.set_feedback("Use YES to toggle Auto Pause.")
                     self._modify_selected_parameter(-1) # Decrement other params with NO
                 else:
                     self._modify_selected_parameter(-1) # Decrement other params with NO
            else:
                self.set_feedback("NO action not defined here.")
        # --- END MODIFICATION ---

        # Actions (Generally independent of focus, but act on selection)
        elif cc == mappings.SAVE_CC:
            self._save_current_song()
        elif cc == mappings.CREATE_CC:
            self._add_new_segment()
        # DELETE is handled above based on focus
        # RENAME is removed

    # --- Segment Deletion Method (Direct) ---
    def _delete_current_segment(self):
        """Performs the actual segment deletion directly."""
        if self.selected_segment_index is None or not self.current_song or not self.current_song.segments:
            self.set_feedback("No segment selected to delete", is_error=True)
            return

        try:
            index_to_delete = self.selected_segment_index
            num_segments_before = len(self.current_song.segments)

            removed_segment = self.current_song.remove_segment(index_to_delete)
            self.set_feedback(f"Deleted Segment {index_to_delete + 1}")

            num_segments_after = len(self.current_song.segments)

            # Adjust selection
            if num_segments_after == 0:
                # No segments left
                self.selected_segment_index = None
                self.selected_parameter_key = None
                self.focused_column = FocusColumn.SEGMENT_LIST # Reset focus
            else:
                # Select the segment that is now at the deleted index,
                # or the last segment if the deleted one was the last.
                self.selected_segment_index = min(index_to_delete, num_segments_after - 1)

            # Update LED if selection changed
            self._update_encoder_led()

        except IndexError:
            self.set_feedback("Error deleting segment (index out of bounds).", is_error=True)
            self._reset_selection_on_error()
        except Exception as e:
            self.set_feedback(f"Error deleting segment: {e}", is_error=True)
            print(f"Unexpected error during segment delete: {e}")

    def _reset_selection_on_error(self):
        """Resets selection state, e.g., after an index error."""
        if self.current_song and self.current_song.segments:
            self.selected_segment_index = 0
            self.selected_parameter_key = self.parameter_keys[0] if self.parameter_keys else None
        else:
            self.selected_segment_index = None
            self.selected_parameter_key = None
        self.focused_column = FocusColumn.SEGMENT_LIST
        self._update_encoder_led()

    # --- Parameter Reset/Copy Method ---
    def _reset_or_copy_parameter(self):
        """Resets the selected parameter to default or copies from the previous segment."""
        if (self.selected_segment_index is None or
                self.selected_parameter_key is None or
                not self.current_song or
                not self.current_song.segments):
            self.set_feedback("No parameter selected", is_error=True)
            return

        try:
            current_index = self.selected_segment_index
            key = self.selected_parameter_key
            current_segment = self.current_song.get_segment(current_index)
            current_value = getattr(current_segment, key)

            if current_index > 0:
                # Copy from previous segment
                prev_segment = self.current_song.get_segment(current_index - 1)
                prev_value = getattr(prev_segment, key)
                if prev_value != current_value:
                    # Use the song's update method which handles validation and dirty flag
                    self.current_song.update_segment(current_index, **{key: prev_value})
                    self.set_feedback(f"'{self.parameter_display_names.get(key, key)}' copied from previous")
                    self._update_encoder_led() # Update LED to reflect new value
                else:
                    self.set_feedback(f"Value already matches previous segment")

            else:
                # Reset to default
                default_segment = Segment() # Create a temporary default segment
                default_value = getattr(default_segment, key)
                if default_value != current_value:
                    # Use the song's update method
                    self.current_song.update_segment(current_index, **{key: default_value})
                    self.set_feedback(f"'{self.parameter_display_names.get(key, key)}' reset to default")
                    self._update_encoder_led() # Update LED to reflect new value
                else:
                     self.set_feedback(f"Value already at default")

        except IndexError:
            self.set_feedback("Segment index error.", is_error=True)
            self._reset_selection_on_error()
        except AttributeError:
            self.set_feedback(f"Parameter '{key}' error.", is_error=True)
        except Exception as e:
            self.set_feedback(f"Error resetting parameter: {e}", is_error=True)
            print(f"Unexpected error during parameter reset/copy: {e}")

    # --- Navigation Methods ---
    def _navigate_focus(self, direction: int):
        """Change focus between columns."""
        if direction > 0: # Move right
            if self.focused_column == FocusColumn.SEGMENT_LIST:
                self.focused_column = FocusColumn.PARAMETER_DETAILS
        elif direction < 0: # Move left
            if self.focused_column == FocusColumn.PARAMETER_DETAILS:
                self.focused_column = FocusColumn.SEGMENT_LIST

        self.clear_feedback()
        self._update_encoder_led() # Update LED based on new focus

    def _change_selected_segment(self, direction: int):
        """Change the selected segment index and handle scrolling."""
        if not self.current_song or not self.current_song.segments:
            self.selected_segment_index = None
            return

        num_segments = len(self.current_song.segments)
        if self.selected_segment_index is None:
            self.selected_segment_index = 0 if direction > 0 else num_segments - 1
        else:
            self.selected_segment_index = (self.selected_segment_index + direction + num_segments) % num_segments

        # --- Restore old behavior: Preserve parameter selection ---
        # Only reset if there's no selected parameter or it's not in the parameter list
        if not self.selected_parameter_key or (self.parameter_keys and self.selected_parameter_key not in self.parameter_keys):
            if self.parameter_keys:
                self.selected_parameter_key = self.parameter_keys[0]
                self.parameter_scroll_offset = 0 # Reset scroll if parameter is reset
            else:
                self.selected_parameter_key = None
                self.parameter_scroll_offset = 0
        # --- End restored behavior ---
        # Note: Parameter scroll offset is still reset if the parameter itself is reset,
        # but not if the parameter is preserved.

        # Adjust segment scroll offset
        max_visible = self._get_max_visible_segments()
        if self.selected_segment_index >= self.segment_scroll_offset + max_visible:
            self.segment_scroll_offset = self.selected_segment_index - max_visible + 1
        elif self.selected_segment_index < self.segment_scroll_offset:
            self.segment_scroll_offset = self.selected_segment_index

        self.clear_feedback()
        self._update_encoder_led() # Update LED

    def _change_selected_parameter_vertically(self, direction: int):
        """Change the selected parameter key and handle scrolling."""
        if self.selected_segment_index is None or not self.parameter_keys:
            self.selected_parameter_key = None
            return

        num_params = len(self.parameter_keys)
        if self.selected_parameter_key is None:
            current_param_index = -1 # Will become 0 or num_params - 1
        else:
            try:
                current_param_index = self.parameter_keys.index(self.selected_parameter_key)
            except ValueError:
                current_param_index = -1 # Fallback

        new_param_index = (current_param_index + direction + num_params) % num_params
        self.selected_parameter_key = self.parameter_keys[new_param_index]

        # Adjust parameter scroll offset
        max_visible = self._get_max_visible_parameters()
        if new_param_index >= self.parameter_scroll_offset + max_visible:
            self.parameter_scroll_offset = new_param_index - max_visible + 1
        elif new_param_index < self.parameter_scroll_offset:
            self.parameter_scroll_offset = new_param_index

        self.clear_feedback()
        self._update_encoder_led() # Update LED for the new parameter

    # --- Helper methods for calculating visible items ---
    def _get_max_visible_items(self, list_area_rect: pygame.Rect) -> int:
        """Calculate how many list items fit in a given rect."""
        available_height = list_area_rect.height - (2 * LIST_TOP_PADDING) # Padding top/bottom
        if available_height <= 0 or LINE_HEIGHT <= 0:
            return 0
        return available_height // LINE_HEIGHT

    def _get_max_visible_segments(self) -> int:
        """Calculate how many segment items fit."""
        # Define the rect based on layout constants
        list_area_top = self.title_rect.bottom + LIST_TOP_PADDING
        list_area_height = self.app.screen.get_height() - list_area_top - FEEDBACK_AREA_HEIGHT
        seg_list_rect = pygame.Rect(LEFT_MARGIN, list_area_top, SEGMENT_LIST_WIDTH, list_area_height)
        return self._get_max_visible_items(seg_list_rect)

    def _get_max_visible_parameters(self) -> int:
        """Calculate how many parameter items fit."""
        list_area_top = self.title_rect.bottom + LIST_TOP_PADDING
        list_area_height = self.app.screen.get_height() - list_area_top - FEEDBACK_AREA_HEIGHT
        param_list_rect = pygame.Rect(PARAM_AREA_X, list_area_top,
                                      self.app.screen.get_width() - PARAM_AREA_X - LEFT_MARGIN,
                                      list_area_height)
        return self._get_max_visible_items(param_list_rect)
    # ----------------------------------------------------

    # --- Drawing ---
    def draw(self, screen, midi_status=None):
        """Draw the song editing screen."""
        # --- Draw Text Input Interface if active ---
        if self.text_input_widget.is_active:
            self.text_input_widget.draw(screen)
            return # Don't draw anything else

        # --- Draw Exit Prompt if active ---
        elif self.exit_prompt_active:
            self._draw_normal_content(screen, midi_status) # Draw underneath
            self._draw_exit_prompt(screen)
        # --- Draw Normal Content ---
        else:
            self._draw_normal_content(screen, midi_status)
            # --- Draw Feedback ---
            self._draw_feedback(screen) # Only draw feedback if no prompt is active

    def _draw_normal_content(self, screen, midi_status=None):
        """Draws the main content of the song edit screen."""
        # Clear screen or assume it's cleared by main loop
        # screen.fill(BLACK)

        # Draw Title with Dirty Flag
        title_text = "Song Editor"
        if self.current_song:
            dirty_flag = "*" if self.current_song.dirty else ""
            title_text = f"Edit: {self.current_song.name}{dirty_flag}"

        title_surf = self.font_large.render(title_text, True, WHITE)
        self.title_rect = title_surf.get_rect(midtop=(screen.get_width() // 2, TOP_MARGIN))
        screen.blit(title_surf, self.title_rect)

        # Example placeholder text:
        placeholder_y = self.title_rect.bottom + LIST_TOP_PADDING # Use constant
        list_area_height = screen.get_height() - placeholder_y - FEEDBACK_AREA_HEIGHT # Use constant

        if self.current_song:
            song_name_surf = self.font.render(f"Editing: {self.current_song.name}", True, WHITE)
            screen.blit(song_name_surf, (20, placeholder_y))
            placeholder_y += 30 # Adjust spacing after song name

            # --- Draw Segment List Column ---
            seg_list_rect = pygame.Rect(LEFT_MARGIN, placeholder_y, SEGMENT_LIST_WIDTH, list_area_height)
            border_color = FOCUS_BORDER_COLOR if self.focused_column == FocusColumn.SEGMENT_LIST else WHITE
            pygame.draw.rect(screen, border_color, seg_list_rect, COLUMN_BORDER_WIDTH)

            if self.current_song.segments:
                max_visible_segments = self._get_max_visible_segments()
                num_segments = len(self.current_song.segments)

                # Ensure scroll offset is valid
                if self.segment_scroll_offset > num_segments - max_visible_segments:
                    self.segment_scroll_offset = max(0, num_segments - max_visible_segments)
                if self.segment_scroll_offset < 0: self.segment_scroll_offset = 0

                start_index = self.segment_scroll_offset
                end_index = min(start_index + max_visible_segments, num_segments)

                # Draw scroll up indicator
                if self.segment_scroll_offset > 0:
                    scroll_up_surf = self.font_small.render("^", True, WHITE)
                    scroll_up_rect = scroll_up_surf.get_rect(centerx=seg_list_rect.centerx, top=seg_list_rect.top + 2)
                    screen.blit(scroll_up_surf, scroll_up_rect)

                seg_text_y = seg_list_rect.top + LIST_TOP_PADDING # Start below indicator space

                for i in range(start_index, end_index):
                    seg = self.current_song.segments[i]
                    is_selected_segment = (i == self.selected_segment_index)
                    is_segment_column_focused = (self.focused_column == FocusColumn.SEGMENT_LIST)
                    color = HIGHLIGHT_COLOR if (is_selected_segment and is_segment_column_focused) else WHITE

                    # --- ADDED: Segment Dirty Flag ---
                    dirty_flag = "*" if seg.dirty else ""
                    # --- END ADDED ---

                    seg_text = f"{i + 1}{dirty_flag}" # Basic text, add dirty flag
                    seg_surf = self.font_small.render(seg_text, True, color)
                    seg_rect = seg_surf.get_rect(topleft=(seg_list_rect.left + 10, seg_text_y))

                    # Draw selection background if focused and selected
                    if is_selected_segment and is_segment_column_focused:
                        # Define background rect slightly smaller than the line height space
                        bg_rect = pygame.Rect(seg_list_rect.left + 2, seg_text_y - 2, seg_list_rect.width - 4, LINE_HEIGHT)
                        # Fill the background rectangle with GREY color
                        pygame.draw.rect(screen, GREY, bg_rect) # <<< Changed from border (width 1) to fill

                    screen.blit(seg_surf, seg_rect)
                    seg_text_y += LINE_HEIGHT

                # Draw scroll down indicator
                if end_index < num_segments:
                    scroll_down_surf = self.font_small.render("v", True, WHITE)
                    scroll_down_rect = scroll_down_surf.get_rect(centerx=seg_list_rect.centerx, bottom=seg_list_rect.bottom - 2)
                    screen.blit(scroll_down_surf, scroll_down_rect)
            else:
                # No segments text
                no_seg_surf = self.font_small.render("No Segments", True, WHITE)
                no_seg_rect = no_seg_surf.get_rect(center=seg_list_rect.center)
                screen.blit(no_seg_surf, no_seg_rect)


            # --- Draw Parameter Details Column ---
            param_detail_rect = pygame.Rect(PARAM_AREA_X, placeholder_y, screen.get_width() - PARAM_AREA_X - LEFT_MARGIN, list_area_height)
            border_color = FOCUS_BORDER_COLOR if self.focused_column == FocusColumn.PARAMETER_DETAILS else WHITE
            pygame.draw.rect(screen, border_color, param_detail_rect, COLUMN_BORDER_WIDTH)

            if self.selected_segment_index is not None and self.parameter_keys:
                try:
                    current_segment = self.current_song.get_segment(self.selected_segment_index) # Get current segment
                    max_visible_params = self._get_max_visible_parameters()
                    num_params = len(self.parameter_keys)

                    # Ensure scroll offset is valid
                    if self.parameter_scroll_offset > num_params - max_visible_params:
                        self.parameter_scroll_offset = max(0, num_params - max_visible_params)
                    if self.parameter_scroll_offset < 0: self.parameter_scroll_offset = 0

                    start_index = self.parameter_scroll_offset
                    end_index = min(start_index + max_visible_params, num_params)

                    param_end_index = min(self.parameter_scroll_offset + max_visible_params, len(self.parameter_keys))

                    # Draw scroll up indicator
                    if self.parameter_scroll_offset > 0:
                        scroll_up_surf = self.font_small.render("^", True, WHITE)
                        scroll_up_rect = scroll_up_surf.get_rect(centerx=param_detail_rect.centerx, top=param_detail_rect.top + 2)
                        screen.blit(scroll_up_surf, scroll_up_rect)

                    param_text_y = param_detail_rect.top + LIST_TOP_PADDING # Start below indicator space

                    for i in range(start_index, end_index):
                        param_key = self.parameter_keys[i]
                        display_name = self.parameter_display_names.get(param_key, param_key)
                        value = getattr(current_segment, param_key, "N/A")

                        # Format boolean values nicely
                        if isinstance(value, bool):
                            value_str = "ON" if value else "OFF"
                        else:
                            # Format floats nicely (e.g., tempo)
                            if isinstance(value, float):
                                value_str = f"{value:.1f}" # One decimal place
                            else:
                                value_str = str(value)

                        # <<< MODIFIED: Add asterisk if parameter is dirty >>>
                        param_dirty_flag = "*" if param_key in current_segment.dirty_params else ""
                        param_text = f"{param_dirty_flag}{display_name}: {value_str}"
                        # <<< END MODIFICATION >>>

                        # --- START MODIFICATION: Format Program Change values ---
                        if param_key in ['program_message_1', 'program_message_2']:
                            # Ensure value is an int before formatting
                            try:
                                value_str = value_to_elektron_format(int(value))
                            except (ValueError, TypeError):
                                value_str = "ERR" # Handle cases where value isn't a valid int
                        elif isinstance(value, bool):
                            value_str = "ON" if value else "OFF"
                        elif isinstance(value, float):
                            value_str = f"{value:.1f}" # One decimal place for floats
                        else:
                            value_str = str(value) # Default string conversion

                        # Add asterisk if parameter is dirty AFTER determining value_str
                        param_dirty_flag = "*" if param_key in current_segment.dirty_params else ""
                        param_text = f"{param_dirty_flag}{display_name}: {value_str}"
                        # --- END CORRECTED LOGIC ---

                        color = WHITE
                        bg_color = None
                        if param_key == self.selected_parameter_key:
                            color = BLACK # Text color when selected
                            bg_color = HIGHLIGHT_COLOR # Background color when selected

                        param_surf = self.font.render(param_text, True, color)
                        param_rect = param_surf.get_rect(topleft=(param_detail_rect.left + PARAM_INDENT, param_text_y))

                        if bg_color:
                            # Draw background highlight slightly larger than text
                            highlight_rect = param_rect.inflate(10, 2)
                            # Ensure highlight doesn't go outside the column bounds
                            highlight_rect.left = max(param_detail_rect.left + COLUMN_BORDER_WIDTH, highlight_rect.left)
                            highlight_rect.right = min(param_detail_rect.right - COLUMN_BORDER_WIDTH, highlight_rect.right)
                            pygame.draw.rect(screen, bg_color, highlight_rect)

                        screen.blit(param_surf, param_rect)
                        param_text_y += LINE_HEIGHT

                    # Draw scroll down indicator
                    if end_index < num_params:
                        scroll_down_surf = self.font_small.render("v", True, WHITE)
                        scroll_down_rect = scroll_down_surf.get_rect(centerx=param_detail_rect.centerx, bottom=param_detail_rect.bottom - 2)
                        screen.blit(scroll_down_surf, scroll_down_rect)

                except (IndexError, AttributeError) as e:
                    # Handle errors fetching segment or attribute
                    error_surf = self.font_small.render(f"Error: {e}", True, ERROR_COLOR)
                    error_rect = error_surf.get_rect(center=param_detail_rect.center)
                    screen.blit(error_surf, error_rect)
            elif self.selected_segment_index is None:
                 # No segment selected text
                 no_sel_surf = self.font_small.render("Select Segment", True, WHITE)
                 no_sel_rect = no_sel_surf.get_rect(center=param_detail_rect.center)
                 screen.blit(no_sel_surf, no_sel_rect)
            # else: No parameters defined (less likely)

        else:
            no_song_surf = self.font.render("No Song Loaded", True, ERROR_COLOR)
            no_song_rect = no_song_surf.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2))
            screen.blit(no_song_surf, no_song_rect)
        # --- End Placeholder ---

    def _draw_feedback(self, screen):
        """Draws the feedback message at the bottom."""
        if self.feedback_message:
            message, timestamp, color = self.feedback_message
            feedback_surf = self.font.render(message, True, color)
            feedback_rect = feedback_surf.get_rect(center=(screen.get_width() // 2, screen.get_height() - 25))
            # Optional: Add a background to make it stand out
            bg_rect = feedback_rect.inflate(10, 5)
            pygame.draw.rect(screen, BLACK, bg_rect)
            pygame.draw.rect(screen, color, bg_rect, 1) # Border
            screen.blit(feedback_surf, feedback_rect)

    # --- Helper to update encoder LED ---
    # This method handles sending MIDI CC to update the B8 encoder LED ring
    # based on the selected parameter's value and curve. It is called
    # automatically when focus changes, selection changes, or values are modified.
    # --- REVERTED TO OLD LOGIC ---
    def _update_encoder_led(self):
        """Calculates and sends MIDI CC to update KNOB_B8_CC LED ring (1-13 LEDs). Applies scaling curves."""
        # Check if the app has the send method and output port is ready
        if not hasattr(self.app, 'send_midi_cc') or not self.app.midi_output_port:
            # --- DEBUG PRINT (Optional) ---
            # print("[LED Debug] Skipping LED update: MIDI output not ready.")
            # --- END DEBUG ---
            return # MIDI output not ready

        led_value = 1  # Default to first LED (never 0)

        # --- DEBUG PRINT ---
        # print(f"[LED Debug] _update_encoder_led called. Focus: {self.focused_column.name}, SegIdx: {self.selected_segment_index}, ParamKey: {self.selected_parameter_key}")
        # --- END DEBUG ---

        # Determine the value only if a valid segment and parameter are selected
        # --- REMOVED FOCUS CHECK ---
        if (self.current_song and self.selected_segment_index is not None and
                self.selected_parameter_key is not None):
        # --- END REMOVED FOCUS CHECK ---

            # --- DEBUG PRINT ---
            # print(f"[LED Debug]   Conditions met. Proceeding to calculate LED value.")
            # --- END DEBUG ---
            try:
                segment = self.current_song.get_segment(self.selected_segment_index)
                key = self.selected_parameter_key
                current_value = getattr(segment, key)

                min_val, max_val, _ = self._get_param_range(key) # Use existing helper

                # Handle boolean separately (map to 1 and 13)
                if isinstance(current_value, bool):
                    led_value = 13 if current_value else 1
                    # --- DEBUG PRINT ---
                    # print(f"[LED Debug]   Boolean value: {current_value} -> LED: {led_value}")
                    # --- END DEBUG ---
                    min_val, max_val = 0, 1 # Set dummy range to skip normalization/scaling below

                # Normalize and scale if we have a valid range and it's not boolean
                if min_val is not None and max_val is not None and max_val > min_val and not isinstance(current_value, bool):
                    # Normalize current_value to 0.0 - 1.0
                    normalized = (current_value - min_val) / (max_val - min_val)
                    # Clamp just in case value is slightly outside range
                    normalized = max(0.0, min(1.0, normalized))
                    # --- DEBUG PRINT ---
                    # print(f"[LED Debug]   Value: {current_value}, Range: ({min_val}, {max_val}), Normalized: {normalized:.3f}")
                    # --- END DEBUG ---

                    # --- Apply Scaling Curve ---
                    curve_type = self.parameter_led_curves.get(key, CurveType.LINEAR) # Default to linear
                    scaled_normalized = normalized # Start with linear assumption

                    if curve_type == CurveType.LOG:
                        scaled_normalized = scale_log(normalized)
                        # --- DEBUG PRINT ---
                        # print(f"[LED Debug]   Applied LOG curve -> Scaled Norm: {scaled_normalized:.3f}")
                        # --- END DEBUG ---
                    elif curve_type == CurveType.STRONG_LOG:
                        scaled_normalized = scale_strong_log(normalized)
                        # --- DEBUG PRINT ---
                        # print(f"[LED Debug]   Applied STRONG_LOG curve -> Scaled Norm: {scaled_normalized:.3f}")
                        # --- END DEBUG ---
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
                    # --- DEBUG PRINT ---
                    # print(f"[LED Debug]   Mapped Scaled Norm to LED value: {led_value}")
                    # --- END DEBUG ---

            except (IndexError, AttributeError, TypeError, ValueError) as e:
                print(f"[LED Debug] Error calculating LED value for {self.selected_parameter_key}: {e}")
                led_value = 1  # Default to first LED on error

        else:
             # --- DEBUG PRINT ---
             # print(f"[LED Debug]   Conditions NOT met or turning LED 'off' (value 1).")
             # --- END DEBUG ---
             led_value = 1 # Set to 1 if conditions not met (e.g., no selection)


        # Send the MIDI CC message for Knob 8 LED
        # Knob 8 LED is CC 16 (9 + 7)
        # Channel is 16 (index 15)
        # Value is 1-13 (never 0)
        # --- DEBUG PRINT ---
        # print(f"[LED Debug]   Final LED value to send: {int(led_value)}")
        # --- END DEBUG ---
        self.app.send_midi_cc(control=16, value=int(led_value), channel=15)
    # --- END REVERT ---

    # --- Ensure _get_param_range exists (it should from previous steps) ---
    def _get_param_range(self, key: str) -> Tuple[float, float, float]:
        """Helper to get min, max, default for a parameter key."""
        # Use constants imported from core.song
        if key == 'tempo': return (MIN_TEMPO, MAX_TEMPO, 120.0)
        if key == 'tempo_ramp': return (MIN_RAMP, MAX_RAMP, 0.0)
        if key == 'loop_length': return (MIN_LOOP_LENGTH, MAX_LOOP_LENGTH, 16)
        if key == 'repetitions': return (MIN_REPETITIONS, MAX_REPETITIONS, 1)
        if key == 'program_message_1': return (MIN_PROGRAM_MSG, MAX_PROGRAM_MSG, 0)
        if key == 'program_message_2': return (MIN_PROGRAM_MSG, MAX_PROGRAM_MSG, 0)
        # Boolean handled separately in _update_encoder_led
        if key == 'automatic_transport_interrupt': return (0, 1, False) # Provide range for bool
        return (0, 1, 0) # Default fallback for unknown

    # --- Other methods like parameter modification, saving etc. ---
    def _modify_selected_parameter(self, direction: int):
        """Modify the selected parameter value using +/- buttons."""
        # --- REMOVED FOCUS CHECK ---
        if (self.selected_segment_index is None or
                self.selected_parameter_key is None or
                not self.current_song):
            # Optionally provide feedback if nothing is selected
            # self.set_feedback("Select segment/parameter first", is_error=True)
            return
        # --- END REMOVED FOCUS CHECK ---

        key = self.selected_parameter_key
        step = PARAM_STEPS.get(key, 1) # Default step is 1

        try:
            segment = self.current_song.get_segment(self.selected_segment_index)
            current_value = getattr(segment, key)
            original_value = current_value # Store original for feedback/LED check

            # Handle boolean toggle
            if isinstance(current_value, bool):
                new_value = not current_value
            elif isinstance(current_value, (int, float)):
                new_value = current_value + (step * direction)
                # Clamp to min/max if applicable
                min_val, max_val, _ = self._get_param_range(key)
                new_value = max(min_val, min(max_val, new_value))
                # Ensure integer types remain integer
                if isinstance(current_value, int):
                    new_value = int(round(new_value))
                # Round floats to avoid precision issues
                elif isinstance(new_value, float):
                    # Round based on step size? e.g., 0.5 step -> 1 decimal
                    decimals = 0
                    if isinstance(step, float) and step < 1:
                        decimals = len(str(step).split('.')[-1])
                    new_value = round(new_value, decimals if decimals > 0 else 2)

            else:
                # Cannot modify this type
                self.set_feedback(f"Cannot modify '{key}' type", is_error=True)
                return

            # Update the song only if the value actually changed
            if new_value != original_value:
                # Use the song's update method (handles validation and dirty flag)
                self.current_song.update_segment(self.selected_segment_index, **{key: new_value})
                self._update_encoder_led() # Update LED to reflect new value
                # Provide brief feedback on change
                display_name = self.parameter_display_names.get(key, key)
                
                # Determine value string for feedback, using Elektron format for program changes
                if key in ['program_message_1', 'program_message_2']:
                    try:
                        # Ensure it's an int before formatting for Elektron style
                        value_str = value_to_elektron_format(int(new_value))
                    except (ValueError, TypeError):
                        value_str = "ERR" # Handle unexpected type
                elif isinstance(new_value, bool):
                    value_str = "ON" if new_value else "OFF"
                else:
                    value_str = str(new_value) # Default string conversion for others
                
                self.set_feedback(f"{display_name}: {value_str}", duration=0.75)
            else:
                # Value didn't change (e.g., at limit) - maybe provide limit feedback
                min_val, max_val, _ = self._get_param_range(key)
                limit_hit = (direction < 0 and new_value == min_val) or \
                            (direction > 0 and new_value == max_val)
                if limit_hit and not isinstance(current_value, bool): # Don't show limit for bool toggle
                    display_name = self.parameter_display_names.get(key, key)
                    limit_type = "min" if direction < 0 else "max"
                    self.set_feedback(f"{display_name}: at {limit_type}", duration=0.5)
                    # Ensure LED is updated even if value didn't change (might already be correct)
                    self._update_encoder_led()


        except (IndexError, AttributeError, TypeError, ValueError) as e:
            self.set_feedback(f"Error modifying '{key}': {e}", is_error=True)
            print(f"Error in _modify_selected_parameter: {e}")

    def _modify_parameter_via_encoder(self, direction: int):
        """Modify the selected parameter value using the encoder."""
        # --- REMOVED FOCUS CHECK ---
        # This now directly calls the modification logic regardless of focus
        self._modify_selected_parameter(direction)
        # --- END REMOVED FOCUS CHECK ---

    def _save_current_song(self):
        """Saves the current song to disk and clears dirty flags."""
        if not self.current_song:
            self.set_feedback("No song loaded to save", is_error=True)
            return False # <<< Return status

        # Check if the song is actually dirty before saving
        if not self.current_song.dirty:
            self.set_feedback(f"'{self.current_song.name}' has no changes to save.")
            return True # <<< Return success (nothing needed saving)

        self.set_feedback(f"Saving '{self.current_song.name}'...")
        pygame.display.flip() # Show feedback immediately

        if file_io.save_song(self.current_song):
            self.set_feedback(f"Saved '{self.current_song.name}' successfully.")
            # Explicitly clear segment dirty flags and param flags after successful save
            self.current_song.clear_segment_dirty_flags() # <<< This now clears both
            # Song.dirty should be cleared by file_io.save_song (or clear it here if needed)
            # self.current_song.dirty = False # Uncomment if save_song doesn't handle this
            return True # <<< Return success
        else:
            # Error message printed by save_song
            self.set_feedback(f"Failed to save '{self.current_song.name}'", is_error=True)
            return False # <<< Return failure

    def _add_new_segment(self):
        """Adds a new segment after the currently selected one, or at the start."""
        if not self.current_song:
            self.set_feedback("No song loaded to add segment to", is_error=True)
            return

        try:
            new_segment = Segment() # Create with defaults
            insert_index = 0 # Default to beginning

            # Determine insertion index and copy parameters if a segment is selected
            if self.selected_segment_index is not None and self.current_song.segments:
                insert_index = self.selected_segment_index + 1
                try:
                    source_segment = self.current_song.get_segment(self.selected_segment_index)
                    # Copy all parameters from the selected segment
                    for key in self.parameter_keys:
                        if hasattr(source_segment, key):
                            setattr(new_segment, key, getattr(source_segment, key))
                    print(f"Copied parameters from segment {self.selected_segment_index + 1} to new segment.")
                except IndexError:
                    print(f"Warning: Could not get segment at index {self.selected_segment_index} to copy parameters.")
                    # Proceed with default new_segment
            elif self.current_song.segments:
                 # If no segment selected but list not empty, add after last one (effectively at end)
                 insert_index = len(self.current_song.segments)
                 # Optionally copy from last segment in this case too? Let's keep it simple for now.


            self.current_song.add_segment(new_segment, index=insert_index)
            self.set_feedback(f"Added new segment at position {insert_index + 1}")

            # Select the newly added segment
            self.selected_segment_index = insert_index
            # Adjust scroll if necessary
            max_visible = self._get_max_visible_segments()
            if self.selected_segment_index >= self.segment_scroll_offset + max_visible:
                self.segment_scroll_offset = self.selected_segment_index - max_visible + 1
            elif self.selected_segment_index < self.segment_scroll_offset:
                 # This case might happen if adding at the beginning while scrolled down
                 self.segment_scroll_offset = self.selected_segment_index


            # Ensure parameter selection is reset/updated
            self.selected_parameter_key = self.parameter_keys[0] if self.parameter_keys else None
            self.parameter_scroll_offset = 0
            self._update_encoder_led()

        except Exception as e:
            self.set_feedback(f"Error adding segment: {e}", is_error=True)
            print(f"Error in _add_new_segment: {e}")

    # --- ADDED: Exit Prompt Handling Methods ---
    def _save_and_exit(self):
        """Saves the song and then allows exit."""
        print("User chose Save & Exit.")
        if self._save_current_song(): # Try saving
            self.exit_prompt_active = False # Deactivate prompt on success
            # Now allow the app to proceed with screen change
            # We don't trigger the change here, just allow it
            self.app.request_screen_change() # <<< Tell app it's ok now
        else:
            # Save failed, keep prompt active
            self.set_feedback("Save failed! Cannot exit.", is_error=True)

    def _discard_and_exit(self):
        """Discards changes and allows exit."""
        print("User chose Discard & Exit.")
        if self.current_song and self.current_song.dirty:
            self.current_song.dirty = False # Mark song as clean
            self.current_song.clear_segment_dirty_flags() # <<< ADDED: Clear segment/param flags too
            # Optionally reload from disk?
            # reloaded = file_io.load_song(self.current_song.name)
            # if reloaded:
            #     self.app.current_song = reloaded # Update app's copy too
            #     self.current_song = self.app.current_song # Update screen's reference
            self.set_feedback("Changes discarded.")
        elif self.current_song:
             self.set_feedback("No changes to discard.") # If song wasn't dirty
        else:
             self.set_feedback("No song loaded.") # If no song

        self.exit_prompt_active = False # Deactivate prompt
        # Allow the app to proceed with screen change
        self.app.request_screen_change() # <<< Tell app it's ok now

    def _cancel_exit(self):
        """Cancels the exit attempt."""
        print("User chose Cancel Exit.")
        self.exit_prompt_active = False # Deactivate prompt
        self.clear_feedback()
        # App's requested screen change is implicitly cancelled
    # -----------------------------------------

    # --- ADDED: Toggle Boolean Parameter ---
    def _toggle_boolean_parameter(self):
        """Toggles the value of the selected boolean parameter."""
        if (self.selected_segment_index is None or
                self.selected_parameter_key is None or
                not self.current_song):
            return

        try:
            segment = self.current_song.get_segment(self.selected_segment_index)
            current_value = getattr(segment, self.selected_parameter_key, None)

            if isinstance(current_value, bool):
                new_value = not current_value
                # Use the song's update method to ensure dirty flags are set
                self.current_song.update_segment(self.selected_segment_index, **{self.selected_parameter_key: new_value})
                self.set_feedback(f"{self.parameter_display_names.get(self.selected_parameter_key, self.selected_parameter_key)}: {'ON' if new_value else 'OFF'}") # Use ON/OFF
                self._update_encoder_led() # Update LED
            else:
                self.set_feedback("Not a boolean parameter.", is_error=True)

        except (IndexError, AttributeError) as e:
            self.set_feedback(f"Error toggling parameter: {e}", is_error=True)
            self._reset_selection_on_error()

    # --- ADDED: Draw Exit Prompt ---
    def _draw_exit_prompt(self, surface):
        """Draws the unsaved changes prompt when trying to exit."""
        # Reuses the unsaved prompt drawing logic but with different text/context
        overlay = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        box_width, box_height = 400, 200
        box_x = (surface.get_width() - box_width) // 2
        box_y = (surface.get_height() - box_height) // 2

        # Use settings colors
        pygame.draw.rect(surface, settings.BLACK, (box_x, box_y, box_width, box_height))
        pygame.draw.rect(surface, settings.BLUE, (box_x, box_y, box_width, box_height), 2)

        title_text = "Unsaved Changes"
        title_surf = self.font_large.render(title_text, True, settings.BLUE)
        title_rect = title_surf.get_rect(midtop=(surface.get_width() // 2, box_y + 15))
        surface.blit(title_surf, title_rect)

        song_name = self.current_song.name if self.current_song else "Error"
        song_text = f"in '{song_name}'"
        song_surf = self.font.render(song_text, True, settings.WHITE)
        song_rect = song_surf.get_rect(midtop=(surface.get_width() // 2, title_rect.bottom + 10))
        surface.blit(song_surf, song_rect)

        save_btn = mappings.button_map.get(mappings.SAVE_CC, f"CC{mappings.SAVE_CC}")
        discard_btn = mappings.button_map.get(mappings.DELETE_CC, f"CC{mappings.DELETE_CC}")
        cancel_btn = mappings.button_map.get(mappings.NO_NAV_CC, f"CC{mappings.NO_NAV_CC}")

        instr1_text = f"Save & Exit? ({save_btn})"
        instr2_text = f"Discard & Exit? ({discard_btn})"
        instr3_text = f"Cancel Exit? ({cancel_btn})"

        instr1_surf = self.font.render(instr1_text, True, settings.GREEN)
        instr1_rect = instr1_surf.get_rect(midtop=(surface.get_width() // 2, song_rect.bottom + 20))
        surface.blit(instr1_surf, instr1_rect)

        instr2_surf = self.font.render(instr2_text, True, settings.RED)
        instr2_rect = instr2_surf.get_rect(midtop=(surface.get_width() // 2, instr1_rect.bottom + 10))
        surface.blit(instr2_surf, instr2_rect)

        instr3_surf = self.font.render(instr3_text, True, settings.WHITE)
        instr3_rect = instr3_surf.get_rect(midtop=(surface.get_width() // 2, instr2_rect.bottom + 10))
        surface.blit(instr3_surf, instr3_rect)
    # -----------------------------

    # --- ADDED: Helper functions for Elektron Bank/Patch format ---
def value_to_elektron_format(value: int) -> str:
    """Converts a MIDI program change value (0-127) to Elektron format (A01-H16)."""
    if not 0 <= value <= 127:
        return "INV" # Invalid value indicator
    bank_index = value // 16
    patch_number = value % 16
    bank_letter = chr(ord('A') + bank_index)
    patch_str = f"{patch_number + 1:02d}"
    return f"{bank_letter}{patch_str}"

def elektron_format_to_value(bank_patch_str: str) -> Optional[int]:
    """Converts an Elektron format string (A01-H16) to a MIDI program change value (0-127)."""
    if not bank_patch_str or len(bank_patch_str) != 3:
        return None
    bank_letter = bank_patch_str[0].upper()
    patch_str = bank_patch_str[1:]
    if not 'A' <= bank_letter <= 'H' or not patch_str.isdigit():
        return None
    bank_index = ord(bank_letter) - ord('A')
    patch_number = int(patch_str) - 1
    if not 0 <= patch_number <= 15:
        return None
    value = bank_index * 16 + patch_number
    return value
# --- END ADDED HELPER FUNCTIONS ---

    # ... (rest of the methods like _save_current_song, _add_new_segment, etc.) ...
