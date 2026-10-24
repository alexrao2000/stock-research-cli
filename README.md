# Stock Research CLI

A headless, read-only command-line program for reviewing a portfolio and watchlist against a dated market snapshot supplied by the user. It has no network feed, broker connection, or trade execution. It never fills missing data with guesses.

## Browser dashboard

One-time setup for the dashboard and optional AI features (the standard CLI analysis remains offline):

```sh
cd /Users/alexr/stock-research-cli
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Start the dashboard with `.venv/bin/python web_app.py`, then open `http://127.0.0.1:8765` in a browser. The page starts with clearly labeled fictional sample data. Use **Load your CSVs** to analyze portfolio, watchlist, and snapshot files locally. The server binds only to `127.0.0.1`; it does not expose a public service. Press Ctrl+C to stop it.

### Optional OpenAI research brief

The dashboard includes **Generate AI brief**. It sends the displayed research summary to OpenAI only after you click the button. The summary can include ticker symbols, shares, average costs, snapshot prices and metrics, and rule-based review flags. The API key stays on the Python server and is never sent to the browser. API use may incur charges. The brief uses only the supplied snapshot, does not fetch live market data, and is not a buy/sell recommendation.

Set `OPENAI_API_KEY` in the project `.env` file. `.env` is excluded from Git. Optionally set `OPENAI_MODEL`; the default is `gpt-5.5`. Restart `web_app.py` after changing `.env`. The dashboard uses certifi's CA bundle for verified HTTPS connections. Without a key, the rest of the dashboard continues to work and the brief displays a setup error.

## Run the synthetic demo

```sh
python3 stock_research_cli.py --demo
```

The demo companies and every metric are fictional. The resulting `BUY REVIEW` and `SELL REVIEW` labels illustrate transparent rules; they are not real recommendations.

### Optional CLI AI brief

Use `--ai-brief` to request a second-pass explanation of supplied data:

```sh
.venv/bin/python stock_research_cli.py --demo --ai-brief
```

For CSVs, add `--ai-brief` to the normal `--portfolio`, `--watchlist`, and `--snapshot` command. This explicitly sends a compact summary of holdings, share counts, average costs, watchlist notes, snapshot metrics, and rule-based flags to OpenAI. The API key stays local in `.env`; normal CLI runs do not call OpenAI. The brief does not fetch live data or give buy/sell instructions. API usage may incur charges.

The updated [CLI AI demo video](media/Stock-Research-CLI-AI-Demo.mp4) uses fictional data and a disclosed AI-generated voice.

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

## Demo videos

- `media/Stock-Research-CLI-AI-Demo.mp4` is the updated terminal walkthrough. It uses fictional company data and clearly labels its AI-generated narration.
- `media/Stock-Research-Demo.mp4` is the earlier walkthrough.

To regenerate the new video, use the `.venv` setup above, run `scripts/render_openai_narration.py`, capture the output of `stock_research_cli.py --demo --ai-brief`, then pass that transcript to `scripts/render_cli_video.py`. Audio generation and the AI brief require internet access and may incur API charges; `ffmpeg` is needed to render the MP4.
