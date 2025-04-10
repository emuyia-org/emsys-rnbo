# -*- coding: utf-8 -*-
"""
Screen for managing Song files (Loading, Creating, Renaming).
"""
import pygame
import time
from typing import List, Optional, Tuple
import datetime # Needed for default new song name

# Core components
from emsys.ui.base_screen import BaseScreen
from emsys.core.song import Song, Segment

# Utilities and Config
from emsys.utils import file_io
from emsys.config import settings, mappings

# --- Import the TextInputWidget ---
from .widgets import TextInputWidget, TextInputStatus
# ------------------------------------

# Define colors (reuse or import from settings)
WHITE = settings.WHITE
BLACK = settings.BLACK
GREEN = settings.GREEN
RED = settings.RED
BLUE = settings.BLUE
HIGHLIGHT_COLOR = GREEN # Color for selected item
FEEDBACK_COLOR = BLUE   # Color for feedback messages
ERROR_COLOR = RED       # Color for error messages

# Define layout constants
LEFT_MARGIN = 15
TOP_MARGIN = 15
LINE_HEIGHT = 30 # Slightly larger line height for easier reading
LIST_TOP_PADDING = 10
LIST_ITEM_INDENT = 25

class FileManageScreen(BaseScreen):
    """Screen for listing, loading, creating, and renaming song files."""

    def __init__(self, app_ref):
        """Initialize the file management screen."""
        super().__init__(app_ref)
        # Define additional fonts needed
        self.font_large = pygame.font.Font(None, 36)  # Larger font for titles
        self.font_small = pygame.font.Font(None, 18)  # Smaller font for indicators/details

        self.title_text = "Song File Manager"
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

    def init(self):
        """Called when the screen becomes active. Load the song list."""
        super().init()
        print(f"{self.__class__.__name__} is now active.")
        self._refresh_song_list()
        self.clear_feedback()
        # Update title (already done in __init__)
        # self.title_text = "Song File Manager"
        # self.title_surf = self.font_large.render(self.title_text, True, WHITE)
        # self.title_rect = self.title_surf.get_rect(midtop=(self.app.screen.get_width() // 2, TOP_MARGIN))

        # --- Reset text input widget state on init ---
        self.text_input_widget.cancel()
        # ---------------------------------------------

    def cleanup(self):
        """Called when the screen becomes inactive."""
        super().cleanup()
        print(f"{self.__class__.__name__} is being deactivated.")
        # --- Ensure text input widget is cleared on exit ---
        self.text_input_widget.cancel()
        # --------------------------------------------------
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
        if msg.type != 'control_change' or msg.value != 127: # Process only CC on messages
            return

        cc = msg.control
        print(f"FileManageScreen received CC: {cc} | TextInput Active: {self.text_input_widget.is_active}")

        # --- Handle Text Input Mode FIRST ---
        if self.text_input_widget.is_active:
            status = self.text_input_widget.handle_input(cc)
            if status == TextInputStatus.CONFIRMED:
                self._confirm_file_rename() # Call the confirmation logic
            elif status == TextInputStatus.CANCELLED:
                self._cancel_file_rename() # Call the cancellation logic
            # If ACTIVE or ERROR, the widget handles drawing, we just wait
            return # Don't process other actions while text input is active
        # ----------------------------------

        # --- Normal File Management Mode ---

        # Handle CREATE_SONG_CC
        if cc == mappings.CREATE_SONG_CC:
            self._create_new_song()
            return

        # Handle RENAME_SONG_CC
        elif cc == mappings.RENAME_SONG_CC:
            self._start_file_rename()
            return

        # --- List Navigation/Selection (only if list exists) ---
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
            self._load_selected_song()

    # --- Methods for Renaming using TextInputWidget ---
    def _start_file_rename(self):
        """Initiates renaming for the selected file using the widget."""
        if self.selected_index is None or not self.song_list:
            self.set_feedback("No song selected to rename", is_error=True)
            return

        try:
            current_name = self.song_list[self.selected_index]
            self.text_input_widget.start(current_name, prompt="Rename File")
            self.clear_feedback()
            print(f"Starting file rename for: {current_name}")
            self.set_feedback("Renaming file...", duration=1.0)
        except IndexError:
            self.set_feedback("Selection error, cannot rename.", is_error=True)
            self.selected_index = 0 if self.song_list else None # Reset index

    def _confirm_file_rename(self):
        """Confirms the file rename using file_io."""
        if not self.text_input_widget.is_active or self.selected_index is None:
            self.text_input_widget.cancel()
            return

        new_name = self.text_input_widget.get_text()
        if new_name is None:
             self.set_feedback("Error getting new name from widget.", is_error=True)
             self.text_input_widget.cancel()
             return

        new_name = new_name.strip()

        try:
            old_name = self.song_list[self.selected_index]
        except IndexError:
            self.set_feedback("Selection error during rename confirmation.", is_error=True)
            self.text_input_widget.cancel()
            self._refresh_song_list() # Refresh list state
            return

        if not new_name:
            self.set_feedback("File name cannot be empty. Rename cancelled.", is_error=True)
            self.text_input_widget.cancel()
            return

        if new_name == old_name:
            self.set_feedback("Name unchanged. Exiting rename.")
            self.text_input_widget.cancel()
            return

        print(f"Attempting to rename file from '{old_name}' to '{new_name}'")

        # --- File Renaming Logic ---
        if not hasattr(file_io, 'rename_song'):
             self.set_feedback("Error: File renaming function not implemented!", is_error=True)
             self.text_input_widget.cancel()
             return

        # Use the rename_song function from file_io
        if file_io.rename_song(old_name, new_name):
            self.set_feedback(f"File renamed to '{new_name}'")

            # --- Critical: Check if the renamed song was the loaded current_song ---
            renamed_current = False
            if self.app.current_song and self.app.current_song.name == old_name:
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

            self.text_input_widget.cancel() # Exit rename mode

        else:
            # file_io.rename_song failed
            self.set_feedback(f"Failed to rename file (see console)", is_error=True)
            # Keep widget active? No, cancel to avoid confusion. User can retry.
            self.text_input_widget.cancel()


    def _cancel_file_rename(self):
        """Cancels the file renaming process."""
        self.set_feedback("Rename cancelled.")
        print("Cancelled file rename mode.")
        self.text_input_widget.cancel()

    # --- End of Renaming Methods ---


    def _create_new_song(self):
        """Creates a new song and navigates to the song edit screen."""
        if self.text_input_widget.is_active: return # Prevent action during text input
        try:
            # Create a default song name based on timestamp to ensure uniqueness
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            new_song_name = f"New_Song_{timestamp}"

            # Create a new song with an initial empty segment
            new_song = Song(name=new_song_name)
            initial_segment = Segment()  # Create with default values
            new_song.add_segment(initial_segment)

            # Set as current song in the app
            self.app.current_song = new_song

            # Save the song to disk
            if file_io.save_song(new_song):
                self.set_feedback(f"Created new song: {new_song_name}", duration=1.5)
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

                # Navigate to the next screen (song edit) after a short delay
                NAVIGATE_EVENT = pygame.USEREVENT + 1
                pygame.time.set_timer(NAVIGATE_EVENT, 1500, loops=1)  # 1500 ms delay
            else:
                self.set_feedback(f"Failed to save new song.", is_error=True)
                self.app.current_song = None

        except Exception as e:
            self.set_feedback(f"Error creating song: {e}", is_error=True)
            print(f"Error in _create_new_song: {e}")
            self.app.current_song = None

    def _load_selected_song(self):
        """Attempts to load the selected song and update the app state."""
        if self.text_input_widget.is_active: return # Prevent action during text input
        if self.selected_index is None or not self.song_list:
            self.set_feedback("No song selected.", is_error=True)
            return

        try:
            selected_basename = self.song_list[self.selected_index]
            self.set_feedback(f"Loading '{selected_basename}'...")
            pygame.display.flip() # Show feedback immediately

            loaded_song = file_io.load_song(selected_basename)

            if loaded_song:
                # CRITICAL: Update the main app's current song
                self.app.current_song = loaded_song
                self.set_feedback(f"Loaded: {selected_basename}", duration=1.5)
                # Navigate to the next screen (likely SongEditScreen) after a short delay
                NAVIGATE_EVENT = pygame.USEREVENT + 1
                pygame.time.set_timer(NAVIGATE_EVENT, 1500, loops=1) # 1500 ms delay

            else:
                # Loading failed (file_io.load_song returns None and prints error)
                self.app.current_song = None # Ensure current song is cleared
                self.set_feedback(f"Failed to load '{selected_basename}'", is_error=True)

        except IndexError:
            self.set_feedback("Selection index error.", is_error=True)
            self.selected_index = 0 if self.song_list else None # Reset index
        except Exception as e:
            self.set_feedback(f"Error during load: {e}", is_error=True)
            self.app.current_song = None # Ensure current song is cleared

    # Override handle_event to catch our custom navigation event
    def handle_event(self, event):
        super().handle_event(event)
        NAVIGATE_EVENT = pygame.USEREVENT + 1
        if event.type == NAVIGATE_EVENT:
            # Check if navigation was triggered by load or create
            # We might need a flag if different destinations are possible
            print("Navigate event triggered after load/create.")
            self.app.next_screen() # Go to the next screen in the list

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
        # --- Draw Normal File List Interface ---
        else:
            # Draw the title
            screen_surface.blit(self.title_surf, self.title_rect)

            # --- Draw Song List ---
            list_area_top = self.title_rect.bottom + LIST_TOP_PADDING
            y_offset = list_area_top

            # Add hint for renaming
            rename_cc = getattr(mappings, 'RENAME_SONG_CC', None)
            rename_hint = f"(Rename: CC {rename_cc})" if rename_cc else ""


            if not self.song_list:
                create_cc = getattr(mappings, 'CREATE_SONG_CC', '?')
                no_songs_text = f"No songs found. Press CC {create_cc} to create."
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
                    display_text = f"{i + 1}. {song_name}"
                    is_selected = (i == self.selected_index)
                    color = HIGHLIGHT_COLOR if is_selected else WHITE

                    item_surf = self.font.render(display_text, True, color)
                    item_rect = item_surf.get_rect(topleft=(LEFT_MARGIN + LIST_ITEM_INDENT, y_offset))

                    if is_selected:
                        # Draw highlight background
                        highlight_rect = pygame.Rect(LEFT_MARGIN, y_offset - 2, screen_surface.get_width() - (2 * LEFT_MARGIN), LINE_HEIGHT)
                        pygame.draw.rect(screen_surface, (40, 80, 40), highlight_rect) # Dark green background
                        # Add rename hint next to selected item
                        if rename_hint:
                            hint_surf = self.font_small.render(rename_hint, True, WHITE)
                            hint_rect = hint_surf.get_rect(midleft=(item_rect.right + 10, item_rect.centery))
                            # Prevent hint going off screen
                            if hint_rect.right > screen_surface.get_width() - LEFT_MARGIN:
                                hint_rect.right = screen_surface.get_width() - LEFT_MARGIN
                            screen_surface.blit(hint_surf, hint_rect)


                    screen_surface.blit(item_surf, item_rect)
                    y_offset += LINE_HEIGHT

                # Draw scroll down indicator if needed
                if end_index < len(self.song_list):
                     scroll_down_surf = self.font_small.render("v", True, WHITE)
                     scroll_down_rect = scroll_down_surf.get_rect(centerx=screen_surface.get_width() // 2, top=y_offset + 5)
                     screen_surface.blit(scroll_down_surf, scroll_down_rect)


        # --- Draw Feedback Message (Common) ---
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

