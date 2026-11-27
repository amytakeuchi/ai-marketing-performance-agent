# Manual baseline (TO FILL IN - not measured)

The BRD's success metric "reduction in investigation time vs a manual baseline" has **not** been measured: it needs a
human doing the work, and an AI assistant cannot time that honestly. Do this before you quote any time-saved figure.

## Protocol (30 minutes)
1. Pick the three benchmark questions below. Do **not** read the agent's answers first.
2. Answer each using only the warehouse (psql / SQL client / spreadsheet). Start a stopwatch per question.
3. Stop when you would be willing to send your conclusion to a marketing director. Record time and your conclusion.
4. Run the agent on the same questions (`make ask Q="..."`); record its latency (shown in the output) and whether its
   conclusion agrees with yours.
5. Be honest about the learning effect (you now know the data) and that you built the system.

| # | Question | Manual time | Manual conclusion | Agent latency | Agreement? |
|---|---|---|---|---|---|
| 1 | Why did Meta ROAS decline in October compared with September? | | | | |
| 2 | Where are users dropping off between ad click and purchase? | | | | |
| 3 | How should I allocate a $50,000 marketing budget? | | | | |

Report it as "n=1 analyst (the author), 3 questions", not as a general productivity claim.
