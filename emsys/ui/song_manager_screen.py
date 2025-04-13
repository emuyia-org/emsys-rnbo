# -*- coding: utf-8 -*-
"""
Screen for managing Songs (Loading, Creating, Renaming).
"""
import pygame
import time
from typing import List, Optional, Tuple
import datetime # Needed for default new song name

# Core components
from emsys.core.song import Song, Segment

# Base class for screens
from emsys.ui.base_screen import BaseScreen

# Utilities and Config
from emsys.utils import file_io
from emsys.config import settings, mappings
# --- Import the specific Fader CC ---
from emsys.config.mappings import FADER_SELECT_CC
# ------------------------------------

# --- Import the TextInputWidget ---
from .widgets import TextInputWidget, TextInputStatus

# --- Define colors (imported from settings) ---
WHITE = settings.WHITE
BLACK = settings.BLACK
GREEN = settings.GREEN
RED = settings.RED
BLUE = settings.BLUE
HIGHLIGHT_COLOR = settings.HIGHLIGHT_COLOR
FEEDBACK_COLOR = settings.FEEDBACK_COLOR
ERROR_COLOR = settings.ERROR_COLOR
# ---------------------------------------------

# Define layout constants
LEFT_MARGIN = 15
TOP_MARGIN = 15
LINE_HEIGHT = 30 # Slightly larger line height for easier reading
LIST_TOP_PADDING = 10
LIST_ITEM_INDENT = 25

class SongManagerScreen(BaseScreen):
    """Screen for listing, loading, creating, and renaming songs."""

    def __init__(self, app_ref):
        """Initialize the song manager screen."""
        super().__init__(app_ref)
        # Define additional fonts needed
        self.font_large = pygame.font.Font(None, 48)  # Larger font for titles
        self.font_small = pygame.font.Font(None, 24)  # Smaller font for indicators/details

        self.title_text = "Song Manager"
        self.title_surf = self.font_large.render(self.title_text, True, WHITE)
        self.title_rect = self.title_surf.get_rect(midtop=(self.app.screen.get_width() // 2, TOP_MARGIN))

        # State for the list and selection
        self.song_list: List[str] = []
        self.selected_index: Optional[int] = None
        self.scroll_offset: int = 0 # Index of the first visible item

        # Feedback message state
        self.feedback_message: Optional[Tuple[str, float, Tuple[int, int, int]]] = None # (message, timestamp, color)
        self.feedback_duration: float = 3.0 # seconds

        # --- Add instance of TextInputWidget ---
        self.text_input_widget = TextInputWidget(app_ref)
        # ---------------------------------------

        # --- Add deletion confirmation state ---
        self.delete_confirmation_active = False
        # -------------------------------------

        # --- Add unsaved changes prompt state ---
        self.unsaved_prompt_active = False
        self.song_to_load_after_prompt: Optional[str] = None # Store the basename of the song to load
        # ----------------------------------------

    def init(self):
        """Called when the screen becomes active. Load the song list."""
        super().init()
        print(f"{self.__class__.__name__} is now active.")
        self._refresh_song_list()
        self.clear_feedback()
        # Update title (already done in __init__)
        # self.title_text = "Song Manager"
        # self.title_surf = self.font_large.render(self.title_text, True, WHITE)
        # self.title_rect = self.title_surf.get_rect(midtop=(self.app.screen.get_width() // 2, TOP_MARGIN))

        # --- Reset text input widget state on init ---
        self.text_input_widget.cancel()
        # ---------------------------------------------
        # --- Reset confirmation states on init ---
        self.delete_confirmation_active = False
        self.unsaved_prompt_active = False
        self.song_to_load_after_prompt = None
        # -----------------------------------------

    def cleanup(self):
        """Called when the screen becomes inactive."""
        super().cleanup()
        print(f"{self.__class__.__name__} is being deactivated.")
        # --- Ensure text input widget is cleared on exit ---
        self.text_input_widget.cancel()
        # --------------------------------------------------
        # --- Reset confirmation states on cleanup ---
        self.delete_confirmation_active = False
        self.unsaved_prompt_active = False
        self.song_to_load_after_prompt = None
        # ------------------------------------------
        self.clear_feedback()

    def _refresh_song_list(self):
        """Fetches the list of songs from file_io and resets selection."""
        current_selection = None
        if self.selected_index is not None and self.selected_index < len(self.song_list):
            current_selection = self.song_list[self.selected_index]

        self.song_list = file_io.list_songs()
        self.scroll_offset = 0 # Reset scroll on refresh

        if not self.song_list:
            self.selected_index = None
        else:
            # Try to restore selection if the item still exists
            try:
                if current_selection and current_selection in self.song_list:
                    self.selected_index = self.song_list.index(current_selection)
                else:
                    self.selected_index = 0 # Default to first item
            except ValueError:
                self.selected_index = 0 # Fallback

            # Adjust scroll offset if needed after refresh/selection reset
            max_visible = self._get_max_visible_items()
            if self.selected_index is not None and self.selected_index >= max_visible:
                 self.scroll_offset = self.selected_index - max_visible + 1
            else:
                 self.scroll_offset = 0


        print(f"Refreshed songs: {self.song_list}, Selected: {self.selected_index}")


    def set_feedback(self, message: str, is_error: bool = False, duration: Optional[float] = None):
        """Display a feedback message."""
        print(f"Feedback: {message}")
        color = ERROR_COLOR if is_error else FEEDBACK_COLOR
        self.feedback_message = (message, time.time(), color)
        self.feedback_duration = duration if duration is not None else 3.0

    def clear_feedback(self):
        """Clear the feedback message."""
        self.feedback_message = None

    def update(self):
        """Update screen state, like clearing timed feedback."""
        super().update()
        if self.feedback_message and (time.time() - self.feedback_message[1] > self.feedback_duration):
            self.clear_feedback()

    def handle_midi(self, msg):
        """Handle MIDI messages for list navigation, selection, creation, and renaming."""
        # --- Only process Control Change messages ---
        if msg.type != 'control_change':
            return

        cc = msg.control
        value = msg.value # Get value for all CC types

        # --- Debug Logging ---
        # Limit logging for fader to avoid spamming console - KEEPING THIS FOR NOW
        log_msg = True
        if cc == FADER_SELECT_CC:
            if not hasattr(self, '_last_fader_value'): self._last_fader_value = -1
            if abs(value - self._last_fader_value) > 5 or value in (0, 127):
                 self._last_fader_value = value
            else:
                 log_msg = False # Suppress log for small fader changes

        # Always log if not fader, or if fader meets criteria
        # if log_msg: # Modified this slightly to ensure fader debug below always runs
        #     print(f"SongManagerScreen received CC: {cc} Value: {value} | TextInput: {self.text_input_widget.is_active} | DeleteConfirm: {self.delete_confirmation_active} | UnsavedPrompt: {self.unsaved_prompt_active}")
        # --- End Debug Logging ---


        # --- Handle Text Input Mode FIRST ---
        if self.text_input_widget.is_active:
            # Text input only responds to button presses (value 127)
            if value == 127:
                status = self.text_input_widget.handle_input(cc)
                if status == TextInputStatus.CONFIRMED:
                    self._confirm_song_rename() # Call the confirmation logic
                elif status == TextInputStatus.CANCELLED:
                    self._cancel_song_rename() # Call the cancellation logic
            # If ACTIVE or ERROR, the widget handles drawing, we just wait
            return # Don't process other actions while text input is active
        # ----------------------------------

        # --- Handle Delete Confirmation Mode ---
        if self.delete_confirmation_active:
            # Delete confirmation only responds to button presses (value 127)
            if value == 127:
                if cc == mappings.YES_NAV_CC:
                    self._perform_delete()
                    return
                elif cc == mappings.NO_NAV_CC:
                    self.delete_confirmation_active = False
                    self.set_feedback("Delete cancelled.")
                    return
            # Ignore other buttons/values during delete confirmation
            return
        # -------------------------------------

        # --- Handle Unsaved Changes Prompt Mode ---
        if self.unsaved_prompt_active:
            # Unsaved prompt only responds to button presses (value 127)
            if value == 127:
                if cc == mappings.SAVE_CC: # Use SAVE button to save
                    self._save_current_and_load_selected()
                elif cc == mappings.DELETE_CC: # Use DELETE button to discard
                    self._discard_changes_and_load_selected()
                elif cc == mappings.NO_NAV_CC: # Use NO button to cancel loading
                    self._cancel_load_due_to_unsaved()
            # Ignore other buttons/values during this prompt
            return
        # ------------------------------------------

        # --- Handle Fader Selection (CC 65) ---
        if cc == FADER_SELECT_CC:
            if not self.song_list:
                return # No songs to select

            num_songs = len(self.song_list)
            # Map 127->0, 0->(num_songs-1)
            # Ensure floating point division and proper scaling
            reversed_value = 127 - value
            target_index = int((reversed_value / 128.0) * num_songs)
            # Clamp index to valid range [0, num_songs-1]
            target_index = max(0, min(num_songs - 1, target_index))

            # --- Add Detailed Logging Here ---
            current_selected = self.selected_index
            # Print this log regardless of the log_msg suppression above for debugging
            print(f"[Fader Debug] Value={value} (Reversed={reversed_value}), NumSongs={num_songs} -> TargetIdx={target_index}, CurrentSelected={current_selected}")
            # --- End Detailed Logging ---


            if target_index != current_selected:
                # Use the more verbose logging only if the selection actually changes
                print(f"          Updating selection: {current_selected} -> {target_index}")
                self.selected_index = target_index
                # Update scroll offset based on new selection
                max_visible = self._get_max_visible_items()
                # If selection is below visible area
                if self.selected_index >= self.scroll_offset + max_visible:
                    print(f"          Scrolling DOWN: Offset {self.scroll_offset} -> {self.selected_index - max_visible + 1}") # DEBUG
                    self.scroll_offset = self.selected_index - max_visible + 1
                # If selection is above visible area
                elif self.selected_index < self.scroll_offset:
                    print(f"          Scrolling UP: Offset {self.scroll_offset} -> {self.selected_index}") # DEBUG
                    self.scroll_offset = self.selected_index
                self.clear_feedback()
            # else: # Optional: Log when no update occurs
            #     print(f"          No selection change needed (TargetIdx == CurrentSelected)")

            return # Fader handled, don't process as button press below

        # --- Normal Song Management Mode (Button Presses Only) ---
        # Process remaining CCs only if they are button presses (value 127)
        if value != 127:
            return

        # Handle CREATE_CC
        if cc == mappings.CREATE_CC:
            self._create_new_song()
            return

        # Handle RENAME_CC
        elif cc == mappings.RENAME_CC:
            self._start_song_rename()
            return

        # --- Add DELETE_CC handling ---
        elif cc == mappings.DELETE_CC: # Note: Using DELETE_CC for song deletion
            self._delete_selected_song()
            return
        # ----------------------------------

        # --- List Navigation/Selection (Buttons - only if list exists) ---
        if not self.song_list:
            # No songs, only allow exit/screen change and creation/rename (handled above)
            if cc in (mappings.UP_NAV_CC, mappings.DOWN_NAV_CC, mappings.YES_NAV_CC):
                self.set_feedback("No songs found.", is_error=True)
            return # Ignore other navigation/selection if list is empty

        num_songs = len(self.song_list)
        max_visible = self._get_max_visible_items()

        if cc == mappings.DOWN_NAV_CC:
            if self.selected_index is not None:
                self.selected_index = (self.selected_index + 1) % num_songs
                # Adjust scroll offset if selection moves below visible area
                if self.selected_index >= self.scroll_offset + max_visible:
                    self.scroll_offset = self.selected_index - max_visible + 1
                # Handle wrap-around scrolling to the top
                if self.selected_index == 0: # Check if wrapped to top
                    self.scroll_offset = 0
            else:
                 self.selected_index = 0 # Select first item if none selected
            self.clear_feedback()

        elif cc == mappings.UP_NAV_CC:
            if self.selected_index is not None:
                self.selected_index = (self.selected_index - 1 + num_songs) % num_songs
                 # Adjust scroll offset if selection moves above visible area
                if self.selected_index < self.scroll_offset:
                    self.scroll_offset = self.selected_index
                # Handle wrap-around scrolling to the bottom
                if self.selected_index == num_songs - 1: # Check if wrapped to bottom
                     self.scroll_offset = max(0, num_songs - max_visible)
            else:
                 self.selected_index = num_songs - 1 # Select last item if none selected
            self.clear_feedback()

        elif cc == mappings.YES_NAV_CC:
            self._load_selected_song() # This now checks for dirty state

    # --- Methods for Renaming using TextInputWidget ---
    def _start_song_rename(self):
        """Initiates renaming for the selected song using the widget."""
        if self.selected_index is None or not self.song_list:
            self.set_feedback("No song selected to rename", is_error=True)
            return

        try:
            current_name = self.song_list[self.selected_index]
            self.text_input_widget.start(current_name, prompt="Rename Song")
            self.clear_feedback()
            print(f"Starting song rename for: {current_name}")
            self.set_feedback("Renaming song...", duration=1.0)
        except IndexError:
            self.set_feedback("Selection error, cannot rename.", is_error=True)
            self.selected_index = 0 if self.song_list else None # Reset index

    def _confirm_song_rename(self):
        """Confirms the song rename using file_io."""
        # Check if widget is active *now*
        if not self.text_input_widget.is_active or self.selected_index is None:
            self.text_input_widget.cancel() # Ensure inactive
            return

        new_name = self.text_input_widget.get_text()
        if new_name is None:
             self.set_feedback("Error getting new name from widget.", is_error=True)
             self.text_input_widget.cancel() # Cancel on error
             return

        new_name = new_name.strip()

        try:
            old_name = self.song_list[self.selected_index]
        except IndexError:
            self.set_feedback("Selection error during rename confirmation.", is_error=True)
            self.text_input_widget.cancel() # Cancel on error
            self._refresh_song_list() # Refresh list state
            return

        if not new_name:
            self.set_feedback("Song name cannot be empty.", is_error=True)
            self.text_input_widget.cancel() # Cancel on validation failure
            return

        if new_name == old_name:
            self.set_feedback("Name unchanged. Exiting rename.")
            self.text_input_widget.cancel() # Cancel if name is the same
            return

        print(f"Attempting to rename song from '{old_name}' to '{new_name}'")

        # --- Song Renaming Logic ---
        if not hasattr(file_io, 'rename_song'):
             self.set_feedback("Error: Song renaming function not implemented!", is_error=True)
             self.text_input_widget.cancel() # Cancel on missing function
             return

        # Use the rename_song function from file_io
        if file_io.rename_song(old_name, new_name):
            self.set_feedback(f"Song renamed to '{new_name}'")

            # --- Critical: Check if the renamed song was the loaded current_song ---
            renamed_current = False
            # Use getattr for safety, although current_song should exist if rename is possible
            current_song_obj = getattr(self.app, 'current_song', None)
            if current_song_obj and current_song_obj.name == old_name:
                print(f"Updating current song in memory from '{old_name}' to '{new_name}'")
                self.app.current_song.name = new_name
                renamed_current = True
                # Optional: Save the current song immediately after rename?
                # if not file_io.save_song(self.app.current_song):
                #     self.set_feedback(f"Renamed, but failed to save current song '{new_name}'", is_error=True)


            # Refresh the list to show the new name and re-select it
            self._refresh_song_list()
            try:
                # Find the new index after refresh
                new_index = self.song_list.index(new_name)
                self.selected_index = new_index
                # Adjust scroll if necessary after re-selection
                max_visible = self._get_max_visible_items()
                if self.selected_index >= self.scroll_offset + max_visible:
                    self.scroll_offset = self.selected_index - max_visible + 1
                elif self.selected_index < self.scroll_offset:
                    self.scroll_offset = self.selected_index

            except (ValueError, IndexError):
                self.selected_index = 0 if self.song_list else None # Fallback selection

            self.text_input_widget.cancel() # Exit rename mode on success

        else:
            # file_io.rename_song failed
            self.set_feedback(f"Failed to rename song", is_error=True)
            self.text_input_widget.cancel() # Cancel on failure


    def _cancel_song_rename(self):
        """Cancels the song renaming process."""
        # Widget should already be inactive if CANCELLED status was returned,
        # but call cancel() again for safety.
        self.set_feedback("Rename cancelled.")
        print("Cancelled song rename mode.")
        self.text_input_widget.cancel()

    # --- End of Renaming Methods ---

    def _delete_selected_song(self):
        """Initiates the deletion of the selected song with confirmation."""
        if self.selected_index is None or not self.song_list:
            self.set_feedback("No song selected to delete", is_error=True)
            return

        try:
            song_name = self.song_list[self.selected_index]
            self.delete_confirmation_active = True
            # Replace CC numbers with button names
            self.set_feedback(f"Delete '{song_name}'?", is_error=True, duration=10.0) # Longer duration
        except IndexError:
            self.set_feedback("Selection error, cannot delete.", is_error=True)
            self.selected_index = 0 if self.song_list else None  # Reset index

    def _perform_delete(self):
        """Performs the actual song deletion after confirmation."""
        if self.selected_index is None or not self.song_list:
            self.delete_confirmation_active = False
            self.set_feedback("No song selected to delete", is_error=True)
            return

        try:
            song_name = self.song_list[self.selected_index]

            # --- MODIFIED LINE: Use getattr for safer access ---
            # Check if the song to be deleted is the currently loaded song
            current_song_obj = getattr(self.app, 'current_song', None)
            is_current_song = (current_song_obj and current_song_obj.name == song_name)
            # --- END MODIFICATION ---

            # Delete the song using file_io
            if hasattr(file_io, 'delete_song') and file_io.delete_song(song_name):
                self.set_feedback(f"Deleted: '{song_name}'")

                # If we deleted the current song, clear the app's current_song reference
                if is_current_song:
                    # This check implies self.app.current_song existed, so direct assignment is safe here
                    self.app.current_song = None
                    print(f"Cleared current song as it was deleted: '{song_name}'")

                # Store the index before refreshing
                deleted_index = self.selected_index

                # Update the song list and selection
                self._refresh_song_list()

                # Adjust selection after deletion
                if not self.song_list:
                    self.selected_index = None
                else:
                    # Try to select the next item, or the previous if it was the last
                    if deleted_index >= len(self.song_list):
                        self.selected_index = len(self.song_list) - 1
                    else:
                        self.selected_index = deleted_index
                    # Ensure selection is within bounds (especially if list became empty)
                    if self.selected_index < 0:
                        self.selected_index = None
                    elif self.selected_index >= len(self.song_list):
                         self.selected_index = len(self.song_list) - 1


            else:
                # file_io.delete_song should print the specific error
                self.set_feedback(f"Failed to delete '{song_name}'", is_error=True)
        except IndexError:
             # This might happen if the list changes unexpectedly between selection and deletion
             self.set_feedback("Selection error during delete.", is_error=True)
             self._refresh_song_list() # Refresh to get a consistent state
        except Exception as e:
            # Catch other unexpected errors
            self.set_feedback(f"Error deleting song: {str(e)}", is_error=True)
            print(f"Unexpected error in _perform_delete: {e}") # Log detailed error

        self.delete_confirmation_active = False # Always deactivate confirmation mode

    def _create_new_song(self):
        """Creates a new song and navigates to the song edit screen."""
        if self.text_input_widget.is_active: return # Prevent action during text input
        try:
            # Create a default song name based on timestamp to ensure uniqueness
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            new_song_name = f"{timestamp}"

            # Create a new song with an initial empty segment
            new_song = Song(name=new_song_name)
            initial_segment = Segment()  # Create with default values
            new_song.add_segment(initial_segment)

            # Don't set as current song in the app - removed this line
            # self.app.current_song = new_song

            # Save the song to disk
            if file_io.save_song(new_song):
                self.set_feedback(f"Created new song: {new_song_name}.")
                # Refresh the song list to include the new song
                self._refresh_song_list()
                # Select the new song in the list
                try:
                    new_song_index = self.song_list.index(new_song_name)
                    self.selected_index = new_song_index
                    # Adjust scroll
                    max_visible = self._get_max_visible_items()
                    if self.selected_index >= self.scroll_offset + max_visible:
                        self.scroll_offset = self.selected_index - max_visible + 1

                except (ValueError, IndexError):
                    pass  # If we can't find or select it, that's ok

                # Remove automatic navigation
                # NAVIGATE_EVENT = pygame.USEREVENT + 1
                # pygame.time.set_timer(NAVIGATE_EVENT, 1500, loops=1)  # 1500 ms delay
            else:
                self.set_feedback(f"Failed to save new song.", is_error=True)
                # Don't need to clear current_song since we never set it

        except Exception as e:
            self.set_feedback(f"Error creating song: {e}", is_error=True)
            print(f"Error in _create_new_song: {e}")
            # Don't need to clear current_song since we never set it

    def _load_selected_song(self):
        """
        Attempts to load the selected song. Checks for unsaved changes in the
        current song before proceeding.
        """
        if self.text_input_widget.is_active: return
        if self.selected_index is None or not self.song_list:
            self.set_feedback("No song selected.", is_error=True)
            return

        try:
            selected_basename = self.song_list[self.selected_index]
            current_song = getattr(self.app, 'current_song', None)

            # Check if the selected song is already loaded
            if current_song and current_song.name == selected_basename:
                self.set_feedback(f"'{selected_basename}' is already loaded.")
                # Optionally navigate to edit screen? For now, just feedback.
                return

            # Check for unsaved changes in the *current* song
            if current_song and current_song.dirty:
                print(f"Unsaved changes detected in '{current_song.name}'. Prompting user.")
                self.song_to_load_after_prompt = selected_basename # Store target song
                self.unsaved_prompt_active = True
                self.set_feedback(f"Unsaved changes in '{current_song.name}'!", is_error=True, duration=10.0)
                # Don't proceed with loading yet
            else:
                # No unsaved changes, or no song currently loaded. Proceed directly.
                self._perform_load(selected_basename)

        except IndexError:
            self.set_feedback("Selection index error.", is_error=True)
            self.selected_index = 0 if self.song_list else None # Reset index
        except Exception as e:
            self.set_feedback(f"Error preparing load: {e}", is_error=True)
            print(f"Unexpected error during load prep: {e}")

    def _perform_load(self, basename_to_load: str):
        """Internal method to actually load the song file."""
        self.set_feedback(f"Loading '{basename_to_load}'...")
        pygame.display.flip() # Show feedback immediately

        loaded_song = file_io.load_song(basename_to_load)

        if loaded_song:
            self.app.current_song = loaded_song
            self.set_feedback(f"Loaded: {basename_to_load}.")
            # Refresh display to show new current song border
        else:
            # Loading failed (file_io.load_song returns None and prints error)
            self.app.current_song = None # Ensure current song is cleared
            self.set_feedback(f"Failed to load '{basename_to_load}'", is_error=True)

        # Reset prompt state regardless of success/failure
        self.unsaved_prompt_active = False
        self.song_to_load_after_prompt = None


    def _save_current_and_load_selected(self):
        """Saves the current song, then loads the selected one."""
        print("User chose SAVE.")
        current_song = getattr(self.app, 'current_song', None)
        basename_to_load = self.song_to_load_after_prompt

        if not current_song or not basename_to_load:
            self.set_feedback("Error: Missing context for save/load.", is_error=True)
            self._reset_prompt_state()
            return

        self.set_feedback(f"Saving '{current_song.name}'...")
        pygame.display.flip()

        if file_io.save_song(current_song):
            self.set_feedback(f"Saved '{current_song.name}'.")
            # Proceed to load the target song
            self._perform_load(basename_to_load)
        else:
            self.set_feedback(f"Failed to save '{current_song.name}'. Load cancelled.", is_error=True)
            # Keep prompt active? Or cancel? Let's cancel load on save failure.
            self._reset_prompt_state()


    def _discard_changes_and_load_selected(self):
        """Discards changes to the current song, then loads the selected one."""
        print("User chose DISCARD.")
        current_song = getattr(self.app, 'current_song', None)
        basename_to_load = self.song_to_load_after_prompt

        if not basename_to_load:
            self.set_feedback("Error: Missing context for discard/load.", is_error=True)
            self._reset_prompt_state()
            return

        if current_song:
            self.set_feedback(f"Discarding changes in '{current_song.name}'...")
            current_song.dirty = False # Mark as not dirty anymore
            pygame.display.flip()
            time.sleep(0.5) # Brief pause for feedback visibility

        # Proceed to load the target song
        self._perform_load(basename_to_load)


    def _cancel_load_due_to_unsaved(self):
        """Cancels the pending load operation."""
        print("User chose CANCEL load.")
        self.set_feedback("Load cancelled.")
        self._reset_prompt_state()

    def _reset_prompt_state(self):
        """Resets the state variables related to the unsaved prompt."""
        self.unsaved_prompt_active = False
        self.song_to_load_after_prompt = None
        # Optionally clear feedback here too, or let it time out
        # self.clear_feedback()


    def _get_max_visible_items(self) -> int:
        """Calculate how many list items fit on the screen."""
        list_area_top = self.title_rect.bottom + LIST_TOP_PADDING
        list_area_bottom = self.app.screen.get_height() - 40 # Reserve space for feedback
        available_height = list_area_bottom - list_area_top
        if available_height <= 0 or LINE_HEIGHT <= 0:
            return 0
        return available_height // LINE_HEIGHT

    def draw(self, screen_surface, midi_status=None):
        """Draws the screen content or the text input widget."""
        # --- Draw Text Input Interface if active ---
        if self.text_input_widget.is_active:
            # Optionally clear background first
            # screen_surface.fill(BLACK)
            self.text_input_widget.draw(screen_surface)
        # --- Draw Unsaved Changes Prompt if active ---
        elif self.unsaved_prompt_active:
            self._draw_unsaved_prompt(screen_surface)
        # --- Draw Delete Confirmation if active ---
        elif self.delete_confirmation_active:
             self._draw_delete_confirmation(screen_surface)
        # --- Draw Normal Song List Interface ---
        else:
            # Draw the title
            screen_surface.blit(self.title_surf, self.title_rect)

            # --- Draw Song List ---
            list_area_top = self.title_rect.bottom + LIST_TOP_PADDING
            y_offset = list_area_top

            # Get the current loaded song name for highlighting
            current_song_name = None
            if hasattr(self.app, 'current_song') and self.app.current_song:
                current_song_name = self.app.current_song.name

            if not self.song_list:
                no_songs_text = f"No songs found."
                no_songs_surf = self.font.render(no_songs_text, True, WHITE)
                no_songs_rect = no_songs_surf.get_rect(centerx=screen_surface.get_width() // 2, top=y_offset + 20)
                screen_surface.blit(no_songs_surf, no_songs_rect)
            else:
                max_visible = self._get_max_visible_items()
                # Ensure scroll offset is valid
                if self.scroll_offset > len(self.song_list) - max_visible:
                    self.scroll_offset = max(0, len(self.song_list) - max_visible)
                if self.scroll_offset < 0:
                    self.scroll_offset = 0

                end_index = min(self.scroll_offset + max_visible, len(self.song_list))

                # Draw scroll up indicator if needed
                if self.scroll_offset > 0:
                     scroll_up_surf = self.font_small.render("^", True, WHITE)
                     scroll_up_rect = scroll_up_surf.get_rect(centerx=screen_surface.get_width() // 2, top=list_area_top - 15)
                     screen_surface.blit(scroll_up_surf, scroll_up_rect)

                # Draw the visible portion of the list
                for i in range(self.scroll_offset, end_index):
                    song_name = self.song_list[i]
                    
                    # Check if this is the currently loaded song
                    is_current = (song_name == current_song_name)
                    
                    # Display the song name
                    display_text = f"{i + 1}. {song_name}"
                    
                    is_selected = (i == self.selected_index)
                    
                    # Determine color - prioritize selection highlight
                    if is_selected:
                        color = HIGHLIGHT_COLOR
                    else:
                        color = WHITE  # Always use white for better visibility

                    item_surf = self.font.render(display_text, True, color)
                    item_rect = item_surf.get_rect(topleft=(LEFT_MARGIN + LIST_ITEM_INDENT, y_offset))

                    if is_selected:
                        # Draw highlight background
                        highlight_rect = pygame.Rect(LEFT_MARGIN, y_offset - 2, screen_surface.get_width() - (2 * LEFT_MARGIN), LINE_HEIGHT)
                        # Use the standard green highlight for selected items
                        pygame.draw.rect(screen_surface, (40, 80, 40), highlight_rect)
                    
                    # Draw a border around the currently loaded song (after background, before text)
                    if is_current:
                        # Create a rectangle slightly larger than the text for the border
                        border_rect = pygame.Rect(LEFT_MARGIN + LIST_ITEM_INDENT - 10, 
                                                y_offset - 2, 
                                                screen_surface.get_width() - LEFT_MARGIN - LIST_ITEM_INDENT - 10, 
                                                LINE_HEIGHT)
                        # Draw the border with a bright cyan color for better visibility
                        border_color = (0, 255, 255)  # Bright cyan
                        pygame.draw.rect(screen_surface, border_color, border_rect, 2)  # 2px border width

                    screen_surface.blit(item_surf, item_rect)

                    y_offset += LINE_HEIGHT

                # Draw scroll down indicator if needed
                if end_index < len(self.song_list):
                     scroll_down_surf = self.font_small.render("v", True, WHITE)
                     scroll_down_rect = scroll_down_surf.get_rect(centerx=screen_surface.get_width() // 2, top=y_offset + 5)
                     screen_surface.blit(scroll_down_surf, scroll_down_rect)


        # --- Draw Feedback Message (Common) ---
        # Draw feedback last so it's on top, unless a prompt is active
        if not self.unsaved_prompt_active and not self.delete_confirmation_active:
             self._draw_feedback(screen_surface)


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

    def _draw_delete_confirmation(self, surface):
        """Draws the delete confirmation overlay."""
        # Create semi-transparent overlay
        overlay = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))  # Semi-transparent black
        surface.blit(overlay, (0, 0))

        # Draw confirmation box
        box_width, box_height = 400, 150
        box_x = (surface.get_width() - box_width) // 2
        box_y = (surface.get_height() - box_height) // 2

        # Box background and border
        pygame.draw.rect(surface, BLACK, (box_x, box_y, box_width, box_height))
        pygame.draw.rect(surface, RED, (box_x, box_y, box_width, box_height), 2)

        # Title
        title_text = "Confirm Delete"
        title_surf = self.font_large.render(title_text, True, RED)
        title_rect = title_surf.get_rect(midtop=(surface.get_width() // 2, box_y + 15))
        surface.blit(title_surf, title_rect)

        # Song name (ensure selected_index is valid)
        song_name = "Error: No song selected" # Default/fallback text
        if self.selected_index is not None and self.selected_index < len(self.song_list):
            try:
                song_name = self.song_list[self.selected_index]
            except IndexError:
                 pass # Keep default text if index becomes invalid

        song_text = f"'{song_name}'"
        song_surf = self.font.render(song_text, True, WHITE)
        song_rect = song_surf.get_rect(midtop=(surface.get_width() // 2, title_rect.bottom + 10))
        surface.blit(song_surf, song_rect)

        # Instruction using button map
        yes_btn = mappings.button_map.get(mappings.YES_NAV_CC, f"CC{mappings.YES_NAV_CC}")
        no_btn = mappings.button_map.get(mappings.NO_NAV_CC, f"CC{mappings.NO_NAV_CC}")
        instr_text = f"Confirm: {yes_btn} | Cancel: {no_btn}"
        instr_surf = self.font.render(instr_text, True, WHITE)
        instr_rect = instr_surf.get_rect(midbottom=(surface.get_width() // 2, box_y + box_height - 15))
        surface.blit(instr_surf, instr_rect)

    def _draw_unsaved_prompt(self, surface):
        """Draws the unsaved changes prompt overlay."""
        # Create semi-transparent overlay
        overlay = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))  # Semi-transparent black
        surface.blit(overlay, (0, 0))

        # Draw confirmation box
        box_width, box_height = 400, 180 # Slightly taller
        box_x = (surface.get_width() - box_width) // 2
        box_y = (surface.get_height() - box_height) // 2

        # Box background and border
        pygame.draw.rect(surface, BLACK, (box_x, box_y, box_width, box_height))
        pygame.draw.rect(surface, BLUE, (box_x, box_y, box_width, box_height), 2) # Blue border

        # Title
        title_text = "Unsaved Changes"
        title_surf = self.font_large.render(title_text, True, BLUE)
        title_rect = title_surf.get_rect(midtop=(surface.get_width() // 2, box_y + 15))
        surface.blit(title_surf, title_rect)

        # Song name (ensure current_song exists)
        song_name = "Error: No current song" # Default/fallback text
        current_song = getattr(self.app, 'current_song', None)
        if current_song:
            song_name = current_song.name

        song_text = f"in '{song_name}'"
        song_surf = self.font.render(song_text, True, WHITE)
        song_rect = song_surf.get_rect(midtop=(surface.get_width() // 2, title_rect.bottom + 10))
        surface.blit(song_surf, song_rect)

        # Instructions using button map
        save_btn = mappings.button_map.get(mappings.SAVE_CC, f"CC{mappings.SAVE_CC}")
        discard_btn = mappings.button_map.get(mappings.DELETE_CC, f"CC{mappings.DELETE_CC}") # Using DELETE for discard
        cancel_btn = mappings.button_map.get(mappings.NO_NAV_CC, f"CC{mappings.NO_NAV_CC}")

        instr1_text = f"Save Changes? ({save_btn})"
        instr2_text = f"Discard Changes? ({discard_btn})"
        instr3_text = f"Cancel Load? ({cancel_btn})"

        instr1_surf = self.font.render(instr1_text, True, GREEN)
        instr1_rect = instr1_surf.get_rect(midtop=(surface.get_width() // 2, song_rect.bottom + 20))
        surface.blit(instr1_surf, instr1_rect)

        instr2_surf = self.font.render(instr2_text, True, RED)
        instr2_rect = instr2_surf.get_rect(midtop=(surface.get_width() // 2, instr1_rect.bottom + 5))
        surface.blit(instr2_surf, instr2_rect)

        instr3_surf = self.font.render(instr3_text, True, WHITE)
        instr3_rect = instr3_surf.get_rect(midtop=(surface.get_width() // 2, instr2_rect.bottom + 5))
        surface.blit(instr3_surf, instr3_rect)

