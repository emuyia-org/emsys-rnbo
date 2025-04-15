# emsys/ui/helpers/led_feedback_handler.py
# -*- coding: utf-8 -*-
"""
Handles calculation and sending of MIDI feedback for controller LEDs,
specifically the encoder ring on the Song Edit Screen.
"""
import math
from typing import Optional, Any, Dict, Tuple
from enum import Enum, auto

# Use absolute imports for consistency
from emsys.core.song import (Song, Segment, MIN_TEMPO, MAX_TEMPO, MIN_RAMP, MAX_RAMP,
                         MIN_LOOP_LENGTH, MAX_LOOP_LENGTH, MIN_REPETITIONS,
                         MAX_REPETITIONS, MIN_PROGRAM_MSG, MAX_PROGRAM_MSG)
from emsys.config import mappings

# Constants for LED calculation
ENCODER_LED_CC = 16 # CC for Knob B8 LED Ring (CC 9 + 7 = 16 ? Verify X-Touch mapping)
ENCODER_LED_CHANNEL = 15 # MIDI Channel 16
MIN_LED_VALUE = 1
MAX_LED_VALUE = 13

class CurveType(Enum):
    """Defines how a parameter value maps to the LED range."""
    LINEAR = auto()
    LOG = auto()      # Moderate curve (e.g., for Tempo)
    STRONG_LOG = auto() # Harsher curve (e.g., for Ramp, Length, Repeats)

# --- Curve Scaling Functions ---
# These take a normalized value (0.0 to 1.0) and return a scaled normalized value (0.0 to 1.0)
def scale_linear(norm_val: float) -> float:
    """Linear scaling (no change)."""
    return norm_val

def scale_log(norm_val: float, exponent: float = 0.5) -> float:
    """Logarithmic-like scaling. Grows faster at the start. exponent < 1.0"""
    if norm_val <= 0: return 0.0
    return norm_val ** exponent

def scale_strong_log(norm_val: float, exponent: float = 0.33) -> float:
    """Stronger logarithmic-like scaling. Grows even faster at the start. exponent << 1.0"""
    if norm_val <= 0: return 0.0
    return norm_val ** exponent

class LedFeedbackHandler:
    """Calculates and sends LED feedback for the Song Edit screen encoder."""

    # Map Parameters to LED Curve Types
    PARAMETER_LED_CURVES: Dict[str, CurveType] = {
        'program_message_1': CurveType.LINEAR,
        'program_message_2': CurveType.LINEAR,
        'tempo': CurveType.LOG,
        'tempo_ramp': CurveType.STRONG_LOG,
        'loop_length': CurveType.LOG, # Changed from STRONG_LOG based on review
        'repetitions': CurveType.LOG, # Changed from STRONG_LOG based on review
        'automatic_transport_interrupt': CurveType.LINEAR,
    }

    def __init__(self, app_ref: Any):
        """
        Initialize the handler.

        Args:
            app_ref: Reference to the main application instance (for sending MIDI).
        """
        self.app = app_ref

    def _get_param_range(self, key: str) -> Tuple[Optional[float], Optional[float]]:
        """Helper to get min, max for a parameter key (ignores default)."""
        # Use constants imported from core.song
        ranges = {
            'tempo': (MIN_TEMPO, MAX_TEMPO),
            'tempo_ramp': (MIN_RAMP, MAX_RAMP),
            'loop_length': (MIN_LOOP_LENGTH, MAX_LOOP_LENGTH),
            'repetitions': (MIN_REPETITIONS, MAX_REPETITIONS),
            'program_message_1': (MIN_PROGRAM_MSG, MAX_PROGRAM_MSG),
            'program_message_2': (MIN_PROGRAM_MSG, MAX_PROGRAM_MSG),
            'automatic_transport_interrupt': (0, 1), # Range for boolean (False=0, True=1)
        }
        return ranges.get(key, (None, None)) # Return None if key unknown

    def update_encoder_led(self, current_song: Optional[Song],
                           selected_segment_index: Optional[int],
                           selected_parameter_key: Optional[str]):
        """
        Calculates and sends MIDI CC to update the encoder LED ring (1-13 LEDs)
        based on the selected parameter's value and curve type.
        """
        # Check if MIDI output is ready via the app reference
        # Assuming app.midi_service provides the necessary check or send method handles it
        # if not self.app.midi_service or not self.app.midi_service.output_port: # Check service/port
        #     print("[LED Handler] Skipping LED update: MIDI output not ready.")
        #     return

        led_value = MIN_LED_VALUE  # Default to first LED (never 0)

        # Determine the value only if a valid segment and parameter are selected
        if (current_song and selected_segment_index is not None and
                selected_parameter_key is not None):
            try:
                segment = current_song.get_segment(selected_segment_index)
                key = selected_parameter_key
                current_value = getattr(segment, key)

                min_val, max_val = self._get_param_range(key)

                # Handle boolean separately (map to 1 and 13)
                if isinstance(current_value, bool):
                    led_value = MAX_LED_VALUE if current_value else MIN_LED_VALUE
                # Normalize and scale if we have a valid numerical range
                elif min_val is not None and max_val is not None and max_val > min_val:
                    # Ensure value is numeric before proceeding
                    if not isinstance(current_value, (int, float)):
                        raise TypeError(f"Value for {key} is not numeric: {current_value}")

                    # Normalize current_value to 0.0 - 1.0
                    normalized = (float(current_value) - min_val) / (max_val - min_val)
                    normalized = max(0.0, min(1.0, normalized)) # Clamp

                    # Apply Scaling Curve
                    curve_type = self.PARAMETER_LED_CURVES.get(key, CurveType.LINEAR)
                    scaler = scale_linear # Default
                    if curve_type == CurveType.LOG:
                        scaler = scale_log
                    elif curve_type == CurveType.STRONG_LOG:
                        scaler = scale_strong_log

                    scaled_normalized = scaler(normalized)

                    # Map Scaled Value to 1-13 LED Range
                    if scaled_normalized <= 0.001: # Handle float precision near zero
                        led_value = MIN_LED_VALUE
                    else:
                        led_value = MIN_LED_VALUE + math.floor(scaled_normalized * (MAX_LED_VALUE - MIN_LED_VALUE))
                        # Ensure max value is hit precisely
                        if scaled_normalized >= 0.999:
                             led_value = MAX_LED_VALUE

                    led_value = max(MIN_LED_VALUE, min(MAX_LED_VALUE, int(led_value))) # Final clamp and int conversion

            except (IndexError, AttributeError, TypeError, ValueError) as e:
                print(f"[LED Handler] Error calculating LED value for {selected_parameter_key}: {e}")
                led_value = MIN_LED_VALUE # Default on error

        # else: # No valid selection, keep default led_value = 1

        # Send the MIDI CC message via the app's send method
        # print(f"[LED Handler] Sending LED Value: CC={ENCODER_LED_CC}, Value={led_value}") # Debug
        self.app.send_midi_cc(control=ENCODER_LED_CC, value=int(led_value), channel=ENCODER_LED_CHANNEL)
