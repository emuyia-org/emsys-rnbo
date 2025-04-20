# emsys/services/midi_service.py
# -*- coding: utf-8 -*-
"""
Handles MIDI device connection, disconnection, and reconnection logic.
"""
import mido
import mido.backends.rtmidi # Explicitly import backend
import time
import traceback
from typing import Optional, Callable, Any

# Use absolute imports for consistency
from emsys.config import settings
from emsys.utils.midi import find_midi_port

# Configuration constants
MIDI_DEVICE_NAME = settings.MIDI_DEVICE_NAME
RESCAN_INTERVAL_SECONDS = settings.RESCAN_INTERVAL_SECONDS
CONNECTION_CHECK_INTERVAL_SECONDS = settings.CONNECTION_CHECK_INTERVAL_SECONDS

class MidiService:
    """Manages MIDI input and output port connections."""

    def __init__(self, status_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize the MIDI service.

        Args:
            status_callback: An optional function to call with status updates.
        """
        self.input_port: Optional[mido.ports.BaseInput] = None
        self.input_port_name: Optional[str] = None
        self.output_port: Optional[mido.ports.BaseOutput] = None
        self.output_port_name: Optional[str] = None
        self.error_message: Optional[str] = None
        self.is_searching: bool = False
        self.last_scan_time: float = 0
        self.last_connection_check_time: float = 0
        self._status_callback = status_callback if status_callback else lambda msg: print(f"MIDI Status: {msg}")

        self._initialize_ports()

    def _initialize_ports(self):
        """Finds and attempts to open the MIDI input and output ports initially."""
        self._status_callback(f"Initializing MIDI: Searching for '{MIDI_DEVICE_NAME}'...")
        found_input_port_name = find_midi_port(MIDI_DEVICE_NAME, verbose=True, port_type='input')
        found_output_port_name = find_midi_port(MIDI_DEVICE_NAME, verbose=True, port_type='output')

        # --- Handle Input Port ---
        if found_input_port_name:
            try:
                self.input_port = mido.open_input(found_input_port_name)
                self.input_port_name = found_input_port_name
                self.error_message = None
                self.is_searching = False
                print(f"Successfully opened MIDI Input: '{self.input_port_name}'")
                self._status_callback(f"MIDI Input Connected: '{self.input_port_name}'")
            except (IOError, OSError) as e:
                self.input_port = None
                self.input_port_name = None
                self.error_message = f"Error opening Input '{found_input_port_name}': {e}"
                print(self.error_message)
                self._status_callback(f"Error opening MIDI Input: {e}")
                self._start_search_mode()
        else:
            self.error_message = f"MIDI Input '{MIDI_DEVICE_NAME}' not found."
            print(self.error_message)
            self._status_callback(f"MIDI Input '{MIDI_DEVICE_NAME}' not found. Searching...")
            self._start_search_mode()

        # --- Handle Output Port ---
        if found_output_port_name:
            try:
                self.output_port = mido.open_output(found_output_port_name)
                self.output_port_name = found_output_port_name
                print(f"Successfully opened MIDI Output: '{self.output_port_name}'")
                self._status_callback(f"MIDI Output Connected: '{self.output_port_name}'")
            except (IOError, OSError) as e:
                self.output_port = None
                self.output_port_name = None
                print(f"Warning: Error opening Output '{found_output_port_name}': {e}")
                self._status_callback(f"Warning: Error opening MIDI Output: {e}")
        else:
             print(f"Warning: MIDI Output '{MIDI_DEVICE_NAME}' not found.")
             self._status_callback(f"Warning: MIDI Output '{MIDI_DEVICE_NAME}' not found.")

    def _start_search_mode(self):
        """Sets the service state to actively search for MIDI devices."""
        print("Starting MIDI search mode...")
        self.is_searching = True
        self.last_scan_time = 0 # Reset scan timer
        self._status_callback(self.error_message or "MIDI Searching...")

    def _handle_disconnection(self, reason="Disconnected"):
        """Handles the state change when a MIDI disconnection is detected."""
        if self.input_port is None and self.output_port is None and not self.is_searching:
             return # Already disconnected and searching

        print(f"\n--- Handling MIDI Disconnection (Reason: {reason}) ---")
        self.close_ports() # Use helper to close ports

        self.error_message = f"MIDI Disconnected ({reason}). Searching..."
        self._status_callback(self.error_message)
        self._start_search_mode()

    def check_connection(self):
        """Periodically checks if the connected ports still exist."""
        if self.is_searching or not self.input_port:
            return # Don't check if searching or not connected

        current_time = time.time()
        if current_time - self.last_connection_check_time < CONNECTION_CHECK_INTERVAL_SECONDS:
            return # Check interval not elapsed

        self.last_connection_check_time = current_time
        try:
            available_inputs = mido.get_input_names()
            input_ok = self.input_port_name in available_inputs

            output_ok = True
            if self.output_port:
                available_outputs = mido.get_output_names()
                if self.output_port_name not in available_outputs:
                    output_ok = False
                    print(f"MIDI Output port '{self.output_port_name}' disappeared.")

            if not input_ok or not output_ok:
                reason = "Input port disappeared" if not input_ok else "Output port disappeared"
                self._handle_disconnection(reason=reason)

        except Exception as e:
            print(f"Error checking MIDI connection: {e}")
            self._handle_disconnection(reason=f"Connection check error: {e}")


    def attempt_reconnect(self):
        """Attempts to find and reopen the MIDI input and output ports if searching."""
        if not self.is_searching:
             return # Only reconnect if in search mode

        current_time = time.time()
        if current_time - self.last_scan_time < RESCAN_INTERVAL_SECONDS:
            return # Wait before scanning again

        self.last_scan_time = current_time
        print(f"Scanning for MIDI device '{MIDI_DEVICE_NAME}'...")
        self._status_callback(f"Scanning for '{MIDI_DEVICE_NAME}'...")

        found_input_port_name = find_midi_port(MIDI_DEVICE_NAME, verbose=False, port_type='input')
        found_output_port_name = find_midi_port(MIDI_DEVICE_NAME, verbose=False, port_type='output')

        reconnected_input = False

        # --- Reconnect Input ---
        if found_input_port_name:
            try:
                # Ensure old port is closed before opening new one
                if self.input_port and not self.input_port.closed:
                    self.input_port.close()
                self.input_port = mido.open_input(found_input_port_name)
                self.input_port_name = found_input_port_name
                self.error_message = None
                self.is_searching = False # Stop searching
                reconnected_input = True
                print(f"\nSuccessfully Reconnected MIDI Input: '{self.input_port_name}'")
                self._status_callback(f"MIDI Input Reconnected: '{self.input_port_name}'")
                self.last_connection_check_time = time.time() # Reset check timer
            except (IOError, OSError) as e:
                self.input_port = None
                self.input_port_name = None
                self.error_message = f"Found Input '{found_input_port_name}', but open failed: {e}. Retrying..."
                print(self.error_message)
                self._status_callback(f"MIDI Input open failed: {e}. Retrying...")
                # Keep is_searching = True

        # --- Reconnect Output (only if input reconnected) ---
        if reconnected_input:
            if found_output_port_name:
                 if not self.output_port or self.output_port.closed: # Only try if not already open/reopened
                    try:
                        # Ensure old port is closed
                        if self.output_port and not self.output_port.closed:
                            self.output_port.close()
                        self.output_port = mido.open_output(found_output_port_name)
                        self.output_port_name = found_output_port_name
                        print(f"Successfully Reconnected MIDI Output: '{self.output_port_name}'")
                        self._status_callback(f"MIDI Output Reconnected: '{self.output_port_name}'")
                    except (IOError, OSError) as e:
                        self.output_port = None
                        self.output_port_name = None
                        print(f"Warning: Reconnected Input, but failed to reopen Output '{found_output_port_name}': {e}")
                        self._status_callback(f"Warning: Failed to reopen MIDI Output: {e}")
            else:
                 # Input reconnected, but output still not found
                 print(f"Warning: Reconnected Input, but MIDI Output '{MIDI_DEVICE_NAME}' not found.")
                 self._status_callback(f"Warning: MIDI Output '{MIDI_DEVICE_NAME}' not found.")
                 # Ensure output port object is None if not found
                 if self.output_port and not self.output_port.closed:
                     self.output_port.close()
                 self.output_port = None
                 self.output_port_name = None


        if not reconnected_input and self.is_searching: # Check is_searching again
            # If input still not found after scan interval
            self.error_message = f"MIDI Input '{MIDI_DEVICE_NAME}' not found. Still searching..."
            self._status_callback(self.error_message) # Update status


    def receive_messages(self) -> list[mido.Message]:
        """Receives pending MIDI messages from the input port."""
        messages = []
        if self.input_port and not self.is_searching:
            try:
                # Use iter_pending() for non-blocking receive
                for msg in self.input_port.iter_pending():
                    messages.append(msg)
            except (IOError, OSError) as e:
                print(f"\nMIDI Read Error: {e}")
                self._handle_disconnection(reason=f"Read Error: {e}")
            except Exception as e:
                print(f"\nUnexpected Error processing MIDI: {e}")
                traceback.print_exc()
                self._handle_disconnection(reason=f"Unexpected Error: {e}")
        return messages

    def send_message(self, msg: mido.Message):
        """Sends a MIDI message to the output port."""
        if self.output_port and not self.output_port.closed:
            try:
                self.output_port.send(msg)
            except Exception as e:
                print(f"Error sending MIDI message {msg}: {e}")
                # Consider if sending error should trigger disconnection? Maybe not.
        # else: # Optional: Log if sending is skipped
            # print(f"Skipped sending MIDI message (output port unavailable): {msg}")


    def send_cc(self, control: int, value: int, channel: int = 15):
        """Sends a MIDI Control Change message."""
        # --- DEBUG PRINT (Optional) ---
        # port_status = "Not Initialized"
        # if self.output_port:
        #     port_status = "Open" if not self.output_port.closed else "Closed"
        # print(f"[MIDI Send Debug] Attempting to send CC: Ch={channel+1}, CC={control}, Val={value}. Port Status: {port_status}")
        # --- END DEBUG ---

        if self.output_port and not self.output_port.closed:
            msg = mido.Message('control_change', control=control, value=value, channel=channel)
            self.send_message(msg)
        # else: # Optional: Log failure
            # print(f"Error: MIDI output port is not available to send CC {control}.")

    def close_ports(self):
        """Closes the MIDI input and output ports if they are open."""
        if self.input_port and not self.input_port.closed:
            try:
                self.input_port.close()
                print("MIDI Input port closed.")
            except Exception as e:
                print(f"Error closing MIDI Input port: {e}")
        self.input_port = None
        self.input_port_name = None

        if self.output_port and not self.output_port.closed:
            try:
                self.output_port.close()
                print("MIDI Output port closed.")
            except Exception as e:
                print(f"Error closing MIDI Output port: {e}")
        self.output_port = None
        self.output_port_name = None

    def get_status_string(self) -> str:
        """Returns a string summarizing the current MIDI connection status."""
        if self.is_searching:
            return self.error_message or "MIDI: Searching..."

        input_status = f"In: {self.input_port_name or 'N/A'}"
        output_status = "Out: N/A"
        if self.output_port_name:
            output_status = f"Out: {self.output_port_name}"
        elif find_midi_port(MIDI_DEVICE_NAME, verbose=False, port_type='output'):
            # If output exists but isn't open (e.g., failed initial connect/reconnect)
            output_status = "Out: Ready"

        # Combine input and output status
        return f"MIDI: {input_status} | {output_status}"
    