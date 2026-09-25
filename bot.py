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
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}


def write(path, data):
    with LOCK:
        temp = str(path) + ".tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp, path)


def user_default():
    return {"money": 500, "diamonds": 0, "hp": 100, "max_hp": 100, "clan": None, "first_name": "", "username": ""}


def get_user(uid):
    users = read(USERS_FILE)
    user = users.get(str(uid), user_default())
    for key, value in user_default().items():
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
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menyu", callback_data="main")]])


async def show(update, text, markup=None):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.edit_message_text(text, reply_markup=markup)
        except Exception:
            await query.message.reply_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


def get_clan(name):
    clans = read(CLANS_FILE)
    return clans.get(name)


def ensure_clan(name, clan=None):
    clans = read(CLANS_FILE)
    if clan is None:
        clan = clans.get(name)
    if not isinstance(clan, dict):
        return None
    defaults = {
        "name": name, "leader": "", "members": [], "pending": [], "helpers": [],
        "bank": 0, "level": 1, "xp": 0, "description": "", "logs": []
    }
    for key, value in defaults.items():
        clan.setdefault(key, value)
    clans[name] = clan
    write(CLANS_FILE, clans)
    return clan


def save_clans(clans):
    write(CLANS_FILE, clans)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    person = update.effective_user
    user = get_user(person.id)
    user.update(first_name=person.first_name or "", username=person.username or "")
    save_user(person.id, user)
    await show(update, f"Salom, {person.first_name}! 🎮\n\n💰 Pul: {user['money']:,}\n💎 Almas: {user['diamonds']}\n❤️ HP: {user['hp']}/{user['max_hp']}\n👥 Clan: {user.get('clan') or 'yo‘q'}", menu())


async def profile(update, context):
    uid = update.effective_user.id
    u = get_user(uid)
    await show(update, f"👤 PROFIL\n\n🆔 ID: {uid}\n💰 Pul: {u['money']:,}\n💎 Almas: {u['diamonds']}\n❤️ HP: {u['hp']}/{u['max_hp']}\n👥 Clan: {u.get('clan') or 'yo‘q'}", back())


async def clan(update, context):
    uid = update.effective_user.id
    u = get_user(uid)
    name = u.get("clan")
    if not name:
        await show(update, "👥 Siz clan a’zosi emassiz.\n\n/createclan ClanNomi\n/joinclan ClanNomi\n/requestclan ClanNomi", back())
        return
    data = ensure_clan(name)
    if not data:
        u["clan"] = None
        save_user(uid, u)
        await show(update, "⚠️ Clan topilmadi.", back())
        return
    members = []
    for member in data["members"]:
        member_u = get_user(int(member))
        member_name = member_u.get("first_name") or member_u.get("username") or member
        role = "👑 Rahbar" if member == data["leader"] else ("🛠 Yordamchi" if member in data["helpers"] else "👤 A’zo")
        members.append(f"{role} {member_name}")
    await show(update, f"🏰 CLAN: {name}\n\n👑 Rahbar: {data['leader']}\n👥 A’zolar: {len(data['members'])}\n💰 Bank: {data['bank']:,}\n⭐ Level: {data['level']}\n⭐ XP: {data['xp']}/100\n🧩 Yordamchilar: {len(data['helpers'])}\n⏳ So‘rovlar: {len(data['pending'])}\n\n📋 A’zolar:\n" + ("\n".join(members) or "yo‘q"), back())


async def create_clan(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /createclan ClanNomi")
        return
    uid = update.effective_user.id
    u = get_user(uid)
    name = " ".join(context.args).strip()[:32]
    clans = read(CLANS_FILE)
    if u.get("clan"):
        await update.message.reply_text("Siz allaqachon clandasiz.")
        return
    if not name or name in clans:
        await update.message.reply_text("Clan nomi bo‘sh yoki mavjud.")
        return
    clans[name] = {"name": name, "leader": str(uid), "members": [str(uid)], "pending": [], "helpers": [], "bank": 0, "level": 1, "xp": 0, "description": "", "logs": [f"{datetime.now().isoformat()} | yaratildi"]}
    save_clans(clans)
    u["clan"] = name
    save_user(uid, u)
    await update.message.reply_text(f"✅ {name} clani yaratildi.", reply_markup=menu())


async def join_clan(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /joinclan ClanNomi")
        return
    uid = update.effective_user.id
    u = get_user(uid)
    name = " ".join(context.args).strip()
    clans = read(CLANS_FILE)
    clan = ensure_clan(name, clans.get(name))
    if u.get("clan"):
        await update.message.reply_text("Avval hozirgi clandan chiqing.")
        return
    if not clan:
        await update.message.reply_text("Bunday clan topilmadi.")
        return
    if str(uid) not in clan["members"]:
        clan["members"].append(str(uid))
        save_clans(clans)
    u["clan"] = name
    save_user(uid, u)
    await update.message.reply_text(f"✅ {name} claniga qo‘shildingiz.", reply_markup=menu())


async def leave_clan(update, context):
    uid = update.effective_user.id
    u = get_user(uid)
    name = u.get("clan")
    clans = read(CLANS_FILE)
    clan = ensure_clan(name, clans.get(name)) if name else None
    if not clan:
        await update.message.reply_text("Siz clanda emassiz.")
        return
    clan["members"] = [m for m in clan["members"] if m != str(uid)]
    clan["helpers"] = [m for m in clan["helpers"] if m != str(uid)]
    if clan["leader"] == str(uid) and clan["members"]:
        clan["leader"] = clan["members"][0]
    if clan["members"]:
        clans[name] = clan
    else:
        clans.pop(name, None)
    save_clans(clans)
    u["clan"] = None
    save_user(uid, u)
    await update.message.reply_text("✅ Clandan chiqdingiz.", reply_markup=menu())


async def clans_list(update, context):
    clans = read(CLANS_FILE)
    if not clans:
        await show(update, "🧭 Hozircha clan yo‘q.", back())
        return
    lines = ["🏰 CLANLAR\n"]
    for name, data in sorted(clans.items(), key=lambda item: item[1].get("level", 1), reverse=True):
        lines.append(f"• {name} | 👥 {len(data.get('members', []))} | 💰 {data.get('bank', 0):,} | ⭐ L{data.get('level', 1)} XP {data.get('xp', 0)}/100")
    await show(update, "\n".join(lines), back())


async def request_clan(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /requestclan ClanNomi")
        return
    uid = update.effective_user.id
    u = get_user(uid)
    if u.get("clan"):
        await update.message.reply_text("Avval hozirgi clandan chiqing.")
        return
    name = " ".join(context.args).strip()
    clans = read(CLANS_FILE)
    clan = ensure_clan(name, clans.get(name))
    if not clan:
        await update.message.reply_text("Bunday clan topilmadi.")
        return
    if not any(str(item.get("user")) == str(uid) for item in clan["pending"] if isinstance(item, dict)):
        clan["pending"].append({"user": str(uid), "time": datetime.now().isoformat()})
        save_clans(clans)
        await update.message.reply_text(f"✅ {name} claniga so‘rov yuborildi.")
    else:
        await update.message.reply_text("So‘rov allaqachon yuborilgan.")


def leader_clan(uid):
    u = get_user(uid)
    name = u.get("clan")
    clan = ensure_clan(name) if name else None
    return name, clan if clan and clan.get("leader") == str(uid) else None


async def accept_clan(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /acceptclan USER_ID")
        return
    uid = update.effective_user.id
    name, clan = leader_clan(uid)
    if not clan:
        await update.message.reply_text("Faqat clan rahbari qabul qila oladi.")
        return
    try:
        target = str(int(context.args[0]))
    except ValueError:
        await update.message.reply_text("USER_ID son bo‘lishi kerak.")
        return
    clans = read(CLANS_FILE)
    clan["pending"] = [p for p in clan["pending"] if str(p.get("user")) != target]
    if target not in clan["members"]:
        clan["members"].append(target)
    save_clans(clans)
    target_u = get_user(int(target))
    target_u["clan"] = name
    save_user(int(target), target_u)
    await update.message.reply_text(f"✅ {target} qabul qilindi.")


async def reject_clan(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /rejectclan USER_ID")
        return
    name, clan = leader_clan(update.effective_user.id)
    if not clan:
        await update.message.reply_text("Faqat clan rahbari rad qila oladi.")
        return
    target = str(context.args[0])
    clans = read(CLANS_FILE)
    clan["pending"] = [p for p in clan["pending"] if str(p.get("user")) != target]
    save_clans(clans)
    await update.message.reply_text(f"❌ {target} so‘rovi rad etildi.")


async def assign_helper(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /assignhelper USER_ID")
        return
    name, clan = leader_clan(update.effective_user.id)
    if not clan:
        await update.message.reply_text("Faqat clan rahbari tayinlaydi.")
        return
    target = str(context.args[0])
    if target not in clan["members"]:
        await update.message.reply_text("Bu foydalanuvchi clan a’zosi emas.")
        return
    clans = read(CLANS_FILE)
    if target not in clan["helpers"]:
        clan["helpers"].append(target)
    save_clans(clans)
    await update.message.reply_text(f"✅ {target} yordamchi bo‘ldi.")


async def remove_helper(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /removehelper USER_ID")
        return
    name, clan = leader_clan(update.effective_user.id)
    if not clan:
        await update.message.reply_text("Faqat clan rahbari olib tashlaydi.")
        return
    target = str(context.args[0])
    clans = read(CLANS_FILE)
    clan["helpers"] = [m for m in clan["helpers"] if m != target]
    save_clans(clans)
    await update.message.reply_text(f"✅ {target} yordamchilikdan olindi.")


async def clan_admin(update, context):
    name, clan = leader_clan(update.effective_user.id)
    u = get_user(update.effective_user.id)
    if not u.get("clan"):
        await update.message.reply_text("Siz clan a’zosi emassiz.")
        return
    await update.message.reply_text(f"🏰 {u['clan']} ADMIN\n👑 Rahbar: {'ha' if clan else 'yo‘q'}\n⏳ So‘rovlar: {len(ensure_clan(u['clan'])['pending'])}")


async def donate_clan(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /donateclan MIQDOR")
        return
    uid = update.effective_user.id
    u = get_user(uid)
    name = u.get("clan")
    clan = ensure_clan(name) if name else None
    if not clan:
        await update.message.reply_text("Siz clan a’zosi emassiz.")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Miqdor son bo‘lishi kerak.")
        return
    if amount <= 0 or u["money"] < amount:
        await update.message.reply_text("Miqdor noto‘g‘ri yoki pul yetarli emas.")
        return
    clans = read(CLANS_FILE)
    u["money"] -= amount
    clan["bank"] += amount
    clan["xp"] += max(1, amount // 100)
    while clan["xp"] >= 100:
        clan["xp"] -= 100
        clan["level"] += 1
    clan["logs"].append(f"{datetime.now().isoformat()} | {uid} {amount} xayriya qildi")
    save_clans(clans)
    save_user(uid, u)
    await update.message.reply_text(f"✅ {amount:,} clan bankiga qo‘shildi. XP: {clan['xp']}/100")


async def clan_upgrade(update, context):
    name, clan = leader_clan(update.effective_user.id)
    if not clan:
        await update.message.reply_text("Faqat clan rahbari upgrade qila oladi.")
        return
    cost = 5000 + clan["level"] * 3000
    if clan["bank"] < cost:
        await update.message.reply_text(f"Bank yetarli emas. Kerak: {cost:,}.")
        return
    clans = read(CLANS_FILE)
    clan["bank"] -= cost
    clan["level"] += 1
    clan["xp"] = 0
    save_clans(clans)
    await update.message.reply_text(f"✅ Clan leveli {clan['level']} bo‘ldi.")


async def callback(update, context):
    if update.callback_query.data == "main":
        await start(update, context)
    else:
        await update.callback_query.answer()


async def text_handler(update, context):
    actions = {"👤 Profil": profile, "👥 Clan": clan, "📋 Clanlar": clans_list}
    handler = actions.get(update.message.text)
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
    commands = {
        "start": start, "profile": profile, "createclan": create_clan, "joinclan": join_clan,
        "leaveclan": leave_clan, "clans": clans_list, "clan": clan, "requestclan": request_clan,
        "acceptclan": accept_clan, "rejectclan": reject_clan, "assignhelper": assign_helper,
        "removehelper": remove_helper, "clanadmin": clan_admin, "donateclan": donate_clan,
        "clanupgrade": clan_upgrade,
    }
    for command, handler in commands.items():
        app.add_handler(CommandHandler(command, handler))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
