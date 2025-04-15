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
import sdnotify # For systemd notification
import traceback # For detailed error logs
from typing import Optional, Dict, Any

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
from emsys.services.song_service import SongService # <<< ADDED SongService
from emsys.ui.screen_manager import ScreenManager
from emsys.ui.base_screen import BaseScreen  # Import BaseScreen
# --------------------------

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
        self.midi_service = MidiService(status_callback=self.notify_status)
        self.song_service = SongService(status_callback=self.notify_status) # <<< INSTANTIATE SongService
        # Pass app reference AND SongService reference to ScreenManager
        self.screen_manager = ScreenManager(app_ref=self, song_service_ref=self.song_service)
        # --------------------------

        # --- Application State ---
        # self.current_song removed - managed by SongService
        self.last_midi_message_str = None # Keep for potential display
        # Dictionary mapping control_number to {'press_time': float, 'last_repeat_time': float, 'message': mido.Message}
        self.pressed_buttons: Dict[int, Dict[str, Any]] = {}
        # -------------------------

        # --- Final Initialization Steps ---
        self.screen_manager.set_initial_screen() # Set the first screen active
        if not self.screen_manager.get_active_screen():
             self.notify_status("FAIL: No UI screens loaded.")
             raise RuntimeError("Application cannot start without any screens.")

        self._initial_led_update() # Update LEDs based on initial screen
        # self._load_last_song() # Now handled by SongService init
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
                    self.handle_midi_message(msg)
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
                    midi_status_str = self.midi_service.get_status_string()
                    # Pass SongService status (e.g., current song name/dirty state) if needed
                    song_status_str = f"Song: {self.song_service.get_current_song_name() or 'None'}"
                    if self.song_service.is_current_song_dirty(): song_status_str += "*"

                    active_screen.draw(self.screen, midi_status=midi_status_str, song_status=song_status_str)
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
        """
        Process incoming MIDI messages. Routes based on type and CC.
        Handles button press/release/repeat logic for momentary buttons.
        Directly dispatches messages for non-repeatable controls.
        """
        if hasattr(msg, 'channel') and msg.channel != 15:
            return

        self.last_midi_message_str = str(msg)
        current_time = time.time()

        if msg.type == 'control_change':
            control = msg.control
            value = msg.value

            if control in NON_REPEATABLE_CCS:
                self._dispatch_action(msg)
                return

            if value == 127:
                if control not in self.pressed_buttons:
                    self.pressed_buttons[control] = {
                        'press_time': current_time,
                        'last_repeat_time': current_time,
                        'message': msg
                    }
                    self._dispatch_action(msg)
                return

            elif value == 0:
                if control in self.pressed_buttons:
                    del self.pressed_buttons[control]
                return
            else:
                 return
        else:
            self._dispatch_action(msg)

    def _dispatch_action(self, msg):
        """
        Determines and executes the action associated with a MIDI message.
        Handles global actions (screen switching) or passes to the active screen.
        Prevents global screen switching if an input widget is active on the screen.
        """
        active_screen = self.screen_manager.get_active_screen()

        widget_active = False
        if active_screen:
            text_input_widget = getattr(active_screen, 'text_input_widget', None)
            if text_input_widget and getattr(text_input_widget, 'is_active', False):
                 widget_active = True

        if msg.type == 'control_change':
            control = msg.control
            value = msg.value

            if not widget_active and value == 127:
                if control == NEXT_CC:
                    print(f"Requesting next screen (via CC #{NEXT_CC})")
                    self.screen_manager.request_next_screen()
                    return
                elif control == PREV_CC:
                    print(f"Requesting previous screen (via CC #{PREV_CC})")
                    self.screen_manager.request_previous_screen()
                    return

            if active_screen and hasattr(active_screen, 'handle_midi'):
                try:
                    active_screen.handle_midi(msg)
                except Exception as screen_midi_err:
                     print(f"Error in screen {active_screen.__class__.__name__} handling MIDI {msg}: {screen_midi_err}")
                     traceback.print_exc()
        else:
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

    def update_combined_status(self):
        """Updates the systemd status with screen and MIDI info."""
        screen_name = "No Screen"
        active_screen = self.screen_manager.get_active_screen()
        if active_screen:
            screen_name = active_screen.__class__.__name__
        midi_status = self.midi_service.get_status_string()
        # Include basic song status
        song_status = f"Song: {self.song_service.get_current_song_name() or 'None'}"
        if self.song_service.is_current_song_dirty(): song_status += "*"

        combined_status = f"Screen: {screen_name} | {midi_status} | {song_status}"
        self.notify_status(combined_status)


    def cleanup(self):
        """Clean up resources before exiting."""
        print("Cleaning up application...")
        self.notify_status("Application Shutting Down")

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
