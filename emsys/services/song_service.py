# emsys/services/song_service.py
# -*- coding: utf-8 -*-
"""
Service layer for managing Song objects, including loading, saving,
and modification operations, centralizing song state management.
"""

from typing import Optional, List, Any, Tuple
import os
import traceback
import math
import logging # Ensure logging is imported
import json    # Ensure json is imported at the top

logger = logging.getLogger(__name__) # Ensure logger is initialized


# Use absolute imports
from emsys.core.song import Song, Segment
from emsys.utils import file_io
from emsys.config import settings

# --- Helper Function ---
def _format_duration(total_seconds: float) -> str:
    """Formats total seconds into 'Xhr Xm Xs' string."""
    if total_seconds < 0:
        return "??hr ??m ??s"
    total_seconds = math.ceil(total_seconds) # Round up to nearest second
    
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    
    if hours > 0:
        return f"{hours}hr {minutes}m {seconds}s"
    elif minutes > 0: # If less than an hour but more than 0 minutes
        return f"{minutes}m {seconds}s"
    else: # If less than a minute
        return f"{seconds}s"
# --- End Helper ---


class SongService:
    """Manages the lifecycle and state of the current song."""

    def __init__(self, status_callback=None):
        """Initialize the SongService."""
        self.current_song: Optional[Song] = None
        self.last_loaded_song_name: Optional[str] = None # Store the name used for loading/saving
        self._status_callback = status_callback if status_callback else lambda msg: print(f"SongService Status: {msg}")
        self._initialize_with_last_song() # Load preference and attempt load

    # --- Current Song State Management ---

    def get_current_song(self) -> Optional[Song]:
        """Returns the currently loaded Song object."""
        return self.current_song

    def is_current_song_dirty(self) -> bool:
        """Checks if the current song has unsaved changes."""
        return self.current_song is not None and self.current_song.dirty

    def get_current_song_name(self) -> Optional[str]:
        """Returns the name of the currently loaded song."""
        return self.current_song.name if self.current_song else None

    def get_current_song_duration_str(self) -> str:
        """
        Calculates and returns the estimated duration of the current song
        formatted as 'Xhr Xm Xs'. Returns '??hr ??m ??s' if no song is loaded or
        calculation fails.
        """
        if self.current_song:
            try:
                duration_seconds = self.current_song.calculate_estimated_duration()
                return _format_duration(duration_seconds)
            except Exception as e:
                print(f"Error calculating song duration: {e}")
                return "??hr ??m ??s" # <<< Updated fallback format
        else:
            return "??hr ??m ??s" # <<< Updated fallback format

    def _set_current_song(self, song: Optional[Song], name_used_for_load: Optional[str] = None):
        """Internal method to update the current song and related state."""
        self.current_song = song
        # If a song is successfully loaded or created, store its name
        self.last_loaded_song_name = name_used_for_load if song else None
        # Save the preference whenever the current song changes significantly
        if song:
            self._save_last_song_preference(song.name)
        else:
             self._save_last_song_preference(None) # Clear preference if no song

        status = f"Current song set to: {song.name}" if song else "Current song cleared."
        self._status_callback(status)

    # --- Song Loading ---

    def load_song_by_name(self, basename: str) -> Tuple[bool, str]:
        """
        Loads a song by its basename and sets it as the current song.
        Checks for unsaved changes in the *existing* current song *before* loading.

        Args:
            basename: The basename of the song to load.

        Returns:
            A tuple (success: bool, message: str). Success is True if loaded.
        """
        # Allow loading even if dirty *if* it's the initial load during __init__
        # Check if current_song is None to detect initial state
        if self.current_song is not None and self.is_current_song_dirty():
            # This case should ideally be handled by the UI asking the user first.
            # If called directly, we prevent overwriting dirty data.
            msg = f"Cannot load '{basename}'. Current song '{self.current_song.name}' has unsaved changes."
            self._status_callback(msg)
            print(f"Error: {msg}")
            return False, msg

        self._status_callback(f"Loading song '{basename}'...")
        loaded_song = file_io.load_song(basename)

        if loaded_song:
            self._set_current_song(loaded_song, basename) # Update internal state
            msg = f"Successfully loaded '{basename}'."
            self._status_callback(msg)
            return True, msg
        else:
            msg = f"Failed to load song '{basename}'."
            self._status_callback(msg)
            # Do not clear current song if loading fails
            return False, msg

    # --- Song Saving ---

    def save_current_song(self) -> Tuple[bool, str]:
        """
        Saves the current song to disk using its current name.
        Resets the dirty flag on success.
        """
        if self.current_song is None:
            msg = "No current song to save."
            self._status_callback(msg)
            return False, msg

        if not self.current_song.dirty:
            msg = f"'{self.current_song.name}' has no changes to save."
            # self._status_callback(msg) # Maybe too noisy?
            return True, msg # Nothing to do, considered success

        self._status_callback(f"Saving '{self.current_song.name}'...")
        success = file_io.save_song(self.current_song)

        if success:
            # file_io.save_song sets song.dirty = False
            # Clear segment flags as well after successful save
            self.current_song.clear_segment_dirty_flags()
            msg = f"Successfully saved '{self.current_song.name}'."
            self._status_callback(msg)
            return True, msg
        else:
            # Error message printed by file_io.save_song
            msg = f"Failed to save '{self.current_song.name}'."
            self._status_callback(msg)
            return False, msg

    # --- Song Creation ---

    def create_new_song(self, new_name: str) -> Tuple[bool, str]:
        """
        Creates a new, empty song file, saves it, and sets it as the current song.
        Checks for unsaved changes before proceeding.

        Args:
            new_name: The desired name for the new song.

        Returns:
            A tuple (success: bool, message: str). Success is True if created and set.
        """
        if self.is_current_song_dirty():
            msg = f"Cannot create new song. Current song '{self.current_song.name}' has unsaved changes."
            self._status_callback(msg)
            print(f"Error: {msg}")
            return False, msg

        # Basic validation before creating Song object (redundant with UI checks but safe)
        if not new_name or not new_name.strip():
             msg = "Cannot create song with empty name."
             self._status_callback(msg)
             return False, msg
        # Ensure name doesn't already exist (using stripped name)
        clean_name = new_name.strip()
        if clean_name in self.list_song_names():
            msg = f"Cannot create song. Name '{clean_name}' already exists."
            self._status_callback(msg)
            return False, msg

        self._status_callback(f"Creating new song '{clean_name}'...")
        try:
            new_song = Song(name=clean_name) # Create empty song object with cleaned name

            # --- REMOVED CHECK ---
            # Verify the name attribute immediately after creation
            # if not new_song.name:
            #     msg = f"Error: Song object created with invalid name ('{new_song.name}') from input '{clean_name}'. Cannot proceed."
            #     self._status_callback(msg)
            #     print(f"Critical Error: {msg}")
            #     return False, msg
            # --- END REMOVED CHECK ---

            # Save the new empty song immediately
            if file_io.save_song(new_song):
                # Now set it as current
                self._set_current_song(new_song, new_song.name) # Use name from object
                msg = f"Created and loaded new song '{new_song.name}'."
                self._status_callback(msg)
                return True, msg
            else:
                # file_io.save_song prints its own error, use a generic message here
                msg = f"Failed to save new song '{clean_name}' during creation."
                self._status_callback(msg)
                return False, msg
        except Exception as e:
            msg = f"Error creating song '{clean_name}': {e}"
            self._status_callback(msg)
            traceback.print_exc()
            return False, msg

    # --- Song File Operations ---

    def list_song_names(self) -> List[str]:
        """Returns a list of available song basenames."""
        return file_io.list_songs()

    def rename_song_file(self, old_basename: str, new_basename: str) -> Tuple[bool, str]:
        """
        Renames a song file on disk AND updates the 'name' field within the song data.
        If the renamed song was the current song, updates the current song's name.
        """
        self._status_callback(f"Attempting to rename '{old_basename}' to '{new_basename}'...")

        # 1. Rename the file first
        rename_success = file_io.rename_song(old_basename, new_basename)

        if not rename_success:
            # file_io.rename_song should have logged/printed the error
            msg = f"Failed to rename file '{old_basename}' to '{new_basename}'."
            self._status_callback(msg)
            return False, msg

        # 2. If file rename succeeded, load the song from the NEW path
        logger.info(f"Service: File renamed. Loading '{new_basename}' to update internal name.")
        song_to_update = file_io.load_song(new_basename)

        if not song_to_update:
            # This is bad - rename succeeded but we can't load the renamed file.
            # Maybe try to rename back? For now, report error.
            msg = f"Error: Renamed file to '{new_basename}' but failed to reload it to update content."
            logger.error(msg)
            self._status_callback(msg)
            # Consider attempting to rename back to old_basename here as a recovery step.
            # file_io.rename_song(new_basename, old_basename) # Example recovery attempt
            return False, msg

        # 3. Update the name *within* the loaded song object
        logger.info(f"Service: Loaded song '{song_to_update.name}'. Setting internal name to '{new_basename}'.")
        song_to_update.name = new_basename
        song_to_update.dirty = True # Mark it dirty to force saving the name change

        # 4. Save the song object back to the NEW path (overwriting the renamed file)
        logger.info(f"Service: Saving song with updated internal name to '{new_basename}'.")
        save_success = file_io.save_song(song_to_update) # Save with the new name

        if not save_success:
            # file_io.save_song logs its own errors
            msg = f"Error: Renamed file to '{new_basename}' but failed to save updated content."
            logger.error(msg)
            self._status_callback(msg)
            # File exists with new name but old content. Not ideal.
            return False, msg

        logger.info(f"Service: Successfully updated internal name and saved '{new_basename}'.")

        # 5. Update current song state if necessary (as before)
        if self.current_song and self.last_loaded_song_name == old_basename:
             # The current song object might be the same one we just loaded and saved,
             # or it might be a different instance if it wasn't loaded recently.
             # Safest is to ensure the current_song reference has the correct name.
             self.current_song.name = new_basename
             self.last_loaded_song_name = new_basename # Update tracking name
             self._save_last_song_preference(new_basename) # Update preference
             msg = f"Renamed to '{new_basename}' and updated current song."
             self._status_callback(msg)
             return True, msg
        else:
             # Renamed song wasn't the current one, just report success
             msg = f"Successfully renamed '{old_basename}' to '{new_basename}'."
             self._status_callback(msg)
             return True, msg

    def delete_song_file(self, basename: str) -> Tuple[bool, str]:
        """
        Deletes a song file from disk.
        If the deleted song was the current song, clears the current song state.
        """
        self._status_callback(f"Attempting to delete '{basename}'...")
        success = file_io.delete_song(basename)
        if success:
            # Check if the deleted song was the currently loaded one
            if self.current_song and self.last_loaded_song_name == basename:
                self._set_current_song(None, None) # Clear current song state
                msg = f"Deleted '{basename}' and cleared current song."
                self._status_callback(msg)
                return True, msg
            else:
                msg = f"Successfully deleted '{basename}'."
                self._status_callback(msg)
                return True, msg
        else:
            msg = f"Failed to delete '{basename}'."
            self._status_callback(msg)
            return False, msg

    def duplicate_song(self, original_basename: str, new_basename: str) -> Tuple[bool, str]:
        """
        Duplicates a song file by loading the original, changing its name, and saving it.

        Args:
            original_basename: The basename of the song to duplicate.
            new_basename: The desired basename for the duplicated song.

        Returns:
            A tuple (success: bool, message: str).
        """
        logger.info(f"Service: Starting duplication from '{original_basename}' to '{new_basename}'.") # <<< ADD Log
        self._status_callback(f"Attempting to duplicate '{original_basename}' as '{new_basename}'...")

        # Check if the new name already exists
        if new_basename in self.list_song_names():
            msg = f"Cannot duplicate: Name '{new_basename}' already exists."
            logger.error(msg) # <<< ADD Log
            self._status_callback(msg)
            return False, msg

        # Load the original song data
        logger.info(f"Service: Loading original song '{original_basename}' for duplication.") # <<< ADD Log
        original_song = file_io.load_song(original_basename)
        if not original_song:
            msg = f"Cannot duplicate: Failed to load original song '{original_basename}'."
            logger.error(msg) # <<< ADD Log
            self._status_callback(msg)
            return False, msg
        logger.info(f"Service: Original song '{original_basename}' loaded successfully.") # <<< ADD Log

        try:
            # Create a new Song object for the duplicate
            logger.info("Service: Creating new Song object from original's dict.") # <<< ADD Log
            duplicate_song = Song.from_dict(original_song.to_dict()) # Create from dict to ensure clean state
            logger.info(f"Service: Initial name of duplicate object: '{duplicate_song.name}'") # <<< ADD Log

            # Set the new name
            duplicate_song.name = new_basename # Set the new name
            logger.info(f"Service: Name attribute of duplicate object set to: '{duplicate_song.name}'") # <<< ADD Log

            duplicate_song.dirty = True # Mark the new duplicate as needing saving

            # <<< ADD Log: Check name and dict just before saving >>>
            try:
                dict_to_save = duplicate_song.to_dict()
                logger.info(f"Service: BEFORE save_song - Object name: '{duplicate_song.name}', Dict name: '{dict_to_save.get('name')}'")
                logger.debug(f"Service: BEFORE save_song - Full dict: {json.dumps(dict_to_save)}")
            except Exception as log_err:
                logger.error(f"Service: Error logging dict before save: {log_err}")
            # <<< END Log >>>

            # Save the duplicated song
            save_success = file_io.save_song(duplicate_song)

            if save_success:
                # file_io.save_song resets dirty flag on the saved object
                msg = f"Successfully duplicated '{original_basename}' to '{new_basename}'."
                logger.info(f"Service: {msg}") # <<< ADD Log
                self._status_callback(msg)
                return True, msg
            else:
                # file_io.save_song prints its own error
                msg = f"Failed to save duplicated song '{new_basename}'."
                logger.error(f"Service: {msg} (file_io.save_song returned False)") # <<< ADD Log
                self._status_callback(msg)
                return False, msg
        except Exception as e:
            msg = f"Error during duplication of '{original_basename}': {e}"
            logger.exception(f"Service: {msg}") # <<< Use logger.exception
            self._status_callback(msg)
            traceback.print_exc()
            return False, msg


    # --- Current Song Segment/Parameter Modification ---

    def add_segment_to_current(self, segment: Segment, index: Optional[int] = None) -> Tuple[bool, str]:
        """Adds a segment to the current song."""
        if not self.current_song:
            return False, "No current song loaded."
        try:
            self.current_song.add_segment(segment, index)
            # Add segment marks song as dirty
            msg = f"Added segment at index {index if index is not None else len(self.current_song.segments)}."
            # self._status_callback(msg) # Maybe too noisy for segment edits?
            return True, msg
        except (TypeError, IndexError, Exception) as e:
            msg = f"Error adding segment: {e}"
            self._status_callback(msg)
            traceback.print_exc()
            return False, msg

    def remove_segment_from_current(self, index: int) -> Tuple[bool, str]:
        """Removes a segment from the current song."""
        if not self.current_song:
            return False, "No current song loaded."
        try:
            self.current_song.remove_segment(index)
            # Remove segment marks song as dirty
            msg = f"Removed segment at index {index}."
            # self._status_callback(msg)
            return True, msg
        except (IndexError, Exception) as e:
            msg = f"Error removing segment: {e}"
            self._status_callback(msg)
            traceback.print_exc()
            return False, msg

    def update_segment_in_current(self, index: int, **kwargs) -> Tuple[bool, str]:
        """Updates parameters of a segment in the current song."""
        if not self.current_song:
            return False, "No current song loaded."
        try:
            # This method in Song handles setting dirty flags
            self.current_song.update_segment(index, **kwargs)
            msg = f"Updated parameters for segment {index}."
            # Check if update actually happened (song.update_segment marks dirty flags)
            if self.current_song.dirty: # Or check segment.dirty?
                 # self._status_callback(msg)
                 pass
            return True, msg
        except (IndexError, AttributeError, TypeError, ValueError, Exception) as e:
            msg = f"Error updating segment {index}: {e}"
            self._status_callback(msg)
            traceback.print_exc()
            return False, msg

    def discard_changes_current_song(self):
        """Discards unsaved changes by reloading the current song from disk."""
        if self.current_song and self.last_loaded_song_name:
            name_to_reload = self.last_loaded_song_name
            self._status_callback(f"Discarding changes by reloading '{name_to_reload}'...")
            # Force clear current song *before* reloading to bypass dirty check
            self._set_current_song(None, None)
            success, msg = self.load_song_by_name(name_to_reload)
            if success:
                self._status_callback(f"Changes discarded for '{name_to_reload}'.")
            else:
                 self._status_callback(f"Error reloading '{name_to_reload}' after discard attempt: {msg}")
        elif self.current_song:
            # If it's a new, unsaved song, just clear it
             self._status_callback("Discarding new unsaved song.")
             self._set_current_song(None, None)
        else:
             self._status_callback("No current song or changes to discard.")

    # --- Last Song Preference (Simple text file storage) ---

    def _initialize_with_last_song(self):
        """Loads the last song name preference and attempts to load the song."""
        last_song_file = self._get_last_song_file_path()
        preferred_name = None
        if os.path.exists(last_song_file):
            try:
                with open(last_song_file, "r") as f:
                    last_song_basename = f.read().strip()
                if last_song_basename:
                    print(f"SongService: Last session preference: '{last_song_basename}'")
                    preferred_name = last_song_basename
                else:
                    print("SongService: Last session preference file was empty.")
            except Exception as e:
                print(f"SongService: Error reading last song name preference: {e}")
        else:
            print("SongService: No last song preference file found.")

        if preferred_name:
            print(f"SongService: Attempting initial load of '{preferred_name}'...")
            # Call load_song_by_name, bypassing dirty check logic for init
            success, msg = self.load_song_by_name(preferred_name)
            if not success:
                print(f"SongService: Initial load of '{preferred_name}' failed: {msg}")
                # Optionally clear the preference if the file is missing/corrupt?
                # self._save_last_song_preference(None)
        else:
            # No preference found or error reading it
            pass # No initial song to load

    def _get_last_song_file_path(self) -> str:
        """Gets the path to the file storing the last loaded song name."""
        # Assuming PROJECT_ROOT is accessible via settings
        return os.path.join(settings.PROJECT_ROOT, "last_song.txt")

    def _save_last_song_preference(self, song_name: Optional[str]):
        """Saves the current song name preference to the file."""
        last_song_file = self._get_last_song_file_path()
        try:
            if song_name:
                with open(last_song_file, "w") as f:
                    f.write(song_name)
                # print(f"SongService: Saved last song name preference: '{song_name}'")
            elif os.path.exists(last_song_file):
                # If no song name, remove the preference file
                os.remove(last_song_file)
                # print("SongService: Removed last song name preference file.")
        except Exception as e:
            print(f"SongService: Error saving last song name preference: {e}")

    def get_preferred_song_name(self) -> Optional[str]:
        """Reads and returns the song name stored in the preference file, or None."""
        last_song_file = self._get_last_song_file_path()
        if os.path.exists(last_song_file):
            try:
                with open(last_song_file, "r") as f:
                    last_song_basename = f.read().strip()
                return last_song_basename if last_song_basename else None
            except Exception as e:
                print(f"SongService: Error reading preference file for get_preferred_song_name: {e}")
                return None
        return None


# --- Helper Function ---
def _format_duration(total_seconds: float) -> str:
    """Formats total seconds into 'Xhr Xm Xs' string."""
    if total_seconds < 0:
        return "??hr ??m ??s"
    total_seconds = math.ceil(total_seconds) # Round up to nearest second
    
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    
    if hours > 0:
        return f"{hours}hr {minutes}m {seconds}s"
    elif minutes > 0: # If less than an hour but more than 0 minutes
        return f"{minutes}m {seconds}s"
    else: # If less than a minute
        return f"{seconds}s"
# --- End Helper ---
