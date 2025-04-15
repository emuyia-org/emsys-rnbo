# emsys/ui/helpers/parameter_editor.py
# -*- coding: utf-8 -*-
"""
Handles editing logic for Song Segment parameters.
"""
from typing import Optional, Tuple, Any
import traceback

# Use absolute imports
from emsys.core.song import (Song, Segment, MIN_TEMPO, MAX_TEMPO, MIN_RAMP, MAX_RAMP,
                         MIN_LOOP_LENGTH, MAX_LOOP_LENGTH, MIN_REPETITIONS,
                         MAX_REPETITIONS, MIN_PROGRAM_MSG, MAX_PROGRAM_MSG)

# Define parameter editing steps (centralized here)
PARAM_STEPS = {
    'program_message_1': 1,
    'program_message_2': 1,
    'tempo': 1.0,
    'tempo_ramp': 0.5,
    'loop_length': 1,
    'repetitions': 1,
    'automatic_transport_interrupt': 1, # Step for toggling boolean
}

class ParameterEditor:
    """Provides methods to modify and query segment parameters."""

    def _get_param_range_and_default(self, key: str) -> Tuple[Optional[float], Optional[float], Any]:
        """Helper to get min, max, default for a parameter key."""
        # Use constants imported from core.song
        # Defaults are fetched from a temporary Segment instance
        default_segment = Segment()
        default_val = getattr(default_segment, key, None)

        ranges = {
            'tempo': (MIN_TEMPO, MAX_TEMPO, default_val),
            'tempo_ramp': (MIN_RAMP, MAX_RAMP, default_val),
            'loop_length': (MIN_LOOP_LENGTH, MAX_LOOP_LENGTH, default_val),
            'repetitions': (MIN_REPETITIONS, MAX_REPETITIONS, default_val),
            'program_message_1': (MIN_PROGRAM_MSG, MAX_PROGRAM_MSG, default_val),
            'program_message_2': (MIN_PROGRAM_MSG, MAX_PROGRAM_MSG, default_val),
            'automatic_transport_interrupt': (0, 1, default_val), # Range for bool
        }
        return ranges.get(key, (None, None, None))

    def modify_parameter(self, song: Optional[Song], segment_index: Optional[int],
                         key: Optional[str], direction: int) -> Tuple[Optional[Any], str, bool]:
        """
        Modifies the specified parameter value by a step in the given direction.
        Handles clamping, type consistency, and boolean toggling.

        Args:
            song: The current Song object.
            segment_index: The index of the segment being edited.
            key: The string key of the parameter to modify.
            direction: +1 for increment, -1 for decrement.

        Returns:
            A tuple containing:
            - The new value (or None if modification failed).
            - A status message (e.g., "OK", "At Min", "At Max", "Error: ...").
            - A boolean indicating if the value was actually changed.
        """
        if not all([song, segment_index is not None, key]):
            return None, "Error: Invalid input (song, index, or key missing)", False

        try:
            segment = song.get_segment(segment_index)
            current_value = getattr(segment, key)
            step = PARAM_STEPS.get(key, 1)
            min_val, max_val, _ = self._get_param_range_and_default(key)
            new_value = current_value
            changed = False
            status = "OK"

            # Handle boolean toggle specially
            if isinstance(current_value, bool):
                # Bool toggle ignores direction, just flips
                new_value = not current_value
                changed = True
            elif isinstance(current_value, (int, float)):
                calculated_value = current_value + (step * direction)

                # Clamp to min/max if range is defined
                if min_val is not None and max_val is not None:
                    clamped_value = max(min_val, min(max_val, calculated_value))
                    if calculated_value > max_val: status = "At Max"
                    elif calculated_value < min_val: status = "At Min"
                else:
                    clamped_value = calculated_value # No clamping if range undefined

                # Ensure type consistency and rounding
                if isinstance(current_value, int):
                    new_value = int(round(clamped_value))
                elif isinstance(current_value, float):
                    # Round floats based on step size
                    decimals = 0
                    if isinstance(step, float) and step != 0 and abs(step) < 1:
                         # Quick way to estimate decimals needed for step
                         step_str = str(step)
                         if '.' in step_str:
                             decimals = len(step_str.split('.')[-1])
                    new_value = round(clamped_value, decimals if decimals > 0 else 2) # Default 2 decimals if integer step

                if new_value != current_value:
                    changed = True
            else:
                # Cannot modify this type
                return None, f"Error: Cannot modify type {type(current_value)}", False

            # If the value changed, update the song object directly
            # This ensures the Song's dirty flag logic is triggered
            if changed:
                song.update_segment(segment_index, **{key: new_value})

            return new_value, status, changed

        except (IndexError, AttributeError, TypeError, ValueError) as e:
            error_msg = f"Error modifying '{key}': {e}"
            print(error_msg)
            return None, error_msg, False
        except Exception as e: # Catch unexpected errors
            error_msg = f"Unexpected error modifying '{key}': {e}"
            print(error_msg)
            traceback.print_exc()
            return None, error_msg, False


    def reset_or_copy_parameter(self, song: Optional[Song], segment_index: Optional[int],
                                key: Optional[str]) -> Tuple[Optional[Any], str, bool]:
        """
        Resets the selected parameter to its default value, or copies it from
        the previous segment if available.

        Args:
            song: The current Song object.
            segment_index: The index of the segment being edited.
            key: The string key of the parameter to reset/copy.

        Returns:
            A tuple containing:
            - The new value (or None if action failed).
            - A status message.
            - A boolean indicating if the value was actually changed.
        """
        if not all([song, segment_index is not None, key]):
            return None, "Error: Invalid input", False

        try:
            current_segment = song.get_segment(segment_index)
            current_value = getattr(current_segment, key)
            value_to_set = None
            changed = False
            status = "No change"

            # Try copying from previous segment first
            if segment_index > 0:
                prev_segment = song.get_segment(segment_index - 1)
                prev_value = getattr(prev_segment, key)
                if prev_value != current_value:
                    value_to_set = prev_value
                    status = "Copied from previous"
                    changed = True
                else:
                    status = "Matches previous"
            else:
                # No previous segment, try resetting to default
                _, _, default_value = self._get_param_range_and_default(key)
                if default_value is not None and default_value != current_value:
                    value_to_set = default_value
                    status = "Reset to default"
                    changed = True
                elif default_value is not None:
                     status = "Already default"
                else:
                     status = "No default defined"


            # If a new value was determined, update the song
            if changed and value_to_set is not None:
                 song.update_segment(segment_index, **{key: value_to_set})
                 return value_to_set, status, changed
            else:
                 # Return current value if no change occurred, but indicate status
                 return current_value, status, False

        except (IndexError, AttributeError, TypeError, ValueError) as e:
            error_msg = f"Error resetting/copying '{key}': {e}"
            print(error_msg)
            return None, error_msg, False
        except Exception as e: # Catch unexpected errors
             error_msg = f"Unexpected error resetting/copying '{key}': {e}"
             print(error_msg)
             traceback.print_exc()
             return None, error_msg, False
