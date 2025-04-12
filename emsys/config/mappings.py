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

# --- Fader/Encoder CCs (Example) ---
FADER_SELECT_CC = 65 # Example: Fader on C1 (Layer A or B)
# --- Placeholder Knob CCs (Add your actual CCs here later) ---
KNOB_A1_CC = 10 # Example C1 Knob
KNOB_A2_CC = 11 # Example C2 Knob
KNOB_A3_CC = 12 # Example C3 Knob
KNOB_A4_CC = 13 # Example C4 Knob
KNOB_A5_CC = 14 # Example C5 Knob
KNOB_A6_CC = 15 # Example C6 Knob
KNOB_A7_CC = 16 # Example C7 Knob
KNOB_A8_CC = 17 # Example C8 Knob
KNOB_B1_CC = 74 # Example C1 Knob
KNOB_B2_CC = 75 # Example C2 Knob
KNOB_B3_CC = 76 # Example C3 Knob
KNOB_B4_CC = 77 # Example C4 Knob
KNOB_B5_CC = 78 # Example C5 Knob
KNOB_B6_CC = 79 # Example C6 Knob
KNOB_B7_CC = 80 # Example C7 Knob
KNOB_B8_CC = 81 # Example C8 Knob
# --- End Placeholder Knobs ---

# --- Set of CCs that should NOT trigger the repeat mechanism ---
# Add any CC number here that represents a continuous control (fader, knob)
# even if it might send value 127 momentarily.
NON_REPEATABLE_CCS = {
    FADER_SELECT_CC,
    KNOB_A1_CC,
    KNOB_A2_CC,
    KNOB_A3_CC,
    KNOB_A4_CC,
    KNOB_A5_CC,
    KNOB_A6_CC,
    KNOB_A7_CC,
    KNOB_A8_CC,
    KNOB_B1_CC,
    KNOB_B2_CC,
    KNOB_B3_CC,
    KNOB_B4_CC,
    KNOB_B5_CC,
    KNOB_B6_CC,
    KNOB_B7_CC,
    KNOB_B8_CC,
}
# -------------------------------------------------------------


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
    # FADER_SELECT_CC is not a button, so not typically added here unless needed for UI hints
}
