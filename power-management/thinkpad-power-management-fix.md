# Power Management Fix — ThinkPad T14 + Fedora 43 + Dock

## Problems

1. **Slow wake (~1 min)** after screen lock + inactivity
2. **Apps closing** sometimes after wake (indicates hibernate or crash)
3. **Fingerprint reader** (Digital Persona U.R.U 4500) stops working after wake

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

# Find the current device path
for d in /sys/bus/usb/devices/*/; do [ "$(cat $d/idVendor 2>/dev/null)" = "05ba" ] && echo $d; done

# Trigger udev add event (replace 3-3.2.4 with actual path)
sudo udevadm trigger --action=add /sys/bus/usb/devices/3-3.2.4/
```

Verify:

```bash
# Replace 3-3.2.4 with the path found above
cat /sys/bus/usb/devices/3-3.2.4/power/control
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

## Summary of Created Files

| File | Purpose |
|------|---------|
| `/etc/systemd/sleep.conf.d/thinkpad.conf` | Disables hibernate and hybrid sleep |
| `/etc/udev/rules.d/99-fingerprint-pm.rules` | Keeps fingerprint USB always active (no autosuspend) |
| `/usr/lib/systemd/system-sleep/fingerprint-reset.sh` | Rebinds the reader after each system wake |

---

## Verification After Applying

1. **Fingerprint:** Lock screen → wait 5 min → unlock → test reader (should work without reconnecting)
2. **Wake:** With `sleep-inactive-ac-type = nothing`, only the screen dims — wake is instant
3. **Apps:** With hibernate disabled, apps no longer close. If it still happens → investigate with:
   ```bash
   journalctl -b -1 --no-pager | tail -100
   ```

---

## Revert (if needed)

```bash
sudo rm /etc/systemd/sleep.conf.d/thinkpad.conf
sudo rm /etc/udev/rules.d/99-fingerprint-pm.rules
sudo rm /usr/lib/systemd/system-sleep/fingerprint-reset.sh
gsettings reset org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type
sudo udevadm control --reload-rules
```
