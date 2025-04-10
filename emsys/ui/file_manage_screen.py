# -*- coding: utf-8 -*-
"""
Screen for managing Song files (Loading).
"""
import pygame
import time
from typing import List, Optional, Tuple

# Core components
from emsys.ui.base_screen import BaseScreen  # Updated to absolute import
from emsys.core.song import Song, Segment # Updated to absolute import - added Segment

# Utilities and Config
from emsys.utils import file_io  # Updated to absolute import
from emsys.config import settings, mappings  # Updated to absolute import

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
    """Screen for listing and loading song files."""

    def __init__(self, app_ref):
        """Initialize the file management screen."""
        super().__init__(app_ref)
        # Define additional fonts needed
        self.font_large = pygame.font.Font(None, 36)  # Larger font for titles
        self.font_small = pygame.font.Font(None, 18)  # Smaller font for indicators/details
        
        self.title_text = "Load Song"
        self.title_surf = self.font_large.render(self.title_text, True, WHITE)
        self.title_rect = self.title_surf.get_rect(midtop=(self.app.screen.get_width() // 2, TOP_MARGIN))

        # State for the list and selection
        self.song_list: List[str] = []
        self.selected_index: Optional[int] = None
        self.scroll_offset: int = 0 # Index of the first visible item

        # Feedback message state
        self.feedback_message: Optional[Tuple[str, float, Tuple[int, int, int]]] = None # (message, timestamp, color)
        self.feedback_duration: float = 3.0 # seconds

    def init(self):
        """Called when the screen becomes active. Load the song list."""
        super().init()
        print(f"{self.__class__.__name__} is now active.")
        self._refresh_song_list()
        self.clear_feedback()
        # Update title to reflect the screen can create songs too
        self.title_text = "Song File Manager"
        self.title_surf = self.font_large.render(self.title_text, True, WHITE)
        self.title_rect = self.title_surf.get_rect(midtop=(self.app.screen.get_width() // 2, TOP_MARGIN))

    def cleanup(self):
        """Called when the screen becomes inactive."""
        super().cleanup()
        print(f"{self.__class__.__name__} is being deactivated.")
        self.clear_feedback()

    def _refresh_song_list(self):
        """Fetches the list of songs from file_io and resets selection."""
        self.song_list = file_io.list_songs()
        self.scroll_offset = 0
        if self.song_list:
            self.selected_index = 0
        else:
            self.selected_index = None
        print(f"Found songs: {self.song_list}")

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
        """Handle MIDI messages for list navigation and selection."""
        if msg.type != 'control_change' or msg.value != 127: # Process only CC on messages
            return

        cc = msg.control
        print(f"FileManageScreen received CC: {cc}")
        
        # Handle CREATE_SONG_CC regardless of song list state
        if cc == mappings.CREATE_SONG_CC:
            self._create_new_song()
            return

        if not self.song_list:
            # No songs, only allow exit/screen change and creation
            if cc in (mappings.UP_NAV_CC, mappings.DOWN_NAV_CC, mappings.YES_NAV_CC):
                self.set_feedback("No songs found to load.", is_error=True)
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
                if self.selected_index == 0 and self.scroll_offset > 0:
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
                if self.selected_index == num_songs - 1 and self.scroll_offset < num_songs - max_visible:
                     self.scroll_offset = max(0, num_songs - max_visible)
            else:
                 self.selected_index = num_songs - 1 # Select last item if none selected
            self.clear_feedback()

        elif cc == mappings.YES_NAV_CC:
            self._load_selected_song()

    def _create_new_song(self):
        """Creates a new song and navigates to the song edit screen."""
        try:
            # Create a default song name based on timestamp to ensure uniqueness
            import datetime
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
                # Using pygame events for delayed action is safer than time.sleep() in main loop
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
            print("Navigate event triggered after load.")
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
        """Draws the screen content."""
        # Draw the title
        screen_surface.blit(self.title_surf, self.title_rect)

        # --- Draw Song List ---
        list_area_top = self.title_rect.bottom + LIST_TOP_PADDING
        y_offset = list_area_top

        if not self.song_list:
            no_songs_text = "No songs found. Press Button 23 to create a new song."
            no_songs_surf = self.font.render(no_songs_text, True, WHITE)
            no_songs_rect = no_songs_surf.get_rect(centerx=screen_surface.get_width() // 2, top=y_offset + 20)
            screen_surface.blit(no_songs_surf, no_songs_rect)
        else:
            max_visible = self._get_max_visible_items()
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

                screen_surface.blit(item_surf, item_rect)
                y_offset += LINE_HEIGHT

            # Draw scroll down indicator if needed
            if end_index < len(self.song_list):
                 scroll_down_surf = self.font_small.render("v", True, WHITE)
                 scroll_down_rect = scroll_down_surf.get_rect(centerx=screen_surface.get_width() // 2, top=y_offset + 5)
                 screen_surface.blit(scroll_down_surf, scroll_down_rect)


        # --- Draw Feedback Message ---
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

