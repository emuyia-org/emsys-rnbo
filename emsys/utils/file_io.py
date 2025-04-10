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

# --- Configuration ---

# Define the directory where song files will be stored.
# Option 1: Absolute path (common for deployment on Pi)
# SONGS_DIR = "/home/pi/emsys_songs/"
# Option 2: Relative path (useful for development, relative to the project root)
# Assumes your project root is the parent directory of 'emsys'
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SONGS_DIR = os.path.join(PROJECT_ROOT, "data", "songs")
# Option 3: Relative to the emsys package itself
# Emsys package dir is parent of utils dir
# EMSYS_PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# SONGS_DIR = os.path.join(EMSYS_PACKAGE_DIR, "data", "songs")

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

def save_song(song: Song, directory: str = SONGS_DIR) -> bool:
    """
    Saves a Song object to a JSON file in the specified directory.

    The filename is derived from the sanitized song name.

    Args:
        song: The Song object to save.
        directory: The directory path to save the file in. Defaults to SONGS_DIR.

    Returns:
        True if saving was successful, False otherwise.
    """
    if not isinstance(song, Song):
        print(f"Error: Attempted to save an object that is not a Song: {type(song)}")
        return False

    # Ensure the target directory exists
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as e:
        print(f"Error: Could not create directory '{directory}': {e}")
        return False

    # Prepare data for JSON serialization
    try:
        # Use asdict for Segment dataclasses
        song_data = {
            "name": song.name,
            "segments": [asdict(segment) for segment in song.segments]
        }
    except Exception as e:
        print(f"Error: Failed to convert song '{song.name}' data for serialization: {e}")
        return False

    # Create a safe filename
    base_filename = sanitize_filename(song.name)
    filename = f"{base_filename}.json"
    filepath = os.path.join(directory, filename)

    # Write the JSON data to the file
    try:
        print(f"Attempting to save song to: {filepath}")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(song_data, f, indent=4, ensure_ascii=False)
        print(f"Song '{song.name}' saved successfully as '{filename}'.")
        return True
    except IOError as e:
        print(f"Error: Could not write song file '{filepath}': {e}")
        return False
    except Exception as e:
        print(f"Error: An unexpected error occurred during save to '{filepath}': {e}")
        return False

def load_song(filename_or_basename: str, directory: str = SONGS_DIR) -> Optional[Song]:
    """
    Loads a Song object from a JSON file.

    Args:
        filename_or_basename: The base name of the song (e.g., "my-cool-song")
                              or the full filename ("my-cool-song.json").
        directory: The directory path where the file is located. Defaults to SONGS_DIR.

    Returns:
        The loaded Song object, or None if loading fails.
    """
    # Ensure the filename ends with .json
    if not filename_or_basename.lower().endswith(".json"):
        filename = f"{filename_or_basename}.json"
    else:
        filename = filename_or_basename

    filepath = os.path.join(directory, filename)

    if not os.path.exists(filepath):
        print(f"Error: Song file not found: {filepath}")
        return None
    if not os.path.isfile(filepath):
        print(f"Error: Path exists but is not a file: {filepath}")
        return None

    try:
        print(f"Attempting to load song from: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            song_data = json.load(f)

        # --- Reconstruct the Song object ---
        song_name = song_data.get("name")
        if not song_name:
            print(f"Warning: Song file '{filename}' is missing 'name'. Using default.")
            # Extract name from filename if possible, otherwise default
            song_name = os.path.splitext(filename)[0] if filename else "Untitled Loaded Song"

        loaded_segments: List[Segment] = []
        segment_data_list = song_data.get("segments")

        if segment_data_list is None:
             print(f"Warning: Song file '{filename}' is missing 'segments' list.")
             segment_data_list = [] # Treat as empty list
        elif not isinstance(segment_data_list, list):
             print(f"Error: 'segments' data in '{filename}' is not a list. Cannot load segments.")
             # Decide if you want to return None or a song with no segments
             return Song(name=song_name, segments=[]) # Return song with empty segments

        # Recreate Segment objects
        for i, segment_dict in enumerate(segment_data_list):
            if not isinstance(segment_dict, dict):
                print(f"Warning: Skipping segment #{i+1} in '{filename}' - data is not a dictionary: {segment_dict}")
                continue
            try:
                # Create Segment instance using dictionary unpacking.
                # This assumes keys in JSON match Segment attributes.
                segment = Segment(**segment_dict)
                loaded_segments.append(segment)
            except TypeError as te:
                # Handles cases where keys don't match or are missing
                print(f"Warning: Skipping segment #{i+1} in '{filename}' due to key mismatch or missing keys: {segment_dict}. Error: {te}")
            except Exception as e_seg:
                print(f"Warning: Error creating segment #{i+1} from data in '{filename}': {segment_dict}. Error: {e_seg}")

        # Create the final Song object
        song = Song(name=song_name, segments=loaded_segments)
        print(f"Song '{song.name}' loaded successfully from '{filename}'. Found {len(loaded_segments)} segments.")
        return song

    except json.JSONDecodeError as e:
        print(f"Error: Failed to decode JSON from '{filepath}': {e}")
        return None
    except IOError as e:
        print(f"Error: Could not read song file '{filepath}': {e}")
        return None
    except Exception as e:
        print(f"Error: An unexpected error occurred during load from '{filepath}': {e}")
        return None

def list_songs(directory: str = SONGS_DIR) -> List[str]:
    """
    Lists available song files (basenames without extension) in the directory.

    Args:
        directory: The directory path to scan. Defaults to SONGS_DIR.

    Returns:
        A sorted list of song basenames (e.g., ["my-song", "another-track"]).
    """
    if not os.path.isdir(directory):
        print(f"Info: Song directory '{directory}' not found. No songs to list.")
        # Create it the first time? Optional.
        # try:
        #     os.makedirs(directory, exist_ok=True)
        # except OSError:
        #     pass # Ignore error if creation fails here
        return []
    try:
        files = os.listdir(directory)
        # Filter for .json files and extract the base name
        song_basenames = [
            os.path.splitext(f)[0]
            for f in files
            if f.lower().endswith(".json") and os.path.isfile(os.path.join(directory, f))
        ]
        return sorted(song_basenames)
    except OSError as e:
        print(f"Error: Could not list files in directory '{directory}': {e}")
        return []

# --- Example Usage (for testing this module directly) ---
if __name__ == '__main__':
    print("\n--- Testing file_io Module ---")

    # Ensure the test directory exists
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
