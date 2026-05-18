#!/usr/bin/env python3
# Deploy to: /usr/local/bin/fix-monitor-layout.py
#
# Ensures LG FULL HD (22") is at x=0 (left) and LG ULTRAWIDE (34") is at x=1920 (right),
# regardless of which DP connector number each gets after MST re-enumeration on wake or boot.
#
# Identifies monitors by product name via Mutter's GetCurrentState D-Bus call, then
# calls ApplyMonitorsConfig if the layout is wrong. Safe to run repeatedly — exits
# immediately if the layout is already correct.

import sys
import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib

DEST  = 'org.gnome.Mutter.DisplayConfig'
OBJ   = '/org/gnome/Mutter/DisplayConfig'
IFACE = 'org.gnome.Mutter.DisplayConfig'

ULTRAWIDE = 'LG ULTRAWIDE'
FULLHD    = 'LG FULL HD'
ULTRAWIDE_X = 1920
FULLHD_X    = 0


def log(msg):
    print(f'fix-monitor-layout: {msg}', flush=True)


def dbus_call(bus, method, params=None):
    return bus.call_sync(
        DEST, OBJ, IFACE, method,
        params, None,
        Gio.DBusCallFlags.NONE, 5000, None
    )


def main():
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    except GLib.Error as e:
        log(f'cannot connect to session bus: {e}')
        return 1

    try:
        result = dbus_call(bus, 'GetCurrentState')
    except GLib.Error as e:
        log(f'GetCurrentState failed: {e}')
        return 1

    serial, monitors, logical_monitors, _ = result.unpack()

    # Find connector and active mode for ULTRAWIDE and FULL HD by product name.
    # Mode preference: is-current > is-preferred > first listed.
    connector_mode = {}
    for (conn, vendor, product, serial_str), modes, props in monitors:
        mode_id = None
        for mid, w, h, rate, pref_scale, scales, mode_props in modes:
            if mode_props.get('is-current'):
                mode_id = mid
                break
        if mode_id is None:
            for mid, w, h, rate, pref_scale, scales, mode_props in modes:
                if mode_props.get('is-preferred'):
                    mode_id = mid
                    break
        if mode_id is None and modes:
            mode_id = modes[0][0]
        connector_mode[product] = (conn, mode_id)

    if ULTRAWIDE not in connector_mode or FULLHD not in connector_mode:
        missing = [p for p in (ULTRAWIDE, FULLHD) if p not in connector_mode]
        log(f'monitors not found: {missing} — are both connected?')
        return 1

    uw_conn, uw_mode = connector_mode[ULTRAWIDE]
    fhd_conn, fhd_mode = connector_mode[FULLHD]

    # Read current scale, transform, and primary flag from the active logical config.
    lm_info = {}
    for x, y, scale, transform, primary, lm_mons, lm_props in logical_monitors:
        for conn, vendor, product, serial_str in lm_mons:
            lm_info[product] = {'x': x, 'scale': scale, 'transform': transform, 'primary': primary}

    if lm_info.get(ULTRAWIDE, {}).get('x') == ULTRAWIDE_X and \
       lm_info.get(FULLHD, {}).get('x') == FULLHD_X:
        log('layout already correct')
        return 0

    uw_scale     = lm_info.get(ULTRAWIDE, {}).get('scale', 1.0)
    uw_transform = lm_info.get(ULTRAWIDE, {}).get('transform', 0)
    uw_primary   = lm_info.get(ULTRAWIDE, {}).get('primary', True)
    fhd_scale     = lm_info.get(FULLHD, {}).get('scale', 1.0)
    fhd_transform = lm_info.get(FULLHD, {}).get('transform', 0)
    fhd_primary   = lm_info.get(FULLHD, {}).get('primary', False)

    log(f'fixing: {fhd_conn} (FULL HD) → x={FULLHD_X}, {uw_conn} (ULTRAWIDE) → x={ULTRAWIDE_X}')

    # ApplyMonitorsConfig type: (uua(iiduba(ssa{sv}))a{sv})
    # Each logical monitor: (x, y, scale, transform, is_primary, [(connector, mode_id, {})], {})
    new_lm = [
        (FULLHD_X,    0, fhd_scale, fhd_transform, fhd_primary, [(fhd_conn, fhd_mode, {})], {}),
        (ULTRAWIDE_X, 0, uw_scale,  uw_transform,  uw_primary,  [(uw_conn,  uw_mode,  {})], {}),
    ]

    params = GLib.Variant('(uua(iiduba(ssa{sv}))a{sv})', (serial, 2, new_lm, {}))

    try:
        dbus_call(bus, 'ApplyMonitorsConfig', params)
        log('layout applied')
        return 0
    except GLib.Error as e:
        log(f'ApplyMonitorsConfig failed: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
