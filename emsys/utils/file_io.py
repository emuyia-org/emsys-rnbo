# emsys/utils/file_io.py
"""
Utility functions for handling Song file input/output using JSON.
"""

import json
import os
import re
from dataclasses import asdict, is_dataclass
from typing import List, Optional, Dict, Any

# Updated to use absolute import
from emsys.core.song import Song, Segment
from emsys.config import settings

# --- Configuration ---

# Define file extension for songs
SONG_EXTENSION = ".song" # Using .song as defined

# Define the directory where song files will be stored.
# Try to get from settings, or fall back to a default path if not found
try:
    SONGS_DIR = settings.SONGS_DIR
except AttributeError:
    # Fall back to default path relative to project root
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    SONGS_DIR = os.path.join(PROJECT_ROOT, "data", "songs")
    print(f"Warning: settings.SONGS_DIR not found. Using default: {SONGS_DIR}")

# Ensure the songs directory exists
os.makedirs(SONGS_DIR, exist_ok=True)

print(f"Using song directory: {SONGS_DIR}")


# --- Helper Functions ---

def sanitize_filename(name: str) -> str:
    """
    Removes characters invalid for filenames and replaces spaces.

    Args:
        name: The original string (e.g., song name).

    Returns:
        A sanitized string suitable for use as a filename base.
    """
    if not name:
        return "untitled"
    # Remove characters that are definitely invalid or problematic
    name = re.sub(r'[\\/*?:"<>|]', '', name)
    # Replace whitespace and consecutive hyphens with a single hyphen
    name = re.sub(r'\s+', '-', name).strip('-')
    name = re.sub(r'-+', '-', name)
    # Ensure it's not empty after sanitization
    return name if name else "untitled"

# --- Core I/O Functions ---

def list_songs(directory: str = SONGS_DIR) -> List[str]:
    """
    Lists available song files (basenames without extension) in the directory.

    Args:
        directory: The directory path to scan. Defaults to SONGS_DIR.

    Returns:
        A sorted list of song basenames (e.g., ["my-song", "another-track"]).
    """
    try:
        files = [f for f in os.listdir(directory) if f.endswith(SONG_EXTENSION)]
        # Return only the base name
        return sorted([os.path.splitext(f)[0] for f in files])
    except FileNotFoundError:
        print(f"Error: Songs directory not found at {directory}")
        return []
    except Exception as e:
        print(f"Error listing songs: {e}")
        return []

def save_song(song: Song, directory: str = SONGS_DIR) -> bool:
    """
    Saves a Song object to a JSON file. The filename is derived from song.name.

    Args:
        song: The Song object to save.
        directory: The directory path to save the file in. Defaults to SONGS_DIR.

    Returns:
        True if saving was successful, False otherwise.
    """
    if not song or not song.name:
        print("Error: Cannot save song with invalid name.")
        return False

    # Use the song's name directly for the filename (as done in load/list)
    filename_base = song.name
    filename = os.path.join(directory, f"{filename_base}{SONG_EXTENSION}")

    try:
        data = song.to_dict()
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Song '{song.name}' saved to {filename}")
        song.dirty = False # Reset dirty flag after successful save
        return True
    except TypeError as e:
        print(f"Error serializing song '{song.name}': {e}")
        return False
    except IOError as e:
        print(f"Error writing song file '{filename}': {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred saving song '{song.name}': {e}")
        return False

def load_song(basename: str, directory: str = SONGS_DIR) -> Optional[Song]:
    """
    Loads a Song object from a JSON file by its base name.

    Args:
        basename: The base name of the song (without extension).
        directory: The directory path where the file is located. Defaults to SONGS_DIR.

    Returns:
        The loaded Song object, or None if loading fails.
    """
    filename = os.path.join(directory, f"{basename}{SONG_EXTENSION}")
    if not os.path.exists(filename):
        print(f"Error: Song file not found: {filename}")
        return None
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        song = Song.from_dict(data)
        # Ensure the loaded song's name matches the filename basename
        # This is important because the filename is the source of truth for listing/loading
        if song.name != basename:
             print(f"Warning: Song name in file ('{song.name}') differs from filename ('{basename}'). Using filename.")
             song.name = basename
        song.dirty = False # Ensure loaded song starts clean (already done in from_dict, but explicit here is fine)
        print(f"Song '{basename}' loaded successfully.")
        return song
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from '{filename}': {e}")
        return None
    except KeyError as e:
        print(f"Error loading song '{basename}': Missing key {e}")
        return None
    except TypeError as e:
        print(f"Error processing song data from '{filename}': {e}")
        return None
    except IOError as e:
        print(f"Error reading song file '{filename}': {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred loading song '{basename}': {e}")
        return None

def rename_song(old_basename: str, new_basename: str, directory: str = SONGS_DIR) -> bool:
    """
    Renames a song file safely.

    Args:
        old_basename: Original name of the song file (without extension).
        new_basename: New name for the song file (without extension).
        directory: Directory containing the song files. Defaults to SONGS_DIR.

    Returns:
        True if rename was successful, False otherwise.
    """
    if not old_basename or not new_basename or old_basename == new_basename:
        print("Error: Invalid names provided for renaming.")
        return False

    # --- Enhanced Validation ---
    # Check for characters typically invalid in filenames across OSes
    # Reusing the pattern from sanitize_filename for the check
    if re.search(r'[\\/*?:"<>|]', new_basename):
         print(f"Error: Invalid characters found in new song name '{new_basename}'.")
         return False
    # Also explicitly disallow '.' as it interferes with extension handling
    if '.' in new_basename:
         print(f"Error: '.' character is not allowed in song base names ('{new_basename}').")
         return False
    # Ensure name isn't just whitespace after potential stripping (though UI should handle this)
    if not new_basename.strip():
        print("Error: New song name cannot be empty or just whitespace.")
        return False
    # --- End Enhanced Validation ---


    old_filename = os.path.join(directory, f"{old_basename}{SONG_EXTENSION}")
    new_filename = os.path.join(directory, f"{new_basename}{SONG_EXTENSION}")

    if not os.path.exists(old_filename):
        print(f"Error: Cannot rename, source file '{old_filename}' does not exist.")
        return False

    if os.path.exists(new_filename):
        print(f"Error: Cannot rename, target file '{new_filename}' already exists.")
        return False

    try:
        os.rename(old_filename, new_filename)
        print(f"Renamed '{old_filename}' to '{new_filename}'")
        return True
    except OSError as e:
        print(f"Error renaming file from '{old_basename}' to '{new_basename}': {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred renaming song: {e}")
        return False

# --- NEW: Function to delete a song file ---
def delete_song(basename: str, directory: str = SONGS_DIR) -> bool:
    """
    Deletes a song file safely.

    Args:
        basename: The base name of the song file to delete (without extension).
        directory: Directory containing the song file. Defaults to SONGS_DIR.

    Returns:
        True if deletion was successful, False otherwise.
    """
    if not basename:
        print("Error: Invalid empty basename provided for deletion.")
        return False

    filename = os.path.join(directory, f"{basename}{SONG_EXTENSION}")

    if not os.path.exists(filename):
        print(f"Error: Cannot delete, file '{filename}' does not exist.")
        return False

    try:
        os.remove(filename)
        print(f"Successfully deleted song file: '{filename}'")
        return True
    except OSError as e:
        # This will catch permission errors, file not found (if it disappeared
        # between the check and remove), etc.
        print(f"Error deleting file '{filename}': {e}")
        return False
    except Exception as e:
        # Catch any other unexpected errors during deletion
        print(f"An unexpected error occurred deleting song '{basename}': {e}")
        return False

# --- Example Usage (for testing this module directly) ---
if __name__ == '__main__':
    print("\n--- Testing file_io Module ---")

    # Ensure the test directory exists
    # Use a dedicated test directory to avoid cluttering the main songs dir
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    TEST_SONGS_DIR = os.path.join(PROJECT_ROOT, "data", "test_songs_io") # Unique name
    print(f"Using test directory: {TEST_SONGS_DIR}")
    # Clean up previous test runs if needed
    if os.path.exists(TEST_SONGS_DIR):
        import shutil
        # Be careful with shutil.rmtree!
        # shutil.rmtree(TEST_SONGS_DIR)
        # print("Cleaned up previous test directory.")
        pass # Or manually clean if preferred
    os.makedirs(TEST_SONGS_DIR, exist_ok=True)

    # 1. Create a dummy song
    print("\n1. Creating Test Song...")
    test_seg1 = Segment(tempo=100.0, loop_length=8, repetitions=2)
    test_seg2 = Segment(program_message_1=5, tempo=140.0, tempo_ramp=1.5, loop_length=16)
    test_song = Song(name="My Test Song 1", segments=[test_seg1, test_seg2]) # Simple name
    print(f"   {test_song}")

    # 2. Save the song
    print("\n2. Saving Test Song...")
    save_success = save_song(test_song, directory=TEST_SONGS_DIR)
    print(f"   Save successful: {save_success}")
    assert save_success

    # 3. List songs
    print("\n3. Listing Songs...")
    available_songs = list_songs(directory=TEST_SONGS_DIR)
    print(f"   Available songs: {available_songs}")
    assert test_song.name in available_songs

    # 4. Load the song
    print("\n4. Loading Test Song...")
    loaded_song = load_song(test_song.name, directory=TEST_SONGS_DIR)
    assert loaded_song is not None
    assert loaded_song.name == test_song.name
    print(f"   Loaded song: {loaded_song.name}")

    # 5. Rename the song
    print("\n5. Renaming Test Song...")
    new_name = "My Renamed Song"
    rename_success = rename_song(test_song.name, new_name, directory=TEST_SONGS_DIR)
    print(f"   Rename successful: {rename_success}")
    assert rename_success
    available_songs = list_songs(directory=TEST_SONGS_DIR)
    print(f"   Available songs after rename: {available_songs}")
    assert test_song.name not in available_songs
    assert new_name in available_songs

    # 6. Try to load by old name (should fail)
    print("\n6. Loading by old name (should fail)...")
    old_load_fail = load_song(test_song.name, directory=TEST_SONGS_DIR)
    assert old_load_fail is None
    print("   Correctly failed to load by old name.")

    # 7. Load by new name (should succeed)
    print("\n7. Loading by new name...")
    renamed_loaded = load_song(new_name, directory=TEST_SONGS_DIR)
    assert renamed_loaded is not None
    assert renamed_loaded.name == new_name # Check name was updated correctly by load_song
    print(f"   Loaded renamed song: {renamed_loaded.name}")

    # 8. Delete the renamed song
    print("\n8. Deleting Renamed Song...")
    delete_success = delete_song(new_name, directory=TEST_SONGS_DIR)
    print(f"   Delete successful: {delete_success}")
    assert delete_success
    available_songs = list_songs(directory=TEST_SONGS_DIR)
    print(f"   Available songs after delete: {available_songs}")
    assert new_name not in available_songs

    # 9. Try to delete non-existent song
    print("\n9. Deleting Non-existent Song...")
    delete_fail = delete_song("does-not-exist", directory=TEST_SONGS_DIR)
    print(f"   Delete non-existent returned: {delete_fail}")
    assert not delete_fail # Should return False

    # 10. Test saving song with invalid chars in name (should use sanitized name for file)
    # print("\n10. Saving song with invalid chars...")
    # invalid_char_song = Song(name="Inv@lid / N?me*", segments=[Segment()])
    # save_invalid = save_song(invalid_char_song, directory=TEST_SONGS_DIR)
    # assert save_invalid
    # sanitized = sanitize_filename(invalid_char_song.name)
    # assert sanitized in list_songs(directory=TEST_SONGS_DIR)
    # print(f"   Saved '{invalid_char_song.name}' as '{sanitized}{SONG_EXTENSION}'")
    # # Clean up this file
    # delete_song(sanitized, directory=TEST_SONGS_DIR)

    print("\n--- file_io Testing Complete ---")
    # Consider removing the test directory after tests if desired
    # shutil.rmtree(TEST_SONGS_DIR)
    # print("Removed test directory.")

