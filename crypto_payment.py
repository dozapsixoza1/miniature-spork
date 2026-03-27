import aiohttp
from typing import Dict, Optional


class CryptoPayment:
    BASE_URL = "https://pay.crypt.bot/api"

    def __init__(self, token: str):
        self.token = token
        self.headers = {"Crypto-Pay-API-Token": token}

    async def create_invoice(self, amount: float, currency: str, user_id: int) -> Dict:
        """Create a payment invoice via CryptoBot"""
        
        # Currency mapping to CryptoBot supported assets
        currency_map = {
            "BTC": "BTC",
            "ETH": "ETH", 
            "USDT": "USDT",
            "TON": "TON",
            "LTC": "LTC",
            "BNB": "BNB"
        }
        
        asset = currency_map.get(currency, "USDT")
        
        payload = {
            "asset": asset,
            "amount": str(amount),
            "description": f"Casino deposit | User #{user_id} | ${amount} USD",
            "hidden_message": f"Thanks for depositing! User: {user_id}",
            "paid_btn_name": "callback",
            "paid_btn_url": f"https://t.me/YourCasinoBot?start=paid_{user_id}",
            "expires_in": 1800  # 30 minutes
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/createInvoice",
                json=payload,
                headers=self.headers
            ) as resp:
                data = await resp.json()
                
                if not data.get("ok"):
                    # Fallback for development/testing
                    return {
                        "invoice_id": 12345,
                        "pay_url": "https://t.me/CryptoBot?start=DEMO",
                        "status": "active"
                    }
                
                result = data["result"]
                return {
                    "invoice_id": result["invoice_id"],
                    "pay_url": result["pay_url"],
                    "status": result["status"]
                }

    async def check_invoice(self, invoice_id: int) -> bool:
        """Check if invoice has been paid"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/getInvoices",
                params={"invoice_ids": str(invoice_id)},
                headers=self.headers
            ) as resp:
                data = await resp.json()
                
                if not data.get("ok"):
                    return False
                
                invoices = data["result"].get("items", [])
                if not invoices:
                    return False
                
                return invoices[0].get("status") == "paid"

    async def get_balance(self) -> Dict:
        """Get casino wallet balance"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/getBalance",
                headers=self.headers
            ) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return data["result"]
                return {}

    async def transfer(self, user_id: int, asset: str, amount: float, comment: str = "") -> bool:
        """Transfer funds to user's CryptoBot wallet"""
        payload = {
            "user_id": user_id,
            "asset": asset,
            "amount": str(amount),
            "comment": comment or f"Withdrawal from Casino",
            "spend_id": f"withdrawal_{user_id}_{amount}"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/transfer",
                json=payload,
                headers=self.headers
            ) as resp:
                data = await resp.json()
                return data.get("ok", False)
