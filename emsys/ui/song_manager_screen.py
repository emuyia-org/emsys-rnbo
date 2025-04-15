# emsys/ui/song_manager_screen.py
# -*- coding: utf-8 -*-
"""
Screen for managing Songs (Loading, Creating, Renaming, Deleting).
Uses a helper for confirmation prompts.
"""
import pygame
import time
from datetime import datetime
from typing import List, Optional, Tuple, Any

# Core components
from ..core.song import Song, Segment

# Base class and widgets
from .base_screen import BaseScreen
from .widgets import TextInputWidget, TextInputStatus

# Utilities and Config
from ..utils import file_io
from ..config import settings, mappings

# --- Import Helpers ---
from .helpers.confirmation_prompts import ConfirmationPrompts, PromptType
# --------------------

# Import colors and constants
from emsys.config.settings import (WHITE, BLACK, GREEN, RED, BLUE, GREY,
                                   HIGHLIGHT_COLOR, FEEDBACK_COLOR, ERROR_COLOR,
                                   FEEDBACK_AREA_HEIGHT)

# Define layout constants
LEFT_MARGIN = 15
TOP_MARGIN = 15
LINE_HEIGHT = 30
LIST_TOP_PADDING = 10
LIST_ITEM_INDENT = 25

class SongManagerScreen(BaseScreen):
    """Screen for listing, loading, creating, renaming, and deleting songs."""

    def __init__(self, app_ref):
        """Initialize the song manager screen."""
        super().__init__(app_ref)
        # --- Initialize Helpers ---
        self.prompts = ConfirmationPrompts(app_ref)
        # -------------------------

        # --- Fonts ---
        self.font_large = pygame.font.Font(None, 48)
        self.font_small = pygame.font.Font(None, 24)
        self.font = pygame.font.Font(None, 30) # Standard list font size

        # --- State ---
        self.song_list: List[str] = []
        self.selected_index: Optional[int] = None
        self.scroll_offset: int = 0
        self.feedback_message: Optional[Tuple[str, float, Tuple[int, int, int]]] = None
        self.feedback_duration: float = 3.0
        self.text_input_widget = TextInputWidget(app_ref)
        self.is_renaming: bool = False # Explicit flag for rename state
        self.is_creating: bool = False # Explicit flag for create state
        # Store title rect for positioning calculations
        self.title_rect = pygame.Rect(0,0,0,0)
        # -------------------------

    def init(self):
        """Called when the screen becomes active. Load the song list."""
        super().init()
        print(f"{self.__class__.__name__} is now active.")
        self._refresh_song_list()
        self.clear_feedback()
        self.text_input_widget.cancel()
        self.prompts.deactivate() # Ensure no prompts active
        self.is_renaming = False
        self.is_creating = False
        # Update title rect
        title_text = "Song Manager"
        title_surf = self.font_large.render(title_text, True, WHITE)
        self.title_rect = title_surf.get_rect(midtop=(self.app.screen.get_width() // 2, TOP_MARGIN))


    def cleanup(self):
        """Called when the screen becomes inactive."""
        super().cleanup()
        print(f"{self.__class__.__name__} is being deactivated.")
        self.text_input_widget.cancel()
        self.prompts.deactivate()
        self.clear_feedback()
        self.is_renaming = False
        self.is_creating = False

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
        """Handle MIDI messages for list navigation, selection, and actions."""
        if msg.type != 'control_change': return

        cc = msg.control
        value = msg.value

        # --- Handle Text Input Mode FIRST ---
        if self.text_input_widget.is_active:
            if value == 127: # Only handle button presses
                status = self.text_input_widget.handle_input(cc)
                if status == TextInputStatus.CONFIRMED:
                    if self.is_creating: self._confirm_song_create()
                    elif self.is_renaming: self._confirm_song_rename()
                elif status == TextInputStatus.CANCELLED:
                    if self.is_creating: self._cancel_song_create()
                    elif self.is_renaming: self._cancel_song_rename()
                # Widget remains active until confirm/cancel logic completes
            return # Prevent further processing

        # --- Handle Confirmation Prompts ---
        if self.prompts.is_active():
            action = self.prompts.handle_input(cc, value) # Returns 'confirm', 'discard', 'cancel' or None
            if action:
                prompt_type = self.prompts.active_prompt # Get type before deactivating
                # print(f"Prompt action '{action}' received for prompt {prompt_type.name}") # Debug
                self.prompts.deactivate() # Deactivate prompt after receiving action

                if prompt_type == PromptType.DELETE_SONG:
                    if action == 'confirm': self._perform_delete()
                    elif action == 'cancel': self.set_feedback("Delete cancelled.")
                elif prompt_type == PromptType.UNSAVED_LOAD:
                    if action == 'confirm': self._save_current_and_load_selected()
                    elif action == 'discard': self._discard_changes_and_load_selected()
                    elif action == 'cancel': self._cancel_load_due_to_unsaved()
                elif prompt_type == PromptType.UNSAVED_CREATE:
                    if action == 'confirm': self._save_current_and_proceed_to_create()
                    elif action == 'discard': self._discard_changes_and_proceed_to_create()
                    elif action == 'cancel': self._cancel_create_due_to_unsaved()
            return # Prevent further processing

        # --- Handle Fader Selection ---
        if cc == mappings.FADER_SELECT_CC:
            self._handle_fader_selection(value)
            return

        # --- Normal Mode (Button Presses Only) ---
        if value != 127: return

        # --- Action Buttons ---
        if cc == mappings.CREATE_CC:
            self._initiate_create_new_song()
        elif cc == mappings.RENAME_CC:
            self._start_song_rename()
        elif cc == mappings.DELETE_CC:
            self._initiate_delete_selected_song()
        # --- List Navigation/Selection ---
        elif not self.song_list: # If list empty, only actions above work
            self.set_feedback("No songs found.")
        elif cc == mappings.DOWN_NAV_CC:
            self._change_selection(1)
        elif cc == mappings.UP_NAV_CC:
            self._change_selection(-1)
        elif cc == mappings.YES_NAV_CC:
            self._initiate_load_selected_song() # Check for unsaved changes first


    # --- List Management ---
    def _refresh_song_list(self):
        """Fetches the list of songs from file_io and resets selection."""
        current_selection_name = None
        if self.selected_index is not None and self.selected_index < len(self.song_list):
            try: current_selection_name = self.song_list[self.selected_index]
            except IndexError: pass

        self.song_list = file_io.list_songs()
        self.scroll_offset = 0

        if not self.song_list:
            self.selected_index = None
        else:
            # Try to re-select by name
            if current_selection_name in self.song_list:
                try:
                    self.selected_index = self.song_list.index(current_selection_name)
                    self._adjust_scroll() # Adjust scroll to show selection
                except ValueError:
                    self.selected_index = 0 # Fallback to first item
            else:
                self.selected_index = 0 # Default to first item

        print(f"Refreshed songs: {len(self.song_list)}, Selected: {self.selected_index}")


    def _change_selection(self, direction: int):
        """Changes the selected index and adjusts scroll."""
        if not self.song_list: return
        num_songs = len(self.song_list)

        if self.selected_index is None:
            self.selected_index = 0 if direction > 0 else num_songs - 1
        else:
            self.selected_index = (self.selected_index + direction + num_songs) % num_songs

        self._adjust_scroll()
        self.clear_feedback()

    def _handle_fader_selection(self, fader_value: int):
        """Selects an item based on fader value."""
        if not self.song_list: return
        num_songs = len(self.song_list)
        reversed_value = 127 - fader_value
        target_index = max(0, min(num_songs - 1, int((reversed_value / 128.0) * num_songs)))

        if target_index != self.selected_index:
            # print(f"[Fader Debug] Selecting index {target_index}") # Debug
            self.selected_index = target_index
            self._adjust_scroll()
            self.clear_feedback()

    def _adjust_scroll(self):
        """Adjusts scroll offset based on selected index."""
        if self.selected_index is None: return
        max_visible = self._get_max_visible_items()
        num_songs = len(self.song_list)
        if num_songs <= max_visible:
            self.scroll_offset = 0
            return

        # Scroll down
        if self.selected_index >= self.scroll_offset + max_visible:
            self.scroll_offset = self.selected_index - max_visible + 1
        # Scroll up
        elif self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        # Ensure offset is valid
        self.scroll_offset = max(0, min(self.scroll_offset, num_songs - max_visible))


    # --- Song Actions (Initiation, Confirmation, Cancellation) ---

    # Load
    def _initiate_load_selected_song(self):
        if self.selected_index is None or not self.song_list:
            self.set_feedback("No song selected to load.", is_error=True)
            return
        try:
            basename_to_load = self.song_list[self.selected_index]
            current_song = getattr(self.app, 'current_song', None)

            if current_song and current_song.name == basename_to_load:
                self.set_feedback(f"'{basename_to_load}' is already loaded.")
                # Navigate to edit screen immediately if already loaded
                # Assuming screen manager has reference to edit screen instance
                edit_screen = getattr(self.app.screen_manager, 'song_edit_screen', None)
                if edit_screen:
                     self.app.set_active_screen(edit_screen) # Request change
                return

            if current_song and current_song.dirty:
                 # Activate unsaved changes prompt via helper
                 self.prompts.activate(PromptType.UNSAVED_LOAD, data=basename_to_load)
                 self.set_feedback(f"'{current_song.name}' has unsaved changes!", is_error=True)
            else:
                self._perform_load(basename_to_load) # Load directly

        except IndexError:
            self.set_feedback("Error: Invalid selection index.", is_error=True)

    def _perform_load(self, basename_to_load: str):
        """Internal: Actually loads the song and sets it as current."""
        self.set_feedback(f"Loading '{basename_to_load}'...")
        pygame.display.flip()
        loaded_song = file_io.load_song(basename_to_load)

        if loaded_song:
            self.app.current_song = loaded_song # Update the main app's state
            self.set_feedback(f"Loaded '{basename_to_load}'")
            # Navigate to Song Edit Screen
            edit_screen = getattr(self.app.screen_manager, 'song_edit_screen', None)
            if edit_screen:
                self.app.set_active_screen(edit_screen) # Request screen change
            else:
                 self.set_feedback(f"Loaded '{basename_to_load}', but edit screen unavailable.", is_error=True)
        else:
            self.set_feedback(f"Failed to load '{basename_to_load}'", is_error=True)
        # Prompt state is reset when handling the prompt action

    def _save_current_and_load_selected(self):
        """Handles 'Save' action from the unsaved prompt."""
        current_song = getattr(self.app, 'current_song', None)
        basename_to_load = self.prompts.prompt_data # Get target from prompt data

        if not current_song or not basename_to_load:
            self.set_feedback("Error: State invalid for save/load.", is_error=True)
            return

        self.set_feedback(f"Saving '{current_song.name}'...")
        pygame.display.flip()

        if file_io.save_song(current_song):
            self.set_feedback(f"Saved. Now loading '{basename_to_load}'...")
            pygame.display.flip()
            self._perform_load(basename_to_load)
        else:
            self.set_feedback(f"Save failed! Load cancelled.", is_error=True)

    def _discard_changes_and_load_selected(self):
        """Handles 'Discard' action from the unsaved prompt."""
        current_song = getattr(self.app, 'current_song', None)
        basename_to_load = self.prompts.prompt_data

        if not basename_to_load:
            self.set_feedback("Error: No target song to load.", is_error=True)
            return

        if current_song:
            current_song.dirty = False
            self.set_feedback(f"Discarded changes. Loading '{basename_to_load}'...")
        else:
            self.set_feedback(f"No changes to discard. Loading '{basename_to_load}'...")
        pygame.display.flip()
        self._perform_load(basename_to_load)

    def _cancel_load_due_to_unsaved(self):
        """Handles 'Cancel' action from the unsaved prompt."""
        self.set_feedback("Load cancelled.")

    # Create
    def _initiate_create_new_song(self):
        current_song = getattr(self.app, 'current_song', None)
        if current_song and current_song.dirty:
             # Activate unsaved changes prompt for create
             self.prompts.activate(PromptType.UNSAVED_CREATE)
             self.set_feedback("Current song has unsaved changes!", is_error=True)
        else:
            self._proceed_to_create_name_input()

    def _proceed_to_create_name_input(self):
        """Activates the text input widget for the new song name."""
        self.is_creating = True
        self.is_renaming = False
        # Generate default name
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_name = f"NewSong-{timestamp}"
        i = 1
        final_default_name = default_name
        while final_default_name in self.song_list:
            final_default_name = f"{default_name}-{i}"
            i += 1
        self.text_input_widget.start(initial_text=final_default_name, prompt="Create New Song")
        self.set_feedback("Enter name for the new song.")

    def _confirm_song_create(self):
        """Creates the new song file after name confirmation."""
        new_name = self.text_input_widget.get_text()
        if new_name is None:
             self.set_feedback("Error getting name.", is_error=True)
             self._reset_create_rename_state()
             return
        new_name = new_name.strip()
        if not new_name:
            self.set_feedback("Song name cannot be empty.", is_error=True)
            # Keep widget active for user to correct
            return
        if new_name in self.song_list:
            self.set_feedback(f"Song '{new_name}' already exists.", is_error=True)
            # Keep widget active
            return

        print(f"Creating new song: '{new_name}'")
        try:
            new_song = Song(name=new_name) # Create empty song object
            if file_io.save_song(new_song):
                self.set_feedback(f"Created '{new_name}'")
                self.app.current_song = new_song # Set as current
                self._refresh_song_list() # Update list
                # Navigate to Edit Screen
                edit_screen = getattr(self.app.screen_manager, 'song_edit_screen', None)
                if edit_screen:
                    self.app.set_active_screen(edit_screen) # Request change
                else:
                    print("Warning: Edit screen not found after create.")
            else:
                self.set_feedback(f"Failed to save new song '{new_name}'", is_error=True)
        except Exception as e:
            self.set_feedback(f"Error creating song: {e}", is_error=True)
            print(f"Error during song creation: {e}")

        self._reset_create_rename_state() # Reset state after attempt

    def _cancel_song_create(self):
        """Cancels the song creation process."""
        self.set_feedback("Create cancelled.")
        self._reset_create_rename_state()

    def _save_current_and_proceed_to_create(self):
        """Handles 'Save' action from the UNSAVED_CREATE prompt."""
        current_song = getattr(self.app, 'current_song', None)
        if not current_song:
            self.set_feedback("Error: No current song to save.", is_error=True)
            return
        self.set_feedback(f"Saving '{current_song.name}'...")
        pygame.display.flip()
        if file_io.save_song(current_song):
            self.set_feedback("Saved. Proceeding to create...")
            self._proceed_to_create_name_input()
        else:
            self.set_feedback("Save failed! Create cancelled.", is_error=True)

    def _discard_changes_and_proceed_to_create(self):
        """Handles 'Discard' action from the UNSAVED_CREATE prompt."""
        current_song = getattr(self.app, 'current_song', None)
        if current_song:
            current_song.dirty = False
            self.set_feedback("Discarded changes. Proceeding to create...")
        else:
             self.set_feedback("No changes to discard. Proceeding...")
        self._proceed_to_create_name_input()

    def _cancel_create_due_to_unsaved(self):
        """Handles 'Cancel' action from the UNSAVED_CREATE prompt."""
        self.set_feedback("Create cancelled.")


    # Rename
    def _start_song_rename(self):
        """Initiates renaming the selected song."""
        if self.selected_index is None or not self.song_list:
            self.set_feedback("No song selected to rename", is_error=True)
            return
        try:
            current_name = self.song_list[self.selected_index]
            self.is_renaming = True
            self.is_creating = False
            self.text_input_widget.start(current_name, prompt="Rename Song")
            self.clear_feedback()
        except IndexError:
            self.set_feedback("Selection error.", is_error=True)
            self.selected_index = 0 if self.song_list else None

    def _confirm_song_rename(self):
        """Confirms the song rename action."""
        if self.selected_index is None: # Should not happen if is_renaming is true
             self._reset_create_rename_state()
             return

        new_name = self.text_input_widget.get_text()
        if new_name is None:
             self.set_feedback("Error getting name.", is_error=True)
             self._reset_create_rename_state()
             return
        new_name = new_name.strip()

        try:
            old_name = self.song_list[self.selected_index]
        except IndexError:
            self.set_feedback("Selection error.", is_error=True)
            self._reset_create_rename_state()
            return

        if not new_name:
            self.set_feedback("Song name cannot be empty.", is_error=True)
            # Keep widget active
            return
        if new_name == old_name:
            self.set_feedback("Name unchanged.")
            self._reset_create_rename_state()
            return
        if new_name in self.song_list:
             self.set_feedback(f"Name '{new_name}' already exists.", is_error=True)
             # Keep widget active
             return

        print(f"Renaming '{old_name}' to '{new_name}'")
        if file_io.rename_song(old_name, new_name):
            self.set_feedback(f"Renamed to '{new_name}'")
            # Update current song name if it was the one renamed
            current_song = getattr(self.app, 'current_song', None)
            if current_song and current_song.name == old_name:
                current_song.name = new_name
            self._refresh_song_list() # Refresh list
        else:
            self.set_feedback(f"Failed to rename to '{new_name}'", is_error=True)
            # Keep widget active on failure? Maybe. Let's reset for now.
            self._reset_create_rename_state()

        self._reset_create_rename_state() # Reset state after attempt

    def _cancel_song_rename(self):
        """Cancels the song renaming process."""
        self.set_feedback("Rename cancelled.")
        self._reset_create_rename_state()

    def _reset_create_rename_state(self):
        """Resets flags and text widget after create/rename action."""
        self.is_creating = False
        self.is_renaming = False
        self.text_input_widget.cancel()


    # Delete
    def _initiate_delete_selected_song(self):
        """Starts the delete confirmation process."""
        if self.selected_index is None or not self.song_list:
            self.set_feedback("No song selected to delete", is_error=True)
            return
        try:
            song_name = self.song_list[self.selected_index]
            # Activate delete prompt via helper
            self.prompts.activate(PromptType.DELETE_SONG, data=song_name)
            self.set_feedback(f"Delete '{song_name}'?", is_error=True, duration=10.0)
        except IndexError:
            self.set_feedback("Selection error.", is_error=True)

    def _perform_delete(self):
        """Performs the actual deletion after confirmation."""
        song_to_delete = self.prompts.prompt_data # Get name from prompt data
        if not isinstance(song_to_delete, str):
             self.set_feedback("Error: Invalid state for delete.", is_error=True)
             return

        print(f"Deleting song: '{song_to_delete}'")
        if file_io.delete_song(song_to_delete):
            self.set_feedback(f"Deleted '{song_to_delete}'")
            # Clear current song if it was the one deleted
            current_song = getattr(self.app, 'current_song', None)
            if current_song and current_song.name == song_to_delete:
                self.app.current_song = None
                print("Cleared current song (was deleted).")
            self._refresh_song_list() # Update list
        else:
            self.set_feedback(f"Failed to delete '{song_to_delete}'", is_error=True)
        # Prompt state is reset when handling the prompt action


    # --- Drawing Methods ---
    def draw(self, screen_surface, midi_status=None):
        """Draws the screen content, prompts, or the text input widget."""
        if self.text_input_widget.is_active:
            self.text_input_widget.draw(screen_surface)
        elif self.prompts.is_active():
            self._draw_normal_content(screen_surface, midi_status) # Draw list underneath
            self.prompts.draw(screen_surface) # Draw the active prompt
        else:
            self._draw_normal_content(screen_surface, midi_status)
            self._draw_feedback(screen_surface) # Draw feedback only if no prompt/widget


    def _draw_normal_content(self, screen_surface, midi_status=None):
        """Draws the main list view."""
        screen_surface.fill(BLACK)

        # Draw Title
        title_text = "Song Manager"
        title_surf = self.font_large.render(title_text, True, WHITE)
        # Update title_rect here
        self.title_rect = title_surf.get_rect(midtop=(screen_surface.get_width() // 2, TOP_MARGIN))
        screen_surface.blit(title_surf, self.title_rect)

        # Draw Currently Loaded Song Indicator
        current_song = getattr(self.app, 'current_song', None)
        loaded_text = "Loaded: None"
        if current_song:
            dirty_flag = "*" if current_song.dirty else ""
            loaded_text = f"Loaded: {current_song.name}{dirty_flag}"
        loaded_surf = self.font_small.render(loaded_text, True, GREY)
        loaded_rect = loaded_surf.get_rect(topright=(screen_surface.get_width() - LEFT_MARGIN, TOP_MARGIN + 5))
        screen_surface.blit(loaded_surf, loaded_rect)

        # Draw Song List Area
        list_area_top = self.title_rect.bottom + LIST_TOP_PADDING
        list_area_bottom = screen_surface.get_height() - FEEDBACK_AREA_HEIGHT
        list_area_rect = pygame.Rect(LEFT_MARGIN, list_area_top,
                                      screen_surface.get_width() - 2 * LEFT_MARGIN,
                                      list_area_bottom - list_area_top)

        if not self.song_list:
            no_songs_surf = self.font.render("No songs found.", True, WHITE)
            no_songs_rect = no_songs_surf.get_rect(center=list_area_rect.center)
            screen_surface.blit(no_songs_surf, no_songs_rect)
        else:
            self._draw_song_list_items(screen_surface, list_area_rect)


    def _draw_song_list_items(self, screen, area_rect):
         """Draws the scrollable song list items."""
         max_visible = self._get_max_visible_items()
         num_songs = len(self.song_list)
         start_index = self.scroll_offset
         end_index = min(start_index + max_visible, num_songs)
         current_song = getattr(self.app, 'current_song', None)

         # Draw scroll indicators
         if self.scroll_offset > 0:
             self._draw_scroll_arrow(screen, area_rect, 'up')
         if end_index < num_songs:
             self._draw_scroll_arrow(screen, area_rect, 'down')

         # Draw items
         text_y = area_rect.top + LIST_TOP_PADDING
         for i in range(start_index, end_index):
             song_name = self.song_list[i]
             is_selected = (i == self.selected_index)
             text_color = HIGHLIGHT_COLOR if is_selected else WHITE
             is_loaded = current_song and current_song.name == song_name

             # Add indicator for loaded song ('*> ')
             prefix = "*> " if is_loaded else "   "
             item_text = f"{prefix}{song_name}"
             item_surf = self.font.render(item_text, True, text_color)
             item_rect = item_surf.get_rect(topleft=(area_rect.left + 5, text_y))

             # Draw selection background highlight
             if is_selected:
                 bg_rect = pygame.Rect(area_rect.left, text_y - 2, area_rect.width, LINE_HEIGHT)
                 pygame.draw.rect(screen, GREY, bg_rect) # Filled background

             screen.blit(item_surf, item_rect)
             text_y += LINE_HEIGHT


    def _draw_feedback(self, surface):
        """Draws the feedback message at the bottom."""
        if self.feedback_message:
            message, timestamp, color = self.feedback_message
            feedback_surf = self.font_small.render(message, True, color)
            feedback_rect = feedback_surf.get_rect(centerx=surface.get_width() // 2, bottom=surface.get_height() - 10)
            # Optional: Clear background for feedback area
            bg_rect = pygame.Rect(0, surface.get_height() - FEEDBACK_AREA_HEIGHT, surface.get_width(), FEEDBACK_AREA_HEIGHT)
            pygame.draw.rect(surface, BLACK, bg_rect)
            surface.blit(feedback_surf, feedback_rect)

    def _draw_scroll_arrow(self, screen, area_rect, direction):
        """Draws an up or down scroll arrow."""
        arrow_char = "^" if direction == 'up' else "v"
        arrow_surf = self.font_small.render(arrow_char, True, WHITE)
        if direction == 'up':
             arrow_rect = arrow_surf.get_rect(centerx=area_rect.centerx, top=area_rect.top - 5) # Position above list
        else: # down
             arrow_rect = arrow_surf.get_rect(centerx=area_rect.centerx, bottom=area_rect.bottom + 15) # Position below list
        screen.blit(arrow_surf, arrow_rect)

    # --- List Size Calculation ---
    def _get_max_visible_items(self) -> int:
        """Calculate how many list items fit on the screen."""
        list_area_top = self.title_rect.bottom + LIST_TOP_PADDING
        list_area_bottom = self.app.screen.get_height() - FEEDBACK_AREA_HEIGHT
        available_height = list_area_bottom - list_area_top
        if available_height <= 0 or LINE_HEIGHT <= 0: return 0
        return max(1, available_height // LINE_HEIGHT)
