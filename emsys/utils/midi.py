# emsys/utils/midi.py
"""
MIDI utility functions for the Emsys application.
"""

import mido

def find_midi_port(base_name, verbose=True, port_type='input'):
    """
    Searches for MIDI port containing base_name.

    Args:
        base_name (str): The partial name of the MIDI device.
        verbose (bool): If True, print detailed search information.
        port_type (str): Type of port to find, either 'input' or 'output'.

    Returns:
        str: The full name of the found MIDI port, or None if not found.
    """
    if verbose:
        print(f"Searching for MIDI {port_type} port containing: '{base_name}'")
    try:
        if port_type == 'input':
            available_ports = mido.get_input_names()
        elif port_type == 'output':
            available_ports = mido.get_output_names()
        else:
            print(f"Error: Invalid port_type '{port_type}'. Must be 'input' or 'output'.")
            return None
            
        if verbose:
            print(f"Available {port_type} ports:", available_ports)
        for port_name in available_ports:
            if base_name in port_name:
                if verbose:
                    print(f"Found matching {port_type} port: '{port_name}'")
                return port_name
    except Exception as e:
        print(f"Error getting MIDI {port_type} port names: {e}")
    if verbose:
        print(f"No MIDI {port_type} port found containing '{base_name}'.")
    return None

