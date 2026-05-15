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

### STEP 4 — Fix DisplayPort link retraining on monitor wake

#### Diagnosis (updated)

When GNOME blanks the screen (10-minute idle-delay timer), it sends DPMS-off to all
displays. The LG monitors interpret this as "no signal" and drop the DisplayPort connection
to the dock. On wake (user moves mouse → DPMS-on), the ThinkPad's i915 driver needs to
rebuild the MST (Multi-Stream Transport) link, but the monitors aren't fully awake yet when
the first ACT handshake fires. The monitors detect "no signal" (video pipeline not ready)
and go back into power saving. The i915 driver then retries every ~20 seconds:

```
i915 0000:00:02.0: [drm] *ERROR* Failed to get ACT after 3000 ms, last status: 00
```

The monitors stay dark until the ACT finally succeeds (when the monitor happens to be
receptive at the moment of a retry). Observed symptom: monitors wake briefly, show nothing,
return to power saving; workaround was to switch monitor input to MacBook and back.

**Why `enable_dc=0` doesn't fix this:** DC states are GPU power management (render engine
idle). DPMS-off is an explicit command to the display connectors — a different mechanism
that `enable_dc=0` does not affect. The parameter is applied correctly (kernel log confirms
"Setting dangerous option enable_dc") but the link drop is caused by the monitor's own
response to receiving no signal.

**Connector map (may change between boots):**
- Physical Thunderbolt dock trunk: `card1-DP-6` (referenced in driver errors)
- MST virtual connectors (the actual monitors): `card1-DP-8` and `card1-DP-9`

#### 4a. Turn off energy saving on the LG monitors (hardware fix — partially done)

On each monitor's OSD menu, disable:
- **Smart Energy Saving** — done
- **Auto Power Off** / **No Signal Power Off** — this is the setting that drops the DP link;
  not available in OSD on these models

#### 4b. ~~Disable i915 Display C-states~~ (removed)

`enable_dc=0` was previously applied via `/etc/modprobe.d/i915.conf` based on a
misdiagnosis — DC states are GPU power management, not the cause of DPMS-triggered DP link
drops. The parameter also taints the kernel (`TAINT_USER`). It has been removed; the actual
fix is Step 4c below.

#### 4c. DP MST recovery service (software fix for wake)

A user-level systemd service watches mutter's `PowerSaveMode` D-Bus property for
transitions to `0` (DPMS-on, screen waking). On each wake event it runs a background loop
that cycles `PowerSaveMode` between `3` (off) and `0` (on) every ~6 seconds, giving the
LG monitors repeated chances to complete the i915 MST ACT handshake. The loop exits as
soon as both monitors appear as `connected` in sysfs (checked after each cycle, never
before, to avoid a transient false positive during the initial ACT attempt). A 90-second
debounce in the monitor script prevents the script's own `PowerSaveMode=0` signals from
spawning additional recovery instances.

Typical recovery: **1–2 cycles (~9–15 seconds)** for DPMS-only wakes. After full system
suspend/resume, the Thunderbolt dock itself reinitialises and may need 4–5 cycles (~30s).

Tracked in this repo:
- `scripts/dp-mst-recover.sh` → `/usr/local/bin/dp-mst-recover.sh`
- `scripts/dp-mst-monitor.sh` → `/usr/local/bin/dp-mst-monitor.sh`
- `dotfiles/.config/systemd/user/dp-mst-monitor.service` → `~/.config/systemd/user/`

**Deploy:**

```bash
# Scripts (as root)
sudo cp scripts/dp-mst-recover.sh /usr/local/bin/dp-mst-recover.sh
sudo cp scripts/dp-mst-monitor.sh /usr/local/bin/dp-mst-monitor.sh
sudo chmod +x /usr/local/bin/dp-mst-recover.sh /usr/local/bin/dp-mst-monitor.sh

# User service (as normal user)
mkdir -p ~/.config/systemd/user
cp dotfiles/.config/systemd/user/dp-mst-monitor.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now dp-mst-monitor.service
```

**Verify service is running:**

```bash
systemctl --user status dp-mst-monitor.service
# Should show Active: active (running)
```

**Test recovery manually:**

```bash
/usr/local/bin/dp-mst-recover.sh &
journalctl -t dp-mst-recover -f
# Monitors should come back without needing Mac input switch
```

---

## Summary of Created Files

| File | Purpose |
|------|---------|
| `/etc/systemd/sleep.conf.d/thinkpad.conf` | Disables hibernate and hybrid sleep |
| `/etc/udev/rules.d/99-fingerprint-pm.rules` | Keeps fingerprint USB always active (no autosuspend) |
| `/usr/lib/systemd/system-sleep/fingerprint-reset.sh` | Rebinds the reader after each system wake |
| ~~`/etc/modprobe.d/i915.conf`~~ | Removed — was a misdiagnosis; tainted the kernel for no benefit |
| `/usr/local/bin/dp-mst-recover.sh` | Cycles mutter PowerSaveMode in a loop until both monitors reconnect |
| `/usr/local/bin/dp-mst-monitor.sh` | Watches mutter PowerSaveMode and spawns recovery script on wake |
| `~/.config/systemd/user/dp-mst-monitor.service` | User systemd service that keeps the monitor daemon running |

---

## Verification After Applying

1. **Fingerprint:** Lock screen → wait 5 min → unlock → test reader (should work without reconnecting)
2. **Wake:** With `sleep-inactive-ac-type = nothing`, only the screen dims — wake is instant
3. **Apps:** With hibernate disabled, apps no longer close. If it still happens → investigate with:
   ```bash
   journalctl -b -1 --no-pager | tail -100
   ```
4. **Monitor wake:** Let screen blank (10 min idle) → wake with mouse → monitors should come
   back without needing Mac input switch. Check recovery service log:
   ```bash
   journalctl --user -u dp-mst-monitor.service --since "15 minutes ago"
   ```

---

## Revert (if needed)

```bash
sudo rm /etc/systemd/sleep.conf.d/thinkpad.conf
sudo rm /etc/udev/rules.d/99-fingerprint-pm.rules
sudo rm /usr/lib/systemd/system-sleep/fingerprint-reset.sh
sudo rm /usr/local/bin/dp-mst-recover.sh /usr/local/bin/dp-mst-monitor.sh
systemctl --user disable --now dp-mst-monitor.service
rm ~/.config/systemd/user/dp-mst-monitor.service
gsettings reset org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type
sudo udevadm control --reload-rules
sudo dracut --force
```
