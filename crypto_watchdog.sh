#!/bin/bash
# Cryptobot watchdog (cron, no_agent).
# - restarts the Freqtrade dry-run bot if the process died
# - logs the P&L snapshot to logs/daily_pnl.txt on every run
# - SILENT on success; prints only when it restarts the bot or when the
#   global risk rule trips (drawdown >= 10% -> stop bot + analyse)
#
# Process detection is done by scanning /proc and requiring BOTH the
# freqtrade trade cmdline AND an executable inside the freqtrade venv.
# Using plain `pkill -f freqtrade` is unsafe: it also matches the shell
# that invokes this script (self-kill, seen 2026-09-25).
set -u
BASE=/home/kali/freqtrade
VENV_PY=$(readlink -f "$BASE/.venv/bin/python")
cd "$BASE" || { echo "crypto-watchdog: cannot cd $BASE"; exit 1; }
PY=$BASE/.venv/bin/python
LOG=$BASE/logs/watchdog.log
ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

# Print the PIDs of the real bot processes (empty if none).
find_bot() {
  for p in /proc/[0-9]*; do
    pid=${p#/proc/}
    [ -r "$p/cmdline" ] || continue
    cmd=$(tr '\0' ' ' < "$p/cmdline" 2>/dev/null) || continue
    case "$cmd" in
      *"freqtrade trade --config"*)
        exe=$(readlink -f "$p/exe" 2>/dev/null)
        [ "$exe" = "$VENV_PY" ] && echo "$pid"
        ;;
    esac
  done
}

MSG=""
if [ -z "$(find_bot)" ]; then
  echo "$(ts) bot not running -> restarting" >> "$LOG"
  nohup "$BASE/.venv/bin/freqtrade" trade --config "$BASE/config.json" \
      --strategy SwingHighToSky --dry-run >> "$BASE/logs/trade_stdout.log" 2>&1 &
  sleep 30
  if [ -n "$(find_bot)" ]; then
    echo "$(ts) restart OK pid=$(find_bot | tr '\n' ' ')" >> "$LOG"
    MSG="🟡 crypto-bot: processo assente, riavviato a $(ts). Dry-run SwingHighToSky di nuovo attivo."
  else
    echo "$(ts) restart FAILED" >> "$LOG"
    echo "🔴 crypto-bot: processo morto e riavvio FALLITO ($(ts)). Ultime righe log:"
    tail -5 "$BASE/logs/trade_stdout.log"
    exit 1
  fi
fi

OUT=$("$PY" "$BASE/monitor_pnl.py" 2>&1)
RC=$?
if [ $RC -eq 2 ]; then
  echo "$OUT" >> "$LOG"
  echo "$(ts) DRAWDOWN LIMIT HIT -> stopping bot" >> "$LOG"
  for pid in $(find_bot); do kill "$pid" 2>/dev/null; done
  echo "🔴 crypto-bot: drawdown >= 10% del wallet. Bot FERMATO per la regola di rischio. Analisi richiesta."
  echo "$OUT"
  exit 2
elif [ $RC -eq 3 ]; then
  echo "$OUT" >> "$LOG"
  echo "🔴 crypto-bot: API locale non raggiungibile mentre il processo gira. $(ts)"
  echo "$OUT"
  exit 1
fi

echo "$OUT" >> "$LOG"
[ -n "$MSG" ] && echo "$MSG"
exit 0
