# -*- coding: utf-8 -*-
"""
Main entry point for the Emsys Python Application.

Initializes Pygame, services (MIDI, OSC), UI screens, and runs the main event loop.
"""

import pygame
import sys
import sdnotify # For systemd readiness notification

# Import components from our emsys package (adjust paths as needed)
# from .config import settings # Example: Load settings
# from .services import midi_handler, osc_handler # Example: MIDI/OSC handlers
# from .ui import main_menu_screen, song_edit_screen # Example: UI Screens
# from .core import project_manager # Example: Song management

# --- Constants (Consider moving to config/settings.py later) ---
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320
FPS = 30

# --- Main Application Class ---

class App:
    """Encapsulates the main application logic and state."""

    def __init__(self):
        """Initialize Pygame, services, and application state."""
        print("Initializing App...")

        # Systemd Notifier
        self.notifier = sdnotify.SystemdNotifier()
        self.notify_status("Initializing Pygame...")

        # Initialize Pygame
        pygame.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Emsys Controller')
        self.clock = pygame.time.Clock()
        self.running = False

        # Load Configuration (Placeholder)
        # self.settings = settings.load_settings()
        print("Config loaded (Placeholder).")

        # Initialize Services (Placeholders)
        self.midi = None
        self.osc = None
        try:
            # self.midi = midi_handler.MidiHandler(self.settings['midi_port_name'])
            # self.midi.start() # Start listening thread/callback
            print("MIDI Handler initialized (Placeholder).")

            # --- Notify systemd AFTER potentially blocking resources are acquired ---
            self.notify_status("MIDI Initialized. Notifying systemd READY=1")
            self.notifier.notify("READY=1")
            # --- End systemd notification ---

            # self.osc = osc_handler.OscHandler(self.settings['osc_send_ip'], ...)
            # self.osc.start_server(...) # Start OSC server thread
            print("OSC Handler initialized (Placeholder).")

        except Exception as e:
            print(f"Error initializing services: {e}")
            self.notify_status(f"Error initializing services: {e}")
            # Decide how to handle errors - exit? retry?
            # For now, we might continue without MIDI/OSC for basic UI testing
            # but send READY=1 anyway if basic UI should run
            self.notifier.notify("READY=1") # Or exit?

        # Initialize Core Logic (Placeholder)
        # self.project_manager = project_manager.ProjectManager(self.settings['songs_dir'])
        print("Project Manager initialized (Placeholder).")

        # Initialize UI (Placeholder)
        self.active_screen = None
        self._initialize_ui()
        print("UI Initialized.")
        self.notify_status("Initialization complete. Running...")


    def _initialize_ui(self):
        """Sets up the initial UI screen."""
        # Example: Start with the main menu
        # self.active_screen = main_menu_screen.MainMenuScreen(self) # Pass app reference
        # For now, just a placeholder message
        self.main_font = pygame.font.SysFont(None, 50)
        print("UI setup complete (Placeholder).")


    def notify_status(self, status_message):
        """Helper function to print status and notify systemd."""
        print(f"Status: {status_message}")
        self.notifier.notify(f"STATUS={status_message}")

    def run(self):
        """Main application loop."""
        self.running = True
        while self.running:
            # --- Event Handling ---
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                # Pass events to the active screen for handling
                if self.active_screen:
                    # self.active_screen.handle_event(event) # Placeholder
                    pass # Replace with actual screen handling

            # --- MIDI Handling ---
            if self.midi:
                # midi_messages = self.midi.get_messages() # Placeholder
                # for msg in midi_messages:
                #     self.handle_midi_message(msg) # Placeholder
                pass # Replace with actual MIDI processing

            # --- OSC Handling ---
            if self.osc:
                # osc_messages = self.osc.get_messages() # Placeholder
                # for addr, args in osc_messages:
                #      self.handle_osc_message(addr, args) # Placeholder
                pass # Replace with actual OSC processing

            # --- Update ---
            # Update the active screen's state
            if self.active_screen:
                 # self.active_screen.update() # Placeholder
                 pass # Replace with actual screen update logic

            # --- Draw ---
            self.screen.fill((0, 0, 0)) # Black background

            # Draw the active screen
            if self.active_screen:
                # self.active_screen.draw(self.screen) # Placeholder
                pass # Replace with actual screen drawing
            else:
                # Fallback if no screen is active yet
                text_surf = self.main_font.render("Initializing...", True, (255, 255, 255))
                text_rect = text_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
                self.screen.blit(text_surf, text_rect)


            pygame.display.flip()

            # --- Frame Rate Control ---
            self.clock.tick(FPS)

        # --- Exit ---
        self.cleanup()

    def handle_midi_message(self, msg):
        """Process incoming MIDI messages based on Layer A/B."""
        # Placeholder - Implement Layer A/B logic here
        # Check msg.control, msg.value
        # If Layer A -> self.osc.send(...)
        # If Layer B -> Call relevant Python/UI function
        print(f"MIDI Received (Handler Placeholder): {msg}")

    def handle_osc_message(self, address, args):
        """Process incoming OSC messages (e.g., feedback from RNBO)."""
        # Placeholder - Update internal state based on OSC feedback
        print(f"OSC Received (Handler Placeholder): {address} {args}")
        # Update ui_state variables that the active screen reads

    def change_screen(self, new_screen_instance):
        """Changes the currently active UI screen."""
        # Placeholder for screen management logic
        print(f"Changing screen to {type(new_screen_instance).__name__} (Placeholder)")
        self.active_screen = new_screen_instance


    def cleanup(self):
        """Clean up resources before exiting."""
        self.notify_status("Cleaning up...")
        print("Cleaning up...")
        if self.midi:
            # self.midi.close() # Placeholder
            print("MIDI Handler closed (Placeholder).")
        if self.osc:
             # self.osc.close() # Placeholder
             print("OSC Handler closed (Placeholder).")
        pygame.quit()
        print("Pygame quit.")
        self.notify_status("Exited.")
        self.notifier.notify("STOPPING=1") # Final notification for systemd


# --- Script Entry Point ---
if __name__ == '__main__':
    try:
        app = App()
        app.run()
    except Exception as e:
        print(f"\n--- An unhandled error occurred ---")
        # Attempt to notify systemd of the failure if possible
        try:
            n = sdnotify.SystemdNotifier()
            n.notify("STATUS=Crashed unexpectedly.")
            n.notify("STOPPING=1")
        except Exception as sd_err:
            print(f"(Could not notify systemd: {sd_err})")
        # Log the full traceback
        import traceback
        traceback.print_exc()
        pygame.quit() # Attempt to clean up pygame
        sys.exit(1) # Exit with error code

