#!/bin/sh

# Allow use of this script for pisound button:
# sudo ln -s /home/pi/emsys-rnbo/serv/reboot.sh /usr/local/pisound/scripts/pisound-btn/reboot.sh

. /usr/local/pisound/scripts/common/common.sh

log "Pisound button held for $2 ms, after $1 clicks!"

if [ $1 -ne 1 ]; then
        log "Ignoring hold after $1 clicks..."
        exit 0
fi

aconnect -x

for i in $(seq 1 10); do
        flash_leds 1
        sleep 0.1
done

log "Rebooting the system."

sudo reboot
