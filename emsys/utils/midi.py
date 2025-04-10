# emsys/utils/midi.py
"""
MIDI utility functions for the Emsys application.
"""

import mido

def find_midi_port(base_name, verbose=True):
    """
    Searches for MIDI input port containing base_name.

    Args:
        base_name (str): The partial name of the MIDI device.
        verbose (bool): If True, print detailed search information.

    Returns:
        str: The full name of the found MIDI port, or None if not found.
    """
    if verbose:
        print(f"Searching for MIDI input port containing: '{base_name}'")
    try:
        available_ports = mido.get_input_names()
        if verbose:
            print("Available ports:", available_ports)
        for port_name in available_ports:
            if base_name in port_name:
                if verbose:
                    print(f"Found matching port: '{port_name}'")
                return port_name
    except Exception as e:
        print(f"Error getting MIDI port names: {e}")
    if verbose:
        print(f"No MIDI input port found containing '{base_name}'.")
    return None

