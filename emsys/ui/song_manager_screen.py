# -*- coding: utf-8 -*-
"""
Screen for managing Songs (Loading, Creating, Renaming).
"""
import pygame # Ensure pygame is imported if not already
import time   # Ensure time is imported
from datetime import datetime # Ensure datetime is imported
from typing import List, Optional, Tuple # <<< ADDED List, Optional, Tuple

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

# --- Import colors (imported from settings) ---
from emsys.config.settings import WHITE, BLACK, GREEN, RED, BLUE, HIGHLIGHT_COLOR, FEEDBACK_COLOR, ERROR_COLOR, GREY, FEEDBACK_AREA_HEIGHT # <<< Added GREY and FEEDBACK_AREA_HEIGHT
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

        # --- ADDED: Reset create prompt state ---
        self.create_prompt_active = False
        self.song_name_for_create: Optional[str] = None
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
        # --- ADDED: Reset create prompt state ---
        self.create_prompt_active = False
        self.song_name_for_create: Optional[str] = None
        # ----------------------------------------

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
        # --- ADDED: Reset create prompt state ---
        self.create_prompt_active = False
        self.song_name_for_create = None
        # ------------------------------------------
        self.clear_feedback()

    def _refresh_song_list(self):
        """Fetches the list of songs from file_io and resets selection."""
        current_selection_name = None # <<< Store name instead of index
        if self.selected_index is not None and self.selected_index < len(self.song_list):
            try: # <<< Add try-except for safety
                current_selection_name = self.song_list[self.selected_index]
            except IndexError:
                current_selection_name = None # <<< Handle potential index error

        self.song_list = file_io.list_songs()
        self.scroll_offset = 0 # Reset scroll on refresh

        if not self.song_list:
            self.selected_index = None # <<< No selection if list is empty
        else:
            # Try to re-select the previously selected song by name
            if current_selection_name in self.song_list:
                try:
                    self.selected_index = self.song_list.index(current_selection_name)
                    # Ensure selection is visible
                    max_visible = self._get_max_visible_items()
                    if self.selected_index >= max_visible:
                        self.scroll_offset = self.selected_index - max_visible + 1
                except ValueError:
                    self.selected_index = 0 # Fallback to first item
            else:
                self.selected_index = 0 # Default to first item if previous selection is gone

        print(f"Refreshed songs: {self.song_list}, Selected Index: {self.selected_index}")


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
            return # <<< Added return

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
            status = self.text_input_widget.handle_input(cc)
            if status == TextInputStatus.CONFIRMED:
                # Check if we were creating or renaming
                if self.song_name_for_create is not None: # We were in create flow
                    self._confirm_song_create()
                else: # We were renaming
                    self._confirm_song_rename()
            elif status == TextInputStatus.CANCELLED:
                # Check if we were creating or renaming
                if self.song_name_for_create is not None: # We were in create flow
                    self._cancel_song_create()
                else: # We were renaming
                    self._cancel_song_rename()
            # No return here, widget handles its state
            return # <<< IMPORTANT: Prevent further processing if widget handled it

        # --- Handle Delete Confirmation Mode ---
        if self.delete_confirmation_active:
            if value == 127: # Only react to button presses
                if cc == mappings.YES_NAV_CC:
                    self._perform_delete()
                elif cc == mappings.NO_NAV_CC:
                    self.delete_confirmation_active = False
                    self.set_feedback("Delete cancelled.")
            return # <<< IMPORTANT: Prevent further processing

        # --- Handle Unsaved Changes Prompt Mode (for Loading) ---
        if self.unsaved_prompt_active:
            if value == 127: # Only react to button presses
                if cc == mappings.SAVE_CC: # YES: Save current, then load
                    self._save_current_and_load_selected()
                elif cc == mappings.DELETE_CC: # NO: Discard current, then load
                    self._discard_changes_and_load_selected()
                elif cc == mappings.NO_NAV_CC: # CANCEL: Cancel load
                    self._cancel_load_due_to_unsaved()
            return # <<< IMPORTANT: Prevent further processing

        # --- ADDED: Handle Unsaved Changes Prompt Mode (for Creating) ---
        if self.create_prompt_active:
            if value == 127: # Only react to button presses
                if cc == mappings.SAVE_CC: # YES: Save current, then proceed to create
                    self._save_current_and_proceed_to_create()
                elif cc == mappings.DELETE_CC: # NO: Discard current, then proceed to create
                    self._discard_changes_and_proceed_to_create()
                elif cc == mappings.NO_NAV_CC: # CANCEL: Cancel create
                    self._cancel_create_due_to_unsaved()
            return # <<< IMPORTANT: Prevent further processing
        # -----------------------------------------------------------------


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

            return # <<< Added return

        # --- Normal Song Management Mode (Button Presses Only) ---
        # Process remaining CCs only if they are button presses (value 127)
        if value != 127:
            return # <<< Added return

        # Handle CREATE_CC
        if cc == mappings.CREATE_CC:
            self._initiate_create_new_song() # <<< Use new initiation method
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
            self._load_selected_song() # <<< Check for unsaved changes is now inside this method

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
            self.set_feedback(f"Renamed to '{new_name}'")
            # --- Update current song name if it was the one renamed ---
            current_song = getattr(self.app, 'current_song', None)
            if current_song and current_song.name == old_name:
                current_song.name = new_name
                # Keep dirty status as renaming the file doesn't change content
            # ---------------------------------------------------------
            self._refresh_song_list() # Refresh list to show new name and order
        else:
            # Error message is printed by file_io.rename_song
            self.set_feedback(f"Failed to rename to '{new_name}'", is_error=True)
            # Keep widget active on failure? Or cancel? Let's cancel.
            self.text_input_widget.cancel()

        # Deactivate widget only on success or explicit failure handling above
        # self.text_input_widget.cancel() # Moved into success/failure blocks


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
            self.set_feedback("No song selected to delete.", is_error=True) # <<< Added feedback
            self.delete_confirmation_active = False
            return # <<< Added return

        try:
            song_to_delete = self.song_list[self.selected_index]
            print(f"Attempting to delete song: '{song_to_delete}'")

            if file_io.delete_song(song_to_delete):
                self.set_feedback(f"Deleted '{song_to_delete}'")
                # --- Check if the deleted song was the current song ---
                current_song = getattr(self.app, 'current_song', None)
                if current_song and current_song.name == song_to_delete:
                    self.app.current_song = None # Clear the current song in the app
                    print("Cleared current song as it was deleted.")
                # ----------------------------------------------------
                self._refresh_song_list() # Refresh list and selection
            else:
                # Error message printed by file_io.delete_song
                self.set_feedback(f"Failed to delete '{song_to_delete}'", is_error=True)

        except IndexError:
             self.set_feedback("Error: Invalid selection index.", is_error=True)
        except Exception as e:
            self.set_feedback(f"Error during delete: {e}", is_error=True)
            print(f"Unexpected error during delete: {e}")

        self.delete_confirmation_active = False # Always deactivate confirmation mode


    # --- Modified Create Song Logic ---
    def _initiate_create_new_song(self):
        """
        Checks for unsaved changes before starting the song creation process.
        """
        if self.text_input_widget.is_active: return

        current_song = getattr(self.app, 'current_song', None)

        # Check for unsaved changes
        if current_song and current_song.dirty:
            print("Unsaved changes detected. Activating create prompt.")
            self.create_prompt_active = True
            # We don't have the new name yet, so store None
            self.song_name_for_create = None
            self.set_feedback("Current song has unsaved changes!", is_error=True)
        else:
            # No unsaved changes, proceed directly to getting name
            self._proceed_to_create_name_input()

    def _proceed_to_create_name_input(self):
        """Activates the text input widget to get the new song name."""
        # Generate a default unique name
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_name = f"NewSong-{timestamp}"
        # Ensure the default name doesn't already exist (unlikely but possible)
        i = 1
        final_default_name = default_name
        while final_default_name in self.song_list:
            final_default_name = f"{default_name}-{i}"
            i += 1

        self.song_name_for_create = final_default_name # Store the intended name
        self.text_input_widget.start(initial_text=final_default_name, prompt="Create New Song")
        self.set_feedback("Enter name for the new song.")

    def _confirm_song_create(self):
        """Creates the new song file after getting the name."""
        if not self.text_input_widget.is_active or self.song_name_for_create is None:
            self.set_feedback("Error: Create confirmation in invalid state.", is_error=True)
            self._reset_create_state()
            return

        new_name = self.text_input_widget.get_text()
        if new_name is None:
             self.set_feedback("Error: Could not get name from input.", is_error=True)
             self._reset_create_state()
             return

        new_name = new_name.strip()
        if not new_name:
            self.set_feedback("Error: Song name cannot be empty.", is_error=True)
            # Keep widget active to allow correction? Or cancel? Let's keep active.
            # self._reset_create_state()
            return # Stay in text input

        if new_name in self.song_list:
            self.set_feedback(f"Error: Song '{new_name}' already exists.", is_error=True)
            # Keep widget active
            return # Stay in text input

        print(f"Attempting to create new song: '{new_name}'")
        try:
            # Create a new empty song object
            new_song = Song(name=new_name)
            # Save the new empty song file
            if file_io.save_song(new_song):
                self.set_feedback(f"Created new song '{new_name}'")
                self.app.current_song = new_song # Set as the current song
                self._refresh_song_list() # Update list and select the new song
                # Navigate to Song Edit Screen
                # if self.app.song_edit_screen:
                #     self.app.set_active_screen(self.app.song_edit_screen) # <<< COMMENTED OUT
                # else:
                #     self.set_feedback("Created song, but edit screen unavailable.", is_error=True) # <<< COMMENTED OUT
            else:
                # Error message printed by save_song
                self.set_feedback(f"Failed to save new song '{new_name}'", is_error=True)

        except Exception as e:
            self.set_feedback(f"Error creating song: {e}", is_error=True)
            print(f"Error during song creation: {e}")

        # Reset state regardless of success/failure after attempting save
        self._reset_create_state()


    def _cancel_song_create(self):
        """Cancels the song creation process."""
        self.set_feedback("Create cancelled.")
        self._reset_create_state()

    def _reset_create_state(self):
        """Resets variables related to song creation."""
        self.text_input_widget.cancel()
        self.create_prompt_active = False
        self.song_name_for_create = None

    # --- Methods for Handling Create Prompt ---
    def _save_current_and_proceed_to_create(self):
        """Saves the current song, then proceeds to get the new song name."""
        print("User chose SAVE before creating.")
        current_song = getattr(self.app, 'current_song', None)

        if not current_song:
            self.set_feedback("Error: No current song to save.", is_error=True)
            self._reset_create_state() # Also reset create prompt state
            return

        self.set_feedback(f"Saving '{current_song.name}'...")
        pygame.display.flip()

        if file_io.save_song(current_song):
            self.set_feedback(f"Saved '{current_song.name}'. Proceeding to create...")
            self.create_prompt_active = False # Deactivate prompt
            self._proceed_to_create_name_input() # Start getting name
        else:
            self.set_feedback(f"Failed to save '{current_song.name}'. Create cancelled.", is_error=True)
            self._reset_create_state() # Reset create prompt state on save failure

    def _discard_changes_and_proceed_to_create(self):
        """Discards changes to the current song, then proceeds to get the new song name."""
        print("User chose DISCARD before creating.")
        current_song = getattr(self.app, 'current_song', None)

        if current_song:
            current_song.dirty = False # Mark as not dirty
            # Optionally reload from disk to ensure state is truly discarded?
            # reloaded_song = file_io.load_song(current_song.name)
            # if reloaded_song: self.app.current_song = reloaded_song
            # else: self.app.current_song = None # Failed to reload, clear it
            self.set_feedback(f"Discarded changes in '{current_song.name}'. Proceeding...")
        else:
            self.set_feedback("No current song changes to discard. Proceeding...")

        self.create_prompt_active = False # Deactivate prompt
        self._proceed_to_create_name_input() # Start getting name

    def _cancel_create_due_to_unsaved(self):
        """Cancels the pending create operation."""
        print("User chose CANCEL create.")
        self.set_feedback("Create cancelled.")
        self._reset_create_state() # Reset create prompt state

    # --- End Create Song Logic ---

    def _load_selected_song(self):
        """
        Attempts to load the selected song. Checks for unsaved changes in the
        current song before proceeding.
        """
        if self.text_input_widget.is_active: return
        if self.selected_index is None or not self.song_list:
            self.set_feedback("No song selected to load.", is_error=True)
            return

        try:
            basename_to_load = self.song_list[self.selected_index]
            current_song = getattr(self.app, 'current_song', None)

            # If the selected song is already loaded, do nothing (or maybe go to edit screen?)
            if current_song and current_song.name == basename_to_load:
                self.set_feedback(f"'{basename_to_load}' is already loaded.")
                # Optionally navigate to edit screen if desired
                if self.app.song_edit_screen:
                    self.app.set_active_screen(self.app.song_edit_screen)
                return

            # Check for unsaved changes in the *current* song
            if current_song and current_song.dirty:
                print("Unsaved changes detected. Activating load prompt.")
                self.unsaved_prompt_active = True
                self.song_to_load_after_prompt = basename_to_load # Store target
                self.set_feedback(f"'{current_song.name}' has unsaved changes!", is_error=True)
            else:
                # No unsaved changes, proceed directly to loading
                self._perform_load(basename_to_load)

        except IndexError:
            self.set_feedback("Error: Invalid selection index.", is_error=True)
        except Exception as e:
            self.set_feedback(f"Error preparing to load: {e}", is_error=True)
            print(f"Error in _load_selected_song: {e}")


    def _perform_load(self, basename_to_load: str):
        """Internal method to actually load the song file."""
        self.set_feedback(f"Loading '{basename_to_load}'...")
        pygame.display.flip() # Show feedback immediately

        loaded_song = file_io.load_song(basename_to_load)

        if loaded_song:
            self.app.current_song = loaded_song # Update the main app's current song
            self.set_feedback(f"Loaded '{basename_to_load}'")
            # Navigate to Song Edit Screen after successful load
            # if self.app.song_edit_screen:
            #     self.app.set_active_screen(self.app.song_edit_screen) # <<< COMMENTED OUT
            # else:
            #     self.set_feedback(f"Loaded '{basename_to_load}', but edit screen unavailable.", is_error=True) # <<< COMMENTED OUT
        else:
            # Error message printed by load_song
            self.set_feedback(f"Failed to load '{basename_to_load}'", is_error=True)
            # Should we clear the current song if load fails? Maybe not.
            # self.app.current_song = None

        # Reset prompt state regardless of success/failure
        self._reset_prompt_state() # Use the helper


    def _save_current_and_load_selected(self):
        """Saves the current song, then loads the selected one."""
        print("User chose SAVE.")
        current_song = getattr(self.app, 'current_song', None)
        basename_to_load = self.song_to_load_after_prompt

        if not current_song or not basename_to_load:
            self.set_feedback("Error: Cannot save/load, state invalid.", is_error=True)
            self._reset_prompt_state()
            return

        self.set_feedback(f"Saving '{current_song.name}'...")
        pygame.display.flip()

        if file_io.save_song(current_song):
            self.set_feedback(f"Saved '{current_song.name}'. Now loading...")
            pygame.display.flip()
            # Proceed to load the target song
            self._perform_load(basename_to_load) # This will reset prompt state
        else:
            # Error message printed by save_song
            self.set_feedback(f"Failed to save '{current_song.name}'. Load cancelled.", is_error=True)
            self._reset_prompt_state() # Reset prompt state on save failure


    def _discard_changes_and_load_selected(self):
        """Discards changes to the current song, then loads the selected one."""
        print("User chose DISCARD.")
        current_song = getattr(self.app, 'current_song', None)
        basename_to_load = self.song_to_load_after_prompt

        if not basename_to_load:
            self.set_feedback("Error: No target song to load.", is_error=True)
            self._reset_prompt_state()
            return

        if current_song:
            current_song.dirty = False # Mark as not dirty
            self.set_feedback(f"Discarded changes in '{current_song.name}'. Now loading...")
        else:
            self.set_feedback("No current song changes to discard. Now loading...")

        pygame.display.flip()
        # Proceed to load the target song
        self._perform_load(basename_to_load) # This will reset prompt state


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
        list_area_bottom = self.app.screen.get_height() - FEEDBACK_AREA_HEIGHT # <<< Use constant
        available_height = list_area_bottom - list_area_top
        if available_height <= 0 or LINE_HEIGHT <= 0:
            return 1 # <<< Return 1 instead of 0
        return available_height // LINE_HEIGHT

    def draw(self, screen_surface, midi_status=None):
        """Draws the screen content or the text input widget."""
        # --- Draw Text Input Interface if active ---
        if self.text_input_widget.is_active:
            # Assume widget draws over everything, or clear first if needed
            # screen_surface.fill(BLACK) # Optional clear
            self.text_input_widget.draw(screen_surface)
            # No feedback message when text input is active
        elif self.unsaved_prompt_active:
            self._draw_normal_content(screen_surface, midi_status) # Draw list underneath
            self._draw_unsaved_prompt(screen_surface, "Load Song") # <<< Pass context
        elif self.create_prompt_active: # <<< ADDED
            self._draw_normal_content(screen_surface, midi_status) # Draw list underneath
            self._draw_unsaved_prompt(screen_surface, "Create Song") # <<< Pass context
        elif self.delete_confirmation_active:
             self._draw_normal_content(screen_surface, midi_status) # Draw list underneath
             self._draw_delete_confirmation(screen_surface)
        else:
            # --- Draw Normal Content ---
            self._draw_normal_content(screen_surface, midi_status)
            # --- Draw Feedback Message (Common) ---
            self._draw_feedback(screen_surface)


    def _draw_normal_content(self, screen_surface, midi_status=None):
        """Draws the main list view."""
        # Clear background
        screen_surface.fill(BLACK)

        # Draw Title
        screen_surface.blit(self.title_surf, self.title_rect)

        # --- Draw Currently Loaded Song Indicator ---
        current_song = getattr(self.app, 'current_song', None)
        loaded_text = "Loaded: None"
        if current_song:
            dirty_flag = "*" if current_song.dirty else ""
            loaded_text = f"Loaded: {current_song.name}{dirty_flag}"

        loaded_surf = self.font_small.render(loaded_text, True, GREY) # Use smaller font, grey color
        loaded_rect = loaded_surf.get_rect(topright=(screen_surface.get_width() - LEFT_MARGIN, TOP_MARGIN + 5))
        screen_surface.blit(loaded_surf, loaded_rect)
        # --------------------------------------------

        # Draw Song List
        list_area_top = self.title_rect.bottom + LIST_TOP_PADDING
        max_visible = self._get_max_visible_items()
        list_end_index = min(self.scroll_offset + max_visible, len(self.song_list))

        if not self.song_list:
            no_songs_surf = self.font.render("No songs found.", True, WHITE)
            no_songs_rect = no_songs_surf.get_rect(centerx=screen_surface.get_width() // 2, top=list_area_top + 20)
            screen_surface.blit(no_songs_surf, no_songs_rect)
        else:
            for i in range(self.scroll_offset, list_end_index):
                song_name = self.song_list[i]
                display_index = i - self.scroll_offset # 0-based index for drawing position
                y_pos = list_area_top + (display_index * LINE_HEIGHT)

                is_selected = (i == self.selected_index)
                text_color = HIGHLIGHT_COLOR if is_selected else WHITE

                # Determine if this song is the currently loaded song
                is_loaded = current_song and current_song.name == song_name
                # Remove the '>' prefix and use a fixed indent
                prefix = "  "
                item_text = f"{prefix}{song_name}"
                item_surf = self.font.render(item_text, True, text_color)
                item_rect = item_surf.get_rect(topleft=(LEFT_MARGIN + LIST_ITEM_INDENT, y_pos))

                # Draw selection background if the item is selected
                if is_selected:
                    bg_rect = pygame.Rect(LEFT_MARGIN, y_pos - 2, screen_surface.get_width() - (2 * LEFT_MARGIN), LINE_HEIGHT)
                    pygame.draw.rect(screen_surface, GREY, bg_rect)  # Filled background for proper highlight

                # Blit the song name text
                screen_surface.blit(item_surf, item_rect)

                # If the song is loaded, draw a colored border around it
                if is_loaded:
                    # Inflate the rectangle to create a border around the text
                    border_rect = item_rect.inflate(8, 8)
                    pygame.draw.rect(screen_surface, GREEN, border_rect, 2)  # 2-pixel thick border

            # --- Draw Scroll Indicators ---
            if len(self.song_list) > max_visible:
                # Up arrow if not at the top
                if self.scroll_offset > 0:
                    up_arrow_surf = self.font_small.render("^", True, WHITE)
                    up_arrow_rect = up_arrow_surf.get_rect(centerx=screen_surface.get_width() // 2, top=list_area_top - 15)
                    screen_surface.blit(up_arrow_surf, up_arrow_rect)
                # Down arrow if not at the bottom
                if self.scroll_offset + max_visible < len(self.song_list):
                    down_arrow_surf = self.font_small.render("v", True, WHITE)
                    down_arrow_rect = down_arrow_surf.get_rect(centerx=screen_surface.get_width() // 2, bottom=screen_surface.get_height() - FEEDBACK_AREA_HEIGHT + 10)
                    screen_surface.blit(down_arrow_surf, down_arrow_rect)
            # -----------------------------


    def _draw_feedback(self, surface):
        """Draws the feedback message at the bottom."""
        if self.feedback_message:
            message, timestamp, color = self.feedback_message
            feedback_surf = self.font_small.render(message, True, color)
            feedback_rect = feedback_surf.get_rect(centerx=surface.get_width() // 2, bottom=surface.get_height() - 10)
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

    def _draw_unsaved_prompt(self, surface, context: str = "Operation"): # <<< Added context parameter
        """Draws the unsaved changes prompt overlay."""
        # Create semi-transparent overlay
        overlay = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))  # Semi-transparent black
        surface.blit(overlay, (0, 0))

        # Draw confirmation box
        box_width, box_height = 400, 200 # Slightly taller
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

        # --- Modify text based on context ---
        cancel_action_text = f"Cancel {context}"

        instr1_text = f"Save Changes? ({save_btn})"
        instr2_text = f"Discard Changes? ({discard_btn})"
        instr3_text = f"{cancel_action_text}? ({cancel_btn})"
        # ------------------------------------

        instr1_surf = self.font.render(instr1_text, True, GREEN)
        instr1_rect = instr1_surf.get_rect(midtop=(surface.get_width() // 2, song_rect.bottom + 20))
        surface.blit(instr1_surf, instr1_rect)

        instr2_surf = self.font.render(instr2_text, True, RED)
        instr2_rect = instr2_surf.get_rect(midtop=(surface.get_width() // 2, instr1_rect.bottom + 10)) # <<< Increased spacing
        surface.blit(instr2_surf, instr2_rect)

        instr3_surf = self.font.render(instr3_text, True, WHITE)
        instr3_rect = instr3_surf.get_rect(midtop=(surface.get_width() // 2, instr2_rect.bottom + 10)) # <<< Increased spacing
        surface.blit(instr3_surf, instr3_rect)

