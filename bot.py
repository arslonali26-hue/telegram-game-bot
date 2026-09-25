import json
import os
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN", "").strip()
USERS_FILE = Path("users.json")
CLANS_FILE = Path("clans.json")
DATA_LOCK = threading.RLock()


def read_json(path):
    with DATA_LOCK:
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}


def write_json(path, data):
    with DATA_LOCK:
        temp = str(path) + ".tmp"
        with open(temp, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(temp, path)


def blank_user():
    return {
        "money": 500,
        "diamonds": 0,
        "hp": 100,
        "max_hp": 100,
        "clan": None,
        "first_name": "",
        "username": "",
    }


def get_user(uid):
    users = read_json(USERS_FILE)
    key = str(uid)
    user = users.get(key)
    if not isinstance(user, dict):
        user = blank_user()
    user.setdefault("money", 500)
    user.setdefault("diamonds", 0)
    user.setdefault("hp", 100)
    user.setdefault("max_hp", 100)
    user.setdefault("clan", None)
    user.setdefault("first_name", "")
    user.setdefault("username", "")
    users[key] = user
    write_json(USERS_FILE, users)
    return user


def save_user(uid, user):
    users = read_json(USERS_FILE)
    users[str(uid)] = user
    write_json(USERS_FILE, users)


def menu():
    return ReplyKeyboardMarkup(
        [["👤 Profil", "👥 Clan"], ["📋 Clanlar"]],
        resize_keyboard=True,
    )


def back():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Menyu", callback_data="main")]
    ])


async def show(update, text, markup=None):
    if update.callback_query:
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass
        try:
            await query.edit_message_text(text, reply_markup=markup)
        except Exception:
            await query.message.reply_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    person = update.effective_user
    user = get_user(person.id)
    user["first_name"] = person.first_name or ""
    user["username"] = person.username or ""
    save_user(person.id, user)
    await show(
        update,
        f"Salom, {person.first_name}! 🎮\n\n"
        f"💰 Pul: {user['money']:,}\n"
        f"💎 Almas: {user['diamonds']}\n"
        f"❤️ HP: {user['hp']}/{user['max_hp']}\n"
        f"👥 Clan: {user.get('clan') or 'yo‘q'}",
        menu(),
    )


async def profile(update, context):
    uid = update.effective_user.id
    user = get_user(uid)
    clan_name = user.get("clan") or "yo‘q"
    await show(
        update,
        f"👤 PROFIL\n\n"
        f"🆔 ID: {uid}\n"
        f"💰 Pul: {user['money']:,}\n"
        f"💎 Almas: {user['diamonds']}\n"
        f"❤️ HP: {user['hp']}/{user['max_hp']}\n"
        f"👥 Clan: {clan_name}",
        back(),
    )


async def clan(update, context):
    uid = update.effective_user.id
    user = get_user(uid)
    if not user.get("clan"):
        await show(
            update,
            "👥 Siz clan a’zosi emassiz.\n\n"
            "/createclan ClanNomi — clan yaratish\n"
            "/joinclan ClanNomi — clan qo‘shilish\n"
            "/leaveclan — clandan chiqish",
            back(),
        )
        return

    clans = read_json(CLANS_FILE)
    clan_name = user["clan"]
    clan_data = clans.get(clan_name)
    if not clan_data:
        user["clan"] = None
        save_user(uid, user)
        await show(update, "⚠️ Clan ma’lumotlari topilmadi. Siz clandan chiqarildingiz.", back())
        return

    members = []
    for member_id in clan_data.get("members", []):
        member_data = get_user(int(member_id))
        name = member_data.get("first_name") or member_data.get("username") or member_id
        role = "👑 Rahbar" if member_id == clan_data.get("leader") else "👤 A’zo"
        members.append(f"{role} {name}")

    if not members:
        members = ["👤 Clan a'zolari yo‘q"]

    info = (
        f"🏰 CLAN: {clan_name}\n\n"
        f"👑 Rahbar: {clan_data.get('leader', '-')}\n"
        f"👥 A'zolar: {len(clan_data.get('members', []))}\n"
        f"💰 Bank: {clan_data.get('bank', 0):,}\n"
        f"⭐ Level: {clan_data.get('level', 1)}\n"
        f"⭐ XP: {clan_data.get('xp', 0)}/100\n\n"
        f"📋 A'zolar:\n" + "\n".join(members)
    )
    await show(update, info, back())


async def create_clan(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /createclan ClanNomi")
        return

    uid = update.effective_user.id
    user = get_user(uid)
    if user.get("clan"):
        await update.message.reply_text("Siz allaqachon clandasiz.")
        return

    name = " ".join(context.args).strip()
    if not name:
        await update.message.reply_text("Clan nomi bo‘sh bo‘lishi mumkin emas.")
        return

    clans = read_json(CLANS_FILE)
    if name in clans:
        await update.message.reply_text("Bu clan allaqachon mavjud.")
        return

    clan = {
        "name": name,
        "leader": str(uid),
        "members": [str(uid)],
        "bank": 0,
        "level": 1,
        "xp": 0,
        "description": "",
        "logs": [f"{datetime.now().isoformat()} | {name} clani yaratildi."],
    }
    clans[name] = clan
    write_json(CLANS_FILE, clans)

    user["clan"] = name
    save_user(uid, user)
    await update.message.reply_text(f"✅ {name} clani yaratildi. Siz rahbar bo‘ldingiz.", reply_markup=menu())


async def join_clan(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /joinclan ClanNomi")
        return

    uid = update.effective_user.id
    user = get_user(uid)
    if user.get("clan"):
        await update.message.reply_text("Avval joriy clandan chiqib oling.")
        return

    clan_name = " ".join(context.args).strip()
    clans = read_json(CLANS_FILE)
    clan = clans.get(clan_name)
    if not clan:
        await update.message.reply_text("Bunday clan topilmadi.")
        return

    members = clan.setdefault("members", [])
    if str(uid) not in members:
        members.append(str(uid))
        clan.setdefault("logs", []).append(f"{datetime.now().isoformat()} | {uid} clanga qo‘shildi.")
        write_json(CLANS_FILE, clans)

    user["clan"] = clan_name
    save_user(uid, user)
    await update.message.reply_text(f"✅ {clan_name} claniga qo‘shildingiz.", reply_markup=menu())


async def leave_clan(update, context):
    uid = update.effective_user.id
    user = get_user(uid)
    clan_name = user.get("clan")
    if not clan_name:
        await update.message.reply_text("Siz hozirda clanda emassiz.")
        return

    clans = read_json(CLANS_FILE)
    clan = clans.get(clan_name)
    if not clan:
        user["clan"] = None
        save_user(uid, user)
        await update.message.reply_text("Clan ma’lumotlari topilmadi. Sizdan clan olib tashlandi.")
        return

    members = clan.get("members", [])
    clan["members"] = [member for member in members if member != str(uid)]
    clan.setdefault("logs", []).append(f"{datetime.now().isoformat()} | {uid} clandan chiqdi.")

    if str(uid) == clan.get("leader") and clan.get("members"):
        clan["leader"] = clan["members"][0]

    if not clan.get("members"):
        clans.pop(clan_name, None)
    else:
        clans[clan_name] = clan

    write_json(CLANS_FILE, clans)
    user["clan"] = None
    save_user(uid, user)
    await update.message.reply_text("✅ Clandan chiqdingiz.", reply_markup=menu())


async def clans_list(update, context):
    clans = read_json(CLANS_FILE)
    if not clans:
        await show(update, "🧭 Hozircha hech qanday clan yo‘q.", back())
        return

    lines = ["🏰 CLANLAR RO‘YXATI\n"]
    for name, clan in sorted(clans.items(), key=lambda item: item[1].get("level", 1), reverse=True):
        lines.append(
            f"• {name} | 👥 {len(clan.get('members', []))} | 👑 {clan.get('leader', '-')} | "
            f"💰 {clan.get('bank', 0):,} | ⭐ L{clan.get('level', 1)}"
        )

    await show(update, "\n".join(lines), back())


async def callback(update, context):
    data = update.callback_query.data
    if data == "main":
        await start(update, context)
    else:
        await update.callback_query.answer()


async def text_handler(update, context):
    text = update.message.text
    if text == "👤 Profil":
        await profile(update, context)
        return
    if text == "👥 Clan":
        await clan(update, context)
        return
    if text == "📋 Clanlar":
        await clans_list(update, context)
        return
    await update.message.reply_text("Menyudan tanlang.", reply_markup=menu())


web = Flask(__name__)


@web.get("/")
def home():
    return "Telegram bot is running", 200


@web.get("/health")
def health():
    return "ok", 200


def run_web():
    web.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")), use_reloader=False)


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable topilmadi")

    threading.Thread(target=run_web, daemon=True).start()

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("createclan", create_clan))
    application.add_handler(CommandHandler("joinclan", join_clan))
    application.add_handler(CommandHandler("leaveclan", leave_clan))
    application.add_handler(CommandHandler("clans", clans_list))
    application.add_handler(CommandHandler("clan", clan))
    application.add_handler(CallbackQueryHandler(callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
