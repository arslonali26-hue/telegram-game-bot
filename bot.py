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
LOCK = threading.RLock()
GAMES = {}

# name, currency, price, level-1 damage
WEAPONS = [
("🔫 Pistolet","money",0,10),("🔫 Revolver","money",50000,12),("🔫 Glock","money",75000,14),("🔫 UZI","money",100000,16),("🔫 MP5","money",150000,18),("🔫 MP7","money",200000,20),("🔫 P90","money",250000,22),("🔫 AK-47","money",300000,25),("🔫 M4A1","money",350000,27),("🔫 SCAR-L","money",400000,29),("🔫 FAMAS","money",450000,31),("🔫 G36","money",500000,33),("🔫 Shotgun","money",550000,36),("🔫 SPAS-12","money",650000,39),("🔫 SVD","money",750000,42),("🔫 Kar98k","money",850000,45),("🔫 AWM","money",1000000,50),("🏹 Arbalet","money",600000,35),("🏹 Kamon","money",400000,30),("🔱 Nayza","money",250000,28),("⚔️ Qilich","money",700000,40),("🪓 Bolta","money",450000,34),("🗡️ Machete","money",350000,32),("💥 Granatomyot","money",1500000,60),("⚡ Plazma quroli","money",2500000,70),
("🔥 Inferno Pistolet","diamonds",156,25),("⚡ Thunder Revolver","diamonds",234,28),("☠️ Venom Glock","diamonds",312,30),("🔥 Inferno UZI","diamonds",390,32),("⚡ Storm MP5","diamonds",468,35),("☠️ Venom MP7","diamonds",546,37),("🔥 Phoenix P90","diamonds",624,40),("⚡ Thunder AK","diamonds",780,43),("🔥 Inferno M4","diamonds",936,46),("☠️ Venom SCAR","diamonds",1092,49),("⚡ Storm FAMAS","diamonds",1248,52),("🔥 Dragon G36","diamonds",1404,55),("💀 Hell Shotgun","diamonds",1560,58),("⚡ Thunder SPAS","diamonds",1872,61),("☠️ Venom SVD","diamonds",2184,64),("🔥 Dragon Kar98k","diamonds",2496,67),("👑 Golden AWM","diamonds",3120,70),("⚡ Storm Arbalet","diamonds",3432,73),("🔥 Phoenix Kamon","diamonds",3900,76),("🐉 Dragon Nayza","diamonds",4680,80),("⚔️ Demon Qilich","diamonds",5460,84),("☠️ Reaper Bolta","diamonds",6240,88),("🔥 Inferno Machete","diamonds",7020,92),("💥 Apocalypse Launcher","diamonds",7800,100),("👑 Legendary Plasma","diamonds",15600,120),
]
SHIELDS = [("🪵 Oddiy Himoya","money",50000,50),("🥉 Kuchli Himoya","money",100000,75),("🥈 Temir Himoya","money",175000,100),("🥇 Po‘lat Himoya","money",250000,125),("🛡️ Titan Himoya","money",350000,150),("🔩 Maxsus Himoya","money",500000,200),("💎 Diamond Himoya","diamonds",100,250),("⚡ Energiya Himoyasi","diamonds",200,300),("🔥 Inferno Himoya","diamonds",350,400),("👑 Legendary Himoya","diamonds",600,500)]
MEDKITS = [("💊 Kichik Aptechka","money",1000,10),("💊 Oddiy Aptechka","money",2000,15),("💊 Yaxshi Aptechka","money",3500,20),("💊 Kuchli Aptechka","money",5000,25),("💊 Katta Aptechka","money",7500,30),("💊 Super Aptechka","money",10000,40),("💊 Mega Aptechka","money",15000,50),("💊 Ultra Aptechka","money",25000,60),("💎 Premium Aptechka","diamonds",40,70),("👑 Legendary Aptechka","diamonds",75,75)]


def read(path):
    with LOCK:
        try:
            with open(path, encoding="utf-8") as f: return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError): return {}


def write(path, data):
    with LOCK:
        temp = str(path) + ".tmp"
        with open(temp, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp, path)


def blank_user():
    return {"money":500,"diamonds":0,"hp":100,"max_hp":100,"selected_weapon":0,"weapons":{"0":{"level":1,"xp":0}},
            "shield":None,"shield_hp":0,"shield_max":0,"shield_regen":"","medkits":{},"wins":0,"losses":0,
            "first_name":"","username":"","last_work":"","last_crime":"","last_rob":""}


def migrate(u):
    base = blank_user()
    for k, v in base.items(): u.setdefault(k, v)
    # Old saves used armor and weapon_idx; keep old users playable.
    if "weapon_idx" in u and "selected_weapon" not in u: u["selected_weapon"] = u["weapon_idx"]
    if "armor" in u and not u.get("shield") and u.get("armor", 0):
        u["shield"] = "🪵 Oddiy Himoya"; u["shield_max"] = 50; u["shield_hp"] = min(50, int(u["armor"]))
    u.setdefault("weapons", {}); u["weapons"].setdefault("0", {"level":1,"xp":0})
    u.setdefault("medkits", {})
    for key, e in list(u["weapons"].items()):
        e.setdefault("level", 1); e.setdefault("xp", 0); e["level"] = max(1, min(15, int(e["level"])))
    return u


def get_user(uid):
    users = read(USERS_FILE); key = str(uid); u = migrate(users.get(key, blank_user()))
    # Shield regenerates only outside battle: +1 HP per elapsed 30 minutes.
    if u.get("shield") and u.get("shield_hp", 0) < u.get("shield_max", 0):
        now = datetime.now(); last = u.get("shield_regen")
        if not last: u["shield_regen"] = now.isoformat()
        else:
            try:
                elapsed = int((now - datetime.fromisoformat(last)).total_seconds() // 1800)
                if elapsed > 0:
                    u["shield_hp"] = min(u["shield_max"], u["shield_hp"] + elapsed)
                    u["shield_regen"] = (datetime.fromisoformat(last) + timedelta(minutes=30 * elapsed)).isoformat()
            except ValueError: u["shield_regen"] = now.isoformat()
    users[key] = u; write(USERS_FILE, users); return u


def save_user(uid, u):
    users = read(USERS_FILE); users[str(uid)] = migrate(u); write(USERS_FILE, users)


def menu():
    return ReplyKeyboardMarkup([["⚔️ Jang","👤 Profil"],["🔫 Qurollar","🛡️ Himoya"],["💊 Aptechka","🎒 Inventar"],["💼 Ishlash","🕵️ Jinoyat"],["💰 O‘g‘rilik","🏆 Reyting"],["👑 Admin"]], resize_keyboard=True)


def back(): return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menyu", callback_data="main")]])


async def show(update, text, markup=None):
    if update.callback_query:
        q = update.callback_query
        try: await q.answer()
        except Exception: pass
        try: await q.edit_message_text(text, reply_markup=markup)
        except Exception: await q.message.reply_text(text, reply_markup=markup)
    else: await update.message.reply_text(text, reply_markup=markup)


def price(currency, amount): return "Bepul" if amount == 0 else f"{amount:,} {'Pul' if currency == 'money' else 'Almas'}"


async def start(update, context):
    p = update.effective_user; u = get_user(p.id); u.update(first_name=p.first_name or "", username=p.username or ""); save_user(p.id,u)
    await show(update, f"Salom, {p.first_name}! 🎮\n\n💰 Pul: {u['money']:,}\n💎 Almas: {u['diamonds']}\n❤️ HP: {u['hp']}/{u['max_hp']}\n🛡️ Himoya: {u['shield_hp']}/{u['shield_max']}\n🔫 Qurol: {WEAPONS[u['selected_weapon']][0]}", menu())


async def profile(update, context):
    u=get_user(update.effective_user.id); i=u["selected_weapon"]; e=u["weapons"].get(str(i),{"level":1,"xp":0}); w=WEAPONS[i]
    await show(update, f"👤 PROFIL\n\n💰 Pul: {u['money']:,}\n💎 Almas: {u['diamonds']}\n❤️ HP: {u['hp']}/{u['max_hp']}\n🛡️ Himoya: {u['shield_hp']}/{u['shield_max']}\n🔫 {w[0]} | L{e['level']} | XP {e['xp']}/100\n⚔️ Zarar: {w[3]+(e['level']-1)*5}\n🏆 G‘alaba: {u['wins']} | ❌ Mag‘lubiyat: {u['losses']}", back())


async def weapon_shop(update, page=0):
    u=get_user(update.effective_user.id); page=max(0,min(4,int(page))); rows=[]
    for i in range(page*10,min(page*10+10,50)):
        n,c,p,d=WEAPONS[i]; e=u["weapons"].get(str(i)); mark="✅" if i==u["selected_weapon"] else ("📦" if e else "🔒"); lv=e["level"] if e else 0
        rows.append([InlineKeyboardButton(f"{mark} {i+1}. {n} L{lv} | {price(c,p)}",callback_data=f"weapon:{i}")])
    nav=[]
    if page: nav.append(InlineKeyboardButton("⬅️",callback_data=f"wpage:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/5",callback_data="noop"))
    if page<4: nav.append(InlineKeyboardButton("➡️",callback_data=f"wpage:{page+1}"))
    rows += [nav,[InlineKeyboardButton("🔙 Menyu",callback_data="main")]]
    await show(update,f"🔫 QUROLLAR {page*10+1}–{min(page*10+10,50)}/50\n💰 {u['money']:,} | 💎 {u['diamonds']}",InlineKeyboardMarkup(rows))


async def weapon_detail(update,i):
    u=get_user(update.effective_user.id); n,c,p,d=WEAPONS[i]; e=u["weapons"].get(str(i)); rows=[]
    if not e: rows.append([InlineKeyboardButton(f"🛒 Sotib olish — {price(c,p)}",callback_data=f"buyweapon:{i}")])
    elif i != u["selected_weapon"]: rows.append([InlineKeyboardButton("🎯 Tanlash",callback_data=f"selectweapon:{i}")])
    else: rows.append([InlineKeyboardButton("✅ Tanlangan",callback_data="noop")])
    rows.append([InlineKeyboardButton("🔙 Qurollar",callback_data="wpage:0")])
    lv=e["level"] if e else 1; xp=e["xp"] if e else 0
    await show(update,f"{n}\n\n💳 Narx: {price(c,p)}\n⚔️ Zarar: {d+(lv-1)*5}\n⭐ Level: {lv}/15\n📊 XP: {xp}/100\n\nHar muvaffaqiyatli hujum: L1–4 +10 XP, L5–9 +7 XP, L10–15 +5 XP.",InlineKeyboardMarkup(rows))


async def catalog(update, kind, page=0):
    u=get_user(update.effective_user.id); data=SHIELDS if kind=="shield" else MEDKITS; rows=[]
    for i,(n,c,p,v) in enumerate(data):
        if kind=="shield": label=f"{('✅' if u['shield'] else '🔒')} {i+1}. {n} — {price(c,p)} | {v} HP"
        else: label=f"💊 {i+1}. {n} — {price(c,p)} | +{v} HP (×{u['medkits'].get(str(i),0)})"
        rows.append([InlineKeyboardButton(label,callback_data=f"shop:{kind}:{i}")])
    rows.append([InlineKeyboardButton("🔙 Menyu",callback_data="main")])
    await show(update, f"🛒 {'HIMOYA' if kind=='shield' else 'APTECHKA'}\n💰 {u['money']:,} | 💎 {u['diamonds']}\n⚠️ Aptechka jang paytida sotib olinmaydi.",InlineKeyboardMarkup(rows))


async def inventory(update, context):
    u=get_user(update.effective_user.id); meds="\n".join(f"💊 {MEDKITS[i][0]} × {u['medkits'].get(str(i),0)}" for i in range(10) if u['medkits'].get(str(i),0)) or "Aptechka yo‘q"
    await show(update,f"🎒 INVENTAR\n\n🛡️ {u['shield'] or 'Himoya yo‘q'}\n🛡️ Himoya HP: {u['shield_hp']}/{u['shield_max']}\n\n{meds}",back())


async def buy(update, kind, i):
    uid=update.effective_user.id; u=get_user(uid); data=SHIELDS if kind=="shield" else MEDKITS; n,c,p,v=data[i]
    if kind=="shield" and u.get("shield"): return await update.callback_query.answer("Sizda allaqachon himoya bor.",show_alert=True)
    if u[c] < p: return await update.callback_query.answer(f"{('Pul' if c=='money' else 'Almas')} yetarli emas.",show_alert=True)
    u[c]-=p
    if kind=="shield": u.update(shield=n,shield_hp=v,shield_max=v,shield_regen=datetime.now().isoformat())
    else: u["medkits"][str(i)]=u["medkits"].get(str(i),0)+1
    save_user(uid,u); await update.callback_query.answer("✅ Sotib olindi!"); await catalog(update,kind)


async def fight(update, context):
    uid=update.effective_user.id; u=get_user(uid)
    if u["hp"]<=0: return await show(update,"💀 Siz mag‘lub bo‘lgansiz. Yangi jang boshlash mumkin emas.",back())
    hp=random.randint(80,250); GAMES[uid]={"hp":hp,"max":hp,"damage":random.randint(8,30),"meds":0,"shield_used":False}
    await fight_screen(update,uid)


async def fight_screen(update,uid):
    g=GAMES.get(uid); u=get_user(uid)
    await show(update,f"⚔️ JANG\n\n👾 Raqib: {g['hp']}/{g['max']}\n👤 Siz: {u['hp']}/{u['max_hp']}\n🛡️ Himoya: {u['shield_hp']}/{u['shield_max']}\n💊 Aptechka: {g['meds']}/3",InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Hujum",callback_data="fight:attack"),InlineKeyboardButton("💊 Aptechka",callback_data="fight:heal")],[InlineKeyboardButton("🛡️ Himoyani yoqish",callback_data="fight:block")],[InlineKeyboardButton("🏃 Qochish",callback_data="fight:flee")]]))


async def fight_action(update,action):
    uid=update.effective_user.id; u=get_user(uid); g=GAMES.get(uid)
    if not g: return await update.callback_query.answer("Faol jang yo‘q.",show_alert=True)
    if action=="flee": GAMES.pop(uid,None); return await show(update,"🏃 Jangdan qochdingiz.",back())
    if action=="block":
        g["shield_used"]=True; return await show(update,"🛡️ Himoya yoqildi. Keyingi dushman hujumi bloklanadi.",back())
    if action=="heal":
        if g["meds"]>=3: return await update.callback_query.answer("Bu jangda 3 ta aptechka limiti tugadi.",show_alert=True)
        if u["hp"]>=u["max_hp"]: return await update.callback_query.answer("HP 100/100. Aptechka ishlatilmaydi.",show_alert=True)
        choices=[i for i,n in u["medkits"].items() if n>0]
        if not choices: return await update.callback_query.answer("Inventarda aptechka yo‘q.",show_alert=True)
        i=int(choices[0]); amount=MEDKITS[i][3]; u["medkits"][str(i)]-=1; u["hp"]=min(u["max_hp"],u["hp"]+amount); g["meds"]+=1; save_user(uid,u); await fight_screen(update,uid); return
    # Attack: player damages enemy, then enemy attacks player.
    i=u["selected_weapon"]; e=u["weapons"].setdefault(str(i),{"level":1,"xp":0}); damage=WEAPONS[i][3]+(e["level"]-1)*5; g["hp"]-=random.randint(max(1,damage-5),damage+10)
    if g["hp"]<=0:
        xp=10 if e["level"]<=4 else 7 if e["level"]<=9 else 5; e["xp"]+=xp
        while e["xp"]>=100 and e["level"]<15: e["xp"]-=100; e["level"]+=1
        if e["level"]>=15: e["xp"]=99
        reward=random.randint(100,500); u["wins"]+=1; u["money"]+=reward; save_user(uid,u); GAMES.pop(uid,None)
        return await show(update,f"🏆 G‘ALABA!\n💰 Mukofot: {reward}\n⭐ +{xp} XP | Qurol Level: {e['level']}/15",back())
    incoming=g["damage"]
    if g["shield_used"]: incoming=0; g["shield_used"]=False
    else:
        absorbed=min(u["shield_hp"],incoming); u["shield_hp"]-=absorbed; incoming-=absorbed
        if u["shield_hp"]>=u["shield_max"]: u["shield_regen"]=datetime.now().isoformat()
        u["hp"]=max(0,u["hp"]-incoming)
    if u["hp"]<=0:
        u["losses"]+=1; save_user(uid,u); GAMES.pop(uid,None); return await show(update,"💀 HP 0/100. Siz jangda mag‘lub bo‘ldingiz.",back())
    save_user(uid,u); await fight_screen(update,uid)


async def earn(update,kind):
    uid=update.effective_user.id; u=get_user(uid); field,mins={"work":("last_work",5),"crime":("last_crime",10),"rob":("last_rob",15)}[kind]
    if u.get(field):
        try:
            if datetime.now()<datetime.fromisoformat(u[field])+timedelta(minutes=mins): return await show(update,"⏳ Kutish vaqti hali tugamadi.",back())
        except ValueError: pass
    u[field]=datetime.now().isoformat(); success=random.random() < {"work":1,"crime":.65,"rob":.45}[kind]; amount=random.randint(100,500) if kind=="work" else random.randint(200,2500)
    if success: u["money"]+=amount; text=f"✅ Muvaffaqiyat!\n💰 +{amount}"
    else: amount=min(u["money"],random.randint(50,300)); u["money"]-=amount; text=f"❌ Muvaffaqiyatsiz!\n💸 -{amount}"
    save_user(uid,u); await show(update,text,back())


async def leaderboard(update,context):
    top=sorted(read(USERS_FILE).items(),key=lambda x:(x[1].get("wins",0),x[1].get("money",0)),reverse=True)[:10]
    await show(update,"🏆 TOP 10\n\n"+"\n".join(f"{i}. {v.get('first_name') or k} — {v.get('wins',0)} g‘alaba" for i,(k,v) in enumerate(top,1)),back())


async def admin(update,context):
    if update.effective_user.id in ADMIN_IDS: await show(update,"👑 ADMIN\n/addmoney ID MIQDOR\n/adddiamond ID MIQDOR\n/users",back())
    else: await show(update,"⛔ Siz admin emassiz.",back())


async def add_money(update,context):
    if update.effective_user.id in ADMIN_IDS and len(context.args)==2:
        u=get_user(int(context.args[0])); u["money"]+=int(context.args[1]); save_user(int(context.args[0]),u); await update.message.reply_text("✅ Pul berildi.")


async def add_diamond(update,context):
    if update.effective_user.id in ADMIN_IDS and len(context.args)==2:
        u=get_user(int(context.args[0])); u["diamonds"]+=int(context.args[1]); save_user(int(context.args[0]),u); await update.message.reply_text("✅ Almas berildi.")


async def users_cmd(update,context):
    if update.effective_user.id in ADMIN_IDS: await update.message.reply_text(f"Foydalanuvchilar: {len(read(USERS_FILE))}")


async def callback(update,context):
    d=update.callback_query.data
    if d=="main": await start(update,context)
    elif d=="noop": await update.callback_query.answer()
    elif d.startswith("wpage:"): await weapon_shop(update,int(d.split(":")[1]))
    elif d.startswith("weapon:"): await weapon_detail(update,int(d.split(":")[1]))
    elif d.startswith("selectweapon:"):
        i=int(d.split(":")[1]); u=get_user(update.effective_user.id)
        if str(i) in u["weapons"]: u["selected_weapon"]=i; save_user(update.effective_user.id,u); await weapon_detail(update,i)
    elif d.startswith("buyweapon:"):
        i=int(d.split(":")[1]); u=get_user(update.effective_user.id); n,c,p,_=WEAPONS[i]
        if str(i) in u["weapons"]: return await update.callback_query.answer("Inventarda bor.",show_alert=True)
        if u[c]<p: return await update.callback_query.answer("Mablag‘ yetarli emas.",show_alert=True)
        u[c]-=p; u["weapons"][str(i)]={"level":1,"xp":0}; save_user(update.effective_user.id,u); await weapon_detail(update,i)
    elif d.startswith("shop:"):
        _,kind,i=d.split(":"); await buy(update,kind,int(i))
    elif d.startswith("fight:"): await fight_action(update,d.split(":",1)[1])
    else: await update.callback_query.answer()


async def text_handler(update,context):
    actions={"⚔️ Jang":fight,"👤 Profil":profile,"🔫 Qurollar":lambda u,c:weapon_shop(u,0),"🛡️ Himoya":lambda u,c:catalog(u,"shield"),"💊 Aptechka":lambda u,c:catalog(u,"medkit"),"🎒 Inventar":inventory,"💼 Ishlash":lambda u,c:earn(u,"work"),"🕵️ Jinoyat":lambda u,c:earn(u,"crime"),"💰 O‘g‘rilik":lambda u,c:earn(u,"rob"),"🏆 Reyting":leaderboard,"👑 Admin":admin}
    fn=actions.get(update.message.text)
    if fn: await fn(update,context)
    else: await update.message.reply_text("Menyudan tanlang.",reply_markup=menu())


web=Flask(__name__)
@web.get("/")
def home(): return "Telegram bot is running",200
@web.get("/health")
def health(): return "ok",200
def run_web(): web.run(host="0.0.0.0",port=int(os.getenv("PORT","10000")),use_reloader=False)


def main():
    if not TOKEN: raise RuntimeError("BOT_TOKEN environment variable topilmadi")
    threading.Thread(target=run_web,daemon=True).start(); app=Application.builder().token(TOKEN).build()
    for command,fn in [("start",start),("addmoney",add_money),("adddiamond",add_diamond),("users",users_cmd)]: app.add_handler(CommandHandler(command,fn))
    app.add_handler(CallbackQueryHandler(callback)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler)); app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()
