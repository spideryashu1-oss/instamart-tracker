import asyncio
from playwright.async_api import async_playwright
import aiohttp
import re
import time

# ========= TELEGRAM =========
BOT_TOKEN = "8558476155:AAGm5WeitSST46bVZEq_jySLD1T1Ag2iXDY"
CHAT_IDS = ["7682951862", "1377959451", "8439994620"]  # Add more here

# ========= SETTINGS =========
CART_URL = "https://www.swiggy.com/instamart/cart"
TARGET_PRICE = 70
CHECK_INTERVAL = 300  # 5 minutes


# ---------------- TELEGRAM ----------------
async def send_single(session, chat_id, msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        async with session.post(url, data={"chat_id": chat_id, "text": msg}) as r:
            text = await r.text()
            print(f"📩 Sent to {chat_id}:", text)
    except Exception as e:
        print(f"❌ Error sending to {chat_id}:", e)


async def send_telegram(msg):
    async with aiohttp.ClientSession() as session:
        tasks = [send_single(session, chat_id, msg) for chat_id in CHAT_IDS]
        await asyncio.gather(*tasks)


# ---------------- PRICE FUNCTIONS ----------------
def extract_price(text):
    match = re.search(r"₹\s*(\d+(?:\.\d+)?)", text)
    if match:
        return int(float(match.group(1)))
    return None


async def ensure_cart_loaded(page):
    """Keep retrying until cart loads properly"""
    while True:
        await page.goto(CART_URL, timeout=60000)
        await page.wait_for_timeout(5000)
        body_text = await page.inner_text("body")

        if "Something went wrong" in body_text:
            print("⚠️ Error page detected. Trying Retry...")
            try:
                await page.click("text=Retry", timeout=5000)
            except:
                print("Retry button not clickable. Reloading...")
                await page.reload()
            await asyncio.sleep(5)
            continue

        if "₹" in body_text:
            print("✅ Cart loaded successfully.")
            return

        print("⚠️ Cart not loaded properly. Reloading...")
        await page.reload()
        await asyncio.sleep(5)


# ---------------- MAIN BOT ----------------
async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir="swiggy_profile",
            headless=False,  # First login manually; change to True after login
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = await context.new_page()
        print("➡️ BOT STARTED (Async Telegram Version)")

        try:
            while True:
                print("\n🔄 Checking price...")

                await ensure_cart_loaded(page)

                texts = await page.locator("text=/₹/").all_inner_texts()
                print("📝 Raw texts:", texts)

                prices = [extract_price(t) for t in texts if extract_price(t) is not None]
                print("💰 Extracted prices:", prices)

                if not prices:
                    print("⚠️ No prices found.")
                    await asyncio.sleep(CHECK_INTERVAL)
                    continue

                mrp = None
                item_price = None

                for i in range(len(prices) - 1):
                    if prices[i] > prices[i + 1]:
                        mrp = prices[i]
                        item_price = prices[i + 1]
                        break

                if item_price:
                    print(f"✅ MRP: ₹{mrp} | PRICE: ₹{item_price}")

                    if item_price <= TARGET_PRICE:
                        print("🚨 Target reached! Sending alert...")
                        await send_telegram(
                            f"🚨 Instamart Price Alert\n\n"
                            f"Item price: ₹{item_price}\n"
                            f"MRP: ₹{mrp}\n"
                            f"Target: ₹{TARGET_PRICE}"
                        )
                    else:
                        print("⏳ Price above target.")

                await asyncio.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n🛑 Bot stopped manually.")
            await send_telegram("🛑 Bot stopped by @spideryashu")

        except Exception as e:
            print("❌ Unexpected error:", e)
            await send_telegram(f"❌ Bot crashed!\nError: {e}")

        finally:
            await context.close()
            print("🔒 Browser closed.")


# ---------------- RUN BOT ----------------
if __name__ == "__main__":
    asyncio.run(main())
