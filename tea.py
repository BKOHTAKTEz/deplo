import asyncio
import sqlite3
import aiosqlite
import aiohttp
import random
import time
import logging
import os  # ← ДОБАВЬ ЭТУ СТРОКУ
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    Message, BotCommand, InlineKeyboardMarkup,
    InlineKeyboardButton, CallbackQuery
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ЗАМЕНИ ЭТУ СТРОКУ:
# BOT_TOKEN = "8209183337:AAGD35wDxLjo-hHRBDDHMea-BmvjXazNpvk"
# НА ЭТУ:
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8209183337:AAGD35wDxLjo-hHRBDDHMea-BmvjXazNpvk")

# ВСЁ ОСТАЛЬНОЕ - КАК В ТВОЕМ ИСХОДНОМ КОДЕ (НИЧЕГО НЕ МЕНЯЙ!)
# ... весь остальной код отсюда и до конца файла оставляем как есть

if not BOT_TOKEN:
    raise ValueError("Нет TELEGRAM_BOT_TOKEN в переменных окружения!")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

COOLDOWN_SECONDS = 1800  # 30 минут

# ----- Вероятности редкостей -----
RARITY_PROBABILITIES = {5: 1, 4: 5, 3: 15, 2: 29, 1: 50}

# ----- Диапазоны стоимости находки -----
RARITY_VALUE_RANGES = {
    5: (1000, 10000), 4: (200, 500), 3: (50, 100),
    2: (2, 10), 1: (0.5, 1),
}

# ----- Резервные цены -----
FALLBACK_PRICES = {"meme": 0.00065}

# ----- Класс Blockchain (без изменений) -----
class Blockchain:
    def __init__(self, id, name, fallback_emoji, display_name, coins):
        self.id = id
        self.display_number = id + 1
        self.name = name
        self.fallback_emoji = fallback_emoji
        self.display_name = display_name
        self.coins = coins
        self.coins_by_rarity = {1: [], 2: [], 3: [], 4: [], 5: []}

    def get_display_name_html(self):
        return f"{self.fallback_emoji} {self.display_name}"

    async def update_rarities(self, pool):
        """Обновление редкостей с ценами из БД"""
        prices = []
        for coin in self.coins:
            async with pool.acquire() as conn:
                price_row = await conn.fetchrow(
                    "SELECT price_usd FROM crypto_prices WHERE coin_id = $1",
                    coin["coingecko_id"]
                )
                price = price_row['price_usd'] if price_row else 0.0
            prices.append((price, coin))
        
        prices.sort(key=lambda x: x[0])
        self.coins_by_rarity = {1: [], 2: [], 3: [], 4: [], 5: []}
        
        for i, (price, coin) in enumerate(prices):
            if i < 2: rarity = 1
            elif i == 2: rarity = 2
            elif i == 3: rarity = 3
            elif i == 4: rarity = 4
            else: rarity = 5
            self.coins_by_rarity[rarity].append(coin)

    def get_random_coin_by_rarity(self, rarity):
        coins = self.coins_by_rarity.get(rarity, [])
        if not coins:
            return None
        return random.choice(coins)

def choose_rarity():
    r = random.randint(1, 100)
    cumulative = 0
    for rarity, prob in sorted(RARITY_PROBABILITIES.items()):
        cumulative += prob
        if r <= cumulative:
            return rarity
    return 1

# ----- Блокчейны (без изменений) -----
BLOCKCHAINS = {
    0: Blockchain(
        id=0, name="bitcoin", fallback_emoji="₿", display_name="Биткоин",
        coins=[
            {"name": "btc", "emoji": "₿", "coingecko_id": "bitcoin"},
            {"name": "doge", "emoji": "🐕", "coingecko_id": "dogecoin"},
            {"name": "sats", "emoji": "⚡", "coingecko_id": "1000sats-ordinals"},
            {"name": "pizza", "emoji": "🍕", "coingecko_id": "pizza"},
            {"name": "rats", "emoji": "🐀", "coingecko_id": "rats"},
            {"name": "oxbt", "emoji": "🦬", "coingecko_id": "oxbt"},
        ]
    ),
    1: Blockchain(
        id=1, name="ethereum", fallback_emoji="Ξ", display_name="Эфириум",
        coins=[
            {"name": "eth", "emoji": "Ξ", "coingecko_id": "ethereum"},
            {"name": "shib", "emoji": "🐕", "coingecko_id": "shiba-inu"},
            {"name": "usdt", "emoji": "💵", "coingecko_id": "tether"},
            {"name": "meme", "emoji": "😂", "coingecko_id": "meme"},
            {"name": "omg", "emoji": "🌀", "coingecko_id": "omisego"},
            {"name": "dai", "emoji": "🪙", "coingecko_id": "dai"},
        ]
    ),
    2: Blockchain(
        id=2, name="solana", fallback_emoji="◎", display_name="Солана",
        coins=[
            {"name": "sol", "emoji": "◎", "coingecko_id": "solana"},
            {"name": "pump", "emoji": "🔄", "coingecko_id": "pump"},
            {"name": "fart", "emoji": "💨", "coingecko_id": "fartcoin"},
            {"name": "pepe", "emoji": "🐸", "coingecko_id": "pepe"},
            {"name": "grass", "emoji": "🌿", "coingecko_id": "grass"},
            {"name": "usdt", "emoji": "💵", "coingecko_id": "tether"},
        ]
    ),
    3: Blockchain(
        id=3, name="tron", fallback_emoji="🌞", display_name="Трон",
        coins=[
            {"name": "trc", "emoji": "🌞", "coingecko_id": "tron"},
            {"name": "usdt", "emoji": "💵", "coingecko_id": "tether"},
            {"name": "a7a5", "emoji": "🎰", "coingecko_id": "a7a5"},
            {"name": "jst", "emoji": "⚖️", "coingecko_id": "just"},
            {"name": "sun", "emoji": "☀️", "coingecko_id": "sun"},
            {"name": "flux", "emoji": "⚡", "coingecko_id": "flux"},
        ]
    ),
    4: Blockchain(
        id=4, name="ton", fallback_emoji="💎", display_name="ТОН",
        coins=[
            {"name": "Ton", "emoji": "💎", "coingecko_id": "the-open-network"},
            {"name": "not", "emoji": "🚫", "coingecko_id": "notcoin"},
            {"name": "hmstr", "emoji": "🐹", "coingecko_id": "hamster-kombat"},
            {"name": "major", "emoji": "⭐", "coingecko_id": "major"},
            {"name": "utya", "emoji": "🦆", "coingecko_id": "utya"},
            {"name": "gram", "emoji": "📦", "coingecko_id": "gram"},
        ]
    ),
}

BLOCKCHAIN_BY_ID = {bc.id: bc for bc in BLOCKCHAINS.values()}
BLOCKCHAIN_BY_NAME = {bc.name.lower(): bc for bc in BLOCKCHAINS.values()}
BLOCKCHAIN_BY_DISPLAY_NAME = {bc.display_name.lower(): bc for bc in BLOCKCHAINS.values()}
BLOCKCHAIN_BY_NUMBER = {bc.display_number: bc for bc in BLOCKCHAINS.values()}

# ----- Функция определения уровня -----
def get_level(balance_usd):
    if balance_usd >= 1000000: return 10
    if balance_usd >= 500000: return 9
    if balance_usd >= 200000: return 8
    if balance_usd >= 100000: return 7
    if balance_usd >= 50000: return 6
    if balance_usd >= 20000: return 5
    if balance_usd >= 10000: return 4
    if balance_usd >= 5000: return 3
    if balance_usd >= 3000: return 2
    if balance_usd >= 1000: return 1
    return 0

# ----- Инициализация БД (PostgreSQL версия) -----
async def init_db(pool):
    async with pool.acquire() as conn:
        # Таблица users
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                blockchain INTEGER DEFAULT -1,
                packets REAL DEFAULT 0,
                last_collection BIGINT,
                stars INTEGER DEFAULT 0
            )
        """)
        
        # Таблица collections
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS collections (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                packets REAL,
                coin_name TEXT,
                coin_id TEXT,
                rarity INTEGER,
                collection_time BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()))
            )
        """)
        
        # Таблица payments
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                stars INTEGER,
                amount INTEGER,
                currency TEXT,
                invoice_payload TEXT,
                payment_time BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()))
            )
        """)
        
        # Таблица crypto_prices
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS crypto_prices (
                coin_id TEXT PRIMARY KEY,
                price_usd REAL,
                last_updated BIGINT
            )
        """)
        
        # Таблица leaderboard_cache
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard_cache (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                username TEXT,
                first_name TEXT,
                balance_usd REAL,
                rank_position INTEGER,
                board_type TEXT,
                last_updated BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW())),
                UNIQUE(user_id, board_type)
            )
        """)
        
        # Таблица leaderboard_history
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard_history (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                username TEXT,
                first_name TEXT,
                balance_usd REAL,
                rank_position INTEGER,
                board_type TEXT,
                snapshot_time BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()))
            )
        """)
        
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_collections_user_id ON collections(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_collections_time ON collections(collection_time)")
        
        logger.info("✅ База данных PostgreSQL инициализирована")

# ----- Работа с пользователем (адаптировано для asyncpg) -----
async def get_or_create_user(pool, user_id: int, username: str = None, 
                            first_name: str = None, last_name: str = None):
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        
        if not user:
            await conn.execute("""
                INSERT INTO users (user_id, username, first_name, last_name, 
                                  blockchain, packets, stars, last_collection)
                VALUES ($1, $2, $3, $4, -1, 0, 0, NULL)
            """, user_id, username, first_name, last_name)
            logger.info(f"✅ Создан пользователь ID={user_id}")
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        else:
            # Обновление данных
            updates = []
            values = []
            if username != user['username']:
                updates.append("username = $2")
                values.append(username)
            if first_name != user['first_name']:
                updates.append("first_name = $3")
                values.append(first_name)
            if last_name != user['last_name']:
                updates.append("last_name = $4")
                values.append(last_name)
            
            if updates:
                values.append(user_id)
                query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ${len(values)}"
                await conn.execute(query, *values)
                user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        
        return user

async def update_user(pool, user_id: int, **kwargs):
    if kwargs:
        async with pool.acquire() as conn:
            set_clause = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(kwargs))
            values = list(kwargs.values()) + [user_id]
            await conn.execute(f"UPDATE users SET {set_clause} WHERE user_id = ${len(values)}", *values)

async def add_collection(pool, user_id: int, packets: float, coin_name: str, 
                        coin_id: str, rarity: int):
    now = int(time.time())
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO collections (user_id, packets, coin_name, coin_id, rarity, collection_time)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, user_id, packets, coin_name, coin_id, rarity, now)
        
        await conn.execute("""
            UPDATE users SET packets = packets + $1, last_collection = $2 
            WHERE user_id = $3
        """, packets, now, user_id)

async def check_cooldown(pool, user_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT last_collection FROM users WHERE user_id = $1", user_id)
        if not row or row['last_collection'] is None:
            return None
        last = row['last_collection']
        now = int(time.time())
        passed = now - last
        if passed < COOLDOWN_SECONDS:
            remaining = COOLDOWN_SECONDS - passed
            return divmod(remaining, 60)
        return None

# ----- Работа с ценами -----
COINGECKO_API = "https://api.coingecko.com/api/v3/simple/price"

async def fetch_crypto_prices(pool):
    ids = set()
    for bc in BLOCKCHAINS.values():
        for coin in bc.coins:
            if coin.get("coingecko_id"):
                ids.add(coin["coingecko_id"])
    
    if not ids:
        return

    ids_list = list(ids)
    logger.info(f"📤 Запрос цен для {len(ids_list)} монет")

    chunk_size = 100
    all_data = {}
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(ids_list), chunk_size):
            chunk = ids_list[i:i+chunk_size]
            ids_str = ",".join(chunk)
            params = {"ids": ids_str, "vs_currencies": "usd"}
            try:
                async with session.get(COINGECKO_API, params=params, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        all_data.update(data)
                    else:
                        logger.error(f"Ошибка CoinGecko {resp.status}")
                        if resp.status == 429:
                            await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Ошибка запроса: {e}")
            await asyncio.sleep(2)

    if all_data:
        now = int(time.time())
        async with pool.acquire() as conn:
            for coin_id, prices in all_data.items():
                price = prices.get("usd")
                if price is not None:
                    await conn.execute("""
                        INSERT INTO crypto_prices (coin_id, price_usd, last_updated)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (coin_id) DO UPDATE 
                        SET price_usd = $2, last_updated = $3
                    """, coin_id, price, now)
        logger.info(f"💰 Сохранены цены для {len(all_data)} монет")
    else:
        logger.warning("❌ Не удалось получить цены")

async def get_coin_price(pool, coin_id):
    if not coin_id:
        return 0.0
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT price_usd FROM crypto_prices WHERE coin_id = $1", coin_id)
        if row and row['price_usd'] is not None and row['price_usd'] != 0:
            return row['price_usd']
    return FALLBACK_PRICES.get(coin_id, 0.0)

# ----- Обновление редкостей -----
async def update_all_rarities(pool):
    for bc in BLOCKCHAINS.values():
        await bc.update_rarities(pool)
    logger.info("✅ Редкости обновлены")

# ----- Лидерборд -----
async def update_leaderboard_cache(pool):
    current_time = int(time.time())
    hour_ago = current_time - 3600
    day_ago = current_time - 86400

    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM leaderboard_cache")

        # all_time
        all_time = await conn.fetch("""
            SELECT 
                u.user_id, u.username, u.first_name,
                COALESCE(SUM(c.packets * cp.price_usd), 0) as balance_usd
            FROM users u
            LEFT JOIN collections c ON u.user_id = c.user_id
            LEFT JOIN crypto_prices cp ON cp.coin_id = c.coin_id
            GROUP BY u.user_id, u.username, u.first_name
            HAVING COALESCE(SUM(c.packets * cp.price_usd), 0) > 0
            ORDER BY balance_usd DESC
            LIMIT 10
        """)
        
        for i, row in enumerate(all_time, 1):
            await conn.execute("""
                INSERT INTO leaderboard_cache 
                    (user_id, username, first_name, balance_usd, rank_position, board_type, last_updated)
                VALUES ($1, $2, $3, $4, $5, 'all_time', $6)
            """, row['user_id'], row['username'], row['first_name'], 
               float(row['balance_usd']), i, current_time)

        # daily
        daily = await conn.fetch("""
            SELECT 
                u.user_id, u.username, u.first_name,
                COALESCE(SUM(c.packets * cp.price_usd), 0) as balance_usd
            FROM users u
            LEFT JOIN collections c ON u.user_id = c.user_id
            LEFT JOIN crypto_prices cp ON cp.coin_id = c.coin_id
            WHERE c.collection_time > $1
            GROUP BY u.user_id, u.username, u.first_name
            HAVING COALESCE(SUM(c.packets * cp.price_usd), 0) > 0
            ORDER BY balance_usd DESC
            LIMIT 10
        """, day_ago)
        
        for i, row in enumerate(daily, 1):
            await conn.execute("""
                INSERT INTO leaderboard_cache 
                    (user_id, username, first_name, balance_usd, rank_position, board_type, last_updated)
                VALUES ($1, $2, $3, $4, $5, 'daily', $6)
            """, row['user_id'], row['username'], row['first_name'], 
               float(row['balance_usd']), i, current_time)

        # hourly
        hourly = await conn.fetch("""
            SELECT 
                u.user_id, u.username, u.first_name,
                COALESCE(SUM(c.packets * cp.price_usd), 0) as balance_usd
            FROM users u
            LEFT JOIN collections c ON u.user_id = c.user_id
            LEFT JOIN crypto_prices cp ON cp.coin_id = c.coin_id
            WHERE c.collection_time > $1
            GROUP BY u.user_id, u.username, u.first_name
            HAVING COALESCE(SUM(c.packets * cp.price_usd), 0) > 0
            ORDER BY balance_usd DESC
            LIMIT 10
        """, hour_ago)
        
        for i, row in enumerate(hourly, 1):
            await conn.execute("""
                INSERT INTO leaderboard_cache 
                    (user_id, username, first_name, balance_usd, rank_position, board_type, last_updated)
                VALUES ($1, $2, $3, $4, $5, 'hourly', $6)
            """, row['user_id'], row['username'], row['first_name'], 
               float(row['balance_usd']), i, current_time)

    logger.info("✅ Кэш лидерборда обновлён")

async def calculate_user_balance(pool, user_id: int) -> float:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT COALESCE(SUM(c.packets * cp.price_usd), 0) as balance
            FROM collections c
            LEFT JOIN crypto_prices cp ON cp.coin_id = c.coin_id
            WHERE c.user_id = $1
        """, user_id)
        return float(row['balance']) if row else 0.0

# ----- Форматирование (без изменений) -----
def format_price(price):
    if price == 0:
        return "0"
    s = f"{price:.8f}".rstrip('0').rstrip('.')
    return s

def format_rarity(rarity):
    stars = "★" * rarity
    colors = ["⚪️", "🟢", "🔵", "🟣", "🟡"]
    return f"{colors[rarity-1]} {stars}"

def generate_math_question():
    a = random.randint(10, 99)
    b = random.randint(10, 99)
    c = random.randint(10, 99)
    correct = a + b - c
    wrong1 = correct + random.randint(1, 5)
    wrong2 = correct - random.randint(1, 5)
    while wrong1 == correct or wrong1 == wrong2:
        wrong1 = correct + random.randint(1, 5)
    while wrong2 == correct or wrong2 == wrong1:
        wrong2 = correct - random.randint(1, 5)
    question = f"{a} + {b} - {c} = ?"
    answers = [correct, wrong1, wrong2]
    random.shuffle(answers)
    return question, correct, answers

# ----- Клавиатуры (без изменений) -----
def crypto_collection_keyboard(user_id: int, cooldown_remaining=None):
    if cooldown_remaining:
        minutes, seconds = cooldown_remaining
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"⏳ Подождать {minutes}:{seconds:02d}", callback_data=f"wait_{user_id}")],
        ])
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Начать добычу", callback_data=f"start_verification_{user_id}")]
        ])
    return kb

def verification_keyboard(user_id: int, correct: int, answers: list):
    buttons = []
    for ans in answers:
        callback_data = f"verify_{correct}_{ans}_{user_id}"
        buttons.append([InlineKeyboardButton(text=str(ans), callback_data=callback_data)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ----- Парсинг команды chain -----
def parse_chain_command(args: str):
    if not args:
        return None
    args = args.lower().strip()
    try:
        num = int(args)
        if num in BLOCKCHAIN_BY_NUMBER:
            return BLOCKCHAIN_BY_NUMBER[num]
    except ValueError:
        pass
    if args in BLOCKCHAIN_BY_NAME:
        return BLOCKCHAIN_BY_NAME[args]
    if args in BLOCKCHAIN_BY_DISPLAY_NAME:
        return BLOCKCHAIN_BY_DISPLAY_NAME[args]
    return None

# ----- Общая функция для mining (адаптирована для pool) -----
async def process_mining_command(message: Message, pool):
    try:
        user = await get_or_create_user(
            pool,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        if user['blockchain'] == -1:
            await message.answer("❌ Сначала выберите блокчейн: /chain")
            return
        bc = BLOCKCHAINS[user['blockchain']]
        cooldown = await check_cooldown(pool, message.from_user.id)
        text = f"""
💰 <b>Добыча криптовалюты</b>

⛓️ <b>Блокчейн:</b> {bc.get_display_name_html()}
        """
        if cooldown:
            m, s = cooldown
            text += f"\n⏳ До следующей добычи: {m}:{s:02d}"
            await message.answer(text, reply_markup=crypto_collection_keyboard(message.from_user.id, cooldown))
        else:
            text += "\n✅ Готов к добыче! Нажмите кнопку, чтобы начать."
            await message.answer(text, reply_markup=crypto_collection_keyboard(message.from_user.id))
    except Exception as e:
        logger.error(f"Ошибка в process_mining_command: {e}", exc_info=True)
        await message.answer("❌ Внутренняя ошибка")

# ----- Команды (адаптированы для pool) -----
@dp.message(Command("start"))
async def cmd_start(message: Message):
    try:
        pool = message.bot.get('db_pool')
        user = await get_or_create_user(
            pool,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        bc_num = user['blockchain']
        packets = user['packets']
        stars = user['stars']
        
        if bc_num != -1:
            bc = BLOCKCHAINS[bc_num]
            bc_display = bc.get_display_name_html()
        else:
            bc_display = "❌ Не выбран"
        
        cooldown = await check_cooldown(pool, message.from_user.id)
        cd_text = f"⏳ До следующей добычи: {cooldown[0]}:{cooldown[1]:02d}" if cooldown else "✅ Готов к добыче"
        balance_usd = await calculate_user_balance(pool, message.from_user.id)
        level = get_level(balance_usd)

        text = f"""
🎮 <b>Крипто-майнер</b>

👤 <b>Игрок:</b> {message.from_user.full_name}
⛓️ <b>Блокчейн:</b> {bc_display}
🪙 <b>Монет добыто:</b> {format_price(packets)}
💰 <b>Баланс USD:</b> ${format_price(balance_usd)}
⭐️ <b>Звёзд:</b> {stars}
📊 <b>Уровень:</b> {level}

{cd_text}

<b>Команды:</b>
/chain – выбрать блокчейн
/mining – собрать крипту
/wallet – кошелёк
/leaderboard – таблица лидеров
        """
        await message.answer(text)
    except Exception as e:
        logger.error(f"Ошибка в cmd_start: {e}", exc_info=True)
        await message.answer("❌ Ошибка")

@dp.message(Command("chain"))
async def cmd_chain(message: Message):
    try:
        args = message.text.replace("/chain", "", 1).strip()
        if args.startswith("@gribnoy_robot"):
            args = args.replace("@gribnoy_robot", "").strip()
        
        if args:
            bc = parse_chain_command(args)
            if bc is not None:
                pool = message.bot.get('db_pool')
                await update_user(pool, message.from_user.id, blockchain=bc.id)
                
                # Формируем список монет
                coin_list = ""
                for rarity in range(1, 6):
                    for coin in bc.coins_by_rarity.get(rarity, []):
                        coin_list += f"{coin['emoji']} {coin['name']} {format_rarity(rarity)}\n"
                
                text = f"""
✅ <b>Блокчейн выбран: {bc.get_display_name_html()}</b>

<b>Доступные монеты:</b>
{coin_list}

➡️ Теперь собирайте: /mining
                """
                await message.answer(text)
                return
            else:
                await message.answer("❌ Неверный блокчейн. Используйте /chain чтобы увидеть список.")
                return
        
        # Показываем список
        text = "📍 <b>Выберите блокчейн:</b>\n\n"
        for bc in BLOCKCHAINS.values():
            text += f"{bc.display_number}. {bc.get_display_name_html()}\n"
        text += """
\n<b>Как выбрать:</b>
Напишите /chain с номером или названием

Примеры:
/chain 1 – выбрать Биткоин
/chain bitcoin – выбрать Биткоин
/chain биткоин – выбрать Биткоин
        """
        await message.answer(text)
    except Exception as e:
        logger.error(f"Ошибка в cmd_chain: {e}", exc_info=True)
        await message.answer("❌ Ошибка")

@dp.message(Command("mining"))
async def cmd_mining(message: Message):
    pool = message.bot.get('db_pool')
    await process_mining_command(message, pool)

@dp.message(Command("wallet"))
async def cmd_wallet(message: Message):
    try:
        pool = message.bot.get('db_pool')
        user = await get_or_create_user(
            pool,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        bc_num = user['blockchain']
        if bc_num != -1:
            bc = BLOCKCHAINS[bc_num]
            bc_display = bc.get_display_name_html()
        else:
            bc_display = "Не выбран"
        
        cooldown = await check_cooldown(pool, message.from_user.id)
        cd_text = f"⏳ {cooldown[0]}:{cooldown[1]:02d}" if cooldown else "✅ Готов"

        # Топ-5 монет
        async with pool.acquire() as conn:
            top = await conn.fetch("""
                SELECT coin_name, rarity, SUM(packets) as total
                FROM collections
                WHERE user_id = $1
                GROUP BY coin_name, rarity
                ORDER BY total DESC
                LIMIT 5
            """, message.from_user.id)

        coin_list = ""
        for row in top:
            coin_name = row['coin_name']
            rarity = row['rarity']
            qty = float(row['total'])
            
            # Ищем coin_id
            coin_id = None
            for bc_obj in BLOCKCHAINS.values():
                for coin in bc_obj.coins:
                    if coin["name"].lower() == coin_name.lower():
                        coin_id = coin.get("coingecko_id")
                        break
                if coin_id:
                    break
            
            price = await get_coin_price(pool, coin_id) if coin_id else 0.0
            value = qty * price
            coin_list += f"{format_rarity(rarity)} {coin_name}: {format_price(qty)} шт. (${format_price(value)})\n"

        if not coin_list:
            coin_list = "Пока ничего не добыто\n"

        balance_usd = await calculate_user_balance(pool, message.from_user.id)
        level = get_level(balance_usd)

        text = f"""
📦 <b>Кошелёк</b>

👤 {message.from_user.full_name}
⛓️ Текущий блокчейн: {bc_display}
🪙 Всего монет: {format_price(user['packets'])}
💰 Баланс USD: ${format_price(balance_usd)}
⭐️ Звёзд: {user['stars']}
📊 Уровень: {level}

<b>Собранные монеты (топ-5):</b>
{coin_list}

{cd_text}
        """
        await message.answer(text)
    except Exception as e:
        logger.error(f"Ошибка в cmd_wallet: {e}", exc_info=True)
        await message.answer("❌ Ошибка")

@dp.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message):
    try:
        pool = message.bot.get('db_pool')
        async with pool.acquire() as conn:
            all_time = await conn.fetch("""
                SELECT user_id, username, first_name, balance_usd, rank_position
                FROM leaderboard_cache WHERE board_type = 'all_time' ORDER BY rank_position
            """)
            daily = await conn.fetch("""
                SELECT user_id, username, first_name, balance_usd, rank_position
                FROM leaderboard_cache WHERE board_type = 'daily' ORDER BY rank_position
            """)
            hourly = await conn.fetch("""
                SELECT user_id, username, first_name, balance_usd, rank_position
                FROM leaderboard_cache WHERE board_type = 'hourly' ORDER BY rank_position
            """)

        def fmt(rows, title):
            if not rows:
                return f"<b>{title}:</b>\n   Пока нет данных\n\n"
            s = f"<b>{title}:</b>\n"
            for r in rows:
                display_name = r['first_name'] or f"Игрок {r['user_id']}"
                if r['username']:
                    display_name += f" (@{r['username']})"
                if len(display_name) > 30:
                    display_name = display_name[:27] + "..."
                balance = format_price(r['balance_usd'])
                if r['user_id'] == message.from_user.id:
                    s += f"   🏆 {r['rank_position']}. <b>{display_name}</b> — ${balance}\n"
                else:
                    s += f"   {r['rank_position']}. {display_name} — ${balance}\n"
            s += "\n"
            return s

        user_balance = await calculate_user_balance(pool, message.from_user.id)
        user_pos = "не в топ-10"
        for r in all_time:
            if r['user_id'] == message.from_user.id:
                user_pos = f"{r['rank_position']} место"
                break

        text = f"""
🏆 <b>Таблица лидеров (по балансу USD)</b>

{fmt(hourly, '⏰ За час')}
{fmt(daily, '📅 За сутки')}
{fmt(all_time, '⭐️ За всё время')}

📊 <b>Ваша позиция:</b> {user_pos}
💰 <b>Баланс:</b> ${format_price(user_balance)}
        """
        await message.answer(text)
    except Exception as e:
        logger.error(f"Ошибка в cmd_leaderboard: {e}", exc_info=True)
        await message.answer("❌ Ошибка")

# ----- Текстовые команды -----
@dp.message(F.text.lower().in_({"майн", "майнинг"}))
async def text_mining(message: Message):
    pool = message.bot.get('db_pool')
    await process_mining_command(message, pool)

# ----- Callback: начало верификации -----
@dp.callback_query(F.data.startswith("start_verification_"))
async def start_verification(callback: CallbackQuery):
    try:
        parts = callback.data.split("_")
        if len(parts) != 3:
            await callback.answer("❌ Неверные данные", show_alert=True)
            return
        user_id = int(parts[2])
        if user_id != callback.from_user.id:
            await callback.answer("❌ Эта кнопка не для вас", show_alert=True)
            return
        
        pool = callback.bot.get('db_pool')
        cooldown = await check_cooldown(pool, callback.from_user.id)
        if cooldown:
            m, s = cooldown
            await callback.answer(f"⏳ Подождите {m}:{s:02d}", show_alert=True)
            return
        
        question, correct, answers = generate_math_question()
        text = f"🔐 <b>Майнер запущен, для успешного завершения:</b>\n\nРешите пример:\n{question}"
        await callback.message.edit_text(text, reply_markup=verification_keyboard(callback.from_user.id, correct, answers))
        await callback.answer()
    except Exception as e:
        logger.error(f"start_verification error: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)

# ----- Callback: проверка ответа -----
@dp.callback_query(F.data.startswith("verify_"))
async def verify_callback(callback: CallbackQuery):
    try:
        parts = callback.data.split("_")
        if len(parts) != 4:
            await callback.answer("❌ Неверные данные", show_alert=True)
            return
        correct = int(parts[1])
        chosen = int(parts[2])
        user_id = int(parts[3])
        if user_id != callback.from_user.id:
            await callback.answer("❌ Эта кнопка не для вас", show_alert=True)
            return
        
        pool = callback.bot.get('db_pool')
        
        if chosen == correct:
            await callback.answer("✅ Верно! Собираем крипту...")
            await collect_crypto(callback, pool)
        else:
            now = int(time.time())
            await update_user(pool, callback.from_user.id, last_collection=now)
            await callback.message.edit_text("❌ Неправильный ответ. Кулдаун 30 минут активирован.")
            await callback.answer("❌ Неверно", show_alert=True)
    except Exception as e:
        logger.error(f"verify_callback error: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)

async def collect_crypto(callback: CallbackQuery, pool):
    try:
        user = await get_or_create_user(
            pool,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name
        )
        if user['blockchain'] == -1:
            await callback.message.edit_text("❌ Сначала выберите блокчейн!")
            return
        
        cooldown = await check_cooldown(pool, callback.from_user.id)
        if cooldown:
            m, s = cooldown
            await callback.message.edit_text(f"⏳ Кулдаун ещё не прошёл: {m}:{s:02d}")
            return
        
        bc = BLOCKCHAINS[user['blockchain']]
        rarity = choose_rarity()
        coin = bc.get_random_coin_by_rarity(rarity)
        if coin is None:
            coin = bc.coins[0]
            rarity = 1
        
        price = await get_coin_price(pool, coin["coingecko_id"])
        if price == 0:
            qty = 1.0
            value_usd = 0.0
        else:
            min_val, max_val = RARITY_VALUE_RANGES[rarity]
            target_usd = random.uniform(min_val, max_val)
            qty = target_usd / price
            value_usd = qty * price
        
        await add_collection(pool, callback.from_user.id, qty, coin["name"], 
                            coin["coingecko_id"], rarity)
        
        rarity_str = format_rarity(rarity)
        text = f"""
🎉 <b>Добыто!</b>

👤 {callback.from_user.full_name}
{coin['emoji']} <b>Монета:</b> {coin['name']} {rarity_str}
🔢 <b>Количество:</b> {format_price(qty)} шт.
💵 <b>Стоимость:</b> ${format_price(value_usd)}

⛓️ {bc.get_display_name_html()}

📦 <b>Всего монет:</b> {format_price(user['packets'] + qty)}
⏳ <b>Следующая добыча через:</b> {COOLDOWN_SECONDS // 60} мин.
        """
        await callback.message.edit_text(text)
        await callback.answer(f"Добыто {format_price(qty)} {coin['name']}!")
    except Exception as e:
        logger.error(f"collect_crypto error: {e}", exc_info=True)
        await callback.message.edit_text("❌ Произошла ошибка при добыче. Попробуйте позже.")
        await callback.answer("❌ Ошибка", show_alert=True)

# ----- Пропуск кулдауна -----
@dp.callback_query(F.data.startswith("wait_"))
async def wait_callback(callback: CallbackQuery):
    try:
        parts = callback.data.split("_")
        if len(parts) != 2:
            await callback.answer("❌ Неверные данные", show_alert=True)
            return
        user_id = int(parts[1])
        if user_id != callback.from_user.id:
            await callback.answer("❌ Эта кнопка не для вас", show_alert=True)
            return
        
        pool = callback.bot.get('db_pool')
        cd = await check_cooldown(pool, callback.from_user.id)
        if cd:
            m, s = cd
            await callback.answer(f"⏳ Осталось {m}:{s:02d}", show_alert=True)
        else:
            await callback.answer("✅ Можно собирать!", show_alert=True)
    except Exception as e:
        logger.error(f"wait_callback error: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)

# ----- Команды меню -----
async def set_commands():
    cmds = [
        BotCommand(command="/start", description="Статус"),
        BotCommand(command="/chain", description="Выбрать блокчейн"),
        BotCommand(command="/mining", description="Собрать крипту"),
        BotCommand(command="/wallet", description="Кошелёк"),
        BotCommand(command="/leaderboard", description="Таблица лидеров")
    ]
    try:
        await bot.set_my_commands(cmds)
        logger.info("✅ Команды меню установлены")
    except Exception as e:
        logger.error(f"❌ Ошибка при установке команд: {e}")

# ----- Фоновая задача -----
async def periodic_price_update(pool):
    while True:
        await fetch_crypto_prices(pool)
        await update_all_rarities(pool)
        await update_leaderboard_cache(pool)
        await asyncio.sleep(600)

# ----- Главная функция -----
async def main():
    try:
        logger.info("🔄 Подключение к PostgreSQL...")
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        
        logger.info("🔄 Инициализация базы данных...")
        await init_db(pool)
        
        # Сохраняем pool в bot для доступа из хендлеров
        bot['db_pool'] = pool

        logger.info("🔄 Установка команд меню...")
        await set_commands()

        logger.info("🔄 Получение цен криптовалют...")
        await fetch_crypto_prices(pool)

        logger.info("🔄 Обновление редкостей монет...")
        await update_all_rarities(pool)

        logger.info("🔄 Обновление кэша лидерборда...")
        await update_leaderboard_cache(pool)

        # Запускаем фоновую задачу
        asyncio.create_task(periodic_price_update(pool))

        logger.info("🤖 Крипто-майнер запущен!")
        logger.info(f"⏳ Кулдаун: {COOLDOWN_SECONDS // 60} мин")

        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"🔥 Критическая ошибка при запуске: {e}", exc_info=True)
        raise
    finally:
        if 'pool' in locals():
            await pool.close()
