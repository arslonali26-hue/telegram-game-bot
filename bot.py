import json
import os
import random
import threading
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [7979870096]
USERS_FILE = "users.json"
CLANS_FILE = "clans.json"
GAMES = {}

HP_ITEMS = [(150, 10), (400, 30), (1000, 80), (3000, 250), (6000, 550), (10000, 1000)]
ARMOR_ITEMS = [(150, 10), (400, 30), (1000, 80), (3000, 250), (6000, 550), (10000, 1000)]
MEDKIT_ITEMS = [(150, 1), (400, 3), (1000, 8), (3000, 25), (6000, 55)]
WEAPONS = [("🔪 Pichoq", 0, 10), ("🔫 Pistolet", 100, 20), ("🔫 Revolver", 500, 35), ("🔫 Desert Eagle", 1500, 50), ("🔫 Shotgun", 4000, 75), ("🏹 Arbalet", 10000, 100), ("🔫 UZI", 25000, 140), ("🔫 MP5", 60000, 190), ("🔫 AK-47", 150000, 250), ("🔫 M4A1", 350000, 330), ("🔫 SCAR", 800000, 420), ("💥 RPG", 100000000, 1700)]


def read(path):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): return {}


def write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def default_user():
    return {"money": 500, "diamonds": 0, "hp": 100, "max_hp": 100, "armor": 0, "max_armor": 0, "medkits": 0, "weapon_idx": 0, "weapon": WEAPONS[0][0], "wins": 0, "losses": 0, "clan": None, "last_work": None, "last_crime": None, "last_rob": None, "first_name": "", "username": ""}


def user(uid):
    users = read(USERS_FILE); key = str(uid); changed = False
    if key not in users: users[key] = default_user(); changed = True
    for k, v in default_user().items():
        if k not in users[key]: users[key][k] = v; changed = True
    if changed: write(USERS_FILE, users)
    return users[key]


def save_user(uid, data):
    users = read(USERS_FILE); users[str(uid)] = data; write(USERS_FILE, users)


def kb():
    return ReplyKeyboardMarkup([[KeyboardButton("⚔️ Jang"), KeyboardButton("👤 Profil")], [KeyboardButton("🔫 Qurollar"), KeyboardButton("❤️ HP")], [KeyboardButton("🛡️ Himoya"), KeyboardButton("💊 Aptechka")], [KeyboardButton("👥 Clan"), KeyboardButton("💼 Ishlash")], [KeyboardButton("🎲 Jinoyat"), KeyboardButton("💰 O‘g‘rilik")], [KeyboardButton("🏆 Statistika"), KeyboardButton("👑 Admin")]], resize_keyboard=True)


def back(): return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Asosiy menyu", callback_data="main")]])


async def show(update, text, markup=None):
    if update.callback_query:
        q = update.callback_query
        try: await q.answer()
        except Exception: pass
        try: await q.edit_message_text(text, reply_markup=markup)
        except Exception: await q.message.reply_text(text, reply_markup=markup)
    else: await update.message.reply_text(text, reply_markup=markup)


async def start(update, context):
    u = user(update.effective_user.id); t = update.effective_user
    u.update(first_name=t.first_name or "", username=t.username or ""); save_user(t.id, u)
    await show(update, f"Salom, {t.first_name}! 🎮\n\n💰 Pul: {u['money']}\n💎 Olmos: {u['diamonds']}\n❤️ HP: {u['hp']}/{u['max_hp']}\n🛡️ Himoya: {u['armor']}/{u['max_armor']}\n🔫 Qurol: {u['weapon']}\n👥 Clan: {u['clan'] or 'Yo‘q'}", kb())


async def profile(update, context):
    u = user(update.effective_user.id); total = u['wins'] + u['losses']; rate = u['wins'] * 100 / total if total else 0
    await show(update, f"👤 PROFIL\n\n🆔 ID: {update.effective_user.id}\n💰 Pul: {u['money']}\n💎 Olmos: {u['diamonds']}\n❤️ HP: {u['hp']}/{u['max_hp']}\n🛡️ Himoya: {u['armor']}/{u['max_armor']}\n💊 Aptechka: {u['medkits']}\n🔫 Qurol: {u['weapon']}\n👥 Clan: {u['clan'] or 'Yo‘q'}\n\n🏆 G‘alaba: {u['wins']}\n❌ Mag‘lubiyat: {u['losses']}\n📊 Foiz: {rate:.1f}%", back())


async def shop(update, kind):
    u = user(update.effective_user.id); buttons = []
    if kind == 'weapon':
        for i, (name, price, damage) in enumerate(WEAPONS): buttons.append([InlineKeyboardButton(("✅ " if i <= u['weapon_idx'] else "") + name + ("" if i <= u['weapon_idx'] else f" — {price}"), callback_data=f"weapon:{i}")])
        title = f"🔫 QUROLLAR DO‘KONI\n\n💰 Pul: {u['money']}\n🔫 Joriy: {u['weapon']}"
    else:
        items = {'hp': HP_ITEMS, 'armor': ARMOR_ITEMS, 'medkit': MEDKIT_ITEMS}[kind]
        for i, (price, val) in enumerate(items): buttons.append([InlineKeyboardButton(f"{kind.upper()} +{val} — {price}", callback_data=f"{kind}:{i}")])
        title = f"🛒 {kind.upper()} DO‘KONI\n\n💰 Pul: {u['money']}"
    buttons.append([InlineKeyboardButton("🔙 Asosiy menyu", callback_data="main")]); await show(update, title, InlineKeyboardMarkup(buttons))


async def fight(update, context):
    uid = update.effective_user.id; u = user(uid)
    if u['hp'] <= 0: return await show(update, "❤️ HP tugagan. Avval HP sotib oling.", back())
    hp = random.randint(80, 250); GAMES[uid] = {'hp': hp, 'max': hp, 'name': random.choice(['Qaroqchi', 'Gangster', 'Boss']), 'damage': random.randint(8, 30)}
    await show(update, f"⚔️ JANG!\n\n👾 {GAMES[uid]['name']}\n❤️ Raqib HP: {hp}/{hp}\n👤 Siz: {u['hp']}/{u['max_hp']}", InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Hujum", callback_data="attack"), InlineKeyboardButton("💊 Davolanish", callback_data="heal")], [InlineKeyboardButton("🏃 Qochish", callback_data="flee")]]))


async def fight_action(update, action):
    q = update.callback_query; uid = update.effective_user.id; u = user(uid); g = GAMES.get(uid)
    if not g: return await q.answer("Faol jang yo‘q.", show_alert=True)
    if action == 'flee': GAMES.pop(uid, None); return await show(update, "🏃 Jangdan qochdingiz.", back())
    if action == 'heal':
        if u['medkits'] < 1: return await q.answer("Aptechka yo‘q.", show_alert=True)
        u['medkits'] -= 1; u['hp'] = min(u['max_hp'], u['hp'] + 50)
    else:
        damage = random.randint(max(1, WEAPONS[u['weapon_idx']][2] - 5), WEAPONS[u['weapon_idx']][2] + 10); g['hp'] -= damage
        if g['hp'] <= 0:
            reward = random.randint(100, 500); u['wins'] += 1; u['money'] += reward; save_user(uid, u); GAMES.pop(uid, None); return await show(update, f"🏆 G‘ALABA!\n💰 Mukofot: {reward}", back())
    hit = random.randint(1, g['damage']); absorbed = min(u['armor'], hit); u['armor'] -= absorbed; u['hp'] = max(0, u['hp'] - hit + absorbed)
    if u['hp'] <= 0:
        u['losses'] += 1; u['hp'] = max(1, u['max_hp'] // 2); save_user(uid, u); GAMES.pop(uid, None); return await show(update, "❌ MAG‘LUBIYAT.", back())
    save_user(uid, u); await show(update, f"⚔️ JANG DAVOM ETMOQDA\n\n👾 {g['name']}\n❤️ Raqib HP: {max(0,g['hp'])}/{g['max']}\n👤 Siz: {u['hp']}/{u['max_hp']}", InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Hujum", callback_data="attack"), InlineKeyboardButton("💊 Davolanish", callback_data="heal")], [InlineKeyboardButton("🏃 Qochish", callback_data="flee")]]))


def ready(value, minutes):
    if not value: return True
    try: return datetime.now() >= datetime.fromisoformat(value) + timedelta(minutes=minutes)
    except ValueError: return True


async def earn(update, kind):
    uid = update.effective_user.id; u = user(uid); field, mins = {'work': ('last_work', 5), 'crime': ('last_crime', 10), 'rob': ('last_rob', 15)}[kind]
    if not ready(u[field], mins): return await show(update, "⏳ Hali kutish vaqti tugamadi.", back())
    u[field] = datetime.now().isoformat(); success = random.random() < ({'work': 1, 'crime': .65, 'rob': .45}[kind])
    if success: amount = random.randint(100, 500) if kind == 'work' else random.randint(200, 2500); u['money'] += amount; text = f"✅ Muvaffaqiyat!\n💰 Daromad: {amount}"
    else: amount = min(u['money'], random.randint(50, 300)); u['money'] -= amount; text = f"❌ Muvaffaqiyatsiz!\n💸 Yo‘qotish: {amount}"
    save_user(uid, u); await show(update, text, back())


async def clan_menu(update, context):
    u = user(update.effective_user.id); clans = read(CLANS_FILE)
    if not u['clan']: return await show(update, "👥 Clan yo‘q. Yaratish uchun /createclan NOM yozing.", back())
    c = clans.get(u['clan'], {}); await show(update, f"👥 CLAN: {u['clan']}\n\n👥 A’zolar: {len(c.get('members',[]))}\n💰 Bank: {c.get('bank',0)}", back())


async def create_clan(update, context):
    if not context.args: return await update.message.reply_text("Foydalanish: /createclan ClanNomi")
    uid = update.effective_user.id; u = user(uid); name = ' '.join(context.args).strip(); clans = read(CLANS_FILE)
    if u['clan']: return await update.message.reply_text("Siz allaqachon clandasiz.")
    if name in clans: return await update.message.reply_text("Bu clan mavjud.")
    clans[name] = {'leader': str(uid), 'members': [str(uid)], 'bank': 0}; write(CLANS_FILE, clans); u['clan'] = name; save_user(uid, u); await update.message.reply_text(f"✅ {name} clani yaratildi!", reply_markup=kb())


async def callbacks(update, context):
    data = update.callback_query.data
    if data == 'main': return await start(update, context)
    if data == 'attack': return await fight_action(update, 'attack')
    if data == 'heal': return await fight_action(update, 'heal')
    if data == 'flee': return await fight_action(update, 'flee')
    if data == 'profile': return await profile(update, context)
    if data.startswith('weapon:'):
        i = int(data.split(':')[1]); uid = update.effective_user.id; u = user(uid)
        if i <= u['weapon_idx']: return await update.callback_query.answer("Bu qurol sizda bor.", show_alert=True)
        name, price, _ = WEAPONS[i]
        if u['money'] < price: return await update.callback_query.answer("Pul yetarli emas.", show_alert=True)
        u.update(money=u['money']-price, weapon_idx=i, weapon=name); save_user(uid, u); await update.callback_query.answer("Sotib olindi!"); return await shop(update, 'weapon')
    if data in ('hp','armor','medkit','weapon'): return await shop(update, data)
    if ':' in data and data.split(':')[0] in ('hp','armor','medkit'):
        kind, i = data.split(':'); i = int(i); items = {'hp':HP_ITEMS, 'armor':ARMOR_ITEMS, 'medkit':MEDKIT_ITEMS}[kind]; price, val = items[i]; uid = update.effective_user.id; u = user(uid)
        if u['money'] < price: return await update.callback_query.answer("Pul yetarli emas.", show_alert=True)
        u['money'] -= price
        if kind == 'hp': u['max_hp'] += val; u['hp'] += val
        elif kind == 'armor': u['max_armor'] += val; u['armor'] += val
        else: u['medkits'] += val
        save_user(uid, u); await update.callback_query.answer("Xarid amalga oshdi!"); return await shop(update, kind)
    await update.callback_query.answer()


async def text(update, context):
    actions = {'⚔️ Jang': fight, '👤 Profil': profile, '🔫 Qurollar': lambda u,c: shop(u,'weapon'), '❤️ HP': lambda u,c: shop(u,'hp'), '🛡️ Himoya': lambda u,c: shop(u,'armor'), '💊 Aptechka': lambda u,c: shop(u,'medkit'), '👥 Clan': clan_menu, '💼 Ishlash': lambda u,c: earn(u,'work'), '🎲 Jinoyat': lambda u,c: earn(u,'crime'), '💰 O‘g‘rilik': lambda u,c: earn(u,'rob')}
    fn = actions.get(update.message.text)
    if fn: await fn(update, context)
    elif update.message.text == '🏆 Statistika': await profile(update, context)
    elif update.message.text == '👑 Admin': await admin(update, context)
    else: await update.message.reply_text('Menyudan tanlang.', reply_markup=kb())


async def admin(update, context):
    if update.effective_user.id not in ADMIN_IDS: return await show(update, '⛔ Siz admin emassiz.', back())
    await show(update, '👑 ADMIN\n/addmoney ID MIQDOR\n/adddiamond ID MIQDOR\n/users\n/broadcast MATN', back())


async def addmoney(update, context):
    if update.effective_user.id not in ADMIN_IDS or len(context.args) != 2: return
    u = user(int(context.args[0])); u['money'] += int(context.args[1]); save_user(int(context.args[0]), u); await update.message.reply_text('✅ Pul berildi.')


async def adddiamond(update, context):
    if update.effective_user.id not in ADMIN_IDS or len(context.args) != 2: return
    u = user(int(context.args[0])); u['diamonds'] += int(context.args[1]); save_user(int(context.args[0]), u); await update.message.reply_text('✅ Olmos berildi.')


async def users_cmd(update, context):
    if update.effective_user.id in ADMIN_IDS: await update.message.reply_text(f"Foydalanuvchilar: {len(read(USERS_FILE))}")


app = Flask(__name__)
@app.get('/')
def home(): return 'Telegram bot is running', 200
@app.get('/health')
def health(): return 'ok', 200

def run_web(): app.run(host='0.0.0.0', port=int(os.getenv('PORT', '10000')), use_reloader=False)


def main():
    if not TOKEN: raise RuntimeError('BOT_TOKEN environment variable topilmadi')
    threading.Thread(target=run_web, daemon=True).start()
    bot = Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler('start', start)); bot.add_handler(CommandHandler('createclan', create_clan)); bot.add_handler(CommandHandler('addmoney', addmoney)); bot.add_handler(CommandHandler('adddiamond', adddiamond)); bot.add_handler(CommandHandler('users', users_cmd)); bot.add_handler(CallbackQueryHandler(callbacks)); bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text)); bot.run_polling()

if __name__ == '__main__': main()
