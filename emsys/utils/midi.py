"""
MIDI utility functions for the Emsys application.
"""

import mido

def find_midi_port(base_name):
    """Searches for MIDI input port containing base_name."""
    print(f"Searching for MIDI input port containing: '{base_name}'")
    try:
        available_ports = mido.get_input_names()
        print("Available ports:", available_ports)
        for port_name in available_ports:
            if base_name in port_name:
                print(f"Found matching port: '{port_name}'")
                return port_name
    except Exception as e:
        print(f"Error getting MIDI port names: {e}")
    print(f"No MIDI input port found containing '{base_name}'.")
    return None
