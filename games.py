import random
import math
from typing import Dict, List, Tuple


class SlotMachine:
    SYMBOLS = ["7️⃣", "🍒", "⭐", "🍋", "🍇", "💎", "🔔", "🍀"]
    WEIGHTS = [3, 15, 10, 15, 12, 1, 8, 6]

    COMBOS = [
        (["💎", "💎", "💎"], 150, "💎 ДЖЕКПОТ 💎"),
        (["7️⃣", "7️⃣", "7️⃣"], 100, "🎰 ТРОЙНАЯ СЕМЁРКА"),
        (["🍒", "🍒", "🍒"], 50, "🍒 Три вишни"),
        (["⭐", "⭐", "⭐"], 25, "⭐ Три звезды"),
        (["🍋", "🍋", "🍋"], 15, "🍋 Три лимона"),
        (["🍇", "🍇", "🍇"], 10, "🍇 Три ягоды"),
        (["🔔", "🔔", "🔔"], 8, "🔔 Три колокола"),
        (["🍀", "🍀", "🍀"], 8, "🍀 Три клевера"),
    ]

    def spin(self) -> Dict:
        r1 = random.choices(self.SYMBOLS, weights=self.WEIGHTS)[0]
        r2 = random.choices(self.SYMBOLS, weights=self.WEIGHTS)[0]
        r3 = random.choices(self.SYMBOLS, weights=self.WEIGHTS)[0]

        for combo_symbols, multiplier, name in self.COMBOS:
            if r1 == r2 == r3 == combo_symbols[0]:
                return {"r1": r1, "r2": r2, "r3": r3, "win": True, "multiplier": multiplier, "combo_name": name}

        # Two of a kind
        if r1 == r2 or r2 == r3 or r1 == r3:
            return {"r1": r1, "r2": r2, "r3": r3, "win": True, "multiplier": 2, "combo_name": "🎯 Пара!"}

        # Single 7
        if "7️⃣" in [r1, r2, r3]:
            return {"r1": r1, "r2": r2, "r3": r3, "win": True, "multiplier": 1.5, "combo_name": "7️⃣ Одна семёрка"}

        return {"r1": r1, "r2": r2, "r3": r3, "win": False, "multiplier": 0, "combo_name": ""}


class Dice:
    DICE_EMOJIS = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}

    def roll(self) -> Dict:
        value = random.randint(1, 6)
        # Simulate a "guess" - bot randomly picked a guess
        guess = random.randint(1, 6)
        guess_half = "low" if random.random() < 0.5 else "high"
        actual_half = "low" if value <= 3 else "high"

        if guess == value:
            return {
                "value": value,
                "dice_emoji": self.DICE_EMOJIS[value],
                "win": True,
                "multiplier": 5,
                "result_text": "Точное попадание! x5"
            }
        elif guess_half == actual_half:
            return {
                "value": value,
                "dice_emoji": self.DICE_EMOJIS[value],
                "win": True,
                "multiplier": 1.9,
                "result_text": "Угадал половину! x1.9"
            }
        else:
            return {
                "value": value,
                "dice_emoji": self.DICE_EMOJIS[value],
                "win": False,
                "multiplier": 0,
                "result_text": "Мимо!"
            }


class CoinFlip:
    def flip(self) -> Dict:
        result = random.choice(["heads", "tails"])
        return {"result": result}


class Roulette:
    RED_NUMBERS = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
    BLACK_NUMBERS = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]

    def spin(self) -> Dict:
        number = random.randint(0, 36)
        if number == 0:
            color = "green"
            emoji = "🟢"
            color_name = "Зелёное (0)"
        elif number in self.RED_NUMBERS:
            color = "red"
            emoji = "🔴"
            color_name = "Красное"
        else:
            color = "black"
            emoji = "⚫"
            color_name = "Чёрное"

        return {"number": number, "color": color, "emoji": emoji, "color_name": color_name}

    def check_win(self, bet_type: str, number: int) -> Tuple[bool, int]:
        if bet_type == "red":
            return number in self.RED_NUMBERS, 2
        elif bet_type == "black":
            return number in self.BLACK_NUMBERS, 2
        elif bet_type == "green":
            return number == 0, 14
        elif bet_type == "first":
            return 1 <= number <= 12, 3
        elif bet_type == "second":
            return 13 <= number <= 24, 3
        elif bet_type == "third":
            return 25 <= number <= 36, 3
        elif bet_type == "even":
            return number != 0 and number % 2 == 0, 2
        elif bet_type == "odd":
            return number % 2 == 1, 2
        return False, 0


class Mines:
    def __init__(self, mines_count: int = 5):
        self.mines_count = mines_count

    def generate_board(self) -> List[str]:
        board = ["safe"] * 25
        mine_positions = random.sample(range(25), self.mines_count)
        for pos in mine_positions:
            board[pos] = "mine"
        return board

    @staticmethod
    def calculate_multiplier(safe_opened: int, mines_count: int) -> float:
        if safe_opened == 0:
            return 1.0
        total = 25
        safe_total = total - mines_count
        multiplier = 1.0
        for i in range(safe_opened):
            remaining = total - i
            safe_remaining = safe_total - i
            multiplier *= remaining / safe_remaining
        return round(multiplier * 0.97, 2)  # 3% house edge


class Crash:
    def generate_crash_point(self) -> float:
        # House edge of ~3%
        r = random.random()
        if r < 0.03:
            return 1.0  # instant crash 3% of the time
        crash = 0.99 / (1 - r)
        return round(min(crash, 1000), 2)


class Blackjack:
    SUITS = ["♠", "♥", "♦", "♣"]
    VALUES = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]

    def __init__(self):
        self.deck = [f"{v}{s}" for v in self.VALUES for s in self.SUITS]
        random.shuffle(self.deck)

    def card_value(self, card: str) -> int:
        v = card[:-1]
        if v in ["J", "Q", "K"]:
            return 10
        if v == "A":
            return 11
        return int(v)

    def hand_score(self, hand: List[str]) -> int:
        score = sum(self.card_value(c) for c in hand)
        aces = sum(1 for c in hand if c[:-1] == "A")
        while score > 21 and aces:
            score -= 10
            aces -= 1
        return score

    def deal(self) -> Dict:
        player = [self.deck.pop(), self.deck.pop()]
        dealer = [self.deck.pop(), self.deck.pop()]
        return {
            "player_cards": player,
            "dealer_cards": dealer,
            "player_score": self.hand_score(player),
            "dealer_score": self.hand_score(dealer),
            "deck": self.deck
        }

    def hit(self, state: Dict) -> Dict:
        state["player_cards"].append(state["deck"].pop())
        state["player_score"] = self.hand_score(state["player_cards"])
        return state

    def dealer_play(self, state: Dict) -> Dict:
        while self.hand_score(state["dealer_cards"]) < 17:
            state["dealer_cards"].append(state["deck"].pop())
        state["dealer_score"] = self.hand_score(state["dealer_cards"])
        return state

    def check_result(self, state: Dict) -> Dict:
        p = state["player_score"]
        d = state["dealer_score"]

        if p > 21:
            return {"result": "bust", "multiplier": 0}
        if d > 21:
            return {"result": "dealer_bust", "multiplier": 2}
        if p == 21 and len(state["player_cards"]) == 2:
            return {"result": "blackjack", "multiplier": 2.5}
        if p > d:
            return {"result": "win", "multiplier": 2}
        if p == d:
            return {"result": "push", "multiplier": 1}
        return {"result": "lose", "multiplier": 0}
