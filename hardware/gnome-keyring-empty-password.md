# GNOME Login Keyring — Remove Password for Fingerprint Login

## Problem

Every fingerprint login triggers an "Authentication required to unlock Login keyring" popup. This happens because `pam_fprintd.so` authenticates the session but never supplies the user password to `pam_gnome_keyring.so`, so the keyring stays locked and prompts separately.

## Diagnosis

Fingerprint login via fprintd does not pass a password through PAM. The GNOME keyring is encrypted with the login password, so it has no way to auto-unlock on fingerprint sessions.

## Trade-off

Setting an empty keyring password means `~/.local/share/keyrings/login.keyring` is stored unencrypted on disk. On this machine (no LUKS full-disk encryption), anyone with physical access to the drive can read stored credentials (Wi-Fi passwords, GNOME Online Accounts tokens, libsecret-backed app credentials).

Acceptable risk for a home machine that stays docked; revisit if LUKS is added later.

## Fix

1. Open **seahorse** (GNOME Passwords and Keys):
   ```
   seahorse
   ```
2. In the left panel: **Passwords** → **Login**
3. Right-click the **Login** keyring → **Change Password**
4. Enter your current login password, leave the new password **blank** → **Continue**
5. Log out and back in with fingerprint — the prompt should not appear

## Verification

After logging in with fingerprint, confirm no keyring popup appears and that apps requiring stored credentials (e.g. GNOME Online Accounts) still work.

## Reverting

To re-add a password to the keyring, repeat the steps above and set a non-empty password.
