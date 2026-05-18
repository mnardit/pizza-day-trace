# Codex Review: `pizza-day-trace`

## A. Methodology Soundness

**CRITICAL** - The stated FIFO convention is not the convention implemented. `METHODOLOGY.md:13-20` describes FIFO assignment from tainted inputs to outputs, but `src/tracer.py:47-67` distributes `taint * take // val` for each input slice. That is proportional dilution inside each input, not pure FIFO over tainted satoshi positions. Worked example: one 10-sat input carrying 3 tainted sats, two 5-sat outputs. A strict FIFO-position model gives `[3, 0]`; the current function gives `[1, 2]`. This directly appears in `data/processed/utxo-tree.csv:7-8`: the 11,022 BTC UTXO with 10,000 BTC taint is split into about 4,990.01996007 and 5,009.98003993 BTC of taint, whereas strict FIFO with taint at the front of the input would give 5,500 and 4,500. Either rename the method as "input-order FIFO with per-input haircut" or change the algorithm.

**HIGH** - The pruning rules are defensible as article scope controls, but not as forensic conclusions. The 1 BTC cutoff in `METHODOLOGY.md:26` is a trace-budget threshold, not Bitcoin "dust"; it can hide meaningful fragmentation. The 100-input cluster rule in `METHODOLOGY.md:27` is a heuristic that can miss exchange/consolidation activity below 100 inputs and can collapse non-exchange batching or CoinJoin-like transactions above 100. The depth-5 cutoff in `METHODOLOGY.md:28` is a horizon, not an observed terminal state.

**HIGH** - `METHODOLOGY.md:57` over-claims that under other taint conventions "most descendants either disappear into clusters within 2-3 hops, or sit unspent forever." The current depth-5 output has no `cluster-absorbed` and no `still-unspent` terminal value: `data/processed/summary.json:8-14` says 10000.0 BTC is `depth-pruned`. That sentence is not supported by the current data.

**MEDIUM** - The cluster wording says "the receiving address is treated as a cluster" (`METHODOLOGY.md:27`), but the implementation does not identify or record a receiving address for cluster transactions. It terminates the tainted parent inputs and stores `cluster_input_count` only (`src/tracer.py:240-248`). Use "the spending transaction is treated as a cluster boundary" unless you actually classify outputs.

**MEDIUM** - The methodology should explicitly contrast at least three conventions: strict FIFO/value-order taint, poison taint, and haircut/proportional taint. Given the current code, the comparison is especially important because the implementation is already a hybrid of input-order FIFO and haircut. It would also be worth stating that change-output heuristics are deliberately not used.

## B. Algorithmic Correctness

**CRITICAL** - The topological-order guarantee is overstated. The module docstring says spending transactions are processed in `(block_height, tx_position)` order (`src/tracer.py:8-15`), but the code sorts by `(block_height, txid)` (`src/tracer.py:160-161`). Bitcoin permits same-block parent/child spends. A bad case is: tx B is already pending because it spends one known tainted input, while tx A in the same block creates another tainted input that B also spends. If txid ordering processes B before A, B is marked processed with incomplete taint and will never be revisited.

**HIGH** - `processed_txs` is set before a transaction is fetched and matched (`src/tracer.py:211-238`). That makes incomplete processing unrecoverable. This is the concrete answer to the "earlier-tainted UTXO already processed" question: if a transaction is processed before all tainted inputs to that transaction are visible, later-discovered taint is silently ignored because `spend_txid in self.processed_txs` blocks reprocessing in `_collect_pending_spends` (`src/tracer.py:199-202`).

**HIGH** - Taint assigned to fees can disappear without a terminal bucket. `fifo_distribute` only walks explicit outputs (`src/tracer.py:57-71`). If a transaction's implicit fee consumes a tainted portion under the chosen convention, the remainder stays in local `remaining` and is dropped. The summary conservation check (`src/tracer.py:291-310`) would fall below 10,000 BTC, but there is no warning or "fee/miner" terminal. This may not affect the committed depth-5 CSV if those descendant transactions have no tainted fee loss, but the algorithm does not preserve invariants generally.

**MEDIUM** - `_collect_pending_spends` should terminate on a finite confirmed graph with a static cache: nodes become terminal, spent, or lead to a processed transaction (`src/tracer.py:177-209`). The caveat is correctness, not termination: stale cache entries can mark a UTXO `still-unspent` forever (`src/tracer.py:196-198`), and unconfirmed/missing block heights are collapsed to `0` (`src/tracer.py:203-207`).

**MEDIUM** - `_add_or_update_node` uses minimum depth on update (`src/tracer.py:120-121`), while `_process_tx` defines child depth as `max(parent_depths) + 1` (`src/tracer.py:260-261`). In a correct UTXO trace, an output should be created once with all parent taint visible. If this update path is reached because of an ordering bug, taking `min` can understate depth and delay pruning.

**LOW** - Satoshi integers are the right representation, and the `<` dust comparison is consistent with `METHODOLOGY.md:26`: exactly 1 BTC is traced, below 1 BTC is pruned (`src/tracer.py:185-190`). The CLI converts `--dust-btc` through float multiplication (`src/run_trace.py:17-31`), which is fine for the default `1.0` but brittle for decimal thresholds. Use integer sats or `Decimal` if threshold sensitivity runs are added.

## C. Findings Quality

**MEDIUM** - `headline_findings[0]`: "The famous Pizza Day transaction had a 0.99 BTC fee, almost never mentioned in coverage." The fee is supported. `data/processed/anchor-summary.json:6` gives input value 10000.99 BTC, and the anchor output is 10000 BTC, so the fee is exactly 99,000,000 sats. An external explorer spot check also reports the same fee: https://learnmeabitcoin.com/explorer/tx/a1075db55d416d3ca199f55b6084e2115b9345e16c5cf302fc80e9d5fbf5d48d. The phrase "almost never mentioned" is not proven by `analysis/prior-art.md`; it is a plausible observation from a sample, not a measured literature claim. Safer: "rarely foregrounded in the coverage surveyed here."

**MEDIUM** - `headline_findings[1]`: "Of 131 inputs, 111 were 0.01 BTC dust UTXOs." The count is supported by `data/processed/anchor-summary.json:2-7` and `data/processed/anchor-inputs.csv`. The wording is not ideal: 0.01 BTC is not Bitcoin dust in the policy sense. Call them "0.01 BTC crumbs" or "small 0.01 BTC UTXOs."

**LOW** - `headline_findings[2]`: "Largest single input was 3753.88 BTC, only 5.2 days old." Supported by `data/processed/anchor-summary.json:17-18`. It appears novel relative to `analysis/prior-art.md:55-62`. Keep it, but avoid implying the input was mined directly; `n_inputs_coinbase_direct` is zero (`data/processed/anchor-summary.json:3`).

**MEDIUM** - `headline_findings[3]`: "All 10,000 BTC consolidated into one UTXO at depth 3, mixed with 1,022 BTC of clean coins..." Supported by `data/processed/utxo-tree.csv:6`: depth 3, amount 11,022 BTC, taint 10,000 BTC, address `1PrwYMffhu1XJyVXs6Ba67NidGZVjbGHCq`. The caveat is language: "clean coins" means "not pizza-tainted under this convention," not objectively clean.

**CRITICAL** - `headline_findings[4]`: "At depth 5, all 10,000 BTC of pizza taint is still alive - none dormant, none in a cluster, all still moving." This is the weakest publish-facing claim. The data only shows that all 10,000 BTC is in the depth-limited frontier: `data/processed/headline-summary.json:15-23` and `data/processed/utxo-tree.csv:9-11`. Those rows have blank spend fields because the tracer stops before checking their outspends. "Still alive" and "all still moving" are unsupported. Reframe as: "At the depth-5 horizon, the convention still assigns all 10,000 BTC of taint to three unclassified frontier outputs; the trace intentionally stops there."

**MEDIUM** - `headline_findings[5]`: "The recipient address ... received 14 times in its life but spent only once..." Supported by `data/processed/jercos-summary.json:2-11` and `data/processed/jercos-tributes.csv:1-15`. "Tributes" is interpretive. Use "apparent tributes" or "post-2010 dust deposits" unless sender intent is documented.

**HIGH** - `headline_findings[6]`: "Tributes sent on May 22 anniversaries (2023, 2024) are exactly 546 sats - the Bitcoin dust limit. The smallest possible memorial." The data supports the narrow pattern: the two non-anchor May 22 deposits are 546 sats (`data/processed/jercos-tributes.csv:8-9`), and six non-anchor deposits total are 546 sats (`data/processed/headline-summary.json:42-52`). But n=2 is thin for an anniversary pattern. Also, 546 sats is a common/default P2PKH dust threshold under Bitcoin Core relay policy, not a consensus "Bitcoin dust limit"; dust thresholds vary by script type and policy. The Lightning BOLTs dust-limit discussion states this distinction explicitly: https://github.com/lightning/bolts/blob/master/03-transactions.md#dust-limits. "Smallest possible memorial" is too strong.

## D. Story Arc & Gaps

**Strongest article version:** make the article a case study in the named-coin fallacy. Start with "specific bitcoins" not existing as persistent objects, choose a convention out loud, then show what the convention reveals: the 10,000 BTC output split immediately, reconverged into a single 11,022 BTC UTXO at depth 3, then remained fully assigned to an unclassified depth-5 frontier under the project horizon. The strongest sidebars are the 131-input construction, the exact 0.99 BTC fee, the prior-art correction that these were 131 inputs from one address rather than 131 addresses, and the recipient address's later dust/memorial history.

**Metrics worth adding before publication:** sensitivity runs for dust thresholds and cluster thresholds; a strict FIFO vs haircut vs poison comparison for the first five hops; explicit fee accounting per descendant transaction; current outspend status for the three depth-5 frontier outputs without recursively tracing them; a table of arbitrary convention decisions; and a chain-tip/cache timestamp so "today" claims are reproducible.

**Visualization angle:** use a compact Sankey or UTXO DAG with edge widths as BTC amount and a separate color/intensity for taint amount. The consolidation node at depth 3 is the visual center. The depth-5 frontier should be labeled "trace horizon," not "still moving."

**Weakest claim to drop:** the current `headline_findings[4]` present-tense "still alive / all still moving" claim. The second weakest is "smallest possible memorial" in `headline_findings[6]`.

## E. Code Quality & Repo Polish

**HIGH** - The reproducibility instructions are incomplete. `README.md:24-29` says `make trace`, `make analyze`, `make report`, but `Makefile:1-23` has no `report` target, and `make analyze` requires `anchor-summary.json` and `jercos-summary.json` from `make anchor` and `make jercos` (`src/run_analyze.py:19-25`). A clean clone following the README will fail unless committed processed JSONs are already present.

**HIGH** - The reproducibility claim is too broad for the jercos analysis. `README.md:32` says the trace is offline-reproducible after the first run, but `data/cache.sqlite` is not tracked, and the recipient address can receive new deposits over time. A fresh run in 2027 may produce different `jercos-tributes.csv` and `headline-summary.json` unless the analysis is pinned to a block height or the cache snapshot is published.

**MEDIUM** - `README.md:11` says the trace walks "breadth-first," but the current implementation is topological. The same line says terminal classification includes "still-dormant," but the code emits `still-unspent` (`src/tracer.py:40-44`).

**MEDIUM** - `README.md:39` lists `data/processed/wake-events.csv`, but that file is not produced by the code or present in the tracked file list. If wake events are part of the article, they need an implementation; otherwise remove the promise.

**MEDIUM** - `METHODOLOGY.md:45-47` says raw tx JSON is stored under `data/raw/tx/<txid>.json` and that Blockchair cross-checks are performed. `src/explorer.py:38-75` only writes SQLite cache rows, and there is no cross-check script. Either add the machinery or soften the documentation.

**LOW** - `src/run_jercos.py:102-107` defines `pizza_year_dust` with a broken predicate (`o["date_utc"].endswith` is a method object) and never uses the variable. It is harmless dead code, but it will stand out to a careful reader.

**LOW** - `src/run_analyze.py:63` computes fee in floating point, which produces `0.9899999999997817` in `data/processed/headline-summary.json:7`. Compute fee in sats and format to BTC only for display.

**LOW** - `data/processed/jercos-tributes.csv` contains 14 deposits including the anchor transaction (`data/processed/jercos-tributes.csv:1-2`), while `README.md:41` describes it as "the 13 unspent tributes." Either rename the file as deposits or exclude the anchor from the CSV.

## F. Anything Else Worth Flagging

**HIGH** - Add tests before publishing the repo as an engineering substrate. Minimum fixtures: pure FIFO vs current proportional example, fee-taint accounting, reconvergence into one tx, same-block parent/child ordering, depth pruning before outspend lookup, and the current committed trace conservation.

**MEDIUM** - The prior-art correction about "131 input addresses" is one of the best forensic honesty beats (`analysis/prior-art.md:19-21`). Make it quiet but explicit: 131 inputs, one sending address, zero direct coinbase inputs in this decomposition.

**MEDIUM** - The article should distinguish "chain-verifiable" from "intent-inferred" in the jercos section. The address facts are verifiable; "tribute" and "memorial" are plausible labels inferred from timing and amounts.

**LOW** - Consider publishing the exact command transcript or Make target that regenerates every processed artifact in order: `trace`, `anchor`, `jercos`, `analyze`. Right now the repo feels close to reproducible, but the top-level workflow does not actually encode the full pipeline.

## Verdict

**Ship-with-fixes, not as-is.** The concept is strong and the data has several publishable findings, especially the fee, input composition, prior-art correction, depth-3 consolidation, and recipient-address dust history. But the article should not ship until the taint convention is either corrected or renamed, the depth-5 headline is rewritten, and the reproducibility workflow matches the README.
