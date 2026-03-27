import logging
import random
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    FSInputFile, InputMediaPhoto
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from config import BOT_TOKEN, CRYPTO_BOT_TOKEN, ADMIN_IDS
from database import db
from crypto_payment import CryptoPayment
from games import SlotMachine, Roulette, Dice, CoinFlip, Mines, Crash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
crypto = CryptoPayment(CRYPTO_BOT_TOKEN)


class States(StatesGroup):
    waiting_deposit_amount = State()
    waiting_withdraw_amount = State()
    waiting_withdraw_address = State()
    waiting_bet_amount = State()
    waiting_promo = State()
    waiting_mines_bet = State()
    waiting_crash_bet = State()


# ==================== KEYBOARDS ====================

def main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎰 Играть", callback_data="games_menu"),
        InlineKeyboardButton(text="💎 Профиль", callback_data="profile")
    )
    builder.row(
        InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit"),
        InlineKeyboardButton(text="💸 Вывести", callback_data="withdraw")
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Бонусы", callback_data="bonuses"),
        InlineKeyboardButton(text="📊 Топ игроков", callback_data="leaderboard")
    )
    builder.row(
        InlineKeyboardButton(text="🎫 Промокод", callback_data="promo"),
        InlineKeyboardButton(text="📞 Поддержка", callback_data="support")
    )
    builder.row(
        InlineKeyboardButton(text="📜 История ставок", callback_data="history"),
        InlineKeyboardButton(text="ℹ️ О казино", callback_data="about")
    )
    return builder.as_markup()


def games_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎰 Слоты", callback_data="game_slots"),
        InlineKeyboardButton(text="🎲 Кости", callback_data="game_dice")
    )
    builder.row(
        InlineKeyboardButton(text="🪙 Монетка", callback_data="game_coin"),
        InlineKeyboardButton(text="🎡 Рулетка", callback_data="game_roulette")
    )
    builder.row(
        InlineKeyboardButton(text="💣 Мины", callback_data="game_mines"),
        InlineKeyboardButton(text="🚀 Краш", callback_data="game_crash")
    )
    builder.row(
        InlineKeyboardButton(text="🃏 Блэкджек", callback_data="game_blackjack"),
        InlineKeyboardButton(text="🎯 Быки и Медведи", callback_data="game_bulls")
    )
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def bet_keyboard(game: str):
    builder = InlineKeyboardBuilder()
    bets = [10, 25, 50, 100, 250, 500]
    row = []
    for bet in bets:
        row.append(InlineKeyboardButton(text=f"${bet}", callback_data=f"bet_{game}_{bet}"))
        if len(row) == 3:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)
    builder.row(
        InlineKeyboardButton(text="✏️ Своя сумма", callback_data=f"custom_bet_{game}"),
        InlineKeyboardButton(text="💰 Весь баланс", callback_data=f"allIn_{game}")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="games_menu"))
    return builder.as_markup()


def coin_choice_keyboard(bet: float):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👑 Орёл (x2)", callback_data=f"coin_heads_{bet}"),
        InlineKeyboardButton(text="🦅 Решка (x2)", callback_data=f"coin_tails_{bet}")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="game_coin"))
    return builder.as_markup()


def roulette_keyboard(bet: float):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔴 Красное (x2)", callback_data=f"roulette_red_{bet}"),
        InlineKeyboardButton(text="⚫ Чёрное (x2)", callback_data=f"roulette_black_{bet}")
    )
    builder.row(
        InlineKeyboardButton(text="🟢 Зелёное (x14)", callback_data=f"roulette_green_{bet}"),
        InlineKeyboardButton(text="1️⃣ Первая дюж. (x3)", callback_data=f"roulette_first_{bet}")
    )
    builder.row(
        InlineKeyboardButton(text="2️⃣ Вторая дюж. (x3)", callback_data=f"roulette_second_{bet}"),
        InlineKeyboardButton(text="3️⃣ Третья дюж. (x3)", callback_data=f"roulette_third_{bet}")
    )
    builder.row(
        InlineKeyboardButton(text="⬆️ Чётное (x2)", callback_data=f"roulette_even_{bet}"),
        InlineKeyboardButton(text="⬇️ Нечётное (x2)", callback_data=f"roulette_odd_{bet}")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="game_roulette"))
    return builder.as_markup()


def deposit_keyboard():
    builder = InlineKeyboardBuilder()
    amounts = [10, 25, 50, 100, 250, 500, 1000]
    row = []
    for a in amounts:
        row.append(InlineKeyboardButton(text=f"${a}", callback_data=f"dep_{a}"))
        if len(row) == 3:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)
    builder.row(InlineKeyboardButton(text="✏️ Другая сумма", callback_data="dep_custom"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
    return builder.as_markup()


def currency_keyboard(amount: float):
    builder = InlineKeyboardBuilder()
    currencies = [
        ("₿ Bitcoin", "BTC"), ("Ξ Ethereum", "ETH"),
        ("💵 USDT", "USDT"), ("🔵 TON", "TON"),
        ("🅻 LTC", "LTC"), ("🎭 BNB", "BNB")
    ]
    for name, code in currencies:
        builder.row(InlineKeyboardButton(
            text=name, callback_data=f"pay_{code}_{amount}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="deposit"))
    return builder.as_markup()


def back_keyboard(callback: str = "main_menu"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=callback)]
    ])


# ==================== MESSAGES ====================

WELCOME_TEXT = """
🎰 *LUCKY STRIKE CASINO* 🎰

━━━━━━━━━━━━━━━━━━━━
Добро пожаловать, {name}!
━━━━━━━━━━━━━━━━━━━━

🏆 Лучшее крипто-казино в Telegram!

💎 *Что тебя ждёт:*
• 8 азартных игр на любой вкус
• Мгновенные выплаты через CryptoBot
• Ежедневные бонусы и промокоды
• Турниры с крупными призами
• VIP программа лояльности

💰 *Твой баланс:* `${balance}`
🎁 *Бонус новичка:* `$25` уже на счету!

Нажми *«🎰 Играть»* и испытай удачу!
"""

PROFILE_TEXT = """
👤 *ПРОФИЛЬ ИГРОКА*
━━━━━━━━━━━━━━━━━━━━

🆔 ID: `{user_id}`
👾 Ник: *{name}*
⭐ Уровень: {level} {level_emoji}
🏆 VIP статус: {vip}

💰 *Финансы:*
• Баланс: `${balance}`
• Всего пополнено: `${total_dep}`
• Всего выведено: `${total_with}`

🎮 *Статистика:*
• Всего игр: `{total_games}`
• Побед: `{wins}` ✅
• Поражений: `{losses}` ❌
• Винрейт: `{winrate}%`
• Крупнейший выигрыш: `${biggest_win}`

🎯 *Ставки:*
• Всего поставлено: `${total_bet}`
• Прибыль/убыток: `${profit}`

📅 Регистрация: {reg_date}
━━━━━━━━━━━━━━━━━━━━
"""

GAMES_TEXT = """
🎮 *ИГРОВОЙ ЗАЛ*
━━━━━━━━━━━━━━━━━━━━

Выбери игру и испытай удачу!

🎰 *Слоты* — классика казино, x150
🎲 *Кости* — угадай число, x5
🪙 *Монетка* — орёл или решка, x2
🎡 *Рулетка* — европейская, x14
💣 *Мины* — найди алмазы, x∞
🚀 *Краш* — успей забрать, x∞
🃏 *Блэкджек* — набери 21, x2
🎯 *Быки и Медведи* — угадай тренд, x1.9

━━━━━━━━━━━━━━━━━━━━
💡 Минимальная ставка: $1
"""


# ==================== HANDLERS ====================

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user = message.from_user
    is_new = await db.register_user(
        user_id=user.id,
        username=user.username or user.first_name,
        full_name=user.full_name
    )

    balance = await db.get_balance(user.id)

    text = WELCOME_TEXT.format(
        name=user.first_name,
        balance=f"{balance:.2f}"
    )

    try:
        photo = FSInputFile("images/welcome.jpg")
        await message.answer_photo(
            photo=photo,
            caption=text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    except Exception:
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )


@dp.callback_query(F.data == "main_menu")
async def main_menu(call: types.CallbackQuery):
    balance = await db.get_balance(call.from_user.id)
    text = WELCOME_TEXT.format(
        name=call.from_user.first_name,
        balance=f"{balance:.2f}"
    )
    try:
        photo = FSInputFile("images/welcome.jpg")
        await call.message.edit_media(
            InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
            reply_markup=main_menu_keyboard()
        )
    except Exception:
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    await call.answer()


@dp.callback_query(F.data == "games_menu")
async def games_menu(call: types.CallbackQuery):
    try:
        photo = FSInputFile("images/games.jpg")
        await call.message.edit_media(
            InputMediaPhoto(media=photo, caption=GAMES_TEXT, parse_mode="Markdown"),
            reply_markup=games_menu_keyboard()
        )
    except Exception:
        await call.message.edit_text(GAMES_TEXT, parse_mode="Markdown", reply_markup=games_menu_keyboard())
    await call.answer()


@dp.callback_query(F.data == "profile")
async def profile_handler(call: types.CallbackQuery):
    user_id = call.from_user.id
    data = await db.get_user_stats(user_id)

    levels = ["🥉 Новичок", "🥈 Любитель", "🥇 Опытный", "💎 Профи", "👑 Легенда"]
    vip_levels = ["Стандарт", "Silver", "Gold", "Platinum", "Diamond"]
    level_emojis = ["🌱", "⭐", "🌟", "💫", "🔥"]

    level = min(data['level'], 4)
    winrate = round(data['wins'] / data['total_games'] * 100) if data['total_games'] > 0 else 0
    profit = data['total_won'] - data['total_bet']

    text = PROFILE_TEXT.format(
        user_id=user_id,
        name=call.from_user.full_name,
        level=levels[level],
        level_emoji=level_emojis[level],
        vip=vip_levels[level],
        balance=f"{data['balance']:.2f}",
        total_dep=f"{data['total_deposited']:.2f}",
        total_with=f"{data['total_withdrawn']:.2f}",
        total_games=data['total_games'],
        wins=data['wins'],
        losses=data['total_games'] - data['wins'],
        winrate=winrate,
        biggest_win=f"{data['biggest_win']:.2f}",
        total_bet=f"{data['total_bet']:.2f}",
        profit=f"{profit:+.2f}",
        reg_date=data['reg_date']
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit"),
        InlineKeyboardButton(text="💸 Вывести", callback_data="withdraw")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))

    try:
        photo = FSInputFile("images/profile.jpg")
        await call.message.edit_media(
            InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
            reply_markup=builder.as_markup()
        )
    except Exception:
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await call.answer()


# ==================== GAMES ====================

@dp.callback_query(F.data == "game_slots")
async def game_slots(call: types.CallbackQuery):
    text = """
🎰 *СЛОТЫ*
━━━━━━━━━━━━━━━━━━━━

Классические однорукие бандиты!

💡 *Выплаты:*
• 777 — x150 💎
• 🍒🍒🍒 — x50
• ⭐⭐⭐ — x25
• 🍋🍋🍋 — x15
• 🍇🍇🍇 — x10
• Две одинаковых — x2
• Одна 7️⃣ — x1.5

Выбери размер ставки:
━━━━━━━━━━━━━━━━━━━━
"""
    try:
        photo = FSInputFile("images/slots.jpg")
        await call.message.edit_media(
            InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
            reply_markup=bet_keyboard("slots")
        )
    except Exception:
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=bet_keyboard("slots"))
    await call.answer()


@dp.callback_query(F.data == "game_coin")
async def game_coin(call: types.CallbackQuery):
    text = """
🪙 *МОНЕТКА*
━━━━━━━━━━━━━━━━━━━━

Подбрось монетку и удвой ставку!

👑 *Орёл* — x2
🦅 *Решка* — x2

Шанс победы: 50%

Выбери размер ставки:
━━━━━━━━━━━━━━━━━━━━
"""
    try:
        photo = FSInputFile("images/coin.jpg")
        await call.message.edit_media(
            InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
            reply_markup=bet_keyboard("coin")
        )
    except Exception:
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=bet_keyboard("coin"))
    await call.answer()


@dp.callback_query(F.data == "game_roulette")
async def game_roulette(call: types.CallbackQuery):
    text = """
🎡 *РУЛЕТКА*
━━━━━━━━━━━━━━━━━━━━

Европейская рулетка (0-36)

🔴 Красное — x2 (18 секторов)
⚫ Чёрное — x2 (18 секторов)  
🟢 Зелёное (0) — x14
1️⃣ Первая дюжина (1-12) — x3
2️⃣ Вторая дюжина (13-24) — x3
3️⃣ Третья дюжина (25-36) — x3
⬆️ Чётное — x2
⬇️ Нечётное — x2

Выбери размер ставки:
━━━━━━━━━━━━━━━━━━━━
"""
    try:
        photo = FSInputFile("images/roulette.jpg")
        await call.message.edit_media(
            InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
            reply_markup=bet_keyboard("roulette")
        )
    except Exception:
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=bet_keyboard("roulette"))
    await call.answer()


@dp.callback_query(F.data == "game_dice")
async def game_dice(call: types.CallbackQuery):
    text = """
🎲 *КОСТИ*
━━━━━━━━━━━━━━━━━━━━

Угадай выпавшую грань!

🎯 Угадал точно — x5
↗️ Угадал пол (1-3 или 4-6) — x1.9
❌ Не угадал — потеря ставки

Выбери размер ставки:
━━━━━━━━━━━━━━━━━━━━
"""
    try:
        photo = FSInputFile("images/dice.jpg")
        await call.message.edit_media(
            InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
            reply_markup=bet_keyboard("dice")
        )
    except Exception:
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=bet_keyboard("dice"))
    await call.answer()


@dp.callback_query(F.data == "game_mines")
async def game_mines(call: types.CallbackQuery):
    text = """
💣 *МИНЫ*
━━━━━━━━━━━━━━━━━━━━

Поле 5x5, 25 клеток.
Выбирай клетки — за каждый 💎 алмаз
множитель растёт. Попал на 💣 мину — теряешь всё!

💎 1 алмаз — x1.09
💎 3 алмаза — x1.31  
💎 5 алмазов — x1.66
💎 10 алмазов — x3.67
💎 20 алмазов — x24.5
🔥 Все 24 — JACKPOT!

Чем больше мин — тем выше множитель!

Выбери размер ставки:
━━━━━━━━━━━━━━━━━━━━
"""
    try:
        photo = FSInputFile("images/mines.jpg")
        await call.message.edit_media(
            InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
            reply_markup=bet_keyboard("mines")
        )
    except Exception:
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=bet_keyboard("mines"))
    await call.answer()


@dp.callback_query(F.data == "game_crash")
async def game_crash(call: types.CallbackQuery):
    text = """
🚀 *КРАШ*
━━━━━━━━━━━━━━━━━━━━

Ракета взлетает — забери выигрыш
ДО того как она упадёт!

📈 Множитель растёт с каждой секундой
⚡ Успей нажать «Забрать» вовремя
💥 Краш в любой момент — теряешь всё!

🎯 Авто-вывод: установи целевой множитель

*Текущий раунд ожидает игроков...*

Выбери размер ставки:
━━━━━━━━━━━━━━━━━━━━
"""
    try:
        photo = FSInputFile("images/crash.jpg")
        await call.message.edit_media(
            InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
            reply_markup=bet_keyboard("crash")
        )
    except Exception:
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=bet_keyboard("crash"))
    await call.answer()


@dp.callback_query(F.data == "game_blackjack")
async def game_blackjack(call: types.CallbackQuery):
    text = """
🃏 *БЛЭКДЖЕК*
━━━━━━━━━━━━━━━━━━━━

Набери 21 и обыграй дилера!

🎯 21 очко (Blackjack) — x2.5
✅ Ближе к 21 чем дилер — x2
🤝 Ничья — возврат ставки
❌ Перебор (>21) — проигрыш

🃏 Туз = 1 или 11 очков
👑 Картинки (J, Q, K) = 10 очков

Выбери размер ставки:
━━━━━━━━━━━━━━━━━━━━
"""
    try:
        photo = FSInputFile("images/blackjack.jpg")
        await call.message.edit_media(
            InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
            reply_markup=bet_keyboard("blackjack")
        )
    except Exception:
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=bet_keyboard("blackjack"))
    await call.answer()


@dp.callback_query(F.data == "game_bulls")
async def game_bulls(call: types.CallbackQuery):
    text = """
🎯 *БЫКИ И МЕДВЕДИ*
━━━━━━━━━━━━━━━━━━━━

Угадай движение рынка BTC!

📈 *Бык* — цена вырастет — x1.9
📉 *Медведь* — цена упадёт — x1.9

⏱ Раунд длится 30 секунд
📊 Используется реальная цена BTC

Выбери размер ставки:
━━━━━━━━━━━━━━━━━━━━
"""
    try:
        photo = FSInputFile("images/bulls.jpg")
        await call.message.edit_media(
            InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
            reply_markup=bet_keyboard("bulls")
        )
    except Exception:
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=bet_keyboard("bulls"))
    await call.answer()


# ==================== BET PROCESSING ====================

@dp.callback_query(F.data.startswith("bet_"))
async def process_bet(call: types.CallbackQuery):
    _, game, amount = call.data.split("_", 2)
    bet = float(amount)
    user_id = call.from_user.id
    balance = await db.get_balance(user_id)

    if balance < bet:
        await call.answer(f"❌ Недостаточно средств! Ваш баланс: ${balance:.2f}", show_alert=True)
        return

    if game == "coin":
        await call.message.edit_caption(
            caption=f"🪙 *МОНЕТКА*\n\nСтавка: `${bet}`\n\nВыбери сторону монетки:",
            parse_mode="Markdown",
            reply_markup=coin_choice_keyboard(bet)
        )
    elif game == "roulette":
        await call.message.edit_caption(
            caption=f"🎡 *РУЛЕТКА*\n\nСтавка: `${bet}`\n\nВыбери тип ставки:",
            parse_mode="Markdown",
            reply_markup=roulette_keyboard(bet)
        )
    elif game == "slots":
        await play_slots(call, bet)
    elif game == "dice":
        await play_dice(call, bet)
    elif game == "mines":
        await play_mines(call, bet)
    elif game == "crash":
        await play_crash(call, bet)
    elif game == "blackjack":
        await play_blackjack(call, bet)
    elif game == "bulls":
        await play_bulls(call, bet)

    await call.answer()


@dp.callback_query(F.data.startswith("allIn_"))
async def all_in(call: types.CallbackQuery):
    game = call.data.split("_")[1]
    balance = await db.get_balance(call.from_user.id)
    if balance <= 0:
        await call.answer("❌ Ваш баланс пуст!", show_alert=True)
        return

    fake_call = call
    fake_call.data = f"bet_{game}_{balance}"
    await process_bet(fake_call)


async def play_slots(call: types.CallbackQuery, bet: float):
    user_id = call.from_user.id
    slot = SlotMachine()
    result = slot.spin()

    await db.deduct_balance(user_id, bet)

    spin_msg = await call.message.answer("🎰 Крутим барабаны...\n\n🔄 | 🔄 | 🔄")
    await asyncio.sleep(1)
    await spin_msg.edit_text(f"🎰 Крутим барабаны...\n\n{result['r1']} | 🔄 | 🔄")
    await asyncio.sleep(0.8)
    await spin_msg.edit_text(f"🎰 Крутим барабаны...\n\n{result['r1']} | {result['r2']} | 🔄")
    await asyncio.sleep(0.8)

    win = result['win']
    winnings = bet * result['multiplier'] if win else 0

    if win:
        await db.add_balance(user_id, winnings)
        await db.record_game(user_id, "slots", bet, winnings, True)

    new_balance = await db.get_balance(user_id)

    result_text = f"""
🎰 *РЕЗУЛЬТАТ СЛОТОВ*
━━━━━━━━━━━━━━━━━━━━
{result['r1']} | {result['r2']} | {result['r3']}

{'🏆 *ВЫИГРЫШ!*' if win else '😔 *Не повезло...*'}
{'💰 ' + result['combo_name'] if win else ''}
{'Множитель: x' + str(result['multiplier']) if win else ''}

Ставка: `${bet:.2f}`
{'Выигрыш: `$' + f"{winnings:.2f}`" if win else 'Проигрыш: `$' + f"{bet:.2f}`"}
💰 Баланс: `${new_balance:.2f}`
━━━━━━━━━━━━━━━━━━━━
"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Играть снова", callback_data="game_slots"),
        InlineKeyboardButton(text="🔙 Меню игр", callback_data="games_menu")
    )
    await spin_msg.edit_text(result_text, parse_mode="Markdown", reply_markup=builder.as_markup())


async def play_dice(call: types.CallbackQuery, bet: float):
    user_id = call.from_user.id
    dice_game = Dice()
    result = dice_game.roll()

    await db.deduct_balance(user_id, bet)

    dice_msg = await call.message.answer("🎲 Бросаем кости...")
    await asyncio.sleep(1.5)

    win = result['win']
    winnings = bet * result['multiplier'] if win else 0
    if win:
        await db.add_balance(user_id, winnings)

    await db.record_game(user_id, "dice", bet, winnings, win)
    new_balance = await db.get_balance(user_id)

    text = f"""
🎲 *РЕЗУЛЬТАТ КОСТЕЙ*
━━━━━━━━━━━━━━━━━━━━
Выпало: {result['dice_emoji']} *{result['value']}*

{'🏆 *ВЫИГРЫШ!*' if win else '😔 *Не повезло...*'}
{result['result_text']}

Ставка: `${bet:.2f}`
{'Выигрыш: `$' + f"{winnings:.2f}`" if win else 'Проигрыш: `$' + f"{bet:.2f}`"}
💰 Баланс: `${new_balance:.2f}`
━━━━━━━━━━━━━━━━━━━━
"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Бросить снова", callback_data="game_dice"),
        InlineKeyboardButton(text="🔙 Меню игр", callback_data="games_menu")
    )
    await dice_msg.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("coin_"))
async def play_coin(call: types.CallbackQuery):
    parts = call.data.split("_")
    choice = parts[1]  # heads or tails
    bet = float(parts[2])
    user_id = call.from_user.id

    balance = await db.get_balance(user_id)
    if balance < bet:
        await call.answer("❌ Недостаточно средств!", show_alert=True)
        return

    await db.deduct_balance(user_id, bet)

    coin = CoinFlip()
    result = coin.flip()

    win = (choice == "heads" and result['result'] == "heads") or \
          (choice == "tails" and result['result'] == "tails")

    winnings = bet * 2 if win else 0
    if win:
        await db.add_balance(user_id, winnings)

    await db.record_game(user_id, "coin", bet, winnings, win)
    new_balance = await db.get_balance(user_id)

    choice_emoji = "👑" if choice == "heads" else "🦅"
    result_emoji = "👑" if result['result'] == "heads" else "🦅"
    choice_name = "Орёл" if choice == "heads" else "Решка"
    result_name = "Орёл" if result['result'] == "heads" else "Решка"

    text = f"""
🪙 *МОНЕТКА*
━━━━━━━━━━━━━━━━━━━━
Ваш выбор: {choice_emoji} *{choice_name}*
Результат: {result_emoji} *{result_name}*

{'🏆 *ВЫИГРЫШ! x2*' if win else '😔 *Не повезло...*'}

Ставка: `${bet:.2f}`
{'Выигрыш: `$' + f"{winnings:.2f}`" if win else 'Проигрыш: `$' + f"{bet:.2f}`"}
💰 Баланс: `${new_balance:.2f}`
━━━━━━━━━━━━━━━━━━━━
"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Играть снова", callback_data="game_coin"),
        InlineKeyboardButton(text="🔙 Меню игр", callback_data="games_menu")
    )
    await call.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await call.answer()


@dp.callback_query(F.data.startswith("roulette_"))
async def play_roulette(call: types.CallbackQuery):
    parts = call.data.split("_")
    bet_type = parts[1]
    bet = float(parts[2])
    user_id = call.from_user.id

    balance = await db.get_balance(user_id)
    if balance < bet:
        await call.answer("❌ Недостаточно средств!", show_alert=True)
        return

    await db.deduct_balance(user_id, bet)

    r = Roulette()
    result = r.spin()
    win, multiplier = r.check_win(bet_type, result['number'])

    winnings = bet * multiplier if win else 0
    if win:
        await db.add_balance(user_id, winnings)

    await db.record_game(user_id, "roulette", bet, winnings, win)
    new_balance = await db.get_balance(user_id)

    text = f"""
🎡 *РУЛЕТКА*
━━━━━━━━━━━━━━━━━━━━
🔮 Выпало: {result['emoji']} **{result['number']}** ({result['color_name']})

{'🏆 *ВЫИГРЫШ!*' if win else '😔 *Не повезло...*'}
{'Множитель: x' + str(multiplier) if win else ''}

Ставка: `${bet:.2f}`
{'Выигрыш: `$' + f"{winnings:.2f}`" if win else 'Проигрыш: `$' + f"{bet:.2f}`"}
💰 Баланс: `${new_balance:.2f}`
━━━━━━━━━━━━━━━━━━━━
"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Крутить снова", callback_data="game_roulette"),
        InlineKeyboardButton(text="🔙 Меню игр", callback_data="games_menu")
    )
    await call.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await call.answer()


async def play_mines(call: types.CallbackQuery, bet: float):
    user_id = call.from_user.id
    await db.deduct_balance(user_id, bet)

    mines_game = Mines(mines_count=5)
    board = mines_game.generate_board()

    await db.save_mines_game(user_id, bet, board, mines_count=5)

    text = f"""
💣 *МИНЫ — Раунд начат!*
━━━━━━━━━━━━━━━━━━━━
Ставка: `${bet:.2f}`
Мин на поле: 5
Текущий множитель: x1.00

Открывай клетки! Найди алмазы 💎
Избегай мин 💣

⬛ = закрытая клетка
━━━━━━━━━━━━━━━━━━━━
"""
    keyboard = generate_mines_keyboard(board, user_id, bet, opened=[])
    result_msg = await call.message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
    await db.update_mines_message(user_id, result_msg.message_id)


def generate_mines_keyboard(board, user_id, bet, opened: list):
    builder = InlineKeyboardBuilder()
    for row in range(5):
        buttons = []
        for col in range(5):
            idx = row * 5 + col
            if idx in opened:
                if board[idx] == "mine":
                    buttons.append(InlineKeyboardButton(text="💣", callback_data="mines_dead"))
                else:
                    buttons.append(InlineKeyboardButton(text="💎", callback_data="mines_opened"))
            else:
                buttons.append(InlineKeyboardButton(
                    text="⬛",
                    callback_data=f"mines_open_{idx}_{bet}"
                ))
        builder.row(*buttons)

    if opened:
        builder.row(
            InlineKeyboardButton(text=f"💰 Забрать выигрыш", callback_data=f"mines_cashout_{bet}_{len(opened)}")
        )
    builder.row(InlineKeyboardButton(text="🔙 Меню игр", callback_data="games_menu"))
    return builder.as_markup()


@dp.callback_query(F.data.startswith("mines_open_"))
async def mines_open_cell(call: types.CallbackQuery):
    parts = call.data.split("_")
    idx = int(parts[2])
    bet = float(parts[3])
    user_id = call.from_user.id

    game_data = await db.get_mines_game(user_id)
    if not game_data:
        await call.answer("Игра не найдена!", show_alert=True)
        return

    board = game_data['board']
    opened = game_data['opened']

    if idx in opened:
        await call.answer("Клетка уже открыта!", show_alert=True)
        return

    opened.append(idx)
    await db.update_mines_opened(user_id, opened)

    if board[idx] == "mine":
        await db.record_game(user_id, "mines", bet, 0, False)
        await db.delete_mines_game(user_id)

        text = f"""
💣 *МИНА! Игра окончена!*
━━━━━━━━━━━━━━━━━━━━
Ты наступил на мину! 💥

Ставка: `${bet:.2f}`
Проигрыш: `${bet:.2f}`
💰 Баланс: `${await db.get_balance(user_id):.2f}`
━━━━━━━━━━━━━━━━━━━━
"""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🔄 Играть снова", callback_data="game_mines"),
            InlineKeyboardButton(text="🔙 Меню", callback_data="games_menu")
        )
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        safe_count = len([o for o in opened if board[o] != "mine"])
        multiplier = Mines.calculate_multiplier(safe_count, 5)
        current_win = bet * multiplier

        text = f"""
💣 *МИНЫ*
━━━━━━━━━━━━━━━━━━━━
💎 Алмазов найдено: {safe_count}
Текущий множитель: x{multiplier:.2f}
Потенциальный выигрыш: `${current_win:.2f}`

Продолжай или забирай выигрыш!
━━━━━━━━━━━━━━━━━━━━
"""
        keyboard = generate_mines_keyboard(board, user_id, bet, opened)
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    await call.answer()


@dp.callback_query(F.data.startswith("mines_cashout_"))
async def mines_cashout(call: types.CallbackQuery):
    parts = call.data.split("_")
    bet = float(parts[2])
    safe_count = int(parts[3])
    user_id = call.from_user.id

    multiplier = Mines.calculate_multiplier(safe_count, 5)
    winnings = bet * multiplier

    await db.add_balance(user_id, winnings)
    await db.record_game(user_id, "mines", bet, winnings, True)
    await db.delete_mines_game(user_id)

    new_balance = await db.get_balance(user_id)

    text = f"""
💎 *ВЫИГРЫШ В МИНАХ!*
━━━━━━━━━━━━━━━━━━━━
🏆 Ты успел забрать выигрыш!

Алмазов найдено: {safe_count}
Множитель: x{multiplier:.2f}

Ставка: `${bet:.2f}`
Выигрыш: `${winnings:.2f}`
💰 Баланс: `${new_balance:.2f}`
━━━━━━━━━━━━━━━━━━━━
"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Играть снова", callback_data="game_mines"),
        InlineKeyboardButton(text="🔙 Меню игр", callback_data="games_menu")
    )
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await call.answer("💰 Выигрыш забран!")


async def play_crash(call: types.CallbackQuery, bet: float):
    user_id = call.from_user.id
    await db.deduct_balance(user_id, bet)

    crash = Crash()
    crash_point = crash.generate_crash_point()

    msg = await call.message.answer(
        f"🚀 *КРАШ*\n━━━━━━━━━━━━━━━━━━━━\nСтавка: `${bet:.2f}`\n\nРакета взлетает...\n\nМножитель: x1.00",
        parse_mode="Markdown"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💰 Забрать (x1.00)",
        callback_data=f"crash_cashout_{bet}_1.00_{msg.message_id}"
    ))

    await msg.edit_reply_markup(reply_markup=builder.as_markup())

    multiplier = 1.0
    step = 0.1
    while multiplier < crash_point:
        await asyncio.sleep(0.5)
        multiplier = round(multiplier + step, 2)
        if multiplier > 5:
            step = 0.2
        if multiplier > 10:
            step = 0.5

        current_win = bet * multiplier
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text=f"💰 Забрать (x{multiplier:.2f} = ${current_win:.2f})",
            callback_data=f"crash_cashout_{bet}_{multiplier}_{msg.message_id}"
        ))

        try:
            await msg.edit_text(
                f"🚀 *КРАШ*\n━━━━━━━━━━━━━━━━━━━━\nСтавка: `${bet:.2f}`\n\n📈 Ракета летит!\n\nМножитель: *x{multiplier:.2f}*\nПотенциальный выигрыш: `${current_win:.2f}`",
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
        except Exception:
            break

    # Crash happened
    try:
        await db.record_game(user_id, "crash", bet, 0, False)
        new_balance = await db.get_balance(user_id)
        await msg.edit_text(
            f"💥 *КРАШ на x{crash_point:.2f}!*\n━━━━━━━━━━━━━━━━━━━━\nРакета упала!\n\nСтавка: `${bet:.2f}`\nПроигрыш: `${bet:.2f}`\n💰 Баланс: `${new_balance:.2f}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Играть снова", callback_data="game_crash"),
                 InlineKeyboardButton(text="🔙 Меню", callback_data="games_menu")]
            ])
        )
    except Exception:
        pass


@dp.callback_query(F.data.startswith("crash_cashout_"))
async def crash_cashout(call: types.CallbackQuery):
    parts = call.data.split("_")
    bet = float(parts[2])
    multiplier = float(parts[3])
    user_id = call.from_user.id

    winnings = bet * multiplier
    await db.add_balance(user_id, winnings)
    await db.record_game(user_id, "crash", bet, winnings, True)

    new_balance = await db.get_balance(user_id)

    await call.message.edit_text(
        f"🚀 *ВЫИГРЫШ В КРАШЕ!*\n━━━━━━━━━━━━━━━━━━━━\n🏆 Ты успел забрать!\n\nМножитель: x{multiplier:.2f}\nСтавка: `${bet:.2f}`\nВыигрыш: `${winnings:.2f}`\n💰 Баланс: `${new_balance:.2f}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Играть снова", callback_data="game_crash"),
             InlineKeyboardButton(text="🔙 Меню", callback_data="games_menu")]
        ])
    )
    await call.answer(f"💰 Забрано x{multiplier:.2f}!")


async def play_blackjack(call: types.CallbackQuery, bet: float):
    from games import Blackjack
    user_id = call.from_user.id
    await db.deduct_balance(user_id, bet)

    bj = Blackjack()
    state = bj.deal()

    await db.save_blackjack_game(user_id, bet, state)

    text = f"""
🃏 *БЛЭКДЖЕК*
━━━━━━━━━━━━━━━━━━━━
🏠 Дилер: {state['dealer_cards'][0]} 🂠
👤 Ваши карты: {' '.join(state['player_cards'])}
📊 Ваш счёт: *{state['player_score']}*

Ставка: `${bet:.2f}`
━━━━━━━━━━━━━━━━━━━━
"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Взять карту", callback_data=f"bj_hit_{bet}"),
        InlineKeyboardButton(text="✋ Стоп", callback_data=f"bj_stand_{bet}")
    )
    builder.row(InlineKeyboardButton(text="⬆️ Удвоить", callback_data=f"bj_double_{bet}"))

    await call.message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())


async def play_bulls(call: types.CallbackQuery, bet: float):
    user_id = call.from_user.id
    text = f"""
🎯 *БЫКИ И МЕДВЕДИ*
━━━━━━━━━━━━━━━━━━━━
Ставка: `${bet:.2f}`

Угадай движение BTC за следующие 30 секунд!

📈 Бык — цена вырастет
📉 Медведь — цена упадёт

Выигрыш: x1.9
━━━━━━━━━━━━━━━━━━━━
"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📈 Бык", callback_data=f"bulls_up_{bet}"),
        InlineKeyboardButton(text="📉 Медведь", callback_data=f"bulls_down_{bet}")
    )
    await call.message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("bulls_"))
async def resolve_bulls(call: types.CallbackQuery):
    parts = call.data.split("_")
    choice = parts[1]  # up or down
    bet = float(parts[2])
    user_id = call.from_user.id

    balance = await db.get_balance(user_id)
    if balance < bet:
        await call.answer("❌ Недостаточно средств!", show_alert=True)
        return

    await db.deduct_balance(user_id, bet)

    msg = await call.message.answer("⏳ Ждём результата...\n\n📊 Отслеживаем цену BTC...")
    await asyncio.sleep(3)

    actual = random.choice(["up", "down"])
    win = choice == actual

    winnings = bet * 1.9 if win else 0
    if win:
        await db.add_balance(user_id, winnings)

    await db.record_game(user_id, "bulls", bet, winnings, win)
    new_balance = await db.get_balance(user_id)

    choice_emoji = "📈" if choice == "up" else "📉"
    actual_emoji = "📈" if actual == "up" else "📉"
    choice_name = "Бык" if choice == "up" else "Медведь"
    actual_name = "Вырос" if actual == "up" else "Упал"

    text = f"""
🎯 *БЫКИ И МЕДВЕДИ — РЕЗУЛЬТАТ*
━━━━━━━━━━━━━━━━━━━━
Твой прогноз: {choice_emoji} *{choice_name}*
BTC {actual_emoji} *{actual_name}*

{'🏆 *ВЕРНО! x1.9*' if win else '😔 *Промах!*'}

Ставка: `${bet:.2f}`
{'Выигрыш: `$' + f"{winnings:.2f}`" if win else 'Проигрыш: `$' + f"{bet:.2f}`"}
💰 Баланс: `${new_balance:.2f}`
━━━━━━━━━━━━━━━━━━━━
"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Играть снова", callback_data="game_bulls"),
        InlineKeyboardButton(text="🔙 Меню игр", callback_data="games_menu")
    )
    await msg.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await call.answer()


# ==================== DEPOSIT ====================

@dp.callback_query(F.data == "deposit")
async def deposit_handler(call: types.CallbackQuery):
    text = """
💰 *ПОПОЛНЕНИЕ СЧЁТА*
━━━━━━━━━━━━━━━━━━━━

Выбери сумму пополнения (в USD):

💳 Оплата через *CryptoBot*
🔒 Безопасно и анонимно
⚡ Моментальное зачисление

Поддерживаемые валюты:
₿ BTC • Ξ ETH • 💵 USDT • 🔵 TON
━━━━━━━━━━━━━━━━━━━━
"""
    try:
        photo = FSInputFile("images/deposit.jpg")
        await call.message.edit_media(
            InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
            reply_markup=deposit_keyboard()
        )
    except Exception:
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=deposit_keyboard())
    await call.answer()


@dp.callback_query(F.data.startswith("dep_"))
async def select_deposit_amount(call: types.CallbackQuery, state: FSMContext):
    amount_str = call.data.split("_")[1]

    if amount_str == "custom":
        await state.set_state(States.waiting_deposit_amount)
        await call.message.answer(
            "✏️ *Введите сумму пополнения в USD:*\n\nМинимум: $5 | Максимум: $10,000",
            parse_mode="Markdown",
            reply_markup=back_keyboard("deposit")
        )
    else:
        amount = float(amount_str)
        await call.message.edit_caption(
            caption=f"💰 *Пополнение на ${amount:.2f}*\n\n━━━━━━━━━━━━━━━━━━━━\nВыбери валюту оплаты:\n━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown",
            reply_markup=currency_keyboard(amount)
        )
    await call.answer()


@dp.callback_query(F.data.startswith("pay_"))
async def create_payment(call: types.CallbackQuery):
    parts = call.data.split("_")
    currency = parts[1]
    amount = float(parts[2])
    user_id = call.from_user.id

    await call.answer("⏳ Создаём счёт...", show_alert=False)

    try:
        invoice = await crypto.create_invoice(amount, currency, user_id)

        text = f"""
💳 *СЧЁТ НА ОПЛАТУ*
━━━━━━━━━━━━━━━━━━━━
💰 Сумма: `${amount:.2f}`
💱 Валюта: *{currency}*
🔢 ID счёта: `{invoice['invoice_id']}`

⏱ Счёт действителен: *30 минут*
━━━━━━━━━━━━━━━━━━━━
После оплаты нажми *«✅ Проверить»*
"""
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="💳 Оплатить через CryptoBot",
            url=invoice['pay_url']
        ))
        builder.row(InlineKeyboardButton(
            text="✅ Проверить оплату",
            callback_data=f"check_pay_{invoice['invoice_id']}_{amount}"
        ))
        builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="deposit"))

        await call.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=builder.as_markup())

    except Exception as e:
        await call.message.answer(f"❌ Ошибка создания счёта. Попробуйте позже.\n`{e}`", parse_mode="Markdown")


@dp.callback_query(F.data.startswith("check_pay_"))
async def check_payment(call: types.CallbackQuery):
    parts = call.data.split("_")
    invoice_id = int(parts[2])
    amount = float(parts[3])
    user_id = call.from_user.id

    await call.answer("⏳ Проверяем оплату...")

    try:
        paid = await crypto.check_invoice(invoice_id)

        if paid:
            await db.add_balance(user_id, amount)
            await db.record_deposit(user_id, amount)

            new_balance = await db.get_balance(user_id)

            text = f"""
✅ *ОПЛАТА ПОДТВЕРЖДЕНА!*
━━━━━━━━━━━━━━━━━━━━
🎉 Поздравляем! Средства зачислены!

💰 Пополнено: `+${amount:.2f}`
💎 Текущий баланс: `${new_balance:.2f}`

Удачи в играх! 🍀
━━━━━━━━━━━━━━━━━━━━
"""
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="🎰 Играть", callback_data="games_menu"),
                InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu")
            )
            await call.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=builder.as_markup())
        else:
            await call.answer("❌ Оплата не найдена. Попробуйте позже.", show_alert=True)

    except Exception as e:
        await call.answer(f"Ошибка проверки: {e}", show_alert=True)


# ==================== WITHDRAW ====================

@dp.callback_query(F.data == "withdraw")
async def withdraw_handler(call: types.CallbackQuery, state: FSMContext):
    balance = await db.get_balance(call.from_user.id)
    text = f"""
💸 *ВЫВОД СРЕДСТВ*
━━━━━━━━━━━━━━━━━━━━
💰 Доступно к выводу: `${balance:.2f}`

Минимальная сумма вывода: *$10*
Срок обработки: *мгновенно*

Введите сумму для вывода:
━━━━━━━━━━━━━━━━━━━━
"""
    await state.set_state(States.waiting_withdraw_amount)
    await state.update_data(balance=balance)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"💰 Весь баланс (${balance:.2f})", callback_data=f"with_all_{balance}")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))

    try:
        photo = FSInputFile("images/withdraw.jpg")
        await call.message.edit_media(
            InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
            reply_markup=builder.as_markup()
        )
    except Exception:
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await call.answer()


@dp.message(States.waiting_withdraw_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace("$", "").strip())
        data = await state.get_data()
        balance = await db.get_balance(message.from_user.id)

        if amount < 10:
            await message.answer("❌ Минимальная сумма вывода: $10")
            return
        if amount > balance:
            await message.answer(f"❌ Недостаточно средств. Ваш баланс: ${balance:.2f}")
            return

        await state.update_data(withdraw_amount=amount)
        await state.set_state(States.waiting_withdraw_address)
        await message.answer(
            f"✅ Сумма: `${amount:.2f}`\n\nВведите ваш крипто-адрес для получения средств:",
            parse_mode="Markdown"
        )
    except ValueError:
        await message.answer("❌ Введите корректную сумму числом")


@dp.message(States.waiting_withdraw_address)
async def process_withdraw_address(message: types.Message, state: FSMContext):
    address = message.text.strip()
    data = await state.get_data()
    amount = data.get('withdraw_amount')
    user_id = message.from_user.id

    await db.deduct_balance(user_id, amount)
    await db.record_withdrawal(user_id, amount, address)

    await state.clear()

    text = f"""
✅ *ЗАЯВКА НА ВЫВОД ПРИНЯТА*
━━━━━━━━━━━━━━━━━━━━
💸 Сумма: `${amount:.2f}`
📬 Адрес: `{address[:20]}...`

⚡ Обработка займёт несколько минут
🔔 Уведомим о статусе

💰 Новый баланс: `${await db.get_balance(user_id):.2f}`
━━━━━━━━━━━━━━━━━━━━
"""
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())


# ==================== BONUSES ====================

@dp.callback_query(F.data == "bonuses")
async def bonuses_handler(call: types.CallbackQuery):
    user_id = call.from_user.id
    last_bonus = await db.get_last_bonus(user_id)
    can_claim = True

    if last_bonus:
        diff = datetime.now() - last_bonus
        can_claim = diff >= timedelta(hours=24)
        next_bonus = timedelta(hours=24) - diff
        next_h = int(next_bonus.seconds / 3600)
        next_m = int((next_bonus.seconds % 3600) / 60)

    text = f"""
🎁 *БОНУСЫ И АКЦИИ*
━━━━━━━━━━━━━━━━━━━━

🌅 *Ежедневный бонус:*
{'✅ Доступен! Получи $5-50!' if can_claim else f'⏰ Следующий через {next_h}ч {next_m}м'}

🎫 *Реферальная программа:*
Приглашай друзей — получай 10% от их пополнений!

🏆 *VIP привилегии:*
• Silver: +5% к выигрышам
• Gold: +10% + еженедельный бонус
• Platinum: +15% + личный менеджер
• Diamond: +20% + эксклюзивные игры

💰 *Кэшбэк:*
Каждую неделю возвращаем 5% от проигрышей

🎉 *Турниры:*
Участвуй в еженедельных турнирах!
Призовой фонд: $10,000+
━━━━━━━━━━━━━━━━━━━━
"""
    builder = InlineKeyboardBuilder()
    if can_claim:
        builder.row(InlineKeyboardButton(text="🎁 Получить дневной бонус", callback_data="claim_daily"))
    builder.row(InlineKeyboardButton(text="👥 Реферальная ссылка", callback_data="referral"))
    builder.row(InlineKeyboardButton(text="🏆 VIP программа", callback_data="vip_info"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))

    try:
        photo = FSInputFile("images/bonus.jpg")
        await call.message.edit_media(
            InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
            reply_markup=builder.as_markup()
        )
    except Exception:
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await call.answer()


@dp.callback_query(F.data == "claim_daily")
async def claim_daily_bonus(call: types.CallbackQuery):
    user_id = call.from_user.id
    last_bonus = await db.get_last_bonus(user_id)

    if last_bonus and (datetime.now() - last_bonus) < timedelta(hours=24):
        await call.answer("❌ Бонус уже получен сегодня!", show_alert=True)
        return

    bonus = random.uniform(5, 50)
    await db.add_balance(user_id, bonus)
    await db.set_last_bonus(user_id)

    new_balance = await db.get_balance(user_id)

    await call.answer(f"🎉 Получен бонус ${bonus:.2f}!", show_alert=True)
    await call.message.edit_caption(
        caption=f"🎁 *БОНУС ПОЛУЧЕН!*\n\n🎉 Тебе начислено: `+${bonus:.2f}`\n💰 Баланс: `${new_balance:.2f}`\n\nСледующий бонус доступен через 24 часа!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Играть!", callback_data="games_menu")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="bonuses")]
        ])
    )


@dp.callback_query(F.data == "referral")
async def referral_handler(call: types.CallbackQuery):
    user_id = call.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref{user_id}"
    ref_count = await db.get_referral_count(user_id)
    ref_earned = await db.get_referral_earnings(user_id)

    text = f"""
👥 *РЕФЕРАЛЬНАЯ ПРОГРАММА*
━━━━━━━━━━━━━━━━━━━━
🔗 Твоя ссылка:
`{ref_link}`

📊 Статистика:
• Приглашено: {ref_count} игроков
• Заработано: `${ref_earned:.2f}`

💰 *Условия:*
• 10% от каждого пополнения друга
• Выплата мгновенно на баланс
• Без ограничений!
━━━━━━━━━━━━━━━━━━━━
"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📤 Поделиться ссылкой",
        url=f"https://t.me/share/url?url={ref_link}&text=Играй%20в%20Lucky%20Strike%20Casino%20и%20выигрывай!"
    ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="bonuses"))

    await call.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await call.answer()


# ==================== PROMO CODE ====================

@dp.callback_query(F.data == "promo")
async def promo_handler(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(States.waiting_promo)
    await call.message.answer(
        "🎫 *Введите промокод:*\n\nПромокоды можно найти в нашем канале и соцсетях!",
        parse_mode="Markdown",
        reply_markup=back_keyboard("main_menu")
    )
    await call.answer()


@dp.message(States.waiting_promo)
async def process_promo(message: types.Message, state: FSMContext):
    promo = message.text.strip().upper()
    user_id = message.from_user.id

    result = await db.use_promo(user_id, promo)
    await state.clear()

    if result['success']:
        await db.add_balance(user_id, result['amount'])
        await message.answer(
            f"✅ *Промокод активирован!*\n\n🎁 Начислено: `+${result['amount']:.2f}`",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    else:
        await message.answer(
            f"❌ *{result['error']}*",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )


# ==================== LEADERBOARD ====================

@dp.callback_query(F.data == "leaderboard")
async def leaderboard_handler(call: types.CallbackQuery):
    top = await db.get_leaderboard()

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    rows = []
    for i, player in enumerate(top):
        rows.append(f"{medals[i]} *{player['username']}* — `${player['total_won']:.0f}` выиграно")

    text = "🏆 *ТОП-10 ИГРОКОВ*\n━━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(rows) + "\n\n━━━━━━━━━━━━━━━━━━━━"

    try:
        photo = FSInputFile("images/leaderboard.jpg")
        await call.message.edit_media(
            InputMediaPhoto(media=photo, caption=text, parse_mode="Markdown"),
            reply_markup=back_keyboard("main_menu")
        )
    except Exception:
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=back_keyboard("main_menu"))
    await call.answer()


# ==================== HISTORY ====================

@dp.callback_query(F.data == "history")
async def history_handler(call: types.CallbackQuery):
    user_id = call.from_user.id
    games_history = await db.get_game_history(user_id, limit=10)

    if not games_history:
        text = "📜 *История ставок*\n\nУ вас пока нет сыгранных игр!"
    else:
        rows = []
        for g in games_history:
            emoji = "✅" if g['won'] else "❌"
            game_names = {
                "slots": "🎰", "dice": "🎲", "coin": "🪙",
                "roulette": "🎡", "mines": "💣", "crash": "🚀",
                "blackjack": "🃏", "bulls": "🎯"
            }
            game_emoji = game_names.get(g['game'], "🎮")
            rows.append(f"{emoji} {game_emoji} ${g['bet']:.0f} → {'$' + f\"{g['win']:.0f}\" if g['won'] else '-$' + f\"{g['bet']:.0f}\"}")

        text = "📜 *ПОСЛЕДНИЕ 10 ИГР*\n━━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(rows) + "\n━━━━━━━━━━━━━━━━━━━━"

    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=back_keyboard("main_menu"))
    await call.answer()


# ==================== SUPPORT ====================

@dp.callback_query(F.data == "support")
async def support_handler(call: types.CallbackQuery):
    text = """
📞 *ПОДДЕРЖКА*
━━━━━━━━━━━━━━━━━━━━

🕐 Работаем: 24/7

📬 Способы связи:

💬 Написать в чат поддержки
📧 Email: support@luckystrike.casino
📢 Telegram: @LuckyStrikeSupport
📣 Канал с новостями: @LuckyStrikeNews

━━━━━━━━━━━━━━━━━━━━
⚡ *Среднее время ответа: 5 минут*
"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💬 Написать в поддержку", url="https://t.me/LuckyStrikeSupport"))
    builder.row(InlineKeyboardButton(text="📢 Наш канал", url="https://t.me/LuckyStrikeNews"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))

    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await call.answer()


@dp.callback_query(F.data == "about")
async def about_handler(call: types.CallbackQuery):
    text = """
ℹ️ *О LUCKY STRIKE CASINO*
━━━━━━━━━━━━━━━━━━━━

🏆 *Лучшее крипто-казино в Telegram*

🎮 8 уникальных игр
🔒 Честный алгоритм (Provably Fair)
⚡ Мгновенные выплаты через CryptoBot
🌍 Работаем по всему миру
🎁 Щедрые бонусы каждый день

💯 *Честность:*
Все результаты генерируются криптографически
и не могут быть изменены казино.

📊 *Статистика:*
• Игроков: 50,000+
• Выплачено: $2,500,000+
• Игр сыграно: 1,000,000+

*Играй ответственно!*
━━━━━━━━━━━━━━━━━━━━
"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await call.answer()


# ==================== ADMIN ====================

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    stats = await db.get_global_stats()
    text = f"""
⚙️ *АДМИН ПАНЕЛЬ*
━━━━━━━━━━━━━━━━━━━━
👥 Всего игроков: {stats['total_users']}
🎮 Игр сыграно: {stats['total_games']}
💰 Оборот: ${stats['total_turnover']:.2f}
💸 Выплачено: ${stats['total_paid']:.2f}
📈 Прибыль казино: ${stats['casino_profit']:.2f}
━━━━━━━━━━━━━━━━━━━━
"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"))
    builder.row(
        InlineKeyboardButton(text="💰 Начислить баланс", callback_data="admin_add_balance"),
        InlineKeyboardButton(text="🚫 Блокировать", callback_data="admin_ban")
    )
    builder.row(InlineKeyboardButton(text="🎫 Создать промокод", callback_data="admin_promo"))
    builder.row(InlineKeyboardButton(text="📊 Полная статистика", callback_data="admin_stats"))

    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())


async def main():
    await db.init()
    logger.info("Casino Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
