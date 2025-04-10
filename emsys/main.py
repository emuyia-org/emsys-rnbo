# -*- coding: utf-8 -*-
"""
Main entry point for the Emsys Python Application. V1

Initializes Pygame, basic MIDI, UI placeholder, and runs the main event loop.
Handles exit via MIDI CC 47.
"""

import sys
import os
import sdnotify
import pygame
import mido

# Add the project root directory to the path to enable absolute imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now we can use absolute imports from the emsys package
from emsys.config import settings as settings_module
print(f"Settings module contents: {dir(settings_module)}")

SCREEN_WIDTH = settings_module.SCREEN_WIDTH
SCREEN_HEIGHT = settings_module.SCREEN_HEIGHT
FPS = settings_module.FPS
BLACK = settings_module.BLACK
WHITE = settings_module.WHITE
RED = settings_module.RED
MIDI_DEVICE_NAME = settings_module.MIDI_DEVICE_NAME

from emsys.config.mappings import EXIT_CC, NEXT_SCREEN_CC, PREV_SCREEN_CC
from emsys.utils.midi import find_midi_port

# UI Imports
from emsys.ui.base_screen import BaseScreen
from emsys.ui.main_menu_screen import MainMenuScreen
from emsys.ui.placeholder_screen import PlaceholderScreen

# Additional screen imports
FileManageScreen = None
SongEditScreen = None

try:
    import emsys.ui.file_manage_screen
    if hasattr(emsys.ui.file_manage_screen, 'FileManageScreen'):
        from emsys.ui.file_manage_screen import FileManageScreen
    else:
        print(f"Error: emsys.ui.file_manage_screen module exists but doesn't contain FileManageScreen class")
except ImportError as e:
    print(f"Error importing file_manage_screen: {e}")
    print("Please ensure 'ui/file_manage_screen.py' exists")

try:
    import emsys.ui.song_edit_screen
    if hasattr(emsys.ui.song_edit_screen, 'SongEditScreen'):
        from emsys.ui.song_edit_screen import SongEditScreen
    else:
        print(f"Error: emsys.ui.song_edit_screen module exists but doesn't contain SongEditScreen class")
except ImportError as e:
    print(f"Error importing song_edit_screen: {e}")
    print("Please ensure 'ui/song_edit_screen.py' exists")

print(f"Available screens: FileManageScreen={'Available' if FileManageScreen else 'Not Available'}, "
      f"SongEditScreen={'Available' if SongEditScreen else 'Not Available'}")

# Main Application Class
class App:
    """Encapsulates the main application logic and state."""

    def __init__(self):
        """Initialize Pygame, services, and application state."""
        print("Initializing App...")
        self.notifier = sdnotify.SystemdNotifier()
        self.notify_status("Initializing Pygame...")

        pygame.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Emsys Controller')
        self.clock = pygame.time.Clock()
        pygame.mouse.set_visible(False)
        self.running = False

        self.midi_port = None
        self.midi_port_name = None
        self.active_screen = None
        self.last_midi_message_str = None

        self._initialize_midi()
        self.initialize_screens()

    def initialize_screens(self):
        """Initialize all application screens."""
        print("Initializing Screens...")
        self.placeholder_screen = PlaceholderScreen(self)

        if FileManageScreen:
            self.file_manage_screen = FileManageScreen(self)
        else:
            self.file_manage_screen = None

        if SongEditScreen:
            self.song_edit_screen = SongEditScreen(self)
        else:
            self.song_edit_screen = None

        # Create a list of screens for navigation in the desired order
        self.screens = [
            screen for screen in [
                self.placeholder_screen,
                self.file_manage_screen,
                self.song_edit_screen,
            ] if screen is not None
        ]

        if self.screens:
             self.set_active_screen(self.screens[0])
        else:
             print("WARNING: No screens defined or successfully imported!")
             self.active_screen = None

        print("Screens initialized.")

    def _initialize_midi(self):
        """Finds and opens the MIDI port."""
        self.notify_status("Initializing MIDI...")
        found_port_name = find_midi_port(MIDI_DEVICE_NAME)
        if found_port_name:
            self.midi_port_name = found_port_name
            print(f"Attempting to open MIDI port: '{self.midi_port_name}'")
            try:
                self.midi_port = mido.open_input(self.midi_port_name)
                print(f"Successfully opened MIDI port: {self.midi_port_name}")
                self.notify_status("MIDI Initialized. Notifying systemd READY=1")
                self.notifier.notify("READY=1")
            except Exception as e:
                error_info = f"Error opening MIDI port '{self.midi_port_name}': {e}"
                print(error_info)
                self.notify_status(f"FAIL: {error_info}")
                self.notifier.notify("READY=1")
                self.midi_port = None
        else:
            error_info = f"MIDI Device '{MIDI_DEVICE_NAME}' not found."
            print(error_info)
            self.notify_status(f"FAIL: {error_info}")
            self.notifier.notify("READY=1")

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
            # Event Handling (Pygame)
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    self.running = False
                if self.active_screen:
                    self.active_screen.handle_event(event)

            # MIDI Input Handling
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
                    print("Will attempt to reconnect MIDI in 5 seconds...")
                    self.notify_status("MIDI disconnected. Will retry in 5s")

            # Update
            if self.active_screen:
                 self.active_screen.update()

            # Draw
            self.screen.fill(BLACK)
            if self.active_screen:
                self.active_screen.draw(self.screen)
            pygame.display.flip()

            # Frame Rate Control
            self.clock.tick(FPS)

        # Exit
        self.cleanup()

    def handle_midi_message(self, msg):
        """Process incoming MIDI messages."""
        print(f"MIDI Received: {msg}")
        self.last_midi_message_str = str(msg)

        if msg.type == 'control_change':
            if msg.control == EXIT_CC and msg.value == 127:
                print(f"Exit command received (CC #{EXIT_CC}). Shutting down.")
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


# Script Entry Point
def main():
    """Main function that can be imported and run from other scripts."""
    app = None
    try:
        app = App()
        if app.active_screen is None:
             print("App initialization failed to set an active screen. Exiting.")
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

if __name__ == '__main__':
    main()

