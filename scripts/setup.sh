#!/bin/bash

# Script to set up Raspberry Pi with essential tools, Python, and configurations.

# --- Configuration ---
PYTHON_VERSION="3.11.11"
FASTFETCH_VERSION="2.14.0" # Updated version number as of checking
FASTFETCH_ARCH="armv7l" # Adjust if using a 64-bit OS (aarch64)
# Check Pi Model/OS Arch if needed: dpkg --print-architecture

# --- Script Start ---
echo "--- Starting Raspberry Pi Setup Script ---"

# Exit script immediately if any command fails
set -e

# Ensure the script is run as root/sudo
if [ "$(id -u)" -ne 0 ]; then
  echo "!!! This script must be run using sudo: sudo $0" >&2
  exit 1
fi

# Get the actual username of the user who invoked sudo
# If sudo is invoked directly by root, $SUDO_USER might be empty
if [ -n "$SUDO_USER" ]; then
    HOME_DIR=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    # Fallback for root or if SUDO_USER is not set
    HOME_DIR=$(eval echo ~root)
    echo "Warning: SUDO_USER not set, assuming script is run by standard user via sudo."
    HOME_DIR=$(getent passwd "$(logname)" | cut -d: -f6)
    if [ ! -d "$HOME_DIR" ]; then
        echo "Error: Could not determine the correct home directory." >&2
        exit 1
    fi
fi
# Ensure USER variable reflects the user invoking sudo, not root
USER_INVOKING_SUDO="${SUDO_USER:-$(logname)}"


echo ">>> Running as user: $USER_INVOKING_SUDO, Home directory: $HOME_DIR"


# 1. System Package Management (APT)
echo ">>> Updating package lists and upgrading system packages..."
apt update

# Install timeshift first for initial snapshot
echo ">>> Installing Timeshift..."
apt install -y timeshift
echo ">>> Creating initial Timeshift snapshot..."
timeshift --create --comments "Clean install before setup script" --yes || echo "Warning: Initial timeshift snapshot failed."


echo ">>> Upgrading existing packages..."
apt upgrade -y

echo ">>> Installing essential packages (git, build tools, libraries)..."
# Combine apt installs for efficiency
apt install -y \
    git \
    wget \
    gpg \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    curl \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev \
    libsdl2-2.0-0 \
    libsdl2-ttf-2.0-0 \
    dos2unix

# 2. Install Specific Software Packages & Basic Configs

echo ">>> Installing Fastfetch..."
cd /tmp # Use /tmp for temporary downloads
FASTFETCH_DEB_URL="https://github.com/fastfetch-cli/fastfetch/releases/download/${FASTFETCH_VERSION}/fastfetch-linux-${FASTFETCH_ARCH}.deb"
FASTFETCH_DEB_FILE="fastfetch-linux-${FASTFETCH_ARCH}.deb"
echo "   Downloading Fastfetch from $FASTFETCH_DEB_URL"
curl -fSL -o "$FASTFETCH_DEB_FILE" "$FASTFETCH_DEB_URL"
echo "   Installing Fastfetch package..."
dpkg -i "$FASTFETCH_DEB_FILE"
echo "   Fixing potential Fastfetch dependencies..."
apt-get install -f -y
rm "$FASTFETCH_DEB_FILE" # Clean up downloaded file
cd "$HOME_DIR" # Change back

echo ">>> Running fastfetch for verification..."
fastfetch

echo ">>> Installing Pisound..."
curl https://blokas.io/pisound/install.sh -o /tmp/pisound_install.sh
chmod +x /tmp/pisound_install.sh
sh /tmp/pisound_install.sh
rm /tmp/pisound_install.sh

echo ">>> Installing Zoxide..."
# Run the installer as the regular user, not root
sudo -u "$USER_INVOKING_SUDO" bash -c 'curl -sSfL https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/install.sh | bash'

# *** Zoxide Verification ***
ZOXIDE_PATH="$HOME_DIR/.local/bin/zoxide"
echo ">>> Verifying zoxide installation at $ZOXIDE_PATH..."
if sudo -u "$USER_INVOKING_SUDO" [ -x "$ZOXIDE_PATH" ]; then
    echo "    Zoxide executable found and is executable by $USER_INVOKING_SUDO."
else
    echo "!!! WARNING: Zoxide verification failed." >&2
fi

# Clone FZF repo first (needed for install script path)
echo ">>> Cloning FZF (Fuzzy Finder) repository if needed..."
FZF_DIR="$HOME_DIR/.fzf"
if [ -d "$FZF_DIR" ]; then
  echo "    FZF directory already exists, skipping clone."
else
  sudo -u "$USER_INVOKING_SUDO" git clone --depth 1 https://github.com/junegunn/fzf.git "$FZF_DIR"
fi

echo ">>> Installing Pyenv..."
# Run as the regular user
PYENV_DIR="$HOME_DIR/.pyenv"
if [ -d "$PYENV_DIR" ]; then
  echo "    Pyenv directory already exists, skipping installation."
else
  sudo -u "$USER_INVOKING_SUDO" bash -c 'curl -fsSL https://pyenv.run | bash'
fi

echo ">>> Disabling MOTD on SSH login for user $USER_INVOKING_SUDO..."
# Create the file as the regular user
sudo -u "$USER_INVOKING_SUDO" touch "$HOME_DIR/.hushlogin"
echo "    Created $HOME_DIR/.hushlogin"

# --------------------------------------------------------------------------
# 3. Configure Shell Environment (.bashrc for the specific user)
#    -- MOVED TO RUN *BEFORE* FZF INSTALLER --
# --------------------------------------------------------------------------

BASHRC_FILE="$HOME_DIR/.bashrc"
echo ">>> Configuring $BASHRC_FILE (Attempt 1: Before FZF Install)..."

# --- Helper Functions (Same as v6) ---
delete_from_file() {
    local pattern="$1"; local file="$2"; local user="$3"
    echo "      Removing lines matching pattern '$pattern' from $file..."
    sudo -u "$user" sed -i "\|$pattern|d" "$file"; return $?
}
add_to_bashrc() {
    local line="$1"; local file="$2"; local user="$3"
    echo "      DEBUG: Checking if line exists: $line"
    if sudo -u "$user" grep -Fxq "$line" "$file"; then
        echo "      Line already exists: $line"; return 0
    else
        local grep_exit_code=$?
        echo "      DEBUG: grep exit code: $grep_exit_code (0=found, 1=not found, >1=error)"
        if [ $grep_exit_code -eq 1 ]; then
            echo "      Adding line: $line"
            if sudo -u "$user" bash -c "echo \"$line\" >> \"$file\""; then
                echo "      DEBUG: Line appended successfully."; return 0
            else
                local echo_exit_code=$?; echo "      ERROR: Failed to append line to $file (Exit code: $echo_exit_code)" >&2; return $echo_exit_code
            fi
        else
            echo "      ERROR: grep command failed with exit code $grep_exit_code for file $file" >&2; return $grep_exit_code
        fi
    fi
}

# --- Configuration Steps ---
echo "    Creating backup of $BASHRC_FILE to ${BASHRC_FILE}.bak.\$(date +%F_%T)"
sudo -u "$USER_INVOKING_SUDO" cp "$BASHRC_FILE" "${BASHRC_FILE}.bak.$(date +%F_%T)" || echo "Warning: Failed to backup .bashrc"

echo "    Cleaning potentially problematic lines..."
delete_from_file '^eval$' "$BASHRC_FILE" "$USER_INVOKING_SUDO" || echo "Warning: delete eval failed"

echo "    Ensuring $HOME_DIR/.local/bin is in PATH..."
add_to_bashrc 'export PATH="'"$HOME_DIR"'/.local/bin:$PATH"' "$BASHRC_FILE" "$USER_INVOKING_SUDO" || echo "Warning: add local/bin PATH failed"

echo "    Cleaning/Adding zoxide configurations..."
delete_from_file 'zoxide init' "$BASHRC_FILE" "$USER_INVOKING_SUDO" || echo "Warning: delete zoxide init failed"
delete_from_file 'alias cd=z' "$BASHRC_FILE" "$USER_INVOKING_SUDO" || echo "Warning: delete zoxide alias failed"
add_to_bashrc 'eval "$(zoxide init bash)"' "$BASHRC_FILE" "$USER_INVOKING_SUDO" || echo "Warning: add zoxide init failed"
add_to_bashrc 'alias cd="z"' "$BASHRC_FILE" "$USER_INVOKING_SUDO" || echo "Warning: add zoxide alias failed"

echo "    Cleaning/Adding pyenv configurations..."
delete_from_file 'export PYENV_ROOT=' "$BASHRC_FILE" "$USER_INVOKING_SUDO" || echo "Warning: delete PYENV_ROOT failed"
delete_from_file 'export PATH=.*\$PYENV_ROOT/bin' "$BASHRC_FILE" "$USER_INVOKING_SUDO" || echo "Warning: delete pyenv PATH failed"
delete_from_file 'pyenv init' "$BASHRC_FILE" "$USER_INVOKING_SUDO" || echo "Warning: delete pyenv init failed"
delete_from_file 'pyenv virtualenv-init' "$BASHRC_FILE" "$USER_INVOKING_SUDO" || echo "Warning: delete pyenv virtualenv-init failed"
add_to_bashrc 'export PYENV_ROOT="$HOME/.pyenv"' "$BASHRC_FILE" "$USER_INVOKING_SUDO" || echo "Warning: add PYENV_ROOT failed"
add_to_bashrc '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' "$BASHRC_FILE" "$USER_INVOKING_SUDO" || echo "Warning: add pyenv PATH failed"
add_to_bashrc 'eval "$(pyenv init - bash)"' "$BASHRC_FILE" "$USER_INVOKING_SUDO" || echo "Warning: add pyenv init failed"

# --- Checkpoint 1: View .bashrc after our script modifies it ---
echo ">>> CHECKPOINT 1: Contents of $BASHRC_FILE after script's modifications:"
sudo -u "$USER_INVOKING_SUDO" cat "$BASHRC_FILE" || echo "Warning: Could not cat $BASHRC_FILE at Checkpoint 1"
echo ">>> End of Checkpoint 1."

# --------------------------------------------------------------------------
# 3b. Run FZF Installer *AFTER* configuring .bashrc
# --------------------------------------------------------------------------
echo ">>> Running FZF installation script (--all)..."
# FZF_DIR was defined earlier
if [ -f "$FZF_DIR/install" ]; then
    sudo -u "$USER_INVOKING_SUDO" "$FZF_DIR/install" --all
else
    echo "!!! ERROR: FZF install script not found at $FZF_DIR/install"
fi

# --- Checkpoint 2: View .bashrc after FZF installer runs ---
echo ">>> CHECKPOINT 2: Contents of $BASHRC_FILE after FZF installer:"
sudo -u "$USER_INVOKING_SUDO" cat "$BASHRC_FILE" || echo "Warning: Could not cat $BASHRC_FILE at Checkpoint 2"
echo ">>> End of Checkpoint 2."

# --------------------------------------------------------------------------
# 4. Setup Python using Pyenv AND Application Virtual Environment
#    (This section remains the same as before)
# --------------------------------------------------------------------------

echo ">>> Setting up Python $PYTHON_VERSION using Pyenv and application venv..."
# Need to run pyenv commands AND venv setup as the actual user.
sudo -u "$USER_INVOKING_SUDO" bash -i << PYENV_APP_SETUP_SCRIPT
set -e # Exit inner script on error

echo "   Sourcing shell configuration for pyenv commands..."
export PYENV_ROOT="\$HOME/.pyenv" # Use \$HOME for expansion within the subshell
export PATH="\$PYENV_ROOT/bin:\$PATH"

if command -v pyenv &> /dev/null; then
    eval "\$(pyenv init --path)"
    eval "\$(pyenv init - bash)"
else
    echo "!!! ERROR: pyenv command not found in subshell PATH. Check .bashrc configuration." >&2
    exit 1
fi

echo "   Ensuring Python $PYTHON_VERSION is installed..."
if pyenv versions --bare | grep -q "^$PYTHON_VERSION$"; then
  echo "   Python $PYTHON_VERSION already installed."
else
  echo "   Installing Python $PYTHON_VERSION (this may take a while)..."
  pyenv install "$PYTHON_VERSION"
fi

echo "   Setting global Python version to $PYTHON_VERSION..."
pyenv global "$PYTHON_VERSION"

echo "   Verifying Python version (pyenv):"; pyenv version
echo "   Verifying Python version (executable):"; python --version

APP_DIR="\$HOME/emsys-rnbo"; VENV_DIR="\$APP_DIR/.venv"; REQS_FILE="\$APP_DIR/requirements.txt"
echo "   Ensuring application directory exists: \$APP_DIR"; mkdir -p "\$APP_DIR"

echo "   Creating/updating virtual environment at \$VENV_DIR using pyenv Python..."
if python -m venv "\$VENV_DIR"; then
    echo "   Virtual environment created/updated successfully."
else
    echo "!!! ERROR: Failed to create virtual environment at \$VENV_DIR" >&2; exit 1
fi

echo "   Upgrading pip in the virtual environment..."
if "\$VENV_DIR/bin/pip" install --upgrade pip; then
    echo "   pip upgraded successfully."
else
    echo "!!! ERROR: Failed to upgrade pip in \$VENV_DIR" >&2; exit 1
fi

echo "   Installing requirements from \$REQS_FILE..."
if [ -f "\$REQS_FILE" ]; then
    if "\$VENV_DIR/bin/pip" install -r "\$REQS_FILE"; then
        echo "   Requirements installed successfully."
    else
        echo "!!! ERROR: Failed to install requirements from \$REQS_FILE" >&2; exit 1
    fi
else
    echo "   Warning: requirements.txt not found at \$REQS_FILE. Skipping pip install -r."
fi

echo "   Python and application venv setup complete for user \$(whoami)."

PYENV_APP_SETUP_SCRIPT
# End of the sudo -u block. Back to running as root.

# --------------------------------------------------------------------------
# 5. Application Specific Setup (emsys-rnbo - Non-Python parts like symlinks)
#    (This section remains the same as before)
# --------------------------------------------------------------------------
echo ">>> Setting up emsys-rnbo reboot script symlink..."
EMSYSRNBO_DIR="$HOME_DIR/emsys-rnbo"
PISOUND_BTN_SCRIPT_DIR="/usr/local/pisound/scripts/pisound-btn"
REBOOT_SCRIPT_SRC="$EMSYSRNBO_DIR/scripts/reboot.sh"
REBOOT_SCRIPT_DST="$PISOUND_BTN_SCRIPT_DIR/reboot.sh"

if [ -f "$REBOOT_SCRIPT_SRC" ]; then
    echo "   Making reboot script executable: $REBOOT_SCRIPT_SRC"
    chmod +x "$REBOOT_SCRIPT_SRC"
    if [ -d "$PISOUND_BTN_SCRIPT_DIR" ]; then
        echo "   Creating symlink: $REBOOT_SCRIPT_DST -> $REBOOT_SCRIPT_SRC"
        ln -sf "$REBOOT_SCRIPT_SRC" "$REBOOT_SCRIPT_DST"
    else
        echo "   Warning: Target directory $PISOUND_BTN_SCRIPT_DIR not found. Skipping symlink creation."
    fi
else
    echo "   Warning: Source script $REBOOT_SCRIPT_SRC not found. Skipping chmod and symlink creation."
fi

# Ensure the pi user is in the audio group (common requirement for audio apps)
echo ">>> Ensuring user $USER_INVOKING_SUDO is in the 'audio' group..."
usermod -a -G audio "$USER_INVOKING_SUDO"


# 7. Final Cleanup (Optional) and Reboot

echo ">>> Cleaning up APT cache..."
apt autoremove -y
apt clean

echo ">>> Creating final Timeshift snapshot..."
timeshift --create --comments "Post setup script completion" --yes || echo "Warning: Final timeshift snapshot failed."
timeshift --list

echo "--- Setup Script Finished ---"
echo ">>> System will reboot now. <<<"

# 8. Reboot the System
reboot
