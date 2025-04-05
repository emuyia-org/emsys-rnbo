<div align="center">
    <img src="resources/banner.webp" height="80">
    <p>A live music companion to the MegaCMD ecosystem, built in Max/MSP with RNBO.</p>
</div>

## Setup
> A niche hardware configuration is required. Not made for general use.

- Flash the [latest run-ready RNBO image](https://rnbo.cycling74.com/resources) to your RPi using the [official setup guide](https://rnbo.cycling74.com/learn/raspberry-pi-setup).
- Boot up your RPi. It will need to be booted twice to get into the system.
- On your pi, run all the commands found in [resources/rpi_setup.txt](resources/rpi_setup.txt).
- Download or clone this repository to your computer, and open `max/max.maxproj` in Max. Open the `[rnbo~ @title emsys]` object, navigate to the Export Sidebar, and select your pi device.
- Export to your device with this configuration:
    - Audio: Interface - hw:pisound
    - Audio: MIDI System - raw
    - Audio: Period Frames - 128

## Usage
WIP
