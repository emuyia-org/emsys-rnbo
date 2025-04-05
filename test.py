import pygame
import mido
import sys
import os

# --- Configuration ---
# Base name of the MIDI device to find
# The script will search for any port containing this string
DEVICE_BASE_NAME = 'X-TOUCH MINI'

# Choose a CC number to test (e.g., CC #1 is often the first fader/knob)
TARGET_CC = 1

# Screen dimensions (common for 3.5" screens, adjust if needed)
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BLUE = (0, 0, 255)
GRAY = (100, 100, 100)

# --- Function to find MIDI Port ---
def find_midi_port(base_name):
    """
    Searches for a MIDI input port containing the base_name.

    Args:
        base_name (str): The partial name of the MIDI device (e.g., 'X-TOUCH MINI').

    Returns:
        str: The full name of the found MIDI port, or None if not found.
    """
    print(f"Searching for MIDI input port containing: '{base_name}'")
    available_ports = mido.get_input_names()
    print("Available ports:", available_ports)
    for port_name in available_ports:
        if base_name in port_name:
            print(f"Found matching port: '{port_name}'")
            return port_name
    print(f"No MIDI input port found containing '{base_name}'.")
    return None

# --- Initialization ---
print("Initializing Pygame...")
# Try to ensure Pygame uses the framebuffer if run headless
# os.environ['SDL_VIDEODRIVER'] = 'fbcon' # Usually not needed now, but uncomment if display fails
# os.environ['SDL_FBDEV'] = '/dev/fb0'   # Usually not needed now
pygame.init()
pygame.font.init() # Initialize font module

# Set up display
try:
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption('Pygame MIDI Auto-Detect Test')
    print(f"Display initialized ({SCREEN_WIDTH}x{SCREEN_HEIGHT})")
except pygame.error as e:
    print(f"Error initializing display: {e}")
    print("Make sure HDMI screen is connected and OS can see it.")
    sys.exit(1)

# Set up font
try:
    # Use a default font if available, or specify path to a .ttf file
    main_font = pygame.font.SysFont(None, 36) # Try default system font
    small_font = pygame.font.SysFont(None, 24)
except Exception as e:
    print(f"Error loading font: {e}. Using pygame default.")
    main_font = pygame.font.Font(None, 36) # Pygame's default font
    small_font = pygame.font.Font(None, 24)


# --- MIDI Setup ---
midi_port = None
midi_port_name = None # Store the name of the port we actually open
midi_error = None
cc_value = 0 # Initial value

# Find the MIDI port dynamically
found_port_name = find_midi_port(DEVICE_BASE_NAME)

if found_port_name:
    midi_port_name = found_port_name # Store the found name
    print(f"Attempting to open MIDI port: '{midi_port_name}'")
    try:
        midi_port = mido.open_input(midi_port_name)
        print(f"Successfully opened MIDI port: {midi_port_name}")
    except (IOError, ValueError, OSError) as e: # Added OSError for potential system errors
        print(f"Error opening MIDI port '{midi_port_name}': {e}")
        midi_error = f"MIDI Error: Could not open '{midi_port_name}'. Check permissions/connection."
        midi_port_name = None # Reset name if opening failed
else:
    midi_error = f"MIDI Error: Device '{DEVICE_BASE_NAME}' not found. Check connection."
    print("Available ports listed above.")


# --- Main Loop ---
running = True
clock = pygame.time.Clock()

print("Starting main loop... Press Ctrl+C in terminal or close window to exit.")

try:
    while running:
        # --- Event Handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: # Allow exit with ESC key
                    running = False

        # --- MIDI Input Handling ---
        if midi_port:
            try:
                for msg in midi_port.iter_pending():
                    # Optional: print all messages for debugging
                    # print(f"MIDI Received: {msg}")
                    if msg.type == 'control_change' and msg.control == TARGET_CC:
                        cc_value = msg.value
                        # print(f"Target CC {TARGET_CC} updated to: {cc_value}") # Debug print
            except OSError as e:
                # Handle potential disconnection errors during runtime
                print(f"MIDI Read Error: {e}. Closing port.")
                midi_error = f"MIDI Error: Connection lost to '{midi_port_name}'?"
                midi_port.close()
                midi_port = None # Stop trying to read
        elif not midi_error: # If port is None but no error was set during init
              midi_error = "MIDI port was not opened successfully."


        # --- Drawing ---
        screen.fill(BLACK) # Clear screen

        # Display MIDI Port Status
        if midi_port and midi_port_name:
            status_text = f"Listening on: {midi_port_name}"
            status_color = WHITE
        else:
            # Display the specific error encountered
            status_text = midi_error or "MIDI Port not found or opened."
            status_color = GRAY
        status_surface = small_font.render(status_text, True, status_color)
        # Handle potentially long error messages
        status_rect = status_surface.get_rect(topleft=(10, 10))
        if status_rect.width > SCREEN_WIDTH - 20: # Wrap text if too long
             # Basic wrap (won't look perfect but prevents overflow)
             # A more robust text wrapping function would be better for complex cases
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

        else: # Draw normally if it fits
             screen.blit(status_surface, status_rect)


        # Display Target CC Info
        cc_info_text = f"Monitoring CC #{TARGET_CC}"
        cc_info_surface = main_font.render(cc_info_text, True, WHITE)
        screen.blit(cc_info_surface, (SCREEN_WIDTH // 2 - cc_info_surface.get_width() // 2, 80)) # Adjusted Y pos

        # Display Current CC Value
        value_text = f"Value: {cc_value}"
        value_surface = main_font.render(value_text, True, WHITE)
        screen.blit(value_surface, (SCREEN_WIDTH // 2 - value_surface.get_width() // 2, 120)) # Adjusted Y pos

        # Draw a simple bar graph
        bar_max_width = SCREEN_WIDTH - 40 # Max width of the bar
        bar_height = 50
        bar_x = 20
        bar_y = 180 # Adjusted Y pos
        # Ensure cc_value is within expected range 0-127 before calculating width
        normalized_value = max(0, min(127, cc_value))
        current_bar_width = int((normalized_value / 127.0) * bar_max_width)

        # Draw bar background/outline
        pygame.draw.rect(screen, GRAY, (bar_x, bar_y, bar_max_width, bar_height), 2)
        # Draw filled part of the bar
        if current_bar_width > 0:
            pygame.draw.rect(screen, BLUE, (bar_x, bar_y, current_bar_width, bar_height))

        # Display instructions
        instr_text = "Move controller CC #{}. Press ESC or close window to exit.".format(TARGET_CC)
        instr_surface = small_font.render(instr_text, True, GRAY)
        screen.blit(instr_surface, (10, SCREEN_HEIGHT - 30))


        # --- Update Display ---
        pygame.display.flip()

        # --- Control Framerate ---
        clock.tick(30) # Limit to 30 FPS

except KeyboardInterrupt:
    print("\nExiting due to Ctrl+C")
    running = False
except Exception as e:
    # Catch any other unexpected errors during the main loop
    print(f"\nAn unexpected error occurred: {e}")
    running = False


finally:
    # --- Cleanup ---
    print("Cleaning up...")
    if midi_port:
        print(f"Closing MIDI port: {midi_port_name}")
        try:
            midi_port.close()
        except Exception as e:
            print(f"Error closing MIDI port: {e}") # Log error but continue cleanup
    pygame.quit()
    print("Exited.")
    sys.exit(0) # Ensure clean exit code

