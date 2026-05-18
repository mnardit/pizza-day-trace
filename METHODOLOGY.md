# Methodology

## The problem with "specific bitcoins"

Bitcoin uses an unspent-transaction-output (UTXO) model. A transaction consumes one or more existing UTXOs as inputs and creates new UTXOs as outputs. Outputs are not labelled by their origin: a transaction with two inputs of 5 BTC each and two outputs of 4 BTC and 6 BTC has no canonical mapping from input to output. The 6 BTC output is "from" both inputs in equal measure.

This is not a bug. The UTXO model is deliberately fungible. But it means the question *"where are the bitcoins that paid for the pizza?"* has no unique answer after the first hop.

What we *can* do is pick a tracing convention, apply it consistently, and document every place the convention had to make an arbitrary choice.

## Tracing convention used here

**Strict positional FIFO.** Each input is modelled as a value range whose first `taint` satoshis are tainted and the remaining `value − taint` are clean. Outputs are filled left-to-right by consuming inputs in order; for each input we first donate its tainted portion, then its clean portion. The reference implementation is `fifo_distribute` in `src/tracer.py`.

Concretely, given input list `[T(8), C(2)]` (8 BTC tainted, 2 BTC clean) and output list `[6, 4]`:

- Output 0 (6 BTC): 6 BTC tainted (T's front-loaded 6 of 8 tainted sats).
- Output 1 (4 BTC): 2 BTC tainted (T's remaining 2 tainted sats) + 2 BTC clean.

### Alternatives we considered

- **Poison taint** — any output of a tx with at least one tainted input is fully tainted. Maximally aggressive; over-attributes by 8 BTC in the example above. Useful as an "outer bound" but seldom in chain-analysis pipelines.
- **Haircut / proportional dilution** — each output is tainted in proportion to the share of tainted value in the inputs. In the example: output 0 is `6 × 8/10 = 4.8` BTC tainted, output 1 is `4 × 8/10 = 3.2` BTC tainted. Loses positional information.
- **Strict positional FIFO (this convention)** — sits between the two, is order-deterministic, and is the closest fit to how chain-analysis firms describe their default. We picked it because it is order-deterministic, easy to audit by hand, and matches the way chain-analysis tooling commonly describes FIFO.

We also deliberately do not apply change-output heuristics or address-cluster heuristics during taint propagation. Those can be layered on top of the raw FIFO trace if a reader wants to extend the analysis.

## Pruning

The descendant graph is in principle exponential. To keep depth-5 tracing tractable we apply three pruning rules. These are **trace-budget thresholds**, not forensic conclusions about the destination of the coins; the reader should treat each terminal bucket below as "the trace stopped here under our budget," not as "the taint died here."

1. **Dust cutoff** — UTXOs with taint < 1 BTC are not traced further. They are recorded as `dust-pruned` terminals. 1 BTC is a project budget, not a Bitcoin policy "dust" threshold.
2. **Cluster termination** — when a tainted UTXO is consumed in a transaction with ≥ 100 inputs, the *spending transaction* is treated as a cluster boundary. The tainted inputs are recorded as `cluster-absorbed` and not traced further. This heuristic does not classify the receiving address as a known cluster; it is purely an input-count signal.
3. **Depth horizon** — at depth 5, all remaining tainted UTXOs are recorded as `depth-pruned` without further tracing. This is a horizon, not an observed terminal state.

Each terminal is logged with its classification so the reader can audit where the trace stopped.

## Terminal status taxonomy

| Status | Meaning |
|--------|---------|
| `still-unspent` | The UTXO has never been spent. The taint sits there today. |
| `cluster-absorbed` | Consumed by a transaction that mixed it with ≥100 other inputs. |
| `dust-pruned` | Below the 1 BTC tracing threshold. |
| `depth-pruned` | Reached depth 5 with positive taint, but not classified. |

The article reports `still-unspent` value as the **lower bound** on "Pizza Day coins that never moved". The actual number is higher (some `cluster-absorbed` taint may still be unspent inside the cluster), but we cannot prove it without de-anonymising clusters, which we will not attempt.

## Source of truth

Primary: [mempool.space](https://mempool.space) REST API. All responses cached in `data/cache.sqlite` for reproducibility. Each tx fetched is also stored as raw JSON in `data/raw/tx/<txid>.json` (gitignored, but the cache is authoritative).

Cross-checks against [blockchair.com](https://blockchair.com) on a sample of the descendant graph.

## What we deliberately do not do

- **De-anonymise clusters.** We will name well-known clusters (Mt. Gox, Coinbase, BitFinex) only when the on-chain evidence is unambiguous, which is rare.
- **Trace past depth 5.** The signal-to-noise ratio after 5 hops is poor and the article makes that explicit.
- **Trace Hanyecz's other pizza payments.** He made several. Only the famous transaction is in scope.

## What changes if you disagree with FIFO

If you re-run with poison or haircut conventions, the *set of transactions visited* in a no-pruning trace is the same — the descendant transaction graph is a topological consequence of which UTXOs are spent, independent of how taint is attributed. What changes under a different convention is *how much* taint each output receives, and therefore — because the pruning thresholds in this project key off taint magnitude — *which outputs* the traced subgraph keeps versus drops as `dust-pruned` or stops following past `depth-pruned`. Poison taint, in particular, would mark every output of a tainted transaction as fully tainted and could push the traced graph past the depth horizon faster than strict FIFO does.

The forensic-honesty argument of the article does not depend on the choice of convention; it depends only on the convention being made explicit and applied consistently.
