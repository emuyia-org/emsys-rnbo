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
    # Or perhaps better: assume the script is in the user's home dir?
    # This part might need adjustment depending on how the script is run.
    # Let's assume it's run from the standard user's home via sudo.
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

sudo apt install -y timeshift
timeshift --create --comments "Clean install"


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
    libsdl2-ttf-2.0-0

# 2. Install Specific Software Packages & Basic Configs

echo ">>> Installing Fastfetch..."
# Ensure we are in a temporary directory or home directory for downloading
cd "$HOME_DIR"
FASTFETCH_DEB_URL="https://github.com/fastfetch-cli/fastfetch/releases/download/${FASTFETCH_VERSION}/fastfetch-linux-${FASTFETCH_ARCH}.deb"
FASTFETCH_DEB_FILE="fastfetch-linux-${FASTFETCH_ARCH}.deb"
echo "   Downloading Fastfetch from $FASTFETCH_DEB_URL"
# Use curl -fSL to fail on error, follow redirects, and save with the remote name
curl -fSL -o "$FASTFETCH_DEB_FILE" "$FASTFETCH_DEB_URL"
dpkg -i "$FASTFETCH_DEB_FILE"
# Attempt to fix any dependency issues from dpkg install
apt-get install -f -y
rm "$FASTFETCH_DEB_FILE" # Clean up downloaded file

fastfetch

echo ">>> Installing Pisound..."
# Note: This script might require interaction or have its own dependencies.
# Running it non-interactively might require specific flags if available.
# Consider reviewing the install.sh script itself for non-interactive options.
curl https://blokas.io/pisound/install.sh | sh

echo ">>> Installing Zoxide..."
# Run the installer as the regular user, not root
sudo -u "$USER_INVOKING_SUDO" bash -c 'curl -sSfL https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/install.sh | bash'

# *** Zoxide Verification ***
ZOXIDE_PATH="$HOME_DIR/.local/bin/zoxide"
echo ">>> Verifying zoxide installation at $ZOXIDE_PATH..."
if [ -x "$ZOXIDE_PATH" ]; then
    echo "    Zoxide executable found and is executable."
else
    echo "!!! ERROR: Zoxide installation failed or $ZOXIDE_PATH is not executable." >&2
    echo "    Please check the output above for errors from the zoxide install script."
    # Decide if you want to exit here or continue
    # exit 1
fi

echo ">>> Installing FZF (Fuzzy Finder)..."
# Run git clone and install as the regular user
FZF_DIR="$HOME_DIR/.fzf"
if [ -d "$FZF_DIR" ]; then
  echo "    FZF directory already exists, skipping clone."
else
  sudo -u "$USER_INVOKING_SUDO" git clone --depth 1 https://github.com/junegunn/fzf.git "$FZF_DIR"
fi
# Run non-interactive install as the regular user
sudo -u "$USER_INVOKING_SUDO" "$FZF_DIR/install" --all

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

# 3. Configure Shell Environment (.bashrc and .profile for the specific user)

BASHRC_FILE="$HOME_DIR/.bashrc"
echo ">>> Configuring $BASHRC_FILE..."

# Function to add line to bashrc if not already present
add_to_bashrc() {
    local line="$1"
    local file="$2"
    # Use grep -Fxq for fixed string, exact match, quiet mode
    grep -Fxq "$line" "$file" || echo "$line" >> "$file"
}

# Ensure .local/bin is in PATH (important for zoxide, pipx, etc.)
# Use $HOME_DIR variable directly instead of relying on $HOME expansion later
add_to_bashrc 'export PATH="'"$HOME_DIR"'/.local/bin:$PATH"' "$BASHRC_FILE"

# Add zoxide init
add_to_bashrc 'eval "$(zoxide init bash)"' "$BASHRC_FILE"

# Add z alias for zoxide (optional, common practice)
add_to_bashrc 'alias cd="z"' "$BASHRC_FILE"

# Add Pyenv environment variables and init
add_to_bashrc 'export PYENV_ROOT="$HOME/.pyenv"' "$BASHRC_FILE" # $HOME is usually fine here for pyenv
add_to_bashrc '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' "$BASHRC_FILE"
add_to_bashrc 'eval "$(pyenv init - bash)"' "$BASHRC_FILE"

# Note: FZF install --all should have already modified .bashrc

# 4. Setup Python using Pyenv AND Application Virtual Environment

echo ">>> Setting up Python $PYTHON_VERSION using Pyenv and application venv..."
# Need to run pyenv commands AND venv setup as the actual user.
# Source bashrc within the sudo -u context to get pyenv functions.
# Use bash -i for an interactive shell to ensure .bashrc/.profile sourcing.
sudo -u "$USER_INVOKING_SUDO" bash -i << PYENV_APP_SETUP_SCRIPT
set -e # Exit inner script on error

echo "   Sourcing shell configuration for pyenv commands..."
# Ensure PYENV_ROOT is set if not already exported by .bashrc/.profile sourcing via 'bash -i'
export PYENV_ROOT="\$HOME/.pyenv" # Use \$HOME for expansion within the subshell
export PATH="\$PYENV_ROOT/bin:\$PATH"

# Evaluate pyenv init. Needs to happen *after* PATH is potentially set.
eval "\$(pyenv init --path)" # Handle PATH modification first
eval "\$(pyenv init - bash)" # Then setup shims

echo "   Ensuring Python $PYTHON_VERSION is installed..."
if pyenv versions --bare | grep -q "^$PYTHON_VERSION$"; then
  echo "   Python $PYTHON_VERSION already installed."
else
  echo "   Installing Python $PYTHON_VERSION (this may take a while)..."
  pyenv install "$PYTHON_VERSION"
fi

echo "   Setting global Python version to $PYTHON_VERSION..."
pyenv global "$PYTHON_VERSION"

echo "   Verifying Python version (pyenv):"
pyenv version # Shows the active pyenv version
echo "   Verifying Python version (executable):"
python --version # Verify the actual python executable linked by pyenv shims

# --- Application Specific Python Setup ---
# Define directories relative to the user's HOME inside the subshell
APP_DIR="\$HOME/emsys-rnbo" # Use \$HOME for expansion within the subshell
VENV_DIR="\$APP_DIR/.venv"
REQS_FILE="\$APP_DIR/requirements.txt"

echo "   Creating/updating virtual environment at \$VENV_DIR using pyenv Python..."
# Create the venv using the now-active pyenv python
# The 'python' command here should resolve to the pyenv shim for 3.11.11
if python -m venv "\$VENV_DIR"; then
    echo "   Virtual environment created/updated successfully."
else
    echo "!!! ERROR: Failed to create virtual environment at \$VENV_DIR" >&2
    exit 1 # Exit the subshell script if venv creation fails
fi

echo "   Upgrading pip in the virtual environment..."
# Directly call the pip from the virtual environment
# Use quotes around the path to handle potential special characters
if "\$VENV_DIR/bin/pip" install --upgrade pip; then
    echo "   pip upgraded successfully."
else
    echo "!!! ERROR: Failed to upgrade pip in \$VENV_DIR" >&2
    exit 1 # Exit the subshell script if pip upgrade fails
fi

echo "   Installing requirements from \$REQS_FILE..."
if [ -f "\$REQS_FILE" ]; then
    if "\$VENV_DIR/bin/pip" install -r "\$REQS_FILE"; then
        echo "   Requirements installed successfully."
    else
        echo "!!! ERROR: Failed to install requirements from \$REQS_FILE" >&2
        exit 1 # Exit the subshell script if requirements install fails
    fi
else
    echo "   Warning: requirements.txt not found at \$REQS_FILE. Skipping pip install -r."
fi

echo "   Python and application venv setup complete for user \$(whoami)."

PYENV_APP_SETUP_SCRIPT
# End of the sudo -u block. Back to running as root.

# 5. Application Specific Setup (emsys-rnbo - Non-Python parts like symlinks)

echo ">>> Setting up emsys-rnbo reboot script symlink..."
# This part still needs root privileges, so it stays outside the sudo -u block
EMSYSRNBO_DIR="$HOME_DIR/emsys-rnbo" # Use the previously determined HOME_DIR
PISOUND_BTN_SCRIPT_DIR="/usr/local/pisound/scripts/pisound-btn"
REBOOT_SCRIPT_SRC="$EMSYSRNBO_DIR/scripts/reboot.sh"
REBOOT_SCRIPT_DST="$PISOUND_BTN_SCRIPT_DIR/reboot.sh"

# Ensure the script exists and is executable *before* creating symlink
if [ -f "$REBOOT_SCRIPT_SRC" ]; then
    echo "   Making reboot script executable: $REBOOT_SCRIPT_SRC"
    # Permissions might need to be set before or after symlinking depending on needs
    # Setting them on the source file is generally correct.
    chmod +x "$REBOOT_SCRIPT_SRC"

    if [ -d "$PISOUND_BTN_SCRIPT_DIR" ]; then
        echo "   Creating symlink: $REBOOT_SCRIPT_DST -> $REBOOT_SCRIPT_SRC"
        # Use -f to force overwrite if link exists, -s for symbolic
        ln -sf "$REBOOT_SCRIPT_SRC" "$REBOOT_SCRIPT_DST"
    else
        echo "   Warning: Target directory $PISOUND_BTN_SCRIPT_DIR not found. Skipping symlink creation."
    fi
else
    echo "   Warning: Source script $REBOOT_SCRIPT_SRC not found. Skipping chmod and symlink creation."

# apt install -y python3-pip libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev libportmidi-dev

# usermod -a -G audio pi


# 7. Final Cleanup (Optional) and Reboot

echo ">>> Cleaning up APT cache..."
apt autoremove -y
apt clean

timeshift --create --comments "Post setup"
timeshift --list

echo "--- Setup Script Finished ---"
echo ">>> System will reboot now. <<<"

# 8. Reboot the System
reboot
