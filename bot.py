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
USERS_FILE, CLANS_FILE = Path("users.json"), Path("clans.json")
DATA_LOCK = threading.RLock()
GAMES = {}

# (name, currency, price, level-1 damage)
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
HP_ITEMS = [(150, 10), (400, 30), (1000, 80), (3000, 250)]
ARMOR_ITEMS = [(150, 10), (400, 30), (1000, 80), (3000, 250)]
MEDKIT_ITEMS = [(150, 1), (400, 3), (1000, 8), (3000, 25)]


def read(path):
    with DATA_LOCK:
        try:
            with open(path, encoding="utf-8") as f: return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError): return {}


def write(path, data):
    with DATA_LOCK:
        tmp = str(path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def blank_user():
    return {"money": 500, "diamonds": 0, "hp": 100, "max_hp": 100, "armor": 0, "max_armor": 0,
            "medkits": 0, "selected_weapon": 0, "weapons": {"0": {"level": 1, "xp": 0}},
            "wins": 0, "losses": 0, "clan": None, "last_work": "", "last_crime": "", "last_rob": "",
            "first_name": "", "username": ""}


def migrate(value):
    base = blank_user()
    for key, default in base.items(): value.setdefault(key, default)
    # Migrate old weapon_idx/weapon saves safely.
    if "weapon_idx" in value and "selected_weapon" not in value: value["selected_weapon"] = value["weapon_idx"]
    value.setdefault("weapons", {})
    value["weapons"].setdefault("0", {"level": 1, "xp": 0})
    for i in range(len(WEAPONS)):
        entry = value["weapons"].setdefault(str(i), {"level": 1, "xp": 0})
        entry.setdefault("level", 1); entry.setdefault("xp", 0)
        entry["level"] = max(1, min(15, int(entry["level"])))
        entry["xp"] = max(0, min(99, int(entry["xp"])))
    value.pop("weapon_idx", None); value.pop("weapon", None)
    return value


def get_user(uid):
    users = read(USERS_FILE); key = str(uid)
    value = migrate(users.get(key, blank_user()))
    users[key] = value
    write(USERS_FILE, users)
    return value


def save_user(uid, value):
    users = read(USERS_FILE); users[str(uid)] = migrate(value); write(USERS_FILE, users)


def menu():
    return ReplyKeyboardMarkup([["⚔️ Jang", "👤 Profil"], ["🔫 Qurollar", "❤️ HP"], ["🛡️ Himoya", "💊 Aptechka"],
                                ["💼 Ishlash", "🕵️ Jinoyat"], ["💰 O‘g‘rilik", "👥 Clan"], ["🏆 Reyting", "👑 Admin"]], resize_keyboard=True)


def back(): return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menyu", callback_data="main")]])


async def show(update, text, markup=None):
    if update.callback_query:
        q = update.callback_query
        try: await q.answer()
        except Exception: pass
        try: await q.edit_message_text(text, reply_markup=markup)
        except Exception: await q.message.reply_text(text, reply_markup=markup)
    else: await update.message.reply_text(text, reply_markup=markup)


async def start(update, context):
    person = update.effective_user; u = get_user(person.id)
    u.update(first_name=person.first_name or "", username=person.username or ""); save_user(person.id, u)
    await show(update, f"Salom, {person.first_name}! 🎮\n\n💰 Pul: {u['money']}\n💎 Olmos: {u['diamonds']}\n❤️ HP: {u['hp']}/{u['max_hp']}\n🔫 Qurol: {WEAPONS[u['selected_weapon']][0]}", menu())


async def profile(update, context):
    uid = update.effective_user.id; u = get_user(uid); total = u["wins"] + u["losses"]
    rate = round(u["wins"] * 100 / total, 1) if total else 0; w = WEAPONS[u["selected_weapon"]]; e = u["weapons"][str(u["selected_weapon"])]
    await show(update, f"👤 PROFIL\n\n🆔 ID: {uid}\n💰 Pul: {u['money']}\n💎 Olmos: {u['diamonds']}\n❤️ HP: {u['hp']}/{u['max_hp']}\n🛡️ Himoya: {u['armor']}/{u['max_armor']}\n🔫 {w[0]} | Level {e['level']} | XP {e['xp']}/100\n⚔️ Zarar: {w[3] + (e['level']-1)*5}\n🏆 G‘alaba: {u['wins']} | ❌ Mag‘lubiyat: {u['losses']} | 📈 {rate}%\n👥 Clan: {u['clan'] or 'yo‘q'}", back())


def money_text(currency, price): return "Bepul" if price == 0 else f"{price:,} {'💰' if currency == 'money' else '💎'}"


async def weapon_shop(update, page=0):
    uid = update.effective_user.id; u = get_user(uid); page = max(0, min(4, int(page))); rows = []
    for i in range(page * 10, min(page * 10 + 10, 50)):
        name, currency, price, damage = WEAPONS[i]; e = u["weapons"].get(str(i)); owned = e is not None
        level = e["level"] if owned else 0
        mark = "✅" if i == u["selected_weapon"] else ("📦" if owned else "🔒")
        rows.append([InlineKeyboardButton(f"{mark} {i+1}. {name} L{level} | {damage + max(0, level-1)*5 if owned else damage} dmg | {money_text(currency, price)}", callback_data=f"weapon:{i}")])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"weappage:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/5", callback_data="noop"))
    if page < 4: nav.append(InlineKeyboardButton("➡️", callback_data=f"weappage:{page+1}"))
    rows.append(nav); rows.append([InlineKeyboardButton("🔙 Menyu", callback_data="main")])
    await show(update, f"🔫 QUROLLAR ({page*10+1}–{min(page*10+10,50)}/50)\n💰 {u['money']:,} | 💎 {u['diamonds']}", InlineKeyboardMarkup(rows))


async def weapon_detail(update, index):
    uid = update.effective_user.id; u = get_user(uid); name, currency, price, base = WEAPONS[index]; e = u["weapons"].get(str(index)); rows = []
    if e is None: rows.append([InlineKeyboardButton(f"🛒 Sotib olish — {money_text(currency, price)}", callback_data=f"buyweapon:{index}")])
    else:
        if index != u["selected_weapon"]: rows.append([InlineKeyboardButton("🎯 Tanlash", callback_data=f"selectweapon:{index}")])
        else: rows.append([InlineKeyboardButton("✅ Tanlangan", callback_data="noop")])
    rows.append([InlineKeyboardButton("🔙 Qurollar", callback_data="weappage:0")])
    level = e["level"] if e else 1; xp = e["xp"] if e else 0
    await show(update, f"{name}\n\n💳 Narx: {money_text(currency, price)}\n⚔️ Level 1 zarari: {base}\n⚔️ Hozirgi zarar: {base+(level-1)*5}\n⭐ Level: {level}/15\n📊 XP: {xp}/100\n\nHar muvaffaqiyatli hujum XP beradi. 100 XP = keyingi level.", InlineKeyboardMarkup(rows))


async def fight(update, context):
    uid = update.effective_user.id; u = get_user(uid)
    if u["hp"] <= 0: return await show(update, "❤️ HP tugagan. Avval HP sotib oling.", back())
    hp = random.randint(80, 250); GAMES[uid] = {"hp": hp, "max": hp, "name": random.choice(["Qaroqchi", "Gangster", "Boss"]), "damage": random.randint(8,30)}
    await fight_screen(update, uid)


async def fight_screen(update, uid):
    g = GAMES.get(uid); u = get_user(uid)
    if not g: return await show(update, "Faol jang yo‘q.", back())
    await show(update, f"⚔️ JANG\n\n👾 {g['name']}\n❤️ Raqib: {g['hp']}/{g['max']}\n👤 Siz: {u['hp']}/{u['max_hp']}\n🔫 {WEAPONS[u['selected_weapon']][0]}", InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Hujum", callback_data="fight:attack"), InlineKeyboardButton("💊 Davolanish", callback_data="fight:heal")], [InlineKeyboardButton("🏃 Qochish", callback_data="fight:flee")]]))


async def fight_action(update, action):
    uid = update.effective_user.id; u = get_user(uid); g = GAMES.get(uid)
    if not g: return await update.callback_query.answer("Faol jang yo‘q.", show_alert=True)
    if action == "flee": GAMES.pop(uid, None); return await show(update, "🏃 Jangdan qochdingiz.", back())
    if action == "heal":
        if u["medkits"] < 1: return await update.callback_query.answer("Aptechka yo‘q.", show_alert=True)
        u["medkits"] -= 1; u["hp"] = min(u["max_hp"], u["hp"] + 50)
    else:
        index = u["selected_weapon"]; e = u["weapons"][str(index)]; damage = WEAPONS[index][3] + (e["level"]-1)*5
        g["hp"] -= random.randint(max(1, damage-5), damage+10)
        if g["hp"] <= 0:
            e["xp"] += 10 if e["level"] <= 4 else (7 if e["level"] <= 9 else 5)
            while e["xp"] >= 100 and e["level"] < 15: e["xp"] -= 100; e["level"] += 1
            if e["level"] >= 15: e["xp"] = 99
            reward = random.randint(100,500); u["wins"] += 1; u["money"] += reward; save_user(uid,u); GAMES.pop(uid,None)
            return await show(update, f"🏆 G‘ALABA!\n💰 Mukofot: {reward}\n⭐ Qurol XP: {e['xp']}/100 | Level: {e['level']}/15", back())
    hit = random.randint(1,g["damage"]); block = min(u["armor"],hit); u["armor"] -= block; u["hp"] = max(0,u["hp"]-hit+block)
    if u["hp"] <= 0:
        u["losses"] += 1; u["hp"] = max(1,u["max_hp"]//2); save_user(uid,u); GAMES.pop(uid,None); return await show(update,"❌ MAG‘LUBIYAT.",back())
    save_user(uid,u); await fight_screen(update,uid)


def ready(u, field, minutes):
    if not u.get(field): return True
    try: return datetime.now() >= datetime.fromisoformat(u[field]) + timedelta(minutes=minutes)
    except ValueError: return True


async def earn(update, kind):
    uid = update.effective_user.id; u = get_user(uid); field, mins = {"work": ("last_work",5), "crime": ("last_crime",10), "rob": ("last_rob",15)}[kind]
    if not ready(u,field,mins): return await show(update,"⏳ Kutish vaqti hali tugamadi.",back())
    u[field] = datetime.now().isoformat(); success = random.random() < {"work":1,"crime":.65,"rob":.45}[kind]
    amount = random.randint(100,500) if kind == "work" else random.randint(200,2500)
    if success: u["money"] += amount; text = f"✅ Muvaffaqiyat!\n💰 Daromad: {amount}"
    else: amount = min(u["money"],random.randint(50,300)); u["money"] -= amount; text = f"❌ Muvaffaqiyatsiz!\n💸 Yo‘qotish: {amount}"
    save_user(uid,u); await show(update,text,back())


async def leaderboard(update, context):
    top = sorted(read(USERS_FILE).items(), key=lambda x:(x[1].get("wins",0),x[1].get("money",0)), reverse=True)[:10]
    await show(update,"🏆 TOP 10 O‘YINCHI\n\n"+"\n".join(f"{i}. {v.get('first_name') or k} — 🏆 {v.get('wins',0)} | 💰 {v.get('money',0)}" for i,(k,v) in enumerate(top,1)),back())


async def admin(update, context):
    if update.effective_user.id not in ADMIN_IDS: return await show(update,"⛔ Siz admin emassiz.",back())
    await show(update,"👑 ADMIN\n/addmoney ID MIQDOR\n/adddiamond ID MIQDOR\n/broadcast MATN\n/users",back())


async def add_money(update, context):
    if update.effective_user.id not in ADMIN_IDS or len(context.args)!=2: return
    try:
        uid, amount = int(context.args[0]), int(context.args[1]); u=get_user(uid); u["money"] += amount; save_user(uid,u); await update.message.reply_text("✅ Pul berildi.")
    except ValueError: await update.message.reply_text("Foydalanish: /addmoney ID MIQDOR")


async def add_diamond(update, context):
    if update.effective_user.id not in ADMIN_IDS or len(context.args)!=2: return
    try:
        uid, amount = int(context.args[0]), int(context.args[1]); u=get_user(uid); u["diamonds"] += amount; save_user(uid,u); await update.message.reply_text("✅ Olmos berildi.")
    except ValueError: await update.message.reply_text("Foydalanish: /adddiamond ID MIQDOR")


async def users_cmd(update, context):
    if update.effective_user.id in ADMIN_IDS: await update.message.reply_text(f"Foydalanuvchilar: {len(read(USERS_FILE))}")


async def broadcast(update, context):
    if update.effective_user.id not in ADMIN_IDS or not context.args: return
    sent=0
    for uid in read(USERS_FILE):
        try: await context.bot.send_message(int(uid)," ".join(context.args)); sent+=1
        except Exception: pass
    await update.message.reply_text(f"✅ {sent} ta foydalanuvchiga yuborildi.")


async def callback(update, context):
    data=update.callback_query.data
    if data == "main": await start(update,context)
    elif data == "noop": await update.callback_query.answer()
    elif data.startswith("weappage:"): await weapon_shop(update,int(data.split(":")[1]))
    elif data.startswith("weapon:"): await weapon_detail(update,int(data.split(":")[1]))
    elif data.startswith("selectweapon:"):
        i=int(data.split(":")[1]); u=get_user(update.effective_user.id)
        if str(i) in u["weapons"]: u["selected_weapon"]=i; save_user(update.effective_user.id,u); await update.callback_query.answer("Qurol tanlandi!"); await weapon_detail(update,i)
    elif data.startswith("buyweapon:"):
        i=int(data.split(":")[1]); u=get_user(update.effective_user.id); name,currency,price,damage=WEAPONS[i]
        if str(i) in u["weapons"]: return await update.callback_query.answer("Bu qurol inventarda bor.",show_alert=True)
        if u[currency] < price: return await update.callback_query.answer(f"{('Pul' if currency=='money' else 'Olmos')} yetarli emas.",show_alert=True)
        u[currency]-=price; u["weapons"][str(i)]={"level":1,"xp":0}; save_user(update.effective_user.id,u); await update.callback_query.answer("✅ Qurol sotib olindi!"); await weapon_detail(update,i)
    elif data.startswith("fight:"): await fight_action(update,data.split(":",1)[1])
    else: await update.callback_query.answer()


async def text_handler(update, context):
    actions={"⚔️ Jang":fight,"👤 Profil":profile,"🔫 Qurollar":lambda u,c:weapon_shop(u,0),"❤️ HP":lambda u,c:shop(u,"hp"),"🛡️ Himoya":lambda u,c:shop(u,"armor"),"💊 Aptechka":lambda u,c:shop(u,"medkit"),"💼 Ishlash":lambda u,c:earn(u,"work"),"🕵️ Jinoyat":lambda u,c:earn(u,"crime"),"💰 O‘g‘rilik":lambda u,c:earn(u,"rob"),"🏆 Reyting":leaderboard,"👑 Admin":admin}
    fn=actions.get(update.message.text)
    if fn: await fn(update,context)
    else: await update.message.reply_text("Menyudan tanlang.",reply_markup=menu())


async def shop(update, kind):
    u=get_user(update.effective_user.id); items={"hp":HP_ITEMS,"armor":ARMOR_ITEMS,"medkit":MEDKIT_ITEMS}[kind]; rows=[[InlineKeyboardButton(f"{kind.upper()} +{v} — {p}",callback_data=f"buy:{kind}:{i}")] for i,(p,v) in enumerate(items)]
    rows.append([InlineKeyboardButton("🔙 Menyu",callback_data="main")]); await show(update,f"🛒 {kind.upper()} DO‘KONI\n💰 Pul: {u['money']}",InlineKeyboardMarkup(rows))


web=Flask(__name__)
@web.get("/")
def home(): return "Telegram bot is running",200
@web.get("/health")
def health(): return "ok",200
def run_web(): web.run(host="0.0.0.0",port=int(os.getenv("PORT","10000")),use_reloader=False)


def main():
    if not TOKEN: raise RuntimeError("BOT_TOKEN environment variable topilmadi")
    threading.Thread(target=run_web,daemon=True).start(); app=Application.builder().token(TOKEN).build()
    for command, fn in [("start",start),("addmoney",add_money),("adddiamond",add_diamond),("broadcast",broadcast),("users",users_cmd)]: app.add_handler(CommandHandler(command,fn))
    app.add_handler(CallbackQueryHandler(callback)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler)); app.run_polling(drop_pending_updates=True)

if __name__ == "__main__": main()
