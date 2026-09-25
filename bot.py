import json
import os
import random
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
            with open(path, encoding="utf-8") as file:
                value = json.load(file)
                return value if isinstance(value, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}


def write(path, data):
    with LOCK:
        temporary = str(path) + ".tmp"
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(temporary, path)


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


def clans_data():
    clans = read(CLANS_FILE)
    defaults = {"leader": "", "members": [], "pending": [], "helpers": [], "bank": 0, "level": 1, "xp": 0, "territory": 0, "war_wins": 0, "war_losses": 0, "logs": []}
    changed = False
    for name, clan in clans.items():
        if not isinstance(clan, dict):
            clan = {}
            clans[name] = clan
            changed = True
        for key, value in defaults.items():
            if key not in clan:
                clan[key] = value.copy() if isinstance(value, list) else value
                changed = True
        clan.setdefault("name", name)
    if changed:
        write(CLANS_FILE, clans)
    return clans


def clan_for(name):
    if not name:
        return None
    return clans_data().get(name)


def leader_clan(uid):
    user = get_user(uid)
    name = user.get("clan")
    clan = clan_for(name)
    return name, clan if clan and clan.get("leader") == str(uid) else None


def command_reply(update, text):
    return update.message.reply_text(text, reply_markup=back())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    person = update.effective_user
    user = get_user(person.id)
    user.update(first_name=person.first_name or "", username=person.username or "")
    save_user(person.id, user)
    await update.message.reply_text(
        f"Salom, {person.first_name}! 🎮\n\n"
        f"💰 Pul: {user['money']:,}\n💎 Almas: {user['diamonds']}\n"
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
    data = clan_for(name)
    if not data:
        await show(update, "👥 Siz clan a’zosi emassiz.\n\n/createclan ClanNomi\n/joinclan ClanNomi\n/requestclan ClanNomi")
        return
    members = []
    for member in data["members"]:
        member_user = get_user(int(member))
        display = member_user.get("first_name") or member_user.get("username") or member
        role = "👑 Rahbar" if member == data["leader"] else ("🛠 Yordamchi" if member in data["helpers"] else "👤 A’zo")
        members.append(f"{role} {display}")
    await show(update, f"🏰 CLAN: {name}\n\n👑 Rahbar: {data['leader']}\n👥 A’zolar: {len(data['members'])}\n💰 Bank: {data['bank']:,}\n⭐ Level: {data['level']}\n⭐ XP: {data['xp']}/100\n🌍 Hudud: {data['territory']}\n⚔️ War: {data['war_wins']}W / {data['war_losses']}L\n🧩 Yordamchilar: {len(data['helpers'])}\n⏳ So‘rovlar: {len(data['pending'])}\n\n📋 A’zolar:\n" + ("\n".join(members) or "yo‘q"))


async def create_clan(update, context):
    if not context.args:
        await command_reply(update, "Foydalanish: /createclan ClanNomi")
        return
    uid = update.effective_user.id
    user = get_user(uid)
    name = " ".join(context.args).strip()[:32]
    clans = clans_data()
    if user.get("clan"):
        await command_reply(update, "Siz allaqachon clandasiz.")
        return
    if not name or name in clans:
        await command_reply(update, "Clan nomi bo‘sh yoki mavjud.")
        return
    clans[name] = {"name": name, "leader": str(uid), "members": [str(uid)], "pending": [], "helpers": [], "bank": 0, "level": 1, "xp": 0, "territory": 0, "war_wins": 0, "war_losses": 0, "logs": [f"{datetime.now().isoformat()} | clan yaratildi"]}
    write(CLANS_FILE, clans)
    user["clan"] = name
    save_user(uid, user)
    await update.message.reply_text(f"✅ {name} clani yaratildi.", reply_markup=menu())


async def join_clan(update, context):
    if not context.args:
        await command_reply(update, "Foydalanish: /joinclan ClanNomi")
        return
    uid = update.effective_user.id
    user = get_user(uid)
    name = " ".join(context.args).strip()
    clans = clans_data()
    if user.get("clan"):
        await command_reply(update, "Avval hozirgi clandan chiqing.")
        return
    clan_data = clans.get(name)
    if not clan_data:
        await command_reply(update, "Bunday clan topilmadi.")
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
    clans = clans_data()
    clan_data = clans.get(name) if name else None
    if not clan_data:
        await command_reply(update, "Siz clanda emassiz.")
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
    await command_reply(update, "✅ Clandan chiqdingiz.")


async def clans_list(update, context):
    clans = clans_data()
    if not clans:
        await show(update, "🧭 Hozircha clan yo‘q.")
        return
    lines = ["🏰 CLANLAR\n"]
    for name, data in sorted(clans.items(), key=lambda item: item[1].get("level", 1), reverse=True):
        lines.append(f"• {name} | 👥 {len(data['members'])} | 💰 {data['bank']:,} | ⭐ L{data['level']} | 🌍 {data['territory']}")
    await show(update, "\n".join(lines))


async def request_clan(update, context):
    if not context.args:
        await command_reply(update, "Foydalanish: /requestclan ClanNomi")
        return
    uid = update.effective_user.id
    user = get_user(uid)
    if user.get("clan"):
        await command_reply(update, "Avval hozirgi clandan chiqing.")
        return
    name = " ".join(context.args).strip()
    clans = clans_data()
    clan_data = clans.get(name)
    if not clan_data:
        await command_reply(update, "Bunday clan topilmadi.")
        return
    if not any(str(item.get("user")) == str(uid) for item in clan_data["pending"] if isinstance(item, dict)):
        clan_data["pending"].append({"user": str(uid), "time": datetime.now().isoformat()})
        write(CLANS_FILE, clans)
        await command_reply(update, f"✅ {name} claniga so‘rov yuborildi.")
    else:
        await command_reply(update, "So‘rov allaqachon yuborilgan.")


def war_power(clan):
    return clan.get("level", 1) * 50 + len(clan.get("members", [])) * 20 + clan.get("territory", 0) * 15


async def clan_war(update, context):
    if not context.args:
        await command_reply(update, "Foydalanish: /clanwar RaqibClanNomi")
        return
    uid = update.effective_user.id
    user = get_user(uid)
    source_name = user.get("clan")
    target_name = " ".join(context.args).strip()
    clans = clans_data()
    source = clans.get(source_name) if source_name else None
    target = clans.get(target_name)
    if not source:
        await command_reply(update, "Siz clan a’zosi emassiz.")
        return
    if not target:
        await command_reply(update, "Raqib clan topilmadi.")
        return
    if source_name == target_name:
        await command_reply(update, "O‘z clanngizga qarshi urush boshlay olmaysiz.")
        return
    source_roll = war_power(source) + random.randint(1, 100)
    target_roll = war_power(target) + random.randint(1, 100)
    if source_roll >= target_roll:
        reward = 2000 + source.get("level", 1) * 250
        source["bank"] += reward
        source["territory"] += 1
        source["war_wins"] += 1
        target["territory"] = max(0, target["territory"] - 1)
        target["war_losses"] += 1
        result = f"🏆 G‘ALABA!\n\n⚔️ {source_name} → {target_name}\n💰 Mukofot: {reward:,}\n🌍 Hudud: +1\n📊 Kuch: {source_roll}–{target_roll}"
    else:
        source["bank"] = max(0, source["bank"] - 1000)
        source["war_losses"] += 1
        target["bank"] += 1000
        target["war_wins"] += 1
        result = f"⚔️ MAG‘LUBIYAT\n\n⚔️ {source_name} → {target_name}\n💸 Yo‘qotish: 1,000\n📊 Kuch: {source_roll}–{target_roll}"
    source.setdefault("logs", []).append(f"{datetime.now().isoformat()} | {target_name} bilan war")
    write(CLANS_FILE, clans)
    await command_reply(update, result)


async def clan_donate(update, context):
    if not context.args:
        await command_reply(update, "Foydalanish: /donateclan MIQDOR")
        return
    uid = update.effective_user.id
    user = get_user(uid)
    clan_name = user.get("clan")
    clans = clans_data()
    clan_data = clans.get(clan_name) if clan_name else None
    try:
        amount = int(context.args[0])
    except ValueError:
        await command_reply(update, "Miqdor son bo‘lishi kerak.")
        return
    if not clan_data or amount <= 0 or user["money"] < amount:
        await command_reply(update, "Miqdor noto‘g‘ri yoki pul yetarli emas.")
        return
    user["money"] -= amount
    clan_data["bank"] += amount
    clan_data["xp"] += max(1, amount // 100)
    while clan_data["xp"] >= 100:
        clan_data["xp"] -= 100
        clan_data["level"] += 1
    write(CLANS_FILE, clans)
    save_user(uid, user)
    await command_reply(update, f"✅ {amount:,} clan bankiga qo‘shildi. XP: {clan_data['xp']}/100")


async def clan_upgrade(update, context):
    name, clan_data = leader_clan(update.effective_user.id)
    if not clan_data:
        await command_reply(update, "Faqat clan rahbari upgrade qila oladi.")
        return
    cost = 5000 + clan_data["level"] * 3000
    if clan_data["bank"] < cost:
        await command_reply(update, f"Bank yetarli emas. Kerak: {cost:,}.")
        return
    clans = clans_data()
    clan_data["bank"] -= cost
    clan_data["level"] += 1
    clan_data["xp"] = 0
    write(CLANS_FILE, clans)
    await command_reply(update, f"✅ Clan leveli {clan_data['level']} bo‘ldi.")


async def clan_admin(update, context):
    user = get_user(update.effective_user.id)
    name, clan_data = leader_clan(update.effective_user.id)
    if not user.get("clan"):
        await show(update, "Siz clan a’zosi emassiz.")
        return
    await show(update, f"🏰 {name} ADMIN\n👑 Rahbar: {'ha' if clan_data else 'yo‘q'}\n⏳ So‘rovlar: {len(clan_for(name)['pending'])}")


async def accept_clan(update, context):
    if not context.args:
        await command_reply(update, "Foydalanish: /acceptclan USER_ID")
        return
    name, clan_data = leader_clan(update.effective_user.id)
    if not clan_data:
        await command_reply(update, "Faqat clan rahbari qabul qila oladi.")
        return
    target = str(context.args[0])
    clans = clans_data()
    clan_data["pending"] = [item for item in clan_data["pending"] if str(item.get("user")) != target]
    if target not in clan_data["members"]:
        clan_data["members"].append(target)
    write(CLANS_FILE, clans)
    target_user = get_user(int(target))
    target_user["clan"] = name
    save_user(int(target), target_user)
    await command_reply(update, f"✅ {target} qabul qilindi.")


async def reject_clan(update, context):
    if not context.args:
        await command_reply(update, "Foydalanish: /rejectclan USER_ID")
        return
    name, clan_data = leader_clan(update.effective_user.id)
    if not clan_data:
        await command_reply(update, "Faqat clan rahbari rad qila oladi.")
        return
    clans = clans_data()
    target = str(context.args[0])
    clan_data["pending"] = [item for item in clan_data["pending"] if str(item.get("user")) != target]
    write(CLANS_FILE, clans)
    await command_reply(update, f"❌ {target} so‘rovi rad etildi.")


async def assign_helper(update, context):
    if not context.args:
        await command_reply(update, "Foydalanish: /assignhelper USER_ID")
        return
    name, clan_data = leader_clan(update.effective_user.id)
    if not clan_data:
        await command_reply(update, "Faqat clan rahbari tayinlaydi.")
        return
    target = str(context.args[0])
    if target not in clan_data["members"]:
        await command_reply(update, "Bu foydalanuvchi clan a’zosi emas.")
        return
    clans = clans_data()
    if target not in clan_data["helpers"]:
        clan_data["helpers"].append(target)
    write(CLANS_FILE, clans)
    await command_reply(update, f"✅ {target} yordamchi bo‘ldi.")


async def remove_helper(update, context):
    if not context.args:
        await command_reply(update, "Foydalanish: /removehelper USER_ID")
        return
    name, clan_data = leader_clan(update.effective_user.id)
    if not clan_data:
        await command_reply(update, "Faqat clan rahbari olib tashlaydi.")
        return
    clans = clans_data()
    target = str(context.args[0])
    clan_data["helpers"] = [member for member in clan_data["helpers"] if member != target]
    write(CLANS_FILE, clans)
    await command_reply(update, f"✅ {target} yordamchilikdan olindi.")


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
    application = Application.builder().token(TOKEN).build()
    commands = {
        "start": start, "profile": profile, "createclan": create_clan, "joinclan": join_clan,
        "leaveclan": leave_clan, "clans": clans_list, "clan": clan, "requestclan": request_clan,
        "acceptclan": accept_clan, "rejectclan": reject_clan, "assignhelper": assign_helper,
        "removehelper": remove_helper, "clanadmin": clan_admin, "donateclan": clan_donate,
        "clanupgrade": clan_upgrade, "clanwar": clan_war,
    }
    for command, handler in commands.items():
        application.add_handler(CommandHandler(command, handler))
    application.add_handler(CallbackQueryHandler(callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
