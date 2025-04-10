# -*- coding: utf-8 -*-
"""
Main entry point for the Emsys Python Application. V1

Initializes Pygame, basic MIDI, UI placeholder, and runs the main event loop.
Handles exit via MIDI CC 47. Includes MIDI device auto-reconnection.
"""

import sys
import os
import time # Needed for timers
import traceback # Needed for detailed error logs
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

# Import settings constants
SCREEN_WIDTH = settings_module.SCREEN_WIDTH
SCREEN_HEIGHT = settings_module.SCREEN_HEIGHT
FPS = settings_module.FPS
BLACK = settings_module.BLACK
WHITE = settings_module.WHITE
RED = settings_module.RED
MIDI_DEVICE_NAME = settings_module.MIDI_DEVICE_NAME
# Import reconnection settings
RESCAN_INTERVAL_SECONDS = settings_module.RESCAN_INTERVAL_SECONDS
CONNECTION_CHECK_INTERVAL_SECONDS = settings_module.CONNECTION_CHECK_INTERVAL_SECONDS

from emsys.config.mappings import EXIT_CC, NEXT_SCREEN_CC, PREV_SCREEN_CC
from emsys.utils.midi import find_midi_port

# UI Imports
from emsys.ui.base_screen import BaseScreen
# from emsys.ui.main_menu_screen import MainMenuScreen # Assuming not used based on test.py
from emsys.ui.placeholder_screen import PlaceholderScreen

# Additional screen imports (keep existing logic)
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
try:
    import emsys.ui.song_edit_screen
    if hasattr(emsys.ui.song_edit_screen, 'SongEditScreen'):
        from emsys.ui.song_edit_screen import SongEditScreen
    else:
        print(f"Error: emsys.ui.song_edit_screen module exists but doesn't contain SongEditScreen class")
except ImportError as e:
    print(f"Error importing song_edit_screen: {e}")

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

        # MIDI State
        self.midi_port = None
        self.midi_port_name = None
        self.midi_error_message = None # To display status on screen if needed
        self.is_searching = False
        self.last_scan_time = 0
        self.last_connection_check_time = 0

        # UI State
        self.active_screen = None
        self.last_midi_message_str = None # Keep for potential display

        self._initialize_midi() # Attempt initial connection
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
             self.notify_status("FAIL: No UI screens loaded.")
             # Consider exiting if no screens? Or run with a default error screen?

        print("Screens initialized.")

    def _initialize_midi(self):
        """Finds and attempts to open the MIDI port initially."""
        self.notify_status(f"Initializing MIDI: Searching for '{MIDI_DEVICE_NAME}'...")
        # Use verbose=True for initial search
        found_port_name = find_midi_port(MIDI_DEVICE_NAME, verbose=True)
        if found_port_name:
            self.midi_port_name = found_port_name
            print(f"Attempting to open MIDI port: '{self.midi_port_name}'")
            try:
                self.midi_port = mido.open_input(self.midi_port_name)
                print(f"Successfully opened MIDI port: {self.midi_port_name}")
                self.notify_status(f"MIDI OK: {self.midi_port_name}. Notifying READY=1")
                self.notifier.notify("READY=1")
                self.is_searching = False
                self.midi_error_message = None
                self.last_connection_check_time = time.time() # Start checking connection
            except (IOError, ValueError, OSError, mido.MidiError) as e:
                error_info = f"Found '{self.midi_port_name}', but failed to open: {e}"
                print(error_info)
                self.midi_port = None
                self.midi_port_name = None
                self.midi_error_message = error_info + " Will retry..."
                self.is_searching = True # Start searching
                self.last_scan_time = time.time()
                self.notify_status(f"MIDI FAIL: {error_info}. Retrying...")
                self.notifier.notify("READY=1") # Notify ready even if MIDI fails initially
        else:
            error_info = f"MIDI Device '{MIDI_DEVICE_NAME}' not found."
            print(error_info)
            self.midi_port = None
            self.midi_port_name = None
            self.midi_error_message = error_info + " Will retry..."
            self.is_searching = True # Start searching
            self.last_scan_time = time.time()
            self.notify_status(f"MIDI FAIL: {error_info}. Retrying...")
            self.notifier.notify("READY=1") # Notify ready even if MIDI fails initially

    def _handle_disconnection(self, reason="Disconnected"):
        """Handles the state change when a MIDI disconnection is detected."""
        if self.midi_port is None and not self.is_searching:
             # Avoid handling disconnection multiple times if already disconnected and searching
             return

        print(f"\n--- Handling MIDI Disconnection (Reason: {reason}) ---")
        current_name = self.midi_port_name or MIDI_DEVICE_NAME # Use last known name or base name
        self.midi_error_message = f"{reason} from '{current_name}'. Searching..."
        self.notify_status(f"MIDI WARN: {self.midi_error_message}")
        print(f"Setting error message: {self.midi_error_message}")

        port_to_close = self.midi_port
        self.midi_port = None # Set to None immediately
        self.midi_port_name = None

        if port_to_close:
            try:
                print(f"Attempting to close port: {current_name}")
                port_to_close.close()
                print(f"Port {current_name} closed.")
            except Exception as close_err:
                print(f"Error closing MIDI port (might be expected on disconnect): {close_err}")

        self.is_searching = True
        self.last_scan_time = time.time() # Start scan timer immediately
        print(f"Set midi_port=None, is_searching=True. Starting scan timer.")
        print("----------------------------------------------------\n")

    def _attempt_reconnect(self):
        """Attempts to find and reopen the MIDI port during runtime."""
        print(f"[Reconnect Check] Attempting to find and open '{MIDI_DEVICE_NAME}'...")
        # Use verbose=False for reconnect attempts to reduce log spam
        found_port_name = find_midi_port(MIDI_DEVICE_NAME, verbose=False)
        if found_port_name:
            print(f"[Reconnect Check] Device '{MIDI_DEVICE_NAME}' found as '{found_port_name}'. Attempting to open...")
            try:
                # Optional small delay
                # time.sleep(0.1)
                new_port = mido.open_input(found_port_name)
                print(f"[Reconnect Check] SUCCESS! Reconnected to '{found_port_name}'.")
                self.midi_port = new_port
                self.midi_port_name = found_port_name
                self.midi_error_message = None # Clear error
                self.is_searching = False # Stop searching
                self.last_connection_check_time = time.time() # Reset connection check timer
                self.notify_status(f"MIDI OK: Reconnected to {self.midi_port_name}")
            except (IOError, ValueError, OSError, mido.MidiError) as e:
                error_msg = f"Found '{found_port_name}', but failed to open: {e}"
                print(f"[Reconnect Check] Error opening MIDI port '{found_port_name}': {e}")
                # Keep searching, update error message if it changed
                new_error_display = error_msg + " Retrying..."
                if new_error_display != self.midi_error_message:
                    self.midi_error_message = new_error_display
                    self.notify_status(f"MIDI WARN: {error_msg}. Retrying...")
                self.midi_port = None # Ensure port is None
                self.midi_port_name = None
                self.is_searching = True # Ensure searching continues
            except Exception as e:
                 error_msg = f"Found '{found_port_name}', unexpected error opening: {e}"
                 print(f"[Reconnect Check] Unexpected error opening '{found_port_name}': {e}")
                 traceback.print_exc()
                 new_error_display = error_msg + " Retrying..."
                 if new_error_display != self.midi_error_message:
                     self.midi_error_message = new_error_display
                     self.notify_status(f"MIDI WARN: {error_msg}. Retrying...")
                 self.midi_port = None
                 self.midi_port_name = None
                 self.is_searching = True # Continue searching even on unexpected open error
        else:
            # Device not found during this scan
            error_msg = f"Device '{MIDI_DEVICE_NAME}' not found."
            # print(f"[Reconnect Check] {error_msg}") # Less verbose
            new_error_display = error_msg + " Retrying..."
            if new_error_display != self.midi_error_message:
                 self.midi_error_message = new_error_display
                 # No need to notify status every time it's not found, handled by initial disconnect message
            self.is_searching = True # Ensure searching continues

    def notify_status(self, status_message):
        """Helper function to print status and notify systemd."""
        max_len = 80 # Limit systemd status length
        truncated_message = status_message[:max_len] + '...' if len(status_message) > max_len else status_message
        print(f"Status: {status_message}") # Print full message to console
        try:
            # Update internal error message for potential UI display
            # self.midi_error_message = status_message # Or maybe only on errors?
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
        # Initial status depends on MIDI state
        if self.midi_port:
             self.notify_status(f"Running. Screen: {self.active_screen.__class__.__name__}. MIDI: {self.midi_port_name}")
        else:
             self.notify_status(f"Running. Screen: {self.active_screen.__class__.__name__}. MIDI: Searching...")

        while self.running:
            current_time = time.time()

            # --- Event Handling (Pygame) ---
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    self.running = False
                # Pass other events to the active screen
                if self.active_screen:
                    self.active_screen.handle_event(event) # Assuming screens have this method

            # --- MIDI Reconnection Attempt ---
            if self.midi_port is None and self.is_searching:
                if (current_time - self.last_scan_time) >= RESCAN_INTERVAL_SECONDS:
                    self.last_scan_time = current_time
                    # Status update is handled within _attempt_reconnect if needed
                    self._attempt_reconnect()
                    # Update status after attempt regardless of success/fail
                    if self.midi_port:
                         self.notify_status(f"Screen: {self.active_screen.__class__.__name__}. MIDI: {self.midi_port_name}")
                    elif self.midi_error_message:
                         self.notify_status(f"Screen: {self.active_screen.__class__.__name__}. MIDI: {self.midi_error_message}")
                    else: # Should have an error message if searching
                         self.notify_status(f"Screen: {self.active_screen.__class__.__name__}. MIDI: Searching...")


            # --- MIDI Input Handling & Active Check ---
            if self.midi_port:
                # --- Active Connection Check ---
                if (current_time - self.last_connection_check_time) >= CONNECTION_CHECK_INTERVAL_SECONDS:
                    self.last_connection_check_time = current_time
                    try:
                        # Use verbose=False for background checks
                        if not find_midi_port(self.midi_port_name, verbose=False):
                            print(f"[Active Check] Port '{self.midi_port_name}' is GONE.")
                            self._handle_disconnection("Device not listed")
                            continue # Skip reading this frame
                    except Exception as check_err:
                         print(f"[Active Check] Error while checking available ports: {check_err}")
                         self._handle_disconnection(f"Port check error: {check_err}")
                         continue

                # --- Process MIDI Messages ---
                try:
                    while True: # Use non-blocking receive
                        msg = self.midi_port.receive(block=False)
                        if msg is None:
                            break # No more messages pending
                        self.handle_midi_message(msg) # Process the message

                except (OSError, mido.MidiError) as e: # Catch specific read errors
                    print(f"MIDI Read Error: {e}.")
                    self._handle_disconnection(f"Read error: {e}")
                    continue # Skip rest of frame

                except Exception as e: # Catch unexpected errors during receive
                    print(f"\n--- Unexpected MIDI Error During Receive ---")
                    print(f"Error type: {type(e)}")
                    print(f"Error details: {e}")
                    traceback.print_exc()
                    self._handle_disconnection(f"Unexpected error: {e}")
                    # Decide whether to keep searching or stop on unexpected errors
                    self.is_searching = False # Stop searching on truly unexpected errors
                    self.midi_error_message = f"Unexpected MIDI Error: {e}. Stopped."
                    self.notify_status(f"MIDI FATAL: Unexpected error {e}. Stopped.")
                    # Optionally stop the app: self.running = False
                    continue

            # --- Update Active Screen ---
            if self.active_screen:
                 try:
                     self.active_screen.update() # Assuming screens have this method
                 except Exception as screen_update_err:
                      print(f"Error updating screen {self.active_screen.__class__.__name__}: {screen_update_err}")
                      traceback.print_exc()
                      # Handle screen error? Switch screen? Exit?
                      # For now, just log it.

            # --- Draw ---
            self.screen.fill(BLACK)
            if self.active_screen:
                try:
                    # Pass MIDI status info to the draw method if needed
                    midi_status = self.midi_error_message or (f"Connected: {self.midi_port_name}" if self.midi_port else "Initializing MIDI...")
                    self.active_screen.draw(self.screen, midi_status=midi_status) # Modify draw signature if needed
                except Exception as screen_draw_err:
                     print(f"Error drawing screen {self.active_screen.__class__.__name__}: {screen_draw_err}")
                     traceback.print_exc()
                     # Draw a fallback error message?
                     try:
                         font = pygame.font.Font(None, 24)
                         err_surf = font.render(f"Screen Draw Error!", True, RED)
                         self.screen.blit(err_surf, (10, 10))
                     except: pass # Ignore errors during error drawing
            else:
                 # Draw something if no screen is active
                 try:
                     font = pygame.font.Font(None, 36)
                     err_surf = font.render("No Active Screen!", True, RED)
                     self.screen.blit(err_surf, (self.screen.get_width()//2 - err_surf.get_width()//2, self.screen.get_height()//2 - err_surf.get_height()//2))
                 except: pass

            pygame.display.flip()

            # --- Frame Rate Control ---
            self.clock.tick(FPS)

        # --- Exit ---
        self.cleanup()

    def handle_midi_message(self, msg):
        """Process incoming MIDI messages."""
        # Optional: Reduce console spam by only printing specific messages or errors
        # print(f"MIDI Received: {msg}")
        self.last_midi_message_str = str(msg) # Store for potential display

        if msg.type == 'control_change':
            # --- Global CC Handling ---
            if msg.control == EXIT_CC and msg.value == 127:
                print(f"Exit command received (CC #{EXIT_CC}). Shutting down.")
                self.notify_status("Exit command received...")
                self.running = False
                return # Stop processing this message further
            elif msg.control == NEXT_SCREEN_CC and msg.value == 127:
                print(f"Next screen command received (CC #{NEXT_SCREEN_CC})")
                self.next_screen()
                return # Stop processing this message further
            elif msg.control == PREV_SCREEN_CC and msg.value == 127:
                print(f"Previous screen command received (CC #{PREV_SCREEN_CC})")
                self.previous_screen()
                return # Stop processing this message further

            # --- Pass to Active Screen ---
            # Check if active_screen exists and has a handle_midi method
            if self.active_screen and hasattr(self.active_screen, 'handle_midi'):
                try:
                    self.active_screen.handle_midi(msg)
                except Exception as screen_midi_err:
                     print(f"Error in screen {self.active_screen.__class__.__name__} handling MIDI {msg}: {screen_midi_err}")
                     traceback.print_exc()
        else:
             # Handle other message types if needed, or pass them to the screen
             if self.active_screen and hasattr(self.active_screen, 'handle_midi'):
                 try:
                     self.active_screen.handle_midi(msg)
                 except Exception as screen_midi_err:
                      print(f"Error in screen {self.active_screen.__class__.__name__} handling MIDI {msg}: {screen_midi_err}")
                      traceback.print_exc()


    def next_screen(self):
        """Switch to the next available screen."""
        if not hasattr(self, 'screens') or not self.screens: return # No screens to switch
        try:
            current_index = self.screens.index(self.active_screen)
            next_index = (current_index + 1) % len(self.screens)
            self.set_active_screen(self.screens[next_index])
        except (ValueError, AttributeError): # Handle if active_screen somehow not in list
             if self.screens: self.set_active_screen(self.screens[0])

    def previous_screen(self):
        """Switch to the previous available screen."""
        if not hasattr(self, 'screens') or not self.screens: return # No screens to switch
        try:
            current_index = self.screens.index(self.active_screen)
            prev_index = (current_index - 1) % len(self.screens) # Correctly handles negative index
            self.set_active_screen(self.screens[prev_index])
        except (ValueError, AttributeError): # Handle if active_screen somehow not in list
             if self.screens: self.set_active_screen(self.screens[0])

    def set_active_screen(self, screen):
        """Set the active screen, call cleanup/init if needed, and notify status."""
        if self.active_screen == screen or screen is None:
            if screen is None: print("Error: Attempted to set active screen to None.")
            return # No change needed or invalid input

        # Cleanup old screen
        if self.active_screen and hasattr(self.active_screen, 'cleanup'):
            print(f"Cleaning up screen: {self.active_screen.__class__.__name__}")
            try: self.active_screen.cleanup()
            except Exception as e: print(f"Error during screen cleanup: {e}")

        self.active_screen = screen

        # Initialize new screen
        if hasattr(self.active_screen, 'init'):
             print(f"Initializing screen: {self.active_screen.__class__.__name__}")
             try: self.active_screen.init()
             except Exception as e: print(f"Error during screen init: {e}")

        print(f"Switched to screen: {screen.__class__.__name__}")
        # Update status notification (MIDI status might change later in the loop)
        current_midi_status = self.midi_error_message or (self.midi_port_name if self.midi_port else "Searching...")
        self.notify_status(f"Screen: {self.active_screen.__class__.__name__}. MIDI: {current_midi_status}")


    def cleanup(self):
        """Clean up resources before exiting."""
        current_status = "Cleaning up..."
        self.notify_status(current_status)
        print(current_status)

        if self.active_screen and hasattr(self.active_screen, 'cleanup'):
            print(f"Cleaning up final screen: {self.active_screen.__class__.__name__}")
            try: self.active_screen.cleanup()
            except Exception as e: print(f"Error during final screen cleanup: {e}")

        # Ensure MIDI port is closed if it exists
        if self.midi_port:
            print(f"Closing MIDI port: {self.midi_port_name}")
            try: self.midi_port.close()
            except Exception as e: print(f"Error closing MIDI port: {e}")
        self.midi_port = None # Ensure it's None after closing

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
        # Check if initialization resulted in a usable state
        if app.active_screen is None and not app.screens:
             print("App initialization failed: No screens loaded. Exiting.")
             if app: app.cleanup() # Attempt cleanup even if init failed partially
             sys.exit(1)
        elif app.active_screen is None and app.screens:
             print("App initialization warning: Screens loaded but no active screen set.")
             # Attempt to set the first screen again? Or proceed cautiously?
             app.set_active_screen(app.screens[0])
             if app.active_screen is None: # Check if setting it worked
                  print("Failed to set initial active screen. Exiting.")
                  if app: app.cleanup()
                  sys.exit(1)

        app.run()
        sys.exit(0) # Normal exit
    except KeyboardInterrupt:
         print("\nCtrl+C detected. Exiting gracefully.")
         if app: app.cleanup()
         sys.exit(0)
    except Exception as e:
        print(f"\n--- An unhandled error occurred in main ---")
        traceback.print_exc()
        try:
            n = sdnotify.SystemdNotifier()
            n.notify("STATUS=Crashed unexpectedly.")
            n.notify("STOPPING=1")
        except Exception as sd_err:
            print(f"(Could not notify systemd: {sd_err})")
        # Attempt cleanup even after crash
        if app:
            try:
                if app.active_screen and hasattr(app.active_screen, 'cleanup'): app.active_screen.cleanup()
                if app.midi_port: app.midi_port.close()
            except: pass # Ignore errors during crash cleanup
        try: pygame.quit()
        except: pass
        sys.exit(1) # Exit with error code

if __name__ == '__main__':
    main()
