# emsys/ui/placeholder_screen.py

import pygame
import time # Import the time module
import random # Import random module for randomizing animation timing
import subprocess # Import subprocess to run git command
from emsys.ui.base_screen import BaseScreen
# Import necessary colors
from emsys.config.settings import WHITE, GREEN, YELLOW, RED, GREY, BLACK#, SCREEN_WIDTH, SCREEN_HEIGHT # <<< ADDED SCREEN_WIDTH, SCREEN_HEIGHT
from emsys.config import mappings # Import mappings for button CCs
from emsys.ui.helpers.confirmation_prompts import ConfirmationPrompts, PromptType # Import prompt helper

class PlaceholderScreen(BaseScreen):
    """
    A simple placeholder screen displaying basic info, a MIDI status indicator,
    a persistent winking animation, the Git commit ID, and handling shutdown/reboot prompts.
    """
    def __init__(self, app):
        # Initialize the BaseScreen (sets self.app and self.font)
        super().__init__(app)

        # --- Message to Display ---
        self.message = "Placeholder Screen" # <<< ADDED: Initialize the message attribute
        # --- End Message ---

        # --- Title ---
        self.title_text = "emsys"
        # Use a pixel font for title
        self.title_font = self.get_pixel_font(36)
        self.title_surf = self.title_font.render(self.title_text, True, GREY)
        self.title_rect = self.title_surf.get_rect()
        # --- End Title ---

        # --- Git Commit ID ---
        self.commit_id = self._get_git_commit_id()
        self.commit_font = self.get_pixel_font(22) # Use a small font
        commit_text = f"{self.commit_id}" if self.commit_id else ""
        self.commit_surf = self.commit_font.render(commit_text, True, GREY)
        self.commit_rect = self.commit_surf.get_rect()
        # --- End Git Commit ID ---

        # Indicator properties
        self.indicator_radius = 8
        self.indicator_padding = 15 # Padding from screen edges

        # --- Persistent Animation ---
        # Use a pixel font for the kaomoji
        #self.kaomoji_font = pygame.font.Font(None, 48)
        self.kaomoji_font = self.get_pixel_font(34)
        self.kaomoji_open_surf = self.kaomoji_font.render("(v_v)", True, RED)
        self.kaomoji_wink_surf = self.kaomoji_font.render("(-_-)", True, RED)
        self.kaomoji_open_rect = self.kaomoji_open_surf.get_rect()
        self.kaomoji_wink_rect = self.kaomoji_wink_surf.get_rect()
        
        # Base values for animation timing
        self.base_cycle_duration = 10.0  # Base cycle time in seconds
        self.base_wink_duration = 0.15  # Base wink duration
        
        # Set initial random durations
        self.randomize_animation_timing()
        
        # Track when we last started a cycle
        self.last_cycle_start_time = time.time() # <<< ADDED: Initialize last_cycle_start_time
        # --- End Persistent Animation ---

        # --- Confirmation Prompts ---
        # Pass the app reference to ConfirmationPrompts
        self.confirmation_prompts = ConfirmationPrompts(app_ref=self.app) # <<< MODIFIED: Pass app_ref
        # --- End Confirmation Prompts ---

        # --- Button State Tracking ---
        self.no_button_held = False
        # --- End Button State Tracking ---

        # Add any other specific initializations for PlaceholderScreen
        print("PlaceholderScreen initialized")

    def _get_git_commit_id(self):
        """Attempts to get the short git commit hash."""
        try:
            # Run the git command to get the short commit hash
            result = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                capture_output=True,
                text=True,
                check=True,
                cwd='/home/pi/emsys-rnbo' # Ensure running in the correct directory
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            # Handle errors like git not found or not a git repo
            print(f"Could not get git commit ID: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred while getting git commit ID: {e}")
            return None

    def randomize_animation_timing(self):
        """Randomize the animation cycle and wink durations slightly."""
        # Randomize cycle duration (base ±20%)
        self.animation_cycle_duration = random.uniform(
            self.base_cycle_duration * 0.8,
            self.base_cycle_duration * 1.2
        )
        
        # Randomize wink duration (base ±10%)
        self.wink_duration = random.uniform(
            self.base_wink_duration * 0.9, 
            self.base_wink_duration * 1.1
        )

    def draw(self, screen_surface, midi_status=None, song_status=None, duration_status=None): # <<< ADD duration_status
        # <<< ADDED: Get screen dimensions from the passed surface >>>
        screen_width = screen_surface.get_width()
        screen_height = screen_surface.get_height()
        # <<< END ADDED >>>

        screen_surface.fill(BLACK)

        # --- Handle Persistent Animation ---
        current_time = time.time()
        # Calculate position within the animation cycle
        elapsed_time = current_time - self.last_cycle_start_time
        
        # Check if we need to start a new cycle with new random timing
        if elapsed_time >= self.animation_cycle_duration:
            self.last_cycle_start_time = current_time
            self.randomize_animation_timing()
            elapsed_time = 0  # Reset elapsed time for new cycle

        kaomoji_to_draw = None
        rect_to_use = None

        # Determine which frame to show based on cycle time
        # Show wink for the last `wink_duration` seconds of the cycle
        if elapsed_time > (self.animation_cycle_duration - self.wink_duration):
            kaomoji_to_draw = self.kaomoji_wink_surf
            rect_to_use = self.kaomoji_wink_rect
        else: # Otherwise, show eyes open
            kaomoji_to_draw = self.kaomoji_open_surf
            rect_to_use = self.kaomoji_open_rect

        if kaomoji_to_draw and rect_to_use:
            # Center the kaomoji horizontally, position vertically (e.g., 1/3 down)
            rect_to_use.centerx = screen_width // 2 # <<< Use screen_width from surface
            rect_to_use.centery = screen_height // 3 # <<< Use screen_height from surface
            screen_surface.blit(kaomoji_to_draw, rect_to_use)

            # --- Draw Title Below Kaomoji ---
            # Position title centered horizontally, below the kaomoji rect
            self.title_rect.centerx = screen_width // 2 # <<< Use screen_width from surface
            self.title_rect.top = rect_to_use.bottom + 10 # Add 10px padding
            screen_surface.blit(self.title_surf, self.title_rect)
            # --- End Draw Title ---

        # --- End Persistent Animation ---

        # --- Draw MIDI Status Indicator ---
        indicator_color = GREY # Default color if no status
        if midi_status:
            # Determine color based on status string content
            status_lower = midi_status.lower()
            if "error" in status_lower or "disconnected" in status_lower:
                indicator_color = RED
            elif "searching" in status_lower:
                indicator_color = YELLOW
            elif "midi in:" in status_lower: # Assume connected if input is mentioned and no error/search
                indicator_color = GREEN
            # Add more specific checks if needed based on main.py's status strings

        # Calculate indicator position (top-right corner)
        indicator_pos = (screen_width - self.indicator_padding - self.indicator_radius, # <<< Use screen_width from surface
                         self.indicator_padding + self.indicator_radius)

        # Draw the indicator circle
        pygame.draw.circle(screen_surface, indicator_color, indicator_pos, self.indicator_radius) # <<< Use screen_surface

        # --- Draw Git Commit ID ---
        # Position commit ID in the bottom-left corner
        self.commit_rect.bottomleft = (self.indicator_padding, screen_height - self.indicator_padding) # <<< Use screen_height from surface
        screen_surface.blit(self.commit_surf, self.commit_rect)
        # --- End Draw Git Commit ID ---

        # --- Draw Confirmation Prompt (if active) ---
        self.confirmation_prompts.draw(screen_surface) # <<< Use screen_surface
        # --- End Draw Confirmation Prompt ---

    # Implement other methods like handle_event, handle_midi, update if needed
    def handle_midi(self, msg):
        """Handle MIDI input, checking for shutdown/reboot combinations and prompts."""
        if msg.type != 'control_change':
            return # Only interested in CC messages

        cc = msg.control
        value = msg.value

        # --- Handle Active Confirmation Prompt ---
        if self.confirmation_prompts.is_active():
            action = self.confirmation_prompts.handle_input(cc, value)
            if action:
                active_prompt_type = self.confirmation_prompts.active_prompt
                self.confirmation_prompts.deactivate() # Deactivate prompt after action

                if action == 'confirm':
                    if active_prompt_type == PromptType.SHUTDOWN:
                        print("Shutdown confirmed, triggering app shutdown.")
                        # Call the App's method to handle cleanup and shutdown
                        self.app.trigger_shutdown()
                    elif active_prompt_type == PromptType.REBOOT:
                        print("Reboot confirmed, triggering app reboot.")
                        self.app.trigger_reboot()
                    elif active_prompt_type == PromptType.STOP_SERVICE: # Added
                        print("Service stop confirmed, triggering service stop.")
                        self.app.trigger_service_stop()
                    elif active_prompt_type == PromptType.RESTART_SERVICE: # Added
                        print("Service restart confirmed, triggering service restart.")
                        self.app.trigger_service_restart()
                elif action == 'cancel':
                    print("Shutdown/Reboot/Service Action cancelled.")
            return # Input was handled by the prompt

        # --- Handle Button State and Combinations (No active prompt) ---
        # Track NO button state
        if cc == mappings.NO_NAV_CC:
            if value == 127:
                self.no_button_held = True
                # print("NO button held") # Debug
            elif value == 0:
                self.no_button_held = False
                # print("NO button released") # Debug
            return # Don't process NO button further for combinations

        # Check for combinations ONLY on button press (value 127) while NO is held
        if self.no_button_held and value == 127:
            if cc == mappings.DELETE_CC:
                print("Shutdown combination detected (NO + DELETE)")
                self.confirmation_prompts.activate(PromptType.SHUTDOWN)
                return # Combination handled
            elif cc == mappings.RENAME_CC:
                print("Reboot combination detected (NO + RENAME)")
                self.confirmation_prompts.activate(PromptType.REBOOT)
                return # Combination handled

        # --- Handle Single Button Presses (No active prompt, NO not held) ---
        if not self.no_button_held and value == 127:
            if cc == mappings.DELETE_CC:
                print("Stop Service button detected (DELETE)")
                self.confirmation_prompts.activate(PromptType.STOP_SERVICE)
                return # Action handled
            elif cc == mappings.RENAME_CC:
                print("Restart Service button detected (RENAME)")
                self.confirmation_prompts.activate(PromptType.RESTART_SERVICE)
                return # Action handled


        # If no combination or prompt was handled, pass to base or do nothing
        # super().handle_midi(msg) # Optional: if base class has MIDI handling

    def cleanup(self):
        """Called when the screen becomes inactive."""
        # Reset button state if screen changes while NO is held
        self.no_button_held = False
        # Deactivate any active prompt if screen changes
        self.confirmation_prompts.deactivate()
        print("PlaceholderScreen cleaned up.")
        super().cleanup() # Call base class cleanup if it exists

    def get_pixel_font(self, size):
        """
        Try to load a pixel font, fall back to default if not available.
        Common pixel fonts on Linux systems: "ProggyClean", "Monospace", "FixedSys"
        """
        try:
            # Try some common pixel fonts that might be available
            font_options = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
                "/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf"
            ]
            
            for font_path in font_options:
                try:
                    return pygame.font.Font(font_path, size)
                except:
                    continue
                    
            # If specific files didn't work, try system fonts by name
            pixely_fonts = ["ProggyClean", "FixedSys", "Courier", "Monospace"]
            for font_name in pixely_fonts:
                try:
                    return pygame.font.SysFont(font_name, size)
                except:
                    continue
                    
            # Fall back to default
            return pygame.font.Font(None, size)
        except Exception as e:
            print(f"Font loading error: {e}")
            return pygame.font.Font(None, size)  # Default font as fallback

