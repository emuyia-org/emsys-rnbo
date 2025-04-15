# emsys/ui/song_edit_screen.py
# -*- coding: utf-8 -*-
"""
Screen for viewing and editing Song objects.
Uses helpers for parameter editing and LED feedback.
"""
import pygame
import time
from typing import List, Optional, Tuple, Any, Dict
from enum import Enum, auto

# Core components
from ..core.song import Song, Segment # Keep direct access to Song/Segment structure
from ..utils import file_io # For saving
from ..config import settings, mappings

# Base class and widgets
from .base_screen import BaseScreen
from .widgets import TextInputWidget, TextInputStatus, FocusColumn

# --- Import Helpers ---
from .helpers.led_feedback_handler import LedFeedbackHandler
from .helpers.parameter_editor import ParameterEditor
# --------------------

# Import colors and constants
from emsys.config.settings import (ERROR_COLOR, FEEDBACK_COLOR, HIGHLIGHT_COLOR,
                                   BLACK, WHITE, GREY, BLUE, FOCUS_BORDER_COLOR,
                                   FEEDBACK_AREA_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT) # Add SCREEN_WIDTH/HEIGHT if needed

# Define layout constants (Keep layout definitions here)
LEFT_MARGIN = 15
TOP_MARGIN = 15
LINE_HEIGHT = 36
PARAM_INDENT = 30
SEGMENT_LIST_WIDTH = 180
PARAM_AREA_X = LEFT_MARGIN + SEGMENT_LIST_WIDTH + 15
COLUMN_BORDER_WIDTH = 2
LIST_TOP_PADDING = 10

# Helper to convert program change value to display format
def value_to_elektron_format(value: int) -> str:
    """Converts a MIDI program change value (0-127) to Elektron format (A01-H16)."""
    if not 0 <= value <= 127: return "INV"
    bank_index = value // 16
    patch_number = value % 16
    bank_letter = chr(ord('A') + bank_index)
    patch_str = f"{patch_number + 1:02d}"
    return f"{bank_letter}{patch_str}"


class SongEditScreen(BaseScreen):
    """Screen for editing song structure and segment parameters."""

    def __init__(self, app_ref):
        """Initialize the song editing screen."""
        super().__init__(app_ref)
        # --- Initialize Helpers ---
        self.led_handler = LedFeedbackHandler(app_ref)
        self.param_editor = ParameterEditor()
        # -------------------------

        # --- Fonts ---
        self.font_large = pygame.font.Font(None, 48)
        self.font_small = pygame.font.Font(None, 32)
        self.font = pygame.font.Font(None, 36)
        # Store title rect for positioning calculations
        self.title_rect = pygame.Rect(0,0,0,0)

        # --- State ---
        self.current_song: Optional[Song] = None
        self.selected_segment_index: Optional[int] = None
        self.selected_parameter_key: Optional[str] = None
        self.focused_column: FocusColumn = FocusColumn.SEGMENT_LIST
        self.segment_scroll_offset: int = 0
        self.parameter_scroll_offset: int = 0
        self.feedback_message: Optional[Tuple[str, float, Tuple[int, int, int]]] = None
        self.feedback_duration: float = 2.0
        self.exit_prompt_active: bool = False
        # Renaming is not handled here, but text input widget might be used by future features
        self.text_input_widget = TextInputWidget(app_ref) # Keep instance for potential future use

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
        """Called when the screen becomes active. Load the current song."""
        super().init()
        print(f"{self.__class__.__name__} is now active.")
        # Get current song from the main app reference
        self.current_song = getattr(self.app, 'current_song', None)

        # Initialize selection state
        if self.current_song and self.current_song.segments:
            self.selected_segment_index = 0
            self.selected_parameter_key = self.parameter_keys[0] if self.parameter_keys else None
        else:
            self.selected_segment_index = None
            self.selected_parameter_key = None

        # Reset screen-specific state
        self.focused_column = FocusColumn.SEGMENT_LIST
        self.exit_prompt_active = False
        self.segment_scroll_offset = 0
        self.parameter_scroll_offset = 0
        self.clear_feedback()
        self.text_input_widget.cancel() # Ensure inactive

        if not self.current_song:
            self.set_feedback("No song loaded!", is_error=True, duration=5.0)

        self._update_leds() # Update LEDs on activation

    def cleanup(self):
        """Called when the screen becomes inactive."""
        super().cleanup()
        print(f"{self.__class__.__name__} is being deactivated.")
        self.exit_prompt_active = False
        self.text_input_widget.cancel()
        self.clear_feedback()
        # Optionally turn off LEDs specifically for this screen
        # self.app.send_midi_cc(control=16, value=0) # Or use led_handler if it has an 'off' method

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
        """Update screen state, like clearing timed feedback."""
        super().update()
        if self.feedback_message and (time.time() - self.feedback_message[1] > self.feedback_duration):
            self.clear_feedback()

    def handle_midi(self, msg):
        """Handle MIDI messages delegated from the main app."""
        if msg.type != 'control_change':
             return # Ignore non-CC messages for now

        cc = msg.control
        value = msg.value

        # --- Handle Text Input Mode FIRST (if ever used) ---
        if self.text_input_widget.is_active:
            if value == 127: # Only react to button presses
                 # status = self.text_input_widget.handle_input(cc)
                 # Handle status based on widget's purpose (currently none)
                 pass
            return # Don't process other actions while text input is active

        # --- Handle Exit Confirmation Prompt ---
        if self.exit_prompt_active:
            if value == 127: # Button press
                if cc == mappings.SAVE_CC: self._save_and_exit()
                elif cc == mappings.DELETE_CC: self._discard_and_exit()
                elif cc == mappings.NO_NAV_CC: self._cancel_exit()
            return

        # --- Handle Fader for Selection ---
        if cc == mappings.FADER_SELECT_CC:
            self._handle_fader_selection(value)
            return

        # --- Handle Encoder Rotation for Parameter Adjustment ---
        if cc == mappings.KNOB_B8_CC: # Assuming B8 is the primary editing encoder
            direction = 0
            # Determine direction based on relative value (adjust if different encoder type)
            if 1 <= value <= 63: direction = 1 # Clockwise / Increment
            elif 65 <= value <= 127: direction = -1 # Counter-clockwise / Decrement

            if direction != 0:
                self._modify_parameter_via_encoder(direction)
            return

        # --- Normal Edit Mode Handling (Button Presses Only) ---
        if value != 127:
            return # Ignore CC releases or other values for buttons

        # --- Action Buttons ---
        if cc == mappings.SAVE_CC:
            self._save_current_song()
        elif cc == mappings.CREATE_CC:
            self._add_new_segment()
        elif cc == mappings.DELETE_CC:
            # DELETE behavior depends on focus
            if self.focused_column == FocusColumn.SEGMENT_LIST:
                self._delete_current_segment()
            elif self.focused_column == FocusColumn.PARAMETER_DETAILS:
                self._reset_or_copy_parameter() # Use DELETE to reset/copy parameter
        # --- Navigation Buttons ---
        elif cc == mappings.DOWN_NAV_CC:
            if self.focused_column == FocusColumn.SEGMENT_LIST: self._change_selected_segment(1)
            else: self._change_selected_parameter_vertically(1)
        elif cc == mappings.UP_NAV_CC:
            if self.focused_column == FocusColumn.SEGMENT_LIST: self._change_selected_segment(-1)
            else: self._change_selected_parameter_vertically(-1)
        elif cc == mappings.RIGHT_NAV_CC:
            self._navigate_focus(1)
        elif cc == mappings.LEFT_NAV_CC:
            self._navigate_focus(-1)
        # --- Parameter Modification Buttons (YES/NO) ---
        elif cc == mappings.YES_NAV_CC:
            # Increment focused parameter (or toggle boolean)
            if self.focused_column == FocusColumn.PARAMETER_DETAILS:
                self._modify_parameter_via_button(1)
        elif cc == mappings.NO_NAV_CC:
            # Decrement focused parameter
             if self.focused_column == FocusColumn.PARAMETER_DETAILS:
                self._modify_parameter_via_button(-1)
        # else: Unhandled button press

    # --- Helper to update LEDs using the handler ---
    def _update_leds(self):
        """Calls the LED handler to update controller feedback."""
        self.led_handler.update_encoder_led(
            self.current_song,
            self.selected_segment_index,
            self.selected_parameter_key
        )

    # --- Parameter Modification ---
    def _modify_parameter(self, direction: int):
        """Common logic to modify parameter using the editor."""
        if self.focused_column != FocusColumn.PARAMETER_DETAILS:
            return # Can only modify when parameter column is focused

        new_value, status, changed = self.param_editor.modify_parameter(
            self.current_song, self.selected_segment_index, self.selected_parameter_key, direction
        )

        if new_value is not None: # Modification attempted (even if no change)
            if changed:
                self._update_leds() # Update LED on successful change
                # Format feedback message
                key = self.selected_parameter_key
                display_name = self.parameter_display_names.get(key, key)
                if key in ['program_message_1', 'program_message_2']:
                    value_str = value_to_elektron_format(int(new_value))
                elif isinstance(new_value, bool):
                    value_str = "ON" if new_value else "OFF"
                elif isinstance(new_value, float):
                     value_str = f"{new_value:.1f}"
                else:
                    value_str = str(new_value)
                self.set_feedback(f"{display_name}: {value_str}", duration=0.75)
            elif status in ["At Min", "At Max"]:
                 key = self.selected_parameter_key
                 display_name = self.parameter_display_names.get(key, key)
                 self.set_feedback(f"{display_name}: {status.lower()}", duration=0.5)
                 # Ensure LED is correct even at limit
                 self._update_leds()
            # else: Status "OK" but not changed (e.g., trying to increment bool) - no feedback needed
        else:
            # An error occurred during modification
            self.set_feedback(status, is_error=True) # Status contains the error message

    def _modify_parameter_via_encoder(self, direction: int):
        """Modify using encoder (calls common logic)."""
        self._modify_parameter(direction)

    def _modify_parameter_via_button(self, direction: int):
        """Modify using +/- buttons (calls common logic)."""
        # Special case: If the parameter is boolean, YES/NO both just toggle it.
        # The modify_parameter helper handles the toggling logic.
        if self.selected_parameter_key == 'automatic_transport_interrupt':
             self._modify_parameter(1) # Pass direction 1 to trigger bool toggle logic
        else:
            self._modify_parameter(direction) # Use actual direction for non-booleans

    def _reset_or_copy_parameter(self):
        """Resets or copies the selected parameter using the editor."""
        if self.focused_column != FocusColumn.PARAMETER_DETAILS: return

        new_value, status, changed = self.param_editor.reset_or_copy_parameter(
            self.current_song, self.selected_segment_index, self.selected_parameter_key
        )

        self.set_feedback(status) # Display status (e.g., "Copied", "Reset", "Matches", "Error")
        if changed:
            self._update_leds()

    # --- Navigation and Selection ---
    def _handle_fader_selection(self, fader_value: int):
        """Handles selection changes via the fader."""
        if not self.current_song: return

        reversed_value = 127 - fader_value

        if self.focused_column == FocusColumn.SEGMENT_LIST:
            if not self.current_song.segments: return
            num_items = len(self.current_song.segments)
            target_index = max(0, min(num_items - 1, int((reversed_value / 128.0) * num_items)))
            if target_index != self.selected_segment_index:
                self.selected_segment_index = target_index
                self._adjust_segment_scroll()
                # Preserve parameter selection when segment changes via fader
                # self._ensure_parameter_selection() # Keep existing param selected
                self.clear_feedback()
                self._update_leds() # Update LED for potentially new segment's value

        elif self.focused_column == FocusColumn.PARAMETER_DETAILS:
            if self.selected_segment_index is None or not self.parameter_keys: return
            num_items = len(self.parameter_keys)
            target_param_index = max(0, min(num_items - 1, int((reversed_value / 128.0) * num_items)))
            target_key = self.parameter_keys[target_param_index]
            if target_key != self.selected_parameter_key:
                self.selected_parameter_key = target_key
                self._adjust_parameter_scroll()
                self.clear_feedback()
                self._update_leds() # Update LED for new parameter

    def _navigate_focus(self, direction: int):
        """Change focus between columns."""
        if direction > 0 and self.focused_column == FocusColumn.SEGMENT_LIST:
            self.focused_column = FocusColumn.PARAMETER_DETAILS
        elif direction < 0 and self.focused_column == FocusColumn.PARAMETER_DETAILS:
            self.focused_column = FocusColumn.SEGMENT_LIST
        else:
            return # No change

        self.clear_feedback()
        self._update_leds() # Update LED based on new focus

    def _change_selected_segment(self, direction: int):
        """Change the selected segment index and handle scrolling."""
        if not self.current_song or not self.current_song.segments: return

        num_segments = len(self.current_song.segments)
        if self.selected_segment_index is None: # Select first/last if none selected
            self.selected_segment_index = 0 if direction > 0 else num_segments - 1
        else:
            self.selected_segment_index = (self.selected_segment_index + direction + num_segments) % num_segments

        self._adjust_segment_scroll()
        # self._ensure_parameter_selection() # Keep parameter selected
        self.clear_feedback()
        self._update_leds() # Update LED for potentially new value

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
        self._update_leds() # Update LED for the new parameter

    def _adjust_segment_scroll(self):
        """Adjust segment scroll offset based on selection."""
        if self.selected_segment_index is None: return
        max_visible = self._get_max_visible_segments()
        num_segments = len(self.current_song.segments) if self.current_song else 0
        if num_segments <= max_visible:
            self.segment_scroll_offset = 0
            return

        # Scroll down if selection is below visible area
        if self.selected_segment_index >= self.segment_scroll_offset + max_visible:
            self.segment_scroll_offset = self.selected_segment_index - max_visible + 1
        # Scroll up if selection is above visible area
        elif self.selected_segment_index < self.segment_scroll_offset:
            self.segment_scroll_offset = self.selected_segment_index
        # Ensure offset doesn't go out of bounds
        self.segment_scroll_offset = max(0, min(self.segment_scroll_offset, num_segments - max_visible))


    def _adjust_parameter_scroll(self):
        """Adjust parameter scroll offset based on selection."""
        if self.selected_parameter_key is None or not self.parameter_keys: return
        max_visible = self._get_max_visible_parameters()
        num_params = len(self.parameter_keys)
        if num_params <= max_visible:
            self.parameter_scroll_offset = 0
            return

        try:
            current_param_index = self.parameter_keys.index(self.selected_parameter_key)
        except ValueError:
            return # Should not happen

        # Scroll down
        if current_param_index >= self.parameter_scroll_offset + max_visible:
            self.parameter_scroll_offset = current_param_index - max_visible + 1
        # Scroll up
        elif current_param_index < self.parameter_scroll_offset:
            self.parameter_scroll_offset = current_param_index
        # Ensure offset doesn't go out of bounds
        self.parameter_scroll_offset = max(0, min(self.parameter_scroll_offset, num_params - max_visible))

    # --- Song/Segment Actions ---
    def _save_current_song(self):
        """Saves the current song to disk."""
        if not self.current_song:
            self.set_feedback("No song loaded to save", is_error=True)
            return False

        if not self.current_song.dirty:
            self.set_feedback(f"'{self.current_song.name}' has no changes.")
            return True

        self.set_feedback(f"Saving '{self.current_song.name}'...")
        pygame.display.flip() # Show feedback immediately

        if file_io.save_song(self.current_song):
            self.set_feedback(f"Saved '{self.current_song.name}' successfully.")
            # file_io.save_song should set song.dirty = False
            # Explicitly clear segment dirty flags *after* successful save
            self.current_song.clear_segment_dirty_flags() # Clear param flags too
            return True
        else:
            # Error message printed by save_song
            self.set_feedback(f"Failed to save '{self.current_song.name}'", is_error=True)
            return False

    def _add_new_segment(self):
        """Adds a new segment after the selected one or at the start."""
        if not self.current_song:
            self.set_feedback("No song loaded", is_error=True)
            return

        try:
            new_segment = Segment() # Create with defaults
            insert_index = 0 # Default to beginning

            # Determine insertion index and copy parameters if a segment is selected
            if self.selected_segment_index is not None and self.current_song.segments:
                insert_index = self.selected_segment_index + 1
                try:
                    source_segment = self.current_song.get_segment(self.selected_segment_index)
                    # Copy parameters using ParameterEditor's knowledge? Or simple getattr?
                    for key in self.parameter_keys: # Use defined keys
                        if hasattr(source_segment, key):
                            setattr(new_segment, key, getattr(source_segment, key))
                    print(f"Copied parameters from segment {self.selected_segment_index + 1}")
                except IndexError:
                    print(f"Warning: Could not get segment at index {self.selected_segment_index} to copy.")
            elif self.current_song.segments: # No selection, but segments exist -> add at end
                 insert_index = len(self.current_song.segments)

            self.current_song.add_segment(new_segment, index=insert_index)
            self.set_feedback(f"Added new segment at {insert_index + 1}")

            # Select the newly added segment and update UI
            self.selected_segment_index = insert_index
            self._adjust_segment_scroll()
            self._ensure_parameter_selection() # Select first parameter
            self._update_leds()

        except Exception as e:
            self.set_feedback(f"Error adding segment: {e}", is_error=True)
            print(f"Error in _add_new_segment: {e}")

    def _delete_current_segment(self):
        """Deletes the currently selected segment."""
        if self.selected_segment_index is None or not self.current_song or not self.current_song.segments:
            self.set_feedback("No segment selected", is_error=True)
            return

        try:
            index_to_delete = self.selected_segment_index
            num_segments_before = len(self.current_song.segments)

            self.current_song.remove_segment(index_to_delete)
            self.set_feedback(f"Deleted Segment {index_to_delete + 1}")

            num_segments_after = len(self.current_song.segments)

            # Adjust selection and focus
            if num_segments_after == 0:
                self.selected_segment_index = None
                self.selected_parameter_key = None
                self.focused_column = FocusColumn.SEGMENT_LIST # Reset focus
            else:
                # Select the segment now at the deleted index, or the last one
                self.selected_segment_index = min(index_to_delete, num_segments_after - 1)
                self._adjust_segment_scroll()
                self._ensure_parameter_selection() # Make sure a param is selected

            self._update_leds()

        except IndexError:
            self.set_feedback("Error deleting segment (index).", is_error=True)
            self._reset_selection_on_error()
        except Exception as e:
            self.set_feedback(f"Error deleting segment: {e}", is_error=True)
            print(f"Unexpected error during segment delete: {e}")

    def _reset_selection_on_error(self):
        """Resets selection state after an error."""
        if self.current_song and self.current_song.segments:
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
                 self.parameter_scroll_offset = 0 # Reset scroll if param resets
        elif self.selected_segment_index is None:
             self.selected_parameter_key = None # No segment, no param
             self.parameter_scroll_offset = 0


    # --- Exit Prompt Handling ---
    def can_deactivate(self) -> bool:
        """Checks if the screen can be deactivated (e.g., no unsaved changes)."""
        if self.current_song and self.current_song.dirty:
            self.exit_prompt_active = True # Activate the prompt
            self.set_feedback("Current song has unsaved changes!", is_error=True)
            return False # Block deactivation
        return True # OK to deactivate

    def _save_and_exit(self):
        """Saves the song and signals readiness to exit."""
        if self._save_current_song():
            self.exit_prompt_active = False
            self.clear_feedback()
            self.app.request_screen_change() # Signal to App/ScreenManager
        else:
            self.set_feedback("Save failed! Cannot exit.", is_error=True)
            # Keep prompt active

    def _discard_and_exit(self):
        """Discards changes and signals readiness to exit."""
        if self.current_song:
            self.current_song.dirty = False # Mark as clean
            self.current_song.clear_segment_dirty_flags()
            # Optionally reload from disk?
            # self.app.current_song = file_io.load_song(self.current_song.name) or None
            self.set_feedback("Changes discarded.")
        self.exit_prompt_active = False
        self.app.request_screen_change()

    def _cancel_exit(self):
        """Cancels the exit attempt."""
        self.exit_prompt_active = False
        self.clear_feedback()
        # No need to call request_screen_change, the pending change was implicitly cancelled

    # --- Drawing Methods ---
    def draw(self, screen, midi_status=None):
        """Draw the song editing screen content or prompts."""
        if self.text_input_widget.is_active:
            self.text_input_widget.draw(screen) # Draw input widget if active
        elif self.exit_prompt_active:
            self._draw_normal_content(screen, midi_status) # Draw screen underneath
            self._draw_exit_prompt(screen) # Draw prompt overlay
        else:
            self._draw_normal_content(screen, midi_status) # Draw normal screen
            self._draw_feedback(screen) # Draw feedback only if no prompt

    def _draw_normal_content(self, screen, midi_status=None):
        """Draws the main content: title, segments, parameters."""
        # Clear screen or assume main loop does
        # screen.fill(BLACK)

        # --- Draw Title ---
        title_text = "Song Editor"
        if self.current_song:
            dirty_flag = "*" if self.current_song.dirty else ""
            title_text = f"Edit: {self.current_song.name}{dirty_flag}"
        title_surf = self.font_large.render(title_text, True, WHITE)
        # Update title_rect here as screen size might change theoretically
        self.title_rect = title_surf.get_rect(midtop=(screen.get_width() // 2, TOP_MARGIN))
        screen.blit(title_surf, self.title_rect)

        # Calculate layout areas
        list_area_top = self.title_rect.bottom + LIST_TOP_PADDING
        available_height = screen.get_height() - list_area_top - FEEDBACK_AREA_HEIGHT
        seg_list_rect = pygame.Rect(LEFT_MARGIN, list_area_top, SEGMENT_LIST_WIDTH, available_height)
        param_detail_rect = pygame.Rect(PARAM_AREA_X, list_area_top,
                                        screen.get_width() - PARAM_AREA_X - LEFT_MARGIN, available_height)

        # --- Draw Segment List ---
        self._draw_segment_list(screen, seg_list_rect)

        # --- Draw Parameter Details ---
        self._draw_parameter_details(screen, param_detail_rect)

        # --- Draw Column Focus Borders ---
        if self.focused_column == FocusColumn.SEGMENT_LIST:
            pygame.draw.rect(screen, FOCUS_BORDER_COLOR, seg_list_rect, COLUMN_BORDER_WIDTH)
            pygame.draw.rect(screen, WHITE, param_detail_rect, COLUMN_BORDER_WIDTH) # Inactive border
        else: # PARAMETER_DETAILS focused
            pygame.draw.rect(screen, WHITE, seg_list_rect, COLUMN_BORDER_WIDTH) # Inactive border
            pygame.draw.rect(screen, FOCUS_BORDER_COLOR, param_detail_rect, COLUMN_BORDER_WIDTH)


    def _draw_segment_list(self, screen, area_rect: pygame.Rect):
        """Draws the scrollable segment list."""
        if not self.current_song: # Draw "No Song Loaded" if applicable
             no_song_surf = self.font.render("No Song Loaded", True, ERROR_COLOR)
             no_song_rect = no_song_surf.get_rect(center=area_rect.center)
             screen.blit(no_song_surf, no_song_rect)
             return
        if not self.current_song.segments: # Draw "No Segments"
            no_seg_surf = self.font_small.render("No Segments", True, WHITE)
            no_seg_rect = no_seg_surf.get_rect(center=area_rect.center)
            screen.blit(no_seg_surf, no_seg_rect)
            return

        max_visible = self._get_max_visible_segments()
        num_segments = len(self.current_song.segments)
        start_index = self.segment_scroll_offset
        end_index = min(start_index + max_visible, num_segments)

        # Draw scroll indicators
        if self.segment_scroll_offset > 0:
            self._draw_scroll_arrow(screen, area_rect, 'up')
        if end_index < num_segments:
            self._draw_scroll_arrow(screen, area_rect, 'down')

        # Draw list items
        text_y = area_rect.top + LIST_TOP_PADDING
        for i in range(start_index, end_index):
            seg = self.current_song.segments[i]
            is_selected = (i == self.selected_segment_index)
            is_focused = (self.focused_column == FocusColumn.SEGMENT_LIST)
            color = HIGHLIGHT_COLOR if (is_selected and is_focused) else WHITE
            dirty_flag = "*" if seg.dirty else ""
            seg_text = f"{i + 1}{dirty_flag}"
            seg_surf = self.font_small.render(seg_text, True, color)
            seg_rect = seg_surf.get_rect(topleft=(area_rect.left + 10, text_y))

            # Draw selection background highlight
            if is_selected and is_focused:
                bg_rect = pygame.Rect(area_rect.left + 2, text_y - 2, area_rect.width - 4, LINE_HEIGHT)
                pygame.draw.rect(screen, GREY, bg_rect)

            screen.blit(seg_surf, seg_rect)
            text_y += LINE_HEIGHT

    def _draw_parameter_details(self, screen, area_rect: pygame.Rect):
        """Draws the scrollable parameter list for the selected segment."""
        if self.selected_segment_index is None:
            no_sel_surf = self.font_small.render("Select Segment", True, WHITE)
            no_sel_rect = no_sel_surf.get_rect(center=area_rect.center)
            screen.blit(no_sel_surf, no_sel_rect)
            return
        if not self.current_song or not self.parameter_keys: return # Should not happen if segment selected

        try:
            current_segment = self.current_song.get_segment(self.selected_segment_index)
            max_visible = self._get_max_visible_parameters()
            num_params = len(self.parameter_keys)
            start_index = self.parameter_scroll_offset
            end_index = min(start_index + max_visible, num_params)

            # Draw scroll indicators
            if self.parameter_scroll_offset > 0:
                self._draw_scroll_arrow(screen, area_rect, 'up')
            if end_index < num_params:
                 self._draw_scroll_arrow(screen, area_rect, 'down')

            # Draw list items
            text_y = area_rect.top + LIST_TOP_PADDING
            for i in range(start_index, end_index):
                param_key = self.parameter_keys[i]
                display_name = self.parameter_display_names.get(param_key, param_key)
                value = getattr(current_segment, param_key, "N/A")

                # Format value for display
                if param_key in ['program_message_1', 'program_message_2']:
                    value_str = value_to_elektron_format(int(value)) if isinstance(value, int) else "ERR"
                elif isinstance(value, bool): value_str = "ON" if value else "OFF"
                elif isinstance(value, float): value_str = f"{value:.1f}"
                else: value_str = str(value)

                param_dirty_flag = "*" if param_key in current_segment.dirty_params else ""
                param_text = f"{param_dirty_flag}{display_name}: {value_str}"

                is_selected = (param_key == self.selected_parameter_key)
                text_color = BLACK if is_selected else WHITE
                bg_color = HIGHLIGHT_COLOR if is_selected else None

                param_surf = self.font.render(param_text, True, text_color)
                param_rect = param_surf.get_rect(topleft=(area_rect.left + PARAM_INDENT, text_y))

                # Draw background highlight
                if bg_color:
                    highlight_rect = param_rect.inflate(10, 2)
                    highlight_rect.left = max(area_rect.left + COLUMN_BORDER_WIDTH, highlight_rect.left)
                    highlight_rect.right = min(area_rect.right - COLUMN_BORDER_WIDTH, highlight_rect.right)
                    pygame.draw.rect(screen, bg_color, highlight_rect)

                screen.blit(param_surf, param_rect)
                text_y += LINE_HEIGHT

        except (IndexError, AttributeError, TypeError) as e:
            # Handle errors fetching segment or attribute
            error_surf = self.font_small.render(f"Error: {e}", True, ERROR_COLOR)
            error_rect = error_surf.get_rect(center=area_rect.center)
            screen.blit(error_surf, error_rect)


    def _draw_feedback(self, screen):
        """Draws the feedback message at the bottom."""
        if self.feedback_message:
            message, timestamp, color = self.feedback_message
            feedback_surf = self.font.render(message, True, color)
            # Position feedback centered horizontally at the bottom
            feedback_rect = feedback_surf.get_rect(centerx=screen.get_width() // 2,
                                                   bottom=screen.get_height() - (FEEDBACK_AREA_HEIGHT // 2) + 5)

            # Optional: Add a background panel for feedback
            bg_rect = pygame.Rect(0, screen.get_height() - FEEDBACK_AREA_HEIGHT,
                                  screen.get_width(), FEEDBACK_AREA_HEIGHT)
            pygame.draw.rect(screen, BLACK, bg_rect) # Black background
            # pygame.draw.rect(screen, color, bg_rect, 1) # Optional border

            screen.blit(feedback_surf, feedback_rect)

    def _draw_exit_prompt(self, screen):
        """Draws the unsaved changes prompt when trying to exit."""
        # Create semi-transparent overlay
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        # Box dimensions and position
        box_width, box_height = 400, 200
        box_x = (screen.get_width() - box_width) // 2
        box_y = (screen.get_height() - box_height) // 2

        # Draw box background and border
        pygame.draw.rect(screen, settings.BLACK, (box_x, box_y, box_width, box_height))
        pygame.draw.rect(screen, settings.BLUE, (box_x, box_y, box_width, box_height), 2)

        # --- Text Elements ---
        title_surf = self.font_large.render("Unsaved Changes", True, settings.BLUE)
        title_rect = title_surf.get_rect(midtop=(screen.get_width() // 2, box_y + 15))
        screen.blit(title_surf, title_rect)

        song_name = self.current_song.name if self.current_song else "Error"
        song_surf = self.font.render(f"in '{song_name}'", True, settings.WHITE)
        song_rect = song_surf.get_rect(midtop=(screen.get_width() // 2, title_rect.bottom + 10))
        screen.blit(song_surf, song_rect)

        # Button instructions
        save_btn = mappings.button_map.get(mappings.SAVE_CC, f"CC{mappings.SAVE_CC}")
        discard_btn = mappings.button_map.get(mappings.DELETE_CC, f"CC{mappings.DELETE_CC}")
        cancel_btn = mappings.button_map.get(mappings.NO_NAV_CC, f"CC{mappings.NO_NAV_CC}")

        instr1_surf = self.font.render(f"Save & Exit? ({save_btn})", True, settings.GREEN)
        instr1_rect = instr1_surf.get_rect(midtop=(screen.get_width() // 2, song_rect.bottom + 20))
        screen.blit(instr1_surf, instr1_rect)

        instr2_surf = self.font.render(f"Discard & Exit? ({discard_btn})", True, settings.RED)
        instr2_rect = instr2_surf.get_rect(midtop=(screen.get_width() // 2, instr1_rect.bottom + 10))
        screen.blit(instr2_surf, instr2_rect)

        instr3_surf = self.font.render(f"Cancel Exit? ({cancel_btn})", True, settings.WHITE)
        instr3_rect = instr3_surf.get_rect(midtop=(screen.get_width() // 2, instr2_rect.bottom + 10))
        screen.blit(instr3_surf, instr3_rect)


    def _draw_scroll_arrow(self, screen, area_rect, direction):
        """Draws an up or down scroll arrow."""
        arrow_char = "^" if direction == 'up' else "v"
        arrow_surf = self.font_small.render(arrow_char, True, WHITE)
        if direction == 'up':
             arrow_rect = arrow_surf.get_rect(centerx=area_rect.centerx, top=area_rect.top + 2)
        else: # down
             arrow_rect = arrow_surf.get_rect(centerx=area_rect.centerx, bottom=area_rect.bottom - 2)
        screen.blit(arrow_surf, arrow_rect)


    # --- List Size Calculation ---
    def _get_max_visible_items(self, list_area_rect: pygame.Rect) -> int:
        """Calculate how many list items fit in a given rect."""
        available_height = list_area_rect.height - (2 * LIST_TOP_PADDING) # Padding top/bottom
        if available_height <= 0 or LINE_HEIGHT <= 0: return 0
        return max(1, available_height // LINE_HEIGHT) # Ensure at least 1 is visible if height > 0

    def _get_max_visible_segments(self) -> int:
        """Calculate how many segment items fit."""
        # Use layout constants to define the rect dynamically
        list_area_top = self.title_rect.bottom + LIST_TOP_PADDING
        available_height = self.app.screen.get_height() - list_area_top - FEEDBACK_AREA_HEIGHT
        seg_list_rect = pygame.Rect(LEFT_MARGIN, list_area_top, SEGMENT_LIST_WIDTH, available_height)
        return self._get_max_visible_items(seg_list_rect)

    def _get_max_visible_parameters(self) -> int:
        """Calculate how many parameter items fit."""
        list_area_top = self.title_rect.bottom + LIST_TOP_PADDING
        available_height = self.app.screen.get_height() - list_area_top - FEEDBACK_AREA_HEIGHT
        param_list_rect = pygame.Rect(PARAM_AREA_X, list_area_top,
                                      self.app.screen.get_width() - PARAM_AREA_X - LEFT_MARGIN,
                                      available_height)
        return self._get_max_visible_items(param_list_rect)
