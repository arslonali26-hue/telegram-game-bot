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
    ("🔪 Pichoq", "money", 0, 10), ("🔫 Pistolet", "money", 100, 20), ("🔫 Revolver", "money", 500, 35),
    ("🔫 Desert Eagle", "money", 1500, 50), ("🔫 Shotgun", "money", 4000, 75), ("🏹 Arbalet", "money", 10000, 100),
]
SHIELDS = [
    ("🪵 Oddiy Himoya", "money", 50000, 50), ("🥉 Kuchli Himoya", "money", 100000, 75),
    ("🥈 Temir Himoya", "money", 175000, 100), ("🥇 Po‘lat Himoya", "money", 250000, 125),
    ("🛡️ Titan Himoya", "money", 350000, 150), ("🔩 Maxsus Himoya", "money", 500000, 200),
]
MEDKITS = [
    ("💊 Kichik Aptechka", "money", 1000, 10), ("💊 Oddiy Aptechka", "money", 2000, 15),
    ("💊 Yaxshi Aptechka", "money", 3500, 20), ("💊 Kuchli Aptechka", "money", 5000, 25),
    ("💊 Katta Aptechka", "money", 7500, 30), ("💊 Super Aptechka", "money", 10000, 40),
]


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
        "money": 500,
        "diamonds": 0,
        "hp": 100,
        "max_hp": 100,
        "selected_weapon": 0,
        "weapons": {"0": {"level": 1, "xp": 0}},
        "shield": None,
        "shield_hp": 0,
        "shield_max": 0,
        "shield_regen": "",
        "medkits": {},
        "wins": 0,
        "losses": 0,
        "clan": None,
        "first_name": "",
        "username": "",
        "last_work": "",
        "last_crime": "",
        "last_rob": "",
    }


def migrate(value):
    if not isinstance(value, dict):
        value = {}
    base = default_user()
    for key, val in base.items():
        value.setdefault(key, val)
    if "weapon_idx" in value and "selected_weapon" not in value:
        value["selected_weapon"] = value["weapon_idx"]
    value.setdefault("weapons", {})
    value["weapons"].setdefault("0", {"level": 1, "xp": 0})
    for key, item in list(value["weapons"].items()):
        if isinstance(item, dict):
            item.setdefault("level", 1)
            item.setdefault("xp", 0)
            item["level"] = max(1, min(15, int(item["level"])))
            item["xp"] = max(0, min(99, int(item["xp"])))
        else:
            value["weapons"][key] = {"level": 1, "xp": 0}
    value.setdefault("medkits", {})
    value.pop("armor", None)
    value.pop("weapon_idx", None)
    value.pop("weapon", None)
    return value


def get_user(uid):
    users = read(USERS_FILE)
    key = str(uid)
    user = migrate(users.get(key, default_user()))
    users[key] = user
    if user.get("shield") and user.get("shield_hp", 0) < user.get("shield_max", 0):
        last = user.get("shield_regen")
        now = datetime.now()
        if not last:
            user["shield_regen"] = now.isoformat()
        else:
            try:
                last_dt = datetime.fromisoformat(last)
                elapsed = int((now - last_dt).total_seconds() // 1800)
                if elapsed > 0:
                    user["shield_hp"] = min(user["shield_max"], user["shield_hp"] + elapsed)
                    user["shield_regen"] = (last_dt + timedelta(minutes=30 * elapsed)).isoformat()
            except ValueError:
                user["shield_regen"] = now.isoformat()
    write(USERS_FILE, users)
    return user


def save_user(uid, value):
    users = read(USERS_FILE)
    users[str(uid)] = migrate(value)
    write(USERS_FILE, users)


def menu():
    return ReplyKeyboardMarkup([
        ["⚔️ Jang", "👤 Profil"],
        ["🔫 Qurollar", "🛡️ Himoya"],
        ["💊 Aptechka", "🎒 Inventar"],
        ["💼 Ishlash", "🕵️ Jinoyat"],
        ["💰 O‘g‘rilik", "👥 Clan"],
        ["🏆 Reyting", "👑 Admin"],
    ], resize_keyboard=True)


def back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menyu", callback_data="main")]])


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


def currency_label(currency, amount):
    if amount == 0:
        return "Bepul"
    return f"{amount:,} {'💰' if currency == 'money' else '💎'}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    person = update.effective_user
    value = get_user(person.id)
    value.update(first_name=person.first_name or "", username=person.username or "")
    save_user(person.id, value)
    await show(
        update,
        f"Salom, {person.first_name}! 🎮\n\n"
        f"💰 Pul: {value['money']:,}\n"
        f"💎 Almas: {value['diamonds']}\n"
        f"❤️ HP: {value['hp']}/{value['max_hp']}\n"
        f"🛡️ Himoya: {value['shield_hp']}/{value['shield_max']}\n"
        f"👥 Clan: {value['clan'] or 'yo‘q'}",
        menu(),
    )


async def profile(update, context):
    uid = update.effective_user.id
    value = get_user(uid)
    weapon_index = value["selected_weapon"]
    weapon_name, _, _, weapon_damage = WEAPONS[weapon_index]
    weapon_entry = value["weapons"].get(str(weapon_index), {"level": 1, "xp": 0})
    total = value["wins"] + value["losses"]
    rate = round(value["wins"] * 100 / total, 1) if total else 0
    dmg_now = weapon_damage + (weapon_entry["level"] - 1) * 5
    await show(
        update,
        f"👤 PROFIL\n\n"
        f"🆔 ID: {uid}\n"
        f"💰 Pul: {value['money']:,}\n"
        f"💎 Almas: {value['diamonds']}\n"
        f"❤️ HP: {value['hp']}/{value['max_hp']}\n"
        f"🛡️ Himoya: {value['shield_hp']}/{value['shield_max']}\n"
        f"🔫 Qurol: {weapon_name} (L{weapon_entry['level']})\n"
        f"⚔️ Zarar: {dmg_now}\n"
        f"🏆 G‘alaba: {value['wins']}\n"
        f"❌ Mag‘lubiyat: {value['losses']}\n"
        f"📈 Foiz: {rate}%\n"
        f"👥 Clan: {value['clan'] or 'yo‘q'}",
        back(),
    )


async def weapon_shop(update, page=0):
    uid = update.effective_user.id
    value = get_user(uid)
    page = max(0, min(4, int(page)))
    rows = []
    start = page * 10
    end = min(start + 10, len(WEAPONS))
    for i in range(start, end):
        name, currency, price, _ = WEAPONS[i]
        owned = str(i) in value["weapons"]
        current_level = value["weapons"].get(str(i), {"level": 0}).get("level", 0)
        mark = "✅" if i == value["selected_weapon"] else ("📦" if owned else "🔒")
        rows.append([
            InlineKeyboardButton(
                f"{mark} {i + 1}. {name} L{current_level} | {currency_label(currency, price)}",
                callback_data=f"weapon:{i}",
            )
        ])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"wpage:{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/5", callback_data="noop"))
    if page < 4:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"wpage:{page + 1}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 Menyu", callback_data="main")])
    await show(
        update,
        f"🔫 QUROLLAR {start + 1}–{end}/{len(WEAPONS)}\n💰 {value['money']:,} | 💎 {value['diamonds']}",
        InlineKeyboardMarkup(rows),
    )


async def weapon_detail(update, index):
    uid = update.effective_user.id
    value = get_user(uid)
    name, currency, price, base = WEAPONS[index]
    entry = value["weapons"].get(str(index), {"level": 1, "xp": 0})
    level = entry["level"]
    xp = entry["xp"]
    rows = []
    if str(index) not in value["weapons"]:
        rows.append([InlineKeyboardButton(f"🛒 Sotib olish — {currency_label(currency, price)}", callback_data=f"buyweapon:{index}")])
    else:
        if index != value["selected_weapon"]:
            rows.append([InlineKeyboardButton("🎯 Tanlash", callback_data=f"selectweapon:{index}")])
        else:
            rows.append([InlineKeyboardButton("✅ Tanlangan", callback_data="noop")])
    rows.append([InlineKeyboardButton("🔙 Qurollar", callback_data="wpage:0")])
    await show(
        update,
        f"{name}\n\n"
        f"💳 Narx: {currency_label(currency, price)}\n"
        f"⚔️ Zarar: {base + (level - 1) * 5}\n"
        f"⭐ Level: {level}/15\n"
        f"📊 XP: {xp}/100\n\n"
        f"Har muvaffaqiyatli hujum +XP beradi. 100 XP = 1 level.",
        InlineKeyboardMarkup(rows),
    )


async def catalog(update, kind, page=0):
    uid = update.effective_user.id
    value = get_user(uid)
    data = SHIELDS if kind == "shield" else MEDKITS
    rows = []
    for i, item in enumerate(data):
        name, currency, price, value_amount = item
        if kind == "shield":
            label = f"{i + 1}. {name} — {currency_label(currency, price)} | {value_amount} HP"
            if value.get("shield") == name:
                label = f"✅ {label}"
        else:
            count = value["medkits"].get(str(i), 0)
            label = f"{i + 1}. {name} — {currency_label(currency, price)} | +{value_amount} HP ({count} dona)"
        rows.append([InlineKeyboardButton(label, callback_data=f"shop:{kind}:{i}")])
    rows.append([InlineKeyboardButton("🔙 Menyu", callback_data="main")])
    await show(
        update,
        f"🛒 {'HIMOYA' if kind == 'shield' else 'APTECHKA'}\n"
        f"💰 {value['money']:,} | 💎 {value['diamonds']}\n\n"
        f"Aptechka jang boshlangandan keyin sotib olib bo‘lmaydi, lekin oldin sotib olinganlar ishlatiladi.",
        InlineKeyboardMarkup(rows),
    )


async def inventory(update, context):
    value = get_user(update.effective_user.id)
    meds = []
    for i in range(len(MEDKITS)):
        count = value["medkits"].get(str(i), 0)
        if count > 0:
            meds.append(f"💊 {MEDKITS[i][0]} × {count}")
    if not meds:
        meds = ["💊 Aptechka yo‘q"]
    shield_text = value["shield"] if value.get("shield") else "Himoya yo‘q"
    await show(
        update,
        f"🎒 INVENTAR\n\n"
        f"🛡️ {shield_text}\n"
        f"🛡️ Himoya HP: {value['shield_hp']}/{value['shield_max']}\n\n"
        + "\n".join(meds),
        back(),
    )


async def buy(update, kind, index):
    uid = update.effective_user.id
    value = get_user(uid)
    if kind == "shield":
        if value.get("shield"):
            return await update.callback_query.answer("Sizda allaqachon himoya bor.", show_alert=True)
        name, currency, price, hp = SHIELDS[index]
        if value[currency] < price:
            return await update.callback_query.answer(f"{currency_label(currency, price)} yetarli emas.", show_alert=True)
        value[currency] -= price
        value["shield"] = name
        value["shield_hp"] = hp
        value["shield_max"] = hp
        value["shield_regen"] = datetime.now().isoformat()
        save_user(uid, value)
        await update.callback_query.answer("✅ Himoya sotib olindi!")
        await catalog(update, "shield")
    else:
        name, currency, price, amount = MEDKITS[index]
        if value[currency] < price:
            return await update.callback_query.answer(f"{currency_label(currency, price)} yetarli emas.", show_alert=True)
        value[currency] -= price
        value["medkits"][str(index)] = value["medkits"].get(str(index), 0) + 1
        save_user(uid, value)
        await update.callback_query.answer("✅ Aptechka sotib olindi!")
        await catalog(update, "medkit")


async def fight(update, context):
    uid = update.effective_user.id
    value = get_user(uid)
    if value["hp"] <= 0:
        await show(update, "💀 Siz mag‘lub bo‘lgansiz. Yangi jang boshlash mumkin emas.", back())
        return
    enemy_hp = random.randint(80, 250)
    GAMES[uid] = {
        "hp": enemy_hp,
        "max": enemy_hp,
        "name": random.choice(["Qaroqchi", "Gangster", "Boss"]),
        "damage": random.randint(8, 30),
        "med_used": 0,
        "shield_used": False,
    }
    await fight_screen(update, uid)


async def fight_screen(update, uid):
    game = GAMES.get(uid)
    value = get_user(uid)
    if not game:
        await show(update, "Faol jang yo‘q.", back())
        return
    buttons = [
        [InlineKeyboardButton("⚔️ Hujum", callback_data="fight:attack"), InlineKeyboardButton("💊 Aptechka", callback_data="fight:heal")],
        [InlineKeyboardButton("🛡️ Himoyani yoqish", callback_data="fight:block"), InlineKeyboardButton("🏃 Qochish", callback_data="fight:flee")],
    ]
    await show(
        update,
        f"⚔️ JANG\n\n"
        f"👾 {game['name']}\n"
        f"❤️ Raqib: {game['hp']}/{game['max']}\n"
        f"👤 Siz: {value['hp']}/{value['max_hp']}\n"
        f"🛡️ Himoya: {value['shield_hp']}/{value['shield_max']}\n"
        f"💊 Aptechka ishlatilgan: {game['med_used']}/3",
        InlineKeyboardMarkup(buttons),
    )


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
        await show(update, "🏃 Jangdan qochdingiz.", back())
        return

    if action == "block":
        game["shield_used"] = True
        await show(update, "🛡️ Himoya yoqildi. Keyingi dushman hujumi bloklanadi.", back())
        return

    if action == "heal":
        if game["med_used"] >= 3:
            await query.answer("Bu jangda 3 ta aptechka limiti tugadi.", show_alert=True)
            return
        if value["hp"] >= value["max_hp"]:
            await query.answer("HP 100/100. Aptechka ishlatilmaydi.", show_alert=True)
            return
        choice = None
        for i in range(len(MEDKITS)):
            if value["medkits"].get(str(i), 0) > 0:
                choice = i
                break
        if choice is None:
            await query.answer("Inventarda aptechka yo‘q.", show_alert=True)
            return
        _, _, _, heal_amount = MEDKITS[choice]
        value["medkits"][str(choice)] -= 1
        if value["medkits"][str(choice)] <= 0:
            value["medkits"].pop(str(choice), None)
        value["hp"] = min(value["max_hp"], value["hp"] + heal_amount)
        game["med_used"] += 1
        save_user(uid, value)
        await fight_screen(update, uid)
        return

    weapon_index = value["selected_weapon"]
    weapon_entry = value["weapons"].get(str(weapon_index), {"level": 1, "xp": 0})
    base_damage = WEAPONS[weapon_index][3]
    damage = random.randint(max(1, base_damage - 5), base_damage + 10) + (weapon_entry["level"] - 1) * 5
    game["hp"] -= damage
    if game["hp"] <= 0:
        xp_gain = 10 if weapon_entry["level"] <= 4 else 7 if weapon_entry["level"] <= 9 else 5
        weapon_entry["xp"] += xp_gain
        while weapon_entry["xp"] >= 100 and weapon_entry["level"] < 15:
            weapon_entry["xp"] -= 100
            weapon_entry["level"] += 1
        if weapon_entry["level"] >= 15:
            weapon_entry["xp"] = 99
        reward = random.randint(100, 500)
        value["wins"] += 1
        value["money"] += reward
        value["weapons"][str(weapon_index)] = weapon_entry
        save_user(uid, value)
        GAMES.pop(uid, None)
        await show(update, f"🏆 G‘ALABA!\n💰 Mukofot: {reward}\n⭐ +{xp_gain} XP | Level: {weapon_entry['level']}/15", back())
        return

    incoming = game["damage"]
    if game["shield_used"]:
        incoming = 0
        game["shield_used"] = False
    else:
        shield_left = value["shield_hp"]
        if shield_left > 0:
            absorbed = min(shield_left, incoming)
            value["shield_hp"] -= absorbed
            incoming -= absorbed
        if incoming > 0:
            value["hp"] = max(0, value["hp"] - incoming)

    if value["hp"] <= 0:
        value["losses"] += 1
        value["hp"] = 100
        save_user(uid, value)
        GAMES.pop(uid, None)
        await show(update, "💀 HP 0/100. Siz jangda mag‘lub bo‘ldingiz.", back())
        return

    save_user(uid, value)
    await fight_screen(update, uid)


def ready_for(value, field, minutes):
    if not value.get(field):
        return True
    try:
        return datetime.now() >= datetime.fromisoformat(value[field]) + timedelta(minutes=minutes)
    except ValueError:
        return True


async def earn(update, kind):
    uid = update.effective_user.id
    value = get_user(uid)
    field_map = {"work": ("last_work", 5), "crime": ("last_crime", 10), "rob": ("last_rob", 15)}
    field, minutes = field_map[kind]
    if not ready_for(value, field, minutes):
        await show(update, "⏳ Kutish vaqti hali tugamadi.", back())
        return
    value[field] = datetime.now().isoformat()
    chance = {"work": 1.0, "crime": 0.65, "rob": 0.45}[kind]
    success = random.random() < chance
    if success:
        amount = random.randint(100, 500) if kind == "work" else random.randint(200, 2500)
        value["money"] += amount
        text = f"✅ Muvaffaqiyat!\n💰 Daromad: {amount}"
    else:
        loss = min(value["money"], random.randint(50, 300))
        value["money"] -= loss
        text = f"❌ Muvaffaqiyatsiz!\n💸 Yo‘qotish: {loss}"
    save_user(uid, value)
    await show(update, text, back())


def clan_meta(clan_name):
    clans = read(CLANS_FILE)
    clan = clans.get(clan_name, {})
    clan.setdefault("bank", 0)
    clan.setdefault("level", 1)
    clan.setdefault("xp", 0)
    clan.setdefault("members", [])
    clan.setdefault("leader", "")
    clan.setdefault("helpers", [])
    clan.setdefault("pending", [])
    clan.setdefault("logs", [])
    clans[clan_name] = clan
    write(CLANS_FILE, clans)
    return clan


async def clan(update, context):
    uid = update.effective_user.id
    value = get_user(uid)
    clans = read(CLANS_FILE)
    if not value.get("clan"):
        await show(update, "👥 Siz clan a’zosi emassiz.\n/createclan Nomi — yaratish\n/joinclan Nomi — qo‘shilish", back())
        return
    clan_name = value["clan"]
    clan_data = clan_meta(clan_name)
    members = clan_data.get("members", [])
    await show(
        update,
        f"👥 CLAN: {clan_name}\n\n"
        f"👥 A’zolar: {len(members)}\n"
        f"💰 Bank: {clan_data.get('bank', 0)}\n"
        f"👑 Lider: {clan_data.get('leader', '-')}\n"
        f"⭐ Level: {clan_data.get('level', 1)}\n"
        f"⭐ XP: {clan_data.get('xp', 0)}/100\n"
        f"🧩 Yordamchilar: {len(clan_data.get('helpers', []))}",
        back(),
    )


async def create_clan(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /createclan ClanNomi")
        return
    uid = update.effective_user.id
    value = get_user(uid)
    name = " ".join(context.args).strip()[:32]
    clans = read(CLANS_FILE)
    if value.get("clan"):
        await update.message.reply_text("Siz allaqachon clandasiz.")
        return
    if name in clans:
        await update.message.reply_text("Bu clan mavjud.")
        return
    clans[name] = {
        "leader": str(uid),
        "members": [str(uid)],
        "bank": 0,
        "level": 1,
        "xp": 0,
        "helpers": [],
        "pending": [],
        "logs": [f"{datetime.now().isoformat()} | {name} clani yaratildi."],
    }
    write(CLANS_FILE, clans)
    value["clan"] = name
    save_user(uid, value)
    await update.message.reply_text(f"✅ {name} clani yaratildi. Siz rahbar bo‘ldingiz.", reply_markup=menu())


async def join_clan(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /joinclan ClanNomi")
        return
    uid = update.effective_user.id
    value = get_user(uid)
    clans = read(CLANS_FILE)
    name = " ".join(context.args).strip()
    if value.get("clan"):
        await update.message.reply_text("Avval hozirgi clandan chiqing.")
        return
    if name not in clans:
        await update.message.reply_text("Bunday clan topilmadi.")
        return
    clans[name].setdefault("members", []).append(str(uid))
    write(CLANS_FILE, clans)
    value["clan"] = name
    save_user(uid, value)
    await update.message.reply_text(f"✅ {name} claniga qo‘shildingiz.", reply_markup=menu())


async def leave_clan(update, context):
    uid = update.effective_user.id
    value = get_user(uid)
    if not value.get("clan"):
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


async def clans_list(update, context):
    clans = read(CLANS_FILE)
    if not clans:
        await show(update, "🧭 Hozircha hech qanday clan yo‘q.", back())
        return
    lines = ["🏰 CLANLAR RO‘YXATI\n"]
    for name, clan in sorted(clans.items(), key=lambda item: item[1].get("level", 1), reverse=True):
        lines.append(f"• {name} | 👥 {len(clan.get('members', []))} | 👑 {clan.get('leader', '-')} | ⭐ L{clan.get('level', 1)}")
    await show(update, "\n".join(lines), back())


async def clan_admin(update, context):
    uid = update.effective_user.id
    value = get_user(uid)
    clan_name = value.get("clan")
    if not clan_name:
        await show(update, "Siz clan a’zosi emassiz.", back())
        return
    clans = read(CLANS_FILE)
    clan = clans.get(clan_name)
    if not clan:
        await show(update, "Clan topilmadi.", back())
        return
    is_leader = clan.get("leader") == str(uid)
    text = f"🏰 CLAN ADMIN\n\nClan: {clan_name}\n👑 Rahbar: {is_leader}\n\n"
    text += "[1] A'zolarni ko'rish\n"
    text += "[2] A'zo qabul qilish\n"
    text += "[3] A'zo chiqarish\n"
    text += "[4] Yordamchi tayinlash\n"
    text += "[5] Yordamchilikni olib tashlash\n"
    if not is_leader:
        text += "\n⚠️ Siz rahbar emassiz. Faqat rahbar boshqaradi."
    await show(update, text, back())


async def request_to_join_clan(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /requestclan ClanNomi")
        return
    uid = update.effective_user.id
    value = get_user(uid)
    if value.get("clan"):
        await update.message.reply_text("Avval joriy clandan chiqib oling.")
        return
    clan_name = " ".join(context.args).strip()
    clans = read(CLANS_FILE)
    clan = clans.get(clan_name)
    if not clan:
        await update.message.reply_text("Bunday clan topilmadi.")
        return
    pending = clan.setdefault("pending", [])
    target = str(uid)
    if not any(item.get("user") == target for item in pending):
        pending.append({"user": target, "time": datetime.now().isoformat()})
        clan.setdefault("logs", []).append(f"{datetime.now().isoformat()} | {uid} clan so‘rovi yubordi.")
        write(CLANS_FILE, clans)
        await update.message.reply_text(f"✅ {clan_name} claniga so‘rov yuborildi.")
    else:
        await update.message.reply_text("Siz allaqachon so‘rov yuborgan bo‘lsangiz.")


async def accept_clan_member(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /acceptclan USER_ID")
        return
    uid = update.effective_user.id
    value = get_user(uid)
    clan_name = value.get("clan")
    if not clan_name:
        await update.message.reply_text("Siz clan a’zosi emassiz.")
        return
    clans = read(CLANS_FILE)
    clan = clans.get(clan_name)
    if not clan:
        await update.message.reply_text("Clan topilmadi.")
        return
    if clan.get("leader") != str(uid):
        await update.message.reply_text("Faqat rahbar qabul qila oladi.")
        return
    try:
        target_uid = str(int(context.args[0]))
    except ValueError:
        await update.message.reply_text("USER_ID son bo‘lishi kerak.")
        return
    pending = clan.get("pending", [])
    clan["pending"] = [item for item in pending if item.get("user") != target_uid]
    members = clan.setdefault("members", [])
    if target_uid not in members:
        members.append(target_uid)
    clan.setdefault("logs", []).append(f"{datetime.now().isoformat()} | {target_uid} clan a'zosi qabul qilindi.")
    write(CLANS_FILE, clans)
    tuser = get_user(int(target_uid))
    tuser["clan"] = clan_name
    save_user(int(target_uid), tuser)
    await update.message.reply_text(f"✅ {target_uid} clan a’zosi qabul qilindi.")


async def reject_clan_member(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /rejectclan USER_ID")
        return
    uid = update.effective_user.id
    value = get_user(uid)
    clan_name = value.get("clan")
    if not clan_name:
        await update.message.reply_text("Siz clan a’zosi emassiz.")
        return
    clans = read(CLANS_FILE)
    clan = clans.get(clan_name)
    if not clan:
        await update.message.reply_text("Clan topilmadi.")
        return
    if clan.get("leader") != str(uid):
        await update.message.reply_text("Faqat rahbar rad qila oladi.")
        return
    try:
        target_uid = str(int(context.args[0]))
    except ValueError:
        await update.message.reply_text("USER_ID son bo‘lishi kerak.")
        return
    clan["pending"] = [item for item in clan.get("pending", []) if item.get("user") != target_uid]
    clan.setdefault("logs", []).append(f"{datetime.now().isoformat()} | {target_uid} so‘rovi rad etildi.")
    write(CLANS_FILE, clans)
    await update.message.reply_text(f"❌ {target_uid} so‘rovi rad etildi.")


async def kick_clan_member(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /kickclan USER_ID")
        return
    uid = update.effective_user.id
    value = get_user(uid)
    clan_name = value.get("clan")
    if not clan_name:
        await update.message.reply_text("Siz clan a’zosi emassiz.")
        return
    clans = read(CLANS_FILE)
    clan = clans.get(clan_name)
    if not clan:
        await update.message.reply_text("Clan topilmadi.")
        return
    if clan.get("leader") != str(uid):
        await update.message.reply_text("Faqat rahbar a'zo chiqarishi mumkin.")
        return
    try:
        target_uid = str(int(context.args[0]))
    except ValueError:
        await update.message.reply_text("USER_ID son bo‘lishi kerak.")
        return
    if target_uid == str(uid):
        await update.message.reply_text("Rahbar o‘zi chiqib ketolmaydi. /leaveclan ishlating.")
        return
    members = clan.get("members", [])
    if target_uid not in members:
        await update.message.reply_text("Bu foydalanuvchi clan a’zosi emas.")
        return
    clan["members"] = [member for member in members if member != target_uid]
    clan.setdefault("logs", []).append(f"{datetime.now().isoformat()} | {target_uid} clan a'zolaridan chiqarildi.")
    write(CLANS_FILE, clans)
    tuser = get_user(int(target_uid))
    tuser["clan"] = None
    save_user(int(target_uid), tuser)
    await update.message.reply_text(f"✅ {target_uid} clan a’zolaridan chiqarildi.")


async def assign_helper(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /assignhelper USER_ID")
        return
    uid = update.effective_user.id
    value = get_user(uid)
    clan_name = value.get("clan")
    if not clan_name:
        await update.message.reply_text("Siz clan a’zosi emassiz.")
        return
    clans = read(CLANS_FILE)
    clan = clans.get(clan_name)
    if not clan:
        await update.message.reply_text("Clan topilmadi.")
        return
    if clan.get("leader") != str(uid):
        await update.message.reply_text("Faqat rahbar yordamchi tayinlaydi.")
        return
    try:
        target_uid = str(int(context.args[0]))
    except ValueError:
        await update.message.reply_text("USER_ID son bo‘lishi kerak.")
        return
    if target_uid not in clan.get("members", []):
        await update.message.reply_text("Bu foydalanuvchi clan a’zosi emas.")
        return
    helpers = clan.setdefault("helpers", [])
    if target_uid not in helpers:
        helpers.append(target_uid)
    clan.setdefault("logs", []).append(f"{datetime.now().isoformat()} | {target_uid} yordamchi etib tayinlandi.")
    write(CLANS_FILE, clans)
    await update.message.reply_text(f"✅ {target_uid} yordamchi etib tayinlandi.")


async def remove_helper(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /removehelper USER_ID")
        return
    uid = update.effective_user.id
    value = get_user(uid)
    clan_name = value.get("clan")
    if not clan_name:
        await update.message.reply_text("Siz clan a’zosi emassiz.")
        return
    clans = read(CLANS_FILE)
    clan = clans.get(clan_name)
    if not clan:
        await update.message.reply_text("Clan topilmadi.")
        return
    if clan.get("leader") != str(uid):
        await update.message.reply_text("Faqat rahbar yordamchini olib tashlashi mumkin.")
        return
    try:
        target_uid = str(int(context.args[0]))
    except ValueError:
        await update.message.reply_text("USER_ID son bo‘lishi kerak.")
        return
    helpers = clan.get("helpers", [])
    if target_uid in helpers:
        clan["helpers"] = [member for member in helpers if member != target_uid]
        clan.setdefault("logs", []).append(f"{datetime.now().isoformat()} | {target_uid} yordamchiliktan olib tashlandi.")
        write(CLANS_FILE, clans)
        await update.message.reply_text(f"✅ {target_uid} yordamchiliktan olib tashlandi.")
    else:
        await update.message.reply_text("Bu foydalanuvchi yordamchi emas.")


async def clan_donate(update, context):
    if not context.args:
        await update.message.reply_text("Foydalanish: /donateclan MIQDOR")
        return
    uid = update.effective_user.id
    value = get_user(uid)
    clan_name = value.get("clan")
    if not clan_name:
        await update.message.reply_text("Siz clan a’zosi emassiz.")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("MIQDOR son bo‘lishi kerak.")
        return
    if amount <= 0:
        await update.message.reply_text("Miqdor 0 dan katta bo‘lishi kerak.")
        return
    if value["money"] < amount:
        await update.message.reply_text("Pul yetarli emas.")
        return
    value["money"] -= amount
    clans = read(CLANS_FILE)
    clan = clans.setdefault(clan_name, {"leader": str(uid), "members": [str(uid)], "bank": 0, "level": 1, "xp": 0, "helpers": [], "pending": [], "logs": []})
    clan["bank"] = clan.get("bank", 0) + amount
    clan["xp"] = clan.get("xp", 0) + max(1, amount // 100)
    while clan.get("xp", 0) >= 100:
        clan["xp"] -= 100
        clan["level"] = clan.get("level", 1) + 1
    clan.setdefault("logs", []).append(f"{datetime.now().isoformat()} | {uid} {amount} pul xayriya qildi.")
    write(CLANS_FILE, clans)
    save_user(uid, value)
    await update.message.reply_text(f"✅ {amount} pul clan bankiga qo‘shildi.")


async def clan_upgrade(update, context):
    uid = update.effective_user.id
    value = get_user(uid)
    clan_name = value.get("clan")
    if not clan_name:
        await update.message.reply_text("Siz clan a’zosi emassiz.")
        return
    clans = read(CLANS_FILE)
    clan = clans.get(clan_name)
    if not clan:
        await update.message.reply_text("Clan topilmadi.")
        return
    if clan.get("leader") != str(uid):
        await update.message.reply_text("Faqat rahbar clan levelini oshirishi mumkin.")
        return
    cost = 5000 + (clan.get("level", 1) * 3000)
    if clan.get("bank", 0) < cost:
        await update.message.reply_text(f"Clan bankida yetarli pul yo‘q. Kerak: {cost}.")
        return
    clan["bank"] -= cost
    clan["level"] = clan.get("level", 1) + 1
    clan["xp"] = 0
    clan.setdefault("logs", []).append(f"{datetime.now().isoformat()} | Rahbar {uid} clan levelini oshirdi.")
    write(CLANS_FILE, clans)
    await update.message.reply_text(f"✅ Clan leveli oshirildi. Yangi level: {clan['level']}")


async def callback(update, context):
    data = update.callback_query.data
    if data == "main":
        await start(update, context)
    elif data == "noop":
        await update.callback_query.answer()
    elif data.startswith("wpage:"):
        await weapon_shop(update, int(data.split(":")[1]))
    elif data.startswith("weapon:"):
        await weapon_detail(update, int(data.split(":")[1]))
    elif data.startswith("selectweapon:"):
        index = int(data.split(":")[1])
        value = get_user(update.effective_user.id)
        if str(index) in value["weapons"]:
            value["selected_weapon"] = index
            save_user(update.effective_user.id, value)
            await weapon_detail(update, index)
    elif data.startswith("buyweapon:"):
        index = int(data.split(":")[1])
        value = get_user(update.effective_user.id)
        if str(index) in value["weapons"]:
            await update.callback_query.answer("Bu qurol inventarda bor.", show_alert=True)
            return
        name, currency, price, _ = WEAPONS[index]
        if value[currency] < price:
            await update.callback_query.answer(f"{currency_label(currency, price)} yetarli emas.", show_alert=True)
            return
        value[currency] -= price
        value["weapons"][str(index)] = {"level": 1, "xp": 0}
        save_user(update.effective_user.id, value)
        await update.callback_query.answer("✅ Quroldan birini sotib oldingiz!")
        await weapon_detail(update, index)
    elif data.startswith("shop:"):
        _, kind, index = data.split(":")
        await buy(update, kind, int(index))
    elif data.startswith("fight:"):
        await fight_action(update, data.split(":", 1)[1])
    else:
        await update.callback_query.answer()


async def text_handler(update, context):
    actions = {
        "⚔️ Jang": fight,
        "👤 Profil": profile,
        "🔫 Qurollar": lambda u, c: weapon_shop(u, 0),
        "🛡️ Himoya": lambda u, c: catalog(u, "shield"),
        "💊 Aptechka": lambda u, c: catalog(u, "medkit"),
        "🎒 Inventar": inventory,
        "💼 Ishlash": lambda u, c: earn(u, "work"),
        "🕵️ Jinoyat": lambda u, c: earn(u, "crime"),
        "💰 O‘g‘rilik": lambda u, c: earn(u, "rob"),
        "👥 Clan": clan,
        "🏆 Reyting": leaderboard,
        "👑 Admin": admin,
    }
    handler = actions.get(update.message.text)
    if handler:
        await handler(update, context)
    else:
        await update.message.reply_text("Menyudan tanlang.", reply_markup=menu())


async def leaderboard(update, context):
    users = read(USERS_FILE)
    top = sorted(users.items(), key=lambda item: (item[1].get("wins", 0), item[1].get("money", 0)), reverse=True)[:10]
    lines = ["🏆 TOP 10 O‘YINCHI\n"]
    for index, (uid, user_data) in enumerate(top, 1):
        lines.append(f"{index}. {user_data.get('first_name') or uid} — 🏆 {user_data.get('wins', 0)} | 💰 {user_data.get('money', 0)}")
    await show(update, "\n".join(lines), back())


async def admin(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await show(update, "⛔ Siz admin emassiz.", back())
        return
    await show(update, "👑 ADMIN\n/addmoney ID MIQDOR\n/adddiamond ID MIQDOR\n/broadcast MATN\n/users", back())


async def add_money(update, context):
    if update.effective_user.id not in ADMIN_IDS or len(context.args) != 2:
        return
    try:
        uid = int(context.args[0])
        amount = int(context.args[1])
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
        uid = int(context.args[0])
        amount = int(context.args[1])
        value = get_user(uid)
        value["diamonds"] += amount
        save_user(uid, value)
        await update.message.reply_text("✅ Almas berildi.")
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
    application.add_handler(CommandHandler("clans", clans_list))
    application.add_handler(CommandHandler("clanadmin", clan_admin))
    application.add_handler(CommandHandler("requestclan", request_to_join_clan))
    application.add_handler(CommandHandler("acceptclan", accept_clan_member))
    application.add_handler(CommandHandler("rejectclan", reject_clan_member))
    application.add_handler(CommandHandler("kickclan", kick_clan_member))
    application.add_handler(CommandHandler("assignhelper", assign_helper))
    application.add_handler(CommandHandler("removehelper", remove_helper))
    application.add_handler(CommandHandler("donateclan", clan_donate))
    application.add_handler(CommandHandler("clanupgrade", clan_upgrade))
    application.add_handler(CommandHandler("addmoney", add_money))
    application.add_handler(CommandHandler("adddiamond", add_diamond))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("users", users_cmd))
    application.add_handler(CallbackQueryHandler(callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
