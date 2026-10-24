#!/usr/bin/env python3
"""Headless stock research CLI. Uses only user-supplied CSV data; never trades."""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from openai_features import generate_brief

TICKER_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")

@dataclass
class Position:
    ticker: str
    shares: float
    average_cost: Optional[float] = None

@dataclass
class Snapshot:
    ticker: str
    name: str
    price: Optional[float]
    change_20d_pct: Optional[float]
    relative_volume: Optional[float]
    revenue_growth_pct: Optional[float]
    fcf_yield_pct: Optional[float]
    net_debt_ebitda: Optional[float]
    volatility_90d_pct: Optional[float]
    market_cap_usd: Optional[float]
    upside_estimate_pct: Optional[float]
    thesis_risk: Optional[bool]
    source: str
    as_of: str


def normalize_ticker(value: str) -> str:
    ticker = (value or "").strip().upper()
    if not ticker or len(ticker) > 10 or any(ch not in TICKER_CHARS for ch in ticker):
        raise ValueError("ticker must be 1–10 characters: letters, numbers, dot, or hyphen")
    return ticker


def optional_number(value: str, field: str, line: int) -> Optional[float]:
    raw = (value or "").strip().replace(",", "")
    if not raw:
        return None
    try:
        number = float(raw.replace("%", ""))
    except ValueError as exc:
        raise ValueError(f"line {line}: {field} must be numeric") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"line {line}: {field} must be finite")
    return number


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError(f"{path}: CSV needs a header row")
        reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
        return [dict((k.strip().lower(), (v or "").strip()) for k, v in row.items() if k) for row in reader]


def load_portfolio(path: Optional[Path]) -> tuple[dict[str, Position], list[str]]:
    positions: dict[str, Position] = {}
    warnings: list[str] = []
    if path is None:
        return positions, warnings
    rows = read_rows(path)
    if not rows or not {"ticker", "shares"}.issubset(rows[0]):
        raise ValueError(f"{path}: expected columns ticker,shares and optional average_cost")
    for line, row in enumerate(rows, 2):
        if not row.get("ticker"):
            warnings.append(f"{path.name}:{line}: skipped blank ticker")
            continue
        try:
            ticker = normalize_ticker(row["ticker"])
            shares = optional_number(row.get("shares", ""), "shares", line)
            cost = optional_number(row.get("average_cost", ""), "average_cost", line)
            if shares is None or shares <= 0:
                raise ValueError(f"line {line}: shares must be greater than zero")
            if cost is not None and cost < 0:
                raise ValueError(f"line {line}: average_cost cannot be negative")
            if ticker in positions:
                prev = positions[ticker]
                if prev.average_cost != cost:
                    warnings.append(f"{path.name}:{line}: duplicate {ticker} has a different cost basis; kept separate row out of weighted cost calculation")
                    # Preserve a weighted average when both cost bases are known.
                    combined = prev.shares + shares
                    weighted = ((prev.average_cost * prev.shares + cost * shares) / combined) if prev.average_cost is not None and cost is not None else None
                    positions[ticker] = Position(ticker, combined, weighted)
                else:
                    positions[ticker] = Position(ticker, prev.shares + shares, cost)
            else:
                positions[ticker] = Position(ticker, shares, cost)
        except ValueError as exc:
            warnings.append(f"{path.name}:{line}: {exc}")
    return positions, warnings


def load_watchlist(path: Optional[Path]) -> tuple[dict[str, str], list[str]]:
    items: dict[str, str] = {}
    warnings: list[str] = []
    if path is None:
        return items, warnings
    rows = read_rows(path)
    if not rows or "ticker" not in rows[0]:
        raise ValueError(f"{path}: expected a ticker column and optional notes")
    for line, row in enumerate(rows, 2):
        if not row.get("ticker"):
            continue
        try:
            ticker = normalize_ticker(row["ticker"])
            note = row.get("notes", "")
            if ticker in items:
                warnings.append(f"{path.name}:{line}: duplicate {ticker} collapsed")
            else:
                items[ticker] = note
        except ValueError as exc:
            warnings.append(f"{path.name}:{line}: {exc}")
    return items, warnings


def load_snapshot(path: Optional[Path]) -> tuple[dict[str, Snapshot], list[str]]:
    data: dict[str, Snapshot] = {}
    warnings: list[str] = []
    if path is None:
        return data, warnings
    rows = read_rows(path)
    required = {"ticker", "source", "as_of"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"{path}: expected ticker,source,as_of plus optional market/fundamental metrics")
    for line, row in enumerate(rows, 2):
        if not row.get("ticker"):
            continue
        try:
            ticker = normalize_ticker(row["ticker"])
            if not row.get("source") or not row.get("as_of"):
                raise ValueError(f"line {line}: source and as_of are required")
            if ticker in data:
                raise ValueError(f"line {line}: duplicate snapshot for {ticker}")
            def num(key: str) -> Optional[float]:
                return optional_number(row.get(key, ""), key, line)
            price = num("price")
            if price is not None and price <= 0:
                raise ValueError(f"line {line}: price must be greater than zero")
            risk_raw = row.get("thesis_risk", "").lower()
            if risk_raw not in ("", "true", "false", "yes", "no", "1", "0"):
                raise ValueError(f"line {line}: thesis_risk must be true or false")
            thesis_risk = None if not risk_raw else risk_raw in ("true", "yes", "1")
            data[ticker] = Snapshot(
                ticker=ticker, name=row.get("name") or ticker, price=price,
                change_20d_pct=num("change_20d_pct"), relative_volume=num("relative_volume"),
                revenue_growth_pct=num("revenue_growth_pct"), fcf_yield_pct=num("fcf_yield_pct"),
                net_debt_ebitda=num("net_debt_ebitda"), volatility_90d_pct=num("volatility_90d_pct"),
                market_cap_usd=num("market_cap_usd"), upside_estimate_pct=num("upside_estimate_pct"),
                thesis_risk=thesis_risk, source=row["source"], as_of=row["as_of"])
        except ValueError as exc:
            warnings.append(f"{path.name}:{line}: {exc}")
    return data, warnings


def fmt_money(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"-${abs(value):,.2f}" if value < 0 else f"${value:,.2f}"

def fmt_pct(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:+.1f}%"

def fmt_num(value: Optional[float], suffix: str = "") -> str:
    return "—" if value is None else f"{value:.1f}{suffix}"

def attention_score(s: Snapshot) -> Optional[float]:
    if s.change_20d_pct is None or s.relative_volume is None:
        return None
    # Momentum and relative volume are attention signals, not a quality rating.
    return max(0.0, min(100.0, 50.0 + s.change_20d_pct * 1.25 + (s.relative_volume - 1.0) * 18.0))

def review_signal(s: Optional[Snapshot]) -> tuple[str, str]:
    if s is None:
        return "NO SNAPSHOT", "No market snapshot supplied for this ticker."
    if not snapshot_is_fresh(s.as_of):
        return "STALE / UNVERIFIED", "Refresh the snapshot date and source before reviewing this ticker."
    if s.thesis_risk is True:
        return "SELL REVIEW", "Snapshot flags thesis risk; review the evidence and position size."
    if s.upside_estimate_pct is not None and s.upside_estimate_pct <= -10:
        return "SELL REVIEW", "Snapshot estimate is materially negative; verify assumptions and source."
    if (s.upside_estimate_pct is not None and s.upside_estimate_pct >= 15
        and s.revenue_growth_pct is not None and s.revenue_growth_pct >= 10
        and s.fcf_yield_pct is not None and s.fcf_yield_pct >= 0
        and s.thesis_risk is False):
        return "BUY REVIEW", "Growth, cash-flow, and upside inputs meet the demo's review thresholds."
    if s.thesis_risk is None:
        return "INSUFFICIENT DATA", "No explicit thesis-risk flag; the buy-review rule cannot be satisfied."
    return "HOLD / WATCH", "Inputs do not meet the demo's buy or sell review thresholds."

def snapshot_is_fresh(as_of: str) -> bool:
    if as_of.upper() in {"DEMO", "SIMULATED", "ILLUSTRATIVE"}:
        return True
    try:
        d = date.fromisoformat(as_of[:10])
    except ValueError:
        return False
    age = (date.today() - d).days
    return 0 <= age <= 7

def source_age_label(as_of: str) -> str:
    if as_of.upper() in {"DEMO", "SIMULATED", "ILLUSTRATIVE"}:
        return "SYNTHETIC DEMO SNAPSHOT — not current market data"
    try:
        d = date.fromisoformat(as_of[:10])
    except ValueError:
        return f"Unverified as_of value: {as_of}"
    age = (date.today() - d).days
    if age < 0:
        return f"WARNING: snapshot date {as_of} is in the future"
    if age > 7:
        return f"STALE SNAPSHOT: {as_of} ({age} days old)"
    return f"Snapshot: {as_of} ({age} days old)"

def screen_candidates(snapshots: dict[str, Snapshot]) -> tuple[list[tuple[Snapshot, float]], list[Snapshot]]:
    emerging: list[tuple[Snapshot, float]] = []
    established: list[Snapshot] = []
    for s in snapshots.values():
        if not snapshot_is_fresh(s.as_of):
            continue
        score = attention_score(s)
        if (score is not None and score >= 65 and s.revenue_growth_pct is not None and s.revenue_growth_pct >= 15):
            emerging.append((s, score))
        # “Established/lower-volatility” is a relative screen, not a safety guarantee.
        if (s.market_cap_usd is not None and s.market_cap_usd >= 10_000_000_000
            and s.volatility_90d_pct is not None and s.volatility_90d_pct <= 25
            and s.fcf_yield_pct is not None and s.fcf_yield_pct > 0
            and s.net_debt_ebitda is not None and s.net_debt_ebitda <= 2.0):
            established.append(s)
    return sorted(emerging, key=lambda x: x[1], reverse=True), sorted(established, key=lambda x: (x.volatility_90d_pct or 999, x.ticker))

def line(text: str = "") -> None:
    print(text)

def report(positions: dict[str, Position], watchlist: dict[str, str], snapshots: dict[str, Snapshot], warnings: list[str], demo: bool) -> None:
    print("\nSTOCK RESEARCH CLI  |  READ-ONLY\n" + "=" * 72)
    if demo:
        line("DATA MODE : SYNTHETIC DEMO — all companies and metrics are fictional")
    elif snapshots:
        sources = sorted({s.source for s in snapshots.values()})
        dates = sorted({s.as_of for s in snapshots.values()})
        line("SOURCE    : " + "; ".join(sources))
        line("DATA DATE : " + "; ".join(dates))
        for d in dates:
            label = source_age_label(d)
            if "STALE" in label or "WARNING" in label or "Unverified" in label:
                line("DATA CHECK: " + label)
    else:
        line("DATA MODE : NO MARKET SNAPSHOT — prices and signals are not inferred")
    line("TRADING   : DISABLED — no broker connection or order execution")
    line("SCOPE     : research signals depend only on supplied snapshot values")

    total_value = 0.0
    known_positions: list[tuple[Position, Optional[Snapshot], Optional[float], Optional[float]]] = []
    for p in positions.values():
        s = snapshots.get(p.ticker)
        value = p.shares * s.price if s and s.price is not None else None
        pnl = (s.price - p.average_cost) * p.shares if s and s.price is not None and p.average_cost is not None else None
        if value is not None:
            total_value += value
        known_positions.append((p, s, value, pnl))
    complete_prices = bool(known_positions) and all(value is not None for _, _, value, _ in known_positions)
    line("\nPORTFOLIO")
    if known_positions:
        line(f"{'TICKER':<9}{'SHARES':>10}{'PRICE':>13}{'VALUE':>14}{'WEIGHT':>10}{'P/L':>13}")
        for p, s, value, pnl in known_positions:
            weight = (value / total_value * 100) if complete_prices and value is not None and total_value > 0 else None
            line(f"{p.ticker:<9}{p.shares:>10.2f}{fmt_money(s.price if s else None):>13}{fmt_money(value):>14}{fmt_pct(weight):>10}{fmt_money(pnl):>13}")
        line(f"Estimated value of priced holdings: {fmt_money(total_value) if total_value else '—'}")
        if not complete_prices:
            line("Weights are omitted because one or more holdings lack supplied prices.")
        if any(p.average_cost is None for p in positions.values()):
            line("P/L is omitted when average cost was not supplied; fees, taxes, and cash are excluded.")
    else:
        line("No positions loaded. Use --portfolio portfolio.csv or --demo.")

    line("\nWATCHLIST")
    if watchlist:
        for ticker, note in watchlist.items():
            s = snapshots.get(ticker)
            price = fmt_money(s.price) if s else "—"
            line(f"{ticker:<9}{price:>13}   {note[:44]}")
    else:
        line("No watchlist loaded. Use --watchlist watchlist.csv or --demo.")

    emerging, established = screen_candidates(snapshots)
    line("\nPOPULAR / EMERGING-GROWTH SCREEN")
    line("Rule: attention proxy (20d momentum + relative volume) ≥65 plus revenue growth ≥15%.")
    line("It is not a broad popularity measure or proof of business quality.")
    if emerging:
        for s, score in emerging[:5]:
            risk = "  HIGH VOLATILITY" if s.volatility_90d_pct is not None and s.volatility_90d_pct >= 45 else ""
            line(f"{s.ticker:<8}{s.name[:22]:<23}attention {score:>4.0f}/100  rev {fmt_pct(s.revenue_growth_pct):>7}  90d vol {fmt_pct(s.volatility_90d_pct):>7}{risk}")
    else:
        line("No candidate meets the screen, or required fields are missing.")

    line("\nESTABLISHED / LOWER-VOLATILITY SCREEN")
    line("Rule: cap ≥$10B, 90d volatility ≤25%, positive FCF yield, net debt/EBITDA ≤2.0.")
    line("A relative screen only; individual stocks can lose value.")
    if established:
        for s in established[:5]:
            line(f"{s.ticker:<8}{s.name[:22]:<23}90d vol {fmt_pct(s.volatility_90d_pct):>7}  FCF yield {fmt_pct(s.fcf_yield_pct):>7}  debt/EBITDA {fmt_num(s.net_debt_ebitda):>5}")
    else:
        line("No candidate meets the screen, or required fields are missing.")

    line("\nCONDITIONAL OPPORTUNITY REVIEW")
    if positions or watchlist:
        for ticker in list(dict.fromkeys([*positions.keys(), *watchlist.keys()])):
            s = snapshots.get(ticker)
            status, reason = review_signal(s)
            line(f"{ticker:<8}{status:<15}{reason}")
    else:
        line("Load a portfolio or watchlist to see ticker-level review flags.")
    line("\nThese are transparent research flags, not personalized instructions to trade.")
    line("The CLI never submits orders. Confirm sources, dates, assumptions, taxes, and risk tolerance independently.")
    if warnings:
        line("\nINPUT WARNINGS")
        for warning in warnings[:8]:
            line("• " + warning)
        if len(warnings) > 8:
            line(f"• ...and {len(warnings) - 8} more")


def demo_paths() -> tuple[Path, Path, Path]:
    base = Path(__file__).resolve().parent / "examples"
    return base / "portfolio.csv", base / "watchlist.csv", base / "snapshot_demo.csv"


def ai_research_summary(
    positions: dict[str, Position],
    watchlist: dict[str, str],
    snapshots: dict[str, Snapshot],
    warnings: list[str],
    demo: bool,
) -> dict[str, object]:
    """Build the compact summary sent only when --ai-brief is requested."""
    values: list[Optional[float]] = []
    rows: list[dict[str, object]] = []
    total = 0.0
    for position in positions.values():
        snapshot = snapshots.get(position.ticker)
        value = position.shares * snapshot.price if snapshot and snapshot.price is not None else None
        pnl = ((snapshot.price - position.average_cost) * position.shares
               if snapshot and snapshot.price is not None and position.average_cost is not None else None)
        values.append(value)
        if value is not None:
            total += value
        rows.append({
            "ticker": position.ticker,
            "shares": position.shares,
            "averageCost": position.average_cost,
            "price": snapshot.price if snapshot else None,
            "value": value,
            "pnl": pnl,
        })
    if rows and all(value is not None for value in values) and total > 0:
        for row in rows:
            row["weight"] = row["value"] / total * 100 if row["value"] is not None else None

    emerging, established = screen_candidates(snapshots)
    reviews = []
    for ticker in dict.fromkeys([*positions, *watchlist]):
        status, reason = review_signal(snapshots.get(ticker))
        reviews.append({"ticker": ticker, "status": status, "reason": reason})
    sources = sorted({snapshot.source for snapshot in snapshots.values()})
    dates = sorted({snapshot.as_of for snapshot in snapshots.values()})
    return {
        "asOf": "; ".join(dates) if dates else ("DEMO" if demo else "—"),
        "source": "; ".join(sources) if sources else ("Synthetic demo snapshot" if demo else "—"),
        "sourceLabel": "SYNTHETIC DEMO DATA — fictional companies and metrics" if demo else "USER-SUPPLIED SNAPSHOT — verify source and date",
        "totalValue": total,
        "positions": rows,
        "watchlist": [{
            "ticker": ticker,
            "note": note,
            "price": snapshots[ticker].price if ticker in snapshots else None,
        } for ticker, note in watchlist.items()],
        "emerging": [{
            "ticker": snapshot.ticker,
            "name": snapshot.name,
            "score": score,
            "revenueGrowth": snapshot.revenue_growth_pct,
            "volatility": snapshot.volatility_90d_pct,
            "highVolatility": snapshot.volatility_90d_pct is not None and snapshot.volatility_90d_pct >= 45,
        } for snapshot, score in emerging[:5]],
        "established": [{
            "ticker": snapshot.ticker,
            "name": snapshot.name,
            "volatility": snapshot.volatility_90d_pct,
            "fcfYield": snapshot.fcf_yield_pct,
            "debtEbitda": snapshot.net_debt_ebitda,
        } for snapshot in established[:5]],
        "reviews": reviews,
        "warnings": warnings[:12],
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only stock research from user-supplied CSVs; no live feed or brokerage integration.")
    parser.add_argument("--portfolio", type=Path, help="CSV: ticker,shares,average_cost")
    parser.add_argument("--watchlist", type=Path, help="CSV: ticker,notes")
    parser.add_argument("--snapshot", type=Path, help="timestamped CSV with user-supplied prices and metrics")
    parser.add_argument("--demo", action="store_true", help="run a fictional offline sample with synthetic data")
    parser.add_argument(
        "--ai-brief", action="store_true",
        help="send the supplied research summary to OpenAI for an optional AI brief (requires OPENAI_API_KEY)",
    )
    args = parser.parse_args(argv)
    if args.demo and any([args.portfolio, args.watchlist, args.snapshot]):
        parser.error("--demo cannot be combined with file arguments")
    try:
        if args.demo:
            args.portfolio, args.watchlist, args.snapshot = demo_paths()
        positions, p_warnings = load_portfolio(args.portfolio)
        watchlist, w_warnings = load_watchlist(args.watchlist)
        snapshots, s_warnings = load_snapshot(args.snapshot)
        if not (args.portfolio or args.watchlist or args.snapshot):
            parser.error("provide --demo or at least one CSV input")
        warnings = p_warnings + w_warnings + s_warnings
        report(positions, watchlist, snapshots, warnings, args.demo)
        if args.ai_brief:
            print("\nAI RESEARCH BRIEF (OpenAI; supplied data only)")
            print("This sends the displayed research summary to OpenAI; no live prices are fetched.")
            summary = ai_research_summary(positions, watchlist, snapshots, warnings, args.demo)
            print(generate_brief(summary, Path(__file__).resolve().parent))
    except RuntimeError as exc:
        print(f"stock-research: AI brief error: {exc}", file=sys.stderr)
        return 3
    except (OSError, ValueError, csv.Error) as exc:
        print(f"stock-research: error: {exc}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
