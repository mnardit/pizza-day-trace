# Codex review request: pizza-day-trace

You are reviewing a research project that will become the engineering substrate
behind a long-form article on max.nardit.com about the famous Bitcoin Pizza Day
transaction (10,000 BTC for two Papa John's pizzas, 2010-05-22). The author's
positioning is **researcher / systems-engineer**, so the bar is forensic honesty
and defensible methodology, not crypto-influencer narrative.

**Do not modify any files.** Produce a written critique only.

## Read these files first (in this order)

1. `README.md` — what the project does
2. `METHODOLOGY.md` — the FIFO-taint forensic methodology
3. `analysis/prior-art.md` — what existing publications already cover
4. `src/explorer.py` — mempool.space client + SQLite cache
5. `src/tracer.py` — the topological UTXO tracer
6. `src/run_anchor.py` — anchor-tx 131-input composition
7. `src/run_jercos.py` — recipient address memorial-dust analysis
8. `src/run_analyze.py` — headline summary aggregation
9. `data/processed/headline-summary.json` — the article-bound findings
10. `data/processed/utxo-tree.csv` — the depth-5 trace output
11. `data/processed/anchor-inputs.csv` — 131 inputs decomposed
12. `data/processed/jercos-tributes.csv` — 14 deposits to recipient address

## What to critique

### A. Methodology soundness
- Is the FIFO-taint convention well-defined and consistently applied?
- Are the pruning rules (1 BTC dust, 100-input cluster threshold, depth 5) defensible? Where might they break the analysis?
- Are we honest about what we cannot prove? Where do we still over-claim?
- What well-known alternative taint conventions (poison, haircut) should we explicitly contrast against?

### B. Algorithmic correctness
- Read `src/tracer.py` carefully. The earlier BFS-by-depth version had a reconvergence double-counting bug; the current version uses topological ordering by block_height. Does it preserve taint invariants under all reconvergence patterns? Any edge cases that would silently miscount?
- `fifo_distribute` — verify the math against a worked example.
- Is `_collect_pending_spends` guaranteed to terminate?
- What happens if a tainted UTXO is spent in a tx whose other inputs include an EARLIER-tainted UTXO that was already processed? Is that case handled?
- Are there off-by-one or precision issues with satoshi-integer FIFO?

### C. Findings quality
The headline findings in `data/processed/headline-summary.json` will appear in the article. For each, judge:
- Is it actually supported by the data?
- Is it novel vs. the prior-art mapped in `analysis/prior-art.md`?
- Is the framing forensically honest, or sneaks in narrative spin?

Specifically interrogate these:
1. "The famous Pizza Day transaction had a 0.99 BTC fee, almost never mentioned" — verify against the data + verify the "almost never mentioned" claim is defensible.
2. "All 10K BTC consolidated into one UTXO at depth 3" — verify from `utxo-tree.csv`.
3. "At depth 5, all 10,000 BTC of pizza taint is still alive" — what does this mean given the depth-5 truncation? Are we hiding something?
4. "May 22 tributes are exactly 546 sats, the Bitcoin dust limit" — is this a real pattern (n=2 is thin) or sample-size theater?

### D. Story arc & gaps
The chosen arc is **forensic honesty** — opening with "specific bitcoins don't really exist in UTXO" and walking through what one defensible convention reveals. Given the data we have, what's the strongest version of this article we can write? What metrics or angles are we currently NOT capturing that the data would support? What's the weakest claim that should be dropped?

### E. Code quality & repo polish
- Are there bugs, dead code, unclear comments, or naming problems?
- Is the repo's reproducibility claim (clone → make trace → identical CSVs) actually true given the cache?
- Anything in the code that would embarrass a careful reader?

### F. Anything else worth flagging
Surprise us. If you see something we missed — an obvious analysis, a sanity check, a sharper framing, a better visualization choice — say so.

## Output format

A Markdown report saved to `analysis/codex-review.md` with sections matching A–F.
Be specific. Quote file paths + line numbers when calling out code issues. Quote
JSON keys when calling out finding issues. Mark severity: **CRITICAL** (publish
would mislead readers), **HIGH** (significant correctness or framing issue),
**MEDIUM** (worth fixing before publishing), **LOW** (polish). End with a
short verdict: should this concept ship as-is, ship-with-fixes, or be reworked.

You have the full repo. Take whatever time you need.
