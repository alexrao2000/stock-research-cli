#!/usr/bin/env python3
"""Serve a local browser dashboard backed by the stock research CLI rules."""
from __future__ import annotations

import json
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import stock_research_cli as core
from openai_features import generate_brief, load_local_env

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
HOST = "127.0.0.1"
PORT = 8765
def make_ai_brief(research: dict[str, Any]) -> str:
    """Explain displayed research without exposing the key to browser code."""
    return generate_brief(research, ROOT)


def analyze(portfolio_text: str, watchlist_text: str, snapshot_text: str, demo: bool = False) -> dict[str, Any]:
    warnings: list[str] = []
    with tempfile.TemporaryDirectory(prefix="stock-research-") as temp:
        temp_path = Path(temp)
        paths: dict[str, Path | None] = {}
        for key, contents in (("portfolio", portfolio_text), ("watchlist", watchlist_text), ("snapshot", snapshot_text)):
            path = temp_path / f"{key}.csv" if contents.strip() else None
            if path:
                path.write_text(contents, encoding="utf-8-sig")
            paths[key] = path
        positions, p_warnings = core.load_portfolio(paths["portfolio"])
        watchlist, w_warnings = core.load_watchlist(paths["watchlist"])
        snapshots, s_warnings = core.load_snapshot(paths["snapshot"])
        warnings.extend(p_warnings + w_warnings + s_warnings)

    total_value = 0.0
    position_rows: list[dict[str, Any]] = []
    values: list[float | None] = []
    for position in positions.values():
        snap = snapshots.get(position.ticker)
        value = position.shares * snap.price if snap and snap.price is not None else None
        pnl = (snap.price - position.average_cost) * position.shares if snap and snap.price is not None and position.average_cost is not None else None
        if value is not None:
            total_value += value
        values.append(value)
        position_rows.append({
            "ticker": position.ticker,
            "shares": position.shares,
            "averageCost": position.average_cost,
            "price": snap.price if snap else None,
            "value": value,
            "pnl": pnl,
        })
    complete_prices = bool(position_rows) and all(value is not None for value in values)
    for row in position_rows:
        row["weight"] = row["value"] / total_value * 100 if complete_prices and row["value"] is not None and total_value > 0 else None

    emerging, established = core.screen_candidates(snapshots)
    emerging_rows = [{
        "ticker": snap.ticker, "name": snap.name, "score": score,
        "revenueGrowth": snap.revenue_growth_pct,
        "volatility": snap.volatility_90d_pct,
        "highVolatility": snap.volatility_90d_pct is not None and snap.volatility_90d_pct >= 45,
    } for snap, score in emerging[:5]]
    established_rows = [{
        "ticker": snap.ticker, "name": snap.name,
        "volatility": snap.volatility_90d_pct,
        "fcfYield": snap.fcf_yield_pct,
        "debtEbitda": snap.net_debt_ebitda,
    } for snap in established[:5]]

    review_rows = []
    for ticker in dict.fromkeys([*positions.keys(), *watchlist.keys()]):
        status, reason = core.review_signal(snapshots.get(ticker))
        review_rows.append({"ticker": ticker, "status": status, "reason": reason})

    sources = sorted({snap.source for snap in snapshots.values()})
    dates = sorted({snap.as_of for snap in snapshots.values()})
    watch_rows = [{
        "ticker": ticker,
        "note": note,
        "price": snapshots[ticker].price if ticker in snapshots else None,
    } for ticker, note in watchlist.items()]
    return {
        "demo": demo,
        "source": "; ".join(sources) if sources else ("Synthetic demo snapshot" if demo else "No snapshot loaded"),
        "asOf": "; ".join(dates) if dates else ("DEMO" if demo else "—"),
        "sourceLabel": "SYNTHETIC DEMO DATA — fictional companies and metrics" if demo or any(d.upper() in {"DEMO", "SIMULATED", "ILLUSTRATIVE"} for d in dates) else "USER-SUPPLIED SNAPSHOT — verify source and date",
        "totalValue": total_value,
        "positions": position_rows,
        "completePrices": complete_prices,
        "watchlist": watch_rows,
        "emerging": emerging_rows,
        "established": established_rows,
        "reviews": review_rows,
        "warnings": warnings[:12],
        "snapshotCount": len(snapshots),
        "positionCount": len(positions),
        "watchCount": len(watchlist),
    }


def demo_payload() -> dict[str, Any]:
    examples = ROOT / "examples"
    return analyze(
        (examples / "portfolio.csv").read_text(encoding="utf-8-sig"),
        (examples / "watchlist.csv").read_text(encoding="utf-8-sig"),
        (examples / "snapshot_demo.csv").read_text(encoding="utf-8-sig"),
        demo=True,
    )


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/api/demo":
            self._json(200, demo_payload())
            return
        if self.path in ("/", "/index.html", "/web", "/web/"):
            body = (WEB / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if self.path not in ("/api/analyze", "/api/brief"):
            self._json(404, {"error": "Not found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            limit = 100_000 if self.path == "/api/brief" else 2_000_000
            if size > limit:
                if self.path == "/api/brief":
                    self._json(413, {"error": "Research data exceeds the 100 KB limit."})
                    return
                self._json(413, {"error": "CSV uploads must be under 2 MB each."})
                return
            payload = json.loads(self.rfile.read(size) or b"{}")
            if self.path == "/api/brief":
                research = payload.get("research")
                if not isinstance(research, dict):
                    self._json(400, {"error": "Expected a research summary."})
                    return
                self._json(200, {"brief": make_ai_brief(research)})
                return
            result = analyze(
                str(payload.get("portfolio", "")),
                str(payload.get("watchlist", "")),
                str(payload.get("snapshot", "")),
            )
            self._json(200, result)
        except RuntimeError as exc:
            self._json(503, {"error": str(exc)})
        except (UnicodeDecodeError, json.JSONDecodeError, OSError, ValueError) as exc:
            self._json(400, {"error": str(exc)})

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")


if __name__ == "__main__":
    load_local_env(ROOT)
    print(f"Stock Research dashboard: http://{HOST}:{PORT}")
    print("Local-only server. Press Ctrl+C to stop.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
