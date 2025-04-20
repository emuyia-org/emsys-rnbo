# emsys/main.py
# -*- coding: utf-8 -*-
"""
Main entry point for the Emsys Python Application. V3 (Refactored with SongService)

Initializes Pygame, MIDI service, Song Service, Screen manager, and runs the main event loop.
Handles exit via MIDI CC 47. Includes MIDI device auto-reconnection via MidiService.
Implements universal button hold-repeat for MIDI CC messages.
"""
import pygame
import mido
import time
import sys
import os
import sdnotify
import traceback
from typing import Optional, Dict, Any, Tuple # <<< Added Tuple
import subprocess

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

# --- Refactored Imports ---
from emsys.services.midi_service import MidiService
from emsys.services.song_service import SongService # <<< ADDED SongService
from emsys.services.osc_service import OSCService # <<< ADDED OSCService
from emsys.ui.screen_manager import ScreenManager
from emsys.ui.base_screen import BaseScreen  # Import BaseScreen
from emsys.ui.playback_screen import PlaybackScreen # <<< Make sure this import exists
# --------------------------

# --- Import specific CCs and non-repeatable set ---
from emsys.config.mappings import (
    NEXT_CC, PREV_CC, NON_REPEATABLE_CCS, KNOB_A1_CC,
    PLAY_CC, STOP_CC # <<< Added transport CCs
)

# Main Application Class
class App:
    """Encapsulates the main application logic and state."""

    def __init__(self):
        """Initialize Pygame, services, and application state."""
        print("Initializing App...")

        # <<< MOVE TYPE HINTS FOR SERVICES HERE >>>
        self.osc_service: Optional[OSCService] = None
        self.screen_manager: Optional[ScreenManager] = None
        self.song_service: Optional[SongService] = None
        self.midi_service: Optional[MidiService] = None
        self.notifier: Optional[sdnotify.SystemdNotifier] = None
        # <<< END MOVE >>>

        self.notifier = sdnotify.SystemdNotifier() # Now assign the instance
        self.notify_status("Initializing Pygame...")

        pygame.init()
        pygame.font.init() # Font init needed for screens/widgets
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Emsys Controller')
        self.clock = pygame.time.Clock()
        pygame.mouse.set_visible(False) # Assume headless operation
        self.running = False

        # --- Instantiate Services ---
        # Now assign instances to the pre-declared attributes
        self.midi_service = MidiService(status_callback=self.notify_status)
        print("Instantiating SongService...")
        self.song_service = SongService(status_callback=self.notify_status)
        print("SongService instantiated.")
        print("Instantiating OSCService...")
        self.osc_service = OSCService(
            status_callback=self.notify_status,
            rnbo_outport_callback=self._handle_rnbo_outport
        )
        print("OSCService instantiated.")
        # --- Log initial song state after SongService init ---
        initial_song_name = self.song_service.get_current_song_name()
        if initial_song_name:
            print(f"SongService initially loaded: '{initial_song_name}'")
            self.notify_status(f"Initial song: {initial_song_name}")
        else:
            print("SongService did not load an initial song.")
            self.notify_status("No initial song loaded.")
        
        # --- Direct MIDI Handler Support ---
        self.direct_midi_handlers = {}

        # Pass app reference AND SongService reference to ScreenManager
        self.screen_manager = ScreenManager(app_ref=self, song_service_ref=self.song_service) # Assign instance
        # --------------------------

        # --- Application State (Remove redundant declarations) ---
        self.last_midi_message_str = None
        self.pressed_buttons: Dict[int, Dict[str, Any]] = {}

        # <<< REMOVE THESE REDUNDANT DECLARATIONS >>>
        # self.osc_service: Optional[OSCService] = None
        # self.screen_manager: Optional[ScreenManager] = None
        # self.song_service: Optional[SongService] = None
        # self.midi_service: Optional[MidiService] = None
        # self.notifier: Optional[sdnotify.SystemdNotifier] = None
        # <<< END REMOVAL >>>

        # --- Playback State ---
        self.is_playing: bool = False
        self.current_segment_index: int = 0
        self.current_repetition: int = 1 # Repetitions are 1-based
        self.current_beat_count: int = 0 # <<< USE THIS for beat count >>>
        self.stop_button_held: bool = False
        # --- RNBO Outport State ---
        self.tin_toggle_state: bool = False # <<< Changed to bool >>>
        # self.last_4n_count: int = 0 # <<< REMOVED redundant state >>>
        # self.last_transport_status: int = 0 # <<< REMOVED redundant state >>>
        # -------------------------
        self.transport_base_path = "p_obj-6"
        self.set_base_path = "p_obj-10"

        # --- Final Initialization Steps ---
        self.screen_manager.set_initial_screen() # <<< Should work now >>>
        if not self.screen_manager.get_active_screen():
             self.notify_status("FAIL: No UI screens loaded.")
             raise RuntimeError("Application cannot start without any screens.")

        self._initial_led_update() # Update LEDs based on initial screen
        self._send_initial_segment_params() # Send params for segment 0
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
            try:
                midi_messages = self.midi_service.receive_messages()
                for msg in midi_messages:
                    self.handle_midi_message(msg) # Call the updated handler
            except Exception as e:
                 print(f"\n--- Unhandled Error in MIDI receive loop ---")
                 traceback.print_exc()

            # --- Process Pygame Events ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if active_screen and hasattr(active_screen, 'handle_event'):
                    try:
                        active_screen.handle_event(event)
                    except Exception as e:
                        print(f"Error in {active_screen.__class__.__name__} handle_event: {e}")
                        traceback.print_exc()

            # --- Handle Button Repeats ---
            self._handle_button_repeats(current_time)

            # --- Update Active Screen ---
            if active_screen and hasattr(active_screen, 'update'):
                try:
                    active_screen.update()
                except Exception as e:
                    print(f"Error in {active_screen.__class__.__name__} update: {e}")
                    traceback.print_exc()


            # --- Drawing ---
            self.screen.fill(BLACK)
            if active_screen and hasattr(active_screen, 'draw'):
                try:
                    # --- Gather Status Strings ---
                    midi_status_str = self.midi_service.get_status_string()
                    osc_status_str = self.osc_service.get_status_string()
                    song_name = self.song_service.get_current_song_name() or 'None'
                    dirty_flag = "*" if self.song_service.is_current_song_dirty() else ""
                    song_status_str = f"Song: {song_name}{dirty_flag}"
                    duration_status_str = f"Duration: {self.song_service.get_current_song_duration_str()}"

                    # --- Calculate Playback Status String (only needed for PlaybackScreen) ---
                    playback_status_str = None
                    if isinstance(active_screen, PlaybackScreen): # Check if it's the PlaybackScreen
                        play_state_char = ">" if self.is_playing else "||"
                        current_song = self.song_service.get_current_song()
                        total_segments = len(current_song.segments) if current_song else 0
                        total_reps = 0
                        if current_song and 0 <= self.current_segment_index < total_segments:
                            try:
                                total_reps = current_song.segments[self.current_segment_index].repetitions
                            except IndexError:
                                total_reps = '?' # Should not happen if song data is valid

                        # <<< USE self.current_beat_count and add 1 for display >>>
                        beat_display = self.current_beat_count + 1
                        playback_status_str = f"Play: {play_state_char} Seg:{self.current_segment_index + 1}/{total_segments} Rep:{self.current_repetition}/{total_reps} Beat:{beat_display}"
                        # <<< END CHANGE >>>
                    # --- End Calculate Playback Status ---

                    # --- CONDITIONAL DRAW CALL (Looks Correct) ---
                    if isinstance(active_screen, PlaybackScreen):
                        # PlaybackScreen expects all arguments
                        # <<< ADD PRINT >>>
                        print(f"DEBUG App: Passing to PlaybackScreen: '{playback_status_str}'")
                        # <<< END PRINT >>>
                        active_screen.draw(
                            self.screen,
                            midi_status=midi_status_str,
                            song_status=song_status_str,
                            duration_status=duration_status_str,
                            playback_status=playback_status_str, # Pass playback status
                            osc_status=osc_status_str          # Pass OSC status
                        )
                    else:
                        # Other screens expect only the base arguments
                        active_screen.draw(
                            self.screen,
                            midi_status=midi_status_str,
                            song_status=song_status_str,
                            duration_status=duration_status_str
                        )
                    # --- END CONDITIONAL DRAW CALL ---

                except Exception as e:
                    print(f"Error in {active_screen.__class__.__name__} draw: {e}")
                    traceback.print_exc()
                    error_font = pygame.font.Font(None, 30)
                    error_surf = error_font.render(f"Draw Error in {active_screen.__class__.__name__}!", True, RED)
                    self.screen.blit(error_surf, (10, self.screen.get_height() // 2))


            pygame.display.flip()
            self.clock.tick(FPS)

        print("Application loop finished.")
        self.cleanup()

    def handle_midi_message(self, msg):
        """Process incoming MIDI messages."""
        # Filter by channel
        if hasattr(msg, 'channel') and msg.channel != 15: # Layer A is usually Ch 16 (index 15)
            # Allow Layer B (Ch 15 / index 14) through as well for editing? Let's assume 15 for now.
            # Revisit if X-Touch uses different channels for A/B.
            # According to xtouch_midi_ref.txt, both layers seem to use the same channel.
            # Let's filter for channel 15 (MIDI channel 16) for now.
            # print(f"Ignoring MIDI message on channel {msg.channel + 1}")
            return

        self.last_midi_message_str = str(msg)
        current_time = time.time()

        # NEW: Check for direct handlers first
        if msg.type == 'control_change' and msg.control in self.direct_midi_handlers:
            try:
                # Call the direct handler and return immediately
                self.direct_midi_handlers[msg.control](msg)
                return
            except Exception as e:
                print(f"[App] Error in direct handler for CC {msg.control}: {e}")
                traceback.print_exc()

        # Continue with regular handling...
        if msg.type == 'control_change':
            control = msg.control
            value = msg.value
            # print(f"Received CC: control={control}, value={value}, channel={msg.channel}") # Debugging

            # --- Handle Transport Controls ---
            if control == PLAY_CC:
                if value == 127: # Button Press
                    print(f"DEBUG: PLAY_CC ({PLAY_CC}) pressed (value={value})")
                    if self.stop_button_held:
                        print("DEBUG: STOP was held, triggering PRIME")
                        param_name = "p_obj-6/transport/Transport.Prime"
                        # <<< CHANGE VALUE TO INT 1 >>>
                        param_value = 1
                        print(f"DEBUG: Sending OSC: {param_name} = {param_value}")
                        self.osc_service.send_rnbo_param(param_name, param_value)
                        # Reset state after prime
                        self.is_playing = False
                        self.current_segment_index = 0
                        self.current_repetition = 1
                        self._send_segment_params(self.current_segment_index) # Send params for segment 0
                        self.update_combined_status()
                    else:
                        print("DEBUG: Triggering CONTINUE")
                        param_name = "p_obj-6/transport/Transport.Continue"
                        # <<< CHANGE VALUE TO INT 1 >>>
                        param_value = 1
                        print(f"DEBUG: Sending OSC: {param_name} = {param_value}")
                        self.osc_service.send_rnbo_param(param_name, param_value)
                        # self.is_playing = True # State is set via OSC feedback
                        self.update_combined_status()
                    # Play doesn't usually repeat, clear from pressed state immediately?
                    if control in self.pressed_buttons: del self.pressed_buttons[control]
                elif value == 0: # Button Release
                    print(f"DEBUG: PLAY_CC ({PLAY_CC}) released (value={value})")
                return # Handled

            elif control == STOP_CC:
                if value == 127: # Button Press
                    print("STOP pressed")
                    param_name = "p_obj-6/transport/Transport.Stop"
                    # <<< CHANGE VALUE TO INT 1 >>>
                    param_value = 1
                    print(f"DEBUG: Sending OSC: {param_name} = {param_value}")
                    self.osc_service.send_rnbo_param(param_name, param_value)
                    self.stop_button_held = True
                    # self.is_playing = False # Set based on Transport.Status feedback
                    self.update_combined_status()
                    # Add to pressed buttons for hold detection, but don't repeat STOP command itself
                    if control not in self.pressed_buttons:
                         self.pressed_buttons[control] = {'press_time': current_time, 'last_repeat_time': current_time, 'message': msg}
                elif value == 0: # Button Release
                     print("STOP released")
                     self.stop_button_held = False
                     if control in self.pressed_buttons: del self.pressed_buttons[control]
                return # Handled

            # --- Handle Specific Controls (e.g., Knobs) FIRST ---
            if control == KNOB_A1_CC:
                # Define the full OSC path for the parameter
                rnbo_param_path = "p_obj-6/tempo/Transport.Tempo"

                # Send the raw MIDI value (0-127) using send_rnbo_param
                # Assuming the RNBO parameter handles this range or normalization internally
                self.osc_service.send_rnbo_param(rnbo_param_path, value)

                # Optionally, dispatch to screen as well if needed for UI feedback
                # self._dispatch_action(msg)
                return # Handled

            # --- Handle Button Release (value == 0) ---
            if value == 0:
                if control in self.pressed_buttons:
                    # Check if it was the STOP button release, already handled above
                    if control != STOP_CC:
                        del self.pressed_buttons[control]
                # Dispatch release messages so screens can react (e.g., update held state)
                self._dispatch_action(msg)
                return # Stop processing here for releases

            # --- Handle Button Press (value == 127) ---
            elif value == 127:
                # Check if it was PLAY/STOP press, already handled above
                if control in [PLAY_CC, STOP_CC]:
                    return # Already handled

                # If it's a non-repeatable button, dispatch immediately and stop
                if control in NON_REPEATABLE_CCS:
                    self._dispatch_action(msg)
                    return

                # Otherwise, handle as a potentially repeating button press
                if control not in self.pressed_buttons:
                    self.pressed_buttons[control] = {
                        'press_time': current_time,
                        'last_repeat_time': current_time, # Set initial repeat time for delay calc
                        'message': msg
                    }
                    # Dispatch the initial press action
                    self._dispatch_action(msg)
                # If already pressed (e.g., duplicate MIDI message), do nothing here, repeat logic handles it
                return # Stop processing here for button presses (127)

            # --- Handle ALL OTHER CC Values (Encoders, Faders, etc.) ---
            else:
                self._dispatch_action(msg)
                return # Stop processing here after dispatching

        # --- Handle Non-CC Messages (Notes, Program Changes, etc.) ---
        else:
            self._dispatch_action(msg)
            # No return needed here as it's the end of the function

    def _dispatch_action(self, msg):
        """
        Determines and executes the action associated with a MIDI message.
        Handles global actions (screen switching) or passes to the active screen.
        Prevents global screen switching if an input widget is active on the screen.
        """

        active_screen = self.screen_manager.get_active_screen()

        # Check for active input widgets (e.g., text input)
        widget_active = False
        if active_screen:
            # Example check - adapt if your widget attribute names differ
            text_input_widget = getattr(active_screen, 'text_input_widget', None)
            if text_input_widget and getattr(text_input_widget, 'is_active', False):
                 widget_active = True
                 # print("[Dispatch] Text input widget is active, blocking global actions.") # Debug

        # --- Handle Global Actions (Screen Switching) ---
        # Only check for global actions on specific CCs and *only* if a widget isn't active
        # Crucially, check the value is 127 for button presses to trigger screen changes
        if not widget_active and msg.type == 'control_change' and msg.value == 127:
            control = msg.control
            if control == NEXT_CC:
                print(f"Requesting next screen (via CC #{NEXT_CC})")
                self.screen_manager.request_next_screen()
                self.update_combined_status() # Update status after screen change request
                return # Handled globally, don't pass to screen
            elif control == PREV_CC:
                print(f"Requesting previous screen (via CC #{PREV_CC})")
                self.screen_manager.request_previous_screen()
                self.update_combined_status() # Update status after screen change request
                return # Handled globally, don't pass to screen

        # --- Pass Message to Active Screen ---
        # If it wasn't a handled global action, pass it to the screen's handler
        if active_screen and hasattr(active_screen, 'handle_midi'):
            try:
                active_screen.handle_midi(msg)
            except Exception as screen_midi_err:
                 print(f"Error in screen {active_screen.__class__.__name__} handling MIDI {msg}: {screen_midi_err}")
                 traceback.print_exc()

    def _handle_button_repeats(self, current_time):
        """Check and handle button repeats based on the current time."""
        pressed_controls = list(self.pressed_buttons.keys())
        for control in pressed_controls:
            if control not in self.pressed_buttons: continue

            if control in NON_REPEATABLE_CCS:
                continue

            state = self.pressed_buttons[control]
            time_held = current_time - state['press_time']

            if time_held >= BUTTON_REPEAT_DELAY_S:
                if (current_time - state['last_repeat_time']) >= BUTTON_REPEAT_INTERVAL_S:
                    self._dispatch_action(state['message'])
                    state['last_repeat_time'] = current_time


    def _initial_led_update(self):
        """Send initial LED values via MidiService, potentially based on active screen."""
        print("Sending initial LED states...")
        for i in range(8): # Example: Knobs B1-B8 LEDs CC 9-16 (Verify mapping!)
             knob_led_cc = 9 + i
             self.send_midi_cc(control=knob_led_cc, value=0)

        active_screen = self.screen_manager.get_active_screen()
        # Delegate LED updates to screens or their helpers
        if active_screen and hasattr(active_screen, '_update_leds'):
            if callable(getattr(active_screen, '_update_leds')):
                 print(f"Calling initial LED update for {active_screen.__class__.__name__}")
                 try:
                     active_screen._update_leds()
                 except Exception as e:
                      print(f"Error calling _update_leds on {active_screen.__class__.__name__}: {e}")


    # --- Methods for Screens to Interact with App/Services ---
    def send_midi_cc(self, control: int, value: int, channel: int = 15):
        """Allows screens to send MIDI CC messages via the MidiService."""
        self.midi_service.send_cc(control, value, channel)

    def request_screen_change(self):
        """Signals ScreenManager that a blocked change can proceed."""
        self.screen_manager.request_screen_change_approved()

    def set_active_screen(self, screen_instance: BaseScreen):
        """Allows direct screen setting request to ScreenManager."""
        print(f"Direct request to set active screen to {screen_instance.__class__.__name__}")
        self.screen_manager.pending_screen_change = screen_instance # Handled by main loop

    # --- OSC Callback Handler ---
    def _handle_rnbo_outport(self, outport_name: str, value: Any):
        """Callback function passed to OSCService to handle incoming messages."""
        # print(f"App received OSC: {outport_name} = {value}") # Debug
        current_song = self.song_service.get_current_song()
        if not current_song: return # No song loaded, nothing to do

        if outport_name == "Transport.LoadNowBeat":
            # This is a bang (value is usually 1 or similar)
            # Triggered just before the start of the *next* loop/repetition
            print(f"Received LoadNowBeat (Value: {value}) - Current Seg: {self.current_segment_index+1}, Rep: {self.current_repetition}")
            self._process_segment_transition()

        elif outport_name == "Tin.Toggle":
             try:
                 # <<< Update boolean state >>>
                 self.tin_toggle_state = bool(int(value))
                 print(f"Tin.Toggle state changed: {'ON' if self.tin_toggle_state else 'OFF'}")
             except (ValueError, TypeError):
                 print(f"Warning: Could not parse Tin.Toggle value: {value}")

        elif outport_name == "Transport.Status":
            try:
                new_is_playing = (int(value) == 1)
                if new_is_playing != self.is_playing:
                    self.is_playing = new_is_playing # <<< Update primary state >>>
                    print(f"Transport Status changed: {'Playing' if self.is_playing else 'Stopped'}")
                    if not self.is_playing:
                        # Reset counters if stopping (unless Prime logic handles it)
                        self._reset_playback_state() # Reset reps/beats on stop
                        pass
                    self.update_combined_status() # Update status display
                    self._update_transport_leds() # Update LEDs based on new state
            except (ValueError, TypeError):
                 print(f"Warning: Could not parse Transport.Status value: {value}")


        # <<< Beat Count Handling (Looks Correct) >>>
        elif outport_name == "Transport.4nCount":
            try:
                new_beat_count = int(value)
                # <<< ADD CHECK AND PRINT >>>
                if new_beat_count != self.current_beat_count:
                    print(f"DEBUG App: Received Transport.4nCount = {new_beat_count}") # Log reception
                    self.current_beat_count = new_beat_count
                # <<< END CHECK AND PRINT >>>
            except (ValueError, TypeError):
                print(f"Warning: Could not parse beat count value: {value}")
        # <<< END Beat Count Handling >>>

        # Add handlers for other outports like Tempo, PGM changes if needed
        # elif outport_name == "Set.PGM1":
        #     print(f"RNBO reported PGM1 change: {value}") # Example
        # elif outport_name == "Transport.Tempo":
        #     print(f"RNBO reported Tempo change: {value}") # Example

    # --- Playback Logic ---
    def _process_segment_transition(self):
        """Handles logic when LoadNowBeat is received."""
        current_song = self.song_service.get_current_song()
        if not current_song or not current_song.segments:
            print("LoadNowBeat ignored: No song or segments loaded.")
            return

        num_segments = len(current_song.segments)
        if not (0 <= self.current_segment_index < num_segments):
            print(f"LoadNowBeat ignored: Invalid segment index {self.current_segment_index}")
            self.current_segment_index = 0 # Reset index
            self.current_repetition = 1
            return

        current_segment = current_song.segments[self.current_segment_index]
        total_repetitions = current_segment.repetitions

        # Check if the repetition that just *finished* was the last one
        is_last_repetition = (self.current_repetition >= total_repetitions)

        next_segment_index = self.current_segment_index
        next_repetition = self.current_repetition + 1

        if is_last_repetition:
            print(f"Segment {self.current_segment_index + 1} finished.")
            # --- Check for Auto Stop ---
            if current_segment.automatic_transport_interrupt:
                print(f"Auto-stopping transport after segment {self.current_segment_index + 1}.")
                self.osc_service.send_rnbo_param("p_obj-6/transport/Transport.Stop", 1)
                # Don't advance segment index or send PGM, transport is stopping.
                # State will be updated via Transport.Status message.
                return # Stop processing here

            # --- Advance to Next Segment ---
            next_segment_index = (self.current_segment_index + 1) % num_segments
            next_repetition = 1 # Reset repetition count for the new segment
            print(f"Advancing to segment {next_segment_index + 1}")

            # --- Send PGM messages for the NEXT segment IF Tin.Toggle is ON ---
            if self.tin_toggle_state == 1:
                next_segment = current_song.segments[next_segment_index]
                print(f"Tin.Toggle is ON. Sending PGM messages for segment {next_segment_index + 1}: PGM1={next_segment.program_message_1}, PGM2={next_segment.program_message_2}")
                self.osc_service.send_rnbo_param("p_obj-10/Set.PGM1", next_segment.program_message_1)
                self.osc_service.send_rnbo_param("p_obj-10/Set.PGM2", next_segment.program_message_2)
            else:
                print("Tin.Toggle is OFF. Skipping PGM messages.")

            # --- Update State AFTER processing the finished segment ---
            self.current_segment_index = next_segment_index
            self.current_repetition = next_repetition

            # --- Send Parameters for the NEW Current Segment ---
            self._send_segment_params(self.current_segment_index)

        else:
            # --- Still within the same segment, just increment repetition ---
            self.current_repetition = next_repetition
            print(f"Starting repetition {self.current_repetition}/{total_repetitions} of segment {self.current_segment_index + 1}")
            # No need to send PGM or segment params again

        self.update_combined_status() # Update status display

    def _send_segment_params(self, segment_index: int):
        """Sends the Tempo, Loop Length, and Repetitions for the given segment index to RNBO."""
        current_song = self.song_service.get_current_song()
        if not current_song or not current_song.segments: return
        num_segments = len(current_song.segments)
        if not (0 <= segment_index < num_segments):
            print(f"Error sending params: Invalid segment index {segment_index}")
            return

        segment = current_song.segments[segment_index]
        print(f"Sending params for segment {segment_index + 1}: Tempo={segment.tempo}, Loop={segment.loop_length}, Reps={segment.repetitions}")

        # Tempo path is correct: p_obj-6/tempo/Transport.Tempo
        self.osc_service.send_rnbo_param("p_obj-6/tempo/Transport.Tempo", float(segment.tempo))

        # PGM paths are correct: p_obj-10/Set.PGM1, p_obj-10/Set.PGM2
        print(f"Sending initial PGM for segment {segment_index + 1}: PGM1={segment.program_message_1}, PGM2={segment.program_message_2}")
        self.osc_service.send_rnbo_param("p_obj-10/Set.PGM1", segment.program_message_1)
        self.osc_service.send_rnbo_param("p_obj-10/Set.PGM2", segment.program_message_2)

    def _send_initial_segment_params(self):
        """Sends parameters for the very first segment when the app starts."""
        self._send_segment_params(0)

    # --- Status Update ---
    def update_combined_status(self):
        """Updates the systemd status with screen, MIDI, OSC, and Song info."""
        screen_name = "No Screen"
        active_screen = self.screen_manager.get_active_screen()
        if active_screen:
            screen_name = active_screen.__class__.__name__
        midi_status = self.midi_service.get_status_string()
        osc_status = self.osc_service.get_status_string()
        song_name = self.song_service.get_current_song_name() or 'None'
        dirty_flag = "*" if self.song_service.is_current_song_dirty() else ""
        song_status = f"Song: {song_name}{dirty_flag}"
        # duration_str = self.song_service.get_current_song_duration_str() # Duration not needed for systemd status

        # Combine for systemd status (Removed playback_status)
        combined_status = f"{screen_name} | {midi_status} | {osc_status} | {song_status}"
        self.notify_status(combined_status)


    def cleanup(self):
        """Clean up resources before exiting."""
        print("Cleaning up application...")
        self.notify_status("Application Shutting Down")

        # Stop transport before quitting
        if self.osc_service and self.osc_service.client:
            print("Sending STOP command to RNBO...")
            # <<< CHANGE VALUE TO INT 1 >>>
            self.osc_service.send_rnbo_param("p_obj-6/transport/Transport.Stop", 1)
            time.sleep(0.1) # Give OSC message time to send

        # Check for unsaved changes via SongService
        if self.song_service.is_current_song_dirty():
            print("Warning: Exiting with unsaved changes.")
            # For a service, typically save automatically or just exit.
            # self.song_service.save_current_song() # Or just let it be lost

        # Save the last song preference (handled by SongService internally now)
        # self.song_service._save_last_song_preference(self.song_service.get_current_song_name())

        # Cleanup active screen
        self.screen_manager.cleanup_active_screen()

        # Cleanup MIDI service
        self._initial_led_update() # Re-use to turn off LEDs
        time.sleep(0.1)
        self.midi_service.close_ports()

        # Cleanup OSC service # <<< ENSURE THIS IS CALLED >>>
        if self.osc_service:
            self.osc_service.stop()

        # Quit Pygame
        pygame.font.quit()
        pygame.quit()
        print("Pygame quit.")
        self.notifier.notify("STOPPING=1")
        print("Cleanup finished.")

    # --- System Control Methods ---
    def trigger_shutdown(self):
        """Perform cleanup and initiate system shutdown."""
        print("Shutdown requested. Cleaning up...")
        self.notify_status("System Shutting Down...")
        self.cleanup() # Perform application cleanup first
        print("Cleanup complete. Initiating system shutdown.")
        # NOTE: This requires the script to run with sudo or have passwordless sudo configured for shutdown
        try:
            subprocess.run(['sudo', 'shutdown', 'now'], check=True)
        except Exception as e:
            print(f"Failed to execute shutdown command: {e}")
            self.notify_status(f"Shutdown failed: {e}")
        # If shutdown fails, we might want to exit the app anyway or handle it differently
        self.running = False # Ensure the app loop stops if shutdown fails

    def trigger_reboot(self):
        """Perform cleanup and initiate system reboot."""
        print("Reboot requested. Cleaning up...")
        self.notify_status("System Rebooting...")
        self.cleanup() # Perform application cleanup first
        print("Cleanup complete. Initiating system reboot.")
        # NOTE: This requires the script to run with sudo or have passwordless sudo configured for reboot
        try:
            subprocess.run(['sudo', 'reboot'], check=True)
        except Exception as e:
            print(f"Failed to execute reboot command: {e}")
            self.notify_status(f"Reboot failed: {e}")
        # If reboot fails, we might want to exit the app anyway or handle it differently
        self.running = False # Ensure the app loop stops if reboot fails

    def trigger_service_stop(self):
        """Initiate systemd service stop for emsys-python and rnbooscquery-emsys."""
        print("Service stop requested for emsys-python and rnbooscquery-emsys.")
        self.notify_status("Stopping services...")
        # NOTE: This requires the script user (pi) to have passwordless sudo configured for systemctl
        try:
            # Stop both services
            subprocess.run(['sudo', 'systemctl', 'stop', 'rnbooscquery-emsys.service', 'emsys-python.service'], check=True)
            # If the command succeeds, this process will likely be terminated before the next line.
            self.running = False
        except Exception as e:
            print(f"Failed to execute service stop command: {e}")
            self.notify_status(f"Service stop failed: {e}")
            # If stop fails, the app continues running.

    def trigger_service_restart(self):
        """Initiate systemd service restart for emsys-python and rnbooscquery-emsys."""
        print("Service restart requested for emsys-python and rnbooscquery-emsys.")
        self.notify_status("Restarting services...")
        # NOTE: This requires the script user (pi) to have passwordless sudo configured for systemctl
        try:
            # Restart both services
            subprocess.run(['sudo', 'systemctl', 'restart', 'emsys-python.service', 'rnbooscquery-emsys.service'], check=True)
            # If the command succeeds, this process will likely be terminated before the next line.
            self.running = False
        except Exception as e:
            print(f"Failed to execute service restart command: {e}")
            self.notify_status(f"Service restart failed: {e}")
            # If restart fails, the app continues running.

    def _reset_playback_state(self, reset_segment: bool = False):
        """Resets repetition and beat counters. Optionally resets segment index."""
        print("Resetting playback state...")
        if reset_segment:
            self.current_segment_index = 0
        self.current_repetition = 1
        self.current_beat_count = 0 # <<< RESET Beat Count >>>


# Script Entry Point
def main():
    """Main function."""
    app = None
    try:
        app = App()
        app.run()
        sys.exit(0)
    except KeyboardInterrupt:
         print("\nCtrl+C detected. Exiting gracefully.")
         if app: app.cleanup()
         sys.exit(0)
    except RuntimeError as e:
        print(f"Application initialization failed: {e}")
        try:
            if app and app.midi_service: app.midi_service.close_ports()
            if app and app.notifier:
                 app.notifier.notify("STATUS=Initialization Failed. Exiting.")
                 app.notifier.notify("STOPPING=1")
            pygame.quit()
        except: pass
        sys.exit(1)
    except Exception as e:
        print(f"\n--- An unhandled error occurred in main ---")
        traceback.print_exc()
        try:
            n = sdnotify.SystemdNotifier()
            n.notify("STATUS=Crashed unexpectedly.")
            n.notify("STOPPING=1")
        except Exception as sd_err:
            print(f"(Could not notify systemd: {sd_err})")
        if app: app.cleanup()
        else:
             try: pygame.quit()
             except: pass
        sys.exit(1)

if __name__ == '__main__':
    main()
