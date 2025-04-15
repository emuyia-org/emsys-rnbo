# -*- coding: utf-8 -*-
"""
Main entry point for the Emsys Python Application. V2 (Refactored)

Initializes Pygame, MIDI service, Screen manager, and runs the main event loop.
Handles exit via MIDI CC 47. Includes MIDI device auto-reconnection via MidiService.
Implements universal button hold-repeat for MIDI CC messages.
"""
import pygame
import mido
import time
import sys
import os
import sdnotify # For systemd notification
import traceback # For detailed error logs
from typing import Optional, Dict, Any # <<< ADDED Dict and Any

# Add the project root directory to the path to enable absolute imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now we can use absolute imports from the emsys package
from emsys.config import settings as settings_module
# Import settings constants
SCREEN_WIDTH = settings_module.SCREEN_WIDTH
SCREEN_HEIGHT = settings_module.SCREEN_HEIGHT
FPS = settings_module.FPS
BLACK = settings_module.BLACK
WHITE = settings_module.WHITE
RED = settings_module.RED

# --- Import Button Repeat Settings ---
BUTTON_REPEAT_DELAY_S = getattr(settings_module, 'BUTTON_REPEAT_DELAY_MS', 500) / 1000.0
BUTTON_REPEAT_INTERVAL_S = getattr(settings_module, 'BUTTON_REPEAT_INTERVAL_MS', 100) / 1000.0

# --- Import specific CCs and non-repeatable set ---
from emsys.config.mappings import NEXT_CC, PREV_CC, NON_REPEATABLE_CCS

# --- Refactored Imports ---
from emsys.services.midi_service import MidiService
from emsys.ui.screen_manager import ScreenManager
from emsys.ui.base_screen import BaseScreen  # Import BaseScreen
# --------------------------

from emsys.utils import file_io # Keep for load/save last song operations

# Main Application Class
class App:
    """Encapsulates the main application logic and state."""

    def __init__(self):
        """Initialize Pygame, services, and application state."""
        print("Initializing App...")
        self.notifier = sdnotify.SystemdNotifier()
        self.notify_status("Initializing Pygame...")

        pygame.init()
        pygame.font.init() # Font init needed for screens/widgets
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Emsys Controller')
        self.clock = pygame.time.Clock()
        pygame.mouse.set_visible(False) # Assume headless operation
        self.running = False

        # --- Instantiate Services ---
        # Pass self.notify_status as the callback for MidiService
        self.midi_service = MidiService(status_callback=self.notify_status)
        self.screen_manager = ScreenManager(app_ref=self) # Pass app reference
        # --------------------------

        # --- Application State ---
        self.current_song = None # Will be loaded/managed by screens interacting with file_io
        self.last_midi_message_str = None # Keep for potential display
        # Dictionary mapping control_number to {'press_time': float, 'last_repeat_time': float, 'message': mido.Message}
        self.pressed_buttons: Dict[int, Dict[str, Any]] = {}
        # -------------------------

        # --- Final Initialization Steps ---
        self.screen_manager.set_initial_screen() # Set the first screen active
        if not self.screen_manager.get_active_screen():
            # Handle case where no screens could be initialized
             self.notify_status("FAIL: No UI screens loaded.")
             raise RuntimeError("Application cannot start without any screens.") # Raise error to stop init

        self._initial_led_update() # Update LEDs based on initial screen
        self._load_last_song()
        print("App initialization complete.")


    def notify_status(self, status_message):
        """Helper function to print status and notify systemd."""
        max_len = 80 # Limit systemd status length
        truncated_message = status_message[:max_len] + '...' if len(status_message) > max_len else status_message
        print(f"Status: {status_message}") # Print full message to console
        try:
            self.notifier.notify(f"STATUS={truncated_message}")
        except Exception as e:
            print(f"Could not notify systemd: {e}")

    def run(self):
        """Main application loop."""
        self.running = True
        self.notify_status("Application Running") # Initial running status
        # Update status with initial screen and MIDI state
        self.update_combined_status()
        self.notifier.notify("READY=1")
        print("Application loop started.")

        while self.running:
            current_time = time.time()

            # --- Process Pending Screen Change ---
            self.screen_manager.process_pending_change()
            active_screen = self.screen_manager.get_active_screen() # Get current active screen

            # --- MIDI Connection Management ---
            if self.midi_service.is_searching:
                self.midi_service.attempt_reconnect()
            else:
                self.midi_service.check_connection()

            # --- Process MIDI Input ---
            # Get messages from the service
            try:
                midi_messages = self.midi_service.receive_messages()
                for msg in midi_messages:
                    self.handle_midi_message(msg)
            except Exception as e:
                 print(f"\n--- Unhandled Error in MIDI receive loop ---")
                 traceback.print_exc()
                 # Consider if this should stop the app or try to recover

            # --- Process Pygame Events ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                # Pass event to active screen if it has a handler
                if active_screen and hasattr(active_screen, 'handle_event'):
                    try: # Add try-except around screen handlers
                        active_screen.handle_event(event)
                    except Exception as e:
                        print(f"Error in {active_screen.__class__.__name__} handle_event: {e}")
                        traceback.print_exc()

            # --- Handle Button Repeats ---
            self._handle_button_repeats(current_time)

            # --- Update Active Screen ---
            if active_screen and hasattr(active_screen, 'update'):
                try: # Add try-except
                    active_screen.update()
                except Exception as e:
                    print(f"Error in {active_screen.__class__.__name__} update: {e}")
                    traceback.print_exc()


            # --- Drawing ---
            self.screen.fill(BLACK)
            if active_screen and hasattr(active_screen, 'draw'):
                try: # Add try-except
                    # Get MIDI status string from the service
                    midi_status_str = self.midi_service.get_status_string()
                    active_screen.draw(self.screen, midi_status=midi_status_str)
                except Exception as e:
                    print(f"Error in {active_screen.__class__.__name__} draw: {e}")
                    traceback.print_exc()
                    # Optionally draw an error message to the screen
                    error_font = pygame.font.Font(None, 30)
                    error_surf = error_font.render(f"Draw Error in {active_screen.__class__.__name__}!", True, RED)
                    self.screen.blit(error_surf, (10, self.screen.get_height() // 2))


            pygame.display.flip()
            self.clock.tick(FPS)
            # Optional: Update systemd status periodically
            # if current_time - last_status_update > 5.0:
            #    self.update_combined_status()
            #    last_status_update = current_time

        print("Application loop finished.")
        self.cleanup()

    def handle_midi_message(self, msg):
        """
        Process incoming MIDI messages. Routes based on type and CC.
        Handles button press/release/repeat logic for momentary buttons.
        Directly dispatches messages for non-repeatable controls.
        """
        # Filter channel (e.g., only channel 16 - Mido index 15)
        if hasattr(msg, 'channel') and msg.channel != 15:
            # print(f"Ignoring MIDI message on channel {msg.channel + 1}") # Debug
            return

        self.last_midi_message_str = str(msg) # Store for potential display
        current_time = time.time()

        if msg.type == 'control_change':
            control = msg.control
            value = msg.value

            # Check if this CC is an encoder/fader/etc. (non-repeatable)
            if control in NON_REPEATABLE_CCS:
                # Directly dispatch non-repeatable controls
                self._dispatch_action(msg)
                return # Handled non-repeatable CC

            # Handle MOMENTARY Button Press (value == 127)
            if value == 127:
                if control not in self.pressed_buttons:
                    # print(f"Button Press Detected: CC {control}") # Debug
                    self.pressed_buttons[control] = {
                        'press_time': current_time,
                        'last_repeat_time': current_time,
                        'message': msg
                    }
                    # --- Dispatch action ONLY on initial press ---
                    self._dispatch_action(msg)
                return # Handled momentary press

            # Handle MOMENTARY Button Release (value == 0)
            elif value == 0:
                if control in self.pressed_buttons:
                    # print(f"Button Release Detected: CC {control}") # Debug
                    del self.pressed_buttons[control]
                # --- DO NOT DISPATCH ACTION ON RELEASE ---
                return # Handled momentary release

            # Handle Other CC Values (if any non-momentary, non-repeatable buttons exist)
            else:
                 # print(f"Unhandled CC value: CC {control}, Value {value}") # Optional debug
                 return

        # Handle Non-CC Messages (Notes, etc.) - Dispatch directly
        else:
            self._dispatch_action(msg)

    def _dispatch_action(self, msg):
        """
        Determines and executes the action associated with a MIDI message.
        Handles global actions (screen switching) or passes to the active screen.
        Prevents global screen switching if an input widget is active on the screen.
        """
        active_screen = self.screen_manager.get_active_screen()

        # --- Check if TextInputWidget is active on the current screen ---
        # This requires the screen to expose its widget's state
        widget_active = False
        if active_screen:
            # Check standard attribute name used in provided screens
            text_input_widget = getattr(active_screen, 'text_input_widget', None)
            if text_input_widget and getattr(text_input_widget, 'is_active', False):
                 widget_active = True
                 # print("TextInputWidget is active, bypassing global screen nav.") # Debug


        # --- Handle Control Change Messages ---
        if msg.type == 'control_change':
            control = msg.control
            value = msg.value

            # --- Global Actions (Screen Navigation - only if widget is NOT active) ---
            # Check common button press value (e.g., 127)
            if not widget_active and value == 127:
                if control == NEXT_CC:
                    print(f"Requesting next screen (via CC #{NEXT_CC})")
                    self.screen_manager.request_next_screen()
                    return # Action handled

                elif control == PREV_CC:
                    print(f"Requesting previous screen (via CC #{PREV_CC})")
                    self.screen_manager.request_previous_screen()
                    return # Action handled

            # --- Pass to Active Screen (Always, unless handled by global action) ---
            # If widget is active, NEXT/PREV CCs will fall through here.
            # If widget is inactive, other CCs will fall through here.
            if active_screen and hasattr(active_screen, 'handle_midi'):
                try:
                    # print(f"Passing CC {control} (Val:{value}) to screen: {active_screen.__class__.__name__}") # Debug
                    active_screen.handle_midi(msg)
                except Exception as screen_midi_err:
                     print(f"Error in screen {active_screen.__class__.__name__} handling MIDI {msg}: {screen_midi_err}")
                     traceback.print_exc()
            # else: # Debug
                 # if active_screen: print(f"Screen {active_screen.__class__.__name__} has no handle_midi method for {msg}")
                 # else: print(f"No active screen to handle MIDI {msg}")

        # --- Handle Other Message Types (Notes, etc.) ---
        else:
            # Pass non-CC messages directly to the active screen
            if active_screen and hasattr(active_screen, 'handle_midi'):
                try:
                    # print(f"Passing non-CC message {msg} to screen: {active_screen.__class__.__name__}") # Debug
                    active_screen.handle_midi(msg)
                except Exception as screen_midi_err:
                     print(f"Error in screen {active_screen.__class__.__name__} handling MIDI {msg}: {screen_midi_err}")
                     traceback.print_exc()
            # else: print(f"No active screen or handle_midi method for non-CC message {msg}") # Debug


    def _handle_button_repeats(self, current_time):
        """Check and handle button repeats based on the current time."""
        # Iterate over a copy of keys in case the dict changes during iteration
        pressed_controls = list(self.pressed_buttons.keys())
        for control in pressed_controls:
            if control not in self.pressed_buttons: continue # Check if released during iteration

            # Skip repeat for non-repeatable controls (faders, knobs, etc.)
            if control in NON_REPEATABLE_CCS:
                continue

            state = self.pressed_buttons[control]
            time_held = current_time - state['press_time']

            # Check if initial delay has passed
            if time_held >= BUTTON_REPEAT_DELAY_S:
                # Check if repeat interval has passed since last repeat/press
                if (current_time - state['last_repeat_time']) >= BUTTON_REPEAT_INTERVAL_S:
                    # print(f"Repeat Action for CC {control}") # Debug
                    self._dispatch_action(state['message']) # Dispatch the original press message again
                    state['last_repeat_time'] = current_time # Update last repeat time


    def _initial_led_update(self):
        """Send initial LED values via MidiService, potentially based on active screen."""
        print("Sending initial LED states...")
        # Example: Turn off LEDs for specific knobs (e.g., B1-B8, CC 9-16)
        for i in range(8):
            knob_cc = 9 + i
            self.send_midi_cc(control=knob_cc, value=0) # Default channel is 15

        # Optionally, trigger the active screen's LED update method if it exists
        active_screen = self.screen_manager.get_active_screen()
        if active_screen and hasattr(active_screen, '_update_encoder_led'):
            if callable(getattr(active_screen, '_update_encoder_led')):
                print(f"Calling initial LED update for {active_screen.__class__.__name__}")
                try:
                    active_screen._update_encoder_led()
                except Exception as e:
                    print(f"Error calling _update_encoder_led on {active_screen.__class__.__name__}: {e}")


    # --- Methods for Screens to Interact with App/Services ---
    def send_midi_cc(self, control: int, value: int, channel: int = 15):
        """Allows screens to send MIDI CC messages via the MidiService."""
        self.midi_service.send_cc(control, value, channel)

    def request_screen_change(self):
        """
        Called by a screen (e.g., after resolving an exit prompt) to indicate
        that a previously blocked screen change can now proceed.
        Delegates to the ScreenManager.
        """
        self.screen_manager.request_screen_change_approved()

    def set_active_screen(self, screen_instance: BaseScreen):
        """Allows screens (or other logic) to request a specific screen change."""
        # This bypasses the normal next/prev logic and sets directly
        # Useful for actions like "Load Song -> Go to Edit Screen"
        print(f"Direct request to set active screen to {screen_instance.__class__.__name__}")
        # Set pending change, main loop will process it
        self.screen_manager.pending_screen_change = screen_instance

    def update_combined_status(self):
        """Updates the systemd status with screen and MIDI info."""
        screen_name = "No Screen"
        active_screen = self.screen_manager.get_active_screen()
        if active_screen:
            screen_name = active_screen.__class__.__name__
        midi_status = self.midi_service.get_status_string()
        # Combine and truncate if necessary
        combined_status = f"Screen: {screen_name} | {midi_status}"
        self.notify_status(combined_status) # Use notify_status for truncation and sending


    # --- Load/Save Last Song ---
    def _load_last_song(self):
        """Load the previously loaded song name."""
        # This logic remains simple, interacting directly with file_io for this specific file
        last_song_file = os.path.join(settings_module.PROJECT_ROOT, "last_song.txt")
        if os.path.exists(last_song_file):
            try:
                with open(last_song_file, "r") as f:
                    last_song_basename = f.read().strip()
                if last_song_basename:
                    # Load the actual song object - screens handle this on init/load actions
                    # Here, we just notify about the last *name*
                    print(f"Last session ended with song: '{last_song_basename}'")
                    # We don't set self.current_song here, let SongManager load it
                    # self.notify_status(f"Last song was: {last_song_basename}")
            except Exception as e:
                print(f"Error loading last song name: {e}")


    def _save_last_song(self):
        """Save the name of the current song to persistent storage."""
        # Screens are responsible for updating self.current_song
        last_song_file = os.path.join(settings_module.PROJECT_ROOT, "last_song.txt")
        if self.current_song and self.current_song.name:
            try:
                with open(last_song_file, "w") as f:
                    f.write(self.current_song.name)
                print(f"Saved last song name: '{self.current_song.name}'")
            except Exception as e:
                 print(f"Error saving last song name: {e}")
        elif os.path.exists(last_song_file):
             try:
                 # If no current song, remove the file
                 os.remove(last_song_file)
                 print("Removed last_song.txt (no current song).")
             except Exception as e:
                  print(f"Error removing last_song.txt: {e}")

    def cleanup(self):
        """Clean up resources before exiting."""
        print("Cleaning up application...")
        self.notify_status("Application Shutting Down")

        # Check for unsaved changes (optional, depends on desired exit behavior)
        active_screen = self.screen_manager.get_active_screen()
        is_dirty = False
        if hasattr(self.current_song, 'dirty') and self.current_song.dirty:
             is_dirty = True
        # Some screens might have their own dirty state (e.g., unsaved edits not yet in song object)
        # if active_screen and getattr(active_screen, 'is_dirty', False): is_dirty = True

        if is_dirty:
            print("Warning: Exiting with unsaved changes.")
            # For a service, usually save automatically or just exit.
            # For interactive, might prompt, but less applicable here.

        # Save the name of the current song (even if dirty)
        self._save_last_song()

        # Cleanup active screen
        self.screen_manager.cleanup_active_screen()

        # Close MIDI ports via service
        # Optionally send LED off command first
        self._initial_led_update() # Re-use to turn off LEDs
        time.sleep(0.1) # Short pause
        self.midi_service.close_ports()

        # Quit Pygame
        pygame.font.quit()
        pygame.quit()
        print("Pygame quit.")
        self.notifier.notify("STOPPING=1")
        print("Cleanup finished.")


# Script Entry Point
def main():
    """Main function."""
    app = None
    try:
        app = App() # Initialization happens within App.__init__
        app.run()
        sys.exit(0) # Normal exit
    except KeyboardInterrupt:
         print("\nCtrl+C detected. Exiting gracefully.")
         if app: app.cleanup()
         sys.exit(0)
    except RuntimeError as e: # Catch init errors specifically
        print(f"Application initialization failed: {e}")
        # Attempt minimal cleanup if app partially initialized
        try:
            if app and app.midi_service: app.midi_service.close_ports()
            if app and app.notifier:
                 app.notifier.notify("STATUS=Initialization Failed. Exiting.")
                 app.notifier.notify("STOPPING=1")
            pygame.quit()
        except: pass # Ignore cleanup errors during init failure
        sys.exit(1)
    except Exception as e:
        print(f"\n--- An unhandled error occurred in main ---")
        traceback.print_exc()
        # Attempt to notify systemd and cleanup
        try:
            n = sdnotify.SystemdNotifier()
            n.notify("STATUS=Crashed unexpectedly.")
            n.notify("STOPPING=1")
        except Exception as sd_err:
            print(f"(Could not notify systemd: {sd_err})")
        if app: app.cleanup() # Attempt full cleanup
        else:
             try: pygame.quit() # Minimal cleanup if app failed early
             except: pass
        sys.exit(1) # Exit with error code

if __name__ == '__main__':
    main()
