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

# --- Button Name Mapping ---
# Dictionary to map CC numbers to user-friendly button names
button_map = {
    NEXT_CC: "NEXT",
    PREV_CC: "PREV",
    UP_NAV_CC: "UP",
    DOWN_NAV_CC: "DOWN",
    LEFT_NAV_CC: "LEFT",
    RIGHT_NAV_CC: "RIGHT",
    YES_NAV_CC: "YES",
    NO_NAV_CC: "NO",
    RENAME_CC: "RENAME",
    SAVE_CC: "SAVE",
    DELETE_CC: "DELETE",
    CREATE_CC: "CREATE",
    # Add other CCs if they correspond to named buttons
}
