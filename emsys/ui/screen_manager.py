# emsys/ui/screen_manager.py
# -*- coding: utf-8 -*-
"""
Manages the application screens, including initialization and switching.
"""
import pygame
import traceback
from typing import List, Optional, Type, Any

# Use absolute imports
from emsys.ui.base_screen import BaseScreen
from emsys.ui.placeholder_screen import PlaceholderScreen
from emsys.ui.song_manager_screen import SongManagerScreen
from emsys.ui.song_edit_screen import SongEditScreen

# Define screen classes in order
# Filter out None values if imports failed (though main should handle this)
SCREEN_CLASSES = [
    screen for screen in [
        PlaceholderScreen,
        SongManagerScreen,
        SongEditScreen,
    ] if screen is not None
]

class ScreenManager:
    """Handles the lifecycle and switching of application screens."""

    def __init__(self, app_ref: Any):
        """
        Initialize the ScreenManager.

        Args:
            app_ref: A reference to the main application instance.
                     Used to pass to screen constructors.
        """
        self.app = app_ref
        self.screens: List[BaseScreen] = []
        self.active_screen: Optional[BaseScreen] = None
        self.pending_screen_change: Optional[BaseScreen] = None

        self._initialize_screens()

    def _initialize_screens(self):
        """Instantiate all available screen classes."""
        print("Initializing Screens...")
        self.screens = []
        for ScreenClass in SCREEN_CLASSES:
            try:
                screen_instance = ScreenClass(self.app)
                self.screens.append(screen_instance)
                print(f"  - Initialized {ScreenClass.__name__}")
            except Exception as e:
                print(f"Error initializing screen {ScreenClass.__name__}: {e}")
                traceback.print_exc()

        if not self.screens:
            print("WARNING: No screens successfully initialized!")
            # The main app should handle this case (e.g., exit)
        else:
            # Set the first screen as active initially
            # The actual call to set_active_screen is done by the App after manager init
            print("Screen instances created.")

    def set_initial_screen(self):
        """Sets the first available screen as active."""
        if self.screens:
            self.set_active_screen(self.screens[0])
        else:
             print("ScreenManager: Cannot set initial screen, no screens available.")


    def set_active_screen(self, screen: Optional[BaseScreen]):
        """
        Sets the active screen, handling cleanup of the old screen and init of the new.

        Args:
            screen: The screen instance to activate. If None, does nothing.
        """
        if screen is None or self.active_screen == screen:
            if screen is None:
                print("ScreenManager Error: Attempted to set active screen to None.")
            return # No change needed or invalid input

        old_screen = self.active_screen

        # Cleanup old screen
        if old_screen and hasattr(old_screen, 'cleanup'):
            try:
                print(f"Cleaning up {old_screen.__class__.__name__}...")
                old_screen.cleanup()
            except Exception as e:
                print(f"Error during {old_screen.__class__.__name__} cleanup: {e}")
                traceback.print_exc()

        self.active_screen = screen
        # Notify the app about the change (e.g., for status updates)
        if hasattr(self.app, 'notify_status'):
            status_msg = f"Screen Activated: {self.active_screen.__class__.__name__}"
            self.app.notify_status(status_msg)


        # Initialize new screen
        if hasattr(self.active_screen, 'init'):
             try:
                 print(f"Initializing {self.active_screen.__class__.__name__}...")
                 self.active_screen.init()
             except Exception as e:
                 print(f"Error during {self.active_screen.__class__.__name__} init: {e}")
                 traceback.print_exc()
                 # Revert to old screen on init failure? Or maybe a default error screen?
                 print(f"Reverting to previous screen due to init error.")
                 self.active_screen = old_screen
                 # Re-initialize the old screen if needed? Or assume it's state is ok?
                 # if old_screen and hasattr(old_screen, 'init'): old_screen.init()
                 if hasattr(self.app, 'notify_status'):
                     self.app.notify_status(f"FAIL: Init error in {screen.__class__.__name__}. Reverted.")
                 return # Stop the screen change process

    def request_next_screen(self):
        """Requests a change to the next screen in the list."""
        if not self.screens or self.active_screen is None:
            print("ScreenManager: Cannot navigate next, no screens or no active screen.")
            return

        try:
            current_index = self.screens.index(self.active_screen)
            next_index = (current_index + 1) % len(self.screens)
            self.pending_screen_change = self.screens[next_index]
            print(f"ScreenManager: Requested next screen: {self.pending_screen_change.__class__.__name__}")
        except ValueError:
             print("ScreenManager Error: Active screen not found in screen list.")
             # Default to first screen if current is lost
             self.pending_screen_change = self.screens[0]

    def request_previous_screen(self):
        """Requests a change to the previous screen in the list."""
        if not self.screens or self.active_screen is None:
            print("ScreenManager: Cannot navigate previous, no screens or no active screen.")
            return

        try:
            current_index = self.screens.index(self.active_screen)
            prev_index = (current_index - 1 + len(self.screens)) % len(self.screens)
            self.pending_screen_change = self.screens[prev_index]
            print(f"ScreenManager: Requested previous screen: {self.pending_screen_change.__class__.__name__}")
        except ValueError:
            print("ScreenManager Error: Active screen not found in screen list.")
            # Default to last screen if current is lost
            self.pending_screen_change = self.screens[-1]

    def process_pending_change(self):
        """If a screen change is pending, performs the change."""
        if self.pending_screen_change:
            screen_to_set = self.pending_screen_change
            self.pending_screen_change = None # Clear request
             # Check if the current screen allows deactivation (e.g., unsaved changes prompt)
            can_deactivate = True
            if self.active_screen and hasattr(self.active_screen, 'can_deactivate'):
                 if callable(getattr(self.active_screen, 'can_deactivate')):
                     can_deactivate = self.active_screen.can_deactivate()
                 else:
                     # If can_deactivate exists but is not callable, assume it's a boolean attribute
                     can_deactivate = bool(getattr(self.active_screen, 'can_deactivate', True))


            if can_deactivate:
                 print(f"ScreenManager: Processing pending change to {screen_to_set.__class__.__name__}")
                 self.set_active_screen(screen_to_set)
            else:
                 print(f"ScreenManager: Pending change blocked by active screen ({self.active_screen.__class__.__name__}).")
                 # Keep self.pending_screen_change = None, the request is effectively cancelled.
                 # The screen that blocked must handle re-requesting if needed (e.g., after save/discard).

    def request_screen_change_approved(self):
        """
        Called by a screen (e.g., after resolving an exit prompt) to indicate
        that a previously blocked screen change can now proceed if one was pending.
        """
        # This signal indicates readiness. The main loop will call
        # process_pending_change again, which should now succeed.
        # We don't need to re-set pending_screen_change here.
        print("ScreenManager: Screen signaled readiness for change. Main loop will re-attempt.")
        # If a screen change wasn't pending, this does nothing.

    def get_active_screen(self) -> Optional[BaseScreen]:
        """Returns the currently active screen instance."""
        return self.active_screen

    def cleanup_active_screen(self):
        """Calls the cleanup method of the currently active screen."""
        if self.active_screen and hasattr(self.active_screen, 'cleanup'):
            try:
                self.active_screen.cleanup()
            except Exception as e:
                 print(f"Error during final cleanup of {self.active_screen.__class__.__name__}: {e}")
                 traceback.print_exc()
