# Power Management Fix — ThinkPad T14 + Fedora 43 + Dock

## Problems

1. **Slow wake (~1 min)** after screen lock + inactivity — caused by GNOME auto-suspend (fixed in Step 2)
2. **Apps closing** sometimes after wake (indicates hibernate or crash)
3. **Fingerprint reader** (Digital Persona U.R.U 4500) stops working after wake
4. **90-second lock screen delay** after monitor wakes from its own energy saving — caused by DisplayPort MST link retraining failures (fixed in Step 4)

## Diagnosis

- Current sleep mode: `s2idle` (shallow sleep — deep sleep not available on this hardware)
- GNOME auto-suspend: 15 min of inactivity → suspend (causes slow wake via dock)
- Fingerprint USB ID: `05ba:000a`, observed path: `/sys/bus/usb/devices/3-3.2.4/`
  - Path is dock-port-dependent and may differ between sessions — always locate by vendor ID
  - `power/control = auto` → autosuspend active, puts device in bad state
  - `power/autosuspend_delay_ms = 2000` → suspends after 2s
  - `power/wakeup = disabled`
  - Find the current path: `for d in /sys/bus/usb/devices/*/; do [ "$(cat $d/idVendor 2>/dev/null)" = "05ba" ] && echo $d; done`

---

## Step-by-Step Fixes

### STEP 1 — Disable hibernate (fixes "apps closing")

```bash
sudo mkdir -p /etc/systemd/sleep.conf.d
sudo vi /etc/systemd/sleep.conf.d/thinkpad.conf
```

Content:

```ini
[Sleep]
AllowSuspend=yes
AllowHibernation=no
AllowSuspendThenHibernate=no
AllowHybridSleep=no
```

---

### STEP 2 — Disable GNOME auto-suspend (fixes slow wake)

Run as **normal user** (not root):

```bash
# Option A: Disable automatic suspend entirely when plugged in (AC)
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'

# Option B: Just increase the timeout to 30 minutes (more conservative)
# gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-timeout 1800
```

> With Option A, the system never auto-suspends when on AC power (dock).
> Only the screen turns off. Wake is instant because there is no real suspend.

---

### STEP 3 — Fix fingerprint reader after wake

#### 3a. udev rule to disable USB autosuspend for the device

```bash
sudo vi /etc/udev/rules.d/99-fingerprint-pm.rules
```

Content:

```
# Digital Persona U.are.U 4500 - disable USB autosuspend
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="05ba", ATTR{idProduct}=="000a", \
  ATTR{power/autosuspend}="-1", \
  ATTR{power/control}="on"
```

Apply to the live device (no reboot needed):

```bash
sudo udevadm control --reload-rules

# Trigger udev add event for the fingerprint reader (path-independent)
for d in /sys/bus/usb/devices/*/; do
  [ "$(cat $d/idVendor 2>/dev/null)" = "05ba" ] && sudo udevadm trigger --action=add "$d"
done
```

Verify:

```bash
for d in /sys/bus/usb/devices/*/; do
  [ "$(cat $d/idVendor 2>/dev/null)" = "05ba" ] && cat "${d}power/control"
done
# Should show: on
```

#### 3b. Script to reinitialize the reader after system wake

```bash
sudo vi /usr/lib/systemd/system-sleep/fingerprint-reset.sh
```

Content:

```bash
#!/bin/bash
if [ "$1" = "post" ]; then
    sleep 2
    for device in /sys/bus/usb/devices/*/; do
        if [ -f "$device/idVendor" ] && [ "$(cat $device/idVendor)" = "05ba" ]; then
            if [ -f "$device/idProduct" ] && [ "$(cat $device/idProduct)" = "000a" ]; then
                DEVPATH=$(basename "$device")
                echo "$DEVPATH" > /sys/bus/usb/drivers/usb/unbind 2>/dev/null
                sleep 1
                echo "$DEVPATH" > /sys/bus/usb/drivers/usb/bind 2>/dev/null
            fi
        fi
    done
    systemctl restart fprintd.service 2>/dev/null
fi
```

```bash
sudo chmod +x /usr/lib/systemd/system-sleep/fingerprint-reset.sh
```

---

### STEP 4 — Fix DisplayPort link retraining delay on monitor wake

#### Diagnosis

When the LG monitors activate their own energy saving (independent of GNOME DPMS, which is
already disabled), they drop the DisplayPort connection to the dock. On wake, the i915 driver
must re-establish the MST (Multi-Stream Transport) link. This fails repeatedly with ACT
handshake timeouts visible in the journal:

```
i915 0000:00:02.0: [drm] *ERROR* Failed to get ACT after 3000 ms, last status: 00
```

Each failure takes 3 seconds; with multiple retries and the monitor cycling back to sleep
(showing "no signal" each time), the total delay reaches ~90 seconds before the lock screen
appears.

Affected ports: `card1-DP-6` and `card1-DP-7`.

#### 4a. Turn off energy saving on the LG monitors (hardware fix)

On each monitor's OSD menu, disable:
- **Smart Energy Saving** (or equivalent)
- **Auto Power Off** / **No Signal Power Off**

This prevents the DP link from being dropped in the first place. The exact menu path
depends on the LG model (22" and 34").

#### 4b. Disable i915 Display C-states (software fix)

```bash
sudo vi /etc/modprobe.d/i915.conf
```

Content (also tracked at `scripts/i915.conf` in this repo):

```
options i915 enable_dc=0
```

Then rebuild the initramfs and reboot:

```bash
sudo dracut --force
sudo reboot
```

Verify after reboot:

```bash
# Should show enable_dc:0
sudo systool -m i915 -av 2>/dev/null | grep enable_dc
# Or check journal — ACT timeout errors should be gone on next monitor wake
journalctl -b --no-pager | grep -i "Failed to get ACT"
```

---

## Summary of Created Files

| File | Purpose |
|------|---------|
| `/etc/systemd/sleep.conf.d/thinkpad.conf` | Disables hibernate and hybrid sleep |
| `/etc/udev/rules.d/99-fingerprint-pm.rules` | Keeps fingerprint USB always active (no autosuspend) |
| `/usr/lib/systemd/system-sleep/fingerprint-reset.sh` | Rebinds the reader after each system wake |
| `/etc/modprobe.d/i915.conf` | Disables i915 Display C-states to prevent DP MST link drops |

---

## Verification After Applying

1. **Fingerprint:** Lock screen → wait 5 min → unlock → test reader (should work without reconnecting)
2. **Wake:** With `sleep-inactive-ac-type = nothing`, only the screen dims — wake is instant
3. **Apps:** With hibernate disabled, apps no longer close. If it still happens → investigate with:
   ```bash
   journalctl -b -1 --no-pager | tail -100
   ```
4. **Lock screen delay:** Lock → let monitors sleep → wake mouse/keyboard → lock screen should appear within a few seconds, not ~90s. No `Failed to get ACT` errors in journal.

---

## Revert (if needed)

```bash
sudo rm /etc/systemd/sleep.conf.d/thinkpad.conf
sudo rm /etc/udev/rules.d/99-fingerprint-pm.rules
sudo rm /usr/lib/systemd/system-sleep/fingerprint-reset.sh
sudo rm /etc/modprobe.d/i915.conf
gsettings reset org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type
sudo udevadm control --reload-rules
sudo dracut --force
```
