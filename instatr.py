import asyncio
from playwright.async_api import async_playwright
import aiohttp
import re
import os

# ========= TELEGRAM =========
BOT_TOKEN = os.getenv(""8558476155:AAGm5WeitSST46bVZEq_jySLD1T1Ag2iXDY")
CHAT_IDS = os.getenv("7682951862", "1377959451").split(",")

# ========= SETTINGS =========
CART_URL = "https://www.swiggy.com/instamart/cart"
TARGET_PRICE = int(os.getenv("TARGET_PRICE", "70"))


# ---------------- TELEGRAM ----------------
async def send_single(session, chat_id, msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        async with session.post(url, data={"chat_id": chat_id, "text": msg}) as r:
            text = await r.text()
            print(f"📩 Sent to {chat_id}: {text}")
    except Exception as e:
        print(f"❌ Error sending to {chat_id}: {e}")


async def send_telegram(msg):
    valid_chat_ids = [c.strip() for c in CHAT_IDS if c.strip()]
    if not BOT_TOKEN or not valid_chat_ids:
        print("⚠️ BOT_TOKEN or CHAT_IDS missing.")
        return

    async with aiohttp.ClientSession() as session:
        tasks = [send_single(session, chat_id, msg) for chat_id in valid_chat_ids]
        await asyncio.gather(*tasks)


# ---------------- PRICE FUNCTIONS ----------------
def extract_price(text):
    match = re.search(r"₹\s*(\d+(?:\.\d+)?)", text)
    if match:
        return int(float(match.group(1)))
    return None


async def ensure_cart_loaded(page, max_attempts=5):
    for attempt in range(1, max_attempts + 1):
        print(f"🔄 Loading cart... attempt {attempt}/{max_attempts}")
        await page.goto(CART_URL, timeout=60000)
        await page.wait_for_timeout(5000)
        body_text = await page.inner_text("body")

        if "Something went wrong" in body_text:
            print("⚠️ Error page detected. Trying retry/reload...")
            try:
                await page.click("text=Retry", timeout=5000)
            except Exception:
                await page.reload()
            await asyncio.sleep(3)
            continue

        if "₹" in body_text:
            print("✅ Cart loaded successfully.")
            return True

        print("⚠️ Cart not loaded properly. Reloading...")
        await page.reload()
        await asyncio.sleep(3)

    print("❌ Cart failed to load after max attempts.")
    return False


# ---------------- MAIN BOT ----------------
async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir="swiggy_profile",
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )

        page = await context.new_page()
        print("➡️ BOT STARTED")

        try:
            print("🔄 Checking price once...")

            loaded = await ensure_cart_loaded(page)
            if not loaded:
                await send_telegram("❌ Instamart cart failed to load.")
                return

            texts = await page.locator("text=/₹/").all_inner_texts()
            print("📝 Raw texts:", texts)

            prices = [extract_price(t) for t in texts if extract_price(t) is not None]
            print("💰 Extracted prices:", prices)

            if not prices:
                print("⚠️ No prices found.")
                await send_telegram("⚠️ No prices found in Instamart cart.")
                return

            mrp = None
            item_price = None

            for i in range(len(prices) - 1):
                if prices[i] > prices[i + 1]:
                    mrp = prices[i]
                    item_price = prices[i + 1]
                    break

            if item_price is not None:
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
                    await send_telegram(
                        f"ℹ️ Checked Instamart\n\n"
                        f"Item price: ₹{item_price}\n"
                        f"MRP: ₹{mrp}\n"
                        f"Target: ₹{TARGET_PRICE}\n"
                        f"Status: Above target"
                    )
            else:
                print("⚠️ Could not determine item price and MRP.")
                await send_telegram("⚠️ Could not determine item price and MRP.")

        except Exception as e:
            print("❌ Unexpected error:", e)
            await send_telegram(f"❌ Bot crashed!\nError: {e}")

        finally:
            await context.close()
            print("🔒 Browser closed.")


if __name__ == "__main__":
    asyncio.run(main())
