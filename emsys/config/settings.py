"""
General settings for the Emsys application.
"""

import os

# Display settings
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320
FPS = 30

FEEDBACK_AREA_HEIGHT = 40

# Device settings
MIDI_DEVICE_NAME = 'X-TOUCH MINI'

# MIDI Reconnection Settings
RESCAN_INTERVAL_SECONDS = 3.0  # How often to scan for the device when disconnected
CONNECTION_CHECK_INTERVAL_SECONDS = 1.0 # How often to check if the connected device is still present

# --- Button Repeat Settings ---
# Delay in milliseconds after initial press before repeating starts
BUTTON_REPEAT_DELAY_MS = 500
# Interval in milliseconds between repeated actions
BUTTON_REPEAT_INTERVAL_MS = 25

# --- Color Definitions ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
GREY = (128, 128, 128)

# UI Specific Colors
HIGHLIGHT_COLOR = GREEN         # For selected items in lists
FEEDBACK_COLOR = BLUE           # For general feedback messages
ERROR_COLOR = RED               # For error messages
FOCUS_BORDER_COLOR = BLUE       # For indicating the focused UI column/area
# Add other colors as needed


# --- File Storage Settings ---
# Define where song files will be stored
# Use platform-independent path joining
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SONGS_DIR = os.path.join(PROJECT_ROOT, "data", "songs")