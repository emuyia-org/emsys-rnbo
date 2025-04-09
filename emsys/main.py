# -*- coding: utf-8 -*-
"""
Main entry point for the Emsys Python Application. V1

Initializes Pygame, basic MIDI, UI placeholder, and runs the main event loop.
Handles exit via MIDI CC 47.
"""

import pygame
import mido
import sys
import os
import sdnotify # For systemd readiness notification
import time # For potential sleep/timing

# --- Constants ---
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320
FPS = 30
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)

# --- Configuration ---
# Base name of the MIDI device to find
DEVICE_BASE_NAME = 'X-TOUCH MINI'
# MIDI CC number designated for exiting the application (Layer B)
EXIT_CC_NUMBER = 47
# MIDI CC numbers for screen navigation
NEXT_SCREEN_CC = 82
PREV_SCREEN_CC = 90

# --- UI Imports --- # MODIFIED: Grouped UI imports
from ui.base_screen import BaseScreen
from ui.main_menu_screen import MainMenuScreen # Keep for future use

# --- ADDED IMPORTS ---
# Ensure these files exist and contain the correct class definitions
FileManageScreen = None
SongEditScreen = None

try:
    # Import each module and check if it has the expected class
    import ui.file_manage_screen
    if hasattr(ui.file_manage_screen, 'FileManageScreen'):
        from ui.file_manage_screen import FileManageScreen
    else:
        print(f"Error: ui.file_manage_screen module exists but doesn't contain FileManageScreen class")
except ImportError as e:
    print(f"Error importing file_manage_screen: {e}")
    print("Please ensure 'ui/file_manage_screen.py' exists")

try:
    import ui.song_edit_screen
    if hasattr(ui.song_edit_screen, 'SongEditScreen'):
        from ui.song_edit_screen import SongEditScreen
    else:
        print(f"Error: ui.song_edit_screen module exists but doesn't contain SongEditScreen class")
except ImportError as e:
    print(f"Error importing song_edit_screen: {e}")
    print("Please ensure 'ui/song_edit_screen.py' exists")

print(f"Available screens: FileManageScreen={'Available' if FileManageScreen else 'Not Available'}, "
      f"SongEditScreen={'Available' if SongEditScreen else 'Not Available'}")
# --- END ADDED IMPORTS ---


# --- Minimal Placeholder Screen ---
class PlaceholderScreen(BaseScreen):
    """A very basic screen to display something, including last MIDI message."""
    def __init__(self, app_ref):
        super().__init__(app_ref)
        self.title_text = "emsys Running!"
        self.title_surf = self.font.render(self.title_text, True, WHITE)
        self.title_rect = self.title_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20)) # Move title up slightly

        # Pre-render placeholder for MIDI message area
        self.midi_placeholder_text = "Waiting for MIDI..."
        self.midi_placeholder_surf = self.font_small.render(self.midi_placeholder_text, True, WHITE)
        self.midi_placeholder_rect = self.midi_placeholder_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20)) # Position below title

    def draw(self, screen_surface):
        """Draws the screen content."""
        # Draw main title
        screen_surface.blit(self.title_surf, self.title_rect)

        # Get the last MIDI message string from the App instance
        last_midi_msg = self.app.last_midi_message_str # Read from App

        # Render and draw the last MIDI message or placeholder
        if last_midi_msg:
            # Render the actual last message
            midi_surf = self.font_small.render(last_midi_msg, True, WHITE)
            midi_rect = midi_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20)) # Same position as placeholder
            screen_surface.blit(midi_surf, midi_rect)
        else:
            # Draw the "Waiting for MIDI..." placeholder
            screen_surface.blit(self.midi_placeholder_surf, self.midi_placeholder_rect)


# --- MIDI Helper Function (from test.py, adapted) ---
def find_midi_port(base_name):
    """Searches for MIDI input port containing base_name."""
    print(f"Searching for MIDI input port containing: '{base_name}'")
    try:
        available_ports = mido.get_input_names()
        print("Available ports:", available_ports)
        for port_name in available_ports:
            if base_name in port_name:
                print(f"Found matching port: '{port_name}'")
                return port_name
    except Exception as e:
        print(f"Error getting MIDI port names: {e}")
    print(f"No MIDI input port found containing '{base_name}'.")
    return None

# --- Main Application Class ---
class App:
    """Encapsulates the main application logic and state."""

    def __init__(self):
        """Initialize Pygame, services, and application state."""
        print("Initializing App...")
        self.notifier = sdnotify.SystemdNotifier()
        self.notify_status("Initializing Pygame...")

        pygame.init()
        pygame.font.init() # Ensure font module is initialized
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Emsys Controller')
        self.clock = pygame.time.Clock()
        pygame.mouse.set_visible(False) # Hide mouse cursor
        self.running = False

        self.midi_port = None
        self.midi_port_name = None
        self.active_screen = None
        # self.main_font = pygame.font.SysFont(None, 36) # Using fonts from BaseScreen now

        # --- ADDED: Attribute to store last MIDI message ---
        self.last_midi_message_str = None
        # --- END ADDED ---

        # Initialize MIDI Directly (like test.py)
        self._initialize_midi()

        # Initialize UI - Create all screen instances
        self.initialize_screens()

    def initialize_screens(self):
        """Initialize all application screens."""
        print("Initializing Screens...")
        # Create the screen instances
        self.placeholder_screen = PlaceholderScreen(self)

        # --- MODIFIED: Check if classes were imported successfully ---
        if FileManageScreen:
            self.file_manage_screen = FileManageScreen(self)
        else:
            self.file_manage_screen = None # Ensure it's None if import failed

        if SongEditScreen:
            self.song_edit_screen = SongEditScreen(self)
        else:
            self.song_edit_screen = None # Ensure it's None if import failed
        # --- END MODIFIED ---

        # You can add other screens like MainMenuScreen here when ready
        # self.main_menu_screen = MainMenuScreen(self)

        # Create a list of screens for navigation in the desired order
        # Filter out None entries in case imports failed
        self.screens = [
            screen for screen in [
                self.placeholder_screen,
                self.file_manage_screen,
                self.song_edit_screen,
                # Add other screens here (e.g., self.main_menu_screen)
            ] if screen is not None
        ]

        # Set the initial active screen (using the first one in the list)
        if self.screens:
             self.set_active_screen(self.screens[0])
        else:
             print("WARNING: No screens defined or successfully imported!")
             # Create a minimal error screen or exit
             self.active_screen = None # Will cause exit in run()

        print("Screens initialized.")

    def _initialize_midi(self):
        """Finds and opens the MIDI port."""
        self.notify_status("Initializing MIDI...")
        found_port_name = find_midi_port(DEVICE_BASE_NAME)
        if found_port_name:
            self.midi_port_name = found_port_name
            print(f"Attempting to open MIDI port: '{self.midi_port_name}'")
            try:
                self.midi_port = mido.open_input(self.midi_port_name)
                print(f"Successfully opened MIDI port: {self.midi_port_name}")
                # --- Notify systemd AFTER MIDI port is successfully opened ---
                self.notify_status("MIDI Initialized. Notifying systemd READY=1")
                self.notifier.notify("READY=1")
                # --- End systemd notification ---
            except Exception as e:
                error_info = f"Error opening MIDI port '{self.midi_port_name}': {e}"
                print(error_info)
                self.notify_status(f"FAIL: {error_info}")
                self.notifier.notify("READY=1") # Notify ready even if MIDI fails for now
                self.midi_port = None
        else:
            error_info = f"MIDI Device '{DEVICE_BASE_NAME}' not found."
            print(error_info)
            self.notify_status(f"FAIL: {error_info}")
            self.notifier.notify("READY=1") # Notify ready even if MIDI fails for now

    def notify_status(self, status_message):
        """Helper function to print status and notify systemd."""
        max_len = 80
        truncated_message = status_message[:max_len] + '...' if len(status_message) > max_len else status_message
        print(f"Status: {truncated_message}")
        try:
            self.notifier.notify(f"STATUS={truncated_message}")
        except Exception as e:
            print(f"Could not notify systemd: {e}")

    def run(self):
        """Main application loop."""
        if not self.active_screen:
             print("ERROR: No active screen set during initialization. Exiting.")
             self.cleanup()
             return

        self.running = True
        self.notify_status(f"Running. Active Screen: {self.active_screen.__class__.__name__}")
        while self.running:
            # --- Event Handling (Pygame) ---
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    self.running = False
                if self.active_screen:
                    self.active_screen.handle_event(event)

            # --- MIDI Input Handling ---
            if self.midi_port:
                try:
                    for msg in self.midi_port.iter_pending():
                        self.handle_midi_message(msg)
                except OSError as e:
                    print(f"MIDI Read Error: {e}. Closing port.")
                    self.notify_status(f"MIDI Error: {e}")
                    if self.midi_port:
                        try: self.midi_port.close()
                        except Exception as midi_err: 
                            print(f"Error closing MIDI port: {midi_err}")
                    self.midi_port = None
                    # Try to re-open after a brief pause
                    print("Will attempt to reconnect MIDI in 5 seconds...")
                    self.notify_status("MIDI disconnected. Will retry in 5s")

            # --- Update ---
            if self.active_screen:
                 self.active_screen.update()

            # --- Draw ---
            self.screen.fill(BLACK)
            if self.active_screen:
                self.active_screen.draw(self.screen)
            pygame.display.flip()

            # --- Frame Rate Control ---
            self.clock.tick(FPS)

        # --- Exit ---
        self.cleanup()

    def handle_midi_message(self, msg):
        """Process incoming MIDI messages."""
        # --- DEBUGGING LINE (still useful) ---
        print(f"MIDI Received: {msg}")
        # --- END DEBUGGING LINE ---

        # --- ADDED: Store string representation of the message ---
        self.last_midi_message_str = str(msg)
        # --- END ADDED ---

        if msg.type == 'control_change':
            if msg.control == EXIT_CC_NUMBER and msg.value == 127:
                print(f"Exit command received (CC #{EXIT_CC_NUMBER}). Shutting down.")
                self.notify_status("Exit command received...")
                self.running = False
            elif msg.control == NEXT_SCREEN_CC and msg.value == 127:
                print(f"Next screen command received (CC #{NEXT_SCREEN_CC})")
                self.next_screen()
            elif msg.control == PREV_SCREEN_CC and msg.value == 127:
                print(f"Previous screen command received (CC #{PREV_SCREEN_CC})")
                self.previous_screen()
            else:
                if self.active_screen and hasattr(self.active_screen, 'handle_midi'):
                    self.active_screen.handle_midi(msg)

    def next_screen(self):
        """Switch to the next available screen."""
        if hasattr(self, 'screens') and self.screens:
            try:
                current_index = self.screens.index(self.active_screen)
                next_index = (current_index + 1) % len(self.screens)
                self.set_active_screen(self.screens[next_index])
            except (ValueError, AttributeError):
                 if self.screens: self.set_active_screen(self.screens[0])

    def previous_screen(self):
        """Switch to the previous available screen."""
        if hasattr(self, 'screens') and self.screens:
            try:
                current_index = self.screens.index(self.active_screen)
                prev_index = (current_index - 1) % len(self.screens)
                self.set_active_screen(self.screens[prev_index])
            except (ValueError, AttributeError):
                 if self.screens: self.set_active_screen(self.screens[0])

    def set_active_screen(self, screen):
        """Set the active screen, call cleanup/init if needed, and notify status."""
        if self.active_screen != screen and screen is not None:
            if self.active_screen and hasattr(self.active_screen, 'cleanup'):
                try: self.active_screen.cleanup()
                except Exception as e: print(f"Error during cleanup: {e}")

            self.active_screen = screen

            if hasattr(self.active_screen, 'init'):
                 try: self.active_screen.init()
                 except Exception as e: print(f"Error during init: {e}")

            print(f"Switched to screen: {screen.__class__.__name__}")
            self.notify_status(f"Screen: {self.active_screen.__class__.__name__}")
        elif screen is None:
            print("Error: Attempted to set active screen to None.")

    def cleanup(self):
        """Clean up resources before exiting."""
        current_status = "Cleaning up..."
        self.notify_status(current_status)
        print(current_status)

        if self.active_screen and hasattr(self.active_screen, 'cleanup'):
            print(f"Cleaning up final screen: {self.active_screen.__class__.__name__}")
            try: self.active_screen.cleanup()
            except Exception as e: print(f"Error during final screen cleanup: {e}")

        if self.midi_port:
            print(f"Closing MIDI port: {self.midi_port_name}")
            try: self.midi_port.close()
            except Exception as e: print(f"Error closing MIDI port: {e}")
        pygame.quit()
        print("Pygame quit.")
        current_status = "Exited."
        print(current_status)
        try:
            self.notifier.notify(f"STATUS={current_status}")
            self.notifier.notify("STOPPING=1")
        except Exception as e:
            print(f"Could not notify systemd on exit: {e}")


# --- Script Entry Point ---
if __name__ == '__main__':
    # Added basic error handling for screen imports at the top
    app = None
    try:
        app = App()
        # Check if app initialization failed to set an active screen
        if app.active_screen is None:
             print("App initialization failed to set an active screen. Exiting.")
             # Attempt minimal cleanup if app object exists
             if app: app.cleanup()
             sys.exit(1)

        app.run()
        sys.exit(0)
    except Exception as e:
        print(f"\n--- An unhandled error occurred in main ---")
        import traceback
        traceback.print_exc()
        try:
            n = sdnotify.SystemdNotifier()
            n.notify("STATUS=Crashed unexpectedly.")
            n.notify("STOPPING=1")
        except Exception as sd_err:
            print(f"(Could not notify systemd: {sd_err})")
        if app:
            try:
                if app.active_screen and hasattr(app.active_screen, 'cleanup'): app.active_screen.cleanup()
                if app.midi_port: app.midi_port.close()
            except: pass
        try: pygame.quit()
        except: pass
        sys.exit(1)

