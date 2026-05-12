# Keyboard Layout: Accents on ABNT2 + US Layouts

## Context

Two keyboards in use:

| Keyboard | Layout | When used |
|---|---|---|
| ThinkPad T14 built-in | ABNT2 (Brazilian) | Undocked |
| Logitech MX Keys | US (American) | Docked, lid closed |

## Diagnosis

GNOME was configured with only the `us` layout (`xkb: us`), which is wrong for the ABNT2 laptop keyboard and has no dead keys for the US external keyboard. Accents (á, ã, ê, ç, etc.) were unavailable on both.

- The **ABNT2** keyboard needs the `br` xkb layout, which maps the physical Brazilian keys correctly (ç, dead acute ´, dead tilde ~, etc.)
- The **US/Logitech** keyboard needs `us(intl)` — US International with dead keys — so that `' + a = á`, `~ + a = ã`, `` ` + a = à ``, `" + a = ä`, etc. (pressing Space after a dead key produces the bare character)

## Fix

Add both layouts to GNOME input sources:

```bash
gsettings set org.gnome.desktop.input-sources sources "[('xkb', 'br'), ('xkb', 'us+intl')]"
```

Switch between them with **Super+Space**. Use `br` for the laptop keyboard and `us+intl` for the Logitech.

To verify:

```bash
gsettings get org.gnome.desktop.input-sources sources
# Expected: [('xkb', 'br'), ('xkb', 'us+intl')]
```

## Known issue: cedilha (ç) on us(intl) produces ć instead

### Diagnosis

XKB defines `dead_acute + c = ć` (c-acute, U+0107) by spec. Brazilian Portuguese convention expects `' + c = ç`, but that's not what the standard XKB compose table does. The fix is to override it in `~/.XCompose`, which IBus reads on GNOME Wayland.

### Fix

Create `~/.XCompose` (deploy path: `~/.XCompose`):

```
include "%L"

# Fix: dead_acute + c/C → ç/Ç (Brazilian Portuguese convention)
# XKB us(intl) maps this to ć/Ć by default
<dead_acute> <c> : "ç" ccedilla
<dead_acute> <C> : "Ç" Ccedilla
```

Then restart IBus to pick it up:

```bash
ibus restart
```

The `include "%L"` line preserves all other compose sequences from the system table.

## Notes

- On `us(intl)`, `'` is a dead key. To type a bare apostrophe, press `'` then `Space`.
- If a third layout is ever needed, append it to the array; GNOME cycles through them with Super+Space.
- GNOME does not support per-device keyboard layouts natively on Wayland — layout switching must be done manually.
