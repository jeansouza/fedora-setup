#!/bin/bash
# Deploy to: /usr/local/bin/dp-mst-recover.sh
#
# Called when mutter sets PowerSaveMode = 0 (DPMS-on, screen waking).
# Repeatedly cycles mutter's PowerSaveMode off→on, giving the LG monitors
# multiple chances to wake and pass the i915 MST ACT handshake. Stops as
# soon as both monitors are detected as connected.
#
# is_recovered is checked only AFTER a full cycle (never before) to avoid
# a false positive on the transient sysfs state that appears briefly after
# the initial DPMS-on before the ACT handshake has resolved.

DBUS_DEST="org.gnome.Mutter.DisplayConfig"
DBUS_PATH="/org/gnome/Mutter/DisplayConfig"
DBUS_IFACE="org.gnome.Mutter.DisplayConfig"

set_power_mode() {
    busctl --user set-property "$DBUS_DEST" "$DBUS_PATH" "$DBUS_IFACE" \
        PowerSaveMode i "$1" 2>/dev/null
}

is_recovered() {
    local n
    n=$(grep -l '^connected$' /sys/class/drm/card1-DP-*/status 2>/dev/null | wc -l)
    [ "$n" -ge 2 ]
}

sleep 3  # let mutter finish its own DPMS-on before we start cycling

for attempt in $(seq 1 10); do
    logger -t dp-mst-recover "attempt $attempt: cycling PowerSaveMode"
    set_power_mode 3   # brief DPMS-off to reset the dock's MST state
    sleep 1
    set_power_mode 0   # DPMS-on: triggers a fresh ACT handshake attempt
    sleep 5            # ACT timeout is 3000ms; 2s margin for link to stabilise
    if is_recovered; then
        logger -t dp-mst-recover "monitors recovered on attempt $attempt"
        sleep 2  # let mutter apply its saved config before we correct it
        /usr/local/bin/fix-monitor-layout.py 2>&1 | logger -t fix-monitor-layout
        exit 0
    fi
done

logger -t dp-mst-recover "gave up after 10 attempts"
