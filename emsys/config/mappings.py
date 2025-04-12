# emsys/config/mappings.py
"""
X-TOUCH MINI
Button ref: (L)ayer A-B // (C)olumn 1-8 // (R)ow 1-2
"""

# MIDI CC numbers for screen navigation
NEXT_CC = 82 # NEXT
PREV_CC = 90 # PREV

# --- Navigation/Editing CCs (Layer B) ---
UP_NAV_CC = 88  # UP
DOWN_NAV_CC = 96 # DOWN
LEFT_NAV_CC = 95 # LEFT
RIGHT_NAV_CC = 97 # RIGHT
YES_NAV_CC = 89 # YES
NO_NAV_CC = 87 # NO

# --- Song Edit Specific CCs (Layer B) ---
RENAME_CC = 85 # RENAME
SAVE_CC = 86 # SAVE
DELETE_CC = 93 # DELETE
CREATE_CC = 94 # CREATE
