"""
General settings for the Emsys application.
"""

import os

# Display settings
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320
FPS = 30

# Device settings
MIDI_DEVICE_NAME = 'X-TOUCH MINI'

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)


# --- File Storage Settings ---
# Define where song files will be stored
# Use platform-independent path joining
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SONGS_DIR = os.path.join(PROJECT_ROOT, "data", "songs")