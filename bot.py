import json
import os
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

TOKEN = os.getenv("BOT_TOKEN", "").strip()
USERS_FILE = Path("users.json")
CLANS_FILE = Path("clans.json")
LOCK = threading.RLock()


def read(path):
    with LOCK:
        try:
            with open(path, encoding="utf-8") as f:
                value = json.load(f)
                return value if isinstance(value, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}


def write(path, data):
    with LOCK:
        tmp = str(path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def default_user():
    return {"money": 500, "diamonds": 0, "hp": 100, "max_hp": 100, "clan": None, "first_name": "", "username": ""}


def get_user(uid):
    users = read(USERS_FILE)
    user = users.get(str(uid), default_user())
    for key, value in default_user().items():
        user.setdefault(key, value)
    users[str(uid)] = user
    write(USERS_FILE, users)
    return user


def save_user(uid, user):
    users = read(USERS_FILE)
    users[str(uid)] = user
    write(USERS_FILE, users)


def menu():
    return ReplyKeyboardMarkup([["👤 Profil", "👥 Clan"], ["📋 Clanlar"]], resize_keyboard=True)


def back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="main")]])


def command_back():
    return back()


async def show(update, text, markup=None):
    markup = markup or back()
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


def clans_with_defaults():
    clans = read(CLANS_FILE)
    for name, clan in clans.items():
        if not isinstance(clan, dict):
            clans[name] = {}
            clan = clans[name]
        defaults = {"name": name, "leader": "", "members": [], "pending": [], "helpers": [], "bank": 0, "level": 1, "xp": 0, "description": "", "logs": []}
        for key, value in defaults.items():
            clan.setdefault(key, value)
    write(CLANS_FILE, clans)
    return clans


def clan_for(name):
    if not name:
        return None
    return clans_with_defaults().get(name)


def leader_clan(uid):
    user = get_user(uid)
    name = user.get("clan")
    clan = clan_for(name)
    return name, clan if clan and clan.get("leader") == str(uid) else None


def reply_text(update, text):
    return update.message.reply_text(text, reply_markup=command_back())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    person = update.effective_user
    user = get_user(person.id)
    user.update(first_name=person.first_name or "", username=person.username or "")
    save_user(person.id, user)
    await update.message.reply_text(
        f"Salom, {person.first_name}! 🎮\n\n💰 Pul: {user['money']:,}\n💎 Almas: {user['diamonds']}\n"
        f"❤️ HP: {user['hp']}/{user['max_hp']}\n👥 Clan: {user.get('clan') or 'yo‘q'}",
        reply_markup=menu(),
    )


async def profile(update, context):
    uid = update.effective_user.id
    user = get_user(uid)
    await show(update, f"👤 PROFIL\n\n🆔 ID: {uid}\n💰 Pul: {user['money']:,}\n💎 Almas: {user['diamonds']}\n❤️ HP: {user['hp']}/{user['max_hp']}\n👥 Clan: {user.get('clan') or 'yo‘q'}")


async def clan(update, context):
    uid = update.effective_user.id
    user = get_user(uid)
    name = user.get("clan")
    if not name:
        await show(update, "👥 Siz clan a’zosi emassiz.\n\n/createclan ClanNomi\n/joinclan ClanNomi\n/requestclan ClanNomi")
        return
    data = clan_for(name)
    if not data:
        user["clan"] = None
        save_user(uid, user)
        await show(update, "⚠️ Clan topilmadi.")
        return
    members = []
    for member in data["members"]:
        member_user = get_user(int(member))
        display = member_user.get("first_name") or member_user.get("username") or member
        role = "👑 Rahbar" if member == data["leader"] else ("🛠 Yordamchi" if member in data["helpers"] else "👤 A’zo")
        members.append(f"{role} {display}")
    await show(update, f"🏰 CLAN: {name}\n\n👑 Rahbar: {data['leader']}\n👥 A’zolar: {len(data['members'])}\n💰 Bank: {data['bank']:,}\n⭐ Level: {data['level']}\n⭐ XP: {data['xp']}/100\n🧩 Yordamchilar: {len(data['helpers'])}\n⏳ So‘rovlar: {len(data['pending'])}\n\n📋 A’zolar:\n" + ("\n".join(members) or "yo‘q"))


async def create_clan(update, context):
    if not context.args:
        await reply_text(update, "Foydalanish: /createclan ClanNomi")
        return
    uid = update.effective_user.id
    user = get_user(uid)
    name = " ".join(context.args).strip()[:32]
    clans = clans_with_defaults()
    if user.get("clan"):
        await reply_text(update, "Siz allaqachon clandasiz.")
        return
    if not name or name in clans:
        await reply_text(update, "Clan nomi bo‘sh yoki mavjud.")
        return
    clans[name] = {"name": name, "leader": str(uid), "members": [str(uid)], "pending": [], "helpers": [], "bank": 0, "level": 1, "xp": 0, "description": "", "logs": [f"{datetime.now().isoformat()} | clan yaratildi"]}
    write(CLANS_FILE, clans)
    user["clan"] = name
    save_user(uid, user)
    await update.message.reply_text(f"✅ {name} clani yaratildi.", reply_markup=menu())


async def join_clan(update, context):
    if not context.args:
        await reply_text(update, "Foydalanish: /joinclan ClanNomi")
        return
    uid = update.effective_user.id
    user = get_user(uid)
    name = " ".join(context.args).strip()
    clans = clans_with_defaults()
    clan_data = clans.get(name)
    if user.get("clan"):
        await reply_text(update, "Avval hozirgi clandan chiqing.")
        return
    if not clan_data:
        await reply_text(update, "Bunday clan topilmadi.")
        return
    if str(uid) not in clan_data["members"]:
        clan_data["members"].append(str(uid))
        write(CLANS_FILE, clans)
    user["clan"] = name
    save_user(uid, user)
    await update.message.reply_text(f"✅ {name} claniga qo‘shildingiz.", reply_markup=menu())


async def leave_clan(update, context):
    uid = update.effective_user.id
    user = get_user(uid)
    name = user.get("clan")
    clans = clans_with_defaults()
    clan_data = clans.get(name) if name else None
    if not clan_data:
        await reply_text(update, "Siz clanda emassiz.")
        return
    clan_data["members"] = [member for member in clan_data["members"] if member != str(uid)]
    clan_data["helpers"] = [member for member in clan_data["helpers"] if member != str(uid)]
    if clan_data["leader"] == str(uid) and clan_data["members"]:
        clan_data["leader"] = clan_data["members"][0]
    if clan_data["members"]:
        clans[name] = clan_data
    else:
        clans.pop(name, None)
    write(CLANS_FILE, clans)
    user["clan"] = None
    save_user(uid, user)
    await reply_text(update, "✅ Clandan chiqdingiz.")


async def clans_list(update, context):
    clans = clans_with_defaults()
    if not clans:
        await show(update, "🧭 Hozircha clan yo‘q.")
        return
    lines = ["🏰 CLANLAR\n"]
    for name, data in sorted(clans.items(), key=lambda item: item[1].get("level", 1), reverse=True):
        lines.append(f"• {name} | 👥 {len(data['members'])} | 💰 {data['bank']:,} | ⭐ L{data['level']} XP {data['xp']}/100")
    await show(update, "\n".join(lines))


async def request_clan(update, context):
    if not context.args:
        await reply_text(update, "Foydalanish: /requestclan ClanNomi")
        return
    uid = update.effective_user.id
    user = get_user(uid)
    if user.get("clan"):
        await reply_text(update, "Avval hozirgi clandan chiqing.")
        return
    name = " ".join(context.args).strip()
    clans = clans_with_defaults()
    clan_data = clans.get(name)
    if not clan_data:
        await reply_text(update, "Bunday clan topilmadi.")
        return
    if not any(str(item.get("user")) == str(uid) for item in clan_data["pending"] if isinstance(item, dict)):
        clan_data["pending"].append({"user": str(uid), "time": datetime.now().isoformat()})
        write(CLANS_FILE, clans)
        await reply_text(update, f"✅ {name} claniga so‘rov yuborildi.")
    else:
        await reply_text(update, "So‘rov allaqachon yuborilgan.")


async def accept_clan(update, context):
    if not context.args:
        await reply_text(update, "Foydalanish: /acceptclan USER_ID")
        return
    name, clan_data = leader_clan(update.effective_user.id)
    if not clan_data:
        await reply_text(update, "Faqat clan rahbari qabul qila oladi.")
        return
    try:
        target = str(int(context.args[0]))
    except ValueError:
        await reply_text(update, "USER_ID son bo‘lishi kerak.")
        return
    clans = clans_with_defaults()
    clan_data["pending"] = [item for item in clan_data["pending"] if str(item.get("user")) != target]
    if target not in clan_data["members"]:
        clan_data["members"].append(target)
    write(CLANS_FILE, clans)
    target_user = get_user(int(target))
    target_user["clan"] = name
    save_user(int(target), target_user)
    await reply_text(update, f"✅ {target} qabul qilindi.")


async def reject_clan(update, context):
    if not context.args:
        await reply_text(update, "Foydalanish: /rejectclan USER_ID")
        return
    name, clan_data = leader_clan(update.effective_user.id)
    if not clan_data:
        await reply_text(update, "Faqat clan rahbari rad qila oladi.")
        return
    clans = clans_with_defaults()
    target = str(context.args[0])
    clan_data["pending"] = [item for item in clan_data["pending"] if str(item.get("user")) != target]
    write(CLANS_FILE, clans)
    await reply_text(update, f"❌ {target} so‘rovi rad etildi.")


async def assign_helper(update, context):
    if not context.args:
        await reply_text(update, "Foydalanish: /assignhelper USER_ID")
        return
    name, clan_data = leader_clan(update.effective_user.id)
    if not clan_data:
        await reply_text(update, "Faqat clan rahbari tayinlaydi.")
        return
    target = str(context.args[0])
    if target not in clan_data["members"]:
        await reply_text(update, "Bu foydalanuvchi clan a’zosi emas.")
        return
    clans = clans_with_defaults()
    if target not in clan_data["helpers"]:
        clan_data["helpers"].append(target)
    write(CLANS_FILE, clans)
    await reply_text(update, f"✅ {target} yordamchi bo‘ldi.")


async def remove_helper(update, context):
    if not context.args:
        await reply_text(update, "Foydalanish: /removehelper USER_ID")
        return
    name, clan_data = leader_clan(update.effective_user.id)
    if not clan_data:
        await reply_text(update, "Faqat clan rahbari olib tashlaydi.")
        return
    clans = clans_with_defaults()
    target = str(context.args[0])
    clan_data["helpers"] = [member for member in clan_data["helpers"] if member != target]
    write(CLANS_FILE, clans)
    await reply_text(update, f"✅ {target} yordamchilikdan olindi.")


async def clan_admin(update, context):
    user = get_user(update.effective_user.id)
    name, clan_data = leader_clan(update.effective_user.id)
    if not user.get("clan"):
        await show(update, "Siz clan a’zosi emassiz.")
        return
    await show(update, f"🏰 {name} ADMIN\n👑 Rahbar: {'ha' if clan_data else 'yo‘q'}\n⏳ So‘rovlar: {len(clan_for(name)['pending'])}")


async def donate_clan(update, context):
    if not context.args:
        await reply_text(update, "Foydalanish: /donateclan MIQDOR")
        return
    uid = update.effective_user.id
    user = get_user(uid)
    name = user.get("clan")
    clan_data = clan_for(name)
    if not clan_data:
        await reply_text(update, "Siz clan a’zosi emassiz.")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await reply_text(update, "Miqdor son bo‘lishi kerak.")
        return
    if amount <= 0 or user["money"] < amount:
        await reply_text(update, "Miqdor noto‘g‘ri yoki pul yetarli emas.")
        return
    clans = clans_with_defaults()
    user["money"] -= amount
    clan_data["bank"] += amount
    clan_data["xp"] += max(1, amount // 100)
    while clan_data["xp"] >= 100:
        clan_data["xp"] -= 100
        clan_data["level"] += 1
    clan_data["logs"].append(f"{datetime.now().isoformat()} | {uid} {amount} xayriya qildi")
    write(CLANS_FILE, clans)
    save_user(uid, user)
    await reply_text(update, f"✅ {amount:,} clan bankiga qo‘shildi. XP: {clan_data['xp']}/100")


async def clan_upgrade(update, context):
    name, clan_data = leader_clan(update.effective_user.id)
    if not clan_data:
        await reply_text(update, "Faqat clan rahbari upgrade qila oladi.")
        return
    cost = 5000 + clan_data["level"] * 3000
    if clan_data["bank"] < cost:
        await reply_text(update, f"Bank yetarli emas. Kerak: {cost:,}.")
        return
    clans = clans_with_defaults()
    clan_data["bank"] -= cost
    clan_data["level"] += 1
    clan_data["xp"] = 0
    write(CLANS_FILE, clans)
    await reply_text(update, f"✅ Clan leveli {clan_data['level']} bo‘ldi.")


async def callback(update, context):
    if update.callback_query.data == "main":
        await start(update, context)
    else:
        await update.callback_query.answer()


async def text_handler(update, context):
    handlers = {"👤 Profil": profile, "👥 Clan": clan, "📋 Clanlar": clans_list}
    handler = handlers.get(update.message.text)
    if handler:
        await handler(update, context)
    else:
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
    app = Application.builder().token(TOKEN).build()
    commands = {"start": start, "profile": profile, "createclan": create_clan, "joinclan": join_clan, "leaveclan": leave_clan, "clans": clans_list, "clan": clan, "requestclan": request_clan, "acceptclan": accept_clan, "rejectclan": reject_clan, "assignhelper": assign_helper, "removehelper": remove_helper, "clanadmin": clan_admin, "donateclan": donate_clan, "clanupgrade": clan_upgrade}
    for command, handler in commands.items():
        app.add_handler(CommandHandler(command, handler))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
