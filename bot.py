import json
import os
import random
import threading
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {7979870096}
USERS_FILE = Path("users.json")
CLANS_FILE = Path("clans.json")
LOCK = threading.RLock()
GAMES = {}

WEAPONS = [
    ("🔫 Pistolet", "money", 0, 10), ("🔫 Revolver", "money", 50000, 12), ("🔫 Glock", "money", 75000, 14),
    ("🔫 UZI", "money", 100000, 16), ("🔫 MP5", "money", 150000, 18), ("🔫 MP7", "money", 200000, 20),
    ("🔫 P90", "money", 250000, 22), ("🔫 AK-47", "money", 300000, 25), ("🔫 M4A1", "money", 350000, 27),
    ("🔫 SCAR-L", "money", 400000, 29), ("🔫 FAMAS", "money", 450000, 31), ("🔫 G36", "money", 500000, 33),
    ("🔫 Shotgun", "money", 550000, 36), ("🔫 SPAS-12", "money", 650000, 39), ("🔫 SVD", "money", 750000, 42),
    ("🔫 Kar98k", "money", 850000, 45), ("🔫 AWM", "money", 1000000, 50), ("🏹 Arbalet", "money", 600000, 35),
    ("🏹 Kamon", "money", 400000, 30), ("🔱 Nayza", "money", 250000, 28), ("⚔️ Qilich", "money", 700000, 40),
    ("🪓 Bolta", "money", 450000, 34), ("🗡️ Machete", "money", 350000, 32), ("💥 Granatomyot", "money", 1500000, 60),
    ("⚡ Plazma quroli", "money", 2500000, 70),
    ("🔥 Inferno Pistolet", "diamonds", 156, 25), ("⚡ Thunder Revolver", "diamonds", 234, 28),
    ("☠️ Venom Glock", "diamonds", 312, 30), ("🔥 Inferno UZI", "diamonds", 390, 32), ("⚡ Storm MP5", "diamonds", 468, 35),
    ("☠️ Venom MP7", "diamonds", 546, 37), ("🔥 Phoenix P90", "diamonds", 624, 40), ("⚡ Thunder AK", "diamonds", 780, 43),
    ("🔥 Inferno M4", "diamonds", 936, 46), ("☠️ Venom SCAR", "diamonds", 1092, 49), ("⚡ Storm FAMAS", "diamonds", 1248, 52),
    ("🔥 Dragon G36", "diamonds", 1404, 55), ("💀 Hell Shotgun", "diamonds", 1560, 58), ("⚡ Thunder SPAS", "diamonds", 1872, 61),
    ("☠️ Venom SVD", "diamonds", 2184, 64), ("🔥 Dragon Kar98k", "diamonds", 2496, 67), ("👑 Golden AWM", "diamonds", 3120, 70),
    ("⚡ Storm Arbalet", "diamonds", 3432, 73), ("🔥 Phoenix Kamon", "diamonds", 3900, 76), ("🐉 Dragon Nayza", "diamonds", 4680, 80),
    ("⚔️ Demon Qilich", "diamonds", 5460, 84), ("☠️ Reaper Bolta", "diamonds", 6240, 88), ("🔥 Inferno Machete", "diamonds", 7020, 92),
    ("💥 Apocalypse Launcher", "diamonds", 7800, 100), ("👑 Legendary Plasma", "diamonds", 15600, 120),
]

SHIELDS = [
    ("🪵 Oddiy Himoya", "money", 50000, 50), ("🥉 Kuchli Himoya", "money", 100000, 75),
    ("🥈 Temir Himoya", "money", 175000, 100), ("🥇 Po‘lat Himoya", "money", 250000, 125),
    ("🛡️ Titan Himoya", "money", 350000, 150), ("🔩 Maxsus Himoya", "money", 500000, 200),
    ("💎 Diamond Himoya", "diamonds", 100, 250), ("⚡ Energiya Himoyasi", "diamonds", 200, 300),
    ("🔥 Inferno Himoya", "diamonds", 350, 400), ("👑 Legendary Himoya", "diamonds", 600, 500),
]

MEDKITS = [
    ("💊 Kichik Aptechka", "money", 1000, 10), ("💊 Oddiy Aptechka", "money", 2000, 15),
    ("💊 Yaxshi Aptechka", "money", 3500, 20), ("💊 Kuchli Aptechka", "money", 5000, 25),
    ("💊 Katta Aptechka", "money", 7500, 30), ("💊 Super Aptechka", "money", 10000, 40),
    ("💊 Mega Aptechka", "money", 15000, 50), ("💊 Ultra Aptechka", "money", 25000, 60),
    ("💎 Premium Aptechka", "diamonds", 40, 70), ("👑 Legendary Aptechka", "diamonds", 75, 75),
]


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
        temp = str(path) + ".tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp, path)


def blank_user():
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


def migrate(u):
    base = blank_user()
    for key, value in base.items():
        u.setdefault(key, value)
    if "weapon_idx" in u and "selected_weapon" not in u:
        u["selected_weapon"] = u["weapon_idx"]
    if "armor" in u and not u.get("shield") and u.get("armor"):
        u["shield"] = "🪵 Oddiy Himoya"
        u["shield_max"] = 50
        u["shield_hp"] = min(50, int(u["armor"]))
    u.setdefault("weapons", {})
    u["weapons"].setdefault("0", {"level": 1, "xp": 0})
    for key, item in list(u["weapons"].items()):
        item.setdefault("level", 1)
        item.setdefault("xp", 0)
        item["level"] = max(1, min(15, int(item["level"])))
        item["xp"] = max(0, min(99, int(item["xp"])))
    u.setdefault("medkits", {})
    u.pop("armor", None)
    u.pop("weapon_idx", None)
    u.pop("weapon", None)
    return u


def get_user(uid):
    users = read(USERS_FILE)
    key = str(uid)
    u = migrate(users.get(key, blank_user()))
    if u.get("shield") and u.get("shield_hp", 0) < u.get("shield_max", 0):
        last = u.get("shield_regen")
        now = datetime.now()
        if not last:
            u["shield_regen"] = now.isoformat()
        else:
            try:
                last_dt = datetime.fromisoformat(last)
                elapsed = int((now - last_dt).total_seconds() // 1800)
                if elapsed > 0:
                    u["shield_hp"] = min(u["shield_max"], u["shield_hp"] + elapsed)
                    u["shield_regen"] = (last_dt + timedelta(minutes=30 * elapsed)).isoformat()
            except ValueError:
                u["shield_regen"] = now.isoformat()
    users[key] = u
    write(USERS_FILE, users)
    return u


def save_user(uid, u):
    users = read(USERS_FILE)
    users[str(uid)] = migrate(u)
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
        q = update.callback_query
        try:
            await q.answer()
        except Exception:
            pass
        try:
            await q.edit_message_text(text, reply_markup=markup)
        except Exception:
            await q.message.reply_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


def currency_label(currency, amount):
    if amount == 0:
        return "Bepul"
    return f"{amount:,} {'💰' if currency == 'money' else '💎'}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id)
    u.update(first_name=user.first_name or "", username=user.username or "")
    save_user(user.id, u)
    await show(
        update,
        f"Salom, {user.first_name}! 🎮\n\n💰 Pul: {u['money']:,}\n💎 Almas: {u['diamonds']}\n❤️ HP: {u['hp']}/{u['max_hp']}\n🛡️ Himoya: {u['shield_hp']}/{u['shield_max']}\n🔫 Qurol: {WEAPONS[u['selected_weapon']][0]}",
        menu(),
    )


async def profile(update, context):
    uid = update.effective_user.id
    u = get_user(uid)
    weapon_index = u["selected_weapon"]
    weapon = WEAPONS[weapon_index]
    entry = u["weapons"].get(str(weapon_index), {"level": 1, "xp": 0})
    total = u["wins"] + u["losses"]
    rate = round(u["wins"] * 100 / total, 1) if total else 0
    damage = weapon[3] + (entry["level"] - 1) * 5
    await show(
        update,
        f"👤 PROFIL\n\n🆔 ID: {uid}\n💰 Pul: {u['money']:,}\n💎 Almas: {u['diamonds']}\n❤️ HP: {u['hp']}/{u['max_hp']}\n🛡️ Himoya: {u['shield_hp']}/{u['shield_max']}\n🔫 {weapon[0]} | Level {entry['level']} | XP {entry['xp']}/100\n⚔️ Zarar: {damage}\n🏆 G‘alaba: {u['wins']} | ❌ Mag‘lubiyat: {u['losses']} | 📈 {rate}%\n👥 Clan: {u['clan'] or 'yo‘q'}",
        back(),
    )


async def weapon_shop(update, page=0):
    uid = update.effective_user.id
    u = get_user(uid)
    page = max(0, min(4, int(page)))
    rows = []
    start_index = page * 10
    end_index = min(start_index + 10, len(WEAPONS))
    for i in range(start_index, end_index):
        name, currency, price, _ = WEAPONS[i]
        owned = str(i) in u["weapons"]
        current_level = u["weapons"].get(str(i), {"level": 0}).get("level", 0)
        mark = "✅" if i == u["selected_weapon"] else ("📦" if owned else "🔒")
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
        f"🔫 QUROLLAR {start_index + 1}–{end_index}/{len(WEAPONS)}\n💰 {u['money']:,} | 💎 {u['diamonds']}",
        InlineKeyboardMarkup(rows),
    )


async def weapon_detail(update, index):
    uid = update.effective_user.id
    u = get_user(uid)
    name, currency, price, base = WEAPONS[index]
    entry = u["weapons"].get(str(index), {"level": 1, "xp": 0})
    level = entry["level"]
    xp = entry["xp"]
    rows = []
    if str(index) not in u["weapons"]:
        rows.append([InlineKeyboardButton(f"🛒 Sotib olish — {currency_label(currency, price)}", callback_data=f"buyweapon:{index}")])
    else:
        if index != u["selected_weapon"]:
            rows.append([InlineKeyboardButton("🎯 Tanlash", callback_data=f"selectweapon:{index}")])
        else:
            rows.append([InlineKeyboardButton("✅ Tanlangan", callback_data="noop")])
    rows.append([InlineKeyboardButton("🔙 Qurollar", callback_data="wpage:0")])
    await show(
        update,
        f"{name}\n\n💳 Narx: {currency_label(currency, price)}\n⚔️ Zarar: {base + (level - 1) * 5}\n⭐ Level: {level}/15\n📊 XP: {xp}/100\n\nHar muvaffaqiyatli hujum +XP beradi. 100 XP = keyingi level.",
        InlineKeyboardMarkup(rows),
    )


async def catalog(update, kind, page=0):
    uid = update.effective_user.id
    u = get_user(uid)
    data = SHIELDS if kind == "shield" else MEDKITS
    rows = []
    for i, item in enumerate(data):
        name, currency, price, value = item
        if kind == "shield":
            label = f"{i + 1}. {name} — {currency_label(currency, price)} | {value} HP"
            if u.get("shield") == name:
                label = f"✅ {label}"
        else:
            count = u["medkits"].get(str(i), 0)
            label = f"{i + 1}. {name} — {currency_label(currency, price)} | +{value} HP ({count} dona)"
        rows.append([InlineKeyboardButton(label, callback_data=f"shop:{kind}:{i}")])
    rows.append([InlineKeyboardButton("🔙 Menyu", callback_data="main")])
    await show(
        update,
        f"🛒 {'HIMOYA' if kind == 'shield' else 'APTECHKA'}\n💰 {u['money']:,} | 💎 {u['diamonds']}\n\nAptechka jang boshlangandan keyin sotib olib bo‘lmaydi, lekin oldin sotib olinganlar ishlatiladi.",
        InlineKeyboardMarkup(rows),
    )


async def inventory(update, context):
    u = get_user(update.effective_user.id)
    meds = []
    for i in range(len(MEDKITS)):
        count = u["medkits"].get(str(i), 0)
        if count > 0:
            meds.append(f"💊 {MEDKITS[i][0]} × {count}")
    if not meds:
        meds = ["💊 Aptechka yo‘q"]
    shield_text = u["shield"] if u.get("shield") else "Himoya yo‘q"
    await show(
        update,
        f"🎒 INVENTAR\n\n🛡️ {shield_text}\n🛡️ Himoya HP: {u['shield_hp']}/{u['shield_max']}\n\n" + "\n".join(meds),
        back(),
    )


async def buy(update, kind, index):
    uid = update.effective_user.id
    u = get_user(uid)
    if kind == "shield":
        if u.get("shield"):
            return await update.callback_query.answer("Sizda allaqachon himoya bor.", show_alert=True)
        name, currency, price, hp = SHIELDS[index]
        if u[currency] < price:
            return await update.callback_query.answer(f"{currency_label(currency, price)} yetarli emas.", show_alert=True)
        u[currency] -= price
        u["shield"] = name
        u["shield_hp"] = hp
        u["shield_max"] = hp
        u["shield_regen"] = datetime.now().isoformat()
        save_user(uid, u)
        await update.callback_query.answer("✅ Himoya sotib olindi!")
        await catalog(update, "shield")
    else:
        name, currency, price, amount = MEDKITS[index]
        if u[currency] < price:
            return await update.callback_query.answer(f"{currency_label(currency, price)} yetarli emas.", show_alert=True)
        u[currency] -= price
        u["medkits"][str(index)] = u["medkits"].get(str(index), 0) + 1
        save_user(uid, u)
        await update.callback_query.answer("✅ Aptechka sotib olindi!")
        await catalog(update, "medkit")


async def fight(update, context):
    uid = update.effective_user.id
    u = get_user(uid)
    if u["hp"] <= 0:
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
    u = get_user(uid)
    if not game:
        await show(update, "Faol jang yo‘q.", back())
        return
    buttons = [
        [InlineKeyboardButton("⚔️ Hujum", callback_data="fight:attack"), InlineKeyboardButton("💊 Aptechka", callback_data="fight:heal")],
        [InlineKeyboardButton("🛡️ Himoyani yoqish", callback_data="fight:block"), InlineKeyboardButton("🏃 Qochish", callback_data="fight:flee")],
    ]
    await show(
        update,
        f"⚔️ JANG\n\n👾 {game['name']}\n❤️ Raqib: {game['hp']}/{game['max']}\n👤 Siz: {u['hp']}/{u['max_hp']}\n🛡️ Himoya: {u['shield_hp']}/{u['shield_max']}\n💊 Aptechka ishlatilgan: {game['med_used']}/3",
        InlineKeyboardMarkup(buttons),
    )


async def fight_action(update, action):
    uid = update.effective_user.id
    q = update.callback_query
    u = get_user(uid)
    game = GAMES.get(uid)
    if not game:
        await q.answer("Faol jang yo‘q.", show_alert=True)
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
            await q.answer("Bu jangda 3 ta aptechka limiti tugadi.", show_alert=True)
            return
        if u["hp"] >= u["max_hp"]:
            await q.answer("HP 100/100. Aptechka ishlatilmaydi.", show_alert=True)
            return
        choice = None
        for i in range(len(MEDKITS)):
            if u["medkits"].get(str(i), 0) > 0:
                choice = i
                break
        if choice is None:
            await q.answer("Inventarda aptechka yo‘q.", show_alert=True)
            return
        _, _, _, heal_amount = MEDKITS[choice]
        u["medkits"][str(choice)] -= 1
        if u["medkits"][str(choice)] <= 0:
            u["medkits"].pop(str(choice), None)
        u["hp"] = min(u["max_hp"], u["hp"] + heal_amount)
        game["med_used"] += 1
        save_user(uid, u)
        await fight_screen(update, uid)
        return

    weapon_index = u["selected_weapon"]
    entry = u["weapons"].get(str(weapon_index), {"level": 1, "xp": 0})
    base_damage = WEAPONS[weapon_index][3]
    damage = random.randint(max(1, base_damage - 5), base_damage + 10) + (entry["level"] - 1) * 5
    game["hp"] -= damage
    if game["hp"] <= 0:
        xp_gain = 10 if entry["level"] <= 4 else 7 if entry["level"] <= 9 else 5
        entry["xp"] += xp_gain
        while entry["xp"] >= 100 and entry["level"] < 15:
            entry["xp"] -= 100
            entry["level"] += 1
        if entry["level"] >= 15:
            entry["xp"] = 99
        reward = random.randint(100, 500)
        u["wins"] += 1
        u["money"] += reward
        save_user(uid, u)
        GAMES.pop(uid, None)
        await show(update, f"🏆 G‘ALABA!\n💰 Mukofot: {reward}\n⭐ +{xp_gain} XP | Level: {entry['level']}/15", back())
        return

    incoming = game["damage"]
    if game["shield_used"]:
        incoming = 0
        game["shield_used"] = False
    else:
        shield_left = u["shield_hp"]
        if shield_left > 0:
            absorbed = min(shield_left, incoming)
            u["shield_hp"] -= absorbed
            incoming -= absorbed
        if incoming > 0:
            u["hp"] = max(0, u["hp"] - incoming)

    if u["hp"] <= 0:
        u["losses"] += 1
        u["hp"] = 100
        save_user(uid, u)
        GAMES.pop(uid, None)
        await show(update, "💀 HP 0/100. Siz jangda mag‘lub bo‘ldingiz.", back())
        return

    save_user(uid, u)
    await fight_screen(update, uid)


def ready_for(u, field, minutes):
    if not u.get(field):
        return True
    try:
        return datetime.now() >= datetime.fromisoformat(u[field]) + timedelta(minutes=minutes)
    except ValueError:
        return True


async def earn(update, kind):
    uid = update.effective_user.id
    u = get_user(uid)
    field_map = {"work": ("last_work", 5), "crime": ("last_crime", 10), "rob": ("last_rob", 15)}
    field, minutes = field_map[kind]
    if not ready_for(u, field, minutes):
        await show(update, "⏳ Kutish vaqti hali tugamadi.", back())
        return
    u[field] = datetime.now().isoformat()
    chance = {"work": 1.0, "crime": 0.65, "rob": 0.45}[kind]
    success = random.random() < chance
    if success:
        amount = random.randint(100, 500) if kind == "work" else random.randint(200, 2500)
        u["money"] += amount
        text = f"✅ Muvaffaqiyat!\n💰 Daromad: {amount}"
    else:
        loss = min(u["money"], random.randint(50, 300))
        u["money"] -= loss
        text = f"❌ Muvaffaqiyatsiz!\n💸 Yo‘qotish: {loss}"
    save_user(uid, u)
    await show(update, text, back())


async def clan(update, context):
    uid = update.effective_user.id
    u = get_user(uid)
    clans = read(CLANS_FILE)
    if not u.get("clan"):
        await show(update, "👥 Siz clan a’zosi emassiz.\n/createclan Nomi — yaratish\n/joinclan Nomi — qo‘shilish", back())
        return
    current = clans.get(u["clan"], {})
    await show(
        update,
        f"👥 CLAN: {u['clan']}\n\n👥 A’zolar: {len(current.get('members', []))}\n💰 Bank: {current.get('bank', 0)}\n👑 Lider: {current.get('leader', '-')}"
        ,
        back(),
    )


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
    if name in clans:
        await update.message.reply_text("Bu clan mavjud.")
        return
    clans[name] = {"leader": str(uid), "members": [str(uid)], "bank": 0}
    write(CLANS_FILE, clans)
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
    if u.get("clan"):
        await update.message.reply_text("Avval hozirgi clandan chiqing.")
        return
    if name not in clans:
        await update.message.reply_text("Bunday clan topilmadi.")
        return
    clans[name].setdefault("members", []).append(str(uid))
    write(CLANS_FILE, clans)
    u["clan"] = name
    save_user(uid, u)
    await update.message.reply_text(f"✅ {name} claniga qo‘shildingiz.", reply_markup=menu())


async def leave_clan(update, context):
    uid = update.effective_user.id
    u = get_user(uid)
    if not u.get("clan"):
        await update.message.reply_text("Siz clanda emassiz.")
        return
    name = u["clan"]
    clans = read(CLANS_FILE)
    data = clans.get(name, {})
    data["members"] = [member for member in data.get("members", []) if member != str(uid)]
    if data.get("leader") == str(uid) and data["members"]:
        data["leader"] = data["members"][0]
    if data.get("members"):
        clans[name] = data
    else:
        clans.pop(name, None)
    write(CLANS_FILE, clans)
    u["clan"] = None
    save_user(uid, u)
    await update.message.reply_text("✅ Clandan chiqdingiz.", reply_markup=menu())


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
        u = get_user(uid)
        u["money"] += amount
        save_user(uid, u)
        await update.message.reply_text("✅ Pul berildi.")
    except ValueError:
        await update.message.reply_text("Foydalanish: /addmoney ID MIQDOR")


async def add_diamond(update, context):
    if update.effective_user.id not in ADMIN_IDS or len(context.args) != 2:
        return
    try:
        uid = int(context.args[0])
        amount = int(context.args[1])
        u = get_user(uid)
        u["diamonds"] += amount
        save_user(uid, u)
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
        u = get_user(update.effective_user.id)
        if str(index) in u["weapons"]:
            u["selected_weapon"] = index
            save_user(update.effective_user.id, u)
            await weapon_detail(update, index)
    elif data.startswith("buyweapon:"):
        index = int(data.split(":")[1])
        u = get_user(update.effective_user.id)
        if str(index) in u["weapons"]:
            await update.callback_query.answer("Bu qurol inventarda bor.", show_alert=True)
            return
        name, currency, price, _ = WEAPONS[index]
        if u[currency] < price:
            await update.callback_query.answer(f"{currency_label(currency, price)} yetarli emas.", show_alert=True)
            return
        u[currency] -= price
        u["weapons"][str(index)] = {"level": 1, "xp": 0}
        save_user(update.effective_user.id, u)
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
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("createclan", create_clan))
    app.add_handler(CommandHandler("joinclan", join_clan))
    app.add_handler(CommandHandler("leaveclan", leave_clan))
    app.add_handler(CommandHandler("addmoney", add_money))
    app.add_handler(CommandHandler("adddiamond", add_diamond))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
