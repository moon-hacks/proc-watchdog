#!/usr/bin/env python3
"""Daily P&L logger for the Hermes Freqtrade dry-run instance.

Reads the local Freqtrade REST API and appends one line per run to
/home/kali/freqtrade/logs/daily_pnl.txt. Prints a short summary to stdout
and exits 2 when an abnormal drawdown is detected (> 10% of the wallet).
"""
import base64
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

BASE = "/home/kali/freqtrade"
CREDS = os.path.join(BASE, "api_creds.env")
LOG = os.path.join(BASE, "logs", "daily_pnl.txt")

DRAWDOWN_LIMIT = 10.0  # % of wallet -> hard stop per skill risk rules


def load_creds():
    env = {}
    with open(CREDS) as fh:
        for line in fh:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k] = v
    return env["FT_USER"], env["FT_PASS"], env.get("FT_URL", "http://127.0.0.1:8080")


def api(path, user, pw, url):
    req = urllib.request.Request(url + path)
    tok = base64.b64encode(f"{user}:{pw}".encode()).decode()
    req.add_header("Authorization", "Basic " + tok)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def main():
    user, pw, url = load_creds()
    try:
        profit = api("/api/v1/profit", user, pw, url)
        status = api("/api/v1/status", user, pw, url)
        balance = api("/api/v1/balance", user, pw, url)
    except Exception as exc:  # bot down / api unreachable
        msg = f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ} API UNREACHABLE: {exc}"
        with open(LOG, "a") as fh:
            fh.write(msg + "\n")
        print(msg)
        return 3

    total = profit.get("profit_closed_coin", 0.0) or 0.0
    pct = profit.get("profit_closed_percent", 0.0) or 0.0
    all_pct = profit.get("profit_all_percent", 0.0) or 0.0
    all_coin = profit.get("profit_all_coin", 0.0) or 0.0
    wins, losses = profit.get("winning_trades", 0), profit.get("losing_trades", 0)
    n = wins + losses
    wr = (100.0 * wins / n) if n else 0.0
    tot_bal = balance.get("total", 0.0)
    open_trades = len(status)
    best = profit.get("best_pair")
    worst = profit.get("worst_pair")

    line = (
        f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ} "
        f"wallet={tot_bal:.2f} closed_pnl={total:+.3f}USDT ({pct:+.2f}%) "
        f"all_pnl={all_coin:+.3f}USDT ({all_pct:+.2f}%) "
        f"trades={wins}W/{losses}L wr={wr:.1f}% "
        f"open={open_trades} best={best[0] if best else '-'} worst={worst[0] if worst else '-'}"
    )
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as fh:
        fh.write(line + "\n")
    print(line)

    # risk rule: drawdown > 10% of the dry-run wallet
    dd = -min(0.0, all_pct)
    if dd >= DRAWDOWN_LIMIT:
        print(f"ALERT: drawdown {dd:.2f}% >= {DRAWDOWN_LIMIT}% -> stop bot and analyse")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
