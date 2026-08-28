#!/usr/bin/env python3
"""
userbot_runner.py — Aapki Telethon-based userbot.py ko IMPORT karta hai
Aur uske main() function ko call karta hai taaki client start ho.
"""

import importlib.util
import os, sys, asyncio, logging

logging.basicConfig(level=logging.ERROR)

if len(sys.argv) < 3:
    logging.error("Usage: userbot_runner.py <user_id> <session_file>")
    sys.exit(1)

USER_ID = int(sys.argv[1])
SESSION_FILE = sys.argv[2]

# ─── Hardcoded API credentials ────────────────────────────
API_ID = 32557753
API_HASH = "3aec7775e6af24432f2414f941409876"

if not os.path.exists(SESSION_FILE):
    logging.error(f"Session file not found: {SESSION_FILE}")
    sys.exit(1)

with open(SESSION_FILE) as f:
    SESSION_STRING = f.read().strip()

# ─── Patch Telethon's TelegramClient ─────────────────────
from telethon import TelegramClient
from telethon.sessions import StringSession

_original_init = TelegramClient.__init__

def _patched_init(self, session, api_id, api_hash, *args, **kwargs):
    injected_session = StringSession(SESSION_STRING)
    _original_init(self, injected_session, API_ID, API_HASH, *args, **kwargs)

TelegramClient.__init__ = _patched_init

# ─── Import userbot.py ────────────────────────────────────
try:
    spec = importlib.util.spec_from_file_location("userbot", "userbot.py")
    userbot_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(userbot_mod)
    logging.info(f"✅ Userbot loaded for user {USER_ID}")
except Exception as e:
    logging.error(f"Failed to load userbot: {e}")
    sys.exit(1)

# ─── Call main() ──────────────────────────────────────────
# userbot.py ke andar if __name__ == "__main__" block
# import ke time nahi chalta. Isliye manually call karte hain.
try:
    if hasattr(userbot_mod, "main"):
        asyncio.run(userbot_mod.main())
    else:
        logging.error("❌ userbot.py mein 'main()' function nahi mila!")
        sys.exit(1)
except KeyboardInterrupt:
    # Userbot ke cleanup code ko respect karo
    logging.info("👋 Userbot stopped by user.")
except Exception as e:
    logging.error(f"❌ Userbot runtime error: {e}")
    sys.exit(1)
