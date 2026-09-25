async def clan(update, context):
    uid = update.effective_user.id
    user = get_user(uid)
    clans = read(CLANS_FILE)

    if not user.get("clan"):
        text = (
            "🏰 CLAN MENYUSI\n\n"
            "📌 /createclan ClanNomi — clan yaratish\n"
            "📨 /joinclan ClanNomi — clan qo‘shilish\n"
            "🚪 /leaveclan — clandan chiqish\n"
            "📋 /clans — barcha clanlar ro‘yxati"
        )
        await show(update, text, back())
        return

    clan_name = user["clan"]
    clan = clans.get(clan_name)
    if not clan:
        user["clan"] = None
        save_user(uid, user)
        await show(update, "⚠️ Clan ma’lumotlari topilmadi. Siz clan a’zolikdan chiqarildingiz.", back())
        return

    members = []
    for member_id in clan.get("members", []):
        try:
            member_uid = int(member_id)
        except ValueError:
            continue
        member_data = get_user(member_uid)
        name = member_data.get("first_name") or member_data.get("username") or str(member_uid)
        role = "👑 Rahbar" if str(member_uid) == clan.get("leader") else "👤 A'zo"
        members.append(f"{role} {name}")

    if not members:
        members = ["👤 Clan a'zolari yo‘q"]

    info = (
        f"🏰 CLAN: {clan_name}\n\n"
        f"👑 Rahbar: {clan.get('leader', '-')}\n"
        f"👥 A'zolar: {len(clan.get('members', []))}\n"
        f"💰 Xazina: {clan.get('bank', 0):,}\n"
        f"⭐ Level: {clan.get('level', 1)}\n"
        f"⭐ XP: {clan.get('xp', 0)}/100\n"
        f"📜 Tavsif: {clan.get('description', 'yo‘q')}\n\n"
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

    clans = read(CLANS_FILE)
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
        "tag": "",
        "logo": "🏰",
        "created_at": datetime.now().isoformat(),
        "wins": 0,
        "losses": 0,
        "logs": [f"{datetime.now().isoformat()} | {name} clani yaratildi."]
    }
    clans[name] = clan
    write(CLANS_FILE, clans)

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
        await update.message.reply_text("Avval hozirgi clandan chiqib oling.")
        return

    name = " ".join(context.args).strip()
    clans = read(CLANS_FILE)
    clan = clans.get(name)
    if not clan:
        await update.message.reply_text("Bunday clan topilmadi.")
        return

    clan.setdefault("members", [])
    if str(uid) not in clan["members"]:
        clan["members"].append(str(uid))
        clan.setdefault("logs", []).append(f"{datetime.now().isoformat()} | {uid} clanga qo‘shildi.")
        write(CLANS_FILE, clans)

    user["clan"] = name
    save_user(uid, user)
    await update.message.reply_text(f"✅ {name} claniga qo‘shildingiz.", reply_markup=menu())


async def leave_clan(update, context):
    uid = update.effective_user.id
    user = get_user(uid)
    clan_name = user.get("clan")
    if not clan_name:
        await update.message.reply_text("Siz hozirda clanda emassiz.")
        return

    clans = read(CLANS_FILE)
    clan = clans.get(clan_name)
    if not clan:
        user["clan"] = None
        save_user(uid, user)
        await update.message.reply_text("Clan ma’lumoti topilmadi. Sizdan clan olib tashlandi.")
        return

    members = clan.get("members", [])
    if str(uid) in members:
        members = [m for m in members if m != str(uid)]
        clan["members"] = members
        clan.setdefault("logs", []).append(f"{datetime.now().isoformat()} | {uid} clandan chiqdi.")

    if str(uid) == clan.get("leader") and members:
        clan["leader"] = members[0]

    if not members:
        clans.pop(clan_name, None)
    else:
        clans[clan_name] = clan

    write(CLANS_FILE, clans)

    user["clan"] = None
    save_user(uid, user)
    await update.message.reply_text("✅ Clandan chiqdingiz.", reply_markup=menu())


async def clans_list(update, context):
    clans = read(CLANS_FILE)
    if not clans:
        await show(update, "🧭 Hozircha hech qanday clan yo‘q.", back())
        return

    lines = ["🏰 CLANLAR RO‘YXATI\n"]
    for name, clan in sorted(clans.items(), key=lambda x: x[1].get("level", 1), reverse=True):
        members_count = len(clan.get("members", []))
        bank = clan.get("bank", 0)
        level = clan.get("level", 1)
        xp = clan.get("xp", 0)
        leader = clan.get("leader", "-")
        lines.append(f"• {name} | 👑 {leader} | 👥 {members_count} | 💰 {bank:,} | ⭐ L{level} XP {xp}/100")

    await show(update, "\n".join(lines), back())


async def clan(update, context):
    uid = update.effective_user.id
    user = get_user(uid)
    clans = read(CLANS_FILE)

    if not user.get("clan"):
        text = (
            "🏰 CLAN MENYUSI\n\n"
            "📌 /createclan ClanNomi — clan yaratish\n"
            "📨 /joinclan ClanNomi — clan qo‘shilish\n"
            "🚪 /leaveclan — clandan chiqish\n"
            "📋 /clans — barcha clanlar ro‘yxati"
        )
        await show(update, text, back())
        return

    clan_name = user["clan"]
    clan = clans.get(clan_name)
    if not clan:
        user["clan"] = None
        save_user(uid, user)
        await show(update, "⚠️ Clan ma’lumotlari topilmadi. Siz clan a’zolikdan chiqarildingiz.", back())
        return

    members = []
    for member_id in clan.get("members", []):
        try:
            member_uid = int(member_id)
        except ValueError:
            continue
        member_data = get_user(member_uid)
        name = member_data.get("first_name") or member_data.get("username") or str(member_uid)
        role = "👑 Rahbar" if str(member_uid) == clan.get("leader") else "👤 A'zo"
        members.append(f"{role} {name}")

    if not members:
        members = ["👤 Clan a'zolari yo‘q"]

    info = (
        f"🏰 CLAN: {clan_name}\n\n"
        f"👑 Rahbar: {clan.get('leader', '-')}\n"
        f"👥 A'zolar: {len(clan.get('members', []))}\n"
        f"💰 Xazina: {clan.get('bank', 0):,}\n"
        f"⭐ Level: {clan.get('level', 1)}\n"
        f"⭐ XP: {clan.get('xp', 0)}/100\n"
        f"📜 Tavsif: {clan.get('description', 'yo‘q')}\n\n"
        f"📋 A'zolar:\n" + "\n".join(members)
    )
    await show(update, info, back())
