# emsys/ui/placeholder_screen.py

import pygame
import time # Import the time module
import random # Import random module for randomizing animation timing
import subprocess # Import subprocess to run git command
from emsys.ui.base_screen import BaseScreen
# Import necessary colors
from emsys.config.settings import WHITE, GREEN, YELLOW, RED, GREY #, SCREEN_WIDTH, SCREEN_HEIGHT

class PlaceholderScreen(BaseScreen):
    """
    A simple placeholder screen displaying basic info, a MIDI status indicator,
    a persistent winking animation, and the Git commit ID.
    """
    def __init__(self, app):
        # Initialize the BaseScreen (sets self.app and self.font)
        super().__init__(app)

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
        self.last_cycle_start_time = time.time()
        # --- End Persistent Animation ---

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

    def draw(self, screen, midi_status=None, song_status=None):
        """Draw the placeholder content with a MIDI status indicator, song status and animation."""
        # Get screen dimensions dynamically
        screen_width = screen.get_width()
        screen_height = screen.get_height()

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
            rect_to_use.centerx = screen_width // 2
            rect_to_use.centery = screen_height // 3
            screen.blit(kaomoji_to_draw, rect_to_use)

            # --- Draw Title Below Kaomoji ---
            # Position title centered horizontally, below the kaomoji rect
            self.title_rect.centerx = screen_width // 2
            self.title_rect.top = rect_to_use.bottom + 10 # Add 10px padding
            screen.blit(self.title_surf, self.title_rect)
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
        indicator_pos = (screen_width - self.indicator_padding - self.indicator_radius,
                         self.indicator_padding + self.indicator_radius)

        # Draw the indicator circle
        pygame.draw.circle(screen, indicator_color, indicator_pos, self.indicator_radius)

        # --- Draw Git Commit ID ---
        # Position commit ID in the bottom-left corner
        self.commit_rect.bottomleft = (self.indicator_padding, screen_height - self.indicator_padding)
        screen.blit(self.commit_surf, self.commit_rect)
        # --- End Draw Git Commit ID ---

        # Additional rendering for song_status can be added here if needed.
        # ...

    # Implement other methods like handle_event, handle_midi, update if needed
    # ...

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

