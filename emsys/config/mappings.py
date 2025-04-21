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

# --- Transport Control CCs (Layer A) ---
PLAY_CC = 32 # PLAY/CONTINUE (Button A16)
STOP_CC = 31 # STOP (Button A15)
# PRIME is STOP (hold) + PLAY (press)

# --- Program Change Range ---
MIN_PROGRAM_MSG = 0
MAX_PROGRAM_MSG = 127

# --- Encoder CCs (Rotation/Value & Push) ---
# Assuming standard X-TOUCH MINI mapping for Layer B
# Knobs B1-B8 Rotation: CC 9-16
# Knobs B1-B8 Push: CC 73-80 (Incorrect assumption in previous log? Let's stick to 81 for B8 push for now as it was used)
# Knobs B1-B8 LED Value: CC 9-16
# Knobs B1-B8 LED Style: CC 25-32

# --- Fader CC ---
FADER_A_CC = 1 # CC for the fader (Layer B, Fader 9)
FADER_SELECT_CC = 65 # CC for the fader (Layer B, Fader 9)

# --- Placeholder Knob CCs (Add your actual CCs here later) ---
KNOB_A1_CC = 10
KNOB_A2_CC = 11
KNOB_A3_CC = 12
KNOB_A4_CC = 13
KNOB_A5_CC = 14
KNOB_A6_CC = 15
KNOB_A7_CC = 16
KNOB_A8_CC = 17
KNOB_B1_CC = 74
KNOB_B2_CC = 75
KNOB_B3_CC = 76
KNOB_B4_CC = 77
KNOB_B5_CC = 78
KNOB_B6_CC = 79
KNOB_B7_CC = 80
KNOB_B8_CC = 81
# --- End Placeholder Knobs ---

# --- Set of CCs that should NOT trigger the repeat mechanism ---
# Add any CC number here that represents a continuous control (fader, knob)
# even if it might send value 127 momentarily.
NON_REPEATABLE_CCS = {
    FADER_A_CC,
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
    # Add transport controls if they shouldn't repeat? Play/Stop are usually momentary.
    # PLAY_CC, # Let's allow repeat for now, might be useful? Revisit if needed.
    # STOP_CC,
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
    PLAY_CC: "PLAY", # Added
    STOP_CC: "STOP", # Added
    # Add other CCs if they correspond to named buttons
    # FADER_SELECT_CC is not a button, so not typically added here unless needed for UI hints
}
