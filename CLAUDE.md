# CLAUDE.md — fedora-setup

This repo documents the Fedora 43 configuration and fixes on Jean's ThinkPad T14.

## Machine context

- **Hardware:** ThinkPad T14, docked (lid always closed), external keyboard + mouse
- **OS:** Fedora 43, GNOME
- **Sleep mode:** `s2idle` only — deep sleep (`s3`) is not available on this hardware
- **Fingerprint reader:** Digital Persona U.are.U 4500 USB, ID `05ba:000a`
  - Historically loses USB enumeration after system wake; fixed via udev rule + systemd-sleep script

## Repo conventions

- Each fix or configuration lives in the most specific subdirectory (`power-management/`, `hardware/`, etc.)
- Docs are Markdown; include a **Diagnóstico** section explaining *why* before the fix steps
- Scripts that live on the system go in `scripts/` with the intended deploy path noted in a comment at the top
- Dotfiles tracked here mirror the real paths; note the real path in a comment or frontmatter

## Current known issues / status

- Power management fix applied (see `power-management/thinkpad-power-management-fix.md`):
  - Hibernate disabled
  - GNOME auto-suspend on AC disabled
  - Fingerprint USB autosuspend disabled via udev
  - Post-wake fingerprint rebind script deployed

## Working with this repo

When the user reports a new issue or symptom, first ask for:
1. `journalctl -b -1 --no-pager | tail -100` output if it involves a crash/hang
2. `systemctl status <service>` for service-related issues
3. `dmesg | tail -50` for hardware/USB issues

When writing scripts that go on the system, prefer systemd units or udev rules over cron.
