# proc-watchdog

Keep **any** long-running process alive on Linux — a trading bot, a scraper, an agent, a queue worker —
with a tiny watchdog that restarts it, records its health, and enforces a kill switch.

No systemd. No daemon. No dependencies. One bash script and a cron line.

```
*/15 * * * * /path/to/watchdog.sh
```

## Why not just `pgrep -f mybot`?

Because it is a landmine. `pgrep -f` matches the **full command line**, and your watchdog's own
invocation often contains the pattern you are searching for — so the script can match *itself*,
conclude "all good", or `pkill` its own shell. I hit exactly this bug and it silently disabled the
watchdog.

The fix in this repo scans `/proc` and requires **two independent facts**:

1. `/proc/<pid>/cmdline` contains your exact start command,
2. `/proc/<pid>/exe` resolves to the interpreter from **your** virtualenv.

```bash
find_proc() {
  for p in /proc/[0-9]*; do
    pid=${p#/proc/}
    [ -r "$p/cmdline" ] || continue
    cmd=$(tr '\0' ' ' < "$p/cmdline" 2>/dev/null) || continue
    case "$cmd" in
      *"myapp run --config"*)
        exe=$(readlink -f "$p/exe" 2>/dev/null)
        [ "$exe" = "$VENV_PY" ] && echo "$pid"
        ;;
    esac
  done
}
```

You can never match a stray system Python, a shell, or the watchdog itself.

## What you get

| file | purpose |
|---|---|
| `crypto_watchdog.sh` | restarts the process if dead, logs a health snapshot, enforces the risk rule, **silent unless it acts** |
| `monitor_pnl.py` | example health script (Freqtrade): polls the REST API, appends one line per run, exits `2` on drawdown ≥ 10% |

## Design rules this follows

- **Speak only when you act.** A watchdog that messages every 15 minutes gets muted — and a muted
  watchdog is worse than none.
- **One kill switch, in one place.** Your app's internal guards protect a request; the health script
  protects the *account*.
- **Idempotent.** Two runs must never start two copies — guaranteed by the two-condition check above.
- **Test it or you don't have it.** Kill the process, run the watchdog, confirm both the restart and the
  log line.

## Full setup (Freqtrade users)

The complete version — drop-in watchdog, P&L logger, backtest runner, dry-run config and the setup
guide — is packaged here: **[Freqtrade Self-Healing Starter Kit](https://tntofficial.gumroad.com/l/priklq)**.

## Further reading

- [Keep any long-running Python process alive on Linux for $0](https://dev.to/matteo_adorni_948bc601a06/keep-any-long-running-python-process-alive-on-linux-for-0-the-proc-watchdog-pattern-1c9)
- [Keep Freqtrade running 24/7: systemd vs a zero-dependency watchdog](https://dev.to/matteo_adorni_948bc601a06/keep-freqtrade-running-247-systemd-vs-a-zero-dependency-watchdog-2d44)

## License

MIT — see `LICENSE`.
