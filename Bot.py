import telebot
from telebot import types
import json
import os
import time
import random
import hashlib
from datetime import datetime

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8348786219:AAFW5wY-XNhpaeoEgXuuBf28UVbz7Uy8Ngk"

ADMINS_USERNAMES = ["ww13kelm", "monster_psy", "venter8"]
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
    
    # Добавляем недостающие поля (совместимость со старой базой)
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
            "referrals": 0,
            "withdrawn": 0,
            "referrer": None,
            "last_daily": None,
            "cooldowns": {},
            "registered": datetime.now().isoformat(),
            "username": None
        }
        save_db(db)
    
    # Добавляем недостающие поля для старых пользователей
    user = db["users"][user_id]
    if "cooldowns" not in user:
        user["cooldowns"] = {}
    if "registered" not in user:
        user["registered"] = datetime.now().isoformat()
    if "username" not in user:
        user["username"] = None
    if "referrer" not in user:
        user["referrer"] = None
    if "referrals" not in user:
        user["referrals"] = 0
    if "withdrawn" not in user:
        user["withdrawn"] = 0
    if "last_daily" not in user:
        user["last_daily"] = None
    if "clicked_links" not in user:
        user["clicked_links"] = []
    
    return user

def update_username(db, user):
    """Обновляет username пользователя в базе"""
    user_id = str(user.id)
    if user_id in db["users"]:
        db["users"][user_id]["username"] = user.username
        save_db(db)

def is_admin(user):
    username = user.username.lower() if user.username else ""
    return username in ADMINS_USERNAMES or user.id in ADMIN_IDS

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
    """Проверяет, перешёл ли пользователь по всем обязательным ссылкам"""
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
        
        # Проверка каналов
        not_subscribed = check_subscription(message.from_user.id)
        # Проверка ссылок
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
    markup.row("Вывод 🤑", "Рассылка 📢")
    markup.row("Техподдержка 💫")
    if is_admin(user):
        markup.row("🔧 Админ-панель")
    return markup

@bot.message_handler(commands=["start"])
def start_handler(message):
    db = load_db()
    user_id = str(message.from_user.id)
    user = get_user(db, user_id)
    
    # Обновляем username
    user["username"] = message.from_user.username
    save_db(db)
    
    # Обработка параметров start
    args = message.text.split()
    if len(args) > 1:
        param = args[1]
        
        # Проверка на ссылку
        if param.startswith("link_"):
            link_id = param[5:]
            if link_id in db.get("links", {}):
                if "clicked_links" not in user:
                    user["clicked_links"] = []
                if link_id not in user["clicked_links"]:
                    user["clicked_links"].append(link_id)
                    save_db(db)
                
                # Редирект на оригинальную ссылку
                original_url = db["links"][link_id]["url"]
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔗 Перейти", url=original_url))
                bot.send_message(message.chat.id, "✅ Переход засчитан! Нажмите кнопку ниже:", reply_markup=markup)
                return
        
        # Реферальная система
        elif param.isdigit() and user["referrer"] is None:
            ref_id = param
            if ref_id != user_id and ref_id in db["users"]:
                user["referrer"] = ref_id
                db["users"][ref_id]["balance"] += 1
                db["users"][ref_id]["referrals"] += 1
                save_db(db)
                try:
                    bot.send_message(int(ref_id), "🎉 По вашей ссылке зарегистрировался новый пользователь! +1🌟")
                except:
                    pass
    
    save_db(db)
    
    # Проверка подписки
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
    markup.row("Назад ◀️")
    return markup

@bot.message_handler(func=lambda m: m.text == "Профиль 👤")
@subscription_required
def profile_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    update_username(db, message.from_user)
    
    text = f"""👤 Текущая информация ℹ️

💫 Звезд у тебя на балансе: {user['balance']} 🌟
🧑‍🤝‍🧑 Приглашено друзей: {user['referrals']}
🤑 Вывел звезд: {user['withdrawn']}"""
    
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
    
    # Отправляем invoice для оплаты Telegram Stars
    try:
        bot.send_invoice(
            chat_id=message.chat.id,
            title=f"Пополнение на {amount} ⭐",
            description=f"Пополнение баланса в боте на {amount} звёзд",
            invoice_payload=f"topup_{message.from_user.id}_{amount}",
            provider_token="",  # Для Telegram Stars оставляем пустым
            currency="XTR",  # Telegram Stars
            prices=[types.LabeledPrice(label=f"{amount} звёзд", amount=amount)],
            start_parameter=f"topup_{amount}"
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка создания платежа: {e}")
        bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu_keyboard(message.from_user))

# Обработка pre_checkout_query
@bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout_handler(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# Обработка успешной оплаты
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
    
    text = f"""🧑‍🤝‍🧑 Пригласи друга и получи 1🌟!

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
    user["balance"] += promo["stars"]
    promo["activations"] -= 1
    if "used_by" not in promo:
        promo["used_by"] = []
    promo["used_by"].append(user_id)
    save_db(db)
    
    user_states.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        f"✅ Промокод активирован! +{promo['stars']}🌟\n💫 Ваш баланс: {user['balance']}🌟",
        reply_markup=profile_keyboard()
    )

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
🦔 Пнуть ежа: 50% +200% ставки / 50% -ставка"""
    
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
    
    if value in game_config["win_values"]:
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
    
    # Проверка кулдауна
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
    
    # Обновляем кулдаун
    user["cooldowns"]["hedgehog"] = time.time()
    save_db(db)
    
    # Игра
    bot.send_message(message.chat.id, "🦶 Вы замахиваетесь на ежа...")
    time.sleep(2)
    
    win = random.random() < 0.5
    
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
    markup.row("💫 Вывести 50🌟", "💫 Вывести 100🌟")
    markup.row("Назад ◀️")
    return markup

@bot.message_handler(func=lambda m: m.text == "Вывод 🤑")
@subscription_required
def withdraw_handler(message):
    db = load_db()
    user = get_user(db, message.from_user.id)
    update_username(db, message.from_user)
    
    if user["balance"] < 50:
        bot.send_message(
            message.chat.id,
            f"❌ Для вывода нужно минимум 50🌟\n💫 Ваш баланс: {user['balance']}🌟"
        )
        return
    
    text = f"""🤑 Вывод звёзд

💫 Ваш баланс: {user['balance']}🌟

Выберите сколько звёзд вывести:"""
    
    bot.send_message(message.chat.id, text, reply_markup=withdraw_keyboard())

@bot.message_handler(func=lambda m: m.text in ["💫 Вывести 50🌟", "💫 Вывести 100🌟"])
@subscription_required
def withdraw_amount_handler(message):
    db = load_db()
    user_id = str(message.from_user.id)
    user = get_user(db, user_id)
    update_username(db, message.from_user)
    
    amount = 50 if "50" in message.text else 100
    
    if user["balance"] < amount:
        bot.send_message(message.chat.id, f"❌ Недостаточно звёзд! Нужно {amount}🌟, у вас {user['balance']}🌟")
        return
    
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
    markup.row("Назад ◀️")
    return markup

@bot.message_handler(func=lambda m: m.text == "🔧 Админ-панель")
def admin_panel_handler(message):
    if not is_admin(message.from_user):
        return
    
    bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())

@bot.message_handler(func=lambda m: m.text == "📊 Статистика")
def stats_handler(message):
    if not is_admin(message.from_user):
        return
    
    db = load_db()
    total_users = len(db["users"])
    total_balance = sum(u.get("balance", 0) for u in db["users"].values())
    total_withdrawn = sum(u.get("withdrawn", 0) for u in db["users"].values())
    banned_count = len(db.get("banned", []))
    channels_count = len(db.get("channels", []))
    links_count = len(db.get("links", {}))
    
    text = f"""📊 Статистика бота

👥 Всего пользователей: {total_users}
🚫 Заблокировано: {banned_count}
💫 Всего звёзд на балансах: {total_balance}🌟
🤑 Всего выведено: {total_withdrawn}🌟
📺 Каналов для подписки: {channels_count}
🔗 Обязательных ссылок: {links_count}"""
    
    bot.send_message(message.chat.id, text)

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
    
    # Генерируем уникальный ID для ссылки
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
        f"✅ Ссылка добавлена!\n\n📝 Название: {name}\n🔗 URL: {url}\n\n📊 Трекинговая ссылка (для отслеживания):\n{tracking_url}"
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
    text = f"""💰 Информация о пользователе

🆔 ID: {target_id}
👤 Username: @{user.get('username') or 'нет'}
💫 Баланс: {user.get('balance', 0)}🌟
🧑‍🤝‍🧑 Рефералов: {user.get('referrals', 0)}
🤑 Выведено: {user.get('withdrawn', 0)}🌟"""
    
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
    
    user_states[message.from_user.id] = "admin_create_promo"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Назад ◀️")
    bot.send_message(message.chat.id, "Введите: КОД ЗВЁЗДЫ АКТИВАЦИИ\nПример: BONUS 10 100", reply_markup=markup)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "admin_create_promo")
def create_promo_input_handler(message):
    if message.text == "Назад ◀️":
        user_states.pop(message.from_user.id, None)
        bot.send_message(message.chat.id, "🔧 Админ-панель", reply_markup=admin_keyboard())
        return
    
    try:
        parts = message.text.strip().split()
        code = parts[0].upper()
        stars = float(parts[1])
        activations = int(parts[2])
    except:
        bot.send_message(message.chat.id, "❌ Неверный формат! Пример: BONUS 10 100")
        return
    
    db = load_db()
    
    db["promocodes"][code] = {
        "stars": stars,
        "activations": activations,
        "used_by": []
    }
    save_db(db)
    
    bot.send_message(message.chat.id, f"✅ Промокод создан!\n\n🎟 Код: {code}\n💫 Звёзд: {stars}🌟\n🔢 Активаций: {activations}")
    
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
