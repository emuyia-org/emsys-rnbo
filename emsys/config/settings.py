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

# --- Colors ---
WHITE = (255, 255, 255)
CYAN = (0, 255, 255)
BLACK = (0, 0, 0)
GREY = (100, 100, 100)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)

# UI Specific Colors
HIGHLIGHT_COLOR = YELLOW # For selected text/items
FOCUS_BORDER_COLOR = BLUE # Border around the focused column/widget
ERROR_COLOR = RED
FEEDBACK_COLOR = GREEN
MULTI_SELECT_COLOR = (180, 180, 255) # Light blue/purple for multi-selected items
MULTI_SELECT_ANCHOR_COLOR = (100, 100, 255) # Darker blue/purple for the anchor in multi-select

# --- UI Layout ---


# --- File Storage Settings ---
# Define where song files will be stored
# Use platform-independent path joining
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SONGS_DIR = os.path.join(PROJECT_ROOT, "data", "songs")

# --- OSC Settings ---
RNBO_TARGET_IP = "127.0.0.1" # IP address of the RNBO runner
RNBO_TARGET_PORT = 1234      # Port the RNBO runner is listening on for OSC
OSC_RECEIVE_IP = "127.0.0.1" # IP address for this app to listen on (if needed)
OSC_RECEIVE_PORT = 1235      # Port for this app to listen on (if needed)