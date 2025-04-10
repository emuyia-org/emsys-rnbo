# emsys/config/mappings.py
"""
X-TOUCH MINI
Button ref: (L)ayer A-B // (C)olumn 1-8 // (R)ow 1-2
"""

# MIDI CC number designated for exiting the application (Layer B)
EXIT_CC = 47

# MIDI CC numbers for screen navigation
NEXT_SCREEN_CC = 82 # LB C1 R1
PREV_SCREEN_CC = 90 # LB C1 R2

# --- Navigation/Editing CCs (Layer B) ---
UP_NAV_CC = 88  # LB C7 R1
DOWN_NAV_CC = 96 # LB C7 R2
LEFT_NAV_CC = 95 # LB C6 R2
RIGHT_NAV_CC = 97 # LB C8 R2

YES_NAV_CC = 89 # LB C8 R1
NO_NAV_CC = 87 # LB C6 R1

# --- Song Edit Specific CCs (Layer B) ---
RENAME_SONG_CC = 85 # LB C3 R2
SAVE_SONG_CC = 86 # LB C5 R1
DELETE_SEGMENT_CC = 93 # LB C4 R2
ADD_SEGMENT_CC = 94 # LB C4 R1
CREATE_SONG_CC = 94 # LB C5 R2


