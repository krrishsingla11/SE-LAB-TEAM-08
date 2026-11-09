"""Health monitor for TC-OPS-01 (OMH-NF-002, 99.5% uptime).

Pings GET /api/health on a fixed interval, writes every result to a CSV file and
prints the uptime percentage at the end. A ping counts as UP only if the HTTP
status is 200 and the JSON body says the database is "connected".

Examples:
    py tests/performance/health_monitor.py --interval 60 --duration 3600
    py tests/performance/health_monitor.py --interval 5 --count 20      (quick demo)
"""
import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


def ping(url, timeout):
    """Return (is_up, status_code, milliseconds, note)."""
    started = time.perf_counter()
    status, note, up = 0, "", False
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            status = response.status
            body = json.loads(response.read().decode() or "{}")
            up = status == 200 and body.get("database") == "connected"
            note = f"database={body.get('database')}"
    except urllib.error.HTTPError as exc:
        status, note = exc.code, "http error"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        note = f"{type(exc).__name__}: {exc}"
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    return up, status, elapsed_ms, note


def run(url, interval, total, timeout, output):
    rows, up_count = [], 0
    with open(output, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp_utc", "up", "status", "ms", "note"])
        for number in range(1, total + 1):
            up, status, millis, note = ping(url, timeout)
            up_count += up
            stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            writer.writerow([stamp, int(up), status, millis, note])
            handle.flush()
            print(f"{number}/{total} {stamp} {'UP' if up else 'DOWN'} {status} {millis} ms {note}")
            rows.append(up)
            if number < total:
                time.sleep(interval)
    uptime = 100.0 * up_count / total
    verdict = "PASS" if uptime >= 99.5 else "FAIL"
    print(f"\nPings: {total}  Up: {up_count}  Uptime: {uptime:.2f}%  (target 99.5%)  -> {verdict}")
    print(f"Results saved to {output}")
    return uptime


def main():
    parser = argparse.ArgumentParser(description="Ping /api/health and report uptime.")
    parser.add_argument("--url", default="http://localhost:5000/api/health")
    parser.add_argument("--interval", type=float, default=60, help="seconds between pings")
    parser.add_argument("--duration", type=float, help="total test time in seconds")
    parser.add_argument("--count", type=int, help="number of pings (instead of --duration)")
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--output", default="health_results.csv")
    args = parser.parse_args()

    total = args.count or max(1, int((args.duration or 600) // args.interval))
    run(args.url, args.interval, total, args.timeout, args.output)


if __name__ == "__main__":
    main()
