import json, os, time
from datetime import datetime, timezone

# ================= SETTINGS =================
BASE = r"C:\Users\YOURUSERNAME\AppData\LocalLow\Conradical Games\Screen Stocks\mods"
MARKET_FILE = BASE + r"\export\market.json"
COMMAND_DIR = BASE + r"\commands\$PLAIN"

PRICE_ID = "$BASE"        # market entry "name" used for price
POSITION_ID = "$PLAIN"    # "stockId" used for player position
LOOP_DELAY = 1.0

# Trader mode
TRADER_ENABLED = True
TRADER_BUY = 600          # BUY when price <=
TRADER_CLOSE = 900        # CLOSE when price >

# Crash mode (start/end as (hour, minute)) - UTC
CRASH_START, CRASH_END = (17, 50), (18, 10)
CRASH_SHORT = 900
CRASH_BUY = 15

EXTRA = 2.0               # safety margin added to cooldowns
CLOSE_LOCK = 3.0          # stops close being spammed

# Lock durations (buy/short get updated from market.json) and unlock times
lock_len = {"buymax.json": 105.0 + EXTRA, "shortmax.json": 102.0 + EXTRA, "closemax.json": CLOSE_LOCK}
unlock_at = dict.fromkeys(lock_len, 0.0)


# ================= HELPERS =================
def read_market():
    try:
        with open(MARKET_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] market.json: {e}")


def find_price(data):
    """Recursively search for a dict whose 'name' is PRICE_ID."""
    if isinstance(data, dict):
        if data.get("name") == PRICE_ID and "price" in data:
            return float(data["price"])
        data = data.values()
    if isinstance(data, (list, type({}.values()))):
        for item in data:
            if isinstance(item, (dict, list)) and (p := find_price(item)) is not None:
                return p


def get_position(market):
    for p in market.get("player", {}).get("positions", []):
        if p.get("stockId") == POSITION_ID:
            return int(p.get("sharesOwned", 0)), int(p.get("sharesShorted", 0))
    return 0, 0


def update_cooldowns(market):
    player = market.get("player", {})
    for cmd, key in (("buymax.json", "buyCooldownSeconds"), ("shortmax.json", "shortCooldownSeconds")):
        try:
            lock_len[cmd] = float(player[key]) + EXTRA
        except (KeyError, TypeError, ValueError):
            pass


def run(cmd):
    left = unlock_at[cmd] - time.time()
    if left > 0:
        print(f"[LOCK] {cmd}: {left:.0f}s left")
        return
    path = os.path.join(COMMAND_DIR, cmd)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["execute"] = True
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        unlock_at[cmd] = time.time() + lock_len[cmd]
        print(f"[ACTION] {cmd} (locked {lock_len[cmd]:.0f}s)")
    except Exception as e:
        print(f"[ERROR] {cmd}: {e}")


def trade(side, owned, shorted):
    """side = 'buy' or 'short'. Closes the opposite position first."""
    same, opposite = (owned, shorted) if side == "buy" else (shorted, owned)
    if same:
        return print(f"[{side.upper()}] Already in position")
    run("closemax.json" if opposite else f"{side}max.json")


def in_crash_time():
    now = datetime.now(timezone.utc)
    return CRASH_START <= (now.hour, now.minute) <= CRASH_END


# ================= MODES =================
def crash_mode(price, owned, shorted):
    print("[MODE] CRASH")
    if owned:
        return                                    # hold
    if shorted:
        if price < CRASH_BUY:
            run("closemax.json")
    elif price > CRASH_SHORT:
        trade("short", owned, shorted)
    elif price < CRASH_BUY:
        trade("buy", owned, shorted)


def trader_mode(price, owned, shorted):
    print(f"[MODE] TRADER (buy <= {TRADER_BUY}, close > {TRADER_CLOSE})")
    if price <= TRADER_BUY:
        trade("buy", owned, shorted)
    elif price > TRADER_CLOSE and (owned or shorted):
        run("closemax.json")


# ================= MAIN =================
def main():
    print("===== SCREEN STOCKS TRADER =====")
    while True:
        time.sleep(LOOP_DELAY)
        market = read_market()
        if market is None:
            continue
        price = find_price(market)
        if price is None:
            print(f"[ERROR] {PRICE_ID} price not found")
            continue

        update_cooldowns(market)
        owned, shorted = get_position(market)
        print(f"\n[{datetime.now():%H:%M:%S}] {PRICE_ID}={price} | owned={owned} shorted={shorted}")

        if in_crash_time():
            crash_mode(price, owned, shorted)
        elif TRADER_ENABLED:
            trader_mode(price, owned, shorted)

if __name__ == "__main__":
    main()
