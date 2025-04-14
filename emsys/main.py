# -*- coding: utf-8 -*-
"""
Main entry point for the Emsys Python Application. V1

Initializes Pygame, basic MIDI, UI placeholder, and runs the main event loop.
Handles exit via MIDI CC 47. Includes MIDI device auto-reconnection.
Implements universal button hold-repeat for MIDI CC messages.
"""

import pygame
import mido
import mido.backends.rtmidi # Explicitly import backend if needed
import time
import sys
import os
import sdnotify # For systemd notification
import traceback # For detailed error logs

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
# Import Button Repeat Settings (convert to seconds for internal use)
# Use getattr for safe access with defaults
BUTTON_REPEAT_DELAY_S = getattr(settings_module, 'BUTTON_REPEAT_DELAY_MS', 500) / 1000.0
BUTTON_REPEAT_INTERVAL_S = getattr(settings_module, 'BUTTON_REPEAT_INTERVAL_MS', 100) / 1000.0


# --- Import specific CCs ---
from emsys.config.mappings import NEXT_CC, PREV_CC, FADER_SELECT_CC # Keep FADER_SELECT_CC if used elsewhere directly
# --- Import the set of non-repeatable CCs ---
from emsys.config.mappings import NON_REPEATABLE_CCS
# -------------------------------------------
from emsys.utils.midi import find_midi_port
from emsys.utils import file_io       # <<< ADDED: Import file_io for load/save song operations

# UI Imports
from emsys.ui.base_screen import BaseScreen
# from emsys.ui.main_menu_screen import MainMenuScreen # Assuming not used based on test.py
from emsys.ui.placeholder_screen import PlaceholderScreen

# Additional screen imports (keep existing logic)
SongManagerScreen = None
SongEditScreen = None
try:
    import emsys.ui.song_manager_screen
    if hasattr(emsys.ui.song_manager_screen, 'SongManagerScreen'):
        from emsys.ui.song_manager_screen import SongManagerScreen
    else:
        print(f"Error: emsys.ui.song_manager_screen module exists but doesn't contain SongManagerScreen class")
except ImportError as e:
    print(f"Error importing song_manager_screen: {e}")
try:
    import emsys.ui.song_edit_screen
    if hasattr(emsys.ui.song_edit_screen, 'SongEditScreen'):
        from emsys.ui.song_edit_screen import SongEditScreen
    else:
        print(f"Error: emsys.ui.song_edit_screen module exists but doesn't contain SongEditScreen class")
except ImportError as e:
    print(f"Error importing song_edit_screen: {e}")

print(f"Available screens: SongManagerScreen={'Available' if SongManagerScreen else 'Not Available'}, "
      f"SongEditScreen={'Available' if SongEditScreen else 'Not Available'}")
print(f"Universal Button Repeat: Delay={BUTTON_REPEAT_DELAY_S*1000}ms, Interval={BUTTON_REPEAT_INTERVAL_S*1000}ms")


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
        self.midi_output_port = None # <<< ADDED: MIDI Output Port
        self.midi_output_port_name = None # <<< ADDED: MIDI Output Port Name
        self.midi_error_message = None
        self.is_searching = False
        self.last_scan_time = 0
        self.last_connection_check_time = 0

        # UI State
        self.active_screen = None
        self.last_midi_message_str = None # Keep for potential display

        # Button Hold State (Universal for all CCs)
        # Dictionary mapping control_number to {'press_time': float, 'last_repeat_time': float, 'message': mido.Message}
        self.pressed_buttons = {}

        self._initialize_midi() # Attempt initial connection (Input and Output)
        self.initialize_screens()
        self._initial_led_update() # <<< ADDED: Update LEDs on startup
        self.current_song = None  # Ensure we have a variable to hold the current song
        self._load_last_song()

    def initialize_screens(self):
        """Initialize all application screens."""
        print("Initializing Screens...")
        self.placeholder_screen = PlaceholderScreen(self)

        if SongManagerScreen:
            self.song_manager_screen = SongManagerScreen(self)
        else:
            self.song_manager_screen = None

        if SongEditScreen:
            self.song_edit_screen = SongEditScreen(self)
        else:
            self.song_edit_screen = None

        # Create a list of screens for navigation in the desired order
        self.screens = [
            screen for screen in [
                self.placeholder_screen,
                self.song_manager_screen,
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
        """Finds and attempts to open the MIDI input and output ports initially."""
        self.notify_status(f"Initializing MIDI: Searching for '{MIDI_DEVICE_NAME}'...")
        # Use verbose=True for initial search
        found_input_port_name = find_midi_port(MIDI_DEVICE_NAME, verbose=True, port_type='input')
        found_output_port_name = find_midi_port(MIDI_DEVICE_NAME, verbose=True, port_type='output') # <<< ADDED: Search for output

        # --- Handle Input Port ---
        if found_input_port_name:
            try:
                self.midi_port = mido.open_input(found_input_port_name)
                self.midi_port_name = found_input_port_name
                self.midi_error_message = None
                self.is_searching = False
                print(f"Successfully opened MIDI Input: '{self.midi_port_name}'")
                self.notify_status(f"MIDI Input Connected: '{self.midi_port_name}'")
            except (IOError, OSError) as e:
                self.midi_port = None
                self.midi_port_name = None
                self.midi_error_message = f"Error opening Input '{found_input_port_name}': {e}"
                print(self.midi_error_message)
                self.notify_status(f"Error opening MIDI Input: {e}")
                self._start_search_mode() # Start searching if initial open fails
        else:
            self.midi_error_message = f"MIDI Input '{MIDI_DEVICE_NAME}' not found."
            print(self.midi_error_message)
            self.notify_status(f"MIDI Input '{MIDI_DEVICE_NAME}' not found. Searching...")
            self._start_search_mode()

        # --- Handle Output Port ---
        if found_output_port_name:
            try:
                # Add use_virtual=False if you encounter issues with virtual ports on Linux
                self.midi_output_port = mido.open_output(found_output_port_name)
                self.midi_output_port_name = found_output_port_name
                print(f"Successfully opened MIDI Output: '{self.midi_output_port_name}'")
                self.notify_status(f"MIDI Output Connected: '{self.midi_output_port_name}'")
            except (IOError, OSError) as e:
                self.midi_output_port = None
                self.midi_output_port_name = None
                # Don't necessarily set midi_error_message here, input status is primary
                print(f"Warning: Error opening Output '{found_output_port_name}': {e}")
                self.notify_status(f"Warning: Error opening MIDI Output: {e}")
                # We might still be able to run without output, don't force search mode just for output failure
        else:
             print(f"Warning: MIDI Output '{MIDI_DEVICE_NAME}' not found.")
             self.notify_status(f"Warning: MIDI Output '{MIDI_DEVICE_NAME}' not found.")
             # No output port found, LED feedback won't work

    def _handle_disconnection(self, reason="Disconnected"):
        """Handles the state change when a MIDI disconnection is detected."""
        if self.midi_port is None and self.midi_output_port is None and not self.is_searching:
             return # Already disconnected and searching

        print(f"\n--- Handling MIDI Disconnection (Reason: {reason}) ---")
        if self.midi_port:
            try:
                self.midi_port.close()
                print("MIDI Input port closed.")
            except Exception as e:
                print(f"Error closing MIDI Input port: {e}")
            self.midi_port = None
            self.midi_port_name = None

        if self.midi_output_port: # <<< ADDED: Close output port
            try:
                self.midi_output_port.close()
                print("MIDI Output port closed.")
            except Exception as e:
                print(f"Error closing MIDI Output port: {e}")
            self.midi_output_port = None
            self.midi_output_port_name = None

        self.midi_error_message = f"MIDI Disconnected ({reason}). Searching..."
        self.notify_status(self.midi_error_message)
        self._start_search_mode()

    def _attempt_reconnect(self):
        """Attempts to find and reopen the MIDI input and output ports."""
        if not self.is_searching:
             return # Should not happen, but safety check

        current_time = time.time()
        if current_time - self.last_scan_time < RESCAN_INTERVAL_SECONDS:
            return # Wait before scanning again

        self.last_scan_time = current_time
        print(f"Scanning for MIDI device '{MIDI_DEVICE_NAME}'...")
        self.notify_status(f"Scanning for '{MIDI_DEVICE_NAME}'...")

        # Use verbose=False during reconnection attempts to reduce log noise
        found_input_port_name = find_midi_port(MIDI_DEVICE_NAME, verbose=False, port_type='input')
        found_output_port_name = find_midi_port(MIDI_DEVICE_NAME, verbose=False, port_type='output') # <<< ADDED: Search output

        reconnected_input = False
        reconnected_output = False

        # --- Reconnect Input ---
        if found_input_port_name:
            try:
                self.midi_port = mido.open_input(found_input_port_name)
                self.midi_port_name = found_input_port_name
                self.midi_error_message = None
                self.is_searching = False # Stop searching once input is found
                reconnected_input = True
                print(f"\nSuccessfully Reconnected MIDI Input: '{self.midi_port_name}'")
                self.notify_status(f"MIDI Input Reconnected: '{self.midi_port_name}'")
            except (IOError, OSError) as e:
                # Failed to open even though found, keep searching
                self.midi_port = None
                self.midi_port_name = None
                self.midi_error_message = f"Found Input '{found_input_port_name}', but open failed: {e}. Retrying..."
                print(self.midi_error_message)
                # Keep is_searching = True
        # else: # No need for else, if not found, is_searching remains True

        # --- Reconnect Output (only if input reconnected successfully) ---
        # We prioritize input being available. Output is secondary.
        if reconnected_input and found_output_port_name:
             if not self.midi_output_port: # Only try if not already open
                try:
                    self.midi_output_port = mido.open_output(found_output_port_name)
                    self.midi_output_port_name = found_output_port_name
                    reconnected_output = True
                    print(f"Successfully Reconnected MIDI Output: '{self.midi_output_port_name}'")
                    self.notify_status(f"MIDI Output Reconnected: '{self.midi_output_port_name}'")
                except (IOError, OSError) as e:
                    self.midi_output_port = None
                    self.midi_output_port_name = None
                    print(f"Warning: Reconnected Input, but failed to reopen Output '{found_output_port_name}': {e}")
                    self.notify_status(f"Warning: Failed to reopen MIDI Output: {e}")
        elif reconnected_input and not found_output_port_name:
             print(f"Warning: Reconnected Input, but MIDI Output '{MIDI_DEVICE_NAME}' not found.")
             self.notify_status(f"Warning: MIDI Output '{MIDI_DEVICE_NAME}' not found.")


        if not reconnected_input:
            # If input still not found after scan interval
            self.midi_error_message = f"MIDI Input '{MIDI_DEVICE_NAME}' not found. Still searching..."
            self.notify_status(self.midi_error_message) # Update status

    # <<< --- ADDED: Missing method --- >>>
    def _start_search_mode(self):
        """Sets the application state to actively search for MIDI devices."""
        print("Starting MIDI search mode...")
        self.is_searching = True
        self.last_scan_time = 0 # Reset scan timer to allow immediate scan attempt
        self.notify_status(self.midi_error_message or "MIDI Searching...") # Update status

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
        self.running = True
        self.notify_status("Application Running")
        self.notifier.notify("READY=1")
        print("Application loop started.")

        loop_counter = 0 # Optional: Counter for loop iterations

        while self.running:
            loop_start_time = time.time() # <<< Timing Start

            current_time = time.time() # Used for button repeats and connection checks

            # --- MIDI Connection Management ---
            if self.is_searching:
                self._attempt_reconnect()
            elif self.midi_port and current_time - self.last_connection_check_time > CONNECTION_CHECK_INTERVAL_SECONDS:
                # Periodically check if the connected port still exists
                self.last_connection_check_time = current_time
                available_inputs = mido.get_input_names()
                # Also check output port if it was opened
                output_ok = True
                if self.midi_output_port:
                    available_outputs = mido.get_output_names()
                    if self.midi_output_port_name not in available_outputs:
                        output_ok = False
                        print(f"MIDI Output port '{self.midi_output_port_name}' disappeared.")

                if self.midi_port_name not in available_inputs or not output_ok:
                    reason = "Port disappeared" if self.midi_port_name not in available_inputs else "Output port disappeared"
                    self._handle_disconnection(reason=reason)
                # else: print("Connection check OK") # Debug

            # --- Process MIDI Input ---
            if self.midi_port and not self.is_searching:
                try:
                    for msg in self.midi_port.iter_pending():
                        self.handle_midi_message(msg)
                except (IOError, OSError) as e:
                    print(f"\nMIDI Read Error: {e}")
                    self._handle_disconnection(reason=f"Read Error: {e}")
                except Exception as e: # Catch other potential errors during read
                    print(f"\nUnexpected Error processing MIDI: {e}")
                    traceback.print_exc() # Log the full traceback
                    self._handle_disconnection(reason=f"Unexpected Error: {e}")

            # --- Process Pygame Events ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                # Pass event to active screen if it has a handler
                if self.active_screen and hasattr(self.active_screen, 'handle_event'):
                    self.active_screen.handle_event(event)

            # --- Handle Button Repeats ---
            self._handle_button_repeats(current_time)

            # --- Update Active Screen ---
            if self.active_screen and hasattr(self.active_screen, 'update'):
                self.active_screen.update()

            # --- Drawing ---
            self.screen.fill(BLACK)
            if self.active_screen and hasattr(self.active_screen, 'draw'):
                # Determine MIDI status string
                midi_status_str = "MIDI: Searching..." if self.is_searching else \
                                  f"MIDI In: {self.midi_port_name or 'N/A'}"
                if self.midi_output_port_name: # Add output status if available
                    midi_status_str += f" | Out: {self.midi_output_port_name}"
                elif not self.is_searching and find_midi_port(MIDI_DEVICE_NAME, verbose=False, port_type='output'):
                     midi_status_str += " | Out: Ready" # Indicate if found but not opened/reopened yet
                elif not self.is_searching:
                     midi_status_str += " | Out: N/A"

                if self.midi_error_message and self.is_searching:
                     midi_status_str = self.midi_error_message # Show specific error during search

                self.active_screen.draw(self.screen, midi_status=midi_status_str)

            pygame.display.flip()
            self.clock.tick(FPS)

        print("Application loop finished.")
        self.cleanup()

    def handle_midi_message(self, msg):
        """
        Process incoming MIDI messages.
        Handles button press/release/repeat logic for momentary buttons.
        Directly dispatches messages for non-repeatable controls (encoders/faders).
        """
        self.last_midi_message_str = str(msg)
        current_time = time.time()

        if msg.type == 'control_change':
            control = msg.control
            value = msg.value

            # Check if this CC is an encoder/fader
            if control in NON_REPEATABLE_CCS:
                # Directly dispatch non-repeatable controls (encoders, faders)
                self._dispatch_action(msg)
                return # Handled non-repeatable CC

            # Handle MOMENTARY Button Press (value == 127)
            if value == 127:
                if control not in self.pressed_buttons:
                    # print(f"Button Press Detected: CC {control} (Value: {value})") # Keep this one? Optional.
                    self.pressed_buttons[control] = {
                        'press_time': current_time,
                        'last_repeat_time': current_time,
                        'message': msg
                    }
                    self._dispatch_action(msg)
                return # Handled momentary press

            # Handle MOMENTARY Button Release (value == 0)
            elif value == 0:
                if control in self.pressed_buttons:
                    # print(f"Button Release Detected: CC {control}") # Keep this one? Optional.
                    del self.pressed_buttons[control]
                self._dispatch_action(msg)
                return # Handled momentary release

            # Handle Other CC Values
            else:
                 self._dispatch_action(msg)
                 return

        # Handle Non-CC Messages
        else:
            self._dispatch_action(msg)

    def _dispatch_action(self, msg):
        """
        Determines and executes the action associated with a MIDI message.
        This is called for initial presses and subsequent repeats.
        Prevents global screen switching if TextInputWidget is active.
        """
        # --- Check if TextInputWidget is active ---
        widget_active = False
        if (hasattr(self.active_screen, 'text_input_widget') and
                self.active_screen.text_input_widget is not None and
                self.active_screen.text_input_widget.is_active):
            widget_active = True
            # print("TextInputWidget is active, bypassing global actions for relevant CCs.") # Debug

        # --- Handle Control Change Messages ---
        if msg.type == 'control_change':
            control = msg.control
            value = msg.value # Value might be relevant for some actions

            # --- Global Actions (only if widget is NOT active) ---
            if not widget_active:
                # Check NEXT_CC (typically requires value 127)
                if control == NEXT_CC and value == 127:
                    print(f"Next screen action triggered by CC #{NEXT_CC}")
                    self.next_screen()
                    return # Screen navigation handled

                # Check PREV_CC (typically requires value 127)
                elif control == PREV_CC and value == 127:
                    print(f"Previous screen action triggered by CC #{PREV_CC}")
                    self.previous_screen()
                    return # Screen navigation handled

            # --- Pass to Active Screen (Always, unless handled by global action above) ---
            # If widget is active, NEXT/PREV CCs will fall through to here.
            # If widget is inactive, other CCs will fall through to here.
            if self.active_screen and hasattr(self.active_screen, 'handle_midi'):
                try:
                    # print(f"Passing CC {control} (Value: {value}) to screen: {self.active_screen.__class__.__name__}") # Debug
                    self.active_screen.handle_midi(msg)
                except Exception as screen_midi_err:
                     print(f"Error in screen {self.active_screen.__class__.__name__} handling MIDI {msg}: {screen_midi_err}")
                     traceback.print_exc()
            # else: print(f"No active screen or handle_midi method for CC {control}") # Debug

        # --- Handle Other Message Types (Notes, etc.) ---
        else:
            # Pass non-CC messages directly to the active screen
            if self.active_screen and hasattr(self.active_screen, 'handle_midi'):
                try:
                    # print(f"Passing non-CC message {msg} to screen: {self.active_screen.__class__.__name__}") # Debug
                    self.active_screen.handle_midi(msg)
                except Exception as screen_midi_err:
                     print(f"Error in screen {self.active_screen.__class__.__name__} handling MIDI {msg}: {screen_midi_err}")
                     traceback.print_exc()
            # else: print(f"No active screen or handle_midi method for non-CC message {msg}") # Debug

    def _handle_button_press(self, control, msg, current_time):
        """Handle the initial press of a button."""
        print(f"Button Press Detected: CC {control} (Value: {msg.value})")
        # Record the press time, initial repeat time, and the message itself
        self.pressed_buttons[control] = {
            'press_time': current_time,
            'last_repeat_time': current_time, # Set to press time initially
            'message': msg # Store the original message for repeats
        }
        # --- Trigger the INITIAL action ---
        self._dispatch_action(msg)

    def _handle_button_release(self, control):
        """Handle the release of a button."""
        print(f"Button Release Detected: CC {control}")
        # Remove the button from the tracking dictionary
        if control in self.pressed_buttons:
            del self.pressed_buttons[control]

    def _handle_button_repeats(self, current_time):
        """Check and handle button repeats based on the current time."""
        # Iterate over a copy of keys in case the dict changes during iteration
        pressed_controls = list(self.pressed_buttons.keys())
        for control in pressed_controls:
            if control not in self.pressed_buttons: continue # Check if button was released during iteration

            # --- Skip repeat for controls defined as non-repeatable ---
            if control in NON_REPEATABLE_CCS:
                # print(f"Skipping repeat for Non-Repeatable CC {control}") # Optional debug
                continue # Don't repeat faders, knobs, etc.
            # ----------------------------------------------------------

            state = self.pressed_buttons[control]
            time_held = current_time - state['press_time']

            # Check if initial delay has passed
            if time_held >= BUTTON_REPEAT_DELAY_S:
                # Check if repeat interval has passed since last repeat/press
                if (current_time - state['last_repeat_time']) >= BUTTON_REPEAT_INTERVAL_S:
                    print(f"Repeat Action for CC {control} (Msg: {state['message']})")
                    self._dispatch_action(state['message']) # Dispatch the original press message again
                    state['last_repeat_time'] = current_time # Update last repeat time

    # <<< --- ADDED: Method to send MIDI CC --- >>>
    def send_midi_cc(self, control: int, value: int, channel: int = 0):
        """Sends a MIDI Control Change message to the output port."""
        port_status = "Not Initialized"
        if self.midi_output_port:
            port_status = "Closed" if self.midi_output_port.closed else "Open"

        # --- DEBUG PRINT ---
        print(f"[MIDI Send Debug] Attempting to send CC: Ch={channel+1}, CC={control}, Val={value}. Port Status: {port_status}")
        # --- END DEBUG ---

        if self.midi_output_port and not self.midi_output_port.closed:
            try:
                msg = mido.Message('control_change', channel=channel, control=control, value=value)
                # --- DEBUG PRINT ---
                print(f"[MIDI Send Debug]   Sending message: {msg}")
                # --- END DEBUG ---
                self.midi_output_port.send(msg)
            except (IOError, OSError) as e:
                print(f"MIDI Send Error (IOError/OSError): {e}")
                self._handle_disconnection(reason=f"Send Error: {e}")
            except Exception as e:
                 print(f"MIDI Send Error (Unexpected): {e}")
        else:
            # --- DEBUG PRINT ---
            print(f"[MIDI Send Debug]   Cannot send MIDI CC - Output port not available or closed.")
            # --- END DEBUG ---
            pass # Already printed status above

    # <<< --- ADDED: Method to update LEDs initially --- >>>
    def _initial_led_update(self):
        """Send initial LED values (e.g., turn them off or set defaults)."""
        print("Sending initial LED states...")
        # Example: Turn off LEDs for all 8 knobs (CC 9-16) on Channel 16
        for i in range(8):
            knob_cc = 9 + i
            self.send_midi_cc(control=knob_cc, value=0, channel=15) # Channel 15 is MIDI channel 16
        # Optionally, call the active screen's update method if it sets LEDs
        if self.active_screen and hasattr(self.active_screen, '_update_encoder_led'):
             self.active_screen._update_encoder_led()

    def next_screen(self):
        """Switch to the next available screen."""
        if not hasattr(self, 'screens') or not self.screens: return # No screens to switch
        try:
            current_index = self.screens.index(self.active_screen)
            next_index = (current_index + 1) % len(self.screens)
            # Log the switch action itself
            print(f"Action: Switch screen {self.active_screen.__class__.__name__} -> {self.screens[next_index].__class__.__name__}")
            self.set_active_screen(self.screens[next_index])
        except (ValueError, AttributeError): # Handle if active_screen somehow not in list
             if self.screens:
                  print(f"Action: Switch screen (fallback) -> {self.screens[0].__class__.__name__}")
                  self.set_active_screen(self.screens[0])

    def previous_screen(self):
        """Switch to the previous available screen."""
        if not hasattr(self, 'screens') or not self.screens: return # No screens to switch
        try:
            current_index = self.screens.index(self.active_screen)
            prev_index = (current_index - 1) % len(self.screens) # Correctly handles negative index
            # Log the switch action itself
            print(f"Action: Switch screen {self.active_screen.__class__.__name__} -> {self.screens[prev_index].__class__.__name__}")
            self.set_active_screen(self.screens[prev_index])
        except (ValueError, AttributeError): # Handle if active_screen somehow not in list
             if self.screens:
                  print(f"Action: Switch screen (fallback) -> {self.screens[0].__class__.__name__}")
                  self.set_active_screen(self.screens[0])

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

        # Status notification includes screen name and MIDI status
        current_midi_status = self.midi_error_message or (self.midi_port_name if self.midi_port else "Searching...")
        self.notify_status(f"Screen: {self.active_screen.__class__.__name__}. MIDI: {current_midi_status}")

    def cleanup(self):
        """Clean up resources before exiting."""
        print("Cleaning up application...")
        self.notify_status("Application Shutting Down")
        # --- Save last song before exit ---
        self._save_last_song()
        
        if self.midi_port:
            try:
                self.midi_port.close()
                print("MIDI Input port closed.")
            except Exception as e:
                print(f"Error closing MIDI Input port during cleanup: {e}")
        if self.midi_output_port:
            try:
                # Optionally send message to turn off LEDs before closing
                self._initial_led_update() # Reuse to turn off LEDs
                time.sleep(0.1) # Short pause to allow message sending
                self.midi_output_port.close()
                print("MIDI Output port closed.")
            except Exception as e:
                print(f"Error closing MIDI Output port during cleanup: {e}")
        pygame.font.quit()
        pygame.quit()
        print("Pygame quit.")
        self.notifier.notify("STOPPING=1")
        print("Cleanup finished.")

    def _load_last_song(self):
        """Load the previously loaded song from persistent storage."""
        import os
        last_song_file = os.path.join(settings_module.PROJECT_ROOT, "last_song.txt")
        if os.path.exists(last_song_file):
            with open(last_song_file, "r") as f:
                last_song_basename = f.read().strip()
            if last_song_basename:
                loaded = file_io.load_song(last_song_basename)
                if loaded:
                    self.current_song = loaded
                    print(f"Loaded last song: {loaded.name}")
                    self.notify_status(f"Loaded last song: {loaded.name}")

    def _save_last_song(self):
        """Save the name of the current song to persistent storage."""
        import os
        last_song_file = os.path.join(settings_module.PROJECT_ROOT, "last_song.txt")
        if self.current_song and self.current_song.name:
            with open(last_song_file, "w") as f:
                f.write(self.current_song.name)
        elif os.path.exists(last_song_file):
            os.remove(last_song_file)


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
                app.pressed_buttons.clear() # Clear button state
            except: pass # Ignore errors during crash cleanup
        try: pygame.quit()
        except: pass
        sys.exit(1) # Exit with error code

if __name__ == '__main__':
    # Optional: Add backend selection if needed, e.g., for ALSA specific settings
    # mido.set_backend('mido.backends.rtmidi/LINUX_ALSA')
    main()
