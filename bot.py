import os, sys, json, asyncio, logging
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ButtonStyle

logging.basicConfig(level=logging.INFO)

# ═══════════════════════════════════════════════════════════
# ═══  HARDCODED CONFIG  ═══════════════════════════════════
# ═══════════════════════════════════════════════════════════

BOT_TOKEN = "8996320529:AAHHheeszUsMme-5NkjY_HsJ5Ws1t_nnG5I"
OWNER_ID = 8188215655

API_ID = 32557753
API_HASH = "3aec7775e6af24432f2414f941409876"

SESSION_DIR = "sessions"
DATA_FILE = "user_data.json"

FORCE_CHANNELS = ["@titankeng", "@titanbotss", "@titanfreeapi"]
OWNER_USERNAME = "TITAN"

# ═══════════════════════════════════════════════════════════

os.makedirs(SESSION_DIR, exist_ok=True)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ─── JSON Data ─────────────────────────────────────────────
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "broadcasts_sent": 0, "total_messages": 0}
    with open(DATA_FILE) as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def save_user(user: types.User):
    data = load_data()
    uid = str(user.id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "joined_at": datetime.now().isoformat(),
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "has_userbot": False,
            "last_active": datetime.now().isoformat()
        }
        save_data(data)
        return True
    data["users"][uid]["last_active"] = datetime.now().isoformat()
    save_data(data)
    return False

# ─── FSM ───────────────────────────────────────────────────
class HostStates(StatesGroup):
    waiting_for_api_id = State()
    waiting_for_api_hash = State()
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_2fa = State()

# ─── Force Join ────────────────────────────────────────────
async def check_force_join(user_id: int) -> list:
    not_joined = []
    for channel in FORCE_CHANNELS:
        try:
            cm = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if cm.status in ("left", "kicked", "banned"):
                not_joined.append(channel)
        except:
            not_joined.append(channel)
    return not_joined

def force_join_keyboard(not_joined: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ch in not_joined:
        n = ch.replace("@", "")
        builder.add(InlineKeyboardButton(
            text=f"📢 Join {ch}", url=f"https://t.me/{n}",
            style=ButtonStyle.DANGER))
    builder.add(InlineKeyboardButton(
        text="✅ I've Joined", callback_data="check_joined",
        style=ButtonStyle.SUCCESS))
    builder.adjust(1)
    return builder.as_markup()

@dp.callback_query(F.data == "check_joined")
async def check_joined_cb(callback: types.CallbackQuery):
    uid = callback.from_user.id
    nj = await check_force_join(uid)
    if nj:
        await callback.answer("❌ Abhi bhi saare channels mein nahi!", show_alert=True)
        return
    await callback.answer("✅ Channels joined!", show_alert=True)
    await show_main_menu(callback.message.edit_text)

# ─── Main Menu ─────────────────────────────────────────────
async def show_main_menu(send_func):
    text = (
        "👑 *TITAN Userbot Manager* 👑\n\n"
        f"👤 *Owner:* `{OWNER_USERNAME}`\n"
        "📢 *Updates:* @titanbotss\n"
        "💬 *Main Channel:* @titankeng\n\n"
        "Apna khud ka userbot host karein!"
    )
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="🚀 Host Userbot", callback_data="host_userbot", style=ButtonStyle.PRIMARY),
        InlineKeyboardButton(text="🔑 Get API ID & Hash", url="https://t.me/titanapiidhashgenbot", style=ButtonStyle.SUCCESS),
        InlineKeyboardButton(text="📞 Contact Owner", url="https://t.me/TITANCONTACT", style=ButtonStyle.DANGER),
    )
    builder.adjust(1)
    await send_func(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

# ─── /start ────────────────────────────────────────────────
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = message.from_user
    is_new = save_user(user)
    if is_new and user.id != OWNER_ID:
        mention = f"@{user.username}" if user.username else user.first_name
        try:
            await bot.send_message(OWNER_ID,
                f"🆕 *New User Joined!*\n👤 {mention}\n🆔 `{user.id}`\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                parse_mode="Markdown")
        except:
            pass
    nj = await check_force_join(user.id)
    if nj:
        txt = "⚠️ *Saare channels join karein pehle:*\n\n"
        for ch in nj:
            txt += f"❌ {ch}\n"
        txt += "\nPhir '✅ I've Joined' dabayein."
        await message.reply(txt, reply_markup=force_join_keyboard(nj), parse_mode="Markdown")
        return
    await show_main_menu(message.reply)

# ─── Host Userbot callback ─────────────────────────────────
@dp.callback_query(F.data == "host_userbot")
async def host_cb(callback: types.CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    nj = await check_force_join(uid)
    if nj:
        txt = "⚠️ *Pehle channels join karein:*\n\n"
        for ch in nj:
            txt += f"❌ {ch}\n"
        await callback.message.edit_text(txt, reply_markup=force_join_keyboard(nj), parse_mode="Markdown")
        await callback.answer()
        return
    if os.path.exists(f"{SESSION_DIR}/{uid}.session"):
        await callback.message.edit_text(
            "⚠️ Already logged in!\n/logout karein pehle.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton("🔙 Back", callback_data="back_main", style=ButtonStyle.PRIMARY)
            ]]), parse_mode="Markdown")
        await callback.answer()
        return
    await callback.message.edit_text(
        "📝 *API Details*\n\n"
        "API ID aur Hash hai to bhejein, nahi to /skip\n\n"
        "▶️ *API ID (numbers only):*", parse_mode="Markdown")
    await state.set_state(HostStates.waiting_for_api_id)
    await callback.answer()

@dp.callback_query(F.data == "back_main")
async def back_main_cb(callback: types.CallbackQuery):
    await show_main_menu(callback.message.edit_text)
    await callback.answer()

# ─── API ID / Hash ─────────────────────────────────────────
@dp.message(HostStates.waiting_for_api_id)
async def api_id_handler(message: types.Message, state: FSMContext):
    txt = message.text.strip()
    if txt.lower() == "/skip":
        await state.update_data(api_id=API_ID, api_hash=API_HASH)
        await message.reply("✅ Default API use honge.\n\n📱 *Phone Number:*\n`+919876543210`", parse_mode="Markdown")
        await state.set_state(HostStates.waiting_for_phone)
        return
    try:
        await state.update_data(api_id=int(txt))
        await message.reply("✅ API ID saved!\n\n🔑 *API Hash bhejein:*", parse_mode="Markdown")
        await state.set_state(HostStates.waiting_for_api_hash)
    except ValueError:
        await message.reply("❌ Sirf numbers. Dobara ya /skip.")

@dp.message(HostStates.waiting_for_api_hash)
async def api_hash_handler(message: types.Message, state: FSMContext):
    await state.update_data(api_hash=message.text.strip())
    await message.reply("✅ API Hash saved!\n\n📱 *Phone Number:*\n`+919876543210`", parse_mode="Markdown")
    await state.set_state(HostStates.waiting_for_phone)

# ─── Phone ─────────────────────────────────────────────────
@dp.message(HostStates.waiting_for_phone)
async def phone_handler(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+"):
        await message.reply("❌ `+` se shuru karein. Example: `+919876543210`")
        return
    data = await state.get_data()
    uid = message.from_user.id
    try:
        client = TelegramClient(
            StringSession(),
            int(data.get("api_id", API_ID)),
            data.get("api_hash", API_HASH)
        )
        await client.connect()
        sent = await client.send_code_request(phone)
        await state.update_data(
            phone=phone,
            temp_client=client,
            phone_code_hash=sent.phone_code_hash
        )
        await message.reply(
            "📱 *Code aaya hai!*\n\n"
            "⚠️ *SPACED FORMAT mein bhejein*\n"
            "Code `78122` hai to bhejein: `7 8 1 2 2`\n\n"
            "Code bhejein:", parse_mode="Markdown")
        await state.set_state(HostStates.waiting_for_code)
    except Exception as e:
        await message.reply(f"❌ {str(e)}")
        await state.clear()

# ─── Code ──────────────────────────────────────────────────
@dp.message(HostStates.waiting_for_code)
async def code_handler(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    data = await state.get_data()
    client = data.get("temp_client")
    phone = data.get("phone")
    code = message.text.strip().replace(" ", "")
    if not code.isdigit():
        await message.reply("❌ Sirf digits. Jaise: `7 8 1 2 2`")
        return
    try:
        await client.sign_in(phone, code)
        # Success — save session string
        ss = client.session.save()
        with open(f"{SESSION_DIR}/{uid}.session", "w") as f:
            f.write(ss)
        await client.disconnect()
        await state.clear()
        ud = load_data()
        ud["users"][str(uid)]["has_userbot"] = True
        save_data(ud)
        await message.reply("✅ *Login Success!* 🎉\n\nUserbot start ho raha hai...", parse_mode="Markdown")
        await start_userbot(uid, message)
    except SessionPasswordNeededError:
        await state.set_state(HostStates.waiting_for_2fa)
        await message.reply("🔑 *2FA enabled!* Password bhejein:", parse_mode="Markdown")
    except (PhoneCodeInvalidError, PhoneCodeExpiredError) as e:
        if "Invalid" in str(e):
            await message.reply("❌ Galat code. Dobara spaced format mein:")
        else:
            await message.reply("❌ Code expired. /start se naya karein.")
            await state.clear()
    except Exception as e:
        await message.reply(f"❌ {str(e)}")

# ─── 2FA ───────────────────────────────────────────────────
@dp.message(HostStates.waiting_for_2fa)
async def twofa_handler(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    pwd = message.text.strip()
    data = await state.get_data()
    client = data.get("temp_client")
    try:
        await client.sign_in(password=pwd)
        ss = client.session.save()
        with open(f"{SESSION_DIR}/{uid}.session", "w") as f:
            f.write(ss)
        await client.disconnect()
        await state.clear()
        ud = load_data()
        ud["users"][str(uid)]["has_userbot"] = True
        save_data(ud)
        await message.reply("✅ *Login Success!* 🎉\n\nUserbot start...", parse_mode="Markdown")
        await start_userbot(uid, message)
    except Exception as e:
        await message.reply(f"❌ Galat password: {str(e)}")

# ─── Start Userbot Subprocess ──────────────────────────────
active_processes: dict = {}

async def start_userbot(uid: int, msg: types.Message):
    python = sys.executable
    runner = "userbot_runner.py"
    sf = f"{SESSION_DIR}/{uid}.session"
    try:
        proc = await asyncio.create_subprocess_exec(
            python, runner, str(uid), sf,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        active_processes[uid] = proc
        await msg.reply(
            "✅ *Userbot Started!*\n\n"
            "/status — Check\n/stop — Stop\n/restart — Restart\n/logout — Delete session",
            parse_mode="Markdown")
        asyncio.create_task(monitor_userbot(uid, proc))
    except Exception as e:
        await msg.reply(f"❌ {str(e)}")

async def monitor_userbot(uid: int, proc: asyncio.subprocess.Process):
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=300)
        if proc.returncode != 0:
            logging.error(f"Userbot {uid} crashed: {err.decode().strip() if err else 'Unknown'}")
    except asyncio.TimeoutError:
        pass
    finally:
        active_processes.pop(uid, None)

# ─── User Commands ─────────────────────────────────────────
@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    uid = message.from_user.id
    if uid in active_processes and active_processes[uid].returncode is None:
        await message.reply("✅ *Running* 🟢", parse_mode="Markdown")
    elif os.path.exists(f"{SESSION_DIR}/{uid}.session"):
        await message.reply("ℹ️ Session hai, userbot nahi. /restart karein.")
    else:
        await message.reply("❌ Login nahi. /start se karein.")

@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):
    uid = message.from_user.id
    if uid in active_processes:
        p = active_processes[uid]
        if p.returncode is None:
            p.terminate()
            await asyncio.sleep(0.5)
        del active_processes[uid]
        await message.reply("✅ Stopped.")
    else:
        await message.reply("ℹ️ Already stopped.")

@dp.message(Command("restart"))
async def cmd_restart(message: types.Message):
    uid = message.from_user.id
    if uid in active_processes:
        p = active_processes[uid]
        if p.returncode is None:
            p.terminate()
        del active_processes[uid]
    sf = f"{SESSION_DIR}/{uid}.session"
    if os.path.exists(sf):
        await message.reply("🔄 Restarting...")
        await start_userbot(uid, message)
    else:
        await message.reply("❌ Pehle login. /start")

@dp.message(Command("logout"))
async def cmd_logout(message: types.Message):
    uid = message.from_user.id
    if uid in active_processes:
        p = active_processes[uid]
        if p.returncode is None:
            p.terminate()
        del active_processes[uid]
    sf = f"{SESSION_DIR}/{uid}.session"
    if os.path.exists(sf):
        os.remove(sf)
        ud = load_data()
        ud["users"][str(uid)]["has_userbot"] = False
        save_data(ud)
        await message.reply("✅ Logged out! Session deleted.")
    else:
        await message.reply("ℹ️ Already logged out.")

# ═══════════════════════════════════════════════════════════
# ─── OWNER COMMANDS ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════

def owner_check(message: types.Message):
    return message.from_user.id == OWNER_ID

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if not owner_check(message):
        return await message.reply("❌ Only owner.")
    data = load_data()
    txt = (
        "📊 *Bot Statistics*\n\n"
        f"👥 Total Users: `{len(data['users'])}`\n"
        f"✅ With Userbot: `{len([u for u in data['users'].values() if u.get('has_userbot')])}`\n"
        f"🟢 Running Now: `{len(active_processes)}`\n"
        f"📢 Broadcasts: `{data.get('broadcasts_sent', 0)}`\n"
        f"👑 Owner: `{OWNER_ID}`"
    )
    await message.reply(txt, parse_mode="Markdown")

@dp.message(Command("users"))
async def cmd_users(message: types.Message):
    if not owner_check(message):
        return await message.reply("❌ Only owner.")
    data = load_data()
    if not data["users"]:
        return await message.reply("No users yet.")
    lines = ["📋 *All Users:*\n"]
    for uid, info in data["users"].items():
        mention = f"@{info['username']}" if info['username'] else info['first_name']
        ub = "✅" if info.get("has_userbot") else "❌"
        lines.append(f"• {mention} (`{uid}`) — UB: {ub}")
    txt = "\n".join(lines)
    if len(txt) > 4000:
        txt = txt[:4000] + "\n... truncated"
    await message.reply(txt, parse_mode="Markdown")

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if not owner_check(message):
        return await message.reply("❌ Only owner.")
    txt = message.text.replace("/broadcast", "", 1).strip()
    if not txt:
        return await message.reply("❌ Use: `/broadcast <msg>`", parse_mode="Markdown")
    data = load_data()
    sent = failed = 0
    sm = await message.reply("📨 Broadcasting...")
    for uid_s in data["users"]:
        try:
            await bot.send_message(int(uid_s), txt, parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    data["broadcasts_sent"] = data.get("broadcasts_sent", 0) + 1
    data["total_messages"] = data.get("total_messages", 0) + sent
    save_data(data)
    await sm.edit_text(f"✅ *Done*\n📨 Sent: `{sent}`\n❌ Failed: `{failed}`", parse_mode="Markdown")

@dp.message(Command("announce"))
async def cmd_announce(message: types.Message):
    if not owner_check(message):
        return await message.reply("❌ Only owner.")
    txt = message.text.replace("/announce", "", 1).strip()
    if not txt:
        return await message.reply("❌ Use: `/announce <msg>`", parse_mode="Markdown")
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🤖 Open Bot", url=f"https://t.me/{(await bot.get_me()).username}", style=ButtonStyle.PRIMARY))
    data = load_data()
    sent = failed = 0
    sm = await message.reply("📢 Announcing...")
    for uid_s in data["users"]:
        try:
            await bot.send_message(int(uid_s), txt, reply_markup=builder.as_markup(), parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    data["broadcasts_sent"] = data.get("broadcasts_sent", 0) + 1
    data["total_messages"] = data.get("total_messages", 0) + sent
    save_data(data)
    await sm.edit_text(f"✅ *Announcement Done*\n📨 Sent: `{sent}`\n❌ Failed: `{failed}`", parse_mode="Markdown")

# ─── Main ──────────────────────────────────────────────────
async def main():
    logging.info("🤖 Bot starting...")
    for f in Path(SESSION_DIR).glob("*.session"):
        pass  # Keep existing sessions
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
