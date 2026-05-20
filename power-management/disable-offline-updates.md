# Disable Offline Updates / Hijacked Shutdown

## Problem

Clicking **Shut Down** in GNOME caused the system to reboot into an offline update
cycle instead of powering off. The machine appeared suspended overnight while updates
ran silently.

## Diagnosis

`journalctl -b -1` revealed that on the previous shutdown, systemd activated
`system-update.target` instead of `poweroff.target`:

```
systemd[1]: Queued start job for default target system-update.target.
systemd[1]: Starting packagekit-offline-update.service - Update the operating system whilst offline...
systemd[1]: Starting dnf5-offline-transaction.service - Offline upgrades/transactions using DNF 5...
```

Root cause: `org.gnome.software download-updates` was `true`. GNOME Software
automatically downloaded pending updates and placed them in the offline queue
(creating `/system-update` → `/var/lib/PackageKit/prepared-update`). On the next
shutdown/reboot, `systemd-system-update-generator` detects that symlink and redirects
the boot to `system-update.target`, bypassing `poweroff.target`.

## Fix

### 1. Disable GNOME Software auto-download

```bash
gsettings set org.gnome.software download-updates false
```

This prevents GNOME Software from downloading and queuing updates for offline install.
The `/system-update` symlink is never created, so shutdown stays clean.

### 2. Deploy user-level update notification

Since auto-download is disabled, the built-in GNOME Software pop-up ("Updates ready
to install") no longer fires. A replacement: a user-level systemd timer that checks
for available updates daily via `dnf check-update` and sends a desktop notification
via `notify-send`.

Files (tracked in `scripts/`):

| Repo path | Deploy path |
|---|---|
| `scripts/update-notify.sh` | `~/.local/bin/update-notify.sh` |
| `scripts/update-notify.service` | `~/.config/systemd/user/update-notify.service` |
| `scripts/update-notify.timer` | `~/.config/systemd/user/update-notify.timer` |

Deploy:

```bash
mkdir -p ~/.local/bin ~/.config/systemd/user
cp scripts/update-notify.sh ~/.local/bin/update-notify.sh
chmod +x ~/.local/bin/update-notify.sh
cp scripts/update-notify.service scripts/update-notify.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now update-notify.timer
```

Verify:

```bash
systemctl --user status update-notify.timer
systemctl --user list-timers update-notify.timer
```

To test the notification immediately:

```bash
systemctl --user start update-notify.service
```

### Result

- Shutting down always powers off cleanly.
- A GNOME desktop notification appears once daily if updates are available.
- Updates are applied manually: `sudo dnf upgrade`.
