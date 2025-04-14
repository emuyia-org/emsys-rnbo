# emsys/song.py
"""
Defines the data structures for Songs and Segments in Emsys.

These classes are designed to hold the structural information for musical pieces,
allowing for sequencing and editing within the application.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

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
    """
    program_message_1: int = 0          # MIDI Program Change 1 (0-127)
    program_message_2: int = 0          # MIDI Program Change 2 (0-127)
    tempo: float = 120.0                # Tempo in Beats Per Minute (30.0-300.0)
    tempo_ramp: float = 0.0             # Time in seconds to ramp to this tempo from previous (0.0-300.0). 0 = instant.
    loop_length: int = 16               # Length of the loop in beats (8-128)
    repetitions: int = 1                # Number of times to repeat this segment (1-128)
    automatic_transport_interrupt: bool = False # Pause playback after this segment finishes? (True/False)
    dirty: bool = field(default=False, compare=False, repr=False) # Tracks unsaved changes for this segment

    def __str__(self) -> str:
        # Include asterisk if this segment has unsaved changes.
        dirty_flag = "*" if self.dirty else ""
        return (f"Segment{dirty_flag}(Prog1={self.program_message_1}, "
                f"Prog2={self.program_message_2}, Tempo={self.tempo}, "
                f"Ramp={self.tempo_ramp}, Loop={self.loop_length}, "
                f"Reps={self.repetitions}, AutoTransport={self.automatic_transport_interrupt})")

# --- Song Data Structure ---
class Song:
    """
    Represents a song, composed of an ordered list of Segments.
    Provides methods for managing the segments within the song.
    Designed to be manipulated by UI components.
    Includes a 'dirty' flag to track unsaved changes.
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
        self.segments: List[Segment] = segments if segments is not None else []
        self.dirty: bool = False  # Flag to track unsaved changes

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
        self.dirty = True # Mark as modified

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
        removed_segment = self.segments.pop(index)
        self.dirty = True # Mark as modified
        return removed_segment

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
        Also sets the segment's and the song's dirty flag if a value changes.

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
        modified = False
        for key, value in kwargs.items():
            if hasattr(segment, key):
                # Only mark as modified if the value actually changes
                if getattr(segment, key) != value:
                    setattr(segment, key, value)
                    modified = True
                # Optional: Trigger validation if implemented in Segment
                # if hasattr(segment, '__post_init__'): segment.__post_init__()
            else:
                raise AttributeError(f"Segment object has no attribute '{key}'")
        if modified:
            segment.dirty = True # Mark the specific segment as dirty
            self.dirty = True # Mark the whole song as dirty

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the Song object to a dictionary suitable for serialization.
        Excludes the runtime 'dirty' flags.

        Returns:
            A dictionary containing the song name and segments.
        """
        # Convert each segment to dict, excluding the 'dirty' field
        segments_list = []
        for segment in self.segments:
            segment_dict = asdict(segment)
            segment_dict.pop('dirty', None) # Remove dirty flag before saving
            segments_list.append(segment_dict)

        return {
            "name": self.name,
            "segments": segments_list
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Song':
        """
        Creates a Song object from a dictionary (deserialization).
        Initializes segments with dirty=False.

        Args:
            data: Dictionary containing song data with 'name' and 'segments'.

        Returns:
            A new Song instance populated with the data.

        Raises:
            KeyError: If required keys are missing.
            TypeError: If data types are incorrect.
        """
        if not isinstance(data, dict):
            raise TypeError("Data must be a dictionary")

        name = data.get("name")
        if not name:
            raise KeyError("Song data must contain 'name'")

        segments_data = data.get("segments", [])
        if not isinstance(segments_data, list):
            raise TypeError("'segments' must be a list")

        segments = []
        for segment_dict in segments_data:
            try:
                # Create Segment instance using dictionary unpacking
                # The 'dirty' flag will default to False as defined in the dataclass
                segment = Segment(**segment_dict)
                segments.append(segment)
            except TypeError as e:
                raise TypeError(f"Error creating segment: {e}")

        song = cls(name=name, segments=segments)
        song.dirty = False # Loaded song starts clean
        return song

    def clear_segments(self):
        """Removes all segments from the song."""
        if self.segments: # Only mark dirty if there were segments to clear
            self.segments = []
            self.dirty = True

    def clear_segment_dirty_flags(self):
        """Resets the dirty flag for all segments in the song."""
        for segment in self.segments:
            segment.dirty = False

    def __len__(self) -> int:
        """Returns the number of segments in the song."""
        return len(self.segments)

    def __repr__(self) -> str:
        dirty_flag = "*" if self.dirty else ""
        return f"Song(name='{self.name}{dirty_flag}', segments={len(self.segments)})"

    def __str__(self) -> str:
        dirty_flag = "*" if self.dirty else ""
        segment_details = "\n  ".join([f"{i+1}: {seg}" for i, seg in enumerate(self.segments)])
        return f"Song: {self.name}{dirty_flag}\nSegments:\n  {segment_details if segment_details else 'No segments.'}"
