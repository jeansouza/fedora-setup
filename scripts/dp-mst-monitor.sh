#!/bin/bash
# Deploy to: /usr/local/bin/dp-mst-monitor.sh
#
# Watches mutter's PowerSaveMode property for transitions to 0 (DPMS-on,
# screen waking). On each wake event, starts dp-mst-recover.sh in the
# background to cycle DPMS and help the LG monitors complete MST link init.
#
# Debounces with a 30-second cooldown so that PowerSaveMode=0 signals fired
# by dp-mst-recover.sh itself do not spawn additional recovery instances.

LAST_SPAWN_FILE="/tmp/dp-mst-last-spawn"
DEBOUNCE=90  # seconds — covers full 10-attempt worst case (10×6s + 3s initial ≈ 63s)

gdbus monitor --session \
    --dest org.gnome.Mutter.DisplayConfig \
    --object-path /org/gnome/Mutter/DisplayConfig 2>/dev/null | \
while IFS= read -r line; do
    if echo "$line" | grep -q "'PowerSaveMode': <0>"; then
        now=$(date +%s)
        last=0
        [ -f "$LAST_SPAWN_FILE" ] && last=$(cat "$LAST_SPAWN_FILE" 2>/dev/null)
        if [ $((now - last)) -ge $DEBOUNCE ]; then
            echo "$now" > "$LAST_SPAWN_FILE"
            /usr/local/bin/dp-mst-recover.sh &
        fi
    fi
done
