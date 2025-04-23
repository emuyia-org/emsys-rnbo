# emsys/ui/song_manager_screen.py
# -*- coding: utf-8 -*-
"""
Screen for managing Songs (Loading, Creating, Renaming, Deleting).
Uses SongService for data operations and state.
"""
import pygame
import time
import os
from datetime import datetime
from typing import List, Optional, Tuple, Any

# Core components (SongService is now the primary interface)
# from ..core.song import Song, Segment # No longer needed directly

# Base class and widgets
from .base_screen import BaseScreen
from .widgets import TextInputWidget, TextInputStatus

# Utilities and Config (Mappings needed for CCs)
# from ..utils import file_io # No longer needed directly
from ..config import settings, mappings

# --- Import Helpers ---
from .helpers.confirmation_prompts import ConfirmationPrompts, PromptType
# --------------------

# Import Service Layer
from ..services.song_service import SongService # <<< IMPORT SongService

# Import colors and constants
from emsys.config.settings import (WHITE, BLACK, GREEN, RED, BLUE, GREY,
                                   HIGHLIGHT_COLOR, FEEDBACK_COLOR, ERROR_COLOR,
                                   FEEDBACK_AREA_HEIGHT)

# Import SongEditScreen for type checking
from .song_edit_screen import SongEditScreen

# Define layout constants
LEFT_MARGIN = 15
TOP_MARGIN = 15
LINE_HEIGHT = 30
LIST_TOP_PADDING = 10
LIST_ITEM_INDENT = 25

class SongManagerScreen(BaseScreen):
    """Screen for listing, loading, creating, renaming, and deleting songs using SongService."""

    def __init__(self, app, song_service: SongService): # <<< ACCEPT SongService
        """Initialize the song manager screen."""
        super().__init__(app)
        self.song_service = song_service # <<< STORE SongService reference
        # --- Initialize Helpers ---
        self.prompts = ConfirmationPrompts(app)
        # -------------------------

        # --- Fonts ---
        self.font_large = self.get_pixel_font(28)
        self.font_medium = self.get_pixel_font(22) # Used for playback status
        self.font_small = self.get_pixel_font(20) # Used for list items
        self.font_tiny = self.get_pixel_font(16) # Used for scroll arrows, maybe status details
        self.font = self.font_small # Default font for items
        self.title_rect = pygame.Rect(0,0,0,0)

        # --- State ---
        self.song_list: List[str] = []
        self.selected_index: Optional[int] = None
        self.scroll_offset: int = 0
        self.feedback_message: Optional[Tuple[str, float, Tuple[int, int, int]]] = None
        self.feedback_duration: float = 3.0
        self.text_input_widget = TextInputWidget(app)
        self.is_renaming: bool = False
        self.is_creating: bool = False
        self.title_rect = pygame.Rect(0,0,0,0)
        self.no_button_held: bool = False # <<< ADDED: Track NO button state
        # -------------------------

    def init(self):
        """Called when the screen becomes active. Load the song list via SongService."""
        super().init()
        print(f"{self.__class__.__name__} is now active.")
        self._refresh_song_list() # Uses song_service.list_song_names()
        self.clear_feedback()
        self.text_input_widget.cancel()
        self.prompts.deactivate()
        self.is_renaming = False
        self.is_creating = False
        self.no_button_held = False # <<< ADDED: Reset NO button state on init
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
        self.no_button_held = False # <<< ADDED: Reset NO button state on cleanup

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

        # --- Handle NO Button State FIRST (Press/Release) ---
        # We need to track this regardless of other states (prompts, text input)
        # so the flag is correct when CREATE is pressed.
        if cc == mappings.NO_NAV_CC:
            if value == 127:
                self.no_button_held = True
                # print("NO button pressed") # Debug
            elif value == 0:
                self.no_button_held = False
                # print("NO button released") # Debug
            # Allow NO press/release to potentially be handled by prompts/widgets below
            # but ensure the flag is set/unset correctly here.

        # --- Handle Text Input Mode ---
        if self.text_input_widget.is_active:
            if value == 127: # Only handle button presses
                status = self.text_input_widget.handle_input(cc)
                if status == TextInputStatus.CONFIRMED:
                    if self.is_creating: self._confirm_song_create()
                    elif self.is_renaming: self._confirm_song_rename()
                elif status == TextInputStatus.CANCELLED:
                    if self.is_creating: self._cancel_song_create()
                    elif self.is_renaming: self._cancel_song_rename()
            return # Return after handling text input or NO button state update

        # --- Handle Confirmation Prompts ---
        if self.prompts.is_active():
            action = self.prompts.handle_input(cc, value)
            if action:
                prompt_type = self.prompts.active_prompt
                prompt_data = self.prompts.prompt_data # <<< CAPTURE data before deactivating
                self.prompts.deactivate() # Deactivate prompt

                if prompt_type == PromptType.DELETE_SONG:
                    if action == 'confirm': self._perform_delete(prompt_data) # Pass data
                    elif action == 'cancel': self.set_feedback("Delete cancelled.")
                elif prompt_type == PromptType.UNSAVED_LOAD:
                    if action == 'confirm': self._save_current_and_load_selected(prompt_data) # Pass data
                    elif action == 'discard': self._discard_changes_and_load_selected(prompt_data) # Pass data
                    elif action == 'cancel': self._cancel_load_due_to_unsaved()
                elif prompt_type == PromptType.UNSAVED_CREATE:
                    if action == 'confirm': self._save_current_and_proceed_to_create()
                    elif action == 'discard': self._discard_changes_and_proceed_to_create()
                    elif action == 'cancel': self._cancel_create_due_to_unsaved()
            return # Return after handling prompt input or NO button state update

        # --- Handle Fader Selection ---
        if cc == mappings.FADER_B_CC:
            self._handle_fader_selection(value)
            return # Return after handling fader or NO button state update

        # --- Normal Mode (Button Presses Only, value == 127) ---
        if value != 127: return # Ignore releases here (except NO handled above)

        # --- Action Buttons ---
        if cc == mappings.CREATE_CC:
            # <<< MODIFIED: Check NO button state for duplication >>>
            if self.no_button_held:
                self._initiate_duplicate_selected_song()
            else:
                self._initiate_create_new_song()
        elif cc == mappings.RENAME_CC:
            self._start_song_rename()
        elif cc == mappings.DELETE_CC:
            self._initiate_delete_selected_song()
        # --- List Navigation/Selection ---
        elif not self.song_list:
            self.set_feedback("No songs found.")
        elif cc == mappings.DOWN_NAV_CC:
            self._change_selection(1)
        elif cc == mappings.UP_NAV_CC:
            self._change_selection(-1)
        elif cc == mappings.YES_NAV_CC:
            self._initiate_load_selected_song()


    # --- List Management ---
    def _refresh_song_list(self):
        """Fetches the list of songs from SongService and resets selection."""
        current_selection_name = None
        if self.selected_index is not None and self.selected_index < len(self.song_list):
            try: current_selection_name = self.song_list[self.selected_index]
            except IndexError: pass

        self.song_list = self.song_service.list_song_names() # <<< Use SongService
        self.scroll_offset = 0

        if not self.song_list:
            self.selected_index = None
        else:
            if current_selection_name in self.song_list:
                try:
                    self.selected_index = self.song_list.index(current_selection_name)
                    self._adjust_scroll()
                except ValueError:
                    self.selected_index = 0
            else:
                self.selected_index = 0

        print(f"Refreshed songs via SongService: {len(self.song_list)}, Selected: {self.selected_index}")


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

        if self.selected_index >= self.scroll_offset + max_visible:
            self.scroll_offset = self.selected_index - max_visible + 1
        elif self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        self.scroll_offset = max(0, min(self.scroll_offset, num_songs - max_visible))


    # --- Song Actions (Initiation, Confirmation, Cancellation) ---

    # Load
    def _initiate_load_selected_song(self):
        if self.selected_index is None or not self.song_list:
            self.set_feedback("No song selected to load.", is_error=True)
            return
        try:
            basename_to_load = self.song_list[self.selected_index]
            current_song_name = self.song_service.get_current_song_name() # <<< Use SongService

            if self.song_service.is_current_song_dirty(): # <<< Use SongService
                 self.prompts.activate(PromptType.UNSAVED_LOAD, data=basename_to_load)
                 self.set_feedback(f"'{current_song_name}' has unsaved changes!", is_error=True)
            else:
                self._perform_load(basename_to_load) # Load directly via SongService

        except IndexError:
            # This error should be less likely now with the check above, but keep as fallback
            self.set_feedback("Error: Invalid selection index.", is_error=True)
            # Attempt to reset selection safely
            self._refresh_song_list()
        except AttributeError: # Handle if screen_manager or screens list is somehow None
             self.set_feedback("Error accessing screens.", is_error=True)

    def _perform_load(self, basename_to_load: str):
        """Internal: Tells SongService to load the song."""
        self.set_feedback(f"Loading '{basename_to_load}'...")
        pygame.display.flip() # Show feedback

        success, message = self.song_service.load_song_by_name(basename_to_load) # <<< Use SongService

        if success:
            self.set_feedback(message) # Use message from service
            # --- Find Edit Screen by Type (Robust) ---
            edit_screen_instance = None
            try:
                for screen in self.app.screen_manager.screens:
                    if isinstance(screen, SongEditScreen):
                        edit_screen_instance = screen
                        break

                if edit_screen_instance:
                    # <<< REMOVED: Print statement about not switching >>>
                    # print(f"Song '{basename_to_load}' loaded. Edit screen found but not switching.")
                    # Keep the actual switch commented out or remove entirely
                    # self.app.set_active_screen(edit_screen_instance) # Request screen change
                    pass # Successfully loaded, no switch needed.
                else:
                    # This feedback replaces the old error message
                    self.set_feedback(f"{message}, but edit screen instance not found.", is_error=True)
            except AttributeError:
                 # This handles if screen_manager or screens list is missing
                 self.set_feedback(f"{message}, but error accessing screen manager.", is_error=True)
            # --- End Find Edit Screen ---
        else:
            self.set_feedback(message, is_error=True) # Use error message from service

    def _save_current_and_load_selected(self, basename_to_load: str): # <<< ACCEPT argument
        """Handles 'Save' action: save via SongService, then load."""
        # basename_to_load = self.prompts.prompt_data # <<< REMOVED - Use argument

        if not basename_to_load:
            self.set_feedback("Error: State invalid for save/load.", is_error=True)
            return

        self.set_feedback(f"Saving current song...") # Name is handled by service
        pygame.display.flip()

        save_success, save_message = self.song_service.save_current_song() # <<< Use SongService

        if save_success:
            self.set_feedback(f"Saved. Now loading '{basename_to_load}'...")
            pygame.display.flip()
            self._perform_load(basename_to_load)
        else:
            self.set_feedback(f"Save failed: {save_message} Load cancelled.", is_error=True)

    def _discard_changes_and_load_selected(self, basename_to_load: str): # <<< ACCEPT argument
        """Handles 'Discard' action: discard via SongService, then load."""
        # basename_to_load = self.prompts.prompt_data # <<< REMOVED - Use argument

        if not basename_to_load:
            self.set_feedback("Error: No target song to load.", is_error=True)
            return

        self.song_service.discard_changes_current_song() # <<< Use SongService
        self.set_feedback(f"Discarded changes. Loading '{basename_to_load}'...")
        pygame.display.flip()
        self._perform_load(basename_to_load)

    def _cancel_load_due_to_unsaved(self):
        """Handles 'Cancel' action from the unsaved prompt."""
        self.set_feedback("Load cancelled.")

    # Create
    def _initiate_create_new_song(self):
        if self.song_service.is_current_song_dirty(): # <<< Use SongService
             self.prompts.activate(PromptType.UNSAVED_CREATE)
             self.set_feedback("Current song has unsaved changes!", is_error=True)
        else:
            self._proceed_to_create_name_input()

    def _proceed_to_create_name_input(self):
        """Activates the text input widget for the new song name."""
        self.is_creating = True
        self.is_renaming = False
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_name = f"NewSong-{timestamp}"
        i = 1
        final_default_name = default_name
        # Check against list from service
        existing_songs = self.song_service.list_song_names() # <<< Use SongService
        while final_default_name in existing_songs:
            final_default_name = f"{default_name}-{i}"
            i += 1
        self.text_input_widget.start(initial_text=final_default_name, prompt="Create New Song")
        self.set_feedback("Enter name for the new song.")

    def _confirm_song_create(self):
        """Creates the new song via SongService after name confirmation."""
        new_name = self.text_input_widget.get_text()
        if new_name is None:
             self.set_feedback("Error getting name.", is_error=True)
             self._reset_create_rename_state()
             return
        new_name = new_name.strip()
        if not new_name:
            self.set_feedback("Song name cannot be empty.", is_error=True)
            return # Keep widget active
        if new_name in self.song_service.list_song_names(): # <<< Use SongService
            self.set_feedback(f"Song '{new_name}' already exists.", is_error=True)
            return # Keep widget active

        print(f"Creating new song via SongService: '{new_name}'")
        success, message = self.song_service.create_new_song(new_name) # <<< Use SongService

        if success:
            self.set_feedback(message)
            self._refresh_song_list() # Update list display
            # Navigate to Edit Screen
            try:
                 edit_screen = self.app.screen_manager.screens[2] # Assuming Edit is 3rd screen
                 if edit_screen:
                     self.app.set_active_screen(edit_screen) # Request screen change
                 else:
                     print("Warning: Edit screen not found after create.")
            except (AttributeError, IndexError):
                 print("Warning: Error finding edit screen after create.")
        else:
            self.set_feedback(message, is_error=True)

        self._reset_create_rename_state() # Reset state after attempt

    def _cancel_song_create(self):
        """Cancels the song creation process."""
        self.set_feedback("Create cancelled.")
        self._reset_create_rename_state()

    def _save_current_and_proceed_to_create(self):
        """Handles 'Save' action: save via SongService, then proceed."""
        self.set_feedback(f"Saving current song...")
        pygame.display.flip()
        save_success, save_message = self.song_service.save_current_song() # <<< Use SongService
        if save_success:
            self.set_feedback("Saved. Proceeding to create...")
            self._proceed_to_create_name_input()
        else:
            self.set_feedback(f"Save failed: {save_message} Create cancelled.", is_error=True)

    def _discard_changes_and_proceed_to_create(self):
        """Handles 'Discard' action: discard via SongService, then proceed."""
        self.song_service.discard_changes_current_song() # <<< Use SongService
        self.set_feedback("Discarded changes. Proceeding to create...")
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
        """Confirms the song rename action via SongService."""
        if self.selected_index is None:
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
            return # Keep widget active
        if new_name == old_name:
            self.set_feedback("Name unchanged.")
            self._reset_create_rename_state()
            return
        if new_name in self.song_service.list_song_names(): # <<< Use SongService
             self.set_feedback(f"Name '{new_name}' already exists.", is_error=True)
             return # Keep widget active

        print(f"Renaming '{old_name}' to '{new_name}' via SongService")
        success, message = self.song_service.rename_song_file(old_name, new_name) # <<< Use SongService

        if success:
            self.set_feedback(message)
            self._refresh_song_list() # Refresh list display
        else:
            self.set_feedback(message, is_error=True)
            # Keep widget active on failure? Let's reset for now.
            # self._reset_create_rename_state()

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
            self.prompts.activate(PromptType.DELETE_SONG, data=song_name)
            self.set_feedback(f"Delete '{song_name}'?", is_error=True, duration=10.0)
        except IndexError:
            self.set_feedback("Selection error.", is_error=True)

    def _perform_delete(self, song_to_delete: Optional[str]): # <<< ACCEPT argument
        """Performs the actual deletion via SongService after confirmation."""
        # song_to_delete = self.prompts.prompt_data # <<< REMOVED - Use argument
        if not isinstance(song_to_delete, str):
             self.set_feedback("Error: Invalid state for delete.", is_error=True)
             return

        print(f"Deleting song via SongService: '{song_to_delete}'")
        success, message = self.song_service.delete_song_file(song_to_delete) # <<< Use SongService

        if success:
            self.set_feedback(message)
            self._refresh_song_list() # Update list display
        else:
            self.set_feedback(message, is_error=True)


    # --- NEW: Duplicate Song Logic ---
    def _initiate_duplicate_selected_song(self):
        """Handles the logic to duplicate the selected song."""
        if self.selected_index is None or not self.song_list:
            self.set_feedback("No song selected to duplicate", is_error=True)
            return

        try:
            original_name = self.song_list[self.selected_index]
        except IndexError:
            self.set_feedback("Selection error.", is_error=True)
            return

        # Find a unique name for the duplicate
        base_duplicate_name = f"{original_name}" # Start with original name
        new_name = base_duplicate_name
        counter = 1
        existing_songs = self.song_service.list_song_names()
        while new_name in existing_songs:
            new_name = f"{base_duplicate_name} {counter}"
            counter += 1
            if counter > 99: # Safety break
                 self.set_feedback(f"Could not find unique name for '{original_name}'.", is_error=True)
                 return

        print(f"Initiating duplication: '{original_name}' -> '{new_name}'")
        self.set_feedback(f"Duplicating '{original_name}'...")
        pygame.display.flip() # Show feedback immediately

        success, message = self.song_service.duplicate_song(original_name, new_name)

        if success:
            self.set_feedback(message)
            # Find the index of the new song to select it
            old_selected_index = self.selected_index
            self._refresh_song_list()
            try:
                self.selected_index = self.song_list.index(new_name)
                self._adjust_scroll()
            except ValueError:
                print(f"Warning: Could not find duplicated song '{new_name}' in list after refresh.")
                self.selected_index = old_selected_index # Fallback
        else:
            self.set_feedback(message, is_error=True)


    # --- Drawing Methods ---
    # <<< MODIFIED: Add **kwargs to accept unused arguments >>>
    def draw(self, screen_surface: pygame.Surface,
             midi_status: Optional[str] = None,
             song_status: Optional[str] = None,
             duration_status: Optional[str] = None,
             **kwargs): # <<< ADDED **kwargs
             # The original removed arguments (osc_status, etc.) will be caught by kwargs
    # <<< END MODIFIED >>>
        """Draws the screen content, prompts, or the text input widget."""
        if self.text_input_widget.is_active:
            self.text_input_widget.draw(screen_surface)
        elif self.prompts.is_active():
            self.prompts.draw(screen_surface)
        else:
            # Pass all arguments (including kwargs) down, although _draw_normal_content won't use the extras
            self._draw_normal_content(screen_surface, midi_status, song_status, duration_status, **kwargs) # <<< Pass **kwargs

    # <<< MODIFIED: Add **kwargs to accept unused arguments passed from draw() >>>
    def _draw_normal_content(self, screen_surface: pygame.Surface,
                             midi_status: Optional[str] = None,
                             song_status: Optional[str] = None,
                             duration_status: Optional[str] = None,
                             **kwargs): # <<< ADDED **kwargs
                             # The original removed arguments (osc_status, etc.) will be caught by kwargs
    # <<< END MODIFIED >>>
        """Draws the main list view and status lines."""
        screen_surface.fill(BLACK)

        # Draw Title
        title_text = "Song Manager"
        title_surf = self.font_large.render(title_text, True, WHITE)
        self.title_rect = title_surf.get_rect(midtop=(screen_surface.get_width() // 2, TOP_MARGIN))
        screen_surface.blit(title_surf, self.title_rect)

        # --- Draw Song Status (Top Right) ---
        loaded_text = song_status or "Song: ?" # Use song_status passed from App
        loaded_surf = self.font_small.render(loaded_text, True, GREY)
        # Position top right, below title might be too low, use original TOP_MARGIN + 5
        loaded_rect = loaded_surf.get_rect(topright=(screen_surface.get_width() - LEFT_MARGIN, TOP_MARGIN + 5))
        screen_surface.blit(loaded_surf, loaded_rect)
        # --- End Song Status ---

        # --- Draw Duration Status (Below Song Status) ---
        duration_text = duration_status or "Duration: ??" # Use duration_status passed from App
        duration_surf = self.font_small.render(duration_text, True, GREY)
        # Position below the song status, aligned to the right
        duration_rect = duration_surf.get_rect(topright=(screen_surface.get_width() - LEFT_MARGIN, loaded_rect.bottom + 2))
        screen_surface.blit(duration_surf, duration_rect)
        # --- End Duration Drawing ---

        # --- REMOVED Status Bar ---
        # The complex status bar drawing logic previously here is removed.
        # --- End REMOVED Status Bar ---


        # Draw Song List Area
        list_area_top = max(self.title_rect.bottom, duration_rect.bottom) + LIST_TOP_PADDING # Ensure list starts below title and duration
        # list_area_bottom = status_rect.top - 10 # <<< CHANGE: Use FEEDBACK_AREA_HEIGHT
        list_area_bottom = screen_surface.get_height() - FEEDBACK_AREA_HEIGHT # Use constant feedback area height
        list_area_rect = pygame.Rect(LEFT_MARGIN, list_area_top,
                                      screen_surface.get_width() - 2 * LEFT_MARGIN,
                                      list_area_bottom - list_area_top)

        if not self.song_list:
            no_songs_text = "No songs found."
            no_songs_surf = self.font.render(no_songs_text, True, GREY)
            no_songs_rect = no_songs_surf.get_rect(center=list_area_rect.center)
            screen_surface.blit(no_songs_surf, no_songs_rect)
        else:
            self._draw_song_list_items(screen_surface, list_area_rect)

        # Draw Feedback Area (always drawn, even if empty)
        self._draw_feedback(screen_surface)


    def _draw_song_list_items(self, screen, area_rect):
         """Draws the scrollable song list items."""
         max_visible = self._get_max_visible_items()
         num_songs = len(self.song_list)
         start_index = self.scroll_offset
         end_index = min(start_index + max_visible, num_songs)
         current_song_name = self.song_service.get_current_song_name() # <<< Use SongService

         if self.scroll_offset > 0:
             self._draw_scroll_arrow(screen, area_rect, 'up')
         if end_index < num_songs:
             self._draw_scroll_arrow(screen, area_rect, 'down')

         text_y = area_rect.top # Start drawing from the top of the area
         for i in range(start_index, end_index):
             song_name = self.song_list[i]
             is_selected = (i == self.selected_index)
             # Use BLACK for selected text, else WHITE.
             text_color = BLACK if is_selected else WHITE
             is_loaded = current_song_name and current_song_name == song_name
             is_dirty = is_loaded and self.song_service.is_current_song_dirty() # Check dirty flag only if loaded

             # Draw selection background only if selected.
             if is_selected:
                 bg_rect = pygame.Rect(area_rect.left, text_y, area_rect.width, LINE_HEIGHT)
                 pygame.draw.rect(screen, GREY, bg_rect) # Use GREY

             # Construct display text
             # prefix = "▶" if is_selected else "  "
             prefix = "  " # No prefix for now
             dirty_indicator = "*" if is_dirty else "" # Second asterisk if dirty
             item_text = f"{prefix}{song_name}{dirty_indicator}"

             item_surf = self.font.render(item_text, True, text_color)
             # Adjust vertical position slightly for better centering within line height
             item_rect = item_surf.get_rect(topleft=(area_rect.left + 5, text_y + (LINE_HEIGHT - self.font.get_height()) // 2))
             screen.blit(item_surf, item_rect)

             # Draw blue outline if the song is loaded (drawn over selection bg if needed)
             if is_loaded:
                 outline_rect = pygame.Rect(area_rect.left, text_y, area_rect.width, LINE_HEIGHT)
                 pygame.draw.rect(screen, BLUE, outline_rect, 2) # Thickness 2

             text_y += LINE_HEIGHT


    def _draw_feedback(self, surface):
        """Draws the feedback message at the bottom, within the feedback area."""
        if self.feedback_message:
            message, timestamp, color = self.feedback_message
            feedback_surf = self.font_small.render(message, True, color)

            # Calculate position within the dedicated feedback area at the bottom
            # status_bar_height = self.font_small.get_height() + 10 # Approximate height of status bar area <-- REMOVE
            # feedback_rect = feedback_surf.get_rect(centerx=surface.get_width() // 2, bottom=surface.get_height() - status_bar_height - 5) # 5px padding <-- REMOVE

            # Center within the bottom FEEDBACK_AREA_HEIGHT
            feedback_rect = feedback_surf.get_rect(centerx=surface.get_width() // 2,
                                                   bottom=surface.get_height() - (FEEDBACK_AREA_HEIGHT - feedback_surf.get_height()) // 2 - 5) # Center vertically in lower area, slight offset up

            # Draw a black background covering the feedback area
            bg_rect = pygame.Rect(0, surface.get_height() - FEEDBACK_AREA_HEIGHT, surface.get_width(), FEEDBACK_AREA_HEIGHT)
            pygame.draw.rect(surface, BLACK, bg_rect)

            surface.blit(feedback_surf, feedback_rect)


    def _draw_scroll_arrow(self, screen, area_rect, direction):
        """Draws an up or down scroll arrow to the right of the list."""
        arrow_char = "^" if direction == 'up' else "v"
        arrow_surf = self.font_small.render(arrow_char, True, GREY) # Use GREY for arrows
        arrow_x = area_rect.right - 10 # Position near the right edge

        if direction == 'up':
             arrow_rect = arrow_surf.get_rect(centerx=arrow_x, top=area_rect.top)
        else: # down
             arrow_rect = arrow_surf.get_rect(centerx=arrow_x, bottom=area_rect.bottom)
        screen.blit(arrow_surf, arrow_rect)

    # --- List Size Calculation ---
    def _get_max_visible_items(self) -> int:
        """Calculate how many list items fit on the screen."""
        list_area_top = max(self.title_rect.bottom, (self.title_rect.bottom + 5 + self.font_small.get_height())) + LIST_TOP_PADDING # Account for title and duration
        status_bar_height = self.font_small.get_height() + 10 # Approximate status bar height
        list_area_bottom = self.app.screen.get_height() - status_bar_height - 10 # Space above status bar
        available_height = list_area_bottom - list_area_top
        if available_height <= 0 or LINE_HEIGHT <= 0: return 0
        # Floor division to get whole items
        return max(1, available_height // LINE_HEIGHT)