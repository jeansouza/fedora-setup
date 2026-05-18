# Monitor Layout Lock

## Problem

Two external LG monitors on a DP MST hub sometimes swap positions after suspend/resume or boot:
- LG FULL HD (22", 1920×1080) should always be on the **left** (x=0)
- LG ULTRAWIDE (34", 2560×1080) should always be on the **right** (x=1920, primary)

## Diagnosis

GNOME stores monitor layouts in `~/.config/monitors.xml`, keyed by connector name + monitor identity (vendor/product/serial). Both LG monitors report an identical placeholder serial (`0x01010101`), so GNOME distinguishes them only by connector name.

After each MST re-enumeration (handled by `dp-mst-monitor.service` + `dp-mst-recover.sh`), the DP connector numbers assigned by the kernel change unpredictably (DP-5 through DP-9 have all appeared). GNOME either matches the wrong saved configuration or falls back to a default that puts the monitors in the wrong order.

`kanshi`, the obvious Wayland display configuration tool, was ruled out — it requires the `zwlr-output-management-v1` protocol, which GNOME/Mutter does not implement.

The correct GNOME-native fix is Mutter's `org.gnome.Mutter.DisplayConfig.ApplyMonitorsConfig` D-Bus method, which identifies monitors by product name in real time and applies the correct layout persistently (method=2 updates `monitors.xml`).

## Fix

### `fix-monitor-layout.py` (`scripts/fix-monitor-layout.py`)

Python script that:
1. Calls `GetCurrentState` to read which connector currently carries each monitor (by product name `LG ULTRAWIDE` / `LG FULL HD`)
2. Checks whether the layout is already correct — exits immediately if so
3. Calls `ApplyMonitorsConfig` with the correct x positions, preserving scale, transform, and primary flag from the current config

### Wake case

`dp-mst-recover.sh` calls `fix-monitor-layout.py` after confirming both monitors are back online (after the MST ACT handshake). A 2-second sleep lets Mutter apply its saved config first, so the script can detect and correct any mis-ordering.

### Boot case

A GNOME autostart entry (`dotfiles/.config/autostart/fix-monitor-layout.desktop`, real path `~/.config/autostart/fix-monitor-layout.desktop`) runs `fix-monitor-layout.py` 5 seconds after session start. The delay lets Mutter finish its initial monitor enumeration before the correction runs.

## Deploy

```bash
# Script
sudo cp scripts/fix-monitor-layout.py /usr/local/bin/fix-monitor-layout.py
sudo chmod +x /usr/local/bin/fix-monitor-layout.py

# Updated MST recovery script
sudo cp scripts/dp-mst-recover.sh /usr/local/bin/dp-mst-recover.sh

# Autostart entry (boot case)
mkdir -p ~/.config/autostart
cp dotfiles/.config/autostart/fix-monitor-layout.desktop ~/.config/autostart/
```

No new services needed — the wake case piggybacks on the existing `dp-mst-monitor.service`.
