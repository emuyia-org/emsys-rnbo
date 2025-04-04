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
    debconf-utils # Needed for debconf-set-selections

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

# Ensure ownership of .bashrc is correct
chown "$USER_INVOKING_SUDO":"$(id -gn "$USER_INVOKING_SUDO")" "$BASHRC_FILE"

# --- Ensure .profile sources .bashrc for login shells ---
PROFILE_FILE="$HOME_DIR/.profile"
echo ">>> Ensuring login shells source .bashrc via $PROFILE_FILE..."

# Standard logic to source .bashrc from .profile for interactive bash shells
PROFILE_BASHRC_LOGIC=$(cat << 'EOF'
# Source .bashrc if it exists and the shell is interactive bash
if [ -n "$BASH_VERSION" ]; then
    if [ -r "$HOME/.bashrc" ]; then
        . "$HOME/.bashrc"
    fi
fi
EOF
)

# Check if the sourcing logic marker is already in .profile
# Using grep -Fq to search for a fixed string quietly. Using a unique part of the logic.
if [ -f "$PROFILE_FILE" ] && grep -Fq 'if [ -r "$HOME/.bashrc" ]; then' "$PROFILE_FILE"; then
    echo "    .bashrc sourcing logic already present in $PROFILE_FILE."
else
    echo "    Appending .bashrc sourcing logic to $PROFILE_FILE..."
    # Append the logic
    echo "$PROFILE_BASHRC_LOGIC" >> "$PROFILE_FILE"
    # Ensure ownership is correct
    chown "$USER_INVOKING_SUDO":"$(id -gn "$USER_INVOKING_SUDO")" "$PROFILE_FILE"
    # Ensure basic permissions (readable/writable by user)
    chmod u+rw "$PROFILE_FILE"
fi
# --- End .profile configuration ---


# 4. Setup Python using Pyenv

echo ">>> Setting up Python $PYTHON_VERSION using Pyenv..."
# Need to run pyenv commands as the actual user
# Source bashrc within the sudo -u context to get pyenv functions
sudo -u "$USER_INVOKING_SUDO" bash -i << PYENV_SCRIPT
set -e # Exit inner script on error
echo "    Sourcing .bashrc for pyenv commands..."
# Try sourcing .profile first, then .bashrc, just in case for interactive setup
[ -r "$HOME/.profile" ] && source "$HOME/.profile" || true
[ -r "$HOME/.bashrc" ] && source "$HOME/.bashrc" || true

echo "    Installing Python $PYTHON_VERSION (this may take a while)..."
if pyenv versions --bare | grep -q "^$PYTHON_VERSION$"; then
  echo "    Python $PYTHON_VERSION already installed."
else
  pyenv install "$PYTHON_VERSION"
fi

echo "    Setting global Python version to $PYTHON_VERSION..."
pyenv global "$PYTHON_VERSION"

echo "    Verifying Python version:"
pyenv version
PYENV_SCRIPT

# 5. Application Specific Setup (emsys-rnbo)

echo ">>> Cloning emsys-rnbo repository..."
EMSYSRNBO_DIR="$HOME_DIR/emsys-rnbo"
# Clone as the regular user
if [ -d "$EMSYSRNBO_DIR" ]; then
  echo "    emsys-rnbo directory already exists, skipping clone."
else
  # cd "$HOME_DIR" # Already likely in home, but doesn't hurt
  sudo -u "$USER_INVOKING_SUDO" git clone https://github.com/emuyia-org/emsys-rnbo.git "$EMSYSRNBO_DIR"
fi

echo ">>> Setting up emsys-rnbo reboot script symlink..."
PISOUND_BTN_SCRIPT_DIR="/usr/local/pisound/scripts/pisound-btn"
REBOOT_SCRIPT_SRC="$EMSYSRNBO_DIR/scripts/reboot.sh"
REBOOT_SCRIPT_DST="$PISOUND_BTN_SCRIPT_DIR/reboot.sh"

if [ -d "$PISOUND_BTN_SCRIPT_DIR" ]; then
  # Create symlink using sudo (needs root)
  # Use -f to force overwrite if link exists, -s for symbolic
  ln -sf "$REBOOT_SCRIPT_SRC" "$REBOOT_SCRIPT_DST"
  echo "    Symlink created: $REBOOT_SCRIPT_DST -> $REBOOT_SCRIPT_SRC"
else
  echo "    Warning: Target directory $PISOUND_BTN_SCRIPT_DIR not found. Skipping symlink."
fi

# 6. Set Console Font (Terminus 16x32)

echo ">>> Setting console font to Terminus 16x32..."

# Pre-seed the debconf database with the desired answers
debconf-set-selections <<EOF
# Set encoding to UTF-8 (standard)
console-setup console-setup/charmap select UTF-8
# Set character set based on UTF-8 (using 'guess' often works well)
console-setup console-setup/codeset select GUESTS
# Set the desired font face
console-setup console-setup/fontface select Terminus
# Set the desired font size
console-setup console-setup/fontsize-text select 16x32
EOF

# Check if debconf-set-selections succeeded
if [ $? -ne 0 ]; then
  echo "!!! ERROR setting debconf selections for console font." >&2
  # Decide whether to exit or continue
  # exit 1
else
  echo "    Applying console-setup configuration non-interactively..."
  # Apply the settings by reconfiguring console-setup without interaction
  dpkg-reconfigure -f noninteractive console-setup
  if [ $? -ne 0 ]; then
    echo "!!! ERROR applying console-setup configuration." >&2
  else
    echo "    Console font configuration updated successfully."
  fi
fi

apt install -y python3-pip libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev libportmidi-dev

# usermod -a -G audio pi


# 7. Final Cleanup (Optional) and Reboot

echo ">>> Cleaning up APT cache..."
apt autoremove -y
apt clean

echo "--- Setup Script Finished ---"
echo ">>> System will reboot now. <<<"

# 8. Reboot the System
reboot
