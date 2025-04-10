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
SONG_EXTENSION = ".song"

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
    Saves a Song object to a JSON file.

    Args:
        song: The Song object to save.
        directory: The directory path to save the file in. Defaults to SONGS_DIR.

    Returns:
        True if saving was successful, False otherwise.
    """
    if not song or not song.name:
        print("Error: Cannot save song with invalid name.")
        return False
    
    filename = os.path.join(directory, f"{song.name}{SONG_EXTENSION}")
    try:
        data = song.to_dict()
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Song '{song.name}' saved to {filename}")
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
        if song.name != basename:
             print(f"Warning: Song name in file ('{song.name}') differs from filename ('{basename}'). Using filename.")
             song.name = basename
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

# --- NEW: Function to rename a song file ---
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
    if '/' in new_basename or '\\' in new_basename or '.' in new_basename:
         print(f"Error: Invalid characters in new song name '{new_basename}'.")
         return False

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

# --- Example Usage (for testing this module directly) ---
if __name__ == '__main__':
    print("\n--- Testing file_io Module ---")

    # Ensure the test directory exists
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    TEST_SONGS_DIR = os.path.join(PROJECT_ROOT, "data", "test_songs")
    print(f"Using test directory: {TEST_SONGS_DIR}")
    if not os.path.exists(TEST_SONGS_DIR):
        os.makedirs(TEST_SONGS_DIR, exist_ok=True)

    # 1. Create a dummy song
    print("\n1. Creating Test Song...")
    test_seg1 = Segment(tempo=100.0, loop_length=8, repetitions=2)
    test_seg2 = Segment(program_message_1=5, tempo=140.0, tempo_ramp=1.5, loop_length=16)
    test_song = Song(name="My Test Song ?!*", segments=[test_seg1, test_seg2])
    print(f"   {test_song}")
    print(f"   Segments: {test_song.segments}")

    # 2. Save the song
    print("\n2. Saving Test Song...")
    save_success = save_song(test_song, directory=TEST_SONGS_DIR)
    print(f"   Save successful: {save_success}")
    assert save_success

    # 3. List songs
    print("\n3. Listing Songs...")
    available_songs = list_songs(directory=TEST_SONGS_DIR)
    print(f"   Available songs: {available_songs}")
    sanitized_name = sanitize_filename(test_song.name)
    assert sanitized_name in available_songs

    # 4. Load the song (using basename)
    print("\n4. Loading Test Song (by basename)...")
    loaded_song = load_song(sanitized_name, directory=TEST_SONGS_DIR)
    if loaded_song:
        print(f"   Loaded song: {loaded_song}")
        print(f"   Loaded segments: {loaded_song.segments}")
        assert loaded_song.name == test_song.name # Original name should be preserved inside JSON
        assert len(loaded_song.segments) == len(test_song.segments)
        assert loaded_song.segments[0].tempo == test_song.segments[0].tempo
        assert loaded_song.segments[1].program_message_1 == test_song.segments[1].program_message_1
    else:
        print("   Failed to load song.")
        assert False # Test failed if load fails

    # 5. Load the song (using full filename)
    print("\n5. Loading Test Song (by full filename)...")
    loaded_song_fname = load_song(f"{sanitized_name}.json", directory=TEST_SONGS_DIR)
    assert loaded_song_fname is not None
    assert loaded_song_fname.name == test_song.name

    # 6. Test loading non-existent song
    print("\n6. Testing Load Non-existent Song...")
    non_existent = load_song("this-does-not-exist", directory=TEST_SONGS_DIR)
    assert non_existent is None
    print("   Load correctly returned None.")

    # 7. Clean up test file (optional)
    # print("\n7. Cleaning up test file...")
    # test_filepath = os.path.join(TEST_SONGS_DIR, f"{sanitized_name}.json")
    # if os.path.exists(test_filepath):
    #     os.remove(test_filepath)
    #     print(f"   Removed {test_filepath}")

    print("\n--- file_io Testing Complete ---")
