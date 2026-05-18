# pizza-day-trace

Forensic UTXO-graph trace of the 10,000 BTC that paid for two pizzas on **2010-05-22**.

Anchor transaction: [`a1075db55d416d3ca199f55b6084e2115b9345e16c5cf302fc80e9d5fbf5d48d`](https://mempool.space/tx/a1075db55d416d3ca199f55b6084e2115b9345e16c5cf302fc80e9d5fbf5d48d) (block 57043).

This repo is the engineering substrate behind the long-form article **[Tracing the Pizza Day bitcoins](https://max.nardit.com/articles/tracing-the-pizza-day-bitcoins)** at max.nardit.com, on what the words *"those specific bitcoins"* can and cannot mean.

## What it does

Starting from the famous 10,000-BTC output, it walks the descendant transaction graph in chain-topological order (block height, then in-block position) up to a **depth-5 horizon**, applying explicit pruning rules. For every traced UTXO it records: address, amount, creation block, spending block (if any), terminal classification (`still-unspent` / `cluster-absorbed` / `dust-pruned` / `depth-pruned`). Depth-pruned UTXOs get their next-hop status checked separately so the article can honestly state that the trace stopped at a horizon, not at an observed dormancy.

It also separately analyses:

- **Anchor input composition** — the 131 UTXOs Hanyecz swept to assemble exactly 10,000 BTC plus a 0.99 BTC fee, including their individual age at the moment of spending.
- **Recipient-address deposit history** — `17SkEw2md5avVNyYgj6RiXuQKNwkXaxFyQ` has 14 funded TXOs, only 1 spent. The other 13 are post-2010 dust deposits, several landing on May-22 anniversaries.
- **Depth-3 consolidation address** — `1PrwYMffhu1XJyVXs6Ba67NidGZVjbGHCq`, which received both pizza halves plus 18 other UTXOs in a single 11,022 BTC consolidation on 2010-07-07. The address has 4 lifetime transactions, all in May–July 2010, and a zero balance today.

## Methodology

See [METHODOLOGY.md](METHODOLOGY.md). The short version: there is no objective notion of "the same coins" in a UTXO system. We commit to one tracing rule (strict positional FIFO) and document every pruning decision.

In a *no-pruning* trace the underlying descendant transaction graph is identical under any taint convention — UTXO spends are chain facts. In this pipeline, however, pruning thresholds key off taint magnitude, so alternative conventions (poison, haircut) can change which branches the trace follows. Poison's inflation in particular can push outputs past the dust cutoff that the other two conventions leave below. On the Pizza-Day trace specifically the 1 BTC dust threshold is below every per-output tainted amount under every convention, so the visited set happens to coincide.

## Reproducibility

```bash
make setup    # python3 -m venv .venv + pip install
make all      # full pipeline: trace + anchor + jercos + analyze
make test     # run invariant tests
```

All blockchain calls are cached in `data/cache.sqlite` (gitignored). The trace records `chain_tip_at_trace_time` in `data/processed/headline-summary.json` so reruns at a different chain tip can be distinguished from the snapshot committed here. After the first network-bound run, every subsequent run is offline and deterministic.

## Outputs

| File | Contents |
|------|----------|
| `data/processed/utxo-tree.csv` | Every traced UTXO under the strict-FIFO convention: parents, depth, address, amount, taint, block timing, terminal status |
| `data/processed/anchor-inputs.csv` | The 131 inputs of the anchor tx with their originating block, age at spend, and whether the source was a direct coinbase |
| `data/processed/jercos-deposits.csv` | All 14 deposits to the recipient address (1 spent, 13 unspent post-2010 dust) |
| `data/processed/headline-summary.json` | Article-bound headline findings + frontier outspend status + consolidation address history |
| `data/processed/summary.json` | Raw trace summary including taint conservation check |
| `data/processed/anchor-summary.json` | Headline numbers from the anchor input analysis |
| `data/processed/jercos-summary.json` | Headline numbers from the recipient-address analysis |

## License

Data: CC0. Code: MIT.
