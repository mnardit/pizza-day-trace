# Codex review v2 — verification pass

You reviewed this repo earlier; the prior report is at `analysis/codex-review.md`.
The author has applied a round of fixes. Verify the fixes landed correctly, and
look for any new issues — including issues you previously missed.

**Do not modify any files.** Produce a written critique only.

## Context: what was changed since your last review

Read `git log --oneline` to confirm. Summary of the second commit:

- `fifo_distribute` rewritten as strict positional FIFO (tainted portion of each input consumed first, then the clean portion). Tests added.
- `_collect_pending_spends` / `_process_tx` now order spending txs by `(block_height, in-block position)` via a new `Explorer.tx_position_in_block` helper. The `processed_txs` short-circuit was removed.
- All depth-pruned UTXOs now get their next-hop outspend status checked in `run_analyze.py` and reported in `data/processed/headline-summary.json` under `depth_horizon_frontier`.
- `data/processed/headline-summary.json` records `chain_tip_at_trace_time` and the strict-FIFO convention name.
- Headline wording softened per your previous review.
- `METHODOLOGY.md` rewritten to describe strict positional FIFO with explicit contrast to poison and haircut; pruning rules reframed as trace-budget thresholds.
- `README.md` rewritten: a single `make all` runs the full pipeline; `make test` runs invariant tests; reproducibility caveats spelled out.
- Renamed `jercos-tributes.csv` → `jercos-deposits.csv`. Dead code in `run_jercos.py` removed.
- Added a new analysis layer: the depth-3 consolidation address `1PrwYMffhu1XJyVXs6Ba67NidGZVjbGHCq` now has its full lifetime history pulled into `headline-summary.json`. Finding: 4 lifetime txs in May–July 2010, zero balance today.
- Added `tests/test_fifo.py` and `tests/test_trace_invariants.py` (13 tests, all passing).

## What to verify

### A. Did the prior review's CRITICAL items actually get fixed?

For each CRITICAL from the previous report, read the relevant file/lines and confirm the fix is real.

1. Strict FIFO vs haircut — check `src/tracer.py:fifo_distribute` and the FIFO tests. Run the worked case mentally.
2. Topological order by `(block, position)` — check `src/tracer.py:_collect_pending_spends`, `src/tracer.py:trace` sort key, and `src/explorer.py:tx_position_in_block`. Is the position resolution correct for a same-block parent/child?
3. Headline #4 reframe — check `data/processed/headline-summary.json:headline_findings` and the new `depth_horizon_frontier` block.

### B. Did the HIGH items get adequately addressed?

Run the same check against your earlier HIGH findings. Specifically:
- Pruning rules now framed as trace-budget thresholds (not forensic terminals)
- "Almost never mentioned" softened
- "Smallest possible memorial" softened
- "Tributes" → "deposits"
- `processed_txs` blocking issue resolved
- Fee-taint loss: is taint conservation now provable, or just empirically observed on this dataset?
- README/Makefile reproducibility: does `make all` from a clean clone actually reproduce all artifacts?
- Reproducibility pinned to chain tip (does `headline-summary.json` actually carry it?)

### C. New issues introduced by the fixes

Critique the fixes themselves:
- The new strict-FIFO implementation — any edge cases (zero-value inputs, fee outputs, OP_RETURN, P2PK without address)?
- The new `_add_or_update_node` path that does `taint_sats += taint_to_add` on revisit — is it still reachable now that `processed_txs` is gone? If so, when?
- `tx_position_in_block` issues `block_txids` calls — what if the txid isn't in that block (reorg, mempool drift)? The fallback returns `10**9` — does that hide bugs?
- Tests cover a few cases but: do they catch poison-taint regressions? Do they catch a same-block parent/child reordering bug?

### D. Findings quality on the new headline set

Re-judge each of the 8 headlines in `data/processed/headline-summary.json:headline_findings`. For each: supported / unsupported / novel / restated / over-claimed. Be especially honest about:
- The 45-day dormancy framing — is it actually supported, or is this artefact of the FIFO convention?
- "One-off transit point, not an exchange wallet" — supported by the address's lifetime stats?
- "Spent-beyond-horizon" framing for the depth-5 frontier — accurate?

### E. New angles the fresh data opens

The consolidation address now has lifetime history attached. What story angles does that open that we are still NOT capturing? (e.g. counterparties on the other 3 txs, the 250 BTC round-trip on 2010-05-22 19:13 → 19:28.) Suggest 1–3 concrete additional analyses with low cost.

### F. Final verdict

Update your previous verdict (ship / ship-with-fixes / rework). Is the concept publishable now? If not, what's the *minimum* remaining set of must-fix items before publish?

## Output

Markdown report saved to `analysis/codex-review-v2.md`. Sections matching A–F.
Severity markers as before: CRITICAL / HIGH / MEDIUM / LOW. Quote file paths and
line numbers when calling out code. End with the updated verdict in one line.
