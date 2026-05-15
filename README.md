# Fedora Setup — ThinkPad T14

Personal documentation of the Fedora configuration on my ThinkPad T14.

## Machine

| | |
|---|---|
| **Model** | Lenovo ThinkPad T14 |
| **OS** | Fedora 43 |
| **Desktop** | GNOME |
| **Use mode** | Docked, lid closed, external keyboard + mouse |

## Hardware

- Fingerprint reader: Digital Persona U.are.U 4500 USB (`05ba:000a`)
- Sleep mode: `s2idle` (deep sleep not available on this hardware)

## Known Issues & Fixes

| Issue | Doc |
|---|---|
| Slow wake (~1 min), apps closing, fingerprint reader dying after wake | [power-management/thinkpad-power-management-fix.md](power-management/thinkpad-power-management-fix.md) |
| Accents unavailable on ABNT2 and US International keyboards; ç produces ć on us(intl) | [hardware/keyboard-layout-accents.md](hardware/keyboard-layout-accents.md) |
| Fingerprint login triggers "unlock Login keyring" popup on every login | [hardware/gnome-keyring-empty-password.md](hardware/gnome-keyring-empty-password.md) |

## Structure

```
fedora-setup/
├── power-management/   # Sleep, suspend, wake, battery configs
├── hardware/           # Device-specific fixes (USB, audio, etc.)
├── scripts/            # Utility scripts deployed on the system
└── dotfiles/           # Config files worth tracking
```
