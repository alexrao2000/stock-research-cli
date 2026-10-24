# Stock Research CLI

A headless, read-only command-line program for reviewing a portfolio and watchlist against a dated market snapshot supplied by the user. It has no network feed, broker connection, or trade execution. It never fills missing data with guesses.

## Run the synthetic demo

```sh
python3 stock_research_cli.py --demo
```

The demo companies and every metric are fictional. The resulting `BUY REVIEW` and `SELL REVIEW` labels illustrate transparent rules; they are not real recommendations.

## Run with your CSVs

```sh
python3 stock_research_cli.py \
  --portfolio portfolio.csv \
  --watchlist watchlist.csv \
  --snapshot snapshot.csv
```

`portfolio.csv` requires `ticker,shares`; `average_cost` is optional. `watchlist.csv` requires `ticker`; `notes` is optional. The market snapshot must include `ticker,source,as_of`. Optional metrics are `name,price,change_20d_pct,relative_volume,revenue_growth_pct,fcf_yield_pct,net_debt_ebitda,volatility_90d_pct,market_cap_usd,upside_estimate_pct,thesis_risk`.

Sample input files are in `examples/`. Provide a trustworthy source and matching as-of date for every snapshot row. Old or unverified dates are flagged. Values and signals are only as reliable as the source snapshot you provide.

## Screening rules

- **Popular / emerging-growth screen:** a transparent attention proxy based on 20-day momentum and relative volume, combined with revenue growth. It is not a universal measure of popularity or company quality.
- **Established / lower-volatility screen:** market cap of at least $10B, 90-day volatility at most 25%, positive free-cash-flow yield, and net debt/EBITDA at most 2.0. This is a relative screen; an individual stock can still lose value.
- **Conditional buy review:** supplied upside estimate at least 15%, revenue growth at least 10%, non-negative FCF yield, and no thesis-risk flag.
- **Conditional sell review:** a thesis-risk flag or supplied upside estimate at or below -10%.

Thresholds are visible in the program and are screening heuristics. They do not account for taxes, cash needs, risk tolerance, or full valuation analysis. “BUY REVIEW” and “SELL REVIEW” mean investigate the inputs; they do not mean place an order.

## Voice demo

`media/Stock-Research-Demo.mp4` contains neural narration. The WAV scene clips are also included. To regenerate them, install `requirements-voice.txt` and run:

```sh
python3 -m pip install -r requirements-voice.txt
python3 scripts/render_narration.py
```

This step requires internet access and `ffmpeg`. It uses the community `edge-tts` client with the `en-US-AndrewMultilingualNeural` voice; the CLI itself remains fully local and has no network dependency. The voice service and client are external and can change availability.
