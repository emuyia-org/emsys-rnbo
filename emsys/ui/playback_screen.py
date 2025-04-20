# emsys/ui/playback_screen.py
# -*- coding: utf-8 -*-
"""
Screen dedicated to displaying playback status information.
"""

import pygame
from typing import Optional

from .base_screen import BaseScreen
from ..config.settings import WHITE, BLACK, GREY, RED, GREEN # Import colors

class PlaybackScreen(BaseScreen):
    """Displays the current playback state of the loaded song."""

    def __init__(self, app):
        super().__init__(app)
        self.font_large = self.get_pixel_font(48) # Larger font for status
        self.font_medium = self.get_pixel_font(36)
        self.font_small = self.get_pixel_font(24)
        self.title_text = "Playback Status"

    def init(self):
        """Called when the screen becomes active."""
        super().init()
        print(f"{self.__class__.__name__} is now active.")
        # No specific init needed for this simple display screen

    def cleanup(self):
        """Called when the screen becomes inactive."""
        super().cleanup()
        print(f"{self.__class__.__name__} is being deactivated.")
        # No specific cleanup needed

    def draw(self, screen_surface: pygame.Surface,
             midi_status: Optional[str] = None, # Keep signature consistent
             song_status: Optional[str] = None,
             duration_status: Optional[str] = None,
             playback_status: Optional[str] = None,
             osc_status: Optional[str] = None,
             tempo_status: Optional[str] = None):     # <<< ADD tempo_status parameter >>>
        """Draws the playback status information."""
        screen_width = screen_surface.get_width()
        screen_height = screen_surface.get_height()
        screen_surface.fill(BLACK)

        # --- Draw Title ---
        title_surf = self.font_medium.render(self.title_text, True, WHITE)
        title_rect = title_surf.get_rect(centerx=screen_width // 2, top=20)
        screen_surface.blit(title_surf, title_rect)

        # --- Draw Current Song Name ---
        song_name_text = song_status or "Song: -" # Get from passed status
        song_surf = self.font_small.render(song_name_text, True, GREY)
        song_rect = song_surf.get_rect(centerx=screen_width // 2, top=title_rect.bottom + 10)
        screen_surface.blit(song_surf, song_rect)

        # --- Draw Tempo ---
        tempo_text = tempo_status or "Tempo: -" # Get from passed status
        tempo_surf = self.font_small.render(tempo_text, True, GREY)
        tempo_rect = tempo_surf.get_rect(centerx=screen_width // 2, top=song_rect.bottom + 5) # Position below song
        screen_surface.blit(tempo_surf, tempo_rect)

        # --- Draw Playback Status ---
        play_status_text = playback_status or "Playback: -"
        parts = play_status_text.split(' ')
        # <<< ADD DEBUG PRINT FOR PARTS >>>
        # print(f"DEBUG PlaybackScreen: Split parts = {parts}")

        play_symbol = "?"
        seg_text = "Seg: -/-"
        rep_text = "Rep: -/-"
        beat_text = "Beat: -" # Default

        # <<< CORRECTED PARSING LOGIC >>>
        if len(parts) >= 2:
            play_symbol = parts[1] # ">" or "||"
        if len(parts) >= 3:
            seg_text = parts[2] # "Seg:X/Y"
        if len(parts) >= 4:
            rep_text = parts[3] # "Rep:A/B"
        if len(parts) >= 5:
            beat_text = parts[4] # "Beat:Z"
        else:
            # This else might not be needed if default covers it, but keep for debug
            print(f"DEBUG PlaybackScreen: Not enough parts ({len(parts)}) to parse beat from '{play_status_text}'")
        # <<< END CORRECTED PARSING LOGIC >>>

        # Display components
        y_start = tempo_rect.bottom + 30 # <<< Adjust y_start based on tempo_rect >>>
        line_spacing = 45

        # Play/Stop Symbol
        play_color = GREEN if play_symbol == ">" else RED
        play_surf = self.font_large.render(play_symbol, True, play_color)
        play_rect = play_surf.get_rect(centerx=screen_width // 2, top=y_start)
        screen_surface.blit(play_surf, play_rect)

        # Segment Info
        seg_surf = self.font_medium.render(seg_text, True, WHITE)
        seg_rect = seg_surf.get_rect(centerx=screen_width // 2, top=play_rect.bottom + line_spacing)
        screen_surface.blit(seg_surf, seg_rect)

        # Repetition Info
        rep_surf = self.font_medium.render(rep_text, True, WHITE)
        rep_rect = rep_surf.get_rect(centerx=screen_width // 2, top=seg_rect.bottom + line_spacing)
        screen_surface.blit(rep_surf, rep_rect) # <<< Draws Rep info >>>

        # Beat Count Info
        beat_surf = self.font_medium.render(beat_text, True, WHITE)
        beat_rect = beat_surf.get_rect(centerx=screen_width // 2, top=rep_rect.bottom + line_spacing)
        screen_surface.blit(beat_surf, beat_rect) # <<< Draws Beat info >>>

    def handle_midi(self, msg):
        """Playback screen doesn't handle specific MIDI input currently."""
        # Transport controls are handled globally in App
        pass

    def get_pixel_font(self, size):
        """Helper to load pixel font (copied from PlaceholderScreen)."""
        try:
            font_options = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
                "/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf"
            ]
            for font_path in font_options:
                try: return pygame.font.Font(font_path, size)
                except: continue
            pixely_fonts = ["ProggyClean", "FixedSys", "Courier", "Monospace"]
            for font_name in pixely_fonts:
                try: return pygame.font.SysFont(font_name, size)
                except: continue
            return pygame.font.Font(None, size)
        except Exception as e:
            print(f"Font loading error: {e}")
            return pygame.font.Font(None, size)
