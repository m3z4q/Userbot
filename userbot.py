from telethon import TelegramClient, events, functions, types
from telethon.errors import FloodWaitError, SessionPasswordNeededError, PremiumAccountRequiredError, PhoneCodeExpiredError
from telethon.tl.functions.channels import InviteToChannelRequest, EditAdminRequest, EditBannedRequest, CreateChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest, SendReactionRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import ChatAdminRights, ChatBannedRights, InputMessagesFilterDocument, ReactionEmoji
from telethon.tl.functions.account import UpdateProfileRequest
import unicodedata
from PIL import Image, ImageDraw, ImageFont
import time, asyncio, os, logging, json, random, requests, io, glob, subprocess, base64, re, urllib.parse

start_time = time.time()
try:
    os.system("ulimit -n 1024")
except:
    pass
logging.basicConfig(level=logging.ERROR)
from gtts import gTTS

try:
    import qrcode as qrcode_mod
    HAS_QR = True
except ImportError:
    HAS_QR = False

try:
    from Crypto.Cipher import DES
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

def decrypt_saavn_url(enc_url):
    if not enc_url or enc_url.startswith("http"):
        return enc_url
    if not HAS_CRYPTO:
        return enc_url
    try:
        key = b'38346591'
        missing = len(enc_url) % 4
        if missing:
            enc_url += '=' * (4 - missing)
        enc_data = base64.b64decode(enc_url)
        cipher = DES.new(key, DES.MODE_ECB)
        decrypted = cipher.decrypt(enc_data)
        pad_len = decrypted[-1]
        if 1 <= pad_len <= 8:
            decrypted = decrypted[:-pad_len]
        decrypted = decrypted.rstrip(b'\x00')
        return decrypted.decode('utf-8')
    except Exception as e:
        return enc_url

api_id = 32557753
api_hash = "3aec7775e6af24432f2414f941409876"
app = TelegramClient("titansession11", api_id, api_hash)

CMD_PREFIX = "."
reply_pool = set()
swp_targets = {}
original_profile = {}
original_pfp = None

# ===== PER-CLIENT STATE =====
titan_targets = {}       # c_key -> {(chat_id, user_id): num}
titan_indices = {}       # c_key -> {(chat_id, user_id, num): idx}

titanl_workers = {}      # c_key -> {(chat_id, user_id): info}
titanl_indices = {}      # c_key -> {(chat_id, user_id): idx}

titanr_workers = {}      # c_key -> {(chat_id, user_id): info}
titanlr_workers = {}     # c_key -> {(chat_id, user_id): info}

processed_trigger_msgs = {}  # c_key -> set(msg_ids)

react_emojis = {}
self_react_emojis = {}

TITAN_SPEEDS = {}
for i in range(1, 8):
    TITAN_SPEEDS[f"titan{i}"] = 0.3
    TITAN_SPEEDS[f"titanr{i}"] = 0.3
for i in range(1, 6):
    TITAN_SPEEDS[f"titanl{i}"] = 0.3
    TITAN_SPEEDS[f"titanlr{i}"] = 0.3
TITAN_SPEEDS["default"] = 0.3

# ===== GLOBAL MUTE STORAGE =====
gmuted_users = {}  # c_key -> set(user_id)

# ============================================================
# PREMIUM EMOJI DATA
# ============================================================

PREMIUM_EMOJI_MAP = {
    "✅": ["6246537187614005254", "6246782404476803545"],
    "✔️": ["6246871001062185760"],
    "🔥": ["4956222745814762495", "4956606007221421405", "6086954744268460848"],
    "💥": ["6032673796530377389"],
    "⚡": ["5791970059597386804", "6087079590377820415"],
    "❤️": ["5783157259152397008", "5801084710343938087"],
    "💙": ["5780496071645991525", "6104780447684757396"],
    "💚": ["5888789252493283486"],
    "💛": ["5840261097719148872"],
    "🧡": ["5840263144212529797"],
    "💜": ["5840265018655703965"],
    "🖤": ["5840266939932994956"],
    "⭐": ["6244496562752331516", "5904618938578243567"],
    "🌟": ["6010156854955480259", "6086924086791902713"],
    "✨": ["6010338729640596556", "6010086134023985536"],
    "👑": ["5794422335599546668", "6089003761496232797"],
    "💰": ["6089104607328342288", "6086730718774300509"],
    "💎": ["6086778246882399112"],
    "👍": ["6089313931149448495", "4958626617535497157"],
    "👎": ["6088789257285988672"],
    "👏": ["6093744967304352336"],
    "😀": ["6093864814071780526", "6093922327978840798"],
    "😂": ["5782741660936966676", "5782746664573867142"],
    "😍": ["6010179687001625256"],
    "🥰": ["6044369013952222465", "6044359320211034681"],
    "😘": ["6044373012566774137"],
    "😎": ["6032853480782172520"],
    "😈": ["6035136809950778133", "6032695825417638128"],
    "👿": ["6035242444671421879"],
    "👻": ["6035070298087231243"],
    "👀": ["6035225389356290238", "6035081585261287115"],
    "👁️": ["6035338338406242050", "6035051267087143217"],
    "💀": ["6035374291577475270"],
}

FLAG_PREMIUM_MAP = {
    "🇺🇸": "5433865586356531140", "🇬🇧": "5433827537241258614",
    "🇮🇳": "5433601609076586221", "🇫🇷": "5433636707549331311",
    "🇩🇪": "5433845881046578644", "🇯🇵": "5434147542369579483",
    "🇷🇺": "5433674924168328689", "🇧🇷": "5433825269498525925",
    "🇮🇹": "5433627189901801019", "🇨🇳": "5435996255207567113",
    "🇨🇦": "5433979415874779870", "🇦🇺": "5434067655977874913",
    "🇰🇷": "5434142701941437163", "🇪🇸": "5434026158003862063",
    "🇲🇽": "5434131139889478358", "🇵🇰": "5434064563601421981",
    "🇧🇩": "5433854239052935880", "🇳🇵": "5433852744404317916",
    "🇱🇰": "5433609855413794108", "🇸🇦": "5433991338703991663",
    "🇦🇪": "5434013938821902926", "🇹🇷": "5433792911214917126",
}

PREMIUM_FALLBACK_POOL = [
    "6035051267087143217", "6034945975963881533", "6034845323405299835",
    "6035338338406242050", "6035225389356290238", "6035081585261287115",
    "6035243995154616907", "6034865170449175739", "6035173858338672933",
    "6034871295072539452", "6035136809950778133", "6032695825417638128",
    "6035355642829475999", "6035337951859184840", "6035060329468137931",
    "6032673796530377389", "6034962795055812935", "6035070298087231243",
    "6035242444671421879", "6035374291577475270", "6032853480782172520",
    "6044373012566774137", "6044369013952222465", "6044359320211034681",
    "5791970059597386804", "5794422335599546668", "6244496562752331516",
    "6246537187614005254", "6246782404476803545", "6247039939305808563",
    "6089104607328342288", "6086730718774300509", "6086664791026307819",
    "6089313931149448495", "6093744967304352336", "6093864814071780526",
    "5783157259152397008", "5780496071645991525", "5782741660936966676",
    "5780690182692935276", "5780793884678296697", "5783024321324651865",
    "4956222745814762495", "4958479549265347295",
]
_emoji_cache = {}

def get_premium_emoji_id(emoji_char):
    global _emoji_cache
    cached = _emoji_cache.get(emoji_char)
    if cached:
        return cached
    if emoji_char in PREMIUM_EMOJI_MAP:
        chosen = random.choice(PREMIUM_EMOJI_MAP[emoji_char])
    elif emoji_char in FLAG_PREMIUM_MAP:
        chosen = FLAG_PREMIUM_MAP[emoji_char]
    else:
        chosen = random.choice(PREMIUM_FALLBACK_POOL)
    _emoji_cache[emoji_char] = chosen
    return chosen

def _utf16_len(ch):
    return len(ch.encode("utf-16-le")) // 2

def is_flag_pair(ch1, ch2):
    return (0x1F1E0 <= ord(ch1) <= 0x1F1FF and 
            0x1F1E0 <= ord(ch2) <= 0x1F1FF)

def is_emoji_char(ch):
    cp = ord(ch)
    if 0x1F1E0 <= cp <= 0x1F1FF: return True
    if cp in (0xFE0F, 0xFE0E, 0x200D): return True
    if 0x1F3FB <= cp <= 0x1F3FF: return True
    if 0x1F600 <= cp <= 0x1F64F: return True
    if 0x1F300 <= cp <= 0x1F5FF: return True
    if 0x1F680 <= cp <= 0x1F6FF: return True
    if 0x2600 <= cp <= 0x26FF: return True
    if 0x2700 <= cp <= 0x27BF: return True
    if 0x1FA00 <= cp <= 0x1FA6F: return True
    if 0x1FA70 <= cp <= 0x1FAFF: return True
    if unicodedata.category(ch) == 'So': return True
    return False

PLACEHOLDER_CHAR = "🌟"

def process_text_to_premium(text):
    if not text:
        return text, []
    new_text = ""
    entities = []
    utf16_offset = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if i + 1 < len(text) and is_flag_pair(ch, text[i+1]):
            flag = ch + text[i+1]
            premium_id = get_premium_emoji_id(flag)
            ph_len = _utf16_len(PLACEHOLDER_CHAR)
            new_text += PLACEHOLDER_CHAR
            entities.append(types.MessageEntityCustomEmoji(
                offset=utf16_offset, length=ph_len, document_id=int(premium_id)
            ))
            utf16_offset += ph_len
            i += 2
            continue
        if is_emoji_char(ch):
            emoji_seq = ch
            j = i + 1
            while j < len(text):
                nc = text[j]
                ncp = ord(nc)
                if ncp in (0xFE0F, 0xFE0E, 0x200D) or 0x1F3FB <= ncp <= 0x1F3FF or 0x1F1E0 <= ncp <= 0x1F1FF:
                    emoji_seq += nc
                    j += 1
                elif is_emoji_char(nc):
                    emoji_seq += nc
                    j += 1
                else:
                    break
            premium_id = get_premium_emoji_id(emoji_seq)
            ph_len = _utf16_len(PLACEHOLDER_CHAR)
            new_text += PLACEHOLDER_CHAR
            entities.append(types.MessageEntityCustomEmoji(
                offset=utf16_offset, length=ph_len, document_id=int(premium_id)
            ))
            utf16_offset += ph_len
            i = j
            continue
        ch_len = _utf16_len(ch)
        new_text += ch
        utf16_offset += ch_len
        i += 1
    return new_text, entities

SELF_UIDS = {}
pair_states = {}
paired_clients = []
UID_OWNER = 8188215655
EMPTY_STR = ""
OWM_API_KEY = "96e7bc09138f66436f22e3fa43f912b0"

def bold_emoji(text, icon="✨"):
    lower = "𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇"
    upper = "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭"
    normal_l = "abcdefghijklmnopqrstuvwxyz"
    normal_u = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result = ""
    for ch in text:
        if ch in normal_l:
            result += lower[normal_l.index(ch)]
        elif ch in normal_u:
            result += upper[normal_u.index(ch)]
        else:
            result += ch
    if icon:
        return icon + " " + result + " " + icon
    return result

FANCY_STYLES = {
    "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ", "f": "ғ",
    "g": "ɢ", "h": "ʜ", "i": "ɪ", "j": "ᴊ", "k": "ᴋ", "l": "ʟ",
    "m": "ᴍ", "n": "ɴ", "o": "ᴏ", "p": "ᴘ", "q": "ǫ", "r": "ʀ",
    "s": "s", "t": "ᴛ", "u": "ᴜ", "v": "ᴠ", "w": "ᴡ", "x": "x",
    "y": "ʏ", "z": "ᴢ",
    "A": "ᴀ", "B": "ʙ", "C": "ᴄ", "D": "ᴅ", "E": "ᴇ", "F": "ғ",
    "G": "ɢ", "H": "ʜ", "I": "ɪ", "J": "ᴊ", "K": "ᴋ", "L": "ʟ",
    "M": "ᴍ", "N": "ɴ", "O": "ᴏ", "P": "ᴘ", "Q": "ǫ", "R": "ʀ",
    "S": "s", "T": "ᴛ", "U": "ᴜ", "V": "ᴠ", "W": "ᴡ", "X": "x",
    "Y": "ʏ", "Z": "ᴢ",
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉"
}
def fancy_text(text):
    result = ""
    for ch in text:
        result += FANCY_STYLES.get(ch, ch)
    return result

EMOJI_MAP = {
    "a": "🅰", "b": "🅱", "c": "🇨", "d": "🇩", "e": "🇪", "f": "🇫",
    "g": "🇬", "h": "🇭", "i": "🇮", "j": "🇯", "k": "🇰", "l": "🇱",
    "m": "🇲", "n": "🇳", "o": "🅾", "p": "🇵", "q": "🇶", "r": "🇷",
    "s": "🇸", "t": "🇹", "u": "🇺", "v": "🇻", "w": "🇼", "x": "🇽",
    "y": "🇾", "z": "🇿",
    "A": "🅰", "B": "🅱", "C": "🇨", "D": "🇩", "E": "🇪", "F": "🇫",
    "G": "🇬", "H": "🇭", "I": "🇮", "J": "🇯", "K": "🇰", "L": "🇱",
    "M": "🇲", "N": "🇳", "O": "🅾", "P": "🇵", "Q": "🇶", "R": "🇷",
    "S": "🇸", "T": "🇹", "U": "🇺", "V": "🇻", "W": "🇼", "X": "🇽",
    "Y": "🇾", "Z": "🇿",
    "0": "0️⃣", "1": "1️⃣", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣",
    "5": "5️⃣", "6": "6️⃣", "7": "7️⃣", "8": "8️⃣", "9": "9️⃣",
    " ": "  "
}
def emoji_text(text):
    result = ""
    for ch in text:
        result += EMOJI_MAP.get(ch, ch) + " "
    return result.strip()

async def text_to_sticker(text, output_path="text_sticker.webp"):
    sticker_size = (512, 512)
    img = Image.new("RGB", sticker_size, "black")
    draw = ImageDraw.Draw(img)
    font_size = 60
    font = None
    bold_fonts = [
        "C:\\Windows\\Fonts\\NirmalaB.ttf", "C:\\Windows\\Fonts\\Mangal.ttf",
        "C:\\Windows\\Fonts\\Arialbd.ttf", "C:\\Windows\\Fonts\\Arial.ttf",
        "C:\\Windows\\Fonts\\Calibrib.ttf", "C:\\Windows\\Fonts\\Timesbd.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/lohit/Lohit-Devanagari.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for font_path in bold_fonts:
        try:
            font = ImageFont.truetype(font_path, font_size)
            draw.text((0, 0), "\u0939", font=font)
            break
        except:
            continue
    if font is None:
        font = ImageFont.load_default()
    max_width = sticker_size[0] - 40
    max_height = sticker_size[1] - 40
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + " " + word if current_line else word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        text_width = bbox[2] - bbox[0]
        if text_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    total_height = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        total_height += (bbox[3] - bbox[1]) + 10
    while total_height > max_height and font_size > 20:
        font_size -= 5
        for font_path in bold_fonts:
            try:
                font = ImageFont.truetype(font_path, font_size)
                break
            except:
                continue
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]
            if text_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        total_height = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            total_height += (bbox[3] - bbox[1]) + 10
    y = (sticker_size[1] - total_height) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (sticker_size[0] - text_width) // 2
        draw.text((x+2, y+2), line, font=font, fill="gray")
        draw.text((x, y), line, font=font, fill="white")
        y += text_height + 10
    img.save(output_path, "WEBP", quality=95)
    return output_path

# ===== TITAN ATTACK TEXTS =====
TITAN_TEXTS = [
    [
        "~×🌷GAY🌷×~", "~×🌼BITCH🌼×~", "~×🌻LESBIAN🌻×~", "~×🌺CHAPRI🌺×~",
        "~×🌹TMKC🌹×~", "~×🏵️TMR🏵×️~", "~×🪷TMKB🪷×~", "~×💮CHUS💮×~",
        "~×🌸HAKLE🌸×~", "~×🌷GAREEB🌷×~", "~×🌼RANDY🌼×~", "~×🌻POOR🌻×~",
        "~×🌺TATTI🌺×~", "~×🌹CHOR🌹×~", "~×🏵️CHAMAR🏵️×~", "~×🪷SPERM COLLECTOR🪷×~",
        "~×💮CHUTI LULLI💮×~", "~×🌸KALWA🌸×~", "~×🌷CHUD🌷×~", "~×🌼CHUTKHOR🌼×~",
        "~×🌻BAUNA🌻×~", "~×🌺MOTE🌺×~", "~×🌹GHIN ARHA TUJHSE🌹×~", "~×🏵️CHI POOR🏵×️~",
        "~🪷PANTY CHOR🪷×~", "~×💮LAND CHUS💮×~", "~×🌸MUH MAI LEGA🌸×~", "~×🌷GAND MARE 🌷×~",
        "~×🌼MOCHI WALE 🌼×~", "~×🌻GANDMARE 🌻×~", "~×🌺KIDDE 🌺×~", "~×🌹LAMO 🌹×~",
        "~×🏵️BIHARI 🏵×️~", "~×🪷MULLE 🪷×~", "~×💮NAJAYESH LADKE 💮×~", "~×🌸GULAM 🌸×~",
        "~×🌷CHAMCHA🌷×~", "~×🌼EWW 🌼×~", "~×🌻CHOTE TATTE 🌻×~", "~×🌺SEX WORKER 🌺×~",
        "~×🌹CHINNAR MA KE LADKE 🌹×~"
    ],
    [
        """𝐒ᴛᴀᴛᴇ 𝐖ᴇᴛʜᴇʀ 𝐓ʜᴇ  𝐒ᴛᴀᴛᴇᴍᴇɴᴛꜱ 𝐀ʀᴇ 𝐓ʀᴜᴇ 𝙾𝚁 𝐅ᴀʟꜱᴇ:-
1] तेरी माँ रंडी - 𝚃𝚛𝚞𝚎😱
2] तू चुदकड़  - 𝚃𝚛𝚞𝚎😍
3] तेरी बहन रंडी - 𝚃𝚛𝚞𝚎🥰
4] तेरी मौसी चुदके भागी हुई है? - 𝚃𝚛𝚞𝚎🤣""",
        "𝘾𝙃𝙐𝙋 𝙍𝘼𝙉𝘿𝙄𝙆𝙀 भेनचोद😜😜🥁🔥 ᭄",
        "ᗷOOᖇ ᖴᗩTGYᗩ  KYᗩ Tᑌᗰᕼᗩᖇᗩ😹😹🤡👉🏻👌🏻 🤤🤤🤤",
        "𝑻𝒖𝒎🤢𝒔𝒂𝒃😱𝒓𝒂𝒏𝒅𝒊😎𝒌𝒆😍𝒃𝒂𝒄𝒉𝒆😈𝒉𝒐🙀𝒏𝒂𝒉𝒊😝𝒎𝒂𝒏𝒐🥶𝒕𝒐🤡𝒂𝒑𝒏𝒊😂𝒎𝒂😭𝒄𝒉𝒖𝒅𝒂𝒐🤣",
        """Fill in the bank question answer in following list
1. teri maa ____ ( rndi/ chinar)
2 teri ____ ( maa / bahen ) chodu
3 Tera baap____ ( grib / chudkad)""",
        "😐 teri 😐 ma 🦍 ulti 🍟 rndy 🥺 ya ⛏️ pulti 🚜 rndy 😆",
        "~𝙈𝘼𝘿𝙍𝘾𝙃𝙊𝘿¿🤔ᒪᑌᑎᗪ ᑕᕼᑌՏ 𝗕𝗔𝗗𝗔 𝗛𝗢ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍ᯓ★🤍 ۞ 🩷🩵💙۞ 🩷🩵💙۞ 🩷🩵💙ᯓ★🤍۞ 🩷🩵💙ᯓ★🤍۞ 🩷🩵💙ᯓ★🤍۞ 🩷🩵💙ᯓ★🤍۞ 🩷🩵💙ᯓ★🤍۞ 🩷🩵💙ᯓ★🤍۞ 🩷🩵💙ᯓ★🤍۞ 🩷🩵💙",
        "༼💕༽﹏﹏﹏﹏﹏﹏﹏﹏﹏ ᴛᴇʀɪ ᗰᗩ 𝘒𝘐 ᑕᕼᑌ𝘛 𝐑𝐔𝐁𝐁𝐄𝐑 кι 𝗧𝗔𝗥𝗛𝗔 𝘒𝘏𝘐𝘊𝘏𝘜𝘕𝘎𝘈 𝙍𝙉𝘿𝙊𝙈 𝐃ᴏ𝘨༆𖣔💙",
        "˚⊱🌈⊰˚ {hater}->જ⁀➴ 𝐓ᴇʀɪ 𝐌ᴀ 𝐊ɪ 𝐂ʜᴜᴛ 𝐌ᴇ 𝐁ᴊᴘ 𝐊ᴀ 𝐊ʜɪʟᴛᴀ 𝐇ᴜᴀ 𝐊ᴀᴍᴀʟ 🌷<3 🫰🏻<-----{-💞-}----->🖤🖤🖤🖤🖤🖤🖤 🖤 ˚⊱🌈⊰˚",
        "˚⊱🇦🇽⊰˚  匚卄ㄩ卩 ᥅ꪖꪀᦔﺃᛕꫀ ᥇ꪖᥴᥴ𝙃ꪀ 𒈙⸻🩵𒈙⸻❤️𒈙⸻🩷𒈙⸻🧡𒈙⸻💛𒈙⸻💚𒈙⸻💙𒈙⸻💜𒈙⸻🖤𒈙⸻🩶𒈙⸻🤍𒈙⸻ ˚⊱🇦🇽⊰˚",
        "ʙʜᴋ ᴛᴇʀɪ ᴍᴀᴀ ꜱᴀꜱᴛɪ ʀᴀɴᴅɪ(🩷)—(❤️)—(🧡)—(💛)—(💚)—(🩵)—(💙)—(💜)—(🖤)—(🩶)—(🤍)—(🤎)—(🌸)—(✨)—(🌙)—(⭐)—(🦋)—(💎)—(👑)—(⚡)—(🔥)—(🌌)—(🎀)—(💫)—(🪽)—(🫧)",
        "𝐓𝐑𝐘 𝐌𝐀𝐀 𝐊𝐎 𝐋𝐘 𝐑𝐄𝐄🍓🍓👈🏻  𝐓𝐑𝐘 𝐌𝐀𝐀 𝐊𝐎 𝐆𝐀𝐑𝐀𝐌 𝐓𝐄𝐋 𝐌𝐄 𝐅𝐑𝐘 𝐊𝐑𝐔🤢🤮🥵🥶😵🤢🥵🤮😵🤮🥴🤢🥵🤢😵",
        "𝐊ʏᴀ 𝐑ᴇ 𝐑ᴀɴᴅɪᴋᴇ 𝐂ᴏᴏʟ 𝐁ᴀɴᴇɢᴀ 𝐓ᴜ 𝐂ʜᴀʟ 𝐀ʙ 𝐂ʜᴜᴅ 𝐀ᴘɴᴇ 𝐁ᴀᴀᴘ TITAN 𝐒ᴇ - 🦢💘",
        "try maa सूर्य☀ nikalte hi pel du 😹🔥💔",
        "oi 𝐓ᴇʀɪ 𝐌‌ᴀᴀ गुलाम ₰🖤",
        "chl rndyce chud ke dikha 😂💥🤣🔥",
        "ᴛᴇʀɪ ᴍᴀᴀ ᴋɪ ᴄʜᴜᴛ ᴍᴇ ᴅᴇᴍᴏɴ ᴀʀᴛ 😈🩸",
        "✝ 𝐀ɴᴛᴀ𝐑 ᴍᴀɴ𝐓ᴀʀ 𝐒ʜᴀɪ𝐓ᴀɴ𝐈 𝐊ʜᴏ𝐏ᴀᴅ𝐀 𝐓𝐄𝐑𝐈 𝐀ᴍᴍ𝐈 𝐊ᴀ 𝐊ᴀʟ𝐀 𝐁ʜᴏs𝐃ᴀ  ━━━━━━━━ 💗᪲᪲᪲࣪ ִֶָ☾.ᯓᡣ𐭩🤍ྀི   ",
        " ׂׂૢ🩵___\n\n➶　　　　　　　➶　　　　　　➶　　　　　➶　　　　　　　　　➤　➷　　　　　　　　➷　　　　 　　　➷　　　　　　➷　　　　　　　　　　　　　　➷ 𝙏𝙀𝙍𝙄 𝙈𝘼𝘼 \\ 𝘽𝘼𝙃𝘼𝙉 𝘿𝙊𝙉𝙊 𝙆𝙊 𝙍𝘼𝙉𝘿𝙄 𝙆𝙊 𝘾𝙃𝙊𝘿𝙐 🤣　➶　　　　　　　➶　　　　　　➶　　　　　➶　　　　　　　　　➤　➷　　　　　　　　➷　　　　 　　　➷　　　　　　➷　　　　　　　　　　　　　　➷"
    ],
    [
        "TERI HACLI MAA KO CODU? 😿💔😤😔😡😨😡💔😭😜🤘🏻😰🤣😜",
        "RANDI K BAACHE TU LADEGA? CODU TERI MAA/-",
        "𝙏𝙀𝙍𝙄 𝙈𝘼𝘼 \\ 𝘽𝘼𝙃𝘼𝙉 𝘿𝙊𝙉𝙊 𝙆𝙊 𝙍𝘼𝙉𝘿𝙄 𝙆𝙊 𝘾𝙃𝙊𝘿𝙐👅　➶",
        "𝐓𝐄𝐑𝐈 𝐌𝐀𝐀_𝐁𝐀𝐇𝐀𝐍 𝐊𝐎 𝐂𝐇𝐎𝐃𝐔 𝐁𝐈𝐍𝐀 𝐂𝐎𝐍𝐃𝐎𝐌 𝐊𝐄 😝 𝐇𝐀𝐇𝐀𝐇𝐀 ׂׂૢ🩵__",
        "चुदाई Kha 😂❤️",
        "उठक बैठक लगा 😏🔥",
        "तेरी माँ चोदू 😍😍",
        "ओय कमजोर 🤢🤢",
        "लंड चूस 🥱🤍➿",
        "पिल्लै 🐕‍",
        "😱 arey 😉 ye 🤡 kaise 😋 kiya 😏 re 😁 teri 😊 maa 😍 randy 😭100% 😂",
        "कमजोर टट्टा",
        "👈🏻👆🏻🖖🏻👇🏻🤲🏻👉🏻🤏🏻 Idr Udr Jidr Bhi Dekhega Teri Randi Maa Dikhegi",
        " 𝘽𝙀𝙏𝘼 🤢᭄᭄᭄᭄ 🌟 𝙇𝙐𝙉𝘿 𝘾𝙃𝙐𝙎 🤪᭄᭄",
        "मदरचोद 🤮🤮",
        "ro 🤣🤣",
        "रंडी",
        "चुप tmr 😒😂",
        "Acha Beta ? Koi Na Mai Teri Maa Coduga 😹💥💯",
        "चुदकड़",
        "कमजोर पिल्ले 🤮👞",
        "Chup Rndyce ⁉",
        "Tmkc Mein Mist Breathing ☁",
        "Teri माँ Dead 😂😂😂",
        "Teri Maa Chodu If Yes Then Reply To My Message 😂😂💯💯",
        "चल तेरी माँ की चुत 🥵🥵",
        "Tera बाप Titan !❄️"
    ],
    [
        "RDP BIKKE SASTE ME (WIZARD KE h8r)KI MAA CHUDE RASHTE ME-------",
        "❤︎ᶠᶸᶜᵏᵧₒᵤMAA CHUDAO APNI 👻",
        "_________________________________________________________✫/PANI PIYUNGA BOTTLE ME TERI 🌚👑 ⚠️  KI MA KO CHODUNGAA HOTLE ME__________________________________________________________✫",
        "🦅 𝐌αᴛᴋҽ 𝐌ҽ 𝐍ʜι 𝐓ʜα 𝐏αɳι 💦 TERI 🕷 𝐌αα -- 𝐁αнαη 𝐑αη∂ιуσ 𝐊ι 𝐑αηι 🧊❤️‍🔥🥵👈🏻______________⋆⁺₊⋆ ☾ ⋆⁺₊⋆ ☁︎⋆⁺₊⋆ ☾ ⋆⁺₊⋆ ☁︎⋆⁺₊⋆ ☾⋆⁺₊⋆ ☾ ⋆⁺₊⋆ ☁︎⋆⁺₊⋆ ☾ ⋆⁺₊⋆ ☁︎⋆⁺₊⋆",
        "𝐓ᴇʀ𝐈 ᴍᴀ𝐀 -- ฿ᴀʜᴀɴ 𝙂𝘼𝘼𝙉𝐀 𝐁𝐀𝐉𝐀𝐀 𝐊𝐑 𝐂ʜ⭕𝐃 𝐃△ʟᴇɴɢ𝐄 ♡⊹🎧˚₊ 🖇️✩ ˚₊‧ ♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊‧♡⊹˚₊ ✩ ˚₊",
        " 𝘼𝙉𝙏𝘼𝙍 𝙈𝘼𝙉𝙏𝘼𝙍 𝙎𝙃𝘼𝙄𝙏𝘼𝙉𝙄 𝙆𝙃𝙊𝙋𝘿𝙊 𝐓𝐄𝐑𝐈⚡⚡  𝙈𝘼 𝙆𝘼 𝙆𝘼ʟ𝘼 𝘽𝙃𝙊𝙎𝘿𝘼࿐________________ ",
        "~×🈹BHOSDIKE🈹×~",
        "~×🈵BEHENCHOD🈵×~",
        "𝙀𝙆 𝙂𝘾 𝙎𝙀 𝙁𝘼𝙍𝘼𝙍 𝙏𝙀𝙍𝙄 𝙈𝘼𝘼 𝙆𝘐 𝘾𝙃𝙐𝙏𝙏 𝙁𝘼𝘼𝘿𝙐𝙐  𝘼𝙄𝙎𝙀 𝘽𝙉𝙀𝙂𝙔 ‍𝙎𝙋𝙈𝙍𝙍𝙍______________________/❤️‍🔥",
        "𝙆𝙔𝘼 𝙍𝙀𝙀 𝙂𝘼𝙍𝙄𝘽 𝙎𝙋𝘼𝙈𝙀𝙍 𝘽𝘼𝙉𝙀𝙂𝙔 𝙏𝙀𝙍𝙄 𝙈𝘼 𝙆𝘐 𝙎𝙀𝘼𝙇 𝙏𝙊𝘿 𝘿𝙐. ________________",
        " TERI 𝐵𝐴𝐻𝐸𝑁 𝐾𝐼 𝐶𝐻𝑈𝐷 𝐶𝐻𝐴𝐷𝐴𝐼 𝑀𝐸 𝐴𝐴𝑃𝐾𝐴 𝑆𝑊𝐴𝐺𝐴𝑇 𝐻𝐴𝐼 🤍☁️🌿~",
        "𝗝𝗢𝗥 𝗦𝗘 𝗕𝗢𝗟𝗢 TERI 𝗠𝗔𝗔 𝗣𝗔𝗧𝗔𝗞 𝗣𝗔𝗧𝗔𝗞 𝗞𝗘 𝗖𝗛𝗨𝗗 𝗚𝗔𝗜 🧸📋🧋🍪~",
        "TERI M̸A̸A̸ Y̸E̸ F̸O̸N̸T̸ M̸E̸ C̸H̸O̸D̸N̸A̸ B̸H̸U̸L̸ G̸A̸Y̸A̸ T̸H̸A̸  🎐🫧🦋🍭",
        "𝐏𝐈𝐊𝐊𝐑 𝗖𝗢𝗟𝗔 𝗗𝗔𝗔𝗟  𝐃𝐔𝐍𝐆𝐀 𝐓𝐄𝐑𝐈  𝐌𝐀𝐀 𝗞𝗘 𝗔𝗡𝗗𝗔𝗥 𝗟𝗢𝗗𝗔𝗔______________________________________________________________________😎",
        "TERI　ＭＫＣ　ＭＥ　ＨＡＭＬＡ ☠ ",
        "TERI MKB-----------------------",
        "𝐓𝐄𝐑𝐈 𝐑𝐔𝐍𝐃𝐘 𝐌𝐀𝐀 𝐂𝐇𝐔𝐃 𝐆𝐀𝐈 𝐓𝐇𝐎𝐊𝐎 𝐓𝐀𝐋𝐈 ❤️‍🔥",
        "(🥀) Nᴇᴡ Gᴇɴ Pɪʟʟᴇ Mᴀᴅʜᴀʀxʜᴏᴅ",
        "HAND SPAMMERS TUMHHARII MAA KO CHOD KE MARDU 😍💕//////////////////////////////////////////////",
        "ᴄʜɪᴅɪʏᴀ ᴄʜᴀᴅɪ ᴘᴇʜᴀᴅ ᴘᴇ ᴜsɴᴇ ᴅɪʏᴀ ᴍᴏᴏᴛ 🐦💦 TERI ᴍᴀᴀ ᴋɪ ᴄʜᴜᴛ 🙆‍♀️🤣___________________________________________________________________________________________________________________________________________",
        "ᴍᴀᴛᴋᴇ ᴍᴀɪ ᴍᴀᴛᴋᴀ ᴍᴀᴛᴋᴇ ᴍᴀɪ ɴɪᴋʟᴀ ᴀᴀʟᴜ ➞ 𝐓ERI MAA KI CHUT ᴋʜᴀᴊʏᴇɢᴀ ʏᴇ  ʙʜᴀᴀʟᴜ⌦",
        "𝐊ᴀsʜᴍɪʀ ᴍᴀɪ ᴘᴀᴅᴅ ʀʜɪ ʙᴏʜᴏᴛ ᴊᴏʀᴏ sᴇ ᴛʜᴀɴᴅ ➝ᴛᴇʀɪ ᴍᴀᴀ ᴋᴀᴀ ʙʜᴏsᴅᴀ ᴀᴜʀ ᴛᴇʀɪ ʙʜᴅɴ ᴋɪ ᴄʜᴜᴛ ᴍᴀɪ ᴍᴇʀᴀ ʟᴜɴᴅ⌦",
        "TERI-->! MAA NANGI CHUD GAYI ->-ᥬ🥵᭄",
        "तेरी  माँ रंडी// €₰🖤",
        " रेंडी के बच्चे ⚡",
        " तेरा बाप टकला ",
        "Lᴜɴᴅ ᴄʜᴜs ᴋᴇ ʙᴀᴅᴀ ʜᴏ 𑁍ࠬܓ<💚>",
        "𝐒ᴛᴀɴᴅ ᴡɪᴛʜ #𝕯𝐈𝐊 ⃟🌷꙰⃟ ᴀɴᴅ 𝐋ɪᴄᴋ ᴍʏ #𝐏𝐎𝐎𝐏 ⃟"
    ],
    [
        "─𝐓𝐄𝐑𝐈 𝐌𝐀𝐊𝐎 𝐂𝐇𝐎𝐃𝐊𝐄 𝐌𝐀𝐑 𝐃𝐔𝐆𝐀─ .✦",
        "𝐂𝐇𝐀𝐋 𝐂𝐎𝐕𝐄𝐑 𝐋𝐄 𝐓𝐌𝐊𝐂 ↚↚ ",
        "✦.── ❝ 𝑺𝑷𝑴𝑹 𝑩𝑵𝑬𝑮𝑬 𝑴𝑬𝑹𝑬 𝑺𝑷𝑬𝑹𝑴.✦",
        "【 𝗧𝗘𝗥𝗜 𝗠𝗔𝗔𝗞𝗢 𝗞𝗨𝗧𝗧𝗜𝗬𝗔 𝗕𝗔𝗡𝗔 𝗞𝗔𝗥 𝗖𝗛𝗢𝗗𝗨𝗨 𝗥𝗡𝗗𝗔𝗟  】",
        "          𝗕𝗛𝗜𝗞𝗔𝗥𝗜 𝗞𝗘 𝗟𝗔𝗗𝗞𝗘\n       ❝.𝗖𝗛𝗔𝗟 𝗦𝗣𝗘𝗘𝗗 𝗕𝗛𝗔𝗗𝗛𝗔.❞",
        "‿*ੈ✩𓆩✧𓆪𝗖𝗛𝗔𝗟 𝗥𝗡𝗗𝗜𝗞𝗘 𝗖𝗛𝗨𝗗𝗟𝗘*ੈ✩‿❦",
        "🅐🅡🅔🅑 🅢🅟🅜🅜🅡 🅒🅗🅤🅓🅚🅔 🅚🅗🅞🅣🅜💥",
        "↛↛𝑪𝑯𝑨𝑳 𝑪𝑯𝑨𝑴𝑨𝑹 𝑪𝑯𝑼𝑫𝑨𝑰 𝑲𝑯𝑨𝑨 ↚↚\n═꩜˚₊· ͟͟͞͞➳❥❝↬↬↫↫❞˚₊· ͟͟͞͞➳❥꩜═\n✦•┈๑⋅⋯ ⋯⋅๑┈•✦✦•┈๑⋅⋯ ⋯⋅๑┈•✦  ",
        "-=-=-=-=-=-=-==-=-=--=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= 𝐓 𝐔 𝐌 -- 𝐋 𝐎 𝐆 𝐎 -- 𝐊 𝐈 -- 𝐌 𝐀 𝐀 -- 𝐊 𝐀 -- 𝐁 𝐇 𝐎 𝐒 𝐃 𝐀 -- 𝐅 𝐀 𝐓 𝐓 𝐀 -- 𝐆 𝐀 𝐘 𝐀-=-=-=",
        "💀𝘁𝗲𝗿𝗲 𝗺𝗮𝗮 𝗸𝗲 𝗯𝗵𝗼𝘀𝗱𝗲 ko\n\n𝟮𝟳𝘅 🐂 ( 𝗯𝘂𝗹𝗹) 𝗯𝘂𝗿 𝗸𝗼 𝗰𝗵𝗼𝗱𝗲𝗴𝗮\n𝟭𝟲 𝘅 🐘  𝗰𝗵𝗼𝗱𝗲𝗴𝗮\n𝟭𝟰 𝘅 🐶 𝗰𝗵𝗼𝗱𝗲𝗴𝗮 \n𝟭𝟯 𝘅🐯 𝗰𝗵𝗼𝗱𝗲𝗴𝗮\n𝟭𝟮𝘅 🐺 𝗰𝗵𝗼𝗱𝗲𝗴𝗮 \n𝟭𝟭𝘅  🦇 𝗰𝗵𝗼𝗱𝗲𝗴𝗮\n𝟭𝟬𝘅 🐛 𝗰𝗵𝗼𝗱𝗲𝗴𝗮\n𝟵𝘅 🦅 𝗰𝗵𝗼𝗱𝗲𝗴𝗮 \n𝟴𝘅 🦖 𝗰𝗵𝗼𝗱𝗲𝗴𝗮\n𝟳𝘅 🦀 𝗰𝗵𝗼𝗱𝗲𝗴𝗮\n𝟲𝘅 🐙 𝗰𝗵𝗼𝗱𝗲𝗴𝗮\n𝟱𝘅 🐗 𝗰𝗵𝗼𝗱𝗲𝗴𝗮 \n𝟰𝘅 🦚 𝗰𝗵𝗼𝗱𝗲𝗴𝗮 \n𝟯𝘅 🐿🦨🦩 𝗰𝗵𝗼𝗱𝗲𝗻𝗴𝗲 \n𝟮𝘅 🦉 𝗰𝗵𝗼𝗱𝗲𝗴𝗮\n𝗜𝗻𝗳𝗶𝗻𝗶𝘁𝗲 𝘅  𝗺𝗮𝗶 𝗯𝗵𝗶 𝗰𝗵𝗼𝗱𝘂𝗻𝗴𝗮 𝘁𝗲𝗿𝗶 𝗺𝗮𝗮  🤣🤰🦇SAL3",
        "TERI DAADI KO.BATMAN BNKE AADHI RAAT KO CHODUNGA ",
        "(•_•)\n/\\  \\__(•_•)\n_// _//\nTeri maiya xhod rha hu😝Teri maa ke pom pom blast hoJaye",
        "𝗧𝗘𝗥𝗜 𝗠𝗔𝗔 𝗥𝗔𝗡𝗗𝗜 𝗛𝗔𝗠𝗘 𝗞𝗬𝗨 𝗕𝗔𝗧𝗔 𝗥𝗛𝗔 𝗛𝗔𝗜── .✦ ‧₊˚ Ջ⋅♡🖤🎀\n⋅♡🖤🎀༘── .✦ ‧₊˚",
        "RAND CHUDAI KHA TMKB 🔥💢 ( ၴႅၴ » » »💔",
        "➤ ⎯꯭̽᭕ᬁ𝗧ᴇ𝗥ɪ 𝗠ᴀ𝗔 𝗠ᴀʀ ɢᴀʏɪ ʀᴀɴᴅɪ 𝗞ᴇ ʙᴀᴄʜᴇ𝁘⃪꯭⃛𓆪꯭𝆬⎯꯭⎯? ⋆👞 ₊˚ෆ𓂃˖˳·˖ ִֶָ ⋆⋆𓂃˖˳·",
        "𝙆𝙔𝘼 𝙍𝙀𝙀 𝙂𝘼𝙍𝙄𝘽 𝙎𝙋𝘼𝙈𝙀𝙍 𝘽𝘼𝙉𝙀𝙂𝙔 𝙏𝙀𝙍𝙄 𝙈𝘼 𝙆𝘐 𝙎𝙀𝘼𝙇 𝙏𝙊𝘿 𝘿𝙐------------------/❤️____________________________________________",
        "ANTAR MANTAR SHAITANI KHOPDA  kamzor KAMJOR KIDE TERI MAA KA BHOSDA࿐❤️‍🩹 ",
        "तेरी माँ की oral pills चूत😹💊😹💊😹💊😹💊",
        "𝙋𝙃𝙇𝙀 𝙏𝙀𝙍𝙄 𝘽𝙃𝙀𝙉 𝘾𝙃𝙊𝘿𝙐 𝙔𝘼 𝙏𝙀𝙍𝙄 𝙈𝙊?😜🗯",
        "🔺पिल्लै Tᴜᴊʜᴇ ᴍᴀʀᴇɴɢᴇ ʏᴀʜɪ ᴅᴇʟʜɪ ᴍᴀʏᴜʀ ᴠɪʜᴀʀ ᴍᴇ ᴊᴀʙ ᴍᴀʀᴇɴɢᴇ ᴅᴇᴋʜ ʟᴇɴᴀ 🔥>💀",
        "𝙀𝙆𝘿𝘼𝙈 𝘾𝙃𝙐𝙋 𝙈𝘼𝘿𝘼𝙍𝘾𝙃𝙊𝘿 𝙏𝙀𝙍𝙄 𝙈𝘼 𝙆𝘼 #𝘾𝙃𝙐𝘿𝘼𝙄 𝙃𝙊𝙎𝙏𝙀𝙇🏥 𝘽𝘼𝙉𝘼𝙍𝙔 𝙃𝙐",
        "agar teri bhen ko teri ma ke samne 🥬 pe bithadu to phle kon chilayegi tri ma ya teri bhen",
        "👌🏿🤙🏿👌🏿👈🏿👀🗣️🫵🏿👶🏿👧🏿teri kale ma baap ki dark love story",
        "East ➡️ or west ⬅️ teri ma babita is best🥵⚒🔥🥵⚒🔥",
        "Soch tera naam loda singh hota fir tera ma tujhe loda smjhke roj chusti",
        "𝘢𝘣𝘦 𝘩𝘢𝘵𝘵 सस्ती Rᴀɴᴅɪ ᴋᴀ काला 𝘉𝘢𝘤𝘤𝘩𝘢🤢",
        "ᴛᴇʀɪ ᶜʰⁱⁿᵃᵃʳ ᵐᵃᵃ ᵏᴏ लकड़गंज ˡᵉ ʲᵃᵃᵏᵉ ᶜʰᵘᵈʷᵃ दूंगा 𝐑ɴ𝐃ɪ𝐊🦖💨🔥 😑👌🏻"
    ],
    [
        "𝘾𝙃𝙐𝙋 𝙍𝘼𝙉𝘿𝙄𝙆𝙀 भेनचोद😜😜🥁🔥 ᭄",
        "𝐒ᴜɴ 𝐓ᴇʀᴇ 𝐌ᴀᴀ 𝐊𝐨 𝐓ᴇʀᴇ 𝐁ᴀᴀᴩ 𝐍ᴇ नहीं 𝐌ᴀɪɴᴇ 𝐂ʜᴏᴅ𝐀 है 🦹🦹🦹",
        "𝐓ᴜᴊʜ𝐄 𝐂ᴏᴏ𝐋 𝐁ᴏʟ𝐔 𝐘ᴀ 𝐑ɴ𝐃𝐈 𝐊ᴀ 𝐁ᴀᴄᴄʜ𝐀 🔥😸🔥😸🔥😸🔥😸🔥",
        "ᵀᴱᴿᴵ ᴹᴬᴬ Cʜɪꪀꫝꞁ (🩵) ༂",
        "तेरी मां रंगबिरंगी रण्डी ❤️🧡💛💚🩵💙",
        "𝐎ʏᴇ 𝐇ᴋʟᴀ 𝐌ᴀᴛ 𝐓ᴇʀɪ 𝐕ᴇɴ 𝐃𝐣 𝐎ᴘᴇʀᴀᴛ𝐎ʀ 𝐒ᴇ 𝐁ᴜɴᴅ 𝐌ʀᴡ𝐀ᴅᴜ ~ 🤪🔥",
        "Tᴜᴊʜᴇ ᴀᴄᴛᴏʀ ʙᴀɴ ɴᴀ ʜᴀɪ? ᴛᴇʀʏ ᴍᴀ Sᴜɴɴʏ ᴅᴇᴏʟ sᴇ चुद जाये 💪🏿😁",
        "𝘾𝙃𝘼𝙇 𝙍𝘼𝙉𝘿𝙄𝙆𝙀 𝙐𝙏𝙃𝘼𝙆 𝘽𝙀𝙏𝙃𝘼𝙆 𝙇𝘼𝙂𝘼🔥",
        "𝗧𝗘𝗥𝗜 𝗠𝗔𝗔 𝗖𝗛𝗨𝗗 𝗥𝗔𝗛𝗜 𝗛𝗔𝗜 𝗗𝗘𝗞𝗛 𝗠𝗧𝗧 ╚══════════════════════════════🩵",
        "𝘔𝘐𝘚𝘛𝘙𝘐 𝘒𝘌 𝘓𝘈𝘋𝘒𝘌 𝘚𝘗𝘈𝘔𝘔𝘌𝘙 𝘉𝘈𝘕𝘌𝘎𝘈 𝘛𝘌𝘙𝘐 𝘔𝘈𝘈 𝘒𝘐 𝘊𝘏𝘜𝘛 🤢🔥",
        "𝐓𝐄𝐑𝚰 𝐌𝐀𝐀 𝐊𝐎 𝚰 𝐋𝐎𝐕𝐄 𝐘𝐎𝐔 𝐑𝐄 😂🤘🏻×~",
        "✦ ⛩𝗖 𝗛 𝗨 𝗗𖣔・✦・⭑・✦・",
        "Tohar maiya ke bur mein యార్ తేరి మమ్మీ పాగల్ maggie style attack 💀💀💔💔💔😱😱😭😭🔥🔥🔥🗣🤣🤣🤣🤣😜😜🔥",
        "𝙥𝙞𝙡𝙡𝙚 𝙩𝙚𝙧𝙞 𝙢𝙖 𝙠𝙖 𝙗𝙪𝙧 𝙗𝙡𝙖𝙨𝙩 𝙝𝙤𝙩𝙖 𝙝𝙪𝙖 𝙙𝙞𝙠𝙝𝙧𝙖 𝙢𝙪𝙟𝙚😂😂",
        "~×👨‍👧𝘒𝘠𝘈 𝙍𝙀𝙔 𝙍𝘼𝙉𝘿𝙔𝘼 𝙁𝙔𝙏𝙀𝙍 𝘽𝘼𝙉𝙀𝙂𝘼 👻❤️",
        "~×👩‍👧oye तेरी माँ etna उछलके kese चुदलेती h 🤯🤯💪🏼~",
        "𝙏𝙀𝙍𝙄 𝙈𝘼𝘼 𝘽𝙃𝙊𝙎𝘿𝙀 𝙈𝙀 𝙇𝘼𝙏 𝙋𝘼𝘿𝙀𝙉𝙂𝙀 𝙎𝘼𝘽𝙃𝙄",
        "𝐭𝐞𝐫𝐢 𝐦𝐚 𝐤𝐚 𝐠𝐚𝐥𝐚 𝐤𝐚𝐭𝐞𝐠𝐚 𝐫𝐞 𝐚𝐚𝐣😂~",
        "𝘾𝙃𝙐𝙋 𝙍𝘼𝙉𝘿𝙄𝙆𝙀 भेनचोद😜😜🥁🔥 ᭄",
        "तेरे मां के दूदू के बीच मेरा lund fas gaya oops 🤪（ ͜.🍆 ͜.）",
        "*, ☞︎︎︎. 𝘾𝙃𝘼𝙇 ☮️ 𝙏𝙀𝙍𝙄 🤞🏻 𝙈𝘼𝘼 🙈 𝙍𝘼𝙉𝘿𝙄 ❤",
        "~×Try mom toilet×~",
        "~×🧠Tri sister k 🫁 bech diye mene ab khus hoja🧠×~",
        "~×Tri maa 420~",
        "~बहुत ज्यादा बड़ी Rɴᴅɪ ho aap toh😆🫧Trymaa ko www m lejakr codunga😂🥊😂🥊😂🥊😂🥊×~",
        "Tri maa ki bh0nsri nhi mili toh kya hogya tri bhen ki shut le lunga",
        "Tri mummy aag m fek kr tri maa ki saari jameen jaydat apne naam krlunga×~",
        "~Tri maa ki fti purani bhosri k sath diwali manauga😑🎇Teri maa kidr codu\nJunglo mein?ya/room no 56 mein?×~",
        "~×Bhen shudwa ले यार×~",
        "Tri maa ki shut mein 12w ka charger daldunga shmjanarndyk",
        "Tri maa की ek baat btani hai wo maa nahi hijda hai hijda×~",
        "Tri mummy ko sbse phele mar dunga fir uski laash ko shod dunga kaisa Raha idea?"
    ],
    [
        "~Tri Chachi ki bhen ki bua ki beti ki nani ki tai ki bhai ki sbki bhen ki bhonsri marunga×~",
        "~×🌪️➪ᵗʳⁱ ᵐᵃᵃ डांसर♫︎ रण्डी😆🧊🌪️×~",
        "~👩🏿      👩🏻‍🦳        👵🏼         👱🏿‍♀️     \n👗      👚        👗         👚\n👖      👖        👖         👖     \n\nतेरी बहन /तेरी माँ /तेरी दादि/ तेरीभुआ.\n\nसब की 𝐂hu𝐃𝐚i hogi🪄 अंतर मंत्र शैतानी खोपड़ा आपकी मां का भोसड़ा 🪄🪄 अंतर मंत्र शैतानी खोपड़ा आपकी मां का भोसड़ा 🪄🪄 अंतर मंत्र शैतानी खोपड़ा आपकी मां का भोसड़ा 🪄",
        "~×𝘙 𝘈 𝘕 𝘋 𝘐 𝘒 𝘌 𝘉𝘈𝘊𝘏𝘌 𝘊 𝘏 𝘜 𝘗 𝘌𝘒𝘋𝘈𝘔? 🤪🤪🤪×~",
        "~×💥Dekh teri ma chodne wala bandar 🐒⃤ triangle ke andar💥×~",
        "~×⚡< Ƭᴇʀɪ Mᴏᴍ Ʀᴀꪀᴅɪ > 【🥋】⚡×~",
        "~×🌧️chup रंडी k bache🌧️×~",
        "~×⛈️ᴋᴜᴛᴛᴇ ɢᴜʟᴀᴍɪ ᴋʀ ?⛈️×~",
        "~×🌨️BARAF🌨️×~",
        "~×🌪️TOORNADO🌪️×~",
        "~×🌋chup rndyke 🍟⛏️🍟⛏️🍟⛏️🍟🔥😁😁🌋×~",
        "~×🏔️🫩🫩🫩Cʜᴜᴘ रंडि k kalwe मदरचोद 🤢👋🏻🏔️×~",
        "~×🗻TERI BAHEN K BOSDE ME AAAG😹❤️‍🔥😹❤️‍🔥😹❤️‍🔥😹❤️‍🔥😹🗻×~",
        "~×🏝️Ary😳 ye😍 kese😱 Kiya 😱re 🤡mc 😂teri😁 ma😘 rndi🤣 hai🤨 100% 🙊🏝️×~",
        "~×🏜️Teri मोम कa रेpe hogya bc 😩🥺🥳😎💔🔥💔😡🤕💪😘🥺🤣🏜️×~",
        "~×🌲𝐓𝐄𝐑𝐈 𝐌𝐀𝐀 𝐊𝐈 ̷C̷̷H̷̷U̷̷T̷ 𝗠𝗘 𝐋𝐎U𝐃𝐀 ̷M̷̷A̷̷D̷̷A̷̷R̷̷C̷̷H̷̷O̷̷D̷🤣🩷🤚🏼🌲×~",
        "~×🌴4𝘎 𝘗𝘐𝘓𝘓𝘖 𝘊𝘖𝘋𝘜🤣🌴×~",
        "~×🌵Dekho मेरे छोटे भाई ने majak Kiya है सब ये \"🤣\"वाला reaction kar do🌵×~",
        "~×🌾𝚝𝚛𝚒 𝚖𝚘𝙼 𝙲𝙷𝚒𝚗𝚊𝚊𝚕🐾🌾×~",
        "~×🌻tri maa ke sir ke baal ukhed duga🌻×~",
        "~×🌺𝙾̶𝚢̶𝚢̶ ̶𝚖𝚊̶𝚍𝚊̶𝚛̶𝚌̶𝚑̶𝚘̶𝚍̶ ̶𝚌̶𝚑̶𝚞̶𝚙̶🌺×~",
        "~×🌸𝑪𝒉𝒖𝒑 ʳᵃⁿᵈⁱ 𝑲𝒆 𝑩𝒂𝒄𝒄𝒉𝒆 🖤🎀🖤🎀🖤🎀🎀🖤🌸×~",
        "~×🌷Foy tri maa ki toot😂🌷×~",
        "~×🌹ⓘ यह संदेश हटा दिया गया था क्योंकि ap chamar ho×~",
        "~×🌼Tri maa k muh pr ek mukke Maar dunga urfi javed jaisi shakal ho jayegi 🤣💞🤣💞🤣💞🌼×~",
        "~×🌻𝘛𝘙𝘐 👃🏻 𝘔𝘌𝘐𝘕 𝘓𝘜𝘕𝘋 𝘎𝘏𝘜𝘚𝘈 𝘋𝘜𝘕𝘎𝘈🤣🌻×~",
        "~×🌞𝘒𝘐 𝘔𝘈𝘒𝘖 𝘊𝘏𝘖𝘋 𝘒𝘙 𝘗𝘈𝘎𝘈𝘓 𝘒𝘙 𝘋𝘜𝘕𝘎𝘈 ??🌞×~",
        "~×🌙CHAAND🌙×~",
        "~×⭐𝘛𝘌𝘙𝘐 𝘔𝘈𝘈 𝘒𝘖 𝘊𝘏𝘖𝘋𝘜𝘕 ??⭐×~",
        "~×🌟𝘛𝘌𝘙𝘐 𝘔𝘈𝘒𝘈 𝘉𝘏𝘖𝘚𝘋𝘈 𝘔𝘈𝘋𝘈𝘙𝘟𝘏𝘖𝘋 ??🌟×~",
        "~×✨ƦƛƝƊƖ ƘƖ Mƛƛ ƤƝƬƖ ƘӇƠԼ ??✨×~",
        "~×💫ƦƲƝƊƳ ƘƖ ƠԼƛƊ ??💫×~",
        "~×🌍𝙏𝙚𝙧𝙞 𝙢𝙖𝙖 𝙠𝙚 𝙗𝙝𝙤𝙨𝙙𝙚 𝙢𝙚 𝙡𝙖𝙩 𝙥𝙙𝙚𝙣𝙜𝙚 𝙗𝙝𝙤𝙩 𝙩𝙚𝙯 👻 😂👯😂👯😂👯 😂👯😂👯😂👯 😂👯😂👯😂👯🌍×~",
        "~×🌏TRI MA ℝ𝔸ℕ𝙳𝙸-Rᴀɴᴅɪ-гคภ๔เ-𝘙𝘈𝙉𝘿Ｉ-𝚁𝙰𝙽𝙳𝙸-яαη∂ι-RÄñÐÌ,-Ɽ₳₦Đł-ᖇᗩ₦ĐI KESE BHI BOL LU RAHEGI TO TRI MA RANDI💘🦋🌏×~",
        "~×🌎DUNIYA🌎×~",
        "~×🌌KAYNAT🌌×~",
        "~×🌠Tery ma konse rang ke condom se chudegi???  🔴🟠🟡🟢🔵🟣🟤⚪️⚫️🌠×~",
        "~×☄️#bAaP_sE_lAdEgA_pAgAL_⚠️☣️☄️×~",
        "~×🪐VO KEHTE HENA TERI MA RANDI SAHI KEHTE HE🗿🗿🗿🗿🗿⚓️⚓️⚓️⚓️⚓️🪐×~",
        "~×🌕आंड भात खाओगे बेटा 🍚 ! 🙇🏻‍♂️\n   तुम्हारी भेन चुसेगी मेरा लंड 🍌 मे रहूँगा बैठा 👻\n\nतेरी मा को चोद दूंगा! बिस्तर पे लेटा लेटा 😜🛖🌕×~",
        "~×🌑Icecream chaat mera lun ni rndike 😆👊🏻😂🙏🥀🥀🌑×~"
    ]
]

TITANL_TEXTS = [
    [
        "🔥 TERI MA KI CHUT ME BBC 🔥\nAaja bhadwe teri ma ko itna chodu ki teri ma bole bas kar bete.\nTERI MAA KI... AULAAD TERE BAAP KI NAHI HAI!",
        "💀 TERI BEHEN MERI DIWANI 💀\nUski video call pe aati hai roz raat ko.\nTERI BEHEN KI CHUT ME LAND DAAL DIYA MAIN..\nAb tu rote reh ja bhadwe!",
        "👿 TERI BUA KA BHOSDA 👿\nIzzat hai kisi cheej ki? Teri ma ne tujhe paida kiya to galati kari.\nMai to teri poori family ka land lord hu.",
        "🖕 TERI MAA KA BALTKAAR 🖕\nTeri ma to itni famous rand hai ki uska rate card bhi hai.\nSunday - 500 | Monday - 700 | Tuesday Full day booking 🎯",
        "😂 TERI BHEN KI CHUT ME MIRCHI 😂\nAaja bhadwe teri behn ko leke bhaagunga.\nTu gareeb hai, teri behn ko tera pura ghar bechna padega."
    ],
    [
        "💀 TERI MA KO RANDI BANA DIYA 💀\nHa bhadwe, teri ma ko maine randi banaya.\nRoz raat ko bulati hai mujhe.\nTERI MA CHUDTI HAI ROZ!",
        "🔥 TERI BEHEN KA VIRGINITY 🔥\nTeri behn ki virginity tune li thi? Nahi, tune nahi li kyunki teri behn ne toh mujhe di thi!",
        "🖕 TERA BAAP BHI MERA CLIENT 🖕\nTera baap roz aata hai mere paas.\nMaine kaha:- TERI BIWI TO MERI RAND HAI!",
        "👿 TERI FAMILY KA BUSINESS 👿\nTeri ma rand\nTeri behn rand\nSAB MERI RAND!",
        "🌋 TERA GHAR TO MERE NAAM 🌋\nTera ghar bhi mere naam hai.\nKyuki teri ma ne sab kuch mere naam kar diya! 💀"
    ],
    [
        "💀 TERI MAI KA BIRTHDAY 💀\nTeri ma ka birthday tha kal.\nMaine gift diya - Ek raat ka session!",
        "🔥 TERI BEHEN KA WEDDING 🔥\nTeri behn ki shaadi hai? Lekin wo to meri hai!",
        "🖕 TERI MAI KI PHOTO 🖕\nTeri ma ki photo mere paas hai.\nNangi photo! Mai group me daal dunga!",
        "👿 TERA BAAP KA SECRET 👿\nTera baap bhi mera client hai!\nWo bhi aata hai mere paas.",
        "🎯 TERI MAI KI CHUT KA COLOR 🎯\nTeri ma ki chut ka color kala hai.\nItna kala ki jungle ka andhera!"
    ],
    [
        "⚔️ TERI MAI KI HISTORY ⚔️\nTeri ma ki history bohot purani hai.\nCollege time se rand thi.",
        "💀 TERI BEHEN KA FAVOURITE 💀\nTeri behn ka favourite kon hai?\nMAI HU!",
        "🔥 TERA GHAR KA MALIK 🔥\nTere ghar ka malik kon hai?\nMAI HU!",
        "🖕 TERA BAAP KA NAAM 🖕\nTera baap ka naam kya hai?\nKya pata? Teri ma ko bhi nahi pata!",
        "👿 TERI MAI KI SKILL 👿\nTeri ma ki skill hai.\nChudai me!"
    ],
    [
        "💀 NATIONAL GEOGRAPHIC - TERI MA 💀\nTeri ma - Ek aisi rand jo roz 20 londo se chudti hai.",
        "🔥 TERI BEHEN KA TALENT SHOW 🔥\nTeri behn ka talent - HAR LONDE KO SATISFY KARNA!",
        "🖕 TERI MAI KA INTERVIEW 🖕\nInterviewer: Aap kaise rand bani?",
        "👿 TERI BEHEN KA RESUME 👿\nSkills: Oral, Doggy, 69, BDSM\nAwards: Best Rand 2020-2024!",
        "💥 TERA PARIVAR - EK SCRIPT 💥\nScene 1: Teri ma apne client ke saath."
    ]
]

async def safe_send_reaction(client, chat_id, msg_id, emoji):
    try:
        await client(SendReactionRequest(peer=chat_id, msg_id=msg_id,
            reaction=[types.ReactionEmoji(emoticon=emoji)]))
    except PremiumAccountRequiredError:
        pass
    except Exception:
        pass

async def continuous_reply_worker(client, chat_id, reply_to_msg_id, texts, system_name, workers_subdict, key):
    idx = 0
    while key in workers_subdict and workers_subdict[key].get("active", False):
        try:
            txt = texts[idx % len(texts)]
            await client.send_message(chat_id, txt, reply_to=reply_to_msg_id)
            idx += 1
            spd = TITAN_SPEEDS.get(system_name, TITAN_SPEEDS["default"])
            await asyncio.sleep(spd)
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 1)
        except Exception:
            await asyncio.sleep(2)
    workers_subdict.pop(key, None)

def build_help_menu(p):
    menu = (
        f"╔{'═'*50}╗\n"
        f"║{' '*12}✦  𝐓𝐈𝐓𝐀𝐍 𝐁𝐎𝐓 𝐯𝟖  ✦{' '*12}║\n"
        f"║{' '*17}𝐏𝐫𝐞𝐟𝐢𝐱: [ {p} ]{' '*20}║\n"
        f"╚{'═'*50}╝\n\n"
    )
    menu += (
        f"◢◤ 𝗥𝗘𝗔𝗖𝗧𝗜𝗢𝗡𝗦 ◢◤\n"
        f"  ├💖 {p}react <emoji>     𝗥𝗘𝗔𝗖𝗧 𝗢𝗡 𝗢𝗧𝗛𝗘𝗥𝗦\n"
        f"  ├💞 {p}mreact <emoji>    𝗥𝗘𝗔𝗖𝗧 𝗢𝗡 𝗦𝗘𝗟𝗙\n"
        f"  └❌ {p}react / {p}mreact            𝗢𝗙𝗙\n\n"
    )
    menu += (
        f"◢◤ 𝗠𝗢𝗗𝗘𝗥𝗔𝗧𝗜𝗢𝗡 ◢◤\n"
        f"  ├🔇 {p}mute (reply/@)    𝗠𝗨𝗧𝗘 𝗨𝗦𝗘𝗥\n"
        f"  ├🔊 {p}unmute (reply/@)  𝗨𝗡𝗠𝗨𝗧𝗘 𝗨𝗦𝗘𝗥\n"
        f"  ├🌐 {p}gmute (reply/@)   𝗚𝗟𝗢𝗕𝗔𝗟 𝗠𝗨𝗧𝗘\n"
        f"  ├🌍 {p}gunmute (reply/@) 𝗚𝗟𝗢𝗕𝗔𝗟 𝗨𝗡𝗠𝗨𝗧𝗘\n"
        f"  ├📢 {p}an <text>         𝗔𝗡𝗢𝗨𝗡𝗖𝗘𝗠𝗘𝗡𝗧\n"
        f"  └📋 {p}mutelist          𝗠𝗨𝗧𝗘𝗗 𝗟𝗜𝗦𝗧\n\n"
    )
    menu += (
        f"◢◤ 𝗔𝗧𝗧𝗔𝗖𝗞 𝗦𝗬𝗦𝗧𝗘𝗠 ◢◤\n"
        f"  ├🎯 {p}titan1—7         𝗦𝗛𝗢𝗥𝗧 𝗧𝗘𝗫𝗧\n"
        f"  ├📝 {p}titanl1—5        𝗟𝗢𝗡𝗚 𝗧𝗘𝗫𝗧\n"
        f"  ├🔄 {p}titanr1—7        𝗦𝗛𝗢𝗥𝗧 𝗖𝗢𝗡𝗧𝗜𝗡𝗨𝗢𝗨𝗦\n"
        f"  ├🔁 {p}titanlr1—5       𝗟𝗢𝗡𝗚 𝗖𝗢𝗡𝗧𝗜𝗡𝗨𝗢𝗨𝗦\n"
        f"  ├🎭 {p}swp / {p}stopswp        𝗦𝗪𝗜𝗣𝗘 𝗠𝗢𝗗𝗘\n"
        f"  ├💬 {p}replypool / {p}stopreply  𝗥𝗘𝗣𝗟𝗬 𝗣𝗢𝗢𝗟\n"
        f"  ├⚡ {p}speed <sys> <s>   𝗦𝗘𝗧 𝗦𝗣𝗘𝗘𝗗\n"
        f"  └💀 {p}killall          𝗦𝗧𝗢𝗣 𝗔𝗟𝗟\n\n"
    )
    menu += (
        f"◢◤ 𝗦𝗧𝗢𝗣 𝗖𝗢𝗠𝗠𝗔𝗡𝗗𝗦 ◢◤\n"
        f"  ├🛑 {p}stoptitan1-7     𝗦𝗧𝗢𝗣 𝗦𝗛𝗢𝗥𝗧\n"
        f"  ├🛑 {p}stoptitanl1-5    𝗦𝗧𝗢𝗣 𝗟𝗢𝗡𝗚\n"
        f"  ├🛑 {p}stoptitanr      𝗦𝗧𝗢𝗣 𝗖𝗢𝗡𝗧𝗜𝗡𝗨𝗢𝗨𝗦 𝗦𝗛𝗢𝗥𝗧\n"
        f"  └🛑 {p}stoptitanlr     𝗦𝗧𝗢𝗣 𝗖𝗢𝗡𝗧𝗜𝗡𝗨𝗢𝗨𝗦 𝗟𝗢𝗡𝗚\n\n"
    )
    menu += (
        f"◢◤ 𝗚𝗥𝗢𝗨𝗣 𝗔𝗗𝗠𝗜𝗡 ◢◤\n"
        f"  ├🔒 {p}lock / {p}unlock        𝗟𝗢𝗖𝗞/𝗨𝗡𝗟𝗢𝗖𝗞\n"
        f"  ├👢 {p}kick              𝗞𝗜𝗖𝗞 𝗨𝗦𝗘𝗥\n"
        f"  ├🗑️ {p}del               𝗗𝗘𝗟𝗘𝗧𝗘 𝗠𝗦𝗚\n"
        f"  ├🧹 {p}purge             𝗣𝗨𝗥𝗚𝗘 𝗕𝗘𝗟𝗢𝗪\n"
        f"  ├⭐ {p}promote / {p}allryt     𝗣𝗥𝗢𝗠𝗢𝗧𝗘\n"
        f"  ├➕ {p}add / {p}addbots         𝗔𝗗𝗗 𝗨𝗦𝗘𝗥/𝗕𝗢𝗧𝗦\n"
        f"  ├📁 {p}crtgc <n>         𝗖𝗥𝗘𝗔𝗧𝗘 𝗚𝗥𝗢𝗨𝗣𝗦\n"
        f"  └📌 {p}pin               𝗣𝗜𝗡 𝗠𝗘𝗦𝗦𝗔𝗚𝗘\n\n"
    )
    menu += (
        f"◢◤ 𝗨𝗧𝗜𝗟𝗜𝗧𝗜𝗘𝗦 ◢◤\n"
        f"  ├🎵 {p}song <name>       𝗦𝗔𝗔𝗩𝗡 𝗗𝗢𝗪𝗡𝗟𝗢𝗔𝗗\n"
        f"  ├🗣️ {p}tts <text>        𝗧𝗘𝗫𝗧 → 𝗦𝗣𝗘𝗘𝗖𝗛\n"
        f"  ├🎨 {p}txtstk <text>     𝗧𝗘𝗫𝗧 → 𝗦𝗧𝗜𝗖𝗞𝗘𝗥\n"
        f"  ├🖼️ {p}mkstk (reply)     𝗜𝗠𝗔𝗚𝗘 → 𝗦𝗧𝗜𝗖𝗞𝗘𝗥\n"
        f"  ├📱 {p}qrcode <text>     𝗤𝗥 𝗖𝗢𝗗𝗘\n"
        f"  ├🌤️ {p}weather <city>    𝗪𝗘𝗔𝗧𝗛𝗘𝗥\n"
        f"  ├🌐 {p}ip <addr>         𝗜𝗣 𝗟𝗢𝗢𝗞𝗨𝗣\n"
        f"  ├🔗 {p}short <url>       𝗨𝗥𝗟 𝗦𝗛𝗢𝗥𝗧𝗘𝗡𝗘𝗥\n"
        f"  ├🧮 {p}calc <expr>       𝗖𝗔𝗟𝗖𝗨𝗟𝗔𝗧𝗢𝗥\n"
        f"  ├✨ {p}fancy <text>      𝗙𝗔𝗡𝗖𝗬 𝗧𝗘𝗫𝗧\n"
        f"  ├🔤 {p}emoji <text>      𝗘𝗠𝗢𝗝𝗜 𝗦𝗧𝗬𝗟𝗘\n"
        f"  └🅿️ {p}pre <text>        𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗘𝗠𝗢𝗝𝗜\n\n"
    )
    menu += (
        f"◢◤ 𝗣𝗥𝗢𝗙𝗜𝗟𝗘 ◢◤\n"
        f"  ├📋 {p}info (reply)      𝗨𝗦𝗘𝗥 𝗜𝗡𝗙𝗢\n"
        f"  ├📸 {p}copy (reply)      𝗖𝗢𝗣𝗬 𝗣𝗥𝗢𝗙𝗜𝗟𝗘\n"
        f"  ├🔄 {p}revert           𝗥𝗘𝗦𝗧𝗢𝗥𝗘 𝗕𝗔𝗖𝗞𝗨𝗣\n"
        f"  └📱 {p}sessions         𝗦𝗛𝗢𝗪 𝗦𝗘𝗦𝗦𝗜𝗢𝗡𝗦\n\n"
    )
    menu += (
        f"◢◤ 𝗣𝗔𝗜𝗥 / 𝗦𝗬𝗦𝗧𝗘𝗠 ◢◤\n"
        f"  ├📞 {p}pair +91xxx       𝗣𝗔𝗜𝗥 𝗡𝗘𝗪 𝗖𝗟𝗜𝗘𝗡𝗧 (𝗢𝗪𝗡𝗘𝗥 𝗢𝗡𝗟𝗬)\n"
        f"  ├🔢 {p}c <code>          𝗩𝗘𝗥𝗜𝗙𝗬 𝗢𝗧𝗣 (𝗢𝗪𝗡𝗘𝗥 𝗢𝗡𝗟𝗬)\n"
        f"  ├🔑 {p}p <password>      𝟮𝗙𝗔 𝗟𝗢𝗚𝗜𝗡 (𝗢𝗪𝗡𝗘𝗥 𝗢𝗡𝗟𝗬)\n"
        f"  ├⚙️ {p}prefix <sym>      𝗖𝗛𝗔𝗡𝗚𝗘 𝗣𝗥𝗘𝗙𝗜𝗫\n"
        f"  ├🏓 {p}ping              𝗣𝗜𝗡𝗚\n"
        f"  └📊 {p}status           𝗕𝗢𝗧 𝗦𝗧𝗔𝗧𝗨𝗦\n\n"
    )
    menu += (
        f"───『 💀 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗧𝗜𝗧𝗔𝗡 𝗕𝗢𝗧 💀 』───\n"
    )
    return menu
async def resolve_user_from_event(event, client, parts):
    """
    Resolve target user from:
    1. Reply to a message → reply sender
    2. Mention in text → @username resolution
    3. Numeric UID in text
    Returns (user_id, user_entity_or_None)
    """
    target_uid = None
    target_entity = None

    # Method 1: Reply
    if event.is_reply:
        reply = await event.get_reply_message()
        if reply and reply.sender_id:
            target_uid = reply.sender_id
            try:
                target_entity = await client.get_entity(target_uid)
            except:
                pass

    # Method 2: Mention (@username) or numeric ID in parts[1]
    if target_uid is None and len(parts) >= 2:
        arg = parts[1].strip()
        # Check if it's a mention (@username)
        if arg.startswith("@"):
            try:
                entity = await client.get_entity(arg)
                target_uid = entity.id
                target_entity = entity
            except Exception:
                pass
        # Check if it's a numeric UID
        elif arg.lstrip("-").isdigit():
            target_uid = int(arg)
            try:
                target_entity = await client.get_entity(target_uid)
            except:
                pass
        # Check if it's a username without @
        else:
            try:
                entity = await client.get_entity(arg)
                target_uid = entity.id
                target_entity = entity
            except:
                pass

    return target_uid, target_entity


@events.register(events.NewMessage)
async def auto_handler(event):
    global CMD_PREFIX, original_pfp, processed_trigger_msgs
    global titan_targets, titan_indices, titanl_workers, titanl_indices
    global titanr_workers, titanlr_workers, gmuted_users

    client = event.client
    sender = await event.get_sender()
    if not sender:
        return
    sender_id = sender.id
    chat_id = event.chat_id
    msg_text = event.text or EMPTY_STR
    cmd_text = msg_text.strip()
    p = CMD_PREFIX
    c_key = id(client)

    # ── AUTO-REACT ──
    if c_key in SELF_UIDS:
        my_id = SELF_UIDS[c_key]
        sr_key = (c_key, chat_id)
        if sr_key in self_react_emojis and sender_id == my_id:
            await safe_send_reaction(client, chat_id, event.id, self_react_emojis[sr_key])
        r_key = (c_key, chat_id)
        if r_key in react_emojis and sender_id != my_id:
            await safe_send_reaction(client, chat_id, event.id, react_emojis[r_key])

    # ── GLOBAL MUTE CHECK ──
    if c_key in gmuted_users and sender_id in gmuted_users[c_key]:
        if sender_id != SELF_UIDS.get(c_key):
            # Delete the message and warn the user
            try:
                await event.delete()
                # Send a private mute notification (only once, to avoid spam)
            except:
                pass
            return  # Don't process anything from globally muted users

    # ── SWP ──
    if (chat_id, sender_id) in swp_targets:
        try:
            await client.send_message(chat_id, "mkc", reply_to=event.id)
        except:
            pass
        return

    # ── REPLYPOOL ──
    if chat_id in reply_pool:
        try:
            await client.send_message(chat_id, "😛", reply_to=event.id)
        except:
            pass
        return

    # ── Ensure per-client tracking ──
    if c_key not in processed_trigger_msgs:
        processed_trigger_msgs[c_key] = set()
    if c_key not in titan_targets:
        titan_targets[c_key] = {}
    if c_key not in titan_indices:
        titan_indices[c_key] = {}
    if c_key not in titanl_workers:
        titanl_workers[c_key] = {}
    if c_key not in titanl_indices:
        titanl_indices[c_key] = {}
    if c_key not in gmuted_users:
        gmuted_users[c_key] = set()

    # ── TITAN1-7 TRIGGER ──
    if (chat_id, sender_id) in titan_targets[c_key]:
        if event.id not in processed_trigger_msgs.get(c_key, set()):
            processed_trigger_msgs[c_key].add(event.id)
            num = titan_targets[c_key][(chat_id, sender_id)]
            texts = TITAN_TEXTS[num - 1]
            idx_key = (chat_id, sender_id, num)
            current_idx = titan_indices[c_key].get(idx_key, 0)
            txt = texts[current_idx % len(texts)]
            titan_indices[c_key][idx_key] = current_idx + 1
            try:
                await client.send_message(chat_id, txt, reply_to=event.id)
            except:
                pass
        return

    # ── TITANL1-5 TRIGGER ──
    if (chat_id, sender_id) in titanl_workers.get(c_key, {}) and titanl_workers[c_key][(chat_id, sender_id)].get("active", False):
        if event.id not in processed_trigger_msgs.get(c_key, set()):
            processed_trigger_msgs[c_key].add(event.id)
            num_data = titanl_workers[c_key][(chat_id, sender_id)].get("num", 0)
            texts = TITANL_TEXTS[num_data - 1] if num_data > 0 else TITANL_TEXTS[0]
            current_idx = titanl_indices[c_key].get((chat_id, sender_id), 0)
            txt = texts[current_idx % len(texts)]
            titanl_indices[c_key][(chat_id, sender_id)] = current_idx + 1
            try:
                await client.send_message(chat_id, txt, reply_to=event.id)
            except:
                pass
        return

    # ── COMMAND PROCESSING ──
    if not cmd_text.startswith(p):
        return

    # Only process commands sent by THIS client's own user
    try:
        me_self = await client.get_me()
        self_uid = me_self.id
    except:
        self_uid = None

    if sender_id != self_uid:
        return

    is_owner = (self_uid == UID_OWNER)

    parts = cmd_text[len(p):].strip().split()
    if not parts:
        return
    cmd = parts[0].lower()

    # === HELP ===
    if cmd == "help":
        menu = build_help_menu(p)
        await event.edit(menu)
        return

    # === PING ===
    if cmd == "ping":
        st = time.time()
        await event.edit(bold_emoji("Pinging...", "📡"))
        en = time.time()
        ms = round((en-st)*1000)
        await event.edit(bold_emoji("PONG", "🏓") + "\n" + bold_emoji(f"{ms} ms", "⚡"))
        return

    # === PRE ===
    if cmd == "pre":
        if len(parts) < 2:
            return await event.edit(bold_emoji("Usage: .pre <text with emojis>", "❌") + "\n" + bold_emoji("Example: .pre Hello! 🔥❤️⭐", "💡"))
        raw_text = " ".join(parts[1:])
        await event.edit(bold_emoji("🔄 Converting to premium emojis...", "✨"))
        try:
            processed_text, entities = process_text_to_premium(raw_text)
            if not entities:
                return await event.edit(bold_emoji("No emojis found in text!", "❌") + "\n" + bold_emoji("Add some emojis like 🔥❤️⭐", "💡"))
            await event.delete()
            await client.send_message(chat_id, processed_text, formatting_entities=entities)
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:80]}", "❌"))
        return

    # === MUTE (reply/mention/UID) — group-level mute ===
    if cmd == "mute":
        target_uid, target_entity = await resolve_user_from_event(event, client, parts)
        if target_uid is None:
            return await event.edit(bold_emoji("Reply to a user, mention @username, or provide UID", "❌"))
        try:
            ban_rights = ChatBannedRights(
                until_date=None,
                send_messages=True,
                send_media=True,
                send_stickers=True,
                send_gifs=True,
                send_games=True,
                send_inline=True,
                send_polls=True,
                embed_links=True
            )
            await client(EditBannedRequest(chat_id, target_uid, ban_rights))
            user_str = f"@{target_entity.username}" if target_entity and getattr(target_entity, 'username', None) else str(target_uid)
            await event.edit(bold_emoji(f"Muted: {user_str}", "🔇"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === UNMUTE (reply/mention/UID) ===
    if cmd == "unmute":
        target_uid, target_entity = await resolve_user_from_event(event, client, parts)
        if target_uid is None:
            return await event.edit(bold_emoji("Reply to a user, mention @username, or provide UID", "❌"))
        try:
            ban_rights = ChatBannedRights(
                until_date=None,
                send_messages=False,
                send_media=False,
                send_stickers=False,
                send_gifs=False,
                send_games=False,
                send_inline=False,
                send_polls=False,
                embed_links=False
            )
            await client(EditBannedRequest(chat_id, target_uid, ban_rights))
            user_str = f"@{target_entity.username}" if target_entity and getattr(target_entity, 'username', None) else str(target_uid)
            await event.edit(bold_emoji(f"Unmuted: {user_str}", "🔊"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === GMUTE (global mute — deletes all messages from user across ALL chats) ===
    if cmd == "gmute":
        target_uid, target_entity = await resolve_user_from_event(event, client, parts)
        if target_uid is None:
            return await event.edit(bold_emoji("Reply to a user, mention @username, or provide UID", "❌"))
        if c_key not in gmuted_users:
            gmuted_users[c_key] = set()
        gmuted_users[c_key].add(target_uid)
        user_str = f"@{target_entity.username}" if target_entity and getattr(target_entity, 'username', None) else str(target_uid)
        await event.edit(bold_emoji(f"Globally Muted: {user_str}", "🌐🔇"))
        return

    # === GUNMUTE (global unmute) ===
    if cmd == "gunmute":
        target_uid, target_entity = await resolve_user_from_event(event, client, parts)
        if target_uid is None:
            return await event.edit(bold_emoji("Reply to a user, mention @username, or provide UID", "❌"))
        if c_key in gmuted_users and target_uid in gmuted_users[c_key]:
            gmuted_users[c_key].discard(target_uid)
            user_str = f"@{target_entity.username}" if target_entity and getattr(target_entity, 'username', None) else str(target_uid)
            await event.edit(bold_emoji(f"Globally Unmuted: {user_str}", "🌐🔊"))
        else:
            await event.edit(bold_emoji("User was not globally muted", "ℹ️"))
        return

    # === MUTELIST ===
    if cmd == "mutelist":
        if c_key not in gmuted_users or not gmuted_users[c_key]:
            return await event.edit(bold_emoji("No globally muted users", "📋"))
        user_list = []
        for uid in gmuted_users[c_key]:
            try:
                entity = await client.get_entity(uid)
                uname = f"@{entity.username}" if entity.username else str(uid)
            except:
                uname = str(uid)
            user_list.append(uname)
        txt = bold_emoji("GLOBALLY MUTED USERS", "📋") + "\n"
        for i, u in enumerate(user_list, 1):
            txt += f"\n{i}. {u}"
        await event.edit(txt)
        return

    # === AN (Announcement) ===
    if cmd == "an":
        if len(parts) < 2:
            return await event.edit(bold_emoji(f"Usage: {p}an <announcement text>", "❌"))
        announce_text = " ".join(parts[1:])
        # Pin an announcement message
        try:
            msg = await client.send_message(chat_id, 
                bold_emoji("📢 ANNOUNCEMENT 📢", "📢") + "\n\n" + announce_text)
            # Also pin it
            await client.pin_message(chat_id, msg.id, notify=True)
            await event.delete()  # Delete the .an command message
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === STATUS ===
    if cmd == "status":
        upt = int(time.time()-start_time)
        txt = bold_emoji("TITAN BOT STATUS", "📊") + "\n"
        txt += bold_emoji(f"Uptime: {upt}s", "⏱") + "\n"
        txt += bold_emoji(f"Prefix: {CMD_PREFIX}", "⚙️") + "\n"
        txt += bold_emoji(f"Paired: {len(paired_clients)}", "📱") + "\n"
        txt += bold_emoji(f"Titan Active: {len(titan_targets.get(c_key, {}))}", "🎯") + "\n"
        muted_cnt = len(gmuted_users.get(c_key, set()))
        txt += bold_emoji(f"GMuted: {muted_cnt}", "🔇") + "\n"
        txt += bold_emoji(f"QR: {'✅' if HAS_QR else '❌'}", "📱")
        await event.edit(txt)
        return

    # === PREFIX ===
    if cmd == "prefix":
        if len(parts) < 2:
            return await event.edit(bold_emoji(f"Current Prefix: {CMD_PREFIX}", "⚙️"))
        newp = parts[1].strip()
        if len(newp) > 3:
            return await event.edit(bold_emoji("Prefix max 3 chars", "❌"))
        CMD_PREFIX = newp
        await event.edit(bold_emoji(f"Prefix Changed: {newp}", "✅"))
        return

    # === SPEED ===
    if cmd == "speed":
        if len(parts) < 3:
            return await event.edit(bold_emoji(f"Usage: {p}speed <system> <seconds>", "❌"))
        sname = parts[1].lower()
        try:
            sv = float(parts[2])
        except:
            return await event.edit(bold_emoji("Invalid speed value", "❌"))
        if sname not in TITAN_SPEEDS:
            return await event.edit(bold_emoji(f"Invalid system: {sname}", "❌"))
        TITAN_SPEEDS[sname] = sv
        await event.edit(bold_emoji(f"Speed: {sname} -> {sv}s", "✅"))
        return

    # === SESSIONS ===
    if cmd == "sessions":
        txt = bold_emoji("ACTIVE SESSIONS", "📱") + "\n"
        txt += bold_emoji(f"Main: titansession11", "🔵") + "\n"
        for c in paired_clients:
            try:
                me = await c.get_me()
                txt += bold_emoji(f"Paired: {me.id}", "🟢") + "\n"
            except:
                pass
        txt += bold_emoji(f"Total: {len(paired_clients)+1}", "📊")
        await event.edit(txt)
        return

   # === REACT ===
    if cmd in ("react", "emoji"):
        r_key = (c_key, chat_id)
        if len(parts) >= 2:
            react_emojis[r_key] = parts[1]
            txt = bold_emoji(f"React ON in THIS chat ✅", "✨")
            txt += "\n" + bold_emoji(f"Emoji: {parts[1]}", "💖")
            await event.edit(txt)
        else:
            if r_key in react_emojis:
                del react_emojis[r_key]
                await event.edit(bold_emoji("React OFF in THIS chat", "🔴"))
            else:
                await event.edit(bold_emoji("Already OFF here", "ℹ️"))
        return

    # === MREACT ===
    if cmd == "mreact":
        sr_key = (c_key, chat_id)
        if len(parts) >= 2:
            self_react_emojis[sr_key] = parts[1]
            txt = bold_emoji(f"Self-React ON in THIS chat ✅", "✨")
            txt += "\n" + bold_emoji(f"Emoji: {parts[1]}", "💖")
            await event.edit(txt)
        else:
            if sr_key in self_react_emojis:
                del self_react_emojis[sr_key]
                await event.edit(bold_emoji("Self-React OFF in THIS chat", "🔴"))
            else:
                await event.edit(bold_emoji("Already OFF here", "ℹ️"))
        return

    # === SWP ===
    if cmd == "swp":
        if not event.is_reply:
            return await event.edit(bold_emoji("Reply to a user", "❌"))
        reply = await event.get_reply_message()
        if not reply or not reply.sender_id:
            return await event.edit(bold_emoji("Reply to a user", "❌"))
        uid = reply.sender_id
        swp_targets[(chat_id, uid)] = True
        await event.edit(bold_emoji("SWP", "🎯") + "\n" + bold_emoji(f"User: {uid}", "👤") + "\n" + bold_emoji("Status: ACTIVE", "✅"))
        return

    # === STOPSWP ===
    if cmd == "stopswp":
        if not event.is_reply:
            return await event.edit(bold_emoji("Reply to user", "❌"))
        reply = await event.get_reply_message()
        if not reply:
            return await event.edit(bold_emoji("Reply to user", "❌"))
        uid = reply.sender_id
        swp_targets.pop((chat_id, uid), None)
        await event.edit(bold_emoji("SWP Stopped", "🔴"))
        return

    # === REPLYPOOL ===
    if cmd == "replypool":
        reply_pool.add(chat_id)
        await event.edit(bold_emoji("ReplyPool: ON", "🟢"))
        return

    # === STOPREPLY ===
    if cmd == "stopreply":
        reply_pool.discard(chat_id)
        await event.edit(bold_emoji("ReplyPool: OFF", "🔴"))
        return

    # === LOCK ===
    if cmd == "lock":
        try:
            rights = ChatBannedRights(until_date=None,
                send_messages=True, send_media=True, send_stickers=True,
                send_gifs=True, send_games=True, send_inline=True, send_polls=True,
                embed_links=True, invite_users=True, change_info=False, pin_messages=False)
            await client(functions.messages.EditChatDefaultBannedRightsRequest(peer=chat_id, banned_rights=rights))
            await event.edit(bold_emoji("Group LOCKED 🔒", "🔐"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === UNLOCK ===
    if cmd == "unlock":
        try:
            rights = ChatBannedRights(until_date=None,
                send_messages=False, send_media=False, send_stickers=False,
                send_gifs=False, send_games=False, send_inline=False, send_polls=False,
                embed_links=False, invite_users=True, change_info=False, pin_messages=False)
            await client(functions.messages.EditChatDefaultBannedRightsRequest(peer=chat_id, banned_rights=rights))
            await event.edit(bold_emoji("Group UNLOCKED 🔓", "🔓"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === KICK ===
    if cmd == "kick":
        target_uid, target_entity = await resolve_user_from_event(event, client, parts)
        if target_uid is None:
            return await event.edit(bold_emoji("Reply, mention @, or provide UID", "❌"))
        try:
            ban_rights = ChatBannedRights(until_date=None, view_messages=True, send_messages=True)
            await client(EditBannedRequest(chat_id, target_uid, ban_rights))
            await asyncio.sleep(0.5)
            await client(EditBannedRequest(chat_id, target_uid, ChatBannedRights(until_date=None)))
            await event.edit(bold_emoji(f"Kicked: {target_uid}", "👢"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === DEL ===
    if cmd == "del":
        if not event.is_reply:
            return await event.edit(bold_emoji("Reply to a message", "❌"))
        reply = await event.get_reply_message()
        if not reply:
            return await event.edit(bold_emoji("Reply to a message", "❌"))
        try:
            await reply.delete()
            await event.edit(bold_emoji("Message Deleted ✅", "🗑"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === PROMOTE ===
    if cmd == "promote":
        target_uid, target_entity = await resolve_user_from_event(event, client, parts)
        if target_uid is None:
            return await event.edit(bold_emoji("Reply, mention @, or provide UID", "❌"))
        try:
            rights = ChatAdminRights(change_info=True, delete_messages=True, ban_users=True,
                invite_users=True, pin_messages=True, manage_call=True,
                add_admins=False, anonymous=False, other=False)
            await client(EditAdminRequest(chat_id, target_uid, rights))
            await event.edit(bold_emoji(f"Promoted: {target_uid}", "⭐"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === ALLRYT ===
    if cmd == "allryt":
        target_uid, target_entity = await resolve_user_from_event(event, client, parts)
        if target_uid is None:
            return await event.edit(bold_emoji("Reply, mention @, or provide UID", "❌"))
        try:
            rights = ChatAdminRights(change_info=True, delete_messages=True, ban_users=True,
                invite_users=True, pin_messages=True, manage_call=True,
                add_admins=True, anonymous=False, other=True)
            await client(EditAdminRequest(chat_id, target_uid, rights))
            await event.edit(bold_emoji(f"All Rights Given: {target_uid}", "⚡"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === WEATHER ===
    if cmd == "weather":
        if len(parts) < 2:
            return await event.edit(bold_emoji("Usage: .weather <city>", "❌"))
        city = " ".join(parts[1:])
        await event.edit(bold_emoji(f"Fetching weather for {city}...", "🌤"))
        try:
            url = f"https://api.openweathermap.org/data/2.5/weather?q={urllib.parse.quote(city)}&appid={OWM_API_KEY}&units=metric"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if data.get("cod") != 200:
                return await event.edit(bold_emoji(f"City not found: {city}", "❌"))
            main = data["main"]
            wind = data["wind"]
            weather = data["weather"][0]
            txt = bold_emoji(f"{city.upper()}", "🌍") + "\n"
            txt += bold_emoji(f"Weather: {weather['main']} ({weather['description']})", "🌤") + "\n"
            txt += bold_emoji(f"Temp: {main['temp']}°C", "🌡") + "\n"
            txt += bold_emoji(f"Feels like: {main['feels_like']}°C", "💨") + "\n"
            txt += bold_emoji(f"Humidity: {main['humidity']}%", "💧") + "\n"
            txt += bold_emoji(f"Wind: {wind['speed']} m/s", "🌬")
            await event.edit(txt)
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === IP ===
    if cmd == "ip":
        if len(parts) < 2:
            return await event.edit(bold_emoji("Usage: .ip <ip>", "❌"))
        ip = parts[1]
        await event.edit(bold_emoji(f"Looking up {ip}...", "🔍"))
        try:
            resp = requests.get(f"http://ip-api.com/json/{ip}", timeout=10)
            data = resp.json()
            if data.get("status") != "success":
                return await event.edit(bold_emoji(f"Invalid IP: {ip}", "❌"))
            txt = bold_emoji(f"IP: {ip}", "🌐") + "\n"
            txt += bold_emoji(f"ISP: {data.get('isp', 'N/A')}", "🏢") + "\n"
            txt += bold_emoji(f"Country: {data.get('country', 'N/A')}", "🗺") + "\n"
            txt += bold_emoji(f"City: {data.get('city', 'N/A')}", "🏙") + "\n"
            txt += bold_emoji(f"Region: {data.get('regionName', 'N/A')}", "📍") + "\n"
            txt += bold_emoji(f"Lat/Lon: {data.get('lat', '?')}, {data.get('lon', '?')}", "📌")
            await event.edit(txt)
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === SHORT ===
    if cmd == "short":
        if len(parts) < 2:
            return await event.edit(bold_emoji("Usage: .short <url>", "❌"))
        url = parts[1]
        await event.edit(bold_emoji("Shortening URL...", "🔗"))
        try:
            resp = requests.get(f"https://tinyurl.com/api-create.php?url={urllib.parse.quote(url)}", timeout=10)
            if resp.status_code == 200:
                short = resp.text.strip()
                await event.edit(bold_emoji(f"Original: {url}", "📎") + "\n" + bold_emoji(f"Short: {short}", "🔗"))
            else:
                await event.edit(bold_emoji("Failed to shorten", "❌"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === CALC ===
    if cmd == "calc":
        if len(parts) < 2:
            return await event.edit(bold_emoji("Usage: .calc 2+2", "❌"))
        expr = " ".join(parts[1:])
        try:
            allowed = set("0123456789+-*/.()% ")
            if not all(c in allowed for c in expr):
                return await event.edit(bold_emoji("Only basic math allowed", "❌"))
            result = eval(expr)
            await event.edit(bold_emoji(f"{expr} = {result}", "🧮"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === FANCY ===
    if cmd == "fancy":
        if len(parts) < 2:
            return await event.edit(bold_emoji("Usage: .fancy <text>", "❌"))
        txt = " ".join(parts[1:])
        fancy = fancy_text(txt)
        await event.edit(f"**Fancy Text:**\n`{fancy}`\n\n**Normal:**\n{txt}")
        return

    # === EMOJI ===
    if cmd == "emoji":
        if len(parts) < 2:
            return await event.edit(bold_emoji("Usage: .emoji <text>", "❌"))
        txt = " ".join(parts[1:])
        result = emoji_text(txt)
        await event.edit(f"**Emoji Style:**\n{result}")
        return

    # === QRCODE ===
    if cmd == "qrcode":
        if len(parts) < 2:
            return await event.edit(bold_emoji("Usage: .qrcode <text>", "❌"))
        txt = " ".join(parts[1:])
        if not HAS_QR:
            return await event.edit(bold_emoji("QR module not installed!", "❌"))
        await event.edit(bold_emoji("Generating QR Code...", "📱"))
        try:
            qr = qrcode_mod.QRCode(box_size=10, border=4)
            qr.add_data(txt)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            qr_path = "qrcode_output.png"
            img.save(qr_path)
            await event.delete()
            await client.send_file(chat_id, qr_path, caption=bold_emoji("QR Code", "📱"))
            os.remove(qr_path)
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === TTS ===
    if cmd == "tts":
        if len(parts) < 2:
            return await event.edit(bold_emoji(f"Usage: {p}tts <text>", "❌"))
        txt_rest = " ".join(parts[1:])
        try:
            gTTS(txt_rest).save("tts.mp3")
            await event.delete()
            await client.send_file(chat_id, "tts.mp3", voice_note=True)
            if os.path.exists("tts.mp3"):
                os.remove("tts.mp3")
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === TXTSTK ===
    if cmd == "txtstk":
        if len(parts) < 2:
            return await event.edit(bold_emoji(f"Usage: {p}txtstk <text>", "❌"))
        txt_rest = " ".join(parts[1:])
        if len(txt_rest) > 200:
            return await event.edit(bold_emoji("Text too long!", "❌"))
        await event.edit(bold_emoji("Creating sticker...", "🎨"))
        try:
            spath = await text_to_sticker(txt_rest)
            await event.delete()
            await client.send_file(chat_id, spath)
            os.remove(spath)
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === MKSTK ===
    if cmd == "mkstk":
        if not event.is_reply:
            return await event.edit(bold_emoji("Reply to an image", "❌"))
        reply = await event.get_reply_message()
        if not reply or (not reply.photo and not reply.sticker):
            return await event.edit(bold_emoji("Reply to a photo/sticker", "❌"))
        await event.edit(bold_emoji("Converting...", "🔄"))
        try:
            img_path = await reply.download_media()
            if not img_path:
                return await event.edit(bold_emoji("Download failed", "❌"))
            img = Image.open(img_path)
            img = img.resize((512, 512), Image.LANCZOS)
            stk_path = "mkstk_output.webp"
            img.save(stk_path, "WEBP", quality=95)
            await event.delete()
            await client.send_file(chat_id, stk_path)
            os.remove(stk_path)
            os.remove(img_path)
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === SONG ===
    if cmd == "song":
        if len(parts) < 2:
            return await event.edit(bold_emoji(f"Usage: {p}song <name>", "❌"))
        query = " ".join(parts[1:])
        await event.edit(bold_emoji(f"📀 Searching: {query}...", "🎵"))
        try:
            res = requests.get(f"https://saavnapi-nine.vercel.app/result/?query={requests.utils.quote(query)}", timeout=15)
            data = res.json()
            if not data:
                return await event.edit(bold_emoji("Not found on Saavan", "❌"))
            song = data[0]
            song_name = song.get("song", query)[:60]
            singers = song.get("singers", "")
            album = song.get("album", "")
            raw_url = song.get("media_url", "")
            if not raw_url:
                return await event.edit(bold_emoji("No media_url found", "❌"))
            caption = bold_emoji(song_name, "🎵")
            if singers:
                caption += "\n" + bold_emoji(f"{singers}", "🎤")
            if album:
                caption += "\n" + bold_emoji(f"Album: {album}", "💿")
            actual_url = decrypt_saavn_url(raw_url)
            await event.edit(bold_emoji(f"⬇️ Downloading: {song_name}...", "📥"))
            safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in song_name)[:40]
            raw_path = f"song_{safe_name}_raw.mp3"
            dl_success = False
            for quality in ["", "/_320.mp4", "/_160.mp4", "/_96.mp4"]:
                try_url = actual_url
                if quality and not actual_url.endswith(".mp4") and not quality.startswith("/"):
                    try_url = actual_url + quality
                hdrs = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Referer': 'https://www.jiosaavn.com/'}
                try:
                    audio_res = requests.get(try_url, timeout=30, stream=True, headers=hdrs)
                    if audio_res.status_code == 200 and int(audio_res.headers.get('content-length', 10000)) > 2000:
                        with open(raw_path, "wb") as f:
                            for chunk in audio_res.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        if os.path.getsize(raw_path) > 5000:
                            dl_success = True
                            break
                except:
                    continue
            if not dl_success or not os.path.exists(raw_path) or os.path.getsize(raw_path) < 1000:
                if os.path.exists(raw_path):
                    os.remove(raw_path)
                return await event.edit(bold_emoji("Download failed - file too small", "❌"))
            final_path = f"song_{safe_name}_final.mp3"
            try:
                subprocess.run(["ffmpeg", "-y", "-i", raw_path, "-codec:a", "libmp3lame", "-b:a", "128k", "-id3v2_version", "3", "-f", "mp3", final_path], capture_output=True, timeout=30)
                if os.path.exists(final_path) and os.path.getsize(final_path) > 1000:
                    send_path = final_path
                else:
                    send_path = raw_path
            except:
                send_path = raw_path
            await event.delete()
            await client.send_file(event.chat_id, send_path, caption=caption,
                attributes=[types.DocumentAttributeAudio(duration=0, title=song_name, performer=singers or "Unknown")])
            for f in [raw_path, final_path]:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass
        except requests.exceptions.Timeout:
            await event.edit(bold_emoji("API timeout, try again", "⏱️"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:80]}", "❌"))
        return

    # === ADD ===
    if cmd == "add":
        if len(parts) < 2:
            return await event.edit(bold_emoji("Usage: .add username", "❌"))
        u = parts[1]
        try:
            ent = await client.get_entity(u)
            try:
                await client(InviteToChannelRequest(chat_id, [ent.id]))
            except:
                await client(AddChatUserRequest(chat_id, ent.id, fwd_limit=10))
            await event.edit(bold_emoji(f"Added: {u}", "✅"))
        except Exception as e:
            await event.edit(bold_emoji(str(e)[:80], "❌"))
        return

    # === ADDBOTS ===
    if cmd == "addbots":
        await event.edit(bold_emoji("Adding bots...", "🔄"))
        bots = ["@clnfucker_bot", "@clnfucker1_bot", "@clnfucker2_bot", "@clnfucker3_bot", "@clnfucker4_bot", "@clnfucker5_bot", "@clnfucker6_bot", "@clnfucker7_bot", "@clnfucker8_bot", "@clnfucker9_bot", "@clnfucker10_bot"]
        added = promoted = failed = 0
        for bot in bots:
            try:
                ent = await client.get_entity(bot)
                try:
                    await client(InviteToChannelRequest(chat_id, [ent.id]))
                except:
                    await client(AddChatUserRequest(chat_id, ent.id, fwd_limit=10))
                added += 1
                await asyncio.sleep(3)
                rights = ChatAdminRights(change_info=True, delete_messages=True, ban_users=True, invite_users=True, pin_messages=True, manage_call=True)
                await client(EditAdminRequest(chat_id, ent.id, rights))
                promoted += 1
                await asyncio.sleep(5)
            except:
                failed += 1
        txt = bold_emoji("BOTS DEPLOYED", "🤖") + "\n"
        txt += bold_emoji(f"Added: {added}", "✅") + "\n"
        txt += bold_emoji(f"Promoted: {promoted}", "⭐") + "\n"
        txt += bold_emoji(f"Failed: {failed}", "❌")
        await event.edit(txt)
        return

    # === CRTGC ===
    if cmd == "crtgc":
        if len(parts) < 2:
            return await event.edit(bold_emoji("Usage: .crtgc 5", "❌"))
        cnt = int(parts[1])
        await event.edit(bold_emoji("Creating groups...", "🔄"))
        for i in range(cnt):
            try:
                await client(CreateChannelRequest(title=f"Titan GC {i+1}", about=EMPTY_STR, megagroup=True))
            except Exception as e:
                await event.edit(bold_emoji(f"Error at {i+1}: {str(e)[:40]}", "❌"))
                return
            await asyncio.sleep(2)
        await event.edit(bold_emoji(f"Created {cnt} groups", "✅"))
        return

    # === PURGE ===
    if cmd == "purge":
        if not event.is_reply:
            return await event.edit(bold_emoji("Reply to a message", "❌"))
        reply = await event.get_reply_message()
        if not reply:
            return await event.edit(bold_emoji("Reply to a message", "❌"))
        cnt = 0
        async for msg in client.iter_messages(chat_id, offset_id=reply.id):
            try:
                if msg.id != event.id:
                    await msg.delete()
                    cnt += 1
            except:
                pass
        try:
            await reply.delete()
            cnt += 1
        except:
            pass
        await event.edit(bold_emoji(f"Purged {cnt} messages ✅", "🧹"))
        return

    # === PIN ===
    if cmd == "pin":
        if not event.is_reply:
            return await event.edit(bold_emoji("Reply to msg", "❌"))
        reply = await event.get_reply_message()
        if not reply:
            return await event.edit(bold_emoji("Reply to msg", "❌"))
        try:
            await client.pin_message(chat_id, reply.id, notify=False)
            await event.edit(bold_emoji("Pinned OK", "📌"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:40]}", "❌"))
        return

    # === INFO (Telegram UID → Phone Number) ===
    if cmd == "info":
        target_uid = None
        if event.is_reply:
            reply = await event.get_reply_message()
            if reply and reply.sender_id:
                target_uid = reply.sender_id
        if target_uid is None and len(parts) >= 2:
            arg = parts[1].strip()
            if arg.lstrip("-").isdigit():
                target_uid = int(arg)
        if target_uid is None and len(parts) >= 2:
            arg = parts[1].strip()
            try:
                if not arg.startswith("@"):
                    arg = "@" + arg
                entity = await client.get_entity(arg)
                target_uid = entity.id
            except Exception:
                return await event.edit(bold_emoji(f"Invalid username: {parts[1]}", "❌"))
        if target_uid is None:
            return await event.edit(bold_emoji(f"Usage: {p}info (reply) / {p}info <uid> / {p}info @username", "❌"))
        await event.edit(bold_emoji(f"🔍 Looking up {target_uid}...", "🔍"))
        try:
            resp = requests.get(
                f"https://r-bots862733number-api.co08.art/tg?key=R-BOTS82ns&q={target_uid}",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30
            )
            data = resp.json()
            phone = "N/A"
            if "location" in data and isinstance(data["location"], dict):
                for k in data["location"]:
                    if k.startswith("count"):
                        phone = k.replace("count", "")
                        if phone and len(phone) > 3:
                            phone = f"+{phone}"
                        break
            user_info = data.get("userid_info", {})
            if isinstance(user_info, list):
                user_info = user_info[0] if user_info else {}
            tg_id = str(user_info.get("telegram_id", target_uid))
            tg_uname = str(user_info.get("username", ""))
            if not tg_uname or tg_uname in ("N/A", "None", ""):
                try:
                    ent = await client.get_entity(target_uid)
                    tg_uname = ent.username or "N/A"
                except:
                    tg_uname = "N/A"
            sp = fancy_text(phone) if phone != "N/A" else "𝐍/𝐀"
            sid = fancy_text(tg_id)
            suname = fancy_text(tg_uname[:25] if tg_uname != "N/A" else "𝐍/𝐀")
            txt = "✧═════════════════════════════✧\n"
            txt += "       「 𝐌𝐀𝐃𝐄 𝐁𝐘 𝐓𝐈𝐓𝐀𝐍 𝐆𝐎𝐅 」\n"
            txt += "✧═════════════════════════════✧\n\n"
            txt += f"  📱 𝐂𝐨𝐮𝐧𝐭𝐫𝐲 𝐂𝐨𝐝𝐞 + 𝐍𝐮𝐦𝐛𝐞𝐫:\n     {sp}\n\n"
            txt += f"  🆔 𝐓𝐞𝐥𝐞𝐠𝐫𝐚𝐦 𝐈𝐃:\n     {sid}\n\n"
            txt += f"  👤 𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞:\n     @{suname}\n\n"
            txt += "✧═════════════════════════════✧\n"
            txt += "  📞 @TITANCONTACT\n  🤖 @g0zig\n"
            txt += "✧═════════════════════════════✧"
            await event.edit(txt)
        except Exception as e:
            await event.edit(bold_emoji(f"API Error: {str(e)[:120]}", "❌"))
        return

    # === INFO2 (Phone → Name/Address) ===
    if cmd == "info2":
        if len(parts) < 2:
            return await event.edit(bold_emoji(f"Usage: {p}info2 <phone>\nExample: {p}info2 8923773512", "❌"))
        mobilenumber = parts[1].replace("+","").replace(" ","").replace("-","").strip()
        if not mobilenumber.isdigit():
            return await event.edit(bold_emoji("Invalid phone number", "❌"))
        await event.edit(bold_emoji(f"🔍 Looking up {mobilenumber}...", "🔍"))
        try:
            resp = requests.get(
                f"https://r-bots923773512fo-api.co08.art/info?key=R-BOTS72EJ&num={mobilenumber}",
                headers={"User-Agent": "Mozilla/5.0"}, timeout=30
            )
            data = resp.json()
            records = data.get("data", [])
            found = data.get("found", 0)
            if not records or found == 0:
                return await event.edit(bold_emoji(f"No records for {mobilenumber}", "❌"))
            txt = "✧═════════════════════════════✧\n"
            txt += "       「 𝐌𝐀𝐃𝐄 𝐁𝐘 𝐓𝐈𝐓𝐀𝐍 𝐆𝐎𝐅 」\n"
            txt += "✧═════════════════════════════✧\n\n"
            txt += f"  📞 𝐍𝐮𝐦𝐛𝐞𝐫: {fancy_text(mobilenumber)}\n"
            txt += f"  📊 𝐑𝐞𝐜𝐨𝐫𝐝𝐬: {fancy_text(str(found))}\n\n─── 𝐃𝐄𝐓𝐀𝐈𝐋𝐒 ───\n\n"
            for i, rec in enumerate(records[:8], 1):
                name = str(rec.get("name", "N/A"))
                fname = str(rec.get("fname", "N/A"))
                email = str(rec.get("email", ""))
                uid_val = str(rec.get("id", "")) if rec.get("id") else ""
                addr = "N/A"
                for addr_key in ["dataname", "address", "location", "area"]:
                    v = rec.get(addr_key)
                    if v and str(v).strip() and str(v) != "null":
                        raw = str(v).replace("!", ", ").replace("null", "").strip().rstrip(",")
                        if raw and len(raw) > 3:
                            addr = raw
                            break
                txt += f"  📍 𝐑𝐞𝐜𝐨𝐫𝐝 #{fancy_text(str(i))}\n"
                txt += f"  👤 𝐍𝐚𝐦𝐞: {fancy_text(name[:50])}\n"
                if fname and fname not in ("None","N/A"):
                    txt += f"  👨 𝐅𝐚𝐭𝐡𝐞𝐫: {fancy_text(fname[:50])}\n"
                if email and email not in ("None","null"):
                    txt += f"  📧 𝐄𝐦𝐚𝐢𝐥: {email[:60]}\n"
                if addr and addr != "N/A":
                    txt += f"  🏠 𝐀𝐝𝐝𝐫𝐞𝐬𝐬: {fancy_text(addr[:70])}\n"
                if uid_val and uid_val != "None":
                    txt += f"  🆔 𝐈𝐃: {uid_val[:30]}\n"
                txt += "\n"
            txt += "✧═════════════════════════════✧\n📞 @TITANCONTACT\n🤖 @g0zig\n✧═════════════════════════════✧"
            if len(txt) > 4000:
                txt = txt[:3800] + "\n\n✧ ... (truncated) ... ✧\n\n📞 @TITANCONTACT\n🤖 @g0zig\n✧═══════✧"
            await event.edit(txt)
        except Exception as e:
            await event.edit(bold_emoji(f"API Error: {str(e)[:120]}", "❌"))
        return

    # === COPY ===
    if cmd == "copy":
        if not event.is_reply:
            return await event.edit(bold_emoji("Reply to user", "❌"))
        reply = await event.get_reply_message()
        if not reply:
            return await event.edit(bold_emoji("Reply to user", "❌"))
        try:
            try:
                me_obj = await client.get_me()
                full_me = await client(GetFullUserRequest("me"))
                original_profile["first_name"] = me_obj.first_name or ""
                original_profile["last_name"] = me_obj.last_name or ""
                original_profile["bio"] = getattr(full_me.full_user, "about", "") or ""
            except:
                original_profile["first_name"] = original_profile["last_name"] = original_profile["bio"] = ""
            if original_pfp is None:
                try:
                    photos = await client.get_profile_photos("me")
                    if photos:
                        original_pfp = await client.download_media(photos[0])
                except:
                    original_pfp = None
            target = await client.get_entity(reply.sender_id)
            nf = target.first_name or ""
            nl = target.last_name or ""
            await client(functions.account.UpdateProfileRequest(first_name=nf, last_name=nl))
            try:
                ft = await client(GetFullUserRequest(reply.sender_id))
                tb = getattr(ft.full_user, "about", "") or ""
            except:
                tb = ""
            await client(functions.account.UpdateProfileRequest(about=tb))
            from telethon.tl.functions.photos import DeletePhotosRequest as DelPhotosReq
            old_photos = await client.get_profile_photos("me")
            if old_photos:
                await client(DelPhotosReq(id=old_photos))
            tgt_photos = await client.get_profile_photos(reply.sender_id, limit=1)
            if tgt_photos:
                f = await client.download_media(tgt_photos[0])
                if f:
                    uploaded = await client.upload_file(f)
                    await client(functions.photos.UploadProfilePhotoRequest(file=uploaded))
                    if os.path.exists(f):
                        os.remove(f)
            await event.edit(bold_emoji("Profile Copied OK", "📸"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:100]}", "❌"))
        return

    # === REVERT ===
    if cmd == "revert":
        if not original_profile:
            return await event.edit(bold_emoji("No backup found", "❌"))
        try:
            fn = original_profile.get("first_name", EMPTY_STR)
            ln = original_profile.get("last_name", EMPTY_STR)
            bio = original_profile.get("bio", EMPTY_STR)
            await client(functions.account.UpdateProfileRequest(first_name=fn, last_name=ln, about=bio))
            from telethon.tl.functions.photos import DeletePhotosRequest as DelPhotosReq
            old_photos = await client.get_profile_photos("me")
            if old_photos:
                await client(DelPhotosReq(id=old_photos))
            if original_pfp and os.path.exists(original_pfp):
                uploaded = await client.upload_file(original_pfp)
                await client(functions.photos.UploadProfilePhotoRequest(file=uploaded))
            await event.edit(bold_emoji("Profile Restored OK", "🔄"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === KILLALL ===
    if cmd == "killall":
        if c_key in titan_targets:
            titan_targets[c_key].clear()
        if c_key in titan_indices:
            titan_indices[c_key].clear()
        if c_key in titanl_workers:
            for k in list(titanl_workers[c_key].keys()):
                titanl_workers[c_key][k]["active"] = False
            titanl_workers[c_key].clear()
        if c_key in titanl_indices:
            titanl_indices[c_key].clear()
        if c_key in titanr_workers:
            for k in list(titanr_workers[c_key].keys()):
                titanr_workers[c_key][k]["active"] = False
            titanr_workers[c_key].clear()
        if c_key in titanlr_workers:
            for k in list(titanlr_workers[c_key].keys()):
                titanlr_workers[c_key][k]["active"] = False
            titanlr_workers[c_key].clear()
        if c_key in processed_trigger_msgs:
            processed_trigger_msgs[c_key].clear()
        await event.edit(bold_emoji("All attacks stopped for this account", "🛑"))
        return

    # === TITAN1-7 ===
    if cmd.startswith("titan") and not any(cmd.startswith(x) for x in ("titanr","titanl","titanlr")):
        try:
            num = int(cmd.replace("titan", ""))
        except:
            return
        if num < 1 or num > 7:
            return
        if not event.is_reply:
            return await event.edit(bold_emoji(f"Reply to user for titan{num}", "❌"))
        reply = await event.get_reply_message()
        if not reply:
            return await event.edit(bold_emoji("Reply to user", "❌"))
        uid = reply.sender_id
        titan_targets[c_key][(chat_id, uid)] = num
        titan_indices[c_key][(chat_id, uid, num)] = 0
        await event.edit(bold_emoji(f"Titan{num}", "⚔️") + "\n" + bold_emoji(f"User: {uid}", "👤") + "\n" + bold_emoji("Status: ACTIVE", "🟢"))
        return

    # === STOPTITAN1-7 ===
    if cmd.startswith("stoptitan") and not any(cmd.startswith(x) for x in ("stoptitanr","stoptitanl","stoptitanlr")):
        try:
            num = int(cmd.replace("stoptitan", ""))
        except:
            return
        if num < 1 or num > 7:
            return
        if not event.is_reply:
            return await event.edit(bold_emoji("Reply to user", "❌"))
        reply = await event.get_reply_message()
        if not reply:
            return await event.edit(bold_emoji("Reply to user", "❌"))
        key = (chat_id, reply.sender_id)
        if key in titan_targets.get(c_key, {}):
            del titan_targets[c_key][key]
            for k in list(titan_indices.get(c_key, {}).keys()):
                if k[0] == chat_id and k[1] == reply.sender_id:
                    del titan_indices[c_key][k]
            await event.edit(bold_emoji(f"Titan{num}: OFF", "🔴"))
        else:
            await event.edit(bold_emoji(f"Titan{num}: Already OFF", "ℹ️"))
        return

    # === TITANL1-5 ===
    if cmd.startswith("titanl") and not cmd.startswith("titanlr"):
        try:
            num = int(cmd.replace("titanl", ""))
        except:
            return
        if num < 1 or num > 5:
            return
        if not event.is_reply:
            return await event.edit(bold_emoji("Reply to user", "❌"))
        reply = await event.get_reply_message()
        if not reply:
            return await event.edit(bold_emoji("Reply to user", "❌"))
        uid = reply.sender_id
        key = (chat_id, uid)
        if key in titanl_workers.get(c_key, {}) and titanl_workers[c_key][key].get("active", False):
            titanl_workers[c_key][key]["active"] = False
            await asyncio.sleep(0.5)
        titanl_workers[c_key][key] = {"active": True, "num": num}
        titanl_indices[c_key][key] = 0
        await event.edit(bold_emoji(f"TitanL{num}", "⚔️") + "\n" + bold_emoji("Status: ACTIVE", "🟢"))
        return

    if cmd.startswith("stoptitanl") and not cmd.startswith("stoptitanlr"):
        try:
            num = int(cmd.replace("stoptitanl", ""))
        except:
            return
        if num < 1 or num > 5:
            return
        if not event.is_reply:
            return await event.edit(bold_emoji("Reply to user", "❌"))
        reply = await event.get_reply_message()
        if not reply:
            return await event.edit(bold_emoji("Reply to user", "❌"))
        key = (chat_id, reply.sender_id)
        if key in titanl_workers.get(c_key, {}) and titanl_workers[c_key][key].get("active", False):
            titanl_workers[c_key][key]["active"] = False
            titanl_workers[c_key].pop(key, None)
            titanl_indices[c_key].pop(key, None)
            await event.edit(bold_emoji(f"TitanL{num}: OFF", "🔴"))
        else:
            await event.edit(bold_emoji(f"TitanL{num}: Already OFF", "ℹ️"))
        return

    # === TITANR1-7 ===
    if cmd.startswith("titanr"):
        try:
            num = int(cmd.replace("titanr", ""))
        except:
            return
        if num < 1 or num > 7:
            return
        if not event.is_reply:
            return await event.edit(bold_emoji("Reply to user", "❌"))
        reply = await event.get_reply_message()
        if not reply:
            return await event.edit(bold_emoji("Reply to user", "❌"))
        uid = reply.sender_id
        tmid = reply.id
        key = (chat_id, uid)
        if c_key not in titanr_workers:
            titanr_workers[c_key] = {}
        if key in titanr_workers[c_key]:
            titanr_workers[c_key][key]["active"] = False
            await asyncio.sleep(0.5)
        texts = TITAN_TEXTS[num - 1]
        sn = f"titanr{num}"
        titanr_workers[c_key][key] = {"msg_id": tmid, "active": True,
            "task": asyncio.create_task(continuous_reply_worker(client, chat_id, tmid, texts, sn, titanr_workers[c_key], key))}
        await event.edit(bold_emoji(f"TitanR{num}", "⚔️") + "\n" + bold_emoji("Continuous: ON", "🟢"))
        return

    if cmd == "stoptitanr":
        cnt = 0
        if c_key in titanr_workers:
            for k in list(titanr_workers[c_key].keys()):
                titanr_workers[c_key][k]["active"] = False
                cnt += 1
            titanr_workers[c_key].clear()
        await event.edit(bold_emoji(f"Stopped {cnt} TitanR tasks", "🔴"))
        return

    # === TITANLR1-5 ===
    if cmd.startswith("titanlr"):
        try:
            num = int(cmd.replace("titanlr", ""))
        except:
            return
        if num < 1 or num > 5:
            return
        if not event.is_reply:
            return await event.edit(bold_emoji("Reply to user", "❌"))
        reply = await event.get_reply_message()
        if not reply:
            return await event.edit(bold_emoji("Reply to user", "❌"))
        uid = reply.sender_id
        tmid = reply.id
        key = (chat_id, uid)
        if c_key not in titanlr_workers:
            titanlr_workers[c_key] = {}
        if key in titanlr_workers[c_key]:
            titanlr_workers[c_key][key]["active"] = False
            await asyncio.sleep(0.5)
        texts = TITANL_TEXTS[num - 1]
        sn = f"titanlr{num}"
        titanlr_workers[c_key][key] = {"msg_id": tmid, "active": True,
            "task": asyncio.create_task(continuous_reply_worker(client, chat_id, tmid, texts, sn, titanlr_workers[c_key], key))}
        await event.edit(bold_emoji(f"TitanLR{num}", "⚔️") + "\n" + bold_emoji("Continuous: ON", "🟢"))
        return

    if cmd == "stoptitanlr":
        cnt = 0
        if c_key in titanlr_workers:
            for k in list(titanlr_workers[c_key].keys()):
                titanlr_workers[c_key][k]["active"] = False
                cnt += 1
            titanlr_workers[c_key].clear()
        await event.edit(bold_emoji(f"Stopped {cnt} TitanLR tasks", "🔴"))
        return

    # === PAIR (OWNER ONLY) ===
    if cmd == "pair":
        if not is_owner:
            return await event.edit(bold_emoji("Only owner can pair", "🔒"))
        try:
            phone = parts[1]
            if not phone.startswith("+"):
                phone = "+" + phone
        except:
            return await event.edit(bold_emoji(f"Usage: {p}pair +91xxxxxxxxx", "❌"))
        await event.edit(bold_emoji(f"Connecting to {phone}...", "📞"))
        try:
            session_name = f"titan_pair_{phone.replace('+', '')}"
            new_client = TelegramClient(session_name, api_id, api_hash)
            await new_client.connect()
            if await new_client.is_user_authorized():
                me_obj = await new_client.get_me()
                paired_uid = me_obj.id
                SELF_UIDS[id(new_client)] = paired_uid
                new_client.add_event_handler(auto_handler)
                paired_clients.append(new_client)
                await event.edit(bold_emoji(f"Session loaded! UID: {paired_uid}", "✅"))
                return
            # FIX: Store phone_code_hash properly
            result = await new_client.send_code_request(phone)
            pair_states[chat_id] = {
                "phone": phone,
                "client": new_client,
                "session_name": session_name,
                "phone_code_hash": result.phone_code_hash  # FIXED: store hash
            }
            await event.edit(bold_emoji(f"OTP sent! Use {p}c <code>", "📱"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === C (verify OTP) (OWNER ONLY) ===
    if cmd == "c":
        if not is_owner:
            return await event.edit(bold_emoji("Only owner can use this", "🔒"))
        if chat_id not in pair_states:
            return await event.edit(bold_emoji(f"Use {p}pair first", "❌"))
        state = pair_states[chat_id]
        if len(parts) < 2:
            return await event.edit(bold_emoji(f"Usage: {p}c 12345", "❌"))
        otp = parts[1]
        await event.edit(bold_emoji("Verifying OTP...", "🔄"))
        try:
            # FIX: Use phone_code_hash from stored state
            await state["client"].sign_in(
                phone=state["phone"],
                code=otp,
                phone_code_hash=state.get("phone_code_hash")  # FIXED: pass hash
            )
            new_client = state["client"]
            me_obj = await new_client.get_me()
            paired_uid = me_obj.id
            SELF_UIDS[id(new_client)] = paired_uid
            new_client.add_event_handler(auto_handler)
            paired_clients.append(new_client)
            pair_states.pop(chat_id, None)
            await event.edit(bold_emoji(f"Paired! UID: {paired_uid}", "✅"))
        except SessionPasswordNeededError:
            pair_states[chat_id]["need_password"] = True
            await event.edit(bold_emoji(f"2FA required! Use {p}p <password>", "🔑"))
        except PhoneCodeExpiredError:
            await event.edit(bold_emoji("Code expired! Use .pair again", "❌"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return

    # === P (2FA password) (OWNER ONLY) ===
    if cmd == "p":
        if not is_owner:
            return await event.edit(bold_emoji("Only owner can use this", "🔒"))
        if chat_id not in pair_states:
            return await event.edit(bold_emoji(f"Use {p}pair first", "❌"))
        state = pair_states[chat_id]
        if not state.get("need_password"):
            return await event.edit(bold_emoji("OTP step first", "❌"))
        if len(parts) < 2:
            return await event.edit(bold_emoji(f"Usage: {p}p password", "❌"))
        password = parts[1]
        await event.edit(bold_emoji("Logging in with 2FA...", "🔄"))
        try:
            await state["client"].sign_in(password=password)
            new_client = state["client"]
            me_obj = await new_client.get_me()
            paired_uid = me_obj.id
            SELF_UIDS[id(new_client)] = paired_uid
            new_client.add_event_handler(auto_handler)
            paired_clients.append(new_client)
            pair_states.pop(chat_id, None)
            await event.edit(bold_emoji(f"2FA Login! UID: {paired_uid}", "✅"))
        except Exception as e:
            await event.edit(bold_emoji(f"Error: {str(e)[:60]}", "❌"))
        return


async def start_paired_client(session_name):
    c = TelegramClient(session_name, api_id, api_hash)
    try:
        await c.connect()
        if not await c.is_user_authorized():
            print(f"⚡ {session_name}: Session expired, skipping")
            await c.disconnect()
            return None
        me = await c.get_me()
        SELF_UIDS[id(c)] = me.id
        c.add_event_handler(auto_handler)
        print(f"✅ Paired: UID={me.id} | Name={me.first_name}")
        return c
    except Exception as e:
        print(f"❌ {session_name}: {str(e)[:60]}")
        try:
            await c.disconnect()
        except:
            pass
        return None


async def main():
    global paired_clients
    print("⚡" * 20)
    print("TITAN BOT v4 [FIXED - MUTE/GMUTE/PAIR/EXPIRED]")
    print("⚡" * 20)
    print("✅ FIX 1: Commands only process by sender's account")
    print("✅ FIX 2: All attack state per-client isolated")
    print("✅ FIX 3: phone_code_hash stored (no more 'expired' error)")
    print("✅ FIX 4: mute/unmute on REPLY + @MENTION + UID")
    print("✅ FIX 5: gmute/gunmute deletes ALL messages globally")
    print("✅ FIX 6: an = announcement, mutelist = show muted")
    print("✅ FIX 7: All commands available to paired users (except pair/c/p)")
    if not HAS_CRYPTO:
        print("⚠️  pip install pycryptodome for Saavn")
    if not HAS_QR:
        print("⚠️  pip install qrcode[pil] for QR")

    await app.connect()
    if not await app.is_user_authorized():
        print("❌ Main session expired.")
        phone = input("Phone (with country code): ")
        await app.send_code_request(phone)
        code = input("OTP: ")
        try:
            await app.sign_in(phone, code)
        except SessionPasswordNeededError:
            pw = input("2FA Password: ")
            await app.sign_in(password=pw)
    else:
        print("✅ Main client authorized")

    me = await app.get_me()
    SELF_UIDS[id(app)] = me.id
    print(f"✅ Logged in: UID={me.id} (@{me.username or 'N/A'})")
    app.add_event_handler(auto_handler)

    # Load saved paired sessions
    pair_files = [f for f in os.listdir(".") if f.startswith("titan_pair_") and f.endswith(".session")]
    print(f"🔍 Found {len(pair_files)} paired session(s)")
    for sf in pair_files:
        sname = sf.replace(".session", "")
        pc = await start_paired_client(sname)
        if pc:
            paired_clients.append(pc)
        await asyncio.sleep(1)

    print("✅ TITAN BOT v4 (FIXED) is running!")
    print("⚡" * 20)
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        for ck in list(titanr_workers.keys()):
            for k in list(titanr_workers[ck].keys()):
                titanr_workers[ck][k]["active"] = False
        for ck in list(titanl_workers.keys()):
            for k in list(titanl_workers[ck].keys()):
                titanl_workers[ck][k]["active"] = False
        for ck in list(titanlr_workers.keys()):
            for k in list(titanlr_workers[ck].keys()):
                titanlr_workers[ck][k]["active"] = False
        for c in paired_clients:
            try:
                c.disconnect()
            except:
                pass
        try:
            app.disconnect()
        except:
            pass
        print("\n👋 Bot stopped.")
