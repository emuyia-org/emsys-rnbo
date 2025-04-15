# emsys/ui/helpers/confirmation_prompts.py
# -*- coding: utf-8 -*-
"""
Handles state and drawing for confirmation prompts used in screens like SongManagerScreen.
"""
import pygame
from typing import Optional, Tuple, Callable, Any
from enum import Enum, auto

# Use absolute imports
from emsys.config import settings, mappings

# --- Define Prompt Types ---
class PromptType(Enum):
    NONE = auto()
    DELETE_SONG = auto()
    UNSAVED_LOAD = auto()
    UNSAVED_CREATE = auto()

class ConfirmationPrompts:
    """Manages the state and drawing of various confirmation prompts."""

    def __init__(self, app_ref: Any):
        """
        Initialize the prompt handler.

        Args:
            app_ref: Reference to the main application (for fonts, screen size).
        """
        self.app = app_ref
        self.active_prompt: PromptType = PromptType.NONE
        self.prompt_data: Optional[Any] = None # Store context (e.g., song name)

        # Fonts (assuming app_ref provides access or pre-initialized fonts)
        # These could be passed in or accessed via app_ref.font_large etc.
        self.font_large = pygame.font.Font(None, 48)
        self.font = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)


    def is_active(self) -> bool:
        """Check if any prompt is currently active."""
        return self.active_prompt != PromptType.NONE

    def activate(self, prompt_type: PromptType, data: Optional[Any] = None):
        """Activate a specific prompt."""
        if not isinstance(prompt_type, PromptType):
            print("Error: Invalid prompt type passed to activate.")
            return
        print(f"Activating prompt: {prompt_type.name} with data: {data}")
        self.active_prompt = prompt_type
        self.prompt_data = data

    def deactivate(self):
        """Deactivate the current prompt."""
        # print(f"Deactivating prompt: {self.active_prompt.name}")
        self.active_prompt = PromptType.NONE
        self.prompt_data = None

    def handle_input(self, cc: int, value: int) -> Optional[str]:
        """
        Handles MIDI input when a prompt is active.

        Args:
            cc: The MIDI CC number.
            value: The MIDI CC value.

        Returns:
            A string representing the action chosen ('confirm', 'discard', 'cancel'),
            or None if the input didn't correspond to an action for the active prompt.
        """
        if not self.is_active() or value != 127: # Only handle button presses
            return None

        action = None
        if self.active_prompt == PromptType.DELETE_SONG:
            if cc == mappings.YES_NAV_CC: action = 'confirm'
            elif cc == mappings.NO_NAV_CC: action = 'cancel'
        elif self.active_prompt in [PromptType.UNSAVED_LOAD, PromptType.UNSAVED_CREATE]:
            if cc == mappings.SAVE_CC: action = 'confirm'    # Corresponds to "Save Changes?"
            elif cc == mappings.DELETE_CC: action = 'discard'   # Corresponds to "Discard Changes?"
            elif cc == mappings.NO_NAV_CC: action = 'cancel'     # Corresponds to "Cancel Operation?"

        # if action: print(f"Prompt action selected: {action}") # Debug
        return action


    def draw(self, surface: pygame.Surface):
        """Draws the currently active prompt."""
        if not self.is_active():
            return

        # Draw semi-transparent overlay
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        # Call specific drawing method based on active prompt
        if self.active_prompt == PromptType.DELETE_SONG:
            self._draw_delete_confirmation(surface)
        elif self.active_prompt == PromptType.UNSAVED_LOAD:
            self._draw_unsaved_prompt(surface, "Load Song")
        elif self.active_prompt == PromptType.UNSAVED_CREATE:
             self._draw_unsaved_prompt(surface, "Create Song")
        # Add other prompt drawing methods if needed


    def _draw_delete_confirmation(self, surface: pygame.Surface):
        """Draws the delete confirmation dialog."""
        box_width, box_height = 400, 150
        box_x = (surface.get_width() - box_width) // 2
        box_y = (surface.get_height() - box_height) // 2
        pygame.draw.rect(surface, settings.BLACK, (box_x, box_y, box_width, box_height))
        pygame.draw.rect(surface, settings.RED, (box_x, box_y, box_width, box_height), 2)

        title_surf = self.font_large.render("Confirm Delete", True, settings.RED)
        title_rect = title_surf.get_rect(midtop=(surface.get_width() // 2, box_y + 15))
        surface.blit(title_surf, title_rect)

        song_name = self.prompt_data if isinstance(self.prompt_data, str) else "Error"
        song_surf = self.font.render(f"'{song_name}'", True, settings.WHITE)
        song_rect = song_surf.get_rect(midtop=(surface.get_width() // 2, title_rect.bottom + 10))
        surface.blit(song_surf, song_rect)

        yes_btn = mappings.button_map.get(mappings.YES_NAV_CC, f"CC{mappings.YES_NAV_CC}")
        no_btn = mappings.button_map.get(mappings.NO_NAV_CC, f"CC{mappings.NO_NAV_CC}")
        instr_surf = self.font.render(f"Confirm: {yes_btn} | Cancel: {no_btn}", True, settings.WHITE)
        instr_rect = instr_surf.get_rect(midbottom=(surface.get_width() // 2, box_y + box_height - 15))
        surface.blit(instr_surf, instr_rect)

    def _draw_unsaved_prompt(self, surface: pygame.Surface, context: str):
        """Draws the unsaved changes prompt dialog."""
        box_width, box_height = 400, 200
        box_x = (surface.get_width() - box_width) // 2
        box_y = (surface.get_height() - box_height) // 2
        pygame.draw.rect(surface, settings.BLACK, (box_x, box_y, box_width, box_height))
        pygame.draw.rect(surface, settings.BLUE, (box_x, box_y, box_width, box_height), 2)

        title_surf = self.font_large.render("Unsaved Changes", True, settings.BLUE)
        title_rect = title_surf.get_rect(midtop=(surface.get_width() // 2, box_y + 15))
        surface.blit(title_surf, title_rect)

        # Get current song name from app state if possible
        song_name = "Error"
        current_song = getattr(self.app, 'current_song', None)
        if current_song and hasattr(current_song, 'name'):
            song_name = current_song.name

        song_surf = self.font.render(f"in '{song_name}'", True, settings.WHITE)
        song_rect = song_surf.get_rect(midtop=(surface.get_width() // 2, title_rect.bottom + 10))
        surface.blit(song_surf, song_rect)

        save_btn = mappings.button_map.get(mappings.SAVE_CC, f"CC{mappings.SAVE_CC}")
        discard_btn = mappings.button_map.get(mappings.DELETE_CC, f"CC{mappings.DELETE_CC}")
        cancel_btn = mappings.button_map.get(mappings.NO_NAV_CC, f"CC{mappings.NO_NAV_CC}")

        instr1_text = f"Save Changes? ({save_btn})"
        instr2_text = f"Discard Changes? ({discard_btn})"
        instr3_text = f"Cancel {context}? ({cancel_btn})"

        instr1_surf = self.font.render(instr1_text, True, settings.GREEN)
        instr1_rect = instr1_surf.get_rect(midtop=(surface.get_width() // 2, song_rect.bottom + 20))
        surface.blit(instr1_surf, instr1_rect)

        instr2_surf = self.font.render(instr2_text, True, settings.RED)
        instr2_rect = instr2_surf.get_rect(midtop=(surface.get_width() // 2, instr1_rect.bottom + 10))
        surface.blit(instr2_surf, instr2_rect)

        instr3_surf = self.font.render(instr3_text, True, settings.WHITE)
        instr3_rect = instr3_surf.get_rect(midtop=(surface.get_width() // 2, instr2_rect.bottom + 10))
        surface.blit(instr3_surf, instr3_rect)
