"""Test the Supabase key in .env, without ever printing it.

Run it in the game folder, on your own computer:
    python test_key.py

It reads .env next to this file, checks the URL and the
publishable key are in the right shape, then pings Supabase.
It prints one plain line: OK when the key works, or what is
wrong when it does not. The key itself is never printed, and
never written to the log by this script.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import supabase_config


def main():
    config, error = supabase_config.check_online_config()
    if error:
        print("FAILED: " + error.replace("\n", " "))
        return 1
    print("Key format OK. Pinging Supabase...")
    ok, message = supabase_config.test_connection(config)
    print(("OK: " if ok else "FAILED: ") + message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
