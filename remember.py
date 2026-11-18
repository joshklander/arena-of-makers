"""Keep me signed in, for Arena of Makers.

When a player turns on "Keep me signed in on this computer",
the server gives the game a random remember token. This
module keeps that token in the computer's own password store,
through the keyring package: on Windows, that is Windows
Credential Manager, which encrypts it for the signed-in
Windows user.

- The password is never stored. Only the remember token is.
- The token is never written to a file in the game folder, so
  it can never be pushed to GitHub or shared by accident.
- The token is never logged or shown.
- Each launch swaps it for a new one, it stops working after
  30 days unused, and turning the setting off deletes it here
  and on the server.

Without the keyring package, the setting is simply not
offered, and the player signs in each launch as before.
"""

import logging

try:
    import keyring
except ImportError:  # the setting is not offered without it
    keyring = None

SERVICE = "Arena of Makers"


def available():
    """True when this computer has a password store to use."""
    return keyring is not None


def _entry_name(config):
    # One entry per Supabase project, so a test project and the
    # real one never mix.
    return "remember:" + config["url"].rstrip("/")


def load_token(config):
    """The saved remember token, or None."""
    if keyring is None:
        return None
    try:
        return keyring.get_password(SERVICE, _entry_name(config))
    except Exception as error:
        logging.warning("Keep me signed in: could not read the password store (%s).",
                        type(error).__name__)
        return None


def save_token(config, token):
    """Save the remember token. Returns True when it was saved."""
    if keyring is None or not token:
        return False
    try:
        keyring.set_password(SERVICE, _entry_name(config), token)
        return True
    except Exception as error:
        logging.warning("Keep me signed in: could not save to the password store (%s).",
                        type(error).__name__)
        return False


def forget_token(config):
    """Remove the saved remember token from this computer."""
    if keyring is None:
        return
    try:
        keyring.delete_password(SERVICE, _entry_name(config))
    except Exception:
        # Nothing was saved, or it was already gone.
        pass
