# emsys/config/mappings.py
"""
X-TOUCH MINI
Button ref: (L)ayer A-B // (C)olumn 1-8 // (R)ow 1-2
Reference: resources/xtouch_midi_ref.txt
"""

# MIDI CC numbers for screen navigation (Layer B Buttons)
NEXT_CC = 82 # B_BTN_1
PREV_CC = 90 # B_BTN_9

# --- Navigation/Editing CCs (Layer B Buttons) ---
UP_NAV_CC = 88  # B_BTN_7
DOWN_NAV_CC = 96 # B_BTN_15
LEFT_NAV_CC = 95 # B_BTN_14
RIGHT_NAV_CC = 97 # B_BTN_16
YES_NAV_CC = 89 # B_BTN_8
NO_NAV_CC = 87 # B_BTN_6

# --- Song Edit Specific CCs (Layer B Buttons) ---
RENAME_CC = 85 # B_BTN_4
SAVE_CC = 86 # B_BTN_5
DELETE_CC = 93 # B_BTN_12
CREATE_CC = 94 # B_BTN_13

# --- Transport Control CCs (Layer A Buttons) ---
PLAY_CC = 32 # A_BTN_15 (PLAY/CONTINUE)
STOP_CC = 31 # A_BTN_14 (STOP)
# PRIME is STOP (hold) + PLAY (press)

# --- Program Change Range ---
MIN_PROGRAM_MSG = 0
MAX_PROGRAM_MSG = 127

# --- Encoder CCs (Rotation/Value & Push) ---
# Layer A Encoder Turn: CC 10-17
KNOB_A1_CC = 10 # Encoder 1 Turn (Layer A)
KNOB_A2_CC = 11 # Encoder 2 Turn (Layer A)
KNOB_A3_CC = 12 # Encoder 3 Turn (Layer A)
KNOB_A4_CC = 13 # Encoder 4 Turn (Layer A)
KNOB_A5_CC = 14 # Encoder 5 Turn (Layer A)
KNOB_A6_CC = 15 # Encoder 6 Turn (Layer A)
KNOB_A7_CC = 16 # Encoder 7 Turn (Layer A)
KNOB_A8_CC = 17 # Encoder 8 Turn (Layer A)

# Layer B Encoder Turn: CC 74-81
KNOB_B1_CC = 74 # Encoder 1 Turn (Layer B)
KNOB_B2_CC = 75 # Encoder 2 Turn (Layer B)
KNOB_B3_CC = 76 # Encoder 3 Turn (Layer B)
KNOB_B4_CC = 77 # Encoder 4 Turn (Layer B)
KNOB_B5_CC = 78 # Encoder 5 Turn (Layer B)
KNOB_B6_CC = 79 # Encoder 6 Turn (Layer B)
KNOB_B7_CC = 80 # Encoder 7 Turn (Layer B)
KNOB_B8_CC = 81 # Encoder 8 Turn (Layer B)

# Layer A Encoder Push: CC 2-9
A_ENC_PUSH_1_CC = 2
A_ENC_PUSH_2_CC = 3
A_ENC_PUSH_3_CC = 4
A_ENC_PUSH_4_CC = 5
A_ENC_PUSH_5_CC = 6
A_ENC_PUSH_6_CC = 7
A_ENC_PUSH_7_CC = 8
A_ENC_PUSH_8_CC = 9

# Layer B Encoder Push: CC 66-73
B_ENC_PUSH_1_CC = 66
B_ENC_PUSH_2_CC = 67
B_ENC_PUSH_3_CC = 68
B_ENC_PUSH_4_CC = 69
B_ENC_PUSH_5_CC = 70
B_ENC_PUSH_6_CC = 71
B_ENC_PUSH_7_CC = 72
B_ENC_PUSH_8_CC = 73

# --- Fader CC ---
FADER_A_CC = 1 # Fader (Layer A)
FADER_B_CC = 65 # Fader (Layer B)

# --- Layer A Buttons (CC 18-33) ---
A_BTN_1_CC = 18
A_BTN_2_CC = 19
A_BTN_3_CC = 20
A_BTN_4_CC = 21
A_BTN_5_CC = 22
A_BTN_6_CC = 23
A_BTN_7_CC = 24
A_BTN_8_CC = 25
A_BTN_9_CC = 26
A_BTN_10_CC = 27
A_BTN_11_CC = 28
A_BTN_12_CC = 29
A_BTN_13_CC = 30
A_BTN_14_CC = 31
A_BTN_15_CC = 32
A_BTN_16_CC = 33

# --- Layer B Buttons (CC 82-97) ---
B_BTN_1_CC = 82
B_BTN_2_CC = 83
B_BTN_3_CC = 84
B_BTN_4_CC = 85
B_BTN_5_CC = 86
B_BTN_6_CC = 87
B_BTN_7_CC = 88
B_BTN_8_CC = 89
B_BTN_9_CC = 90
B_BTN_10_CC = 91
B_BTN_11_CC = 92
B_BTN_12_CC = 93
B_BTN_13_CC = 94
B_BTN_14_CC = 95
B_BTN_15_CC = 96
B_BTN_16_CC = 97

# --- Set of CCs that should NOT trigger the repeat mechanism ---
# Add any CC number here that represents a continuous control (fader, knob turn)
# even if it might send value 127 momentarily.
NON_REPEATABLE_CCS = {
    FADER_A_CC,
    FADER_B_CC,
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
    # Encoder Pushes and Buttons are momentary, so they are repeatable by default.
    # Transport controls (PLAY/STOP) are also momentary.
}
# -------------------------------------------------------------


# --- Button Name Mapping ---
# Dictionary to map CC numbers to user-friendly button/encoder push names
button_map = {
    # Layer A Encoder Pushes
    A_ENC_PUSH_1_CC: "A_ENC_PUSH_1",
    A_ENC_PUSH_2_CC: "A_ENC_PUSH_2",
    A_ENC_PUSH_3_CC: "A_ENC_PUSH_3",
    A_ENC_PUSH_4_CC: "A_ENC_PUSH_4",
    A_ENC_PUSH_5_CC: "A_ENC_PUSH_5",
    A_ENC_PUSH_6_CC: "A_ENC_PUSH_6",
    A_ENC_PUSH_7_CC: "A_ENC_PUSH_7",
    A_ENC_PUSH_8_CC: "A_ENC_PUSH_8",
    # Layer B Encoder Pushes
    B_ENC_PUSH_1_CC: "B_ENC_PUSH_1",
    B_ENC_PUSH_2_CC: "B_ENC_PUSH_2",
    B_ENC_PUSH_3_CC: "B_ENC_PUSH_3",
    B_ENC_PUSH_4_CC: "B_ENC_PUSH_4",
    B_ENC_PUSH_5_CC: "B_ENC_PUSH_5",
    B_ENC_PUSH_6_CC: "B_ENC_PUSH_6",
    B_ENC_PUSH_7_CC: "B_ENC_PUSH_7",
    B_ENC_PUSH_8_CC: "B_ENC_PUSH_8",
    # Layer A Buttons
    A_BTN_1_CC: "A_BTN_1",
    A_BTN_2_CC: "A_BTN_2",
    A_BTN_3_CC: "A_BTN_3",
    A_BTN_4_CC: "A_BTN_4",
    A_BTN_5_CC: "A_BTN_5",
    A_BTN_6_CC: "A_BTN_6",
    A_BTN_7_CC: "A_BTN_7",
    A_BTN_8_CC: "A_BTN_8",
    A_BTN_9_CC: "A_BTN_9",
    A_BTN_10_CC: "A_BTN_10",
    A_BTN_11_CC: "A_BTN_11",
    A_BTN_12_CC: "A_BTN_12",
    A_BTN_13_CC: "A_BTN_13",
    A_BTN_14_CC: "A_BTN_14",
    A_BTN_15_CC: "A_BTN_15",
    A_BTN_16_CC: "A_BTN_16",
    # Layer B Buttons
    B_BTN_1_CC: "B_BTN_1",
    B_BTN_2_CC: "B_BTN_2",
    B_BTN_3_CC: "B_BTN_3",
    B_BTN_4_CC: "B_BTN_4",
    B_BTN_5_CC: "B_BTN_5",
    B_BTN_6_CC: "B_BTN_6",
    B_BTN_7_CC: "B_BTN_7",
    B_BTN_8_CC: "B_BTN_8",
    B_BTN_9_CC: "B_BTN_9",
    B_BTN_10_CC: "B_BTN_10",
    B_BTN_11_CC: "B_BTN_11",
    B_BTN_12_CC: "B_BTN_12",
    B_BTN_13_CC: "B_BTN_13",
    B_BTN_14_CC: "B_BTN_14",
    B_BTN_15_CC: "B_BTN_15",
    B_BTN_16_CC: "B_BTN_16",
    # Fader CCs are not typically mapped as "buttons"

    # Layer B Nav/Edit Buttons
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
    # Layer A Transport Buttons
    PLAY_CC: "PLAY",
    STOP_CC: "STOP",
}
