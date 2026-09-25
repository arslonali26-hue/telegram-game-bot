import json
import os
import random
import threading
from datetime import datetime, timedelta
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
ADMIN_IDS = {7979870096}
USERS_FILE = Path("users.json")
CLANS_FILE = Path("clans.json")
DATA_LOCK = threading.RLock()
GAMES = {}

WEAPONS = [
    ("🔪 Pichoq", 0, 10), ("🔫 Pistolet", 100, 20),
    ("🔫 Revolver", 500, 35), ("🔫 Desert Eagle", 1500, 50),
    ("🔫 Shotgun", 4000, 75), ("🏹 Arbalet", 10000, 100),
]
HP_ITEMS = [(150, 10), (400, 30), (1000, 80), (3000, 250)]
ARMOR_ITEMS = [(150, 10), (400, 30), (1000, 80), (3000, 250)]
MEDKIT_ITEMS = [(150, 1), (400, 3), (1000, 8), (3000, 25)]


def read(path):
    with DATA_LOCK:
        try:
            with open(path, encoding="utf-8") as file:
                value = json.load(file)
                return value if isinstance(value, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}


def write(path, data):
    with DATA_LOCK:
        temporary = str(path) + ".tmp"
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(temporary, path)


def default_user():
    return {
        "money": 500, "diamonds": 0, "hp": 100, "max_hp": 100,
        "armor": 0, "max_armor": 0, "medkits": 0, "weapon_idx": 0,
        "weapon": WEAPONS[0][0], "wins": 0, "losses": 0, "clan": None,
        "last_work": "", "last_crime": "", "last_rob": "",
        "first_name": "", "username": "",
    }


def get_user(uid):
    users = read(USERS_FILE)
    key = str(uid)
    changed = key not in users
    users.setdefault(key, default_user())
    defaults = default_user()
    for name, value in defaults.items():
        if name not in users[key]:
            users[key][name] = value
            changed = True
    if changed:
        write(USERS_FILE, users)
    return users[key]


def save_user(uid, value):
    users = read(USERS_FILE)
    users[str(uid)] = value
    write(USERS_FILE, users)


def menu():
    return ReplyKeyboardMarkup([
        ["⚔️ Jang", "👤 Profil"], ["🔫 Qurollar", "❤️ HP"],
        ["🛡️ Himoya", "💊 Aptechka"], ["💼 Ishlash", "🕵️ Jinoyat"],
        ["💰 O‘g‘rilik", "👥 Clan"], ["🏆 Reyting", "👑 Admin"],
    ], resize_keyboard=True)


def back_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menyu", callback_data="main")]])


async def reply(update, text, markup=None):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.edit_message_text(text, reply_markup=markup)
        except Exception:
            await query.message.reply_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    person = update.effective_user
    value = get_user(person.id)
    value.update(first_name=person.first_name or "", username=person.username or "")
    save_user(person.id, value)
    await update.message.reply_text(
        f"Salom, {person.first_name}! 🎮\n\n💰 Pul: {value['money']}\n💎 Olmos: {value['diamonds']}\n"
        f"❤️ HP: {value['hp']}/{value['max_hp']}\n👥 Clan: {value['clan'] or 'yo‘q'}",
        reply_markup=menu(),
    )


async def profile(update, context):
    uid = update.effective_user.id
    value = get_user(uid)
    total = value["wins"] + value["losses"]
    rate = round(value["wins"] * 100 / total, 1) if total else 0
    await reply(update, f"👤 PROFIL\n\n🆔 ID: {uid}\n💰 Pul: {value['money']}\n💎 Olmos: {value['diamonds']}\n"
                       f"❤️ HP: {value['hp']}/{value['max_hp']}\n🛡️ Himoya: {value['armor']}/{value['max_armor']}\n"
                       f"🔫 Qurol: {value['weapon']}\n🏆 G‘alaba: {value['wins']}\n❌ Mag‘lubiyat: {value['losses']}\n📈 Foiz: {rate}%\n👥 Clan: {value['clan'] or 'yo‘q'}", back_markup())


async def shop(update, kind):
    value = get_user(update.effective_user.id)
    rows = []
    if kind == "weapon":
        for index, (name, price, damage) in enumerate(WEAPONS):
            label = ("✅ " if index <= value["weapon_idx"] else "") + f"{name} ({damage} dmg)"
            if index > value["weapon_idx"]:
                label += f" — {price}"
            rows.append([InlineKeyboardButton(label, callback_data=f"buyweapon:{index}")])
    else:
        items = {"hp": HP_ITEMS, "armor": ARMOR_ITEMS, "medkit": MEDKIT_ITEMS}[kind]
        for index, (price, amount) in enumerate(items):
            rows.append([InlineKeyboardButton(f"{kind.upper()} +{amount} — {price}", callback_data=f"buy:{kind}:{index}")])
    rows.append([InlineKeyboardButton("🔙 Menyu", callback_data="main")])
    await reply(update, f"🛒 {kind.upper()} DO‘KONI\n\n💰 Pul: {value['money']}", InlineKeyboardMarkup(rows))


async def fight(update, context):
    uid = update.effective_user.id
    value = get_user(uid)
    if value["hp"] <= 0:
        await reply(update, "❤️ HP tugagan. Avval HP sotib oling.", back_markup())
        return
    enemy_hp = random.randint(80, 250)
    GAMES[uid] = {"hp": enemy_hp, "max": enemy_hp, "name": random.choice(["Qaroqchi", "Gangster", "Boss"]), "damage": random.randint(8, 30)}
    await show_fight(update, uid)


async def show_fight(update, uid):
    game = GAMES.get(uid)
    value = get_user(uid)
    if not game:
        await reply(update, "Faol jang yo‘q.", back_markup())
        return
    buttons = [[InlineKeyboardButton("⚔️ Hujum", callback_data="fight:attack"), InlineKeyboardButton("💊 Davolanish", callback_data="fight:heal")],
               [InlineKeyboardButton("🏃 Qochish", callback_data="fight:flee")]]
    await reply(update, f"⚔️ JANG\n\n👾 {game['name']}\n❤️ Raqib: {game['hp']}/{game['max']}\n👤 Siz: {value['hp']}/{value['max_hp']}", InlineKeyboardMarkup(buttons))


async def fight_action(update, action):
    uid = update.effective_user.id
    query = update.callback_query
    value = get_user(uid)
    game = GAMES.get(uid)
    if not game:
        await query.answer("Faol jang yo‘q.", show_alert=True)
        return
    if action == "flee":
        GAMES.pop(uid, None)
        await reply(update, "🏃 Jangdan qochdingiz.", back_markup())
        return
    if action == "heal":
        if value["medkits"] < 1:
            await query.answer("Aptechka yo‘q.", show_alert=True)
            return
        value["medkits"] -= 1
        value["hp"] = min(value["max_hp"], value["hp"] + 50)
    else:
        weapon_damage = WEAPONS[value["weapon_idx"]][2]
        game["hp"] -= random.randint(max(1, weapon_damage - 5), weapon_damage + 10)
        if game["hp"] <= 0:
            reward = random.randint(100, 500)
            value["wins"] += 1
            value["money"] += reward
            save_user(uid, value)
            GAMES.pop(uid, None)
            await reply(update, f"🏆 G‘ALABA!\n💰 Mukofot: {reward}", back_markup())
            return
    hit = random.randint(1, game["damage"])
    blocked = min(value["armor"], hit)
    value["armor"] -= blocked
    value["hp"] = max(0, value["hp"] - hit + blocked)
    if value["hp"] <= 0:
        value["losses"] += 1
        value["hp"] = max(1, value["max_hp"] // 2)
        save_user(uid, value)
        GAMES.pop(uid, None)
        await reply(update, "❌ MAG‘LUBIYAT.", back_markup())
        return
    save_user(uid, value)
    await show_fight(update, uid)


def available(value, field, minutes):
    if not value.get(field):
        return True
    try:
        return datetime.now() >= datetime.fromisoformat(value[field]) + timedelta(minutes=minutes)
    except ValueError:
        return True


async def earn(update, kind):
    uid = update.effective_user.id
    value = get_user(uid)
    field, minutes = {"work": ("last_work", 5), "crime": ("last_crime", 10), "rob": ("last_rob", 15)}[kind]
    if not available(value, field, minutes):
        await reply(update, "⏳ Kutish vaqti hali tugamadi.", back_markup())
        return
    value[field] = datetime.now().isoformat()
    chance = {"work": 1.0, "crime": .65, "rob": .45}[kind]
    if random.random() < chance:
        amount = random.randint(100, 500) if kind == "work" else random.randint(200, 2500)
        value["money"] += amount
        text = f"✅ Muvaffaqiyat!\n💰 Daromad: {amount}"
    else:
        amount = min(value["money"], random.randint(50, 300))
        value["money"] -= amount
        text = f"❌ Muvaffaqiyatsiz!\n💸 Yo‘qotish: {amount}"
    save_user(uid, value)
    await reply(update, text, back_markup())


async def clan(update, context):
    value = get_user(update.effective_user.id)
    clans = read(CLANS_FILE)
    if not value["clan"]:
        await reply(update, "👥 Siz clan a’zosi emassiz.\n/createclan Nomi — yaratish\n/joinclan Nomi — qo‘shilish", back_markup())
        return
    current = clans.get(value["clan"], {})
    await reply(update, f"👥 CLAN: {value['clan']}\n\n👥 A’zolar: {len(current.get('members', []))}\n💰 Bank: {current.get('bank', 0)}\n👑 Lider ID: {current.get('leader', '-')}", back_markup())


async def create_clan(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /createclan ClanNomi")
        return
    uid = update.effective_user.id
    value = get_user(uid)
    name = " ".join(context.args).strip()[:32]
    clans = read(CLANS_FILE)
    if value["clan"]:
        await update.message.reply_text("Siz allaqachon clandasiz.")
    elif name in clans:
        await update.message.reply_text("Bu clan mavjud.")
    else:
        clans[name] = {"leader": str(uid), "members": [str(uid)], "bank": 0}
        write(CLANS_FILE, clans)
        value["clan"] = name
        save_user(uid, value)
        await update.message.reply_text(f"✅ {name} clani yaratildi.", reply_markup=menu())


async def join_clan(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /joinclan ClanNomi")
        return
    uid = update.effective_user.id
    value = get_user(uid)
    clans = read(CLANS_FILE)
    name = " ".join(context.args).strip()
    if value["clan"]:
        await update.message.reply_text("Avval hozirgi clandan chiqing.")
    elif name not in clans:
        await update.message.reply_text("Bunday clan topilmadi.")
    else:
        clans[name].setdefault("members", []).append(str(uid))
        write(CLANS_FILE, clans)
        value["clan"] = name
        save_user(uid, value)
        await update.message.reply_text(f"✅ {name} claniga qo‘shildingiz.", reply_markup=menu())


async def leave_clan(update, context):
    uid = update.effective_user.id
    value = get_user(uid)
    if not value["clan"]:
        await update.message.reply_text("Siz clanda emassiz.")
        return
    name = value["clan"]
    clans = read(CLANS_FILE)
    clan_data = clans.get(name, {})
    clan_data["members"] = [member for member in clan_data.get("members", []) if member != str(uid)]
    if clan_data.get("leader") == str(uid) and clan_data["members"]:
        clan_data["leader"] = clan_data["members"][0]
    if clan_data.get("members"):
        clans[name] = clan_data
    else:
        clans.pop(name, None)
    write(CLANS_FILE, clans)
    value["clan"] = None
    save_user(uid, value)
    await update.message.reply_text("✅ Clandan chiqdingiz.", reply_markup=menu())


async def leaderboard(update, context):
    users = read(USERS_FILE)
    top = sorted(users.items(), key=lambda item: (item[1].get("wins", 0), item[1].get("money", 0)), reverse=True)[:10]
    lines = ["🏆 TOP 10 O‘YINCHI\n"]
    for index, (uid, value) in enumerate(top, 1):
        lines.append(f"{index}. {value.get('first_name') or uid} — 🏆 {value.get('wins', 0)} | 💰 {value.get('money', 0)}")
    await reply(update, "\n".join(lines), back_markup())


async def admin(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await reply(update, "⛔ Siz admin emassiz.", back_markup())
        return
    await reply(update, "👑 ADMIN\n/addmoney ID MIQDOR\n/adddiamond ID MIQDOR\n/broadcast MATN\n/users", back_markup())


async def add_money(update, context):
    if update.effective_user.id not in ADMIN_IDS or len(context.args) != 2:
        return
    try:
        uid, amount = int(context.args[0]), int(context.args[1])
        value = get_user(uid)
        value["money"] += amount
        save_user(uid, value)
        await update.message.reply_text("✅ Pul berildi.")
    except ValueError:
        await update.message.reply_text("Foydalanish: /addmoney ID MIQDOR")


async def add_diamond(update, context):
    if update.effective_user.id not in ADMIN_IDS or len(context.args) != 2:
        return
    try:
        uid, amount = int(context.args[0]), int(context.args[1])
        value = get_user(uid)
        value["diamonds"] += amount
        save_user(uid, value)
        await update.message.reply_text("✅ Olmos berildi.")
    except ValueError:
        await update.message.reply_text("Foydalanish: /adddiamond ID MIQDOR")


async def users_cmd(update, context):
    if update.effective_user.id in ADMIN_IDS:
        await update.message.reply_text(f"Foydalanuvchilar: {len(read(USERS_FILE))}")


async def broadcast(update, context):
    if update.effective_user.id not in ADMIN_IDS or not context.args:
        return
    text = " ".join(context.args)
    sent = 0
    for uid in read(USERS_FILE):
        try:
            await context.bot.send_message(int(uid), text)
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ {sent} ta foydalanuvchiga yuborildi.")


async def callback(update, context):
    data = update.callback_query.data
    if data == "main":
        await start(update, context)
    elif data == "profile":
        await profile(update, context)
    elif data.startswith("fight:"):
        await fight_action(update, data.split(":", 1)[1])
    elif data.startswith("buyweapon:"):
        index = int(data.split(":")[1]); uid = update.effective_user.id; value = get_user(uid)
        if index <= value["weapon_idx"]:
            await update.callback_query.answer("Bu qurol sizda bor.", show_alert=True); return
        name, price, _ = WEAPONS[index]
        if value["money"] < price:
            await update.callback_query.answer("Pul yetarli emas.", show_alert=True); return
        value.update(money=value["money"] - price, weapon_idx=index, weapon=name)
        save_user(uid, value); await update.callback_query.answer("Sotib olindi!"); await shop(update, "weapon")
    elif data.startswith("buy:"):
        _, kind, index = data.split(":"); index = int(index); uid = update.effective_user.id; value = get_user(uid)
        items = {"hp": HP_ITEMS, "armor": ARMOR_ITEMS, "medkit": MEDKIT_ITEMS}[kind]
        price, amount = items[index]
        if value["money"] < price:
            await update.callback_query.answer("Pul yetarli emas.", show_alert=True); return
        value["money"] -= price
        if kind == "hp": value["max_hp"] += amount; value["hp"] += amount
        elif kind == "armor": value["max_armor"] += amount; value["armor"] += amount
        else: value["medkits"] += amount
        save_user(uid, value); await update.callback_query.answer("Xarid qilindi!"); await shop(update, kind)
    else:
        await update.callback_query.answer()


async def text_handler(update, context):
    actions = {"⚔️ Jang": fight, "👤 Profil": profile, "🔫 Qurollar": lambda u, c: shop(u, "weapon"),
               "❤️ HP": lambda u, c: shop(u, "hp"), "🛡️ Himoya": lambda u, c: shop(u, "armor"),
               "💊 Aptechka": lambda u, c: shop(u, "medkit"), "💼 Ishlash": lambda u, c: earn(u, "work"),
               "🕵️ Jinoyat": lambda u, c: earn(u, "crime"), "💰 O‘g‘rilik": lambda u, c: earn(u, "rob"),
               "👥 Clan": clan, "🏆 Reyting": leaderboard, "👑 Admin": admin}
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
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("createclan", create_clan))
    application.add_handler(CommandHandler("joinclan", join_clan))
    application.add_handler(CommandHandler("leaveclan", leave_clan))
    application.add_handler(CommandHandler("addmoney", add_money))
    application.add_handler(CommandHandler("adddiamond", add_diamond))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("users", users_cmd))
    application.add_handler(CallbackQueryHandler(callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
