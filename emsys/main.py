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

from ui.base_screen import BaseScreen
from ui.main_menu_screen import MainMenuScreen

# --- Minimal Placeholder Screen ---
class PlaceholderScreen(BaseScreen):
    """A very basic screen to display something."""
    def __init__(self, app_ref):
        super().__init__(app_ref)
        self.text_surf = self.font.render("emsys Running!", True, WHITE)
        self.text_rect = self.text_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))

    def draw(self, screen_surface):
        """Draws the screen content."""
        screen_surface.blit(self.text_surf, self.text_rect)

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
        pygame.font.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Emsys Controller')
        self.clock = pygame.time.Clock()
        pygame.mouse.set_visible(False) # Hide mouse cursor
        self.running = False

        self.midi_port = None
        self.midi_port_name = None
        self.active_screen = None
        self.main_font = pygame.font.SysFont(None, 36) # For potential status text

        # Initialize MIDI Directly (like test.py)
        self._initialize_midi()

        # Initialize UI
        self._initialize_ui() # This will now set self.active_screen

        print("Initialization complete.")
        self.notify_status("Initialization complete. Running...")

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
                # Decide: Exit or continue without MIDI? For now, continue but notify.
                # We still send READY=1 so dependent services might start,
                # but the app might be non-functional without MIDI.
                self.notifier.notify("READY=1") # Or maybe exit?
                self.midi_port = None # Ensure port is None if failed
        else:
            error_info = f"MIDI Device '{DEVICE_BASE_NAME}' not found."
            print(error_info)
            self.notify_status(f"FAIL: {error_info}")
            # Also send READY=1 here? Or exit? Sending READY=1 for now.
            self.notifier.notify("READY=1")


    def _initialize_ui(self):
        """Sets up the initial UI screen."""
        print("Initializing UI...")
        # Create and set the initial screen instance - using MainMenuScreen instead of PlaceholderScreen
        self.active_screen = MainMenuScreen(self)
        print("UI setup complete.")

    def notify_status(self, status_message):
        """Helper function to print status and notify systemd."""
        # Limit message length for systemd status
        max_len = 80
        truncated_message = status_message[:max_len] + '...' if len(status_message) > max_len else status_message
        print(f"Status: {truncated_message}")
        try:
            self.notifier.notify(f"STATUS={truncated_message}")
        except Exception as e:
            print(f"Could not notify systemd: {e}") # Non-fatal if systemd not present

    def run(self):
        """Main application loop."""
        if not self.active_screen:
             print("ERROR: No active screen set during initialization. Exiting.")
             self.cleanup()
             return

        self.running = True
        while self.running:
            # --- Event Handling (Pygame) ---
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    # Although window close button isn't available, handle for completeness
                    self.running = False
                # Pass other events to the active screen
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
                    self.midi_port.close()
                    self.midi_port = None # Stop trying to read

            # --- Update ---
            if self.active_screen:
                 self.active_screen.update()

            # --- Draw ---
            self.screen.fill(BLACK) # Black background
            if self.active_screen:
                self.active_screen.draw(self.screen) # Draw the active screen
            pygame.display.flip()

            # --- Frame Rate Control ---
            self.clock.tick(FPS)

        # --- Exit ---
        self.cleanup()

    def handle_midi_message(self, msg):
        """Process incoming MIDI messages."""
        # print(f"MIDI Received: {msg}") # Debug: Print all messages
        if msg.type == 'control_change':
            # Check for designated EXIT button press (CC #47, value 127)
            if msg.control == EXIT_CC_NUMBER and msg.value == 127:
                print(f"Exit command received (CC #{EXIT_CC_NUMBER}). Shutting down.")
                self.notify_status("Exit command received...")
                self.running = False # Signal main loop to stop
            else:
                # Placeholder for Layer A/B logic to be added later
                # For now, maybe pass to active screen?
                # if self.active_screen:
                #     self.active_screen.handle_midi(msg) # Add this method to screens later
                pass


    def cleanup(self):
        """Clean up resources before exiting."""
        current_status = "Cleaning up..."
        self.notify_status(current_status)
        print(current_status)
        if self.midi_port:
            print(f"Closing MIDI port: {self.midi_port_name}")
            try:
                self.midi_port.close()
            except Exception as e:
                print(f"Error closing MIDI port: {e}")
        pygame.quit()
        print("Pygame quit.")
        current_status = "Exited."
        print(current_status)
        try:
            self.notifier.notify(f"STATUS={current_status}")
            self.notifier.notify("STOPPING=1") # Final notification for systemd
        except Exception as e:
            print(f"Could not notify systemd on exit: {e}")


# --- Script Entry Point ---
if __name__ == '__main__':
    app = None # Define app outside try block for finally clause
    try:
        app = App()
        app.run() # This blocks until self.running is False
        sys.exit(0) # Explicitly exit with success code
    except Exception as e:
        print(f"\n--- An unhandled error occurred in main ---")
        import traceback
        traceback.print_exc()
        # Attempt to notify systemd of the failure if possible
        try:
            n = sdnotify.SystemdNotifier()
            n.notify("STATUS=Crashed unexpectedly.")
            n.notify("STOPPING=1")
        except Exception as sd_err:
            print(f"(Could not notify systemd: {sd_err})")
        # Attempt cleanup even after crash
        if app:
            try:
                if app.midi_port: app.midi_port.close()
            except: pass # Ignore errors during cleanup after crash
        try:
            pygame.quit()
        except: pass # Ignore errors during cleanup after crash
        sys.exit(1) # Exit with error code

