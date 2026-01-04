import telebot
from telebot import types
import json
import os
import time
import random
import hashlib
from datetime import datetime, timedelta

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8348786219:AAEfL5BnDvKQlFXqUBqWcSauYWeNN5hShaw"

ADMINS_USERNAMES = ["ww13kelm", "monster_psy", "venter8", "asd123dad"]
ADMIN_IDS = []

DB_FILE = "database.json"

# ==================== БОТ ====================
bot = telebot.TeleBot(BOT_TOKEN)
BOT_USERNAME = bot.get_me().username
BOT_ID = bot.get_me().id

print(f"🤖 Бот @{BOT_USERNAME} загружен!")

# ==================== БАЗА ДАННЫХ ====================
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
    else:
        db = {}
    
    if "users" not in db:
        db["users"] = {}
    if "promocodes" not in db:
        db["promocodes"] = {}
    if "withdrawals" not in db:
        db["withdrawals"] = {}
    if "banned" not in db:
        db["banned"] = []
    if "channels" not in db:
        db["channels"] = []
    if "links" not in db:
        db["links"] = {}
    
    return db

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def get_user(db, user_id):
    user_id = str(user_id)
    if user_id not in db["users"]:
        db["users"][user_id] = {
            "balance": 0,
            "pieces": 0,
            "referrals": 0,
            "withdrawn": 0,
            "referrer": None,
            "last_daily": None,
            "last_withdraw": None,
            "cooldowns": {},
            "registered": datetime.now().isoformat(),
            "username": None,
            "premium_until": None,
            "custom_emoji": None,
            "custom_title": None,
            "clicked_links": []
        }
        save_db(db)
    
    user = db["users"][user_id]
    defaults = {
        "balance": 0, "pieces": 0, "referrals": 0, "withdrawn": 0,
        "referrer": None, "last_daily": None, "last_withdraw": None,
        "cooldowns": {}, "registered": datetime.now().isoformat(),
        "username": None, "premium_until": None, "custom_emoji": None,
        "custom_title": None, "clicked_links": []
    }
    for key, value in defaults.items():
        if key not in user:
            user[key] = value
    
    return user

def update_username(db, user):
    user_id = str(user.id)
    if user_id in db["users"]:
        db["users"][user_id]["username"] = user.username
        save_db(db)

def is_admin(user):
    username = user.username.lower() if user.username else ""
    return username in ADMINS_USERNAMES or user.id in ADMIN_IDS

def has_premium(db, user_id):
    user = get_user(db, user_id)
    if user["premium_until"] is None:
        return False
    try:
        premium_date = datetime.fromisoformat(user["premium_until"])
        return datetime.now() < premium_date
    except:
        return False

user_states = {}

# ==================== ПРОВЕРКА ПОДПИСКИ ====================
def check_subscription(user_id):
    db = load_db()
    channels = db.get("channels", [])
    not_subscribed = []
    
    for channel in channels:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ["left", "kicked"]:
                chat = bot.get_chat(channel)
                not_subscribed.append({"type": "channel", "data": chat})
        except:
            pass
    
    return not_subscribed

def check_links(user_id):
    db = load_db()
    user = get_user(db, user_id)
    links = db.get("links", {})
    not_clicked = []
    
    for link_id, link_data in links.items():
        if link_id not in user.get("clicked_links", []):
            not_clicked.append({"id": link_id, "url": link_data["url"], "name": link_data.get("name", "Ссылка")})
    
    return not_clicked

def subscription_required(func):
    def wrapper(message):
        db = load_db()
        update_username(db, message.from_user)
        
        if is_admin(message.from_user):
            return func(message)
        
        if str(message.from_user.id) in db.get("banned", []):
            bot.send_message(message.chat.id, "❌ Вы заблокированы в боте.")
            return
        
        not_subscribed = check_subscription(message.from_user.id)
        not_clicked = check_links(message.from_user.id)
        
        if not_subscribed or not_clicked:
            markup = types.InlineKeyboardMarkup()
            
            for item in not_subscribed:
                chat = item["data"]
                if chat.username:
                    markup.add(types.InlineKeyboardButton(
                        f"📢 {chat.title}",
                        url=f"https://t.me/{chat.username}"
                    ))
                elif chat.invite_link:
                    markup.add(types.InlineKeyboardButton(
                        f"📢 {chat.title}",
                        url=chat.invite_link
                    ))
            
            for link in not_clicked:
                tracking_url = f"https://t.me/{BOT_USERNAME}?start=link_{link['id']}"
                markup.add(types.InlineKeyboardButton(
                    f"🔗 {link['name']}",
                    url=tracking_url
                ))
            
            markup.add(types.InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub"))
            
            bot.send_message(
                message.chat.id,
                "❌ Для использования бота выполните условия:",
                reply_markup=markup
            )
            return
        
        return func(message)
    return wrapper

# ==================== ГЛАВНОЕ МЕНЮ ====================
def main_menu_keyboard(user):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Профиль 👤", "Игры 🕹️")
    markup.row("🎁 Кейсы", "🏆 Топ")
    markup.row("🖱 Кликер", "💱 Обменник")
    markup.row("Вывод 🤑", "Премиум 🤟")
    markup.row("Рассылка 📢", "Техподдержка 💫")
    if is_admin(user):
        markup.row("🔧 Админ-панель")
    return markup

@bot.message_handler(commands=["start"])
def start_handler(message):
    db = load_db()
    user_id = str(message.from_user.id)
    user = get_user(db, user_id)
    
    user["username"] = message.from_user.username
    save_db(db)
    
    args = message.text.split()
    if len(args) > 1:
        param = args[1]
        
        if param.startswith("link_"):
            link_id = param[5:]
            if link_id in db.get("links", {}):
                if "clicked_links" not in user:
                    user["clicked_links"] = []
                if link_id not in user["clicked_links"]:
                    user["clicked_links"].append(link_id)
                    save_db(db)
                
                original_url = db["links"][link_id]["url"]
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔗 Перейти", url=original_url))
                bot.send_message(message.chat.id, "✅ Переход засчитан! Нажмите кнопку ниже:", reply_markup=markup)
                return
        
        elif param.isdigit() and user["referrer"] is None:
            ref_id = param
            if ref_id != user_id and ref_id in db["users"]:
                user["referrer"] = ref_id
                referrer = get_user(db, ref_id)
                reward = 1.5 if has_premium(db, ref_id) else 1
                referrer["balance"] += reward
                referrer["referrals"] += 1
                save_db(db)
                try:
                    bot.send_message(int(ref_id), f"🎉 По вашей ссылке зарегистрировался новый пользователь! +{reward}🌟")
                except:
                    pass
    
    save_db(db)
    
    if not is_admin(message.from_user):
        if str(message.from_user.id) in db.get("banned", []):
            bot.send_message(message.chat.id, "❌ Вы заблокированы в боте.")
            return
        
        not_subscribed = check_subscription(message.from_user.id)
        not_clicked = check_links(message.from_user.id)
        
        if not_subscribed or not_clicked:
            markup = types.InlineKeyboardMarkup()
            
            for item in not_subscribed:
                chat = item["data"]
                if chat.username:
                    markup.add(types.InlineKeyboardButton(
                        f"📢 {chat.title}",
                        url=f"https://t.me/{chat.username}"
                    ))
                elif chat.invite_link:
                    markup.add(types.InlineKeyboardButton(
                        f"📢 {chat.title}",
                        url=chat.invite_link
                    ))
            
            for link in not_clicked:
                tracking_url = f"https://t.me/{BOT_USERNAME}?start=link_{link['id']}"
                markup.add(types.InlineKeyboardButton(
                    f"🔗 {link['name']}",
                    url=tracking_url
                ))
            
            markup.add(types.InlineKeyboardButton("✅ Проверить", callback_data="check_sub"))
            
            bot.send_message(
                message.chat.id,
                "❌ Для использования бота выполните условия:",
                reply_markup=markup
            )
            return
    
    bot.send_message(
        message.chat.id,
        "Приветствую вас в боте giftskelms тут можно заработать и вывести звезды⭐️",
        reply_markup=main_menu_keyboard(message.from_user)
    )

# ==================== ПРОФИЛЬ ====================
def profile_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🎁 Ежедневка", "🧑‍🤝‍🧑 Пригласить друга")
    markup.row("🎟 Промокод", "🌟 Пополнить")
    markup.row("🎫 Создать промокод")
    markup.row("Назад ◀️")
    return markup

@bot.message_handler(func=lambda m: m.text == "Профиль 👤")
@subscription_required
def profile_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    update_username(db, message.from_user)
    
    premium_status = "Неактивен"
    if has_premium(db, message.from_user.id):
        premium_date = datetime.fromisoformat(user["premium_until"])
        premium_status = f"Активен до {premium_date.strftime('%d.%m.%Y %H:%M')}"
    
    text = f"""👤 Текущая информация ℹ️

💫 Звезд на балансе: {user['balance']} 🌟
⭐️ Кусков звезды: {user['pieces']}
🧑‍🤝‍🧑 Приглашено друзей: {user['referrals']}
🤑 Вывел звезд: {user['withdrawn']}
👑 Премиум: {premium_status}"""
    
    bot.send_message(message.chat.id, text, reply_markup=profile_keyboard())

@bot.message_handler(func=lambda m: m.text == "Назад ◀️")
@subscription_required
def back_handler(message):
    user_states.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        "Приветствую вас в боте giftskelms тут можно заработать и вывести звезды⭐️",
        reply_markup=main_menu_keyboard(message.from_user)
    )

# ==================== ПОПОЛНЕНИЕ ====================
@bot.message_handler(func=lambda m: m.text == "🌟 Пополнить")
@subscription_required
def topup_handler(message):
    user_states[message.from_user.id] = "waiting_topup_amount"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("10", "50", "100")
    markup.row("250", "500", "1000")
    markup.row("Назад ◀️")
    
    bot.send_message(
        message.chat.id,
        "🌟 Пополнение баланса\n\nВведите сумму звёзд для пополнения или выберите из предложенных:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_topup_amount")
@subscription_required
def topup_amount_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        profile_handler(message)
        return
    
    try:
        amount = int(message.text)
        if amount < 1:
            bot.send_message(message.chat.id, "❌ Минимальная сумма: 1 звезда")
            return
        if amount > 10000:
            bot.send_message(message.chat.id, "❌ Максимальная сумма: 10000 звёзд")
            return
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите число!")
        return
    
    user_states.pop(message.from_user.id, None)
    
    try:
        bot.send_invoice(
            chat_id=message.chat.id,
            title=f"Пополнение на {amount} ⭐",
            description=f"Пополнение баланса в боте на {amount} звёзд",
            invoice_payload=f"topup_{message.from_user.id}_{amount}",
            provider_token="",
            currency="XTR",
            prices=[types.LabeledPrice(label=f"{amount} звёзд", amount=amount)],
            start_parameter=f"topup_{amount}"
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка создания платежа: {e}")
        bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu_keyboard(message.from_user))

@bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout_handler(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=["successful_payment"])
def successful_payment_handler(message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    
    if payload.startswith("topup_"):
        parts = payload.split("_")
        user_id = parts[1]
        amount = int(parts[2])
        
        db = load_db()
        user = get_user(db, user_id)
        user["balance"] += amount
        save_db(db)
        
        bot.send_message(
            message.chat.id,
            f"✅ Оплата успешна!\n\n💫 Начислено: {amount} 🌟\n💰 Ваш баланс: {user['balance']} 🌟",
            reply_markup=main_menu_keyboard(message.from_user)
        )
    
    elif payload.startswith("premium_"):
        parts = payload.split("_")
        user_id = parts[1]
        days = int(parts[2])
        
        db = load_db()
        user = get_user(db, user_id)
        
        if user["premium_until"] and has_premium(db, user_id):
            current = datetime.fromisoformat(user["premium_until"])
        else:
            current = datetime.now()
        
        user["premium_until"] = (current + timedelta(days=days)).isoformat()
        save_db(db)
        
        bot.send_message(
            message.chat.id,
            f"✅ Премиум активирован!\n\n👑 Премиум до: {datetime.fromisoformat(user['premium_until']).strftime('%d.%m.%Y %H:%M')}",
            reply_markup=main_menu_keyboard(message.from_user)
        )
    
    elif payload.startswith("emoji_"):
        user_id = payload.split("_")[1]
        user_states[int(user_id)] = "waiting_custom_emoji"
        bot.send_message(
            message.chat.id,
            "✅ Оплата успешна! Теперь отправьте эмодзи, который хотите видеть в топе:"
        )
    
    elif payload.startswith("title_"):
        user_id = payload.split("_")[1]
        user_states[int(user_id)] = "waiting_custom_title"
        bot.send_message(
            message.chat.id,
            "✅ Оплата успешна! Теперь отправьте звание (до 20 символов):"
        )

# ==================== КАСТОМНЫЙ ЭМОДЗИ ====================
@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_custom_emoji")
def custom_emoji_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    user["custom_emoji"] = message.text.strip()[:5]
    save_db(db)
    
    user_states.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        f"✅ Эмодзи установлен: {user['custom_emoji']}",
        reply_markup=main_menu_keyboard(message.from_user)
    )

# ==================== КАСТОМНОЕ ЗВАНИЕ ====================
@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_custom_title")
def custom_title_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    user["custom_title"] = message.text.strip()[:20]
    save_db(db)
    
    user_states.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        f"✅ Звание установлено: 「{user['custom_title']}」",
        reply_markup=main_menu_keyboard(message.from_user)
    )

# ==================== ЕЖЕДНЕВКА ====================
@bot.message_handler(func=lambda m: m.text == "🎁 Ежедневка")
@subscription_required
def daily_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    update_username(db, message.from_user)
    
    today = datetime.now().date().isoformat()
    
    if user["last_daily"] == today:
        bot.send_message(message.chat.id, "❌ Вы уже забрали ежедневный бонус сегодня!\n⏰ Приходите завтра после 00:00")
        return
    
    bonus = 1
    user["balance"] += bonus
    user["last_daily"] = today
    save_db(db)
    
    bot.send_message(message.chat.id, f"🎁 Вы получили ежедневный бонус: +{bonus}🌟\n💫 Ваш баланс: {user['balance']}🌟")

# ==================== РЕФЕРАЛЬНАЯ ССЫЛКА ====================
@bot.message_handler(func=lambda m: m.text == "🧑‍🤝‍🧑 Пригласить друга")
@subscription_required
def referral_handler(message):
    db = load_db()
    update_username(db, message.from_user)
    
    user_id = message.from_user.id
    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    
    reward = "1.5🌟" if has_premium(db, user_id) else "1🌟"
    
    text = f"""🧑‍🤝‍🧑 Пригласи друга и получи {reward}!

🔗 Твоя реферальная ссылка:
{ref_link}

📤 Отправь эту ссылку другу, и когда он запустит бота, ты получишь награду!"""
    
    bot.send_message(message.chat.id, text)

# ==================== ПРОМОКОДЫ ====================
@bot.message_handler(func=lambda m: m.text == "🎟 Промокод")
@subscription_required
def promocode_handler(message):
    db = load_db()
    update_username(db, message.from_user)
    
    user_states[message.from_user.id] = "waiting_promocode"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Назад ◀️")
    bot.send_message(message.chat.id, "🎟 Введите промокод:", reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_promocode")
@subscription_required
def promocode_input_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        profile_handler(message)
        return
    
    db = load_db()
    code = message.text.strip().upper()
    user_id = str(message.from_user.id)
    
    if code not in db.get("promocodes", {}):
        bot.send_message(message.chat.id, "❌ Промокод не найден!")
        return
    
    promo = db["promocodes"][code]
    
    if user_id in promo.get("used_by", []):
        bot.send_message(message.chat.id, "❌ Вы уже использовали этот промокод!")
        return
    
    if promo["activations"] <= 0:
        bot.send_message(message.chat.id, "❌ Промокод больше не активен!")
        return
    
    user = get_user(db, user_id)
    
    promo_type = promo.get("type", "stars")
    amount = promo.get("stars", 0) if promo_type == "stars" else promo.get("pieces", 0)
    
    if promo_type == "stars":
        user["balance"] += amount
        reward_text = f"+{amount}🌟"
    else:
        user["pieces"] += amount
        reward_text = f"+{amount} кусков"
    
    promo["activations"] -= 1
    if "used_by" not in promo:
        promo["used_by"] = []
    promo["used_by"].append(user_id)
    save_db(db)
    
    user_states.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        f"✅ Промокод активирован! {reward_text}\n💫 Ваш баланс: {user['balance']}🌟\n⭐️ Кусков: {user['pieces']}",
        reply_markup=profile_keyboard()
    )

# ==================== СОЗДАТЬ ПРОМОКОД (ПОЛЬЗОВАТЕЛЬ) ====================
@bot.message_handler(func=lambda m: m.text == "🎫 Создать промокод")
@subscription_required
def user_create_promo_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    update_username(db, message.from_user)
    
    user_states[message.from_user.id] = "user_create_promo_amount"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("1000", "5000", "10000")
    markup.row("Назад ◀️")
    
    text = f"""🎫 Создание промокода на куски

⭐️ У вас кусков: {user['pieces']}

Введите количество кусков для промокода:
(Промокод будет на 1 активацию)"""
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "user_create_promo_amount")
@subscription_required
def user_create_promo_amount_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        profile_handler(message)
        return
    
    try:
        amount = int(message.text)
        if amount <= 0:
            bot.send_message(message.chat.id, "❌ Количество должно быть больше 0!")
            return
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите число!")
        return
    
    db = load_db()
    user = get_user(db, message.from_user.id)
    
    if user["pieces"] < amount:
        bot.send_message(message.chat.id, f"❌ Недостаточно кусков! У вас: {user['pieces']}")
        return
    
    code = f"USER{random.randint(100000, 999999)}"
    
    user["pieces"] -= amount
    db["promocodes"][code] = {
        "type": "pieces",
        "pieces": amount,
        "activations": 1,
        "used_by": [],
        "creator": str(message.from_user.id)
    }
    save_db(db)
    
    user_states.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        f"✅ Промокод создан!\n\n🎫 Код: `{code}`\n⭐️ Кусков: {amount}\n🔢 Активаций: 1",
        parse_mode="Markdown",
        reply_markup=profile_keyboard()
    )

# ==================== КЛИКЕР ====================
@bot.message_handler(func=lambda m: m.text == "🖱 Кликер")
@subscription_required
def clicker_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    update_username(db, message.from_user)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🖱 КЛИК (+100 кусков)", callback_data="click"))
    
    text = f"""🖱 Кликер

⭐️ У вас кусков: {user['pieces']}

Нажимайте кнопку и получайте куски звёзд!
За каждый клик: +100 кусков"""
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "click")
def click_callback(call):
    db = load_db()
    user = get_user(db, call.from_user.id)
    
    user["pieces"] += 100
    save_db(db)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🖱 КЛИК (+100 кусков)", callback_data="click"))
    
    try:
        bot.edit_message_text(
            f"🖱 Кликер\n\n⭐️ У вас кусков: {user['pieces']}\n\n+100 кусков! 🎉",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    except:
        pass
    
    bot.answer_callback_query(call.id, "+100 кусков!")

# ==================== ОБМЕННИК ====================
@bot.message_handler(func=lambda m: m.text == "💱 Обменник")
@subscription_required
def exchange_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    update_username(db, message.from_user)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💱 Обменять 10,000 кусков → 1.5🌟", callback_data="exchange"))
    
    text = f"""💱 Обменник

💫 Звёзд: {user['balance']}🌟
⭐️ Кусков: {user['pieces']}

Курс обмена: 10,000 кусков = 1.5🌟"""
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "exchange")
def exchange_callback(call):
    db = load_db()
    user = get_user(db, call.from_user.id)
    
    if user["pieces"] < 10000:
        bot.answer_callback_query(call.id, f"❌ Недостаточно кусков! Нужно 10,000, у вас {user['pieces']}")
        return
    
    user["pieces"] -= 10000
    user["balance"] += 1.5
    save_db(db)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💱 Обменять 10,000 кусков → 1.5🌟", callback_data="exchange"))
    
    try:
        bot.edit_message_text(
            f"💱 Обменник\n\n💫 Звёзд: {user['balance']}🌟\n⭐️ Кусков: {user['pieces']}\n\n✅ Обмен успешен! +1.5🌟",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    except:
        pass
    
    bot.answer_callback_query(call.id, "✅ Обмен успешен! +1.5🌟")

# ==================== ТОП ====================
@bot.message_handler(func=lambda m: m.text == "🏆 Топ")
@subscription_required
def top_handler(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🏆 Топ по звёздам", "👥 Топ по рефералам")
    markup.row("Назад ◀️")
    
    bot.send_message(message.chat.id, "🏆 Выберите топ:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🏆 Топ по звёздам")
@subscription_required
def top_stars_handler(message):
    db = load_db()
    
    users_list = []
    for uid, udata in db["users"].items():
        users_list.append({
            "id": uid,
            "username": udata.get("username"),
            "balance": udata.get("balance", 0),
            "premium": has_premium(db, uid),
            "emoji": udata.get("custom_emoji"),
            "title": udata.get("custom_title")
        })
    
    users_list.sort(key=lambda x: x["balance"], reverse=True)
    top_10 = users_list[:10]
    
    text = "🏆 Топ-10 по звёздам:\n\n"
    for i, u in enumerate(top_10, 1):
        premium_icon = "💎 " if u["premium"] else ""
        emoji = f"{u['emoji']} " if u["emoji"] else ""
        username = f"@{u['username']}" if u["username"] else f"ID:{u['id']}"
        title = f"\n   「{u['title']}」" if u["title"] else ""
        
        text += f"{i}. {premium_icon}{emoji}{username} — {u['balance']}🌟{title}\n"
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "👥 Топ по рефералам")
@subscription_required
def top_refs_handler(message):
    db = load_db()
    
    users_list = []
    for uid, udata in db["users"].items():
        users_list.append({
            "id": uid,
            "username": udata.get("username"),
            "referrals": udata.get("referrals", 0),
            "premium": has_premium(db, uid),
            "emoji": udata.get("custom_emoji"),
            "title": udata.get("custom_title")
        })
    
    users_list.sort(key=lambda x: x["referrals"], reverse=True)
    top_10 = users_list[:10]
    
    text = "👥 Топ-10 по рефералам:\n\n"
    for i, u in enumerate(top_10, 1):
        premium_icon = "💎 " if u["premium"] else ""
        emoji = f"{u['emoji']} " if u["emoji"] else ""
        username = f"@{u['username']}" if u["username"] else f"ID:{u['id']}"
        title = f"\n   「{u['title']}」" if u["title"] else ""
        
        text += f"{i}. {premium_icon}{emoji}{username} — {u['referrals']} рефералов{title}\n"
    
    bot.send_message(message.chat.id, text)

# ==================== КЕЙСЫ ====================
@bot.message_handler(func=lambda m: m.text == "🎁 Кейсы")
@subscription_required
def cases_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🗑 Кейс со свалки (1🌟)")
    markup.row("💰 Кейс богача (20🌟)")
    markup.row("🐻 Кейс медведя (5🌟)")
    markup.row("⚡ Кейс СУПЕР (10🌟)")
    markup.row("Назад ◀️")
    
    premium_text = " (7% с премиумом)" if has_premium(db, message.from_user.id) else " (3%)"
    
    text = f"""🎁 Кейсы

💫 Ваш баланс: {user['balance']}🌟

🗑 Кейс со свалки — 1🌟
   0-10,000 кусков звёзд

💰 Кейс богача — 20🌟
   10% — 40🌟, 90% — 15🌟

🐻 Кейс медведя — 5🌟
   5% — 🧸 Мишка, 45% — 2🌟, 50% — ничего

⚡ Кейс СУПЕР — 10🌟
   💍 Колечко{premium_text}, 95% — ничего"""
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🗑 Кейс со свалки (1🌟)")
@subscription_required
def case_trash_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    
    if user["balance"] < 1:
        bot.send_message(message.chat.id, "❌ Недостаточно звёзд!")
        return
    
    user["balance"] -= 1
    pieces_won = random.randint(0, 10000)
    user["pieces"] += pieces_won
    save_db(db)
    
    bot.send_message(message.chat.id, f"🗑 Вы открыли Кейс со свалки!\n\n⭐️ Выпало: {pieces_won} кусков звёзд!")

@bot.message_handler(func=lambda m: m.text == "💰 Кейс богача (20🌟)")
@subscription_required
def case_rich_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    
    if user["balance"] < 20:
        bot.send_message(message.chat.id, "❌ Недостаточно звёзд!")
        return
    
    user["balance"] -= 20
    
    if random.random() < 0.1:
        win = 40
    else:
        win = 15
    
    user["balance"] += win
    save_db(db)
    
    bot.send_message(message.chat.id, f"💰 Вы открыли Кейс богача!\n\n🎉 Выпало: {win}🌟!")

@bot.message_handler(func=lambda m: m.text == "🐻 Кейс медведя (5🌟)")
@subscription_required
def case_bear_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    
    if user["balance"] < 5:
        bot.send_message(message.chat.id, "❌ Недостаточно звёзд!")
        return
    
    user["balance"] -= 5
    save_db(db)
    
    roll = random.random()
    
    if roll < 0.05:
        result = "🧸 МИШКА!"
        for admin_username in ADMINS_USERNAMES:
            try:
                for uid, udata in db["users"].items():
                    if udata.get("username", "").lower() == admin_username.lower():
                        bot.send_message(int(uid), f"🎉 ВЫИГРЫШ МИШКИ!\n\n👤 @{message.from_user.username or 'нет'}\n🆔 {message.from_user.id}")
                        break
            except:
                pass
    elif roll < 0.5:
        result = "2🌟"
        user["balance"] += 2
        save_db(db)
    else:
        result = "Ничего 😔"
    
    bot.send_message(message.chat.id, f"🐻 Вы открыли Кейс медведя!\n\n🎰 Выпало: {result}")

@bot.message_handler(func=lambda m: m.text == "⚡ Кейс СУПЕР (10🌟)")
@subscription_required
def case_super_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    
    if user["balance"] < 10:
        bot.send_message(message.chat.id, "❌ Недостаточно звёзд!")
        return
    
    user["balance"] -= 10
    save_db(db)
    
    ring_chance = 0.07 if has_premium(db, message.from_user.id) else 0.03
    
    if random.random() < ring_chance:
        result = "💍 ТГ КОЛЕЧКО!"
        for admin_username in ADMINS_USERNAMES:
            try:
                for uid, udata in db["users"].items():
                    if udata.get("username", "").lower() == admin_username.lower():
                        bot.send_message(int(uid), f"🎉 ВЫИГРЫШ КОЛЕЧКА!\n\n👤 @{message.from_user.username or 'нет'}\n🆔 {message.from_user.id}")
                        break
            except:
                pass
    else:
        result = "Ничего 😔"
    
    bot.send_message(message.chat.id, f"⚡ Вы открыли Кейс СУПЕР!\n\n🎰 Выпало: {result}")

# ==================== ПРЕМИУМ ====================
def premium_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👑 Купить премиум")
    markup.row("🌟 Пополнить")
    markup.row("🎨 Купить эмодзи (3⭐️)")
    markup.row("🏷 Купить звание (4⭐️)")
    markup.row("Назад ◀️")
    return markup

@bot.message_handler(func=lambda m: m.text == "Премиум 🤟")
@subscription_required
def premium_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    
    premium_status = "Неактивен"
    if has_premium(db, message.from_user.id):
        premium_date = datetime.fromisoformat(user["premium_until"])
        premium_status = f"Активен до {premium_date.strftime('%d.%m.%Y %H:%M')}"
    
    text = f"""👑 Премиум подписка

Статус: {premium_status}

🎁 Бонусы премиума:
• 💎 Алмаз в топе рядом с ником
• 💍 Шанс на колечко в Кейсе СУПЕР: 3% → 7%
• 🎮 Шанс победы в играх: +1.2%
• 👥 Награда за реферала: 1🌟 → 1.5🌟
• 📊 Доступ к статистике бота
• 💖 Поддержка автора

💰 Цена: 5⭐️ / день (реальные Telegram Stars)"""
    
    bot.send_message(message.chat.id, text, reply_markup=premium_keyboard())

@bot.message_handler(func=lambda m: m.text == "👑 Купить премиум")
@subscription_required
def buy_premium_handler(message):
    user_states[message.from_user.id] = "waiting_premium_days"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("1", "3", "7")
    markup.row("14", "30")
    markup.row("Назад ◀️")
    
    bot.send_message(
        message.chat.id,
        "👑 На сколько дней купить премиум?\n\n💰 Цена: 5⭐️ за день",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_premium_days")
@subscription_required
def premium_days_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        premium_handler(message)
        return
    
    try:
        days = int(message.text)
        if days < 1:
            bot.send_message(message.chat.id, "❌ Минимум 1 день!")
            return
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите число!")
        return
    
    user_states.pop(message.from_user.id, None)
    price = days * 5
    
    try:
        bot.send_invoice(
            chat_id=message.chat.id,
            title=f"Премиум на {days} дней",
            description=f"Премиум подписка в боте на {days} дней",
            invoice_payload=f"premium_{message.from_user.id}_{days}",
            provider_token="",
            currency="XTR",
            prices=[types.LabeledPrice(label=f"Премиум {days} дней", amount=price)],
            start_parameter=f"premium_{days}"
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == "🎨 Купить эмодзи (3⭐️)")
@subscription_required
def buy_emoji_handler(message):
    try:
        bot.send_invoice(
            chat_id=message.chat.id,
            title="Эмодзи для топа",
            description="Кастомный эмодзи рядом с вашим ником в топе",
            invoice_payload=f"emoji_{message.from_user.id}",
            provider_token="",
            currency="XTR",
            prices=[types.LabeledPrice(label="Эмодзи", amount=3)],
            start_parameter="emoji"
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == "🏷 Купить звание (4⭐️)")
@subscription_required
def buy_title_handler(message):
    try:
        bot.send_invoice(
            chat_id=message.chat.id,
            title="Звание для топа",
            description="Кастомное звание под вашим ником в топе",
            invoice_payload=f"title_{message.from_user.id}",
            provider_token="",
            currency="XTR",
            prices=[types.LabeledPrice(label="Звание", amount=4)],
            start_parameter="title"
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

# ==================== ИГРЫ ====================
def games_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🎰 Орёл или решка", "🎲 Кубик")
    markup.row("🎯 Дротик", "🎳 Боулинг")
    markup.row("🏀 Баскетбол", "⚽ Футбол")
    markup.row("🦔 Пнуть ежа")
    markup.row("Назад ◀️")
    return markup

GAMES_CONFIG = {
    "🎰 Орёл или решка": {"emoji": "🎰", "win_values": [1, 22, 43, 64], "win_reward": 0.5, "lose_penalty": 0.5, "name": "slot"},
    "🎲 Кубик": {"emoji": "🎲", "win_values": [6], "win_reward": 2.5, "lose_penalty": 0.5, "name": "dice"},
    "🎯 Дротик": {"emoji": "🎯", "win_values": [6], "win_reward": 2.5, "lose_penalty": 0.5, "name": "darts"},
    "🎳 Боулинг": {"emoji": "🎳", "win_values": [6], "win_reward": 2.5, "lose_penalty": 0.5, "name": "bowling"},
    "🏀 Баскетбол": {"emoji": "🏀", "win_values": [4, 5], "win_reward": 2.0, "lose_penalty": 0.5, "name": "basketball"},
    "⚽ Футбол": {"emoji": "⚽", "win_values": [3, 4, 5], "win_reward": 1.0, "lose_penalty": 0.5, "name": "football"}
}

@bot.message_handler(func=lambda m: m.text == "Игры 🕹️")
@subscription_required
def games_handler(message):
    db = load_db()
    update_username(db, message.from_user)
    
    text = """🕹️ Игры

Выберите игру. Кулдаун: 1 минута на каждую игру.

🎰 Орёл или решка: 50% +0.5🌟 / 50% -0.5🌟
🎲 Кубик: выпадет 6 = +2.5🌟, иначе -0.5🌟
🎯 Дротик: яблочко = +2.5🌟, иначе -0.5🌟
🎳 Боулинг: страйк = +2.5🌟, иначе -0.5🌟
🏀 Баскетбол: попал = +2.0🌟, иначе -0.5🌟
⚽ Футбол: гол = +1.0🌟, иначе -0.5🌟
🦔 Пнуть ежа: 50% +200% ставки / 50% -ставка

👑 Премиум: +1.2% к шансу победы"""
    
    bot.send_message(message.chat.id, text, reply_markup=games_keyboard())

@bot.message_handler(func=lambda m: m.text in GAMES_CONFIG.keys())
@subscription_required
def game_handler(message):
    db = load_db()
    user_id = str(message.from_user.id)
    user = get_user(db, user_id)
    update_username(db, message.from_user)
    
    game_config = GAMES_CONFIG[message.text]
    game_name = game_config["name"]
    
    cooldowns = user.get("cooldowns", {})
    last_play = cooldowns.get(game_name, 0)
    now = time.time()
    
    if now - last_play < 60:
        remaining = int(60 - (now - last_play))
        bot.send_message(message.chat.id, f"⏳ Подождите ещё {remaining} сек. перед следующей игрой!")
        return
    
    if user["balance"] < game_config["lose_penalty"]:
        bot.send_message(message.chat.id, f"❌ Недостаточно звёзд для игры! Нужно минимум {game_config['lose_penalty']}🌟")
        return
    
    user["cooldowns"][game_name] = now
    save_db(db)
    
    result_msg = bot.send_dice(message.chat.id, emoji=game_config["emoji"])
    value = result_msg.dice.value
    
    db = load_db()
    user = get_user(db, user_id)
    
    win_values = game_config["win_values"].copy()
    
    if has_premium(db, user_id):
        extra_chance = 0.012
        if random.random() < extra_chance:
            win_values = list(range(1, 100))
    
    if value in win_values:
        user["balance"] += game_config["win_reward"]
        result_text = f"🎉 Победа! +{game_config['win_reward']}🌟\n💫 Баланс: {user['balance']}🌟"
    else:
        user["balance"] -= game_config["lose_penalty"]
        user["balance"] = max(0, user["balance"])
        result_text = f"😔 Не повезло! -{game_config['lose_penalty']}🌟\n💫 Баланс: {user['balance']}🌟"
    
    save_db(db)
    
    time.sleep(4)
    bot.send_message(message.chat.id, result_text)

# ==================== ПНУТЬ ЕЖА ====================
@bot.message_handler(func=lambda m: m.text == "🦔 Пнуть ежа")
@subscription_required
def hedgehog_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    update_username(db, message.from_user)
    
    cooldowns = user.get("cooldowns", {})
    last_play = cooldowns.get("hedgehog", 0)
    now = time.time()
    
    if now - last_play < 60:
        remaining = int(60 - (now - last_play))
        bot.send_message(message.chat.id, f"⏳ Подождите ещё {remaining} сек. перед следующей игрой!")
        return
    
    user_states[message.from_user.id] = "waiting_hedgehog_bet"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("1", "5", "10")
    markup.row("25", "50", "100")
    markup.row("Назад ◀️")
    
    text = f"""🦔 Пнуть ежа

💫 Ваш баланс: {user['balance']}🌟

Выберите ставку или введите свою:
• Победа (50%): +200% от ставки
• Проигрыш (50%): ёж мстит, -ставка"""
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_hedgehog_bet")
@subscription_required
def hedgehog_bet_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        games_handler(message)
        return
    
    try:
        bet = float(message.text)
        if bet <= 0:
            bot.send_message(message.chat.id, "❌ Ставка должна быть больше 0!")
            return
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите число!")
        return
    
    db = load_db()
    user_id = str(message.from_user.id)
    user = get_user(db, user_id)
    
    if user["balance"] < bet:
        bot.send_message(message.chat.id, f"❌ Недостаточно звёзд! У вас {user['balance']}🌟")
        return
    
    user_states.pop(message.from_user.id, None)
    
    user["cooldowns"]["hedgehog"] = time.time()
    save_db(db)
    
    bot.send_message(message.chat.id, "🦶 Вы замахиваетесь на ежа...")
    time.sleep(2)
    
    win_chance = 0.512 if has_premium(db, user_id) else 0.5
    win = random.random() < win_chance
    
    db = load_db()
    user = get_user(db, user_id)
    
    if win:
        winnings = bet * 2
        user["balance"] += winnings
        result_text = f"🎉 Вы пнули ежа! Он улетел!\n\n💰 Выигрыш: +{winnings}🌟\n💫 Баланс: {user['balance']}🌟"
    else:
        user["balance"] -= bet
        user["balance"] = max(0, user["balance"])
        result_text = f"🦔💢 Ёж разозлился и отомстил!\n\n😔 Проигрыш: -{bet}🌟\n💫 Баланс: {user['balance']}🌟"
    
    save_db(db)
    bot.send_message(message.chat.id, result_text, reply_markup=games_keyboard())

# ==================== ТЕХПОДДЕРЖКА ====================
@bot.message_handler(func=lambda m: m.text == "Техподдержка 💫")
@subscription_required
def support_handler(message):
    db = load_db()
    update_username(db, message.from_user)
    
    text = """💫 Техподдержка

По всем вопросам вы можете написать нашим администраторам:

👤 @ww13kelm
👤 @MONSTER_PSY"""
    
    bot.send_message(message.chat.id, text)

# ==================== ВЫВОД ====================
def withdraw_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💫 Вывести 500🌟", "💫 Вывести 1000🌟")
    markup.row("Назад ◀️")
    return markup

@bot.message_handler(func=lambda m: m.text == "Вывод 🤑")
@subscription_required
def withdraw_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    update_username(db, message.from_user)
    
    if user["balance"] < 500:
        bot.send_message(
            message.chat.id,
            f"❌ Для вывода нужно минимум 500🌟\n💫 Ваш баланс: {user['balance']}🌟"
        )
        return
    
    if user["last_withdraw"]:
        try:
            last_withdraw_date = datetime.fromisoformat(user["last_withdraw"])
            days_passed = (datetime.now() - last_withdraw_date).days
            if days_passed < 7:
                days_left = 7 - days_passed
                bot.send_message(
                    message.chat.id,
                    f"❌ Вывод доступен раз в неделю!\n⏳ Осталось дней: {days_left}"
                )
                return
        except:
            pass
    
    text = f"""🤑 Вывод звёзд

💫 Ваш баланс: {user['balance']}🌟

Выберите сколько звёзд вывести:"""
    
    bot.send_message(message.chat.id, text, reply_markup=withdraw_keyboard())

@bot.message_handler(func=lambda m: m.text in ["💫 Вывести 500🌟", "💫 Вывести 1000🌟"])
@subscription_required
def withdraw_amount_handler(message):
    db = load_db()
    user_id = str(message.from_user.id)
    user = get_user(db, user_id)
    update_username(db, message.from_user)
    
    amount = 500 if "500" in message.text else 1000
    
    if user["balance"] < amount:
        bot.send_message(message.chat.id, f"❌ Недостаточно звёзд! Нужно {amount}🌟, у вас {user['balance']}🌟")
        return
    
    if user["last_withdraw"]:
        try:
            last_withdraw_date = datetime.fromisoformat(user["last_withdraw"])
            days_passed = (datetime.now() - last_withdraw_date).days
            if days_passed < 7:
                days_left = 7 - days_passed
                bot.send_message(
                    message.chat.id,
                    f"❌ Вывод доступен раз в неделю!\n⏳ Осталось дней: {days_left}"
                )
                return
        except:
            pass
    
    withdrawal_id = str(int(time.time() * 1000))
    
    reg_date = datetime.fromisoformat(user["registered"])
    days_in_bot = (datetime.now() - reg_date).days
    
    db["withdrawals"][withdrawal_id] = {
        "user_id": user_id,
        "username": message.from_user.username,
        "amount": amount,
        "status": "pending",
        "admin_actions": {},
        "created": datetime.now().isoformat()
    }
    
    user["balance"] -= amount
    user["last_withdraw"] = datetime.now().isoformat()
    save_db(db)
    
    admin_text = f"""📥 Новая заявка на вывод!

💫 Звёзд: {amount}🌟
👤 Username: @{message.from_user.username or 'нет'}
🆔 ID: {user_id}
📅 Дней в боте: {days_in_bot}"""
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Принять", callback_data=f"wd_accept_{withdrawal_id}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"wd_decline_{withdrawal_id}")
    )
    
    for admin_username in ADMINS_USERNAMES:
        try:
            for uid, udata in db["users"].items():
                if udata.get("username", "").lower() == admin_username.lower():
                    bot.send_message(int(uid), admin_text, reply_markup=markup)
                    break
        except:
            pass
    
    bot.send_message(
        message.chat.id,
        f"✅ Заявка на вывод {amount}🌟 создана!\n⏳ Ожидайте подтверждения от администратора.",
        reply_markup=main_menu_keyboard(message.from_user)
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("wd_"))
def withdrawal_callback(call):
    if not is_admin(call.from_user):
        bot.answer_callback_query(call.id, "❌ Только для админов!")
        return
    
    db = load_db()
    parts = call.data.split("_")
    action = parts[1]
    withdrawal_id = parts[2]
    
    if withdrawal_id not in db.get("withdrawals", {}):
        bot.answer_callback_query(call.id, "❌ Заявка не найдена!")
        return
    
    withdrawal = db["withdrawals"][withdrawal_id]
    admin_id = str(call.from_user.id)
    
    if withdrawal["status"] != "pending":
        bot.answer_callback_query(call.id, "❌ Заявка уже обработана!")
        return
    
    if "admin_actions" not in withdrawal:
        withdrawal["admin_actions"] = {}
    
    if action == "accept":
        for aid, act in withdrawal["admin_actions"].items():
            if act == "accepted":
                bot.answer_callback_query(call.id, "Другой админ уже принял заявку!")
                bot.edit_message_text(
                    call.message.text + "\n\n✅ Один из админов уже принял эту заявку.",
                    call.message.chat.id,
                    call.message.message_id
                )
                return
        
        withdrawal["admin_actions"][admin_id] = "accepted"
        withdrawal["status"] = "accepted"
        save_db(db)
        
        for uid, udata in db["users"].items():
            if udata.get("username", "").lower() in ADMINS_USERNAMES and uid != admin_id:
                try:
                    bot.send_message(int(uid), f"ℹ️ Заявка #{withdrawal_id} принята админом @{call.from_user.username}")
                except:
                    pass
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🌟 Отправил", callback_data=f"wd_sent_{withdrawal_id}"))
        
        bot.edit_message_text(
            call.message.text + "\n\n✅ Вы приняли заявку.\n\nОтправьте звёзды пользователю и нажмите кнопку ниже:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        
    elif action == "decline":
        withdrawal["admin_actions"][admin_id] = "declined"
        
        declined_count = sum(1 for act in withdrawal["admin_actions"].values() if act == "declined")
        
        if declined_count >= 2:
            withdrawal["status"] = "declined"
            user = get_user(db, withdrawal["user_id"])
            user["balance"] += withdrawal["amount"]
            user["last_withdraw"] = None
            save_db(db)
            
            try:
                bot.send_message(
                    int(withdrawal["user_id"]),
                    f"❌ Ваша заявка на вывод {withdrawal['amount']}🌟 отклонена.\n💫 Звёзды возвращены на баланс."
                )
            except:
                pass
            
            bot.edit_message_text(
                call.message.text + "\n\n❌ Заявка отклонена обоими админами.",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            save_db(db)
            bot.answer_callback_query(call.id, "Вы отклонили заявку. Ждём решения второго админа.")
            bot.edit_message_text(
                call.message.text + "\n\n⏳ Вы отклонили. Ожидаем решения другого админа.",
                call.message.chat.id,
                call.message.message_id
            )
    
    elif action == "sent":
        withdrawal["status"] = "completed"
        user = get_user(db, withdrawal["user_id"])
        user["withdrawn"] += withdrawal["amount"]
        save_db(db)
        
        bot.edit_message_text(
            call.message.text + "\n\n✅ Вывод завершён!",
            call.message.chat.id,
            call.message.message_id
        )
        
        try:
            bot.send_message(
                int(withdrawal["user_id"]),
                f"🎉 Ваш вывод {withdrawal['amount']}🌟 выполнен!\n⭐️ Звёзды отправлены!"
            )
        except:
            pass

# ==================== РАССЫЛКА ====================
@bot.message_handler(func=lambda m: m.text == "Рассылка 📢")
@subscription_required
def broadcast_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    update_username(db, message.from_user)
    
    if not is_admin(message.from_user) and user["balance"] < 10:
        bot.send_message(message.chat.id, f"❌ Для рассылки нужно 10🌟\n💫 Ваш баланс: {user['balance']}🌟")
        return
    
    cost_text = "" if is_admin(message.from_user) else "\n💰 Стоимость: 10🌟"
    
    user_states[message.from_user.id] = "waiting_broadcast"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Назад ◀️")
    
    bot.send_message(
        message.chat.id,
        f"📢 Рассылка{cost_text}\n\nВведите текст для рассылки всем пользователям:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_broadcast")
@subscription_required
def broadcast_text_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        bot.send_message(
            message.chat.id,
            "Приветствую вас в боте giftskelms тут можно заработать и вывести звезды⭐️",
            reply_markup=main_menu_keyboard(message.from_user)
        )
        return
    
    db = load_db()
    user = get_user(db, message.from_user.id)
    
    if not is_admin(message.from_user):
        if user["balance"] < 10:
            bot.send_message(message.chat.id, "❌ Недостаточно звёзд!")
            return
        user["balance"] -= 10
        save_db(db)
    
    success = 0
    failed = 0
    
    broadcast_text = f"📢 Рассылка от @{message.from_user.username or 'пользователя'}:\n\n{message.text}"
    
    for user_id in db["users"]:
        if user_id not in db.get("banned", []):
            try:
                bot.send_message(int(user_id), broadcast_text)
                success += 1
            except:
                failed += 1
    
    user_states.pop(message.from_user.id, None)
    
    bot.send_message(
        message.chat.id,
        f"✅ Рассылка завершена!\n📤 Доставлено: {success}\n❌ Не доставлено: {failed}",
        reply_markup=main_menu_keyboard(message.from_user)
    )

# ==================== АДМИН-ПАНЕЛЬ ====================
def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🚫 Бан", "✅ Разбан")
    markup.row("💰 Баланс", "➕ Добавить звёзды")
    markup.row("➖ Убрать звёзды", "🎟 Создать промокод")
    markup.row("📢 Админ-рассылка", "📊 Статистика")
    markup.row("📺 Каналы", "🔗 Ссылки")
    markup.row("👑 Премиум себе")
    markup.row("Назад ◀️")
    return markup

@bot.message_handler(func=lambda m: m.text == "🔧 Админ-панель")
def admin_panel_handler(message):
    if not is_admin(message.from_user):
        return
    
    bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())

@bot.message_handler(func=lambda m: m.text == "📊 Статистика")
def stats_handler(message):
    db = load_db()
    
    if not is_admin(message.from_user) and not has_premium(db, message.from_user.id):
        bot.send_message(message.chat.id, "❌ Статистика доступна только для премиум-пользователей!")
        return
    
    total_users = len(db["users"])
    total_balance = sum(u.get("balance", 0) for u in db["users"].values())
    total_pieces = sum(u.get("pieces", 0) for u in db["users"].values())
    total_withdrawn = sum(u.get("withdrawn", 0) for u in db["users"].values())
    banned_count = len(db.get("banned", []))
    channels_count = len(db.get("channels", []))
    links_count = len(db.get("links", {}))
    premium_count = sum(1 for uid in db["users"] if has_premium(db, uid))
    
    text = f"""📊 Статистика бота

👥 Всего пользователей: {total_users}
👑 С премиумом: {premium_count}
🚫 Заблокировано: {banned_count}
💫 Всего звёзд на балансах: {total_balance}🌟
⭐️ Всего кусков: {total_pieces}
🤑 Всего выведено: {total_withdrawn}🌟
📺 Каналов для подписки: {channels_count}
🔗 Обязательных ссылок: {links_count}"""
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "👑 Премиум себе")
def admin_premium_handler(message):
    if not is_admin(message.from_user):
        return
    
    user_states[message.from_user.id] = "admin_premium_days"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("30", "90", "365")
    markup.row("Назад ◀️")
    
    bot.send_message(message.chat.id, "👑 На сколько дней выдать себе премиум?", reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "admin_premium_days")
def admin_premium_days_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())
        return
    
    try:
        days = int(message.text)
        if days < 1:
            bot.send_message(message.chat.id, "❌ Минимум 1 день!")
            return
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите число!")
        return
    
    db = load_db()
    user = get_user(db, message.from_user.id)
    
    if user["premium_until"] and has_premium(db, message.from_user.id):
        current = datetime.fromisoformat(user["premium_until"])
    else:
        current = datetime.now()
    
    user["premium_until"] = (current + timedelta(days=days)).isoformat()
    save_db(db)
    
    user_states.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        f"✅ Премиум активирован на {days} дней!\n👑 До: {datetime.fromisoformat(user['premium_until']).strftime('%d.%m.%Y %H:%M')}",
        reply_markup=admin_keyboard()
    )

# ==================== УПРАВЛЕНИЕ КАНАЛАМИ ====================
@bot.message_handler(func=lambda m: m.text == "📺 Каналы")
def channels_handler(message):
    if not is_admin(message.from_user):
        return
    
    db = load_db()
    channels = db.get("channels", [])
    
    if channels:
        channels_list = ""
        for i, ch in enumerate(channels, 1):
            try:
                chat = bot.get_chat(ch)
                channels_list += f"{i}. {chat.title} ({ch})\n"
            except:
                channels_list += f"{i}. {ch} (недоступен)\n"
    else:
        channels_list = "Список пуст"
    
    text = f"""📺 Управление каналами

Текущие каналы для обязательной подписки:
{channels_list}

Выберите действие:"""
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("➕ Добавить канал", "➖ Удалить канал")
    markup.row("Назад ◀️")
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "➕ Добавить канал")
def add_channel_handler(message):
    if not is_admin(message.from_user):
        return
    
    user_states[message.from_user.id] = "admin_add_channel"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Назад ◀️")
    
    text = """➕ Добавление канала

Отправьте ID канала (например: -1001234567890) или @username канала.

⚠️ Бот должен быть администратором канала!"""
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "admin_add_channel")
def add_channel_input_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        channels_handler(message)
        return
    
    db = load_db()
    channel = message.text.strip()
    
    try:
        chat = bot.get_chat(channel)
        member = bot.get_chat_member(channel, BOT_ID)
        
        if member.status not in ["administrator", "creator"]:
            bot.send_message(message.chat.id, "❌ Бот должен быть администратором канала!")
            return
        
        channel_id = chat.id
        
        if channel_id in db["channels"]:
            bot.send_message(message.chat.id, "❌ Этот канал уже добавлен!")
            return
        
        db["channels"].append(channel_id)
        save_db(db)
        
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, f"✅ Канал «{chat.title}» добавлен!")
        channels_handler(message)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

@bot.message_handler(func=lambda m: m.text == "➖ Удалить канал")
def remove_channel_handler(message):
    if not is_admin(message.from_user):
        return
    
    db = load_db()
    channels = db.get("channels", [])
    
    if not channels:
        bot.send_message(message.chat.id, "❌ Список каналов пуст!")
        return
    
    markup = types.InlineKeyboardMarkup()
    for ch in channels:
        try:
            chat = bot.get_chat(ch)
            title = chat.title
        except:
            title = str(ch)
        markup.add(types.InlineKeyboardButton(f"🗑 {title}", callback_data=f"delchan_{ch}"))
    
    bot.send_message(message.chat.id, "Выберите канал для удаления:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("delchan_"))
def delete_channel_callback(call):
    if not is_admin(call.from_user):
        bot.answer_callback_query(call.id, "❌ Только для админов!")
        return
    
    db = load_db()
    channel_id = int(call.data.split("_")[1])
    
    if channel_id in db.get("channels", []):
        db["channels"].remove(channel_id)
        save_db(db)
        bot.answer_callback_query(call.id, "✅ Канал удалён!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "❌ Канал не найден!")

# ==================== УПРАВЛЕНИЕ ССЫЛКАМИ ====================
@bot.message_handler(func=lambda m: m.text == "🔗 Ссылки")
def links_handler(message):
    if not is_admin(message.from_user):
        return
    
    db = load_db()
    links = db.get("links", {})
    
    if links:
        links_list = ""
        for i, (link_id, link_data) in enumerate(links.items(), 1):
            clicks = len([u for u in db["users"].values() if link_id in u.get("clicked_links", [])])
            links_list += f"{i}. {link_data.get('name', 'Ссылка')} - {clicks} переходов\n   {link_data['url']}\n"
    else:
        links_list = "Список пуст"
    
    text = f"""🔗 Управление ссылками

Обязательные ссылки для перехода:
{links_list}

Выберите действие:"""
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("➕ Добавить ссылку", "➖ Удалить ссылку")
    markup.row("Назад ◀️")
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "➕ Добавить ссылку")
def add_link_handler(message):
    if not is_admin(message.from_user):
        return
    
    user_states[message.from_user.id] = "admin_add_link_name"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Назад ◀️")
    
    bot.send_message(message.chat.id, "➕ Введите название ссылки (будет показано пользователям):", reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "admin_add_link_name")
def add_link_name_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        links_handler(message)
        return
    
    user_states[message.from_user.id] = {"state": "admin_add_link_url", "name": message.text}
    bot.send_message(message.chat.id, "🔗 Теперь отправьте URL ссылки:")

@bot.message_handler(func=lambda m: isinstance(user_states.get(m.from_user.id), dict) and user_states.get(m.from_user.id, {}).get("state") == "admin_add_link_url")
def add_link_url_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        links_handler(message)
        return
    
    url = message.text.strip()
    name = user_states[message.from_user.id]["name"]
    
    link_id = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:8]
    
    db = load_db()
    db["links"][link_id] = {
        "url": url,
        "name": name,
        "created": datetime.now().isoformat()
    }
    save_db(db)
    
    user_states.pop(message.from_user.id, None)
    
    tracking_url = f"https://t.me/{BOT_USERNAME}?start=link_{link_id}"
    
    bot.send_message(
        message.chat.id,
        f"✅ Ссылка добавлена!\n\n📝 Название: {name}\n🔗 URL: {url}\n\n📊 Трекинговая ссылка:\n{tracking_url}"
    )
    links_handler(message)

@bot.message_handler(func=lambda m: m.text == "➖ Удалить ссылку")
def remove_link_handler(message):
    if not is_admin(message.from_user):
        return
    
    db = load_db()
    links = db.get("links", {})
    
    if not links:
        bot.send_message(message.chat.id, "❌ Список ссылок пуст!")
        return
    
    markup = types.InlineKeyboardMarkup()
    for link_id, link_data in links.items():
        markup.add(types.InlineKeyboardButton(
            f"🗑 {link_data.get('name', 'Ссылка')}",
            callback_data=f"dellink_{link_id}"
        ))
    
    bot.send_message(message.chat.id, "Выберите ссылку для удаления:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("dellink_"))
def delete_link_callback(call):
    if not is_admin(call.from_user):
        bot.answer_callback_query(call.id, "❌ Только для админов!")
        return
    
    db = load_db()
    link_id = call.data.split("_")[1]
    
    if link_id in db.get("links", {}):
        del db["links"][link_id]
        save_db(db)
        bot.answer_callback_query(call.id, "✅ Ссылка удалена!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "❌ Ссылка не найдена!")

# ==================== БАН / РАЗБАН ====================
@bot.message_handler(func=lambda m: m.text == "🚫 Бан")
def ban_handler(message):
    if not is_admin(message.from_user):
        return
    
    user_states[message.from_user.id] = "admin_ban"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Назад ◀️")
    bot.send_message(message.chat.id, "Введите ID пользователя для бана:", reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "admin_ban")
def ban_input_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())
        return
    
    db = load_db()
    target_id = message.text.strip()
    
    if not target_id.isdigit():
        bot.send_message(message.chat.id, "❌ Введите ID пользователя (только цифры)!")
        return
    
    if target_id not in db["users"]:
        bot.send_message(message.chat.id, "❌ Пользователь не найден в базе!")
        return
    
    if target_id not in db["banned"]:
        db["banned"].append(target_id)
        save_db(db)
        bot.send_message(message.chat.id, f"✅ Пользователь {target_id} заблокирован!")
    else:
        bot.send_message(message.chat.id, "ℹ️ Пользователь уже заблокирован!")
    
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())

@bot.message_handler(func=lambda m: m.text == "✅ Разбан")
def unban_handler(message):
    if not is_admin(message.from_user):
        return
    
    user_states[message.from_user.id] = "admin_unban"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Назад ◀️")
    bot.send_message(message.chat.id, "Введите ID пользователя для разбана:", reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "admin_unban")
def unban_input_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())
        return
    
    db = load_db()
    target_id = message.text.strip()
    
    if not target_id.isdigit():
        bot.send_message(message.chat.id, "❌ Введите ID пользователя (только цифры)!")
        return
    
    if target_id in db["banned"]:
        db["banned"].remove(target_id)
        save_db(db)
        bot.send_message(message.chat.id, f"✅ Пользователь {target_id} разблокирован!")
    else:
        bot.send_message(message.chat.id, "❌ Пользователь не найден в списке заблокированных!")
    
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())

# ==================== БАЛАНС ====================
@bot.message_handler(func=lambda m: m.text == "💰 Баланс")
def check_balance_handler(message):
    if not is_admin(message.from_user):
        return
    
    user_states[message.from_user.id] = "admin_check_balance"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Назад ◀️")
    bot.send_message(message.chat.id, "Введите ID пользователя:", reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "admin_check_balance")
def check_balance_input_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())
        return
    
    db = load_db()
    target_id = message.text.strip()
    
    if not target_id.isdigit():
        bot.send_message(message.chat.id, "❌ Введите ID пользователя (только цифры)!")
        return
    
    if target_id not in db["users"]:
        bot.send_message(message.chat.id, "❌ Пользователь не найден!")
        return
    
    user = db["users"][target_id]
    premium_status = "Да" if has_premium(db, target_id) else "Нет"
    
    text = f"""💰 Информация о пользователе

🆔 ID: {target_id}
👤 Username: @{user.get('username') or 'нет'}
💫 Баланс: {user.get('balance', 0)}🌟
⭐️ Кусков: {user.get('pieces', 0)}
🧑‍🤝‍🧑 Рефералов: {user.get('referrals', 0)}
🤑 Выведено: {user.get('withdrawn', 0)}🌟
👑 Премиум: {premium_status}"""
    
    bot.send_message(message.chat.id, text)
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())

# ==================== ДОБАВИТЬ ЗВЁЗДЫ ====================
@bot.message_handler(func=lambda m: m.text == "➕ Добавить звёзды")
def add_stars_handler(message):
    if not is_admin(message.from_user):
        return
    
    user_states[message.from_user.id] = "admin_add_stars"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Назад ◀️")
    bot.send_message(message.chat.id, "Введите ID пользователя и количество звёзд через пробел:\nПример: 123456789 100", reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "admin_add_stars")
def add_stars_input_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())
        return
    
    try:
        parts = message.text.strip().split()
        target_id = parts[0]
        amount = float(parts[1])
        
        if not target_id.isdigit():
            bot.send_message(message.chat.id, "❌ ID должен содержать только цифры!")
            return
    except:
        bot.send_message(message.chat.id, "❌ Неверный формат! Пример: 123456789 100")
        return
    
    db = load_db()
    
    if target_id not in db["users"]:
        bot.send_message(message.chat.id, "❌ Пользователь не найден!")
        return
    
    db["users"][target_id]["balance"] = db["users"][target_id].get("balance", 0) + amount
    save_db(db)
    
    bot.send_message(message.chat.id, f"✅ Добавлено {amount}🌟 пользователю {target_id}\n💫 Новый баланс: {db['users'][target_id]['balance']}🌟")
    
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())

# ==================== УБРАТЬ ЗВЁЗДЫ ====================
@bot.message_handler(func=lambda m: m.text == "➖ Убрать звёзды")
def remove_stars_handler(message):
    if not is_admin(message.from_user):
        return
    
    user_states[message.from_user.id] = "admin_remove_stars"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Назад ◀️")
    bot.send_message(message.chat.id, "Введите ID пользователя и количество звёзд через пробел:\nПример: 123456789 50", reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "admin_remove_stars")
def remove_stars_input_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())
        return
    
    try:
        parts = message.text.strip().split()
        target_id = parts[0]
        amount = float(parts[1])
        
        if not target_id.isdigit():
            bot.send_message(message.chat.id, "❌ ID должен содержать только цифры!")
            return
    except:
        bot.send_message(message.chat.id, "❌ Неверный формат! Пример: 123456789 50")
        return
    
    db = load_db()
    
    if target_id not in db["users"]:
        bot.send_message(message.chat.id, "❌ Пользователь не найден!")
        return
    
    db["users"][target_id]["balance"] = max(0, db["users"][target_id].get("balance", 0) - amount)
    save_db(db)
    
    bot.send_message(message.chat.id, f"✅ Убрано {amount}🌟 у пользователя {target_id}\n💫 Новый баланс: {db['users'][target_id]['balance']}🌟")
    
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())

# ==================== ПРОМОКОДЫ (АДМИН) ====================
@bot.message_handler(func=lambda m: m.text == "🎟 Создать промокод")
def create_promo_handler(message):
    if not is_admin(message.from_user):
        return
    
    user_states[message.from_user.id] = "admin_create_promo_type"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("⭐️ На звёзды", "🔸 На куски")
    markup.row("Назад ◀️")
    
    bot.send_message(message.chat.id, "🎟 Выберите тип промокода:", reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "admin_create_promo_type")
def create_promo_type_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())
        return
    
    if message.text == "⭐️ На звёзды":
        user_states[message.from_user.id] = {"state": "admin_create_promo", "type": "stars"}
    elif message.text == "🔸 На куски":
        user_states[message.from_user.id] = {"state": "admin_create_promo", "type": "pieces"}
    else:
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Назад ◀️")
    bot.send_message(message.chat.id, "Введите: КОД КОЛИЧЕСТВО АКТИВАЦИИ\nПример: BONUS 10 100", reply_markup=markup)

@bot.message_handler(func=lambda m: isinstance(user_states.get(m.from_user.id), dict) and user_states.get(m.from_user.id, {}).get("state") == "admin_create_promo")
def create_promo_input_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())
        return
    
    try:
        parts = message.text.strip().split()
        code = parts[0].upper()
        amount = float(parts[1])
        activations = int(parts[2])
    except:
        bot.send_message(message.chat.id, "❌ Неверный формат! Пример: BONUS 10 100")
        return
    
    promo_type = user_states[message.from_user.id]["type"]
    
    db = load_db()
    
    if promo_type == "stars":
        db["promocodes"][code] = {
            "type": "stars",
            "stars": amount,
            "activations": activations,
            "used_by": []
        }
        reward_text = f"{amount}🌟"
    else:
        db["promocodes"][code] = {
            "type": "pieces",
            "pieces": int(amount),
            "activations": activations,
            "used_by": []
        }
        reward_text = f"{int(amount)} кусков"
    
    save_db(db)
    
    bot.send_message(message.chat.id, f"✅ Промокод создан!\n\n🎟 Код: {code}\n🎁 Награда: {reward_text}\n🔢 Активаций: {activations}")
    
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())

# ==================== АДМИН-РАССЫЛКА ====================
@bot.message_handler(func=lambda m: m.text == "📢 Админ-рассылка")
def admin_broadcast_handler(message):
    if not is_admin(message.from_user):
        return
    
    user_states[message.from_user.id] = "admin_broadcast"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Назад ◀️")
    bot.send_message(message.chat.id, "Введите текст для рассылки:", reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "admin_broadcast")
def admin_broadcast_text_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())
        return
    
    db = load_db()
    success = 0
    failed = 0
    
    for user_id in db["users"]:
        if user_id not in db.get("banned", []):
            try:
                bot.send_message(int(user_id), message.text)
                success += 1
            except:
                failed += 1
    
    user_states.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        f"✅ Рассылка завершена!\n📤 Доставлено: {success}\n❌ Не доставлено: {failed}",
        reply_markup=admin_keyboard()
    )

# ==================== ПРОВЕРКА ПОДПИСКИ (callback) ====================
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    not_subscribed = check_subscription(call.from_user.id)
    not_clicked = check_links(call.from_user.id)
    
    if not_subscribed or not_clicked:
        bot.answer_callback_query(call.id, "❌ Выполните все условия!")
    else:
        bot.answer_callback_query(call.id, "✅ Все условия выполнены!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        db = load_db()
        get_user(db, call.from_user.id)
        
        bot.send_message(
            call.message.chat.id,
            "Приветствую вас в боте giftskelms тут можно заработать и вывести звезды⭐️",
            reply_markup=main_menu_keyboard(call.from_user)
        )

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    print(f"🤖 Бот @{BOT_USERNAME} запущен!")
    bot.infinity_polling()
