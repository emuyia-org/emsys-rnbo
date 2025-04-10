# emsys/config/mappings.py
"""
X-TOUCH MINI - MIDI CC REFERENCE
... (rest of docstring) ...
"""

# MIDI CC number designated for exiting the application (Layer B)
EXIT_CC = 47 # Button 8 Push

# MIDI CC numbers for screen navigation
NEXT_SCREEN_CC = 82 # Button 11
PREV_SCREEN_CC = 90 # Button 19

# --- Navigation/Editing CCs (Layer B) ---
UP_NAV_CC = 88      # Button 17
DOWN_NAV_CC = 96    # Button 25 (Bottom Right)
LEFT_NAV_CC = 95    # Button 24
RIGHT_NAV_CC = 97   # Button 26 (Encoder 8 Push)

YES_NAV_CC = 87     # Button 16 (Encoder 7 Push) - Often used for Increment/Confirm
NO_NAV_CC = 89      # Button 18 (Encoder 1 Push) - Often used for Decrement/Cancel

# --- Song Edit Specific CCs (Layer B) ---
SAVE_SONG_CC = 86   # Button 15 (Encoder 6 Push)
ADD_SEGMENT_CC = 85 # Button 14 (Encoder 5 Push)
DELETE_SEGMENT_CC = 93 # Button 22 (Encoder 3 Push)
CREATE_SONG_CC = 94 # Button 23 (Encoder 4 Push)
