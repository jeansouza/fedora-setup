#!/bin/bash
# Deploy path: ~/.local/bin/update-notify.sh
# Checks for available DNF updates and sends a GNOME desktop notification if any are found.

output=$(dnf check-update --quiet 2>/dev/null)
rc=$?

if [ "$rc" -eq 100 ]; then
    count=$(echo "$output" | grep -c '^\S')
    notify-send --icon=software-update-available \
        "System Updates Available" \
        "${count} package(s) ready. Run: sudo dnf upgrade"
fi
