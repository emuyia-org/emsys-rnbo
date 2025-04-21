# emsys/main.py
# -*- coding: utf-8 -*-
"""
Main entry point for the Emsys Python Application. V3 (Refactored with SongService)

Initializes Pygame, MIDI service, Song Service, Screen manager, and runs the main event loop.
Handles exit via MIDI CC 47. Includes MIDI device auto-reconnection via MidiService.
Implements universal button hold-repeat for MIDI CC messages.
"""
import pygame
import sys
import os
import time
import traceback
import sdnotify
import subprocess
import logging # <<< ADD logging import
from typing import Optional, Dict, Any, Tuple

# --- Configure Logging Early --- <<< ADD THIS BLOCK
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Optional: Get logger for main.py itself
# --- End Logging Config ---

# Add the project root directory to the path
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
# from emsys.ui.playback_screen import PlaybackScreen # <<< REMOVE PlaybackScreen import
# --------------------------
from emsys.core.song import MIN_TEMPO, MAX_TEMPO # <<< ADD THIS IMPORT

# --- Import specific CCs and non-repeatable set ---
from emsys.config.mappings import (
    NEXT_CC, PREV_CC, NON_REPEATABLE_CCS, KNOB_A1_CC,
    PLAY_CC, STOP_CC # <<< Added transport CCs
)

# --- Import the utility functions ---
from emsys.utils.system import start_rnbo_service_if_needed, stop_rnbo_service # <<< Import stop function

# Main Application Class
class App:
    """Encapsulates the main application logic and state."""

    def __init__(self):
        """Initialize Pygame, services, and application state."""
        print("Initializing App...")
        logger.info("App initialization started.")

        # <<< MOVE TYPE HINTS FOR SERVICES HERE >>>
        self.osc_service: Optional[OSCService] = None
        self.screen_manager: Optional[ScreenManager] = None
        self.song_service: Optional[SongService] = None
        self.midi_service: Optional[MidiService] = None
        self.notifier: Optional[sdnotify.SystemdNotifier] = None
        # <<< END MOVE >>>

        # Add this for status notification rate limiting
        self.last_status_notification_time = 0
        self.status_notification_interval = 2.0  # seconds between status updates
        self.last_status_message = ""

        self.notifier = sdnotify.SystemdNotifier() # Now assign the instance
        self.notify_status("Initializing Pygame...")
        logger.info("Initializing Pygame...")
        pygame.init()
        pygame.font.init() # Font init needed for screens/widgets
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Emsys Controller')
        self.clock = pygame.time.Clock()
        pygame.mouse.set_visible(False) # Assume headless operation
        self.running = False

        # --- Instantiate Services ---
        self.notify_status("Initializing MIDI Service...")
        logger.info("Initializing MIDI Service...")
        self.midi_service = MidiService(status_callback=self.notify_status)
        logger.info("MidiService instantiated.")
        print("MidiService instantiated.")

        # --- Attempt to start RNBO service (if running directly) --- <<< MOVED BLOCK >>>
        # This now happens *after* MidiService is initialized.
        # The function checks if it's running under systemd and skips if so.
        self.notify_status("Checking/Starting RNBO Service (if run directly)...")
        logger.info("Checking/Starting RNBO Service (if run directly)...")
        start_rnbo_service_if_needed() # <<< MOVED HERE
        # --- End RNBO service start attempt ---

        self.notify_status("Initializing Song Service...")
        logger.info("Initializing Song Service...")
        print("Instantiating SongService...")
        self.song_service = SongService(status_callback=self.notify_status)
        logger.info("SongService instantiated.")
        print("SongService instantiated.")

        self.notify_status("Initializing OSC Service...")
        logger.info("Initializing OSC Service...")
        print("Instantiating OSCService...")
        self.osc_service = OSCService(
            status_callback=self.notify_status,
            rnbo_outport_callback=self._handle_rnbo_outport
        )
        logger.info("OSCService instantiated.")
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
        self.notify_status("Initializing Screen Manager...") # <<< Added status
        self.screen_manager = ScreenManager(app_ref=self, song_service_ref=self.song_service) # Assign instance
        print("ScreenManager instantiated.") # <<< Added print
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
        self.current_repetition: int = 1
        self.current_beat_count: int = 0
        self.stop_button_held: bool = False
        # Track current tempo for endless encoder
        self.current_tempo: float = 120.0  # will be synced from RNBO outport
        self.next_segment_prepared: bool = False
        self.prime_action_occurred: bool = False # <<< ADD THIS LINE
        self.is_initial_cycle_after_play: bool = True # <<< ADD THIS FLAG >>>

        # --- Flags for Segment Transition ---
        self.next_segment_prepared: bool = False
        self.prepared_next_segment_index: Optional[int] = None
        # --- End Flags ---

        # --- RNBO Outport State ---
        self.tin_toggle_state: bool = False # <<< Changed to bool >>>
        # self.last_4n_count: int = 0 # <<< REMOVED redundant state >>>
        # self.last_transport_status: int = 0 # <<< REMOVED redundant state >>>
        # -------------------------
        self.transport_base_path = "p_obj-6"
        self.set_base_path = "p_obj-10"

        # --- Final Initialization Steps ---
        self.notify_status("Setting initial screen...") # <<< Added status
        self.screen_manager.set_initial_screen() # <<< Should work now >>>
        if not self.screen_manager.get_active_screen():
             self.notify_status("FAIL: No UI screens loaded.")
             raise RuntimeError("Application cannot start without any screens.")

        self.notify_status("Updating initial LEDs...") # <<< Added status
        self._initial_led_update() # Update LEDs based on initial screen
        self.notify_status("Sending initial segment params...") # <<< Added status
        self._send_initial_segment_params()  # sends initial tempo
        # initialize from first segment if available
        song0 = self.song_service.get_current_song()
        if song0 and song0.segments:
            self.current_tempo = song0.segments[0].tempo

        print("App initialization complete.")
        logger.info("App initialization complete.") # <<< Added logging
        self.notify_status("Initialization Complete")


    def notify_status(self, status_message):
        """Helper function to print status and notify systemd with rate limiting."""
        current_time = time.time()
        
        # Always print to console for debugging (optional)
        if self.last_status_message != status_message:
            print(f"Status: {status_message}")
            self.last_status_message = status_message
        
        # Only send to systemd if enough time has passed since last notification
        if current_time - self.last_status_notification_time >= self.status_notification_interval:
            max_len = 80  # Limit systemd status length
            truncated_message = status_message[:max_len] + '...' if len(status_message) > max_len else status_message
            
            try:
                self.notifier.notify(f"STATUS={truncated_message}")
                self.last_status_notification_time = current_time
            except Exception as e:
                print(f"Could not notify systemd: {e}")

    def run(self):
        """Main application loop."""
        self.running = True
        self.notify_status("Application Running") # Initial running status
        logger.info("Application loop starting.")
        # self.update_combined_status() # <<< Moved initial call inside loop
        # --- Signal READY *after* all init but *before* entering the loop ---
        logger.info("Signalling systemd: READY=1")
        self.notifier.notify("READY=1")
        # --- End Signal ---
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
                    self.handle_midi_message(msg) # <<< Ensure messages are handled
            except Exception as e:
                 print(f"\n--- Unhandled Error in MIDI receive loop ---")
                 traceback.print_exc()
                 # Potentially add a short sleep to prevent tight loop on error
                 time.sleep(0.01)


            # --- Process Pygame Events ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False # <<< Set running to False
                # Pass event to active screen if it has a handler
                if active_screen and hasattr(active_screen, 'handle_event'):
                    try:
                        active_screen.handle_event(event)
                    except Exception as e:
                        print(f"Error in screen {active_screen.__class__.__name__} handling event {event}: {e}")
                        traceback.print_exc()


            # --- Handle Button Repeats ---
            self._handle_button_repeats(current_time)

            # --- Update Active Screen ---
            if active_screen and hasattr(active_screen, 'update'):
                try:
                    active_screen.update() # <<< Call update method
                except Exception as e:
                    print(f"Error in screen {active_screen.__class__.__name__} update: {e}")
                    traceback.print_exc()


            # --- Prepare Status Strings ---
            # <<< Moved status preparation before drawing >>>
            midi_status = self.midi_service.get_status_string()
            osc_status = self.osc_service.get_status_string()
            song_name = self.song_service.get_current_song_name() or 'None'
            dirty_flag = "*" if self.song_service.is_current_song_dirty() else ""
            song_status = f"Song: {song_name}{dirty_flag}"
            duration_str = self.song_service.get_current_song_duration_str() # Calculate duration if needed by screen

            # <<< Get detailed playback status components >>>
            playback_components = self._get_playback_status_components()

            # <<< Update combined systemd status >>>
            # This call updates the systemd status, but doesn't print to console itself
            self.update_combined_status(playback_components)

            # --- Drawing ---
            self.screen.fill(BLACK)
            if active_screen and hasattr(active_screen, 'draw'):
                try:
                    # <<< Pass detailed playback components to draw >>>
                    active_screen.draw(
                        screen_surface=self.screen,
                        midi_status=midi_status,
                        song_status=song_status,
                        duration_status=duration_str, # Pass duration if needed
                        osc_status=osc_status,
                        # Pass individual playback components
                        play_symbol=playback_components['play_symbol'],
                        seg_text=playback_components['seg_text'],
                        rep_text=playback_components['rep_text'],
                        beat_text=playback_components['beat_text'],
                        tempo_text=playback_components['tempo_text'],
                        current_playing_segment_index=playback_components['current_playing_segment_index']
                    )

                except Exception as e:
                    print(f"Error during screen {active_screen.__class__.__name__} draw: {e}")
                    traceback.print_exc()


            pygame.display.flip()
            self.clock.tick(FPS)

        logger.info("Application loop finished.")
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
            cc = control # Added for clarity
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
                        # self.is_playing = False # <<< REMOVED: Let OSC feedback handle play state >>>
                        # self.current_segment_index = 0 # <<< REMOVED: Don't reset segment >>>
                        # self.current_repetition = 1 # <<< REMOVED: Don't reset repetition >>>
                        self.current_beat_count = 0 # <<< ADDED: Reset only beat count >>>
                        self.prime_action_occurred = True
                        # self._send_segment_params(self.current_segment_index) # <<< REMOVED: Don't resend params >>>
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
                # endless encoder: adjust BPM step=1
                direction = 0
                if 1 <= value <= 63:   direction = 1
                elif 65 <= value <= 127: direction = -1
                if direction != 0:
                    new_tempo = self.current_tempo + direction * 1.0
                    # clamp to valid range
                    new_tempo = max(MIN_TEMPO, min(MAX_TEMPO, new_tempo))
                    self.current_tempo = new_tempo
                    self.osc_service.send_rnbo_param("p_obj-6/tempo/Transport.Tempo", new_tempo)
                return  # Handled

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
                        'last_repeat_time': current_time, # Initialize last repeat time
                        'message': msg # Store the original message
                    }
                self._dispatch_action(msg) # Dispatch press action immediately
            elif value == 0: # Button Release
                if cc in self.pressed_buttons:
                    del self.pressed_buttons[cc] # Remove from repeat tracking
                # Optionally dispatch release action if needed (currently not used)
                # self._dispatch_action(msg)
            else: # Handle other CC values (like faders, non-repeating knobs)
                 self._dispatch_action(msg)

        else:
            # Handle non-CC messages if necessary
            # print(f"Received non-CC MIDI: {msg}")
            pass # Pass other message types if needed by screens


    def _dispatch_action(self, msg):
        """
        Determines and executes the action associated with a MIDI message.
        Handles global actions (screen switching) or passes to the active screen.
        Prevents global screen switching if an input widget is active on the screen.
        """

        active_screen = self.screen_manager.get_active_screen()

        # --- Check if a UI widget (like text input) is currently active ---
        widget_active = False
        if active_screen:
            # Check for a text input widget specifically
            text_input_widget = getattr(active_screen, 'text_input_widget', None)
            if text_input_widget and getattr(text_input_widget, 'is_active', False):
                 widget_active = True
                 # print("[Dispatch] Text input widget is active, blocking global actions.") # Debug

        # --- Handle Global Actions (like screen switching) ---
        # Only process global actions if NO widget is active AND it's a button press (value 127)
        if not widget_active and msg.type == 'control_change' and msg.value == 127:
            control = msg.control
            if control == NEXT_CC:
                print(f"Requesting next screen (via CC #{NEXT_CC})")
                self.screen_manager.request_next_screen()
                self.update_combined_status() # Update status after screen change request
                return # Action handled globally, stop processing here
            elif control == PREV_CC:
                print(f"Requesting previous screen (via CC #{PREV_CC})")
                self.screen_manager.request_previous_screen()
                self.update_combined_status() # Update status after screen change request
                return # Action handled globally, stop processing here

        # --- Pass Message to Active Screen's Handler ---
        # If the message wasn't handled as a global action, let the active screen process it.
        if active_screen and hasattr(active_screen, 'handle_midi'):
            try:
                active_screen.handle_midi(msg)
            except Exception as screen_midi_err:
                 print(f"Error in screen {active_screen.__class__.__name__} handling MIDI {msg}: {screen_midi_err}")
                 traceback.print_exc()

    def _handle_button_repeats(self, current_time):
        """Check and handle button repeats based on the current time."""
        # Iterate safely over a copy of keys in case the dictionary changes
        pressed_controls = list(self.pressed_buttons.keys())
        for control in pressed_controls:
            # Re-check if the button is still considered pressed
            if control not in self.pressed_buttons:
                continue

            # Skip controls marked as non-repeatable (like knobs/faders)
            if control in NON_REPEATABLE_CCS:
                continue

            state = self.pressed_buttons[control]
            time_held = current_time - state['press_time']

            # Check if the initial delay has passed
            if time_held >= BUTTON_REPEAT_DELAY_S:
                # Check if the repeat interval has passed since the last repeat (or initial press)
                if (current_time - state['last_repeat_time']) >= BUTTON_REPEAT_INTERVAL_S:
                    print(f"Repeating action for CC {control}") # Debug
                    # Dispatch the original press message again
                    self._dispatch_action(state['message'])
                    # Update the last repeat time
                    state['last_repeat_time'] = current_time

    def _clear_preparation_flags(self):
        """Resets the flags used for segment transition."""
        self.next_segment_prepared = False
        self.prepared_next_segment_index = None

    # ...rest of the App class...

    def _initial_led_update(self):
        """Send initial LED values via MidiService, potentially based on active screen."""
        print("Sending initial LED states...")
        for i in range(8): # Example: Knobs B1-B8 LEDs CC 9-16 (Verify mapping!)
             knob_led_cc = 9 + i
             self.send_midi_cc(control=knob_led_cc, value=0)

        # <<< REMOVED Transport LED update call >>>
        # self._update_transport_leds() # Initial state

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
        current_song = self.song_service.get_current_song()
        # No song? Do nothing. Check added here for robustness.
        if not current_song:
            # Clear flags if no song is loaded to prevent stale state
            self._clear_preparation_flags()
            return

        if outport_name == "Transport.LoadNowBeat":
            # Triggered just before the start of the *next* loop/repetition
            # This signal is now ONLY for PREPARATION (sending PGMs)
            print(f"Received LoadNowBeat (Value: {value}) - Current Seg: {self.current_segment_index+1}, Rep: {self.current_repetition}")
            self._prepare_next_segment_or_rep() # Renamed function call

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
                        # <<< Reset the initial cycle flag when stopping >>>
                        self.is_initial_cycle_after_play = True
                        # Reset counters if stopping (unless Prime logic handles it)
                        # self._reset_playback_state() # <<< REMOVED: Don't reset on stop/pause >>>
                        pass
                    else:
                        # <<< Reset the flag when starting play too, to handle restarts >>>
                        self.is_initial_cycle_after_play = True
                    self.update_combined_status() # Update status display
                    # self._update_transport_leds() # <<< REMOVED Call >>>
            except (ValueError, TypeError):
                 print(f"Warning: Could not parse Transport.Status value: {value}")

        # <<< ADD Tempo Handling >>>
        elif outport_name == "Transport.Tempo":
            try:
                new_tempo = float(value)
                if new_tempo != self.current_tempo:
                    self.current_tempo = new_tempo
                    print(f"Tempo updated via OSC: {self.current_tempo:.1f}")
                    # Optionally update status immediately if needed
                    # self.update_combined_status()
            except (ValueError, TypeError):
                print(f"Warning: Could not parse Transport.Tempo value: {value}")
        # <<< END Tempo Handling >>>

        # <<< Beat Count Handling (Looks Correct) >>>
        elif outport_name == "Transport.4nCount":
            # Signal indicating current beat position.
            # Use Beat 1 to trigger ACTIVATION of a prepared segment or increment repetition.
            try:
                new_beat_count = int(value)
                # Store the raw beat count (0-indexed from RNBO likely)
                self.current_beat_count = new_beat_count

                # Check if it's the first beat (assuming 0 from RNBO marks the start of the cycle)
                # Or adjust to '1' if your RNBO patch sends 1-based counts. Let's assume 0 for now.
                is_first_beat_of_cycle = (new_beat_count == 0) # <<< ADJUST 0 or 1 based on RNBO output >>>

                if is_first_beat_of_cycle:
                    print(f"Beat 0/1 received. Checking for activation...") # Log start of cycle

                    if self.next_segment_prepared and self.prepared_next_segment_index is not None:
                        print(f"Beat 0/1: Activating prepared segment {self.prepared_next_segment_index + 1}.")
                        # --- Activate the prepared segment ---
                        self.current_segment_index = self.prepared_next_segment_index
                        self.current_repetition = 1 # Start rep 1 of the new segment
                        # Send Tempo and Loop Length for the *newly activated* segment
                        self._send_segment_activation_params(self.current_segment_index)
                        # Clear the flags now that activation is done
                        self._clear_preparation_flags()
                        self.is_initial_cycle_after_play = True # <<< Reset flag for new segment's first cycle >>>
                        print(f"Activation complete. Now on Seg {self.current_segment_index + 1}, Rep 1.")
                    else:
                        # --- No segment activation, means the current segment continues ---
                        # Increment repetition count ONLY when the new cycle starts and we are NOT changing segments
                        print(f"Beat 0/1: No segment prepared. Incrementing repetition for segment {self.current_segment_index + 1}.")
                        if current_song and 0 <= self.current_segment_index < len(current_song.segments):
                             # Only increment if we are actually playing and within a valid segment
                             if self.is_playing:
                                 # <<< ADD CHECK FOR PRIME FLAG >>>
                                if self.prime_action_occurred:
                                    print("Prime action occurred, skipping rep increment for this cycle.")
                                    self.prime_action_occurred = False # Reset the flag
                                    # Reset flag after prime action completes its first cycle
                                    self.is_initial_cycle_after_play = False # <<< ADDED Reset after prime cycle >>>
                                # <<< MODIFY INCREMENT LOGIC >>>
                                elif not self.is_initial_cycle_after_play: # Only increment if NOT the first cycle
                                    self.current_repetition += 1
                                    print(f"Segment {self.current_segment_index + 1} starting repetition {self.current_repetition}.")
                                else:
                                    print("Initial cycle after play/segment change, skipping rep increment.")
                                    # Now that the initial cycle has been processed, set flag to False
                                    self.is_initial_cycle_after_play = False
                                # <<< END MODIFY >>>
                             else:
                                 # If stopped on beat 1, reset rep to 1 for consistency when restarting
                                 self.current_repetition = 1
                                 # Flag is reset by Transport.Status handler
                                 print(f"Stopped on Beat 0/1, repetition reset to 1.")
                        else:
                             # Reset if state is invalid
                             self.current_repetition = 1
                             self.is_initial_cycle_after_play = True # <<< Reset flag >>>
                             print(f"Invalid state on Beat 0/1, repetition reset to 1.")

                # Update status display after processing beat count changes
                self.update_combined_status()

            except (ValueError, TypeError):
                print(f"Error parsing Transport.4nCount: {value}")

        # ... potentially handle other outports ...

    # --- Playback Logic ---
    def _prepare_next_segment_or_rep(self):
        """
        Handles logic when LoadNowBeat is received. PREPARES the next segment transition.
        Checks if the current segment is finishing its last repetition.
        If YES: Sends PGM messages for the next segment (if Tin.Toggle ON),
                sets preparation flags, handles auto-stop. Resets internal rep count for next segment.
        If NO: Clears preparation flags.
        Does NOT change self.current_segment_index or self.current_repetition directly.
        """
        current_song = self.song_service.get_current_song()
        if not current_song or not current_song.segments:
            print("LoadNowBeat ignored: No song or segments loaded.")
            self._clear_preparation_flags() # Ensure flags are clear
            return

        num_segments = len(current_song.segments)
        if not (0 <= self.current_segment_index < num_segments):
            print(f"LoadNowBeat ignored: Invalid segment index {self.current_segment_index}")
            self.current_segment_index = 0 # Reset index if invalid
            self.current_repetition = 1
            self._clear_preparation_flags()
            return

        current_segment = current_song.segments[self.current_segment_index]
        total_repetitions = current_segment.repetitions

        # Check if the repetition that just *finished* was the last one
        is_last_repetition = (self.current_repetition >= total_repetitions)

        if is_last_repetition:
            print(f"Segment {self.current_segment_index + 1} finished last repetition ({self.current_repetition}/{total_repetitions}). Preparing next.")

            # --- Check for Auto Stop ---
            if current_segment.automatic_transport_interrupt:
                print(f"Auto-stopping transport after segment {self.current_segment_index + 1}.")
                self.osc_service.send_rnbo_param(f"{self.transport_base_path}/transport/Transport.Stop", 1)
                # Don't prepare next segment if stopping. Clear flags.
                self._clear_preparation_flags()
                return # Stop processing here

            # --- Calculate Next Segment Index ---
            next_segment_index = (self.current_segment_index + 1) % num_segments
            print(f"Preparing transition to segment {next_segment_index + 1}")

            next_segment = current_song.segments[next_segment_index]
            print(f"Sending PREPARATORY PGM messages for upcoming segment {next_segment_index + 1}: PGM1={next_segment.program_message_1}, PGM2={next_segment.program_message_2}")
            self.osc_service.send_rnbo_param(f"{self.set_base_path}/Set.PGM1", next_segment.program_message_1)
            self.osc_service.send_rnbo_param(f"{self.set_base_path}/Set.PGM2", next_segment.program_message_2)

            if self.tin_toggle_state: # Check the boolean state directly
                print(f"Tin.Toggle is ON. Not implemented yet.")

            # --- Set Preparation Flags ---
            print(f"LoadNowBeat: Setting preparation flags for segment {next_segment_index + 1}.")
            self.next_segment_prepared = True
            self.prepared_next_segment_index = next_segment_index
            # DO NOT change self.current_segment_index or self.current_repetition here.

        else:
            # --- Still within the same segment, finished a repetition but not the last one ---
            print(f"Segment {self.current_segment_index + 1} finished repetition {self.current_repetition}/{total_repetitions}. No segment change prepared.")
            # Ensure preparation flags are clear if we are just finishing a rep but not the segment
            self._clear_preparation_flags()
            # DO NOT increment self.current_repetition here. It increments on Beat 1.

        # Update status display immediately after LoadNowBeat processing
        self.update_combined_status()

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

    def _send_segment_activation_params(self, segment_index: int):
        """Sends the Tempo and Loop Length for the given segment index to RNBO.
           Called when a segment becomes active (on Beat 1). Does NOT send PGMs."""
        current_song = self.song_service.get_current_song()
        if not current_song or not current_song.segments: return
        num_segments = len(current_song.segments)
        if not (0 <= segment_index < num_segments):
            print(f"Error sending activation params: Invalid segment index {segment_index}")
            return

        segment = current_song.segments[segment_index]
        print(f"Sending ACTIVATION params for segment {segment_index + 1}: Tempo={segment.tempo}, Loop={segment.loop_length}")

        # Send Tempo
        self.osc_service.send_rnbo_param(f"{self.transport_base_path}/tempo/Transport.Tempo", float(segment.tempo))
        # Send Loop Length (Assuming path exists - replace with actual path if different)
        # Example path, adjust as needed:
        # self.osc_service.send_rnbo_param(f"{self.transport_base_path}/transport/Transport.LoopLength", int(segment.loop_length))
        print(f"Tempo sent. Loop Length ({segment.loop_length}) sending needs correct OSC path.") # Placeholder reminder

        # DO NOT SEND PGMs HERE - They were sent on LoadNowBeat

    def _send_initial_segment_params(self):
        """Sends ALL parameters (Tempo, Loop Length, PGMs) for the very
           first segment (index 0) when the app starts or song loads."""
        current_song = self.song_service.get_current_song()
        segment_index = 0 # Always send for the first segment initially
        if not current_song or not current_song.segments:
            print("Cannot send initial params: No song or segments.")
            return
        num_segments = len(current_song.segments)
        if not (0 <= segment_index < num_segments):
             print(f"Error sending initial params: Invalid segment index {segment_index}")
             return

        segment = current_song.segments[segment_index]
        print(f"Sending INITIAL params for segment {segment_index + 1}: Tempo={segment.tempo}, Loop={segment.loop_length}, PGM1={segment.program_message_1}, PGM2={segment.program_message_2}")

        # Send Tempo
        self.osc_service.send_rnbo_param(f"{self.transport_base_path}/tempo/Transport.Tempo", float(segment.tempo))
        # Send Loop Length (Adjust path as needed)
        # self.osc_service.send_rnbo_param(f"{self.transport_base_path}/transport/Transport.LoopLength", int(segment.loop_length))
        print(f"Tempo sent. Loop Length ({segment.loop_length}) sending needs correct OSC path.") # Placeholder reminder

        # Send PGMs for the initial segment
        self.osc_service.send_rnbo_param(f"{self.set_base_path}/Set.PGM1", segment.program_message_1)
        self.osc_service.send_rnbo_param(f"{self.set_base_path}/Set.PGM2", segment.program_message_2)

        # Update internal tempo state as well
        self.current_tempo = segment.tempo

    # --- Status Update ---
    def update_combined_status(self, playback_components: Optional[Dict[str, Any]] = None):
        """Updates the systemd status with screen, MIDI, OSC, Song, and Playback info."""
        screen_name = "No Screen"
        active_screen = self.screen_manager.get_active_screen()
        if active_screen:
            screen_name = active_screen.__class__.__name__
        midi_status = self.midi_service.get_status_string()
        osc_status = self.osc_service.get_status_string()
        song_name = self.song_service.get_current_song_name() or 'None'
        dirty_flag = "*" if self.song_service.is_current_song_dirty() else ""
        song_status = f"Song: {song_name}{dirty_flag}"

        # Generate playback status string for systemd if components are provided
        playback_status_str = ""
        if playback_components:
            # Format a concise playback status for systemd
            pb_symbol = playback_components['play_symbol']
            pb_seg = playback_components['seg_text'].replace("Seg: ", "")
            pb_rep = playback_components['rep_text'].replace("Rep: ", "")
            pb_beat = playback_components['beat_text'].replace("Beat: ", "B")
            pb_tempo = playback_components['tempo_text'].replace("Tempo: ", "T")
            playback_status_str = f"| {pb_symbol} {pb_seg} {pb_rep} {pb_beat} {pb_tempo}"

        # Combine for systemd status
        combined_status = f"{screen_name} | {midi_status} | {osc_status} | {song_status}{playback_status_str}"
        self.notify_status(combined_status)


    def cleanup(self):
        """Clean up resources before exiting."""
        print("Cleaning up application...")
        logger.info("Cleanup started.")
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

        # --- Stop RNBO Service --- <<< ADD THIS BLOCK
        logger.info("Attempting to stop RNBO service...")
        stop_rnbo_service()
        # --- End Stop RNBO Service ---

        # Cleanup active screen
        self.screen_manager.cleanup_active_screen()

        # Cleanup MIDI service
        self._initial_led_update() # Re-use to turn off LEDs
        time.sleep(0.1)

        if self.midi_service:
            logger.info("Stopping MIDI Service...")
            self.midi_service.close_ports()

        # Cleanup OSC service
        if self.osc_service:
            logger.info("Stopping OSC Service...")
            self.osc_service.stop()

        # Cleanup Song service (if it has resources like open files)
        if self.song_service:
             # Assuming SongService might have cleanup tasks in the future
             # self.song_service.cleanup() # Example placeholder
             pass

        # Quit Pygame
        pygame.font.quit()
        pygame.quit()
        print("Pygame quit.")
        logger.info("Pygame quit.")
        self.notifier.notify("STOPPING=1")
        print("Cleanup finished.")
        logger.info("Cleanup finished.")

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
        """Stops the related systemd services individually."""
        services_to_stop = ["rnbooscquery-emsys.service", "emsys-python.service"]
        self.notify_status(f"Stopping services: {', '.join(services_to_stop)}...")
        logger.info(f"Service stop requested for {', '.join(services_to_stop)}.")

        all_stopped_successfully = True
        errors = []

        # Stop RNBO first, then the Python service
        # This order might be slightly better if RNBO depends on Python,
        # though systemd handles the reverse dependency on start.
        # For stopping, it often makes less difference.
        for service_name in services_to_stop:
            command = ['sudo', 'systemctl', 'stop', service_name]
            logger.info(f"Executing: {' '.join(command)}")
            try:
                # Use check=False initially to log errors without raising immediately
                result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=15)

                if result.returncode == 0:
                    logger.info(f"Successfully issued stop command for {service_name} (or it was inactive).")
                    if result.stdout: logger.debug(f"Stop {service_name} stdout: {result.stdout.strip()}")
                    # systemd often prints "Stopped ..." or nothing to stderr on success
                    if result.stderr: logger.info(f"Stop {service_name} stderr: {result.stderr.strip()}")
                else:
                    # Log non-zero exit code as an error, but continue
                    # Common non-zero codes for 'stop': 5 (inactive) - treat as success for our purpose
                    if result.returncode == 5 and "inactive" in result.stderr.lower():
                         logger.info(f"Service {service_name} was already inactive (exit code 5).")
                         # Treat as success for the overall outcome
                    else:
                        all_stopped_successfully = False
                        error_message = (
                            f"Command failed for 'systemctl stop {service_name}' "
                            f"(exit code {result.returncode}). "
                            f"Stderr: {result.stderr.strip() if result.stderr else 'N/A'}. "
                            f"Stdout: {result.stdout.strip() if result.stdout else 'N/A'}."
                        )
                        logger.error(error_message)
                        errors.append(error_message)
                    # Don't raise here, try stopping the other service

            except FileNotFoundError:
                error_message = f"Error: 'sudo' or 'systemctl' command not found. Cannot stop {service_name}."
                logger.error(error_message)
                errors.append(error_message)
                all_stopped_successfully = False
                break # If systemctl isn't found, no point continuing
            except subprocess.TimeoutExpired:
                error_message = f"Timeout waiting for 'systemctl stop {service_name}' command."
                logger.error(error_message)
                errors.append(error_message)
                all_stopped_successfully = False
                # Continue to next service
            except Exception as e:
                error_message = f"An unexpected error occurred while stopping {service_name}: {e}"
                logger.error(error_message, exc_info=True) # Log traceback
                errors.append(error_message)
                all_stopped_successfully = False
                # Continue to next service

        if all_stopped_successfully:
            self.notify_status("Services stopped successfully.")
            logger.info("All specified services stopped successfully or were already inactive.")
        else:
            final_error_summary = "Service stop attempt finished with errors: " + " | ".join(errors)
            # Show first specific error on screen if available, else generic message
            first_error = errors[0] if errors else "See logs for details"
            self.notify_status(f"Service stop failed: {first_error}")
            logger.error(final_error_summary)

        # Decide what to do after attempting stop.
        # If running under debugger (not systemd), explicitly stop the Python script's loop.
        # If running as a service, stopping emsys-python.service should terminate it anyway.
        if not os.getenv('INVOCATION_ID'): # Check if NOT running under systemd
             logger.info("Detected running outside systemd, initiating application exit after stop attempt.")
             self.running = False # Signal the main loop to terminate

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

    # <<< NEW METHOD to generate playback status components >>>
    def _get_playback_status_components(self) -> Dict[str, Any]:
        """Generates detailed playback status components."""
        current_song = self.song_service.get_current_song()
        num_segments = len(current_song.segments) if current_song and current_song.segments else 0

        play_symbol = ">" if self.is_playing else "||"
        tempo_text = f"Tempo: {self.current_tempo:.1f}" # Use internal tempo state

        seg_text = "Seg: -/-"
        rep_text = "Rep: -/-"
        beat_text = f"Beat: {self.current_beat_count + 1}" # Display 1-based beat count

        current_playing_segment_index = None # Default to None

        if current_song and current_song.segments and 0 <= self.current_segment_index < num_segments:
            current_segment = current_song.segments[self.current_segment_index]
            total_repetitions = current_segment.repetitions
            seg_text = f"Seg: {self.current_segment_index + 1}/{num_segments}"
            rep_text = f"Rep: {self.current_repetition}/{total_repetitions}"
            current_playing_segment_index = self.current_segment_index # Set the index if valid
        else:
            # Handle cases where there's no song or index is invalid
            seg_text = f"Seg: -/{num_segments}" if num_segments > 0 else "Seg: -/-"
            rep_text = "Rep: -/-"
            # beat_text remains as calculated above or default

        return {
            "play_symbol": play_symbol,
            "seg_text": seg_text,
            "rep_text": rep_text,
            "beat_text": beat_text,
            "tempo_text": tempo_text,
            "current_playing_segment_index": current_playing_segment_index
        }
    # <<< END NEW METHOD >>>

# Script Entry Point
def main():
    """Main function."""
    # Logging is already configured above
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
