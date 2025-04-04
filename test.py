import pygame
import mido
import sys
import os

# --- Configuration ---
# !! IMPORTANT: Replace this with the exact name from mido.get_input_names() !!
MIDI_PORT_NAME = 'X-TOUCH MINI:X-TOUCH MINI MIDI 1 20:0'

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
    pygame.display.set_caption('Pygame MIDI Test')
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
midi_error = None
cc_value = 0 # Initial value

print(f"Attempting to open MIDI port: '{MIDI_PORT_NAME}'")
try:
    midi_port = mido.open_input(MIDI_PORT_NAME)
    print(f"Successfully opened MIDI port: {MIDI_PORT_NAME}")
except (IOError, ValueError) as e:
    print(f"Error opening MIDI port '{MIDI_PORT_NAME}': {e}")
    print("Available ports:", mido.get_input_names())
    midi_error = f"MIDI Error: Could not open '{MIDI_PORT_NAME}'. Check name/connection."

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
            for msg in midi_port.iter_pending():
                # Optional: print all messages for debugging
                # print(f"MIDI Received: {msg}")
                if msg.type == 'control_change' and msg.control == TARGET_CC:
                    cc_value = msg.value
                    # print(f"Target CC {TARGET_CC} updated to: {cc_value}") # Debug print
        elif not midi_error: # Should not happen if port closed unexpectedly
             midi_error = "MIDI port connection lost?"


        # --- Drawing ---
        screen.fill(BLACK) # Clear screen

        # Display MIDI Port Status
        if midi_port:
            status_text = f"Listening on: {MIDI_PORT_NAME}"
            status_color = WHITE
        else:
            status_text = midi_error or "MIDI Port not opened."
            status_color = GRAY
        status_surface = small_font.render(status_text, True, status_color)
        screen.blit(status_surface, (10, 10))

        # Display Target CC Info
        cc_info_text = f"Monitoring CC #{TARGET_CC}"
        cc_info_surface = main_font.render(cc_info_text, True, WHITE)
        screen.blit(cc_info_surface, (SCREEN_WIDTH // 2 - cc_info_surface.get_width() // 2, 60))

        # Display Current CC Value
        value_text = f"Value: {cc_value}"
        value_surface = main_font.render(value_text, True, WHITE)
        screen.blit(value_surface, (SCREEN_WIDTH // 2 - value_surface.get_width() // 2, 100))

        # Draw a simple bar graph
        bar_max_width = SCREEN_WIDTH - 40 # Max width of the bar
        bar_height = 50
        bar_x = 20
        bar_y = 160
        current_bar_width = int((cc_value / 127.0) * bar_max_width)

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

finally:
    # --- Cleanup ---
    print("Cleaning up...")
    if midi_port:
        print(f"Closing MIDI port: {MIDI_PORT_NAME}")
        midi_port.close()
    pygame.quit()
    print("Exited.")
    sys.exit(0) # Ensure clean exit code