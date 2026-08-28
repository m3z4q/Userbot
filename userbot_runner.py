#!/usr/bin/env python3
"""
userbot_runner.py — Aapki Telethon-based userbot.py ko IMPORT karta hai
Bina aapki file mein ek line change kiye.
"""

import importlib.util
import os, sys, logging

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
