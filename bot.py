import telebot
import sqlite3
import time
from telebot import types

# ================== CONFIG ==================
TOKEN = "8360955917:AAE4wTNuOF9rijdnLxJOv8RdagMd5C7vxi4"
ADMIN_ID = 6711751890

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ================== DATABASE ==================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    points INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER,
    url TEXT,
    code TEXT,
    points INTEGER,
    unlimited INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS completed (
    user_id INTEGER,
    link_id INTEGER
)
""")

conn.commit()

# ================== MENUS ==================
def user_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ إضافة رابط", "🔗 عرض الروابط")
    kb.add("👤 ملفي الشخصي")
    return kb

def admin_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 الإحصائيات", "➕ إضافة رابط مفتوح")
    kb.add("📋 كل الروابط", "🚫 حذف رابط")
    kb.add("👥 عدد المستخدمين")
    kb.add("⬅️ رجوع")
    return kb

# ================== START ==================
@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
    conn.commit()

    if uid == ADMIN_ID:
        bot.send_message(message.chat.id, "👑 لوحة الأدمن", reply_markup=admin_menu())
    else:
        bot.send_message(message.chat.id, "👋 أهلاً بك في بوت تبادل الزيارات", reply_markup=user_menu())

# ================== PROFILE ==================
@bot.message_handler(func=lambda m: m.text == "👤 ملفي الشخصي")
def profile(m):
    uid = m.from_user.id
    cur.execute("SELECT points, completed FROM users WHERE user_id=?", (uid,))
    p, c = cur.fetchone()
    bot.send_message(m.chat.id, f"⭐ نقاطك: {p}\n✅ روابط مكتملة: {c}")

# ================== ADD LINK (USER) ==================
@bot.message_handler(func=lambda m: m.text == "➕ إضافة رابط")
def add_link(m):
    uid = m.from_user.id
    cur.execute("SELECT points FROM users WHERE user_id=?", (uid,))
    if cur.fetchone()[0] < 100:
        bot.send_message(m.chat.id, "❌ تحتاج 100 نقطة")
        return
    msg = bot.send_message(m.chat.id, "🔗 أرسل الرابط:")
    bot.register_next_step_handler(msg, get_user_url)

def get_user_url(m):
    url = m.text
    msg = bot.send_message(m.chat.id, "🔑 أرسل الرمز:")
    bot.register_next_step_handler(msg, get_user_code, url)

def get_user_code(m, url):
    uid = m.from_user.id
    code = m.text
    cur.execute("INSERT INTO links (owner_id, url, code, points) VALUES (?, ?, ?, 100)", (uid, url, code))
    cur.execute("UPDATE users SET points=points-100 WHERE user_id=?", (uid,))
    conn.commit()
    bot.send_message(m.chat.id, "✅ تم إضافة الرابط")

# ================== SHOW LINKS ==================
@bot.message_handler(func=lambda m: m.text == "🔗 عرض الروابط")
def show_links(m):
    uid = m.from_user.id
    cur.execute("SELECT id, url FROM links WHERE active=1 AND owner_id!=?", (uid,))
    rows = cur.fetchall()
    if not rows:
        bot.send_message(m.chat.id, "لا توجد روابط حالياً")
        return
    for i, u in rows:
        bot.send_message(m.chat.id, f"{u}\n✍️ أرسل الرمز")
        bot.register_next_step_handler(m, check_code, i)

def check_code(m, lid):
    uid = m.from_user.id
    cur.execute("SELECT code, owner_id, points, unlimited FROM links WHERE id=?", (lid,))
    data = cur.fetchone()
    if not data:
        return
    code, owner, pts, un = data
    if m.text != code:
        bot.send_message(m.chat.id, "❌ رمز خطأ")
        return

    cur.execute("SELECT 1 FROM completed WHERE user_id=? AND link_id=?", (uid, lid))
    if cur.fetchone():
        bot.send_message(m.chat.id, "⚠️ سبق إنجازه")
        return

    cur.execute("INSERT INTO completed VALUES (?,?)", (uid, lid))
    cur.execute("UPDATE users SET points=points+1, completed=completed+1 WHERE user_id=?", (uid,))

    if not un:
        cur.execute("UPDATE users SET points=points-1 WHERE user_id=?", (owner,))
        cur.execute("UPDATE links SET points=points-1 WHERE id=?", (lid,))
        if pts-1 <= 0:
            cur.execute("UPDATE links SET active=0 WHERE id=?", (lid,))

    conn.commit()
    bot.send_message(m.chat.id, "✅ تم احتساب النقطة")

# ================== ADMIN ==================
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text == "➕ إضافة رابط مفتوح")
def admin_open_link(m):
    msg = bot.send_message(m.chat.id, "🔗 أرسل الرابط:")
    bot.register_next_step_handler(msg, admin_open_code)

def admin_open_code(m):
    url = m.text
    msg = bot.send_message(m.chat.id, "🔑 أرسل الرمز:")
    bot.register_next_step_handler(msg, admin_save_open, url)

def admin_save_open(m, url):
    cur.execute("INSERT INTO links (owner_id, url, code, unlimited) VALUES (?, ?, ?, 1)", (ADMIN_ID, url, m.text))
    conn.commit()
    bot.send_message(m.chat.id, "✅ رابط مفتوح بدون نقاط")

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text == "📊 الإحصائيات")
def stats(m):
    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM links")
    links = cur.fetchone()[0]
    bot.send_message(m.chat.id, f"👥 المستخدمين: {users}\n🔗 الروابط: {links}")

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text == "👥 عدد المستخدمين")
def users_count(m):
    cur.execute("SELECT COUNT(*) FROM users")
    bot.send_message(m.chat.id, f"👥 عدد المستخدمين: {cur.fetchone()[0]}")

@bot.message_handler(func=lambda m: m.text == "⬅️ رجوع")
def back(m):
    start(m)

# ================== RUN ==================
while True:
    try:
        print("Bot running...")
        bot.infinity_polling()
    except Exception as e:
        print(e)
        time.sleep(5)
