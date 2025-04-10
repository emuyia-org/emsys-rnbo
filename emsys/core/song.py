# emsys/song.py
"""
Defines the data structures for Songs and Segments in Emsys.

These classes are designed to hold the structural information for musical pieces,
allowing for sequencing and editing within the application.
"""

from dataclasses import dataclass, field
from typing import List, Optional

# --- Constants for Validation (Optional but Recommended) ---
# You might want to define these here or import from config if they become more widely used
MIN_TEMPO = 30.0
MAX_TEMPO = 300.0
MIN_RAMP = 0.0
MAX_RAMP = 300.0
MIN_LOOP_LENGTH = 8
MAX_LOOP_LENGTH = 128
MIN_REPETITIONS = 1
MAX_REPETITIONS = 128
MIN_PROGRAM_MSG = 0
MAX_PROGRAM_MSG = 127

# --- Segment Data Structure ---

@dataclass
class Segment:
    """
    Represents one segment or section within a Song.

    Attributes are designed to be easily accessed and modified, suitable for UI editing.
    Consider adding validation logic (e.g., in __post_init__) if strict range
    enforcement is needed outside the UI layer.
    """
    program_message_1: int = 0          # MIDI Program Change 1 (0-127)
    program_message_2: int = 0          # MIDI Program Change 2 (0-127)
    tempo: float = 120.0                # Tempo in Beats Per Minute (30.0-300.0)
    tempo_ramp: float = 0.0             # Time in seconds to ramp to this tempo from previous (0.0-300.0). 0 = instant.
    loop_length: int = 16               # Length of the loop in beats (8-128)
    repetitions: int = 1                # Number of times to repeat this segment (1-128)
    automatic_transport_interrupt: bool = False # Pause playback after this segment finishes? (True=Yes, False=No)

    # Optional: Post-init validation if needed, though UI might handle this
    # def __post_init__(self):
    #     if not (MIN_PROGRAM_MSG <= self.program_message_1 <= MAX_PROGRAM_MSG):
    #         raise ValueError(f"program_message_1 must be between {MIN_PROGRAM_MSG} and {MAX_PROGRAM_MSG}")
    #     # ... add other validations similarly ...
    #     if not (MIN_TEMPO <= self.tempo <= MAX_TEMPO):
    #          raise ValueError(f"Tempo must be between {MIN_TEMPO} and {MAX_TEMPO} BPM")
    #     # etc.

# --- Song Data Structure ---

class Song:
    """
    Represents a song, composed of an ordered list of Segments.

    Provides methods for managing the segments within the song.
    Designed to be manipulated by UI components.
    """
    def __init__(self, name: str, segments: Optional[List[Segment]] = None):
        """
        Initializes a new Song.

        Args:
            name: The name of the song.
            segments: An optional list of Segment objects to initialize the song with.
                      If None, the song starts with an empty segment list.
        """
        if not isinstance(name, str) or not name:
            raise ValueError("Song name must be a non-empty string.")

        self.name: str = name
        # Use field for default_factory to ensure each Song instance gets its own list
        self.segments: List[Segment] = segments if segments is not None else []

    def add_segment(self, segment: Segment, index: Optional[int] = None):
        """
        Adds a segment to the song's segment list.

        Args:
            segment: The Segment object to add.
            index: Optional position at which to insert the segment.
                   If None, appends to the end.
        """
        if not isinstance(segment, Segment):
            raise TypeError("Can only add Segment objects to a Song.")

        if index is None:
            self.segments.append(segment)
        else:
            if not (0 <= index <= len(self.segments)):
                 raise IndexError(f"Index {index} out of range for inserting segment.")
            self.segments.insert(index, segment)

    def remove_segment(self, index: int):
        """
        Removes a segment from the song at the specified index.

        Args:
            index: The index of the segment to remove.

        Returns:
            The removed Segment object.

        Raises:
            IndexError: If the index is out of range.
        """
        if not (0 <= index < len(self.segments)):
            raise IndexError(f"Index {index} out of range for removing segment.")
        return self.segments.pop(index)

    def get_segment(self, index: int) -> Segment:
        """
        Retrieves the segment at the specified index.

        Args:
            index: The index of the segment to retrieve.

        Returns:
            The Segment object at the given index.

        Raises:
            IndexError: If the index is out of range.
        """
        if not (0 <= index < len(self.segments)):
            raise IndexError(f"Index {index} out of range for getting segment.")
        return self.segments[index]

    def update_segment(self, index: int, **kwargs):
        """
        Updates attributes of a segment at the specified index.

        Args:
            index: The index of the segment to update.
            **kwargs: Keyword arguments corresponding to Segment attributes to update
                      (e.g., tempo=130.0, repetitions=4).

        Raises:
            IndexError: If the index is out of range.
            AttributeError: If a keyword argument doesn't match a Segment attribute.
            TypeError: If the type of an updated value is incorrect (depends on Segment definition).
            ValueError: If the value is outside acceptable ranges (if validation is added).
        """
        segment = self.get_segment(index) # Leverage existing method for bounds check
        for key, value in kwargs.items():
            if hasattr(segment, key):
                setattr(segment, key, value)
                # Optional: Trigger validation if implemented in Segment
                # if hasattr(segment, '__post_init__'): segment.__post_init__()
            else:
                raise AttributeError(f"Segment object has no attribute '{key}'")

    def clear_segments(self):
        """Removes all segments from the song."""
        self.segments = []

    def __len__(self) -> int:
        """Returns the number of segments in the song."""
        return len(self.segments)

    def __repr__(self) -> str:
        """Provides a useful string representation of the Song object."""
        return f"Song(name='{self.name}', segments={len(self.segments)})"

    def __str__(self) -> str:
        """Provides a user-friendly string representation."""
        segment_details = "\n  ".join([f"{i+1}: {seg}" for i, seg in enumerate(self.segments)])
        return f"Song: {self.name}\nSegments:\n  {segment_details if segment_details else 'No segments.'}"

'''
# --- Example Usage ---
if __name__ == '__main__':
    print("--- Testing Song/Segment Classes ---")

    # Create example segments
    try:
        seg1 = Segment(
            program_message_1=10,
            program_message_2=25,
            tempo=120.0,
            tempo_ramp=2.0,
            loop_length=16,
            repetitions=4,
            automatic_transport_interrupt=False
        )
        seg2 = Segment(
            program_message_1=11,
            program_message_2=26,
            tempo=90.0,
            tempo_ramp=0.0, # Instant change
            loop_length=32,
            repetitions=2,
            automatic_transport_interrupt=True # Pause after this one
        )
        seg3 = Segment() # Use defaults

        print("\nCreated Segments:")
        print(f"Segment 1: {seg1}")
        print(f"Segment 2: {seg2}")
        print(f"Segment 3 (Defaults): {seg3}")

        # Create a song
        my_song = Song(name="My Awesome Track")
        print(f"\nCreated Song: {my_song}")

        # Add segments
        my_song.add_segment(seg1)
        my_song.add_segment(seg2)
        print(f"\nSong after adding 2 segments: {my_song}")
        print(f"Number of segments: {len(my_song)}")

        # Insert a segment
        my_song.add_segment(seg3, index=1) # Insert seg3 between seg1 and seg2
        print(f"\nSong after inserting segment at index 1: {my_song}")

        # Print detailed song structure
        print("\nDetailed Song Structure:")
        print(str(my_song))

        # Get a specific segment
        retrieved_segment = my_song.get_segment(0)
        print(f"\nRetrieved segment at index 0: {retrieved_segment}")
        assert retrieved_segment == seg1

        # Update a segment
        print("\nUpdating segment at index 2 (originally seg2):")
        my_song.update_segment(2, tempo=95.5, repetitions=3)
        print(str(my_song))
        assert my_song.get_segment(2).tempo == 95.5
        assert my_song.get_segment(2).repetitions == 3

        # Remove a segment
        removed = my_song.remove_segment(1) # Remove seg3
        print(f"\nRemoved segment at index 1: {removed}")
        print(f"Song after removal: {my_song}")
        print(str(my_song))
        assert len(my_song) == 2
        assert removed == seg3

        # Clear all segments
        my_song.clear_segments()
        print(f"\nSong after clearing segments: {my_song}")
        print(str(my_song))
        assert len(my_song) == 0

        # Test initialization with segments
        initial_segments = [Segment(tempo=100), Segment(tempo=110)]
        another_song = Song(name="Preloaded Song", segments=initial_segments)
        print(f"\nCreated song with initial segments: {another_song}")
        print(str(another_song))
        assert len(another_song) == 2

    except (ValueError, TypeError, IndexError, AttributeError) as e:
        print(f"\nAn error occurred during testing: {e}")

    print("\n--- Testing Complete ---")
'''