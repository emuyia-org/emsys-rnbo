import pygame
import mido
import sys
import os
import time # Import the time module for delays
import traceback # For printing detailed errors

# --- Configuration ---
DEVICE_BASE_NAME = 'X-TOUCH MINI'
TARGET_CC = 1
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BLUE = (0, 0, 255)
GRAY = (100, 100, 100)
YELLOW = (255, 255, 0) # For searching status
RED = (255, 0, 0) # For error status

# --- Reconnection & Check Settings ---
RESCAN_INTERVAL_SECONDS = 3 # How often to check for the device when disconnected
CONNECTION_CHECK_INTERVAL_SECONDS = 1.0 # How often to check if the connected device is still present
last_scan_time = 0
last_connection_check_time = 0 # Timer for the active connection check

# --- Function to find MIDI Port ---
def find_midi_port(base_name):
    # print(f"[find_midi_port] Searching for: '{base_name}'") # DEBUG
    try:
        available_ports = mido.get_input_names()
        # print(f"[find_midi_port] Available ports: {available_ports}") # DEBUG (can be verbose)
        for port_name in available_ports:
            if base_name in port_name:
                # print(f"[find_midi_port] Found matching port: '{port_name}'") # DEBUG
                return port_name
    except Exception as e:
        print(f"[find_midi_port] Error getting input names: {e}") # DEBUG
        # It's possible listing ports fails temporarily, treat as not found for robustness
        return None
    # print(f"[find_midi_port] No port found containing '{base_name}'.") # DEBUG
    return None

# --- Function to attempt opening MIDI Port ---
def attempt_open_midi_port(base_name):
    print(f"[attempt_open_midi_port] Trying to find '{base_name}'...") # DEBUG
    found_port_name = find_midi_port(base_name)
    if found_port_name:
        print(f"[attempt_open_midi_port] Device '{base_name}' found as '{found_port_name}'. Attempting to open...") # DEBUG
        try:
            # time.sleep(0.1) # Might be useful on reconnect
            midi_port = mido.open_input(found_port_name)
            print(f"[attempt_open_midi_port] Successfully opened MIDI port: {found_port_name}") # DEBUG
            return midi_port, found_port_name, None # Success
        except (IOError, ValueError, OSError, mido.MidiError) as e: # Catch mido specific errors too
            error_msg = f"Found '{found_port_name}', but failed to open: {e}"
            print(f"[attempt_open_midi_port] Error opening MIDI port '{found_port_name}': {e}") # DEBUG
            return None, None, error_msg # Found but couldn't open
        except Exception as e: # Catch other potential mido errors
             error_msg = f"Found '{found_port_name}', but unexpected error opening: {e}"
             print(f"[attempt_open_midi_port] Unexpected error opening '{found_port_name}': {e}") # DEBUG
             traceback.print_exc() # Print traceback for unexpected open errors
             return None, None, error_msg
    else:
        error_msg = f"MIDI device '{base_name}' not found."
        # print(f"[attempt_open_midi_port] {error_msg}") # DEBUG - Less verbose when searching
        return None, None, error_msg # Not found

# --- Function to trigger disconnection state ---
# Encapsulates the logic needed when a disconnect is detected (either by error or active check)
def handle_disconnection(port_to_close, name_to_clear, error_reason="Disconnected"):
    global midi_port, midi_port_name, midi_error, is_searching, last_scan_time
    print(f"\n--- Handling Disconnection (Reason: {error_reason}) ---") # DEBUG
    current_name = name_to_clear or "Unknown Port"
    midi_error = f"{error_reason} from '{current_name}'. Searching..."
    print(f"Setting error message: {midi_error}") # DEBUG
    if port_to_close:
        try:
            print(f"Attempting to close port: {current_name}") # DEBUG
            port_to_close.close()
            print(f"Port {current_name} closed.") # DEBUG
        except Exception as close_err:
            print(f"Error closing MIDI port (might be expected on disconnect): {close_err}") # DEBUG

    midi_port = None # Stop trying to read and trigger reconnection logic
    midi_port_name = None
    is_searching = True
    last_scan_time = time.time() # Start scan timer immediately
    print(f"Set midi_port=None, is_searching=True. Starting scan timer.") # DEBUG
    print("----------------------------------------------------\n") # DEBUG


# --- Initialization ---
print("Initializing Pygame...")
pygame.init()
pygame.font.init()

# Set up display
try:
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption('Pygame MIDI Auto-Detect & Reconnect Test')
    print(f"Display initialized ({SCREEN_WIDTH}x{SCREEN_HEIGHT})")
except pygame.error as e:
    print(f"Error initializing display: {e}")
    sys.exit(1)

# Set up font
try:
    main_font = pygame.font.SysFont(None, 36)
    small_font = pygame.font.SysFont(None, 24)
except Exception as e:
    print(f"Error loading font: {e}. Using pygame default.")
    main_font = pygame.font.Font(None, 36)
    small_font = pygame.font.Font(None, 24)

# --- MIDI Setup ---
midi_port = None
midi_port_name = None
midi_error = None
cc_value = 0
is_searching = False

# Initial attempt to connect
print("--- Initial MIDI Connection Attempt ---")
midi_port, midi_port_name, midi_error = attempt_open_midi_port(DEVICE_BASE_NAME)
if not midi_port:
    print(f"Initial connection failed: {midi_error}")
    is_searching = True
    last_scan_time = time.time()
    print("Setting state to SEARCHING.") # DEBUG
else:
    print(f"Initial connection SUCCESSFUL to {midi_port_name}") # DEBUG
    last_connection_check_time = time.time() # Start connection check timer only if connected
print("------------------------------------")

# --- Main Loop ---
running = True
clock = pygame.time.Clock()

print("Starting main loop... Press Ctrl+C in terminal or close window to exit.")

try:
    while running:
        current_time = time.time()

        # --- Event Handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        # --- MIDI Input Handling & Reconnection ---
        if midi_port:
            # --- Active Connection Check ---
            if (current_time - last_connection_check_time) >= CONNECTION_CHECK_INTERVAL_SECONDS:
                # print(f"[Active Check] Checking if '{midi_port_name}' is still available...") # DEBUG - Verbose
                last_connection_check_time = current_time
                try:
                    available_ports = mido.get_input_names()
                    if midi_port_name not in available_ports:
                        print(f"[Active Check] Port '{midi_port_name}' is GONE from available ports: {available_ports}") # DEBUG
                        # Trigger the disconnection logic manually
                        handle_disconnection(midi_port, midi_port_name, "Device not listed")
                        # Skip the rest of the MIDI processing for this frame as we just disconnected
                        continue # Go to the next iteration of the main loop
                    # else: # DEBUG - Verbose
                    #    print(f"[Active Check] Port '{midi_port_name}' still listed.") # DEBUG
                except Exception as check_err:
                    # Handle error during the check itself (less likely, but possible)
                    print(f"[Active Check] Error while checking available ports: {check_err}") # DEBUG
                    # Optionally trigger disconnect here too, or just log and retry next time
                    # handle_disconnection(midi_port, midi_port_name, f"Port check error: {check_err}")
                    # continue

            # --- Process MIDI Messages (only if still connected after check) ---
            try:
                while True: # Process all available messages non-blockingly
                    msg = midi_port.receive(block=False)
                    if msg is None:
                        break # No more messages pending
                    # Process the received message
                    # print(f"MIDI Received: {msg}") # Optional debug
                    if msg.type == 'control_change' and msg.control == TARGET_CC:
                        cc_value = msg.value
                        # print(f"Target CC {TARGET_CC} updated to: {cc_value}") # Debug print

            except (OSError, mido.MidiError) as e: # Catch actual read errors if they ever occur
                print(f"\n--- MIDI Read/Receive Error ({type(e).__name__}) ---") # DEBUG
                print(f"Error details: {e}") # DEBUG
                handle_disconnection(midi_port, midi_port_name, f"Read error: {e}")
                continue # Skip rest of loop iteration

            except Exception as e:
                # Handle other potential errors during MIDI processing
                print(f"\n--- Unexpected MIDI Error During Receive ---") # DEBUG
                print(f"Error type: {type(e)}") # DEBUG
                print(f"Error details: {e}") # DEBUG
                traceback.print_exc()
                # Use handle_disconnection for cleanup, but maybe don't auto-search?
                handle_disconnection(midi_port, midi_port_name, f"Unexpected error: {e}")
                is_searching = False # Stop searching on truly unexpected errors
                midi_error = f"Unexpected MIDI Error: {e}. Stopped."
                print("------------------------------------------\n") # DEBUG
                # Optionally stop the app: running = False


        # --- Attempt Reconnection if Disconnected ---
        if midi_port is None and is_searching:
            if (current_time - last_scan_time) >= RESCAN_INTERVAL_SECONDS:
                print(f"\n[Reconnect Check] Time to scan ({current_time - last_scan_time:.1f}s elapsed).") # DEBUG
                last_scan_time = current_time # Reset scan timer

                try:
                    current_ports = mido.get_input_names()
                    print(f"[Reconnect Check] Available MIDI inputs: {current_ports}") # DEBUG
                except Exception as list_err:
                     print(f"[Reconnect Check] Error listing MIDI ports: {list_err}") # DEBUG
                     current_ports = []

                print(f"[Reconnect Check] Attempting to find and open '{DEVICE_BASE_NAME}'...") # DEBUG
                time.sleep(0.2) # Small delay before opening
                new_port, new_name, error = attempt_open_midi_port(DEVICE_BASE_NAME)

                if new_port:
                    print(f"[Reconnect Check] SUCCESS! Reconnected to '{new_name}'.") # DEBUG
                    midi_port = new_port
                    midi_port_name = new_name
                    midi_error = None # Clear error
                    is_searching = False # Stop searching
                    last_connection_check_time = current_time # Reset connection check timer
                    print(f"[Reconnect Check] Cleared error, set is_searching=False.") # DEBUG
                    cc_value = 0 # Optional: Reset CC value
                else:
                    # Keep searching, update error message
                    new_error_msg = (error or f"Device '{DEVICE_BASE_NAME}' not found.") + " Retrying..."
                    if new_error_msg != midi_error:
                         print(f"[Reconnect Check] Failed to reconnect. Error: {error}") # DEBUG
                         midi_error = new_error_msg
                         print(f"[Reconnect Check] Updated error message: {midi_error}") # DEBUG
                    is_searching = True # Ensure searching continues
                print("-" * 20) # Separator


        # --- Drawing ---
        screen.fill(BLACK) # Clear screen

        # Display MIDI Port Status
        status_color = WHITE
        if midi_port and midi_port_name:
            status_text = f"Connected: {midi_port_name}"
        elif is_searching:
            status_text = midi_error or f"Searching for '{DEVICE_BASE_NAME}'..."
            status_color = YELLOW # Indicate searching state
        else:
            status_text = midi_error or "MIDI Port not available."
            status_color = RED # Indicate error state more clearly

        status_surface = small_font.render(status_text, True, status_color)
        # Text wrapping logic (same as before)
        status_rect = status_surface.get_rect(topleft=(10, 10))
        if status_rect.width > SCREEN_WIDTH - 20:
             words = status_text.split(' ')
             lines = []
             current_line = ""
             for word in words:
                 test_line = current_line + word + " "
                 test_surface = small_font.render(test_line, True, status_color)
                 if test_surface.get_width() < SCREEN_WIDTH - 20:
                     current_line = test_line
                 else:
                     lines.append(current_line)
                     current_line = word + " "
             lines.append(current_line)
             y_offset = 10
             for line in lines:
                 line_surface = small_font.render(line.strip(), True, status_color)
                 screen.blit(line_surface, (10, y_offset))
                 y_offset += small_font.get_linesize()
        else:
             screen.blit(status_surface, status_rect)


        # Display Target CC Info
        cc_info_text = f"Monitoring CC #{TARGET_CC}"
        cc_info_surface = main_font.render(cc_info_text, True, WHITE)
        screen.blit(cc_info_surface, (SCREEN_WIDTH // 2 - cc_info_surface.get_width() // 2, 80))

        # Display Current CC Value
        value_text = f"Value: {cc_value}"
        value_surface = main_font.render(value_text, True, WHITE)
        screen.blit(value_surface, (SCREEN_WIDTH // 2 - value_surface.get_width() // 2, 120))

        # Draw a simple bar graph
        bar_max_width = SCREEN_WIDTH - 40
        bar_height = 50
        bar_x = 20
        bar_y = 180
        normalized_value = max(0, min(127, cc_value))
        current_bar_width = int((normalized_value / 127.0) * bar_max_width)

        pygame.draw.rect(screen, GRAY, (bar_x, bar_y, bar_max_width, bar_height), 2)
        if current_bar_width > 0:
            bar_color = BLUE if midi_port else GRAY
            pygame.draw.rect(screen, bar_color, (bar_x, bar_y, current_bar_width, bar_height))

        # Display instructions
        instr_text = "Move controller CC #{}. Press ESC or close window to exit.".format(TARGET_CC)
        instr_surface = small_font.render(instr_text, True, GRAY)
        screen.blit(instr_surface, (10, SCREEN_HEIGHT - 30))

        # --- Update Display ---
        pygame.display.flip()

        # --- Control Framerate ---
        clock.tick(60)

except KeyboardInterrupt:
    print("\nExiting due to Ctrl+C")
    running = False
except Exception as e:
    print(f"\n--- An unexpected error occurred in the main loop ---") # DEBUG
    print(f"Error type: {type(e)}") # DEBUG
    print(f"Error details: {e}") # DEBUG
    traceback.print_exc() # Print full traceback
    running = False

finally:
    # --- Cleanup ---
    print("Cleaning up...")
    # Ensure port is closed even if handle_disconnection wasn't called before exit
    if midi_port:
        print(f"Closing MIDI port during final cleanup: {midi_port_name}")
        try:
            midi_port.close()
        except Exception as e:
            print(f"Error closing MIDI port during final cleanup: {e}")
    pygame.quit()
    print("Exited.")
    sys.exit(0)

