#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A simple MIDI listener service to start the main emsys services.

Listens for a specific MIDI CC message (YES button) and triggers
`sudo systemctl start emsys-python.service rnbooscquery-emsys.service`.

Requires passwordless sudo configured for the 'pi' user for this specific command.
"""

import mido
import mido.backends.rtmidi # Explicitly import backend
import time
import subprocess
import sys
import os

# --- Configuration ---
# Add the project root to sys.path to find config if needed, although hardcoding is fine here
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
config_path = os.path.join(project_root, 'emsys', 'config')
if config_path not in sys.path:
    sys.path.insert(0, config_path)

try:
    from config import settings, mappings
    MIDI_DEVICE_NAME = settings.MIDI_DEVICE_NAME
    START_BUTTON_CC = mappings.YES_NAV_CC # CC 89
except ImportError:
    print("Warning: Could not import settings/mappings. Using hardcoded defaults.")
    MIDI_DEVICE_NAME = 'X-TOUCH MINI' # Fallback
    START_BUTTON_CC = 89 # Fallback for YES button CC

RESCAN_INTERVAL_SECONDS = 5.0
PYTHON_SERVICE_NAME = "emsys-python.service"
RNBO_SERVICE_NAME = "rnbooscquery-emsys.service"
# --- End Configuration ---

def find_midi_input_port(device_name):
    """Finds the MIDI input port name matching the device name."""
    try:
        input_ports = mido.get_input_names()
        for port in input_ports:
            if device_name in port:
                return port
    except Exception as e:
        print(f"Error getting MIDI input names: {e}")
    return None

def start_services():
    """Executes the systemctl command to start the services."""
    command = ['sudo', 'systemctl', 'start', PYTHON_SERVICE_NAME, RNBO_SERVICE_NAME]
    print(f"Executing: {' '.join(command)}")
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print("Services started successfully.")
        print(result.stdout)
        return True
    except FileNotFoundError:
        print(f"Error: 'sudo' command not found. Make sure sudo is installed and in PATH.")
    except subprocess.CalledProcessError as e:
        print(f"Error starting services:")
        print(f"  Command: {' '.join(e.cmd)}")
        print(f"  Return Code: {e.returncode}")
        print(f"  Stderr: {e.stderr.strip()}")
        print(f"  Stdout: {e.stdout.strip()}")
        print("Ensure passwordless sudo is configured correctly for this command.")
    except Exception as e:
        print(f"An unexpected error occurred while starting services: {e}")
    return False

def main_loop():
    """Main loop to listen for MIDI and trigger service start."""
    input_port = None
    port_name = None

    while True:
        if input_port is None or input_port.closed:
            print(f"Searching for MIDI input device: '{MIDI_DEVICE_NAME}'...")
            port_name = find_midi_input_port(MIDI_DEVICE_NAME)
            if port_name:
                try:
                    input_port = mido.open_input(port_name)
                    print(f"Successfully opened MIDI Input: '{port_name}'")
                    print(f"Listening for START button (CC {START_BUTTON_CC})...")
                except (IOError, OSError, mido.MidiError) as e:
                    print(f"Error opening '{port_name}': {e}")
                    input_port = None
                    time.sleep(RESCAN_INTERVAL_SECONDS) # Wait before retrying
                except Exception as e:
                     print(f"Unexpected error opening port: {e}")
                     input_port = None
                     time.sleep(RESCAN_INTERVAL_SECONDS)
            else:
                print(f"Device '{MIDI_DEVICE_NAME}' not found. Retrying in {RESCAN_INTERVAL_SECONDS}s...")
                time.sleep(RESCAN_INTERVAL_SECONDS)
                continue # Go back to searching

        # If port is open, listen for messages
        if input_port and not input_port.closed:
            try:
                for msg in input_port.iter_pending():
                    if msg.type == 'control_change' and msg.control == START_BUTTON_CC and msg.value == 127:
                        print(f"\nStart button (CC {START_BUTTON_CC}) pressed!")
                        # --- Always attempt to start, let systemd handle it if already running ---
                        if start_services():
                            print("Services start command issued.")
                        else:
                            print("Failed to issue start command for services. Continuing to listen...")

                # Basic connection check (less robust than main app's)
                if port_name not in mido.get_input_names():
                    print(f"\nMIDI device '{port_name}' disconnected.")
                    input_port.close()
                    input_port = None
                    port_name = None
                    # No need to sleep here, the outer loop will handle retry delay

                time.sleep(0.01) # Small sleep to prevent busy-waiting

            except (IOError, OSError, mido.MidiError) as e:
                print(f"\nMIDI Read/Connection Error: {e}")
                if input_port: input_port.close()
                input_port = None
                port_name = None
                time.sleep(RESCAN_INTERVAL_SECONDS) # Wait before trying to reconnect
            except Exception as e:
                 print(f"\nUnexpected error in MIDI loop: {e}")
                 if input_port: input_port.close()
                 input_port = None
                 port_name = None
                 time.sleep(RESCAN_INTERVAL_SECONDS)

if __name__ == "__main__":
    print("--- Emsys Starter Service ---")
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Exiting starter script.")
    except Exception as e:
        print(f"\nUnhandled exception in main: {e}")
    finally:
        print("Starter script finished.")
        sys.exit(0)

