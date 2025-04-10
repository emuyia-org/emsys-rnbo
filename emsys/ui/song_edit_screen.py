# -*- coding: utf-8 -*-
"""
Screen for viewing and editing Song objects.
"""
import pygame
import time
from typing import List, Optional, Tuple, Any

from .base_screen import BaseScreen
from ..core.song import Song, Segment
# Import constants for validation/clamping
from ..core.song import (MIN_TEMPO, MAX_TEMPO, MIN_RAMP, MAX_RAMP,
                         MIN_LOOP_LENGTH, MAX_LOOP_LENGTH, MIN_REPETITIONS,
                         MAX_REPETITIONS, MIN_PROGRAM_MSG, MAX_PROGRAM_MSG)
from ..utils import file_io # Import the file I/O utilities
from ..config import settings, mappings

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

    def __init__(self, app_ref):
        """Initialize the song editing screen."""
        super().__init__(app_ref)
        self.current_song: Optional[Song] = None
        self.selected_segment_index: Optional[int] = None
        self.selected_parameter_key: Optional[str] = None
        self.feedback_message: Optional[Tuple[str, float]] = None # (message, timestamp)
        self.feedback_duration: float = 2.0 # seconds

        # Define the order and names of editable parameters
        # Using Segment.__annotations__.keys() is possible but less controlled
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
            # This case should ideally be handled by ensuring a song is loaded
            # before navigating here, perhaps via FileManageScreen.
            self.current_song = None
            print("Warning: No 'current_song' attribute found in app reference.")
            self.set_feedback("No song loaded!", is_error=True, duration=5.0)

        # Initialize selection state
        if self.current_song and self.current_song.segments:
            self.selected_segment_index = 0
            self.selected_parameter_key = self.parameter_keys[0]
        else:
            self.selected_segment_index = None
            self.selected_parameter_key = None

        self.clear_feedback() # Clear any old feedback

    def cleanup(self):
        """Called when the screen becomes inactive."""
        super().cleanup()
        # Optionally prompt to save changes here if needed (more complex)
        print(f"{self.__class__.__name__} is being deactivated.")
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

        # --- Navigation ---
        if cc == mappings.DOWN_NAV_CC:
            self._change_selected_segment(1)
        elif cc == mappings.UP_NAV_CC:
            self._change_selected_segment(-1)
        elif cc == mappings.RIGHT_NAV_CC:
            self._change_selected_parameter(1)
        elif cc == mappings.LEFT_NAV_CC:
            self._change_selected_parameter(-1)

        # --- Value Modification ---
        elif cc == mappings.YES_NAV_CC: # Increment
            self._modify_selected_parameter(1)
        elif cc == mappings.NO_NAV_CC: # Decrement
            self._modify_selected_parameter(-1)

        # --- Actions ---
        elif cc == mappings.SAVE_SONG_CC:
            self._save_current_song()
        elif cc == mappings.ADD_SEGMENT_CC:
            self._add_new_segment()
        elif cc == mappings.DELETE_SEGMENT_CC:
            self._delete_selected_segment()

    # --- Internal Helper Methods for Actions ---

    def _change_selected_segment(self, direction: int):
        """Move segment selection up or down."""
        if not self.current_song or not self.current_song.segments:
            self.set_feedback("No segments to select", is_error=True)
            return

        num_segments = len(self.current_song.segments)
        if self.selected_segment_index is None:
            self.selected_segment_index = 0
        else:
            self.selected_segment_index = (self.selected_segment_index + direction) % num_segments

        # Reset parameter selection when changing segments (optional, could preserve)
        if self.parameter_keys:
            self.selected_parameter_key = self.parameter_keys[0]
        self.clear_feedback()

    def _change_selected_parameter(self, direction: int):
        """Move parameter selection left or right."""
        if self.selected_segment_index is None or not self.parameter_keys:
            self.set_feedback("Select a segment first", is_error=True)
            return

        try:
            current_param_index = self.parameter_keys.index(self.selected_parameter_key)
            next_param_index = (current_param_index + direction) % len(self.parameter_keys)
            self.selected_parameter_key = self.parameter_keys[next_param_index]
            self.clear_feedback()
        except (ValueError, AttributeError):
            # Should not happen if state is consistent, but reset just in case
            self.selected_parameter_key = self.parameter_keys[0]

    def _modify_selected_parameter(self, direction: int):
        """Increment or decrement the value of the selected parameter."""
        if self.selected_segment_index is None or self.selected_parameter_key is None:
            self.set_feedback("Select segment and parameter first", is_error=True)
            return
        if not self.current_song: return # Should not happen

        try:
            segment = self.current_song.get_segment(self.selected_segment_index)
            key = self.selected_parameter_key
            current_value = getattr(segment, key)
            step = PARAM_STEPS.get(key, 1) # Default step is 1

            new_value: Any

            # Handle different types
            if isinstance(current_value, bool):
                new_value = not current_value # Toggle boolean
            elif isinstance(current_value, int):
                new_value = current_value + direction * step
                # Clamping for ints
                if key == 'program_message_1' or key == 'program_message_2':
                    new_value = max(MIN_PROGRAM_MSG, min(MAX_PROGRAM_MSG, new_value))
                elif key == 'loop_length':
                    new_value = max(MIN_LOOP_LENGTH, min(MAX_LOOP_LENGTH, new_value))
                elif key == 'repetitions':
                    new_value = max(MIN_REPETITIONS, min(MAX_REPETITIONS, new_value))
            elif isinstance(current_value, float):
                new_value = current_value + direction * step
                # Clamping for floats
                if key == 'tempo':
                    new_value = max(MIN_TEMPO, min(MAX_TEMPO, new_value))
                elif key == 'tempo_ramp':
                    new_value = max(MIN_RAMP, min(MAX_RAMP, new_value))
                new_value = round(new_value, 2) # Round floats for display/storage
            else:
                self.set_feedback(f"Cannot modify type {type(current_value)}", is_error=True)
                return

            # Update the song data
            self.current_song.update_segment(self.selected_segment_index, **{key: new_value})
            display_name = self.parameter_display_names.get(key, key)
            self.set_feedback(f"{display_name}: {new_value}")

        except (IndexError, AttributeError, TypeError, ValueError) as e:
            self.set_feedback(f"Error modifying value: {e}", is_error=True)

    def _save_current_song(self):
        """Save the current song state to a file."""
        if self.current_song:
            if file_io.save_song(self.current_song):
                self.set_feedback(f"Song '{self.current_song.name}' saved.")
            else:
                self.set_feedback(f"Failed to save song '{self.current_song.name}'", is_error=True)
        else:
            self.set_feedback("No song loaded to save", is_error=True)

    def _add_new_segment(self):
        """Add a new segment with default values after the selected one."""
        if not self.current_song:
            self.set_feedback("Load a song first", is_error=True)
            return

        new_segment = Segment() # Create a segment with defaults
        insert_index = (self.selected_segment_index + 1) if self.selected_segment_index is not None else len(self.current_song.segments)

        try:
            self.current_song.add_segment(new_segment, index=insert_index)
            self.selected_segment_index = insert_index # Select the newly added segment
            if self.parameter_keys:
                 self.selected_parameter_key = self.parameter_keys[0]
            self.set_feedback(f"Added new segment at position {insert_index + 1}")
        except Exception as e:
            self.set_feedback(f"Error adding segment: {e}", is_error=True)

    def _delete_selected_segment(self):
        """Delete the currently selected segment."""
        if self.selected_segment_index is None or not self.current_song or not self.current_song.segments:
            self.set_feedback("No segment selected to delete", is_error=True)
            return

        try:
            removed_segment = self.current_song.remove_segment(self.selected_segment_index)
            num_segments = len(self.current_song.segments)

            # Adjust selection after deletion
            if num_segments == 0:
                self.selected_segment_index = None
                self.selected_parameter_key = None
            elif self.selected_segment_index >= num_segments:
                # If last segment was deleted, select the new last one
                self.selected_segment_index = num_segments - 1
            # Otherwise, the index remains valid (points to the segment after the deleted one)

            self.set_feedback(f"Deleted segment {self.selected_segment_index + 2}") # +2 because index was 0-based and points to next now

        except IndexError:
             self.set_feedback("Error deleting segment (index out of range?)", is_error=True)
             # Reset selection state if inconsistent
             if self.current_song and self.current_song.segments:
                 self.selected_segment_index = 0
             else:
                 self.selected_segment_index = None
                 self.selected_parameter_key = None
        except Exception as e:
            self.set_feedback(f"Error deleting segment: {e}", is_error=True)


    # --- Drawing Methods ---

    def draw(self, screen_surface):
        """Draws the song editor interface."""
        # Clear screen (optional, if main loop doesn't fill)
        # screen_surface.fill(BLACK)

        if not self.current_song:
            # Display message if no song is loaded
            no_song_text = "No Song Loaded. Use File Manager."
            no_song_surf = self.font_large.render(no_song_text, True, WHITE)
            no_song_rect = no_song_surf.get_rect(center=(screen_surface.get_width() // 2, screen_surface.get_height() // 2))
            screen_surface.blit(no_song_surf, no_song_rect)
            self._draw_feedback(screen_surface) # Still draw feedback if any
            return

        # --- Draw Song Title ---
        title_text = f"Editing: {self.current_song.name}"
        title_surf = self.font_large.render(title_text, True, WHITE)
        title_rect = title_surf.get_rect(midtop=(screen_surface.get_width() // 2, TOP_MARGIN))
        screen_surface.blit(title_surf, title_rect)

        # --- Draw Segment List ---
        self._draw_segment_list(screen_surface, title_rect.bottom + 15)

        # --- Draw Parameter Details ---
        self._draw_parameter_details(screen_surface, title_rect.bottom + 15)

        # --- Draw Feedback Message ---
        self._draw_feedback(screen_surface)

    def _draw_segment_list(self, surface, start_y):
        """Draws the list of segments on the left."""
        list_rect = pygame.Rect(LEFT_MARGIN, start_y, SEGMENT_LIST_WIDTH, surface.get_height() - start_y - 40) # Reserve space at bottom for feedback
        # pygame.draw.rect(surface, (50,50,50), list_rect, 1) # Optional: border for debug

        y_offset = list_rect.top + 5

        # Header
        header_surf = self.font.render("Segments:", True, WHITE)
        surface.blit(header_surf, (list_rect.left + 5, y_offset))
        y_offset += LINE_HEIGHT + 5

        if not self.current_song or not self.current_song.segments:
            no_segments_surf = self.font_small.render("No segments yet.", True, WHITE)
            surface.blit(no_segments_surf, (list_rect.left + 10, y_offset))
            return

        # TODO: Implement scrolling if list exceeds available height
        max_items_to_display = list_rect.height // LINE_HEIGHT
        start_index = 0 # For scrolling later

        for i, segment in enumerate(self.current_song.segments[start_index:]):
            if i >= max_items_to_display:
                # Indicate more items below
                more_surf = self.font_small.render("...", True, WHITE)
                surface.blit(more_surf, (list_rect.left + 5, y_offset))
                break

            display_index = start_index + i
            # Basic segment info (e.g., index and tempo)
            seg_text = f"{display_index + 1}: T={segment.tempo:.0f} L={segment.loop_length} R={segment.repetitions}"
            color = HIGHLIGHT_COLOR if display_index == self.selected_segment_index else WHITE
            is_selected = (display_index == self.selected_segment_index)

            seg_surf = self.font_small.render(seg_text, True, color)
            seg_rect = seg_surf.get_rect(topleft=(list_rect.left + 10, y_offset))

            if is_selected:
                 # Draw a selection indicator (e.g., background rectangle)
                 sel_rect = pygame.Rect(list_rect.left, y_offset - 2, list_rect.width, LINE_HEIGHT)
                 pygame.draw.rect(surface, (40, 80, 40), sel_rect) # Dark green background

            surface.blit(seg_surf, seg_rect)
            y_offset += LINE_HEIGHT

    def _draw_parameter_details(self, surface, start_y):
        """Draws the parameters of the selected segment on the right."""
        param_rect = pygame.Rect(PARAM_AREA_X, start_y, surface.get_width() - PARAM_AREA_X - LEFT_MARGIN, surface.get_height() - start_y - 40)
        # pygame.draw.rect(surface, (50,50,50), param_rect, 1) # Optional: border for debug

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
             return # Should not happen if selection logic is correct

        # Header
        header_text = f"Segment {self.selected_segment_index + 1} Parameters:"
        header_surf = self.font.render(header_text, True, WHITE)
        surface.blit(header_surf, (param_rect.left + 5, y_offset))
        y_offset += LINE_HEIGHT + 5

        # Draw each parameter
        for key in self.parameter_keys:
            display_name = self.parameter_display_names.get(key, key)
            try:
                value = getattr(segment, key)
                # Format value nicely
                if isinstance(value, bool):
                    value_str = "YES" if value else "NO"
                elif isinstance(value, float):
                    value_str = f"{value:.1f}" # One decimal place for display
                else:
                    value_str = str(value)

                param_text = f"{display_name}: {value_str}"
                color = HIGHLIGHT_COLOR if key == self.selected_parameter_key else PARAM_COLOR
                is_selected = (key == self.selected_parameter_key)

                param_surf = self.font.render(param_text, True, color)
                param_draw_rect = param_surf.get_rect(topleft=(param_rect.left + PARAM_INDENT, y_offset))

                if is_selected:
                    # Draw selection indicator
                    sel_rect = pygame.Rect(param_rect.left, y_offset - 2, param_rect.width, LINE_HEIGHT)
                    pygame.draw.rect(surface, (40, 80, 40), sel_rect) # Dark green background

                surface.blit(param_surf, param_draw_rect)
                y_offset += LINE_HEIGHT

            except AttributeError:
                # Draw error if attribute doesn't exist (shouldn't happen)
                error_surf = self.font_small.render(f"Error: Param '{key}' not found", True, ERROR_COLOR)
                surface.blit(error_surf, (param_rect.left + PARAM_INDENT, y_offset))
                y_offset += LINE_HEIGHT

    def _draw_feedback(self, surface):
        """Draws the feedback message at the bottom."""
        if self.feedback_message:
            message, timestamp, color = self.feedback_message
            feedback_surf = self.font.render(message, True, color)
            feedback_rect = feedback_surf.get_rect(center=(surface.get_width() // 2, surface.get_height() - 25))
            # Optional: Add a background to make it stand out
            bg_rect = feedback_rect.inflate(10, 5)
            pygame.draw.rect(surface, BLACK, bg_rect)
            pygame.draw.rect(surface, color, bg_rect, 1) # Border
            surface.blit(feedback_surf, feedback_rect)
