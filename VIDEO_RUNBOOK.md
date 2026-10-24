# Live video runbook

Plan for a 2–3 minute live walkthrough. Use the fictional demo so no personal portfolio data appears on screen.

## One-time setup

Run these commands in Terminal before recording:

```sh
cd /Users/alexr/stock-research-cli
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Confirm that `.env` contains `OPENAI_API_KEY` without opening or showing the file during the recording. The key is ignored by Git. The AI brief needs an internet connection and may use paid OpenAI API credits.

## Live CLI recording

1. Press **Shift + Command + 5**, choose the Terminal window or screen area, select your microphone in **Options**, then start recording.
2. In Terminal, run these commands in order:

   ```sh
   cd /Users/alexr/stock-research-cli
   .venv/bin/python stock_research_cli.py --demo --ai-brief
   ```

3. Let the command finish while recording. It makes one AI request using fictional demo data. Do not open or show `.env`.
4. Use this short narration while the output appears:

   > “This is Stock Research CLI, a read-only stock research tool. These companies and numbers are fictional. The portfolio and watchlist are reviewed against the supplied snapshot; the screens show their rules, and the buy-review and sell-review labels are prompts to verify evidence. With the optional AI brief flag, a summary of the supplied data is sent to OpenAI for an explanation. It does not fetch live prices or place trades.”

5. Scroll to the AI brief and point out the snapshot context, concentration, risks, and questions it raises. Stop recording when the brief finishes.

For another run without an AI request, use `.venv/bin/python stock_research_cli.py --demo`.

## Browser dashboard walkthrough (optional)

1. Press **Shift + Command + 5**. Choose to record the browser window or selected screen area. Under **Options**, select the microphone you want. Start recording.
2. Open Terminal and run these commands in order:

   ```sh
   cd /Users/alexr/stock-research-cli
   .venv/bin/python web_app.py
   ```

   Leave this Terminal window running.

3. In the browser, open `http://127.0.0.1:8765`. Click **Load fictional demo** so the visible data is clearly labeled synthetic.
4. Walk through the dashboard and say:

   > “This is Northstar, a read-only stock research dashboard. It reviews a portfolio and watchlist against a dated snapshot. The demo data is fictional.”

5. Point out the portfolio value and positions, then the emerging-growth and established-company screens. Say:

   > “The screens use visible metrics and rules to surface names for review. They don’t use a live feed or place trades.”

6. In **Opportunity review**, show the rule-based flags. Explain that “BUY REVIEW” and “SELL REVIEW” are investigation prompts, not trade instructions.
7. Click **Generate AI brief** and wait for the response. Say:

   > “The AI brief summarizes only the snapshot shown here. This click sends the displayed fictional demo summary to OpenAI; the API key stays on the local server. It doesn’t fetch live prices or make a buy-or-sell decision.”

8. End with:

   > “You can load your own CSVs for local rule-based analysis. Verify the source and date of any snapshot before relying on it.”

9. Stop the screen recording. Return to Terminal and press **Control + C** to stop the dashboard.

## If the brief does not load

Check that the virtual environment was created and `requirements.txt` installed, that `.env` contains a valid API key, and that the computer is online. Restart the dashboard after changing `.env`. Never show or paste the key into the recording.
