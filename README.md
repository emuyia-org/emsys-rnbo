<div align="center">
    <img src="resources/banner.webp" height="80">
    <p>A live music companion to the MegaCMD ecosystem, built in Max/MSP with RNBO.</p>
</div>

## Setup
> A niche hardware configuration is required. Not made for general use.

- Flash the [latest run-ready RNBO image](https://rnbo.cycling74.com/resources) to your RPi using the [official setup guide](https://rnbo.cycling74.com/learn/raspberry-pi-setup).
- On your RPi, run `sudo apt update && sudo apt upgrade -y && sudo apt autoremove -y` to update packages.
- Install the [latest Pisound driver](https://blokas.io/pisound/docs/software/) with `curl https://blokas.io/pisound/install.sh | sh
`, or equivalent driver.
- Reboot with `sudo reboot`.
- Download or clone this repository to your computer, and open `max/main.maxproj` in Max.
- Open the `[rnbo~ @title emsys]` object in `main.maxpat`, and export it to your RPi via the Export Sidebar.

##### Configure Pisound button (optional):
- Install git with `sudo apt install git`.
- Clone this repository with `git clone https://github.com/emuyia-org/emsys-rnbo.git`.
- Run `cd emsys-rnbo` and run `sudo ln -s /home/pi/emsys-rnbo/serv/reboot.sh /usr/local/pisound/scripts/pisound-btn/reboot.sh` to add the reboot script to available Pisound button functions.
- Run `sudo pisound-config` and select "Change Pisound Button Settings" to configure button functionality to taste.

## Usage
WIP
