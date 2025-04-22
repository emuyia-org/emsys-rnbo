# emsys/ui/song_edit_screen.py
# -*- coding: utf-8 -*-
"""
Screen for viewing and editing Song objects using SongService.
Includes integrated playback status display.
"""
import pygame # <<< Ensure pygame is imported
import time # <<< Ensure time is imported
import os # <<< Ensure os is imported
import traceback # <<< Ensure traceback is imported
from typing import List, Optional, Tuple, Any, Dict, Set, Union
from enum import Enum, auto
from dataclasses import asdict

# Core components (Only Segment needed for type hinting, Song managed by service)
from ..core.song import Segment # Keep direct access to Segment structure for type hinting
# from ..utils import file_io # No longer needed directly
from ..config import settings, mappings

# Base class and widgets
from .base_screen import BaseScreen
from .widgets import TextInputWidget, TextInputStatus, FocusColumn

# --- Import Helpers ---
from .helpers.led_feedback_handler import LedFeedbackHandler
from .helpers.parameter_editor import ParameterEditor # ParameterEditor can remain as is
# --------------------

# Import Service Layer
from ..services.song_service import SongService # <<< IMPORT SongService

# Import colors and constants
from emsys.config.settings import (ERROR_COLOR, FEEDBACK_COLOR, HIGHLIGHT_COLOR,
                                   BLACK, WHITE, GREY, BLUE, FOCUS_BORDER_COLOR,
                                   FEEDBACK_AREA_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT,
                                   MULTI_SELECT_COLOR, MULTI_SELECT_ANCHOR_COLOR,
                                   GREEN, RED) # <<< Added GREEN, RED

# <<< ADD A_BTN_12_CC to imports >>>
from emsys.config.mappings import (A_BTN_1_CC, A_BTN_9_CC, A_BTN_13_CC, FADER_A_CC, FADER_B_CC,
                                   A_BTN_12_CC) # <<< ADDED A_BTN_12_CC
# <<< END ADD >>>

# Define layout constants
LEFT_MARGIN = 15
TOP_MARGIN = 15
LINE_HEIGHT = 36
PARAM_INDENT = 30
SEGMENT_LIST_WIDTH = 180
PARAM_AREA_X = LEFT_MARGIN + SEGMENT_LIST_WIDTH + 15
COLUMN_BORDER_WIDTH = 2
LIST_TOP_PADDING = 10
# <<< NEW: Height reserved for playback status at the bottom >>>
PLAYBACK_STATUS_AREA_HEIGHT = 50 # Adjust as needed

# <<< ADDED: Flashing constants >>>
FLASH_INTERVAL_MS = 300 # How often the flash state toggles (milliseconds)
QUEUED_FLASH_COLOR = BLUE # Color to use for flashing queued segment
# <<< END ADDED >>>

# Helper to convert program change value to display format (can stay here or move to utils)
def value_to_elektron_format(value: int) -> str:
    """Converts a MIDI program change value (0-127) to Elektron format (A01-H16)."""
    if not 0 <= value <= 127: return "INV"
    bank_index = value // 16
    patch_number = value % 16
    bank_letter = chr(ord('A') + bank_index)
    patch_str = f"{patch_number + 1:02d}"
    return f"{bank_letter}{patch_str}"


class SongEditScreen(BaseScreen):
    """Screen for editing song structure and segment parameters via SongService."""

    def __init__(self, app, song_service: SongService):
        """Initialize the song editing screen."""
        super().__init__(app)
        self.song_service = song_service
        self.led_handler = LedFeedbackHandler(app)
        self.param_editor = ParameterEditor()

        # --- Fonts ---
        self.font_large = self.get_pixel_font(28)
        self.font_medium = self.get_pixel_font(22) # Used for playback status
        self.font_small = self.get_pixel_font(20) # Used for list items
        self.font_tiny = self.get_pixel_font(16) # Used for scroll arrows, maybe status details
        self.font = self.font_small # Default font for items
        self.title_rect = pygame.Rect(0,0,0,0)

        # --- State ---
        # self.current_song removed - access via self.song_service.get_current_song()
        self.selected_segment_index: Optional[int] = None # Represents the 'anchor' in multi-select
        self.selected_parameter_key: Optional[str] = None
        self.focused_column: FocusColumn = FocusColumn.SEGMENT_LIST
        self.segment_scroll_offset: int = 0
        self.parameter_scroll_offset: int = 0
        self.feedback_message: Optional[Tuple[str, float, Tuple[int, int, int]]] = None
        self.feedback_duration: float = 2.0
        self.text_input_widget = TextInputWidget(app)
        self.no_button_held: bool = False
        # <<< MODIFIED: copied_segment_data can now be a list for multi-copy >>>
        self.copied_segment_data: Optional[List[Dict[str, Any]]] = None
        self.multi_select_indices: Set[int] = set()
        # <<< ADDED: Flashing state >>>
        self.flash_on: bool = False
        self.last_flash_toggle_time: float = 0.0
        # <<< END ADDED >>>
        # -----------------------------------------

        # Define parameter order and display names (kept here for drawing)
        self.parameter_keys: List[str] = [
            'program_message_1', 'program_message_2', 'tempo', 'tempo_ramp',
            'loop_length', 'repetitions', 'automatic_transport_interrupt'
        ]
        self.parameter_display_names: dict[str, str] = {
            'program_message_1': "Prog Ch 1", 'program_message_2': "Prog Ch 2",
            'tempo': "Tempo (BPM)", 'tempo_ramp': "Ramp (Sec)",
            'loop_length': "Length (Beats)", 'repetitions': "Repeats",
            'automatic_transport_interrupt': "Auto Pause"
        }
        # --- END State ---

    def init(self):
        """Called when the screen becomes active. References the current song from SongService."""
        super().init()
        print(f"{self.__class__.__name__} is now active.")
        # Get current song reference from the service
        current_song = self.song_service.get_current_song()

        # Initialize selection state based on song from service
        if current_song and current_song.segments:
            # Try to keep previous selection if possible, otherwise default to 0
            if self.selected_segment_index is None or self.selected_segment_index >= len(current_song.segments):
                 self.selected_segment_index = 0
            # Ensure parameter key is valid or default
            if self.selected_parameter_key not in self.parameter_keys:
                 self.selected_parameter_key = self.parameter_keys[0] if self.parameter_keys else None
        else:
            self.selected_segment_index = None
            self.selected_parameter_key = None

        # Reset screen-specific state
        self.focused_column = FocusColumn.SEGMENT_LIST
        self.segment_scroll_offset = 0
        self.parameter_scroll_offset = 0
        self._adjust_segment_scroll() # Adjust scroll based on selection
        self._adjust_parameter_scroll() # Adjust scroll based on selection
        self.clear_feedback()
        self.text_input_widget.cancel()
        self.no_button_held = False
        self.copied_segment_data = None
        self.multi_select_indices.clear() # <<< ADDED: Clear multi-select

        if not current_song:
            self.set_feedback("No song loaded!", is_error=True, duration=5.0)

        self._update_leds() # Update LEDs on activation

    def cleanup(self):
        """Called when the screen becomes inactive."""
        super().cleanup()
        print(f"{self.__class__.__name__} is being deactivated.")
        self.text_input_widget.cancel()
        self.clear_feedback()
        self.no_button_held = False
        self.copied_segment_data = None
        self.multi_select_indices.clear() # <<< ADDED: Clear multi-select
        # Optionally turn off specific LEDs here using led_handler if needed

    def set_feedback(self, message: str, is_error: bool = False, duration: Optional[float] = None):
        """Display a feedback message."""
        print(f"Feedback: {message}")
        color = ERROR_COLOR if is_error else FEEDBACK_COLOR
        self.feedback_message = (message, time.time(), color)
        self.feedback_duration = duration if duration is not None else 2.0

    def clear_feedback(self):
        """Clear the feedback message."""
        self.feedback_message = None

    def update(self):
        """Update screen state, like clearing timed feedback and handling flashing."""
        super().update()
        current_time = time.time()

        # --- Clear Timed Feedback ---
        if self.feedback_message and (current_time - self.feedback_message[1] > self.feedback_duration):
            self.clear_feedback()

        # --- Update Flashing State ---
        if (current_time - self.last_flash_toggle_time) * 1000 >= FLASH_INTERVAL_MS:
            self.flash_on = not self.flash_on
            self.last_flash_toggle_time = current_time
        # --- End Flashing Update ---

    def handle_midi(self, msg):
        """Handle MIDI messages delegated from the main app."""
        # ... (existing code for non-CC or text input) ...
        if msg.type != 'control_change':
             return

        cc = msg.control
        value = msg.value

        # --- Handle Text Input Mode FIRST (if ever used) ---
        if self.text_input_widget.is_active:
            # ... (text input handling logic - currently none needed here)
            return

        # --- Track NO Button State ---
        if cc == mappings.NO_NAV_CC:
            if value == 127:
                self.no_button_held = True
                # Don't clear multi-select here, allow holding NO across actions
            elif value == 0:
                self.no_button_held = False
                self.multi_select_indices.clear() # <<< Clear multi-select on NO release
                # NO release itself doesn't trigger actions below, so return
                return

        # <<< ADDED: Handle FADER_A_CC for Segment Selection Only >>>
        if cc == FADER_A_CC:
            self.multi_select_indices.clear() # Clear multi-select on fader use
            self._handle_fader_a_segment_selection(value)
            return # Fader A handled
        # <<< END ADDED >>>

        # --- Handle Fader B for Contextual Selection ---
        if cc == FADER_B_CC:
            self.multi_select_indices.clear() # <<< Clear multi-select on fader use
            self._handle_fader_b_contextual_selection(value) # <<< Renamed for clarity
            return # Fader B handled

        # --- Handle Encoder Rotation for Parameter Adjustment ---
        if cc == mappings.KNOB_B8_CC: # Assuming B8 is the primary editing encoder
            direction = 0
            if 1 <= value <= 63: direction = 1
            elif 65 <= value <= 127: direction = -1

            if direction != 0:
                self._modify_parameter_via_encoder(direction)
            return # Encoder handled

        # --- Process Button Presses (value == 127) ---
        if value == 127:
            # <<< ADDED: Handle A_BTN_12_CC for Load/Queue Segment >>>
            if cc == A_BTN_12_CC:
                # Check if STOP button is held (for Reset Song combination in main.py)
                # We access stop_button_held directly from app state for this check
                if not self.app.stop_button_held:
                    self._handle_load_queue_segment()
                    return # Handled
                else:
                    # If STOP is held, let main.py handle the Reset Song combo
                    # Log that we are ignoring it here
                    print(f"UI: Ignoring A_BTN_12 press because STOP is held (Reset Song combo).")
                    pass # Fall through to allow main.py's handler if needed (though it should catch it first)
            # <<< END ADDED >>>

            # <<< ADDED: Handle A_BTN_13_CC for Hold Toggle >>>
            elif cc == A_BTN_13_CC:
                self.app.toggle_hold_state() # Call the App's method
                # Update LEDs and provide feedback based on the new state in App
                self._update_leds()
                hold_state_str = "ON" if self.app.hold_active else "OFF"
                #self.set_feedback(f"Segment Hold {hold_state_str}", duration=1.5)
                return # Handled
            # <<< END ADDED >>>

            # <<< ADDED: Handle A_BTN_1 and A_BTN_9 for Segment Navigation >>>
            elif cc == A_BTN_1_CC: # Navigate Segment UP (regardless of focus)
                self.multi_select_indices.clear() # Clear multi-select on direct segment nav
                self._change_selected_segment(-1)
                return # Handled
            elif cc == A_BTN_9_CC: # Navigate Segment DOWN (regardless of focus)
                self.multi_select_indices.clear() # Clear multi-select on direct segment nav
                self._change_selected_segment(1)
                return # Handled
            # <<< END ADDED >>>

            # --- Action Buttons ---
            elif cc == mappings.SAVE_CC:
                if self.no_button_held and self.focused_column == FocusColumn.SEGMENT_LIST:
                    # NO + SAVE in Segment List = Copy Selected Segment(s)
                    self._copy_multiple_segments()
                elif not self.no_button_held:
                    # SAVE = Save Current Song
                    self._save_current_song()
                return # SAVE CC handled

            elif cc == mappings.CREATE_CC:
                if self.no_button_held and self.focused_column == FocusColumn.SEGMENT_LIST:
                    # NO + CREATE in Segment List = Paste Copied Segment(s)
                    self._paste_multiple_segments()
                elif not self.no_button_held:
                    # CREATE = Add New Segment (or Insert Unique if NO held - handled above?)
                    # Let's stick to simple CREATE = Add New Segment for now
                    self._add_new_segment()
                return # CREATE CC handled

            elif cc == mappings.DELETE_CC:
                if self.no_button_held and self.focused_column == FocusColumn.SEGMENT_LIST:
                    # NO + DELETE in Segment List = Delete Selected Segment(s)
                    self._delete_multiple_segments()
                elif not self.no_button_held and self.focused_column == FocusColumn.SEGMENT_LIST:
                    # DELETE in Segment List = Delete Selected Segment(s) (Same as NO + DELETE)
                    self._delete_multiple_segments()
                elif self.focused_column == FocusColumn.PARAMETER_DETAILS:
                    # DELETE in Parameter Details = Reset/Copy Parameter
                    self._reset_or_copy_parameter()
                return # DELETE CC handled

            # <<< ADDED: Handle RENAME_CC with NO modifier >>>
            elif cc == mappings.RENAME_CC:
                if self.no_button_held:
                    # NO + RENAME = Insert New Segment with Unique PGMs
                    self._insert_new_segment_unique_pgm()
                else:
                    # RENAME = (Currently no action, could be used for song rename later)
                    self.set_feedback("Rename action not implemented yet", duration=1.5)
                return # RENAME CC handled
            # <<< END ADDED >>>

            # --- Navigation Buttons ---
            elif cc == mappings.DOWN_NAV_CC:
                if self.no_button_held and self.focused_column == FocusColumn.SEGMENT_LIST:
                    # NO + DOWN in Segment List = Multi-Select Down
                    self._change_selected_segment_multi(1)
                elif self.focused_column == FocusColumn.SEGMENT_LIST:
                    # DOWN in Segment List = Select Next Segment
                    self.multi_select_indices.clear() # Clear multi-select on single nav
                    self._change_selected_segment(1)
                else: # Parameter Details Focused
                    # DOWN in Parameter Details = Select Next Parameter
                    self._change_selected_parameter_vertically(1)
                return # DOWN handled

            elif cc == mappings.UP_NAV_CC:
                if self.no_button_held and self.focused_column == FocusColumn.SEGMENT_LIST:
                    # NO + UP in Segment List = Multi-Select Up
                    self._change_selected_segment_multi(-1)
                elif self.focused_column == FocusColumn.SEGMENT_LIST:
                    # UP in Segment List = Select Previous Segment
                    self.multi_select_indices.clear() # Clear multi-select on single nav
                    self._change_selected_segment(-1)
                else: # Parameter Details Focused
                    # UP in Parameter Details = Select Previous Parameter
                    self._change_selected_parameter_vertically(-1)
                return # UP handled

            elif cc == mappings.RIGHT_NAV_CC:
                self.multi_select_indices.clear() # <<< Clear multi-select on focus change
                self._navigate_focus(1)
                return # RIGHT handled

            elif cc == mappings.LEFT_NAV_CC:
                self.multi_select_indices.clear() # <<< Clear multi-select on focus change
                self._navigate_focus(-1)
                return # LEFT handled

            # --- Parameter Modification Buttons (YES/NO) ---
            elif cc == mappings.YES_NAV_CC:
                if self.focused_column == FocusColumn.PARAMETER_DETAILS:
                    # YES in Parameter Details = Increment/Toggle Parameter
                    self._modify_parameter_via_button(1)
                return # YES handled

            elif cc == mappings.NO_NAV_CC:
                # NO press is tracked above. If it reaches here, it means value is 127.
                # If parameter column is focused, treat as decrement/toggle.
                if self.focused_column == FocusColumn.PARAMETER_DETAILS:
                     # NO in Parameter Details = Decrement/Toggle Parameter
                     self._modify_parameter_via_button(-1)
                # else:
                    # If segment list focused, NO press (value=127) does nothing here by itself.
                    # Multi-select is handled by checking self.no_button_held with UP/DOWN/etc.
                return # NO handled (as a potential parameter modifier)

    # --- Helper to update LEDs using the handler ---
    def _update_leds(self):
        """Calls the LED handler to update controller feedback based on SongService state."""
        current_song = self.song_service.get_current_song() # Get song from service
        self.led_handler.update_encoder_led(
            current_song, # Pass song object
            self.selected_segment_index,
            self.selected_parameter_key
        )
        # <<< ADDED: Update A_BTN_13 LED based on hold state >>>
        try:
            # Assuming led_handler has a method like set_button_led
            # Or send MIDI directly if handler doesn't support it yet
            hold_led_value = 127 if self.app.hold_active else 0
            # self.led_handler.set_button_led(A_BTN_13_CC, hold_led_value) # Ideal
            self.app.send_midi_cc(A_BTN_13_CC + 64, hold_led_value) # Send to corresponding LED CC (often +64 offset)
        except Exception as e:
            print(f"Error updating hold LED: {e}")
        # <<< END ADDED >>>

    # --- Parameter Modification ---
    def _modify_parameter(self, direction: int):
        """Common logic to modify parameter using the editor and update via SongService."""
        current_song = self.song_service.get_current_song()
        if not current_song or self.selected_segment_index is None or self.selected_parameter_key is None:
            self.set_feedback("Cannot modify: Invalid selection.", is_error=True)
            return

        # ParameterEditor directly modifies the song object if needed (can stay as is)
        # It now gets the song object from the service via this screen
        new_value, status, changed = self.param_editor.modify_parameter(
            current_song, # Pass the song object obtained from the service
            self.selected_segment_index,
            self.selected_parameter_key,
            direction
        )

        # --- Feedback and LED update logic remains the same ---
        if new_value is not None:
            if changed:
                self._update_leds()
                key = self.selected_parameter_key
                display_name = self.parameter_display_names.get(key, key)
                if key in ['program_message_1', 'program_message_2']: value_str = value_to_elektron_format(int(new_value))
                elif isinstance(new_value, bool): value_str = "ON" if new_value else "OFF"
                elif isinstance(new_value, float): value_str = f"{new_value:.1f}"
                else: value_str = str(new_value)
                self.set_feedback(f"{display_name}: {value_str}", duration=0.75)
            elif status in ["At Min", "At Max"]:
                 key = self.selected_parameter_key
                 display_name = self.parameter_display_names.get(key, key)
                 self.set_feedback(f"{display_name}: {status.lower()}", duration=0.5)
                 self._update_leds() # Ensure LED is correct
        else:
            self.set_feedback(status, is_error=True) # Status contains the error message

    def _modify_parameter_via_encoder(self, direction: int):
        """Modify using encoder."""
        self._modify_parameter(direction)

    def _modify_parameter_via_button(self, direction: int):
        """Modify using +/- buttons. Only works if parameter details are focused."""
        # <<< ADDED focus check >>>
        if self.focused_column != FocusColumn.PARAMETER_DETAILS:
            # self.set_feedback("Focus on parameters to edit with YES/NO", duration=1.0) # Optional feedback
            return

        if self.selected_parameter_key == 'automatic_transport_interrupt':
             self._modify_parameter(1) # Toggle bool
        else:
            self._modify_parameter(direction)

    def _reset_or_copy_parameter(self):
        """Resets or copies the selected parameter using the editor via SongService."""
        if self.focused_column != FocusColumn.PARAMETER_DETAILS: return

        current_song = self.song_service.get_current_song()
        if not current_song or self.selected_segment_index is None or self.selected_parameter_key is None:
            self.set_feedback("Cannot reset/copy: Invalid selection.", is_error=True)
            return

        # Pass the song object from the service to the editor
        new_value, status, changed = self.param_editor.reset_or_copy_parameter(
            current_song,
            self.selected_segment_index,
            self.selected_parameter_key
        )

        self.set_feedback(status)
        if changed:
            self._update_leds()

    # --- Navigation and Selection ---
    # <<< RENAMED method >>>
    def _handle_fader_b_contextual_selection(self, fader_value: int):
        """Handles selection changes via Fader B based on the focused column."""
        # <<< NOTE: Fader clears multi-select (handled in handle_midi) >>>
        current_song = self.song_service.get_current_song()
        if not current_song: return

        reversed_value = 127 - fader_value

        if self.focused_column == FocusColumn.SEGMENT_LIST:
            if not current_song.segments: return
            num_items = len(current_song.segments)
            target_index = max(0, min(num_items - 1, int((reversed_value / 128.0) * num_items)))
            if target_index != self.selected_segment_index:
                self.selected_segment_index = target_index
                self._adjust_segment_scroll()
                self.clear_feedback()
                self._update_leds()

        elif self.focused_column == FocusColumn.PARAMETER_DETAILS:
            if self.selected_segment_index is None or not self.parameter_keys: return
            num_items = len(self.parameter_keys)
            target_param_index = max(0, min(num_items - 1, int((reversed_value / 128.0) * num_items)))
            target_key = self.parameter_keys[target_param_index]
            if target_key != self.selected_parameter_key:
                self.selected_parameter_key = target_key
                self._adjust_parameter_scroll()
                self.clear_feedback()
                self._update_leds()
    # <<< END RENAMED method >>>

    # <<< ADDED: New method for Fader A >>>
    def _handle_fader_a_segment_selection(self, fader_value: int):
        """Handles segment selection changes via Fader A, regardless of focus."""
        # <<< NOTE: Fader clears multi-select (handled in handle_midi) >>>
        current_song = self.song_service.get_current_song()
        if not current_song or not current_song.segments:
            return # No song or no segments to select

        reversed_value = 127 - fader_value
        num_items = len(current_song.segments)
        target_index = max(0, min(num_items - 1, int((reversed_value / 128.0) * num_items)))

        # Only update if the segment index actually changes
        if target_index != self.selected_segment_index:
            self.selected_segment_index = target_index
            self._adjust_segment_scroll()
            self.clear_feedback()
            self._update_leds()
            # Optional: Provide feedback that segment changed even if focus was elsewhere
            # self.set_feedback(f"Segment {target_index + 1} selected", duration=0.75)

    def _navigate_focus(self, direction: int):
        """Change focus between columns."""
        # <<< NOTE: Focus change clears multi-select (handled in handle_midi) >>>
        if direction > 0 and self.focused_column == FocusColumn.SEGMENT_LIST:
            self.focused_column = FocusColumn.PARAMETER_DETAILS
        elif direction < 0 and self.focused_column == FocusColumn.PARAMETER_DETAILS:
            self.focused_column = FocusColumn.SEGMENT_LIST
        else:
            return

        self.clear_feedback()
        self._update_leds()

    def _change_selected_segment(self, direction: int):
        """Change the selected segment index (single selection) and handle scrolling."""
        # <<< NOTE: This is called when NO is NOT held, multi-select is cleared in handle_midi >>>
        current_song = self.song_service.get_current_song()
        if not current_song or not current_song.segments: return

        num_segments = len(current_song.segments)
        if self.selected_segment_index is None:
            self.selected_segment_index = 0 if direction > 0 else num_segments - 1
        else:
            self.selected_segment_index = (self.selected_segment_index + direction + num_segments) % num_segments

        self._adjust_segment_scroll()
        self.clear_feedback()
        self._update_leds()

    # <<< NEW METHOD: Multi-select segment navigation >>>
    def _change_selected_segment_multi(self, direction: int):
        """Change the anchor segment index and add to multi-select set."""
        current_song = self.song_service.get_current_song()
        if not current_song or not current_song.segments: return

        num_segments = len(current_song.segments)
        current_anchor = self.selected_segment_index

        # Initialize multi-select with current anchor if it's empty
        if not self.multi_select_indices and current_anchor is not None:
            self.multi_select_indices.add(current_anchor)

        # Calculate new anchor index
        if current_anchor is None:
            new_anchor = 0 if direction > 0 else num_segments - 1
        else:
            new_anchor = (current_anchor + direction + num_segments) % num_segments

        # Update anchor and add to multi-select set
        self.selected_segment_index = new_anchor
        self.multi_select_indices.add(new_anchor)

        self._adjust_segment_scroll() # Scroll based on the new anchor
        self.clear_feedback()
        self._update_leds() # Update LEDs if needed
        # Provide feedback about multi-selection
        #self.set_feedback(f"Multi-select: {len(self.multi_select_indices)} segments", duration=1.0)
    # <<< END NEW METHOD >>>

    def _change_selected_parameter_vertically(self, direction: int):
        """Change the selected parameter key and handle scrolling."""
        if self.selected_segment_index is None or not self.parameter_keys: return

        num_params = len(self.parameter_keys)
        current_param_index = -1
        if self.selected_parameter_key:
            try: current_param_index = self.parameter_keys.index(self.selected_parameter_key)
            except ValueError: pass

        new_param_index = (current_param_index + direction + num_params) % num_params
        self.selected_parameter_key = self.parameter_keys[new_param_index]

        self._adjust_parameter_scroll()
        self.clear_feedback()
        self._update_leds()

    def _adjust_segment_scroll(self):
        """Adjust segment scroll offset based on selection (anchor)."""
        if self.selected_segment_index is None: return
        max_visible = self._get_max_visible_segments() # <<< REMOVED area_rect argument
        current_song = self.song_service.get_current_song()
        num_segments = len(current_song.segments) if current_song else 0
        if num_segments <= max_visible:
            self.segment_scroll_offset = 0
            return

        if self.selected_segment_index >= self.segment_scroll_offset + max_visible:
            self.segment_scroll_offset = self.selected_segment_index - max_visible + 1
        elif self.selected_segment_index < self.segment_scroll_offset:
            self.segment_scroll_offset = self.selected_segment_index
        self.segment_scroll_offset = max(0, min(self.segment_scroll_offset, num_segments - max_visible))


    def _adjust_parameter_scroll(self):
        """Adjust parameter scroll offset based on selection."""
        if self.selected_parameter_key is None or not self.parameter_keys: return
        max_visible = self._get_max_visible_parameters() # <<< REMOVED area_rect argument
        num_params = len(self.parameter_keys)
        if num_params <= max_visible:
            self.parameter_scroll_offset = 0
            return

        try: current_param_index = self.parameter_keys.index(self.selected_parameter_key)
        except ValueError: return # Should not happen if key is valid

        if current_param_index >= self.parameter_scroll_offset + max_visible:
            self.parameter_scroll_offset = current_param_index - max_visible + 1
        elif current_param_index < self.parameter_scroll_offset:
            self.parameter_scroll_offset = current_param_index
        self.parameter_scroll_offset = max(0, min(self.parameter_scroll_offset, num_params - max_visible))

    # --- Song/Segment Actions ---
    def _save_current_song(self):
        """Saves the current song via SongService."""
        success, message = self.song_service.save_current_song() # <<< Use SongService
        self.set_feedback(message, is_error=not success)

    def _add_new_segment(self):
        """Adds a new segment via SongService, copying params from selected/last."""
        current_song = self.song_service.get_current_song()
        if not current_song:
            self.set_feedback("No song loaded", is_error=True)
            return

        try:
            new_segment = Segment()
            new_segment.dirty = True # <<< ADDED: Mark the new segment itself as dirty
            insert_index = 0
            source_segment = None

            if self.selected_segment_index is not None and current_song.segments:
                insert_index = self.selected_segment_index + 1
                try: source_segment = current_song.get_segment(self.selected_segment_index)
                except IndexError: pass
            elif current_song.segments:
                 insert_index = len(current_song.segments)
                 try: source_segment = current_song.get_segment(insert_index - 1) # Copy last if adding at end
                 except IndexError: pass

            # Copy parameters if a source was found
            if source_segment:
                for key in self.parameter_keys:
                    if hasattr(source_segment, key):
                        setattr(new_segment, key, getattr(source_segment, key))
                print(f"Copied parameters from segment index {self.selected_segment_index if insert_index > 0 else 'last'}")

            # Add via service
            success, message = self.song_service.add_segment_to_current(new_segment, index=insert_index) # <<< Use SongService

            if success:
                self.set_feedback(f"Added new segment at {insert_index + 1}")
                # Select the newly added segment and update UI
                self.selected_segment_index = insert_index
                self._adjust_segment_scroll()
                self._ensure_parameter_selection()
                self._update_leds()
            else:
                self.set_feedback(message, is_error=True)

        except Exception as e:
            self.set_feedback(f"Error adding segment: {e}", is_error=True)
            print(f"Error in _add_new_segment: {e}")

    def _insert_new_segment_unique_pgm(self):
        """
        Inserts a new segment after the selected one, copying parameters but
        assigning the next available unique program change values for PGM1 and PGM2.
        """
        current_song = self.song_service.get_current_song()
        if not current_song:
            self.set_feedback("No song loaded", is_error=True)
            return

        try:
            # --- Find Next Unique PGM Values ---
            existing_pgm1 = {seg.program_message_1 for seg in current_song.segments}
            existing_pgm2 = {seg.program_message_2 for seg in current_song.segments}

            next_pgm1 = -1
            for i in range(mappings.MIN_PROGRAM_MSG, mappings.MAX_PROGRAM_MSG + 1):
                if i not in existing_pgm1:
                    next_pgm1 = i
                    break

            next_pgm2 = -1
            for i in range(mappings.MIN_PROGRAM_MSG, mappings.MAX_PROGRAM_MSG + 1):
                if i not in existing_pgm2:
                    next_pgm2 = i
                    break

            if next_pgm1 == -1 or next_pgm2 == -1:
                pgm_unavailable = "PGM1" if next_pgm1 == -1 else "PGM2"
                self.set_feedback(f"Cannot insert: All {pgm_unavailable} values used!", is_error=True, duration=3.0)
                return

            # --- Create and Configure New Segment ---
            new_segment = Segment()
            new_segment.dirty = True
            new_segment.program_message_1 = next_pgm1
            new_segment.program_message_2 = next_pgm2
            # Mark the unique params as dirty initially
            new_segment.dirty_params.add('program_message_1')
            new_segment.dirty_params.add('program_message_2')


            insert_index = 0
            source_segment = None

            if self.selected_segment_index is not None and current_song.segments:
                insert_index = self.selected_segment_index + 1
                try: source_segment = current_song.get_segment(self.selected_segment_index)
                except IndexError: pass
            elif current_song.segments:
                 insert_index = len(current_song.segments)
                 try: source_segment = current_song.get_segment(insert_index - 1) # Copy last if adding at end
                 except IndexError: pass

            # Copy parameters (except PGM values) if a source was found
            if source_segment:
                copied_params_count = 0
                for key in self.parameter_keys:
                    # Skip the PGM values we just set
                    if key in ['program_message_1', 'program_message_2']:
                        continue
                    if hasattr(source_segment, key):
                        value_to_copy = getattr(source_segment, key)
                        setattr(new_segment, key, value_to_copy)
                        copied_params_count += 1
                print(f"Copied {copied_params_count} parameters (excluding PGMs) for unique insert.")

            # --- Add via Service ---
            success, message = self.song_service.add_segment_to_current(new_segment, index=insert_index)

            if success:
                pgm1_str = value_to_elektron_format(next_pgm1)
                pgm2_str = value_to_elektron_format(next_pgm2)
                self.set_feedback(f"Inserted segment {insert_index + 1} ({pgm1_str}/{pgm2_str})")
                # Select the newly added segment and update UI
                self.selected_segment_index = insert_index
                self._adjust_segment_scroll()
                self._ensure_parameter_selection() # Ensure a param is selected
                self.focused_column = FocusColumn.SEGMENT_LIST # Keep focus on segments
                self._update_leds()
            else:
                self.set_feedback(message, is_error=True)

        except Exception as e:
            self.set_feedback(f"Error inserting unique segment: {e}", is_error=True)
            print(f"Error in _insert_new_segment_unique_pgm: {e}")
            traceback.print_exc()

    def _delete_current_segment(self):
        """Deletes the currently selected single segment via SongService."""
        if self.selected_segment_index is None:
            self.set_feedback("No segment selected", is_error=True)
            return

        index_to_delete = self.selected_segment_index
        current_song = self.song_service.get_current_song()
        num_segments_before = len(current_song.segments) if current_song else 0

        success, message = self.song_service.remove_segment_from_current(index_to_delete) # <<< Use SongService

        if success:
            self.set_feedback(f"Deleted Segment {index_to_delete + 1}")
            current_song = self.song_service.get_current_song() # Re-get potentially updated song
            num_segments_after = len(current_song.segments) if current_song else 0

            if num_segments_after == 0:
                self.selected_segment_index = None
                self.selected_parameter_key = None
                self.focused_column = FocusColumn.SEGMENT_LIST
            else:
                self.selected_segment_index = min(index_to_delete, num_segments_after - 1)
                self._adjust_segment_scroll()
                self._ensure_parameter_selection()

            self._update_leds()
        else:
            self.set_feedback(message, is_error=True)
            # Optionally reset selection on error?
            # self._reset_selection_on_error()

    # --- Modified/New Copy/Paste/Delete Helper Methods ---

    def _copy_multiple_segments(self):
        """Copies data of selected segment(s) (single or multi) to clipboard."""
        current_song = self.song_service.get_current_song()
        if not current_song:
            self.set_feedback("No song loaded", is_error=True)
            return

        indices_to_copy = []
        if self.multi_select_indices:
            # Sort indices to maintain order in the copied list
            indices_to_copy = sorted(list(self.multi_select_indices))
        elif self.selected_segment_index is not None:
            indices_to_copy = [self.selected_segment_index]
        else:
            self.set_feedback("No segment selected to copy", is_error=True)
            return

        copied_list = []
        try:
            for index in indices_to_copy:
                segment_to_copy = current_song.get_segment(index)
                segment_data = asdict(segment_to_copy)
                segment_data.pop('dirty', None)
                segment_data.pop('dirty_params', None)
                copied_list.append(segment_data)

            self.copied_segment_data = copied_list # Store as list always
            count = len(copied_list)
            plural = "s" if count > 1 else ""
            self.set_feedback(f"Copied {count} segment{plural}")

        except (IndexError, Exception) as e:
            self.copied_segment_data = None
            self.set_feedback(f"Error copying segment(s): {e}", is_error=True)
            print(f"Error in _copy_multiple_segments: {e}")
            traceback.print_exc()


    def _paste_multiple_segments(self):
        """Pastes the copied segment data (single or multiple) after the selected segment."""
        current_song = self.song_service.get_current_song()
        if not self.copied_segment_data: # Checks if list is None or empty
            self.set_feedback("Nothing copied to paste", is_error=True)
            return
        if not current_song:
            self.set_feedback("No song loaded to paste into", is_error=True)
            return

        try:
            insert_index = 0
            if self.selected_segment_index is not None:
                insert_index = self.selected_segment_index + 1
            elif current_song.segments:
                 insert_index = len(current_song.segments)

            pasted_count = 0
            last_pasted_index = insert_index -1 # Keep track for final selection

            for segment_data in self.copied_segment_data:
                pasted_segment = Segment(**segment_data)
                pasted_segment.dirty = True # Mark pasted segment as needing save

                # Add via service at the current insert_index
                success, message = self.song_service.add_segment_to_current(pasted_segment, index=insert_index)

                if success:
                    pasted_count += 1
                    last_pasted_index = insert_index
                    insert_index += 1 # Increment for the next paste
                else:
                    # Stop pasting if one fails
                    self.set_feedback(f"Paste failed at segment {pasted_count + 1}: {message}", is_error=True)
                    # Update UI state partially if needed
                    self.selected_segment_index = last_pasted_index if last_pasted_index >= 0 else 0
                    self._adjust_segment_scroll()
                    self._ensure_parameter_selection()
                    self._update_leds()
                    return # Exit paste operation

            # If all pastes succeeded
            plural = "s" if pasted_count > 1 else ""
            self.set_feedback(f"Pasted {pasted_count} segment{plural} at {last_pasted_index - pasted_count + 2}")
            # Select the last pasted segment
            self.selected_segment_index = last_pasted_index
            self._adjust_segment_scroll()
            self._ensure_parameter_selection()
            self._update_leds()

        except (TypeError, Exception) as e:
            self.set_feedback(f"Error pasting segment(s): {e}", is_error=True)
            print(f"Error in _paste_multiple_segments: {e}")
            traceback.print_exc()


    def _delete_multiple_segments(self):
        """Deletes the selected segment(s) (single or multi) via SongService."""
        current_song = self.song_service.get_current_song()
        if not current_song:
            self.set_feedback("No song loaded", is_error=True)
            return

        indices_to_delete = set()
        if self.multi_select_indices:
            indices_to_delete = self.multi_select_indices.copy() # Use the set
        elif self.selected_segment_index is not None:
            indices_to_delete.add(self.selected_segment_index)
        else:
            self.set_feedback("No segment selected to delete", is_error=True)
            return

        if not indices_to_delete:
             self.set_feedback("No segment selected to delete", is_error=True)
             return

        # Sort indices in descending order to avoid index shifting issues
        sorted_indices = sorted(list(indices_to_delete), reverse=True)
        original_anchor = self.selected_segment_index # Remember anchor before deletion
        deleted_count = 0
        first_deleted_index = sorted_indices[0] # Highest index deleted

        for index_to_delete in sorted_indices:
            success, message = self.song_service.remove_segment_from_current(index_to_delete)
            if success:
                deleted_count += 1
            else:
                # Stop deleting if one fails
                self.set_feedback(f"Delete failed at segment {index_to_delete + 1}: {message}", is_error=True)
                # Update UI state partially if needed (tricky after partial delete)
                # Try to select the segment before the first one we attempted to delete
                self.selected_segment_index = max(0, first_deleted_index - deleted_count) if current_song.segments else None
                self.multi_select_indices.clear() # Clear multi-select state
                self._adjust_segment_scroll()
                self._ensure_parameter_selection()
                self._update_leds()
                return # Exit delete operation

        # If all deletions succeeded
        plural = "s" if deleted_count > 1 else ""
        self.set_feedback(f"Deleted {deleted_count} segment{plural}")

        # Clear multi-select state *after* successful deletion
        self.multi_select_indices.clear()

        # Update selection logic after deletion
        current_song = self.song_service.get_current_song() # Re-get potentially updated song
        num_segments_after = len(current_song.segments) if current_song else 0

        if num_segments_after == 0:
            self.selected_segment_index = None
            self.selected_parameter_key = None
            self.focused_column = FocusColumn.SEGMENT_LIST
        else:
            # Try to select the segment that was just before the lowest deleted index
            # Or the segment that was at the original anchor position if it still exists
            lowest_deleted_index = sorted_indices[-1]
            new_selection_index = min(lowest_deleted_index, num_segments_after - 1)
            # Alternative: try to keep anchor if possible
            # if original_anchor is not None and original_anchor < num_segments_after:
            #     new_selection_index = original_anchor
            # else: # Fallback if anchor was deleted or out of bounds
            #     new_selection_index = min(lowest_deleted_index, num_segments_after - 1)

            self.selected_segment_index = max(0, new_selection_index) # Ensure it's not negative

        self._adjust_segment_scroll()
        self._ensure_parameter_selection()
        self._update_leds()

    # <<< NEW METHOD: Handle Load/Queue Segment Action >>>
    def _handle_load_queue_segment(self):
        """
        Handles the action for A_BTN_12_CC press (when STOP is not held).
        Loads the selected segment immediately if stopped, or queues it if playing.
        """
        if self.selected_segment_index is None:
            self.set_feedback("No segment selected", is_error=True)
            return

        current_song = self.song_service.get_current_song()
        if not current_song or not (0 <= self.selected_segment_index < len(current_song.segments)):
            self.set_feedback("Invalid segment selection", is_error=True)
            return

        segment_index_to_use = self.selected_segment_index
        segment_num_display = segment_index_to_use + 1

        try:
            if self.app.is_playing:
                # Transport is Active: Queue the segment
                print(f"UI: Requesting queue override for segment {segment_num_display}")
                self.app.queue_segment_override(segment_index_to_use)
                # Feedback is handled by the app method now
                # self.set_feedback(f"Queued Segment {segment_num_display} for next transition", duration=2.0)
            else:
                # Transport is Inactive: Load the segment immediately
                print(f"UI: Requesting immediate load for segment {segment_num_display}")
                self.app.load_segment_immediately(segment_index_to_use)
                # Feedback is handled by the app method now
                # self.set_feedback(f"Loaded Segment {segment_num_display} (Transport Stopped)", duration=2.0)

            # Optional: Update LEDs if the action changes relevant state
            self._update_leds()

        except Exception as e:
            error_msg = f"Error loading/queuing segment: {e}"
            self.set_feedback(error_msg, is_error=True)
            print(f"Error in _handle_load_queue_segment: {e}")
            traceback.print_exc()
    # <<< END NEW METHOD >>>

    # --- END Modified/New Helpers ---

    def _reset_selection_on_error(self):
        """Resets selection state after an error."""
        current_song = self.song_service.get_current_song()
        if current_song and current_song.segments:
            self.selected_segment_index = 0
            self.selected_parameter_key = self.parameter_keys[0] if self.parameter_keys else None
        else:
            self.selected_segment_index = None
            self.selected_parameter_key = None
        self.focused_column = FocusColumn.SEGMENT_LIST
        self.segment_scroll_offset = 0
        self.parameter_scroll_offset = 0
        self._update_leds()

    def _ensure_parameter_selection(self):
        """Ensures a parameter is selected if possible."""
        if self.selected_segment_index is not None and self.parameter_keys:
             if self.selected_parameter_key not in self.parameter_keys:
                 self.selected_parameter_key = self.parameter_keys[0]
                 self.parameter_scroll_offset = 0
        elif self.selected_segment_index is None:
             self.selected_parameter_key = None
             self.parameter_scroll_offset = 0


    # --- Exit Prompt Handling ---
    def can_deactivate(self) -> bool:
        """Checks if the screen can be deactivated. Always returns True now."""
        return True

    # --- Drawing Methods ---
    # <<< Updated draw signature to match BaseScreen >>>
    def draw(self, screen_surface: pygame.Surface,
             midi_status: Optional[str] = None,
             song_status: Optional[str] = None,
             duration_status: Optional[str] = None,
             osc_status: Optional[str] = None,
             play_symbol: Optional[str] = None,
             seg_text: Optional[str] = None,
             rep_text: Optional[str] = None,
             beat_text: Optional[str] = None,
             tempo_text: Optional[str] = None,
             current_playing_segment_index: Optional[int] = None):
        """Draw the song editing screen content, including playback status."""
        if self.text_input_widget.is_active:
            self.text_input_widget.draw(screen_surface)
        else:
            # Pass all status info down
            self._draw_normal_content(screen_surface, midi_status, song_status, duration_status, osc_status,
                                      play_symbol, seg_text, rep_text, beat_text, tempo_text,
                                      current_playing_segment_index)
            self._draw_feedback(screen_surface) # Feedback drawn on top of status

    # <<< Updated signature >>>
    def _draw_normal_content(self, screen_surface: pygame.Surface,
                             midi_status: Optional[str] = None,
                             song_status: Optional[str] = None,
                             duration_status: Optional[str] = None,
                             osc_status: Optional[str] = None,
                             play_symbol: Optional[str] = None,
                             seg_text: Optional[str] = None,
                             rep_text: Optional[str] = None,
                             beat_text: Optional[str] = None,
                             tempo_text: Optional[str] = None,
                             current_playing_segment_index: Optional[int] = None):
        """Draws the main content: title, segments, parameters, and playback status."""
        current_song = self.song_service.get_current_song()

        # --- Draw Title ---
        title_text = song_status or "Song: ?"
        title_surf = self.font_large.render(title_text, True, WHITE)
        self.title_rect = title_surf.get_rect(midtop=(screen_surface.get_width() // 2, TOP_MARGIN))
        screen_surface.blit(title_surf, self.title_rect)

        # --- Calculate layout areas (Adjusted for playback status area) ---
        list_area_top = self.title_rect.bottom + LIST_TOP_PADDING
        # <<< REDUCED height for lists >>>
        available_list_height = screen_surface.get_height() - list_area_top - FEEDBACK_AREA_HEIGHT - PLAYBACK_STATUS_AREA_HEIGHT
        available_list_height = max(0, available_list_height) # Ensure non-negative

        seg_list_rect = pygame.Rect(LEFT_MARGIN, list_area_top, SEGMENT_LIST_WIDTH, available_list_height)
        param_detail_rect = pygame.Rect(PARAM_AREA_X, list_area_top,
                                        screen_surface.get_width() - PARAM_AREA_X - LEFT_MARGIN, available_list_height)

        # --- Draw Segment List (Pass playback info) ---
        self._draw_segment_list(screen_surface, seg_list_rect, current_song, play_symbol, current_playing_segment_index)

        # --- Draw Parameter Details ---
        self._draw_parameter_details(screen_surface, param_detail_rect, current_song)

        # --- Draw Column Focus Borders ---
        if self.focused_column == FocusColumn.SEGMENT_LIST:
            pygame.draw.rect(screen_surface, FOCUS_BORDER_COLOR, seg_list_rect, COLUMN_BORDER_WIDTH)
            pygame.draw.rect(screen_surface, WHITE, param_detail_rect, COLUMN_BORDER_WIDTH)
        else:
            pygame.draw.rect(screen_surface, WHITE, seg_list_rect, COLUMN_BORDER_WIDTH)
            pygame.draw.rect(screen_surface, FOCUS_BORDER_COLOR, param_detail_rect, COLUMN_BORDER_WIDTH)

        # --- Draw Playback Status Area ---
        playback_area_rect = pygame.Rect(
            0, screen_surface.get_height() - FEEDBACK_AREA_HEIGHT - PLAYBACK_STATUS_AREA_HEIGHT,
            screen_surface.get_width(), PLAYBACK_STATUS_AREA_HEIGHT
        )
        self._draw_playback_status(screen_surface, playback_area_rect,
                                   play_symbol, seg_text, rep_text, beat_text, tempo_text)


    # <<< Updated signature and logic >>>
    def _draw_segment_list(self, screen, area_rect: pygame.Rect, current_song,
                           play_symbol: Optional[str], current_playing_segment_index: Optional[int]):
        """Draws the scrollable segment list, highlighting multi-select, playback, and queued segments."""
        if not current_song:
             no_song_surf = self.font.render("No Song Loaded", True, ERROR_COLOR)
             no_song_rect = no_song_surf.get_rect(center=area_rect.center)
             screen.blit(no_song_surf, no_song_rect)
             return
        if not current_song.segments:
            no_seg_surf = self.font_small.render("No Segments", True, WHITE)
            no_seg_rect = no_seg_surf.get_rect(center=area_rect.center)
            screen.blit(no_seg_surf, no_seg_rect)
            return

        max_visible = self._get_max_visible_segments()
        num_segments = len(current_song.segments)
        start_index = self.segment_scroll_offset
        end_index = min(start_index + max_visible, num_segments)

        # Draw scroll arrows
        if self.segment_scroll_offset > 0:
            self._draw_scroll_arrow(screen, area_rect, 'up')
        if end_index < num_segments:
            self._draw_scroll_arrow(screen, area_rect, 'down')

        text_y = area_rect.top + LIST_TOP_PADDING
        for i in range(start_index, end_index):
            segment = current_song.segments[i]
            is_selected_anchor = (i == self.selected_segment_index)
            is_multi_selected = (i in self.multi_select_indices)
            is_playing = (i == current_playing_segment_index)
            is_focused = (self.focused_column == FocusColumn.SEGMENT_LIST)

            # <<< ADDED: Check if segment is queued >>>
            is_queued_override = (i == self.app.pending_override_segment_index)
            is_queued_normal = (self.app.next_segment_prepared and i == self.app.prepared_next_segment_index)
            is_queued = is_queued_override or is_queued_normal
            # <<< END ADDED >>>

            # Determine background color and text color
            bg_color = None
            text_color = WHITE # Default text color

            # <<< MODIFIED: Prioritize flashing highlight >>>
            if is_queued and self.flash_on:
                bg_color = QUEUED_FLASH_COLOR
                text_color = BLACK # Make text visible on flash background
            # <<< END MODIFIED >>>
            elif is_focused: # Apply normal focus/selection highlights if not flashing
                if is_selected_anchor and is_multi_selected:
                    bg_color = MULTI_SELECT_ANCHOR_COLOR # Anchor in multi-select (focused)
                    text_color = BLACK
                elif is_multi_selected:
                    bg_color = MULTI_SELECT_COLOR # Part of multi-select (focused)
                    text_color = BLACK
                elif is_selected_anchor:
                    bg_color = GREY # Single selection (focused)
                    text_color = HIGHLIGHT_COLOR
            else: # Not focused
                if is_selected_anchor and is_multi_selected:
                    #bg_color = MULTI_SELECT_ANCHOR_COLOR # Anchor in multi-select (unfocused) - Use same color?
                    text_color = MULTI_SELECT_ANCHOR_COLOR
                elif is_multi_selected:
                    #bg_color = MULTI_SELECT_COLOR # Part of multi-select (unfocused) - Use same color?
                    text_color = MULTI_SELECT_COLOR
                elif is_selected_anchor:
                    #bg_color = GREY # Single selection (unfocused)
                    text_color = HIGHLIGHT_COLOR # Keep text white on grey

            # Draw background highlight if needed
            if bg_color:
                pygame.draw.rect(screen, bg_color, (area_rect.left + 1, text_y, area_rect.width - 2, LINE_HEIGHT))

            # Draw Play Symbol if playing
            play_symbol_surf = None
            play_symbol_rect = None
            if is_playing and play_symbol:
                play_color = GREEN if play_symbol == ">" else RED
                # Ensure play symbol is visible on flash background
                if is_queued and self.flash_on:
                     play_color = WHITE if play_color == BLACK else play_color # Adjust if needed
                play_symbol_surf = self.font.render(play_symbol, True, play_color)
                play_symbol_rect = play_symbol_surf.get_rect(left=area_rect.left + 5, centery=text_y + LINE_HEIGHT // 2)
                screen.blit(play_symbol_surf, play_symbol_rect)


            # Segment Text (adjust x based on play symbol)
            text_x = area_rect.left + 5
            if play_symbol_rect:
                text_x = play_symbol_rect.right + 5

            dirty_flag = "*" if segment.dirty else ""
            seg_num_str = f"{i + 1:02d}"
            prog1_str = value_to_elektron_format(segment.program_message_1)
            prog2_str = value_to_elektron_format(segment.program_message_2)
            seg_text = f"{seg_num_str}{dirty_flag} {prog1_str}/{prog2_str}"

            seg_surf = self.font.render(seg_text, True, text_color) # Use determined text_color
            seg_rect = seg_surf.get_rect(left=text_x, centery=text_y + LINE_HEIGHT // 2)
            screen.blit(seg_surf, seg_rect)

            text_y += LINE_HEIGHT

    # <<< Updated signature >>>
    def _draw_parameter_details(self, screen, area_rect: pygame.Rect, current_song):
        """Draws the scrollable parameter list for the selected segment."""
        if self.selected_segment_index is None:
            no_sel_surf = self.font_small.render("Select Segment", True, GREY)
            no_sel_rect = no_sel_surf.get_rect(center=area_rect.center)
            screen.blit(no_sel_surf, no_sel_rect)
            return
        if not current_song or not self.parameter_keys:
            # Handle case where song exists but has no params defined (unlikely)
            return

        try:
            segment = current_song.segments[self.selected_segment_index]
            max_visible = self._get_max_visible_parameters() # <<< REMOVED area_rect argument
            num_params = len(self.parameter_keys)
            start_index = self.parameter_scroll_offset
            end_index = min(start_index + max_visible, num_params)

            # Draw scroll arrows if needed
            if self.parameter_scroll_offset > 0:
                self._draw_scroll_arrow(screen, area_rect, 'up')
            if end_index < num_params:
                self._draw_scroll_arrow(screen, area_rect, 'down')

            text_y = area_rect.top + LIST_TOP_PADDING
            for i in range(start_index, end_index):
                key = self.parameter_keys[i]
                display_name = self.parameter_display_names.get(key, key)
                value = getattr(segment, key, 'N/A')

                # Format value
                if key in ['program_message_1', 'program_message_2']:
                    value_str = value_to_elektron_format(value) if isinstance(value, int) else str(value)
                elif key == 'tempo':
                    value_str = f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
                elif key == 'automatic_transport_interrupt':
                    value_str = "ON" if value else "OFF"
                else:
                    value_str = str(value)

                param_dirty_flag = "*" if key in segment.dirty_params else "" # <<< ADD param dirty flag check
                param_text = f"{param_dirty_flag}{display_name}: {value_str}" # <<< Prepend dirty flag

                is_selected = (key == self.selected_parameter_key)
                is_focused = (self.focused_column == FocusColumn.PARAMETER_DETAILS) # <<< Check focus
                text_color = WHITE # Default
                bg_color = None # Default

                if is_selected:
                    if is_focused:
                        bg_color = GREY # <<< Use GREY for focused background
                        text_color = HIGHLIGHT_COLOR # <<< Use HIGHLIGHT_COLOR for focused text
                    else: # Selected but not focused
                        text_color = HIGHLIGHT_COLOR # <<< Use HIGHLIGHT_COLOR for non-focused selected text

                # Draw background highlight if selected and focused
                if bg_color: # Only draw background when focused
                    pygame.draw.rect(screen, bg_color, (area_rect.left + 1, text_y, area_rect.width - 2, LINE_HEIGHT))

                param_surf = self.font.render(param_text, True, text_color) # <<< Use determined text_color
                param_rect = param_surf.get_rect(left=area_rect.left + PARAM_INDENT, centery=text_y + LINE_HEIGHT // 2)
                screen.blit(param_surf, param_rect)

                text_y += LINE_HEIGHT

        except (IndexError, AttributeError, TypeError) as e:
            error_surf = self.font_small.render(f"Error: {e}", True, ERROR_COLOR)
            error_rect = error_surf.get_rect(center=area_rect.center)
            screen.blit(error_surf, error_rect)
            print(f"Error drawing parameters: {e}")
            traceback.print_exc()

    # <<< NEW METHOD to draw playback status >>>
    def _draw_playback_status(self, screen, area_rect: pygame.Rect,
                              play_symbol: Optional[str], seg_text: Optional[str],
                              rep_text: Optional[str], beat_text: Optional[str],
                              tempo_text: Optional[str]):
        """Draws the playback status information in the specified area."""
        # Optional: Draw a faint background or separator line
        # pygame.draw.rect(screen, GREY, area_rect, 1) # Example border
        pygame.draw.line(screen, GREY, area_rect.topleft, area_rect.topright, 1)

        # Use a slightly smaller font for status details
        status_font = self.font_medium # Or self.font_small

        # Defaults
        play_symbol = play_symbol or "?"
        seg_text = seg_text or "Seg: -/-"
        rep_text = rep_text or "Rep: -/-"
        beat_text = beat_text or "Beat: -"
        tempo_text = tempo_text or "Tempo: -"

        # Colors
        play_color = GREEN if play_symbol == ">" else RED
        text_color = WHITE
        # <<< ADDED: Hold status color >>>
        hold_color = HIGHLIGHT_COLOR if self.app.hold_active else GREY # Use highlight color when active

        # Layout items horizontally
        padding = 15 # Reduced padding slightly
        x_pos = area_rect.left + LEFT_MARGIN

        # 1. Play Symbol
        play_surf = self.font_large.render(play_symbol, True, play_color)
        play_rect = play_surf.get_rect(left=x_pos, centery=area_rect.centery)
        screen.blit(play_surf, play_rect)
        x_pos = play_rect.right + padding

        # <<< ADDED: Hold Indicator >>>
        hold_surf = status_font.render("HOLD", True, hold_color)
        hold_rect = hold_surf.get_rect(left=x_pos, centery=area_rect.centery)
        screen.blit(hold_surf, hold_rect)
        x_pos = hold_rect.right + padding
        # <<< END ADDED >>>

        # 2. Segment
        seg_surf = status_font.render(seg_text, True, text_color)
        seg_rect = seg_surf.get_rect(left=x_pos, centery=area_rect.centery)
        screen.blit(seg_surf, seg_rect)
        x_pos = seg_rect.right + padding

        # 3. Repetition
        rep_surf = status_font.render(rep_text, True, text_color)
        rep_rect = rep_surf.get_rect(left=x_pos, centery=area_rect.centery)
        screen.blit(rep_surf, rep_rect)
        x_pos = rep_rect.right + padding

        # 4. Beat
        beat_surf = status_font.render(beat_text, True, text_color)
        beat_rect = beat_surf.get_rect(left=x_pos, centery=area_rect.centery)
        screen.blit(beat_surf, beat_rect)
        x_pos = beat_rect.right + padding

        # 5. Tempo
        tempo_surf = status_font.render(tempo_text, True, text_color)
        tempo_rect = tempo_surf.get_rect(left=x_pos, centery=area_rect.centery)
        if tempo_rect.right > area_rect.right - LEFT_MARGIN:
             tempo_rect.right = area_rect.right - LEFT_MARGIN
        screen.blit(tempo_surf, tempo_rect)

    # <<< END NEW METHOD >>>

    def _draw_feedback(self, screen):
        """Draws the feedback message at the bottom (now above playback status)."""
        if self.feedback_message:
            message, timestamp, color = self.feedback_message
            feedback_surf = self.font_small.render(message, True, color)
            # Position feedback just above the playback status area
            feedback_rect = feedback_surf.get_rect(
                centerx=screen.get_width() // 2,
                bottom=screen.get_height() - PLAYBACK_STATUS_AREA_HEIGHT - 5 # 5px padding
            )
            # Optional: Add a background to feedback for better visibility
            bg_rect = feedback_rect.inflate(10, 4)
            pygame.draw.rect(screen, BLACK, bg_rect) # Black background
            screen.blit(feedback_surf, feedback_rect)


    def _draw_scroll_arrow(self, screen, area_rect, direction):
        """Draws an up or down scroll arrow."""
        arrow_char = "^" if direction == 'up' else "v"
        arrow_surf = self.font_tiny.render(arrow_char, True, WHITE) # Use tiny font
        if direction == 'up':
             arrow_rect = arrow_surf.get_rect(centerx=area_rect.centerx, top=area_rect.top + 2)
        else: # down
             arrow_rect = arrow_surf.get_rect(centerx=area_rect.centerx, bottom=area_rect.bottom - 2)
        screen.blit(arrow_surf, arrow_rect)


    # --- List Size Calculation (Adjusted for playback status area) ---
    def _get_max_visible_items(self) -> int:
        # Height is now passed via the rect
        available_height = self.app.screen.get_height() - (2 * LIST_TOP_PADDING) # Use rect's height
        # Height reserved for feedback and playback status at the bottom
        bottom_reserved_height = FEEDBACK_AREA_HEIGHT + PLAYBACK_STATUS_AREA_HEIGHT
        available_height = max(0, available_height - bottom_reserved_height) # Ensure non-negative

        if available_height <= 0 or LINE_HEIGHT <= 0:
            return 0 # Return 0 if no space
        return max(1, available_height // LINE_HEIGHT) # Floor division

    # <<< Modified to remove area_rect parameter >>>
    def _get_max_visible_segments(self) -> int:
        """Calculates max visible segments based on available height."""
        return self._get_max_visible_items()

    # <<< Modified to remove area_rect parameter >>>
    def _get_max_visible_parameters(self) -> int:
        """Calculates max visible parameters based on available height."""
        return self._get_max_visible_items()
