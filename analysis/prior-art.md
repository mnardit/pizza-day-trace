# Prior Art Survey

A scan of what others have published about the Pizza Day transaction, so we know what's already covered and where the genuine white space is.

## What exists

### 1. Allen Day / Google Cloud — *Visualizing the 10,000 BTC Pizza Network* (2018)

- **Source**: [training-data-analyst repo](https://github.com/GoogleCloudPlatform/training-data-analyst/blob/master/blogs/bitcoin_network/visualizing_the_10000_pizza_bitcoin_network.ipynb), also on Qwiklabs/Google Skills as a paid lab
- **Approach**: BigQuery public Bitcoin dataset, two-degree graph from a seed address
- **Seed used**: `1XPTgDRhN8RFnzniWCddobD9iKZatrvH4` — *Hanyecz's sending address*, not the pizza recipient
- **Methodology issue**: starting from Hanyecz's address means the graph captures *everything Hanyecz sent in 2010*, not the pizza coins specifically. The famous tx is one of many flows from that address. They retrieved 752 datapoints, post-processed to 106 aggregated flows.
- **Visualization convention**: Hanyecz's address as red node, everything else blue, arrow direction = flow, stroke width ∝ BTC amount. Worth reusing.
- **Depth**: 2 degrees.

### 2. Sohier Dane — *Tracing the 10,000 BTC pizza* (Kaggle)
- Derivative of Allen Day's work. 8 years old, 87 upvotes. Same BigQuery template, same 2-degree limit.

### 3. Moussa & Cuzzocrea — *Extracting Insights From Bitcoin Transactions: Data Warehouse Modeling and Analytical Questions* (Jan 2021)
- Academic paper, figure 2 caption: *"131 input addresses participated in the pizza transaction"*
- **Factual error**: it's 131 inputs from **one** address (`1XPTgDRhN8RFnzniWCddobD9iKZatrvH4`), not 131 distinct addresses. Even a peer-reviewed paper misread this transaction's structure. Worth quietly correcting in our piece.

### 4. CoinDesk (Colin Harper, May 22, 2025) — *What You Didn't Know About Laszlo Hanyecz*
- Biographical, no forensic. Key factoids we can reuse:
  - Hanyecz wrote the first MacOS Bitcoin client (April 19, 2010)
  - Hanyecz discovered GPU mining and published the binary May 10, 2010
  - Satoshi messaged Hanyecz privately asking him to stop publicizing GPU mining
  - Hanyecz's address received and spent **81,432 BTC** from April–November 2010
  - He spent "nearly 100,000 BTC" on pizza-style transactions in the year that followed
  - Hanyecz himself: *"I felt like I was beating the internet, getting free food"*

### 5. DeckerSU/pizza_tx_example (GitHub)
- OpenSSL signature verification tutorial using the next-hop tx `cca7507...` as example
- Confirms that tx splits 10K → 5,777 + 4,223 BTC, fee = 0
- Pure cryptographic tutorial, no descendant analysis

### 6. bitcoinpizzaindex.net
- Live counterfactual: 10K BTC = $X today, plus commodity equivalents (gold ounces, silver kg, EUR)
- Single dashboard number. Borrowable rhetorical sidebar: "10K BTC = N kg of gold" framing.

### 7. Mainstream coverage (Fortune, Gemini, SoFi, AJ Bell, BYDFi, Trakx, Gate, Medium, etc.)
- All counterfactual-valuation + biography. None do descendant tracing.

## Recurring claims worth verifying

| Claim | Source | Our verification |
|-------|--------|------------------|
| Block time `1:16 PM` ET | CoinDesk | Mempool confirms `18:16 UTC` = `14:16 ET`. CoinDesk's `1:16 PM` is wrong by 1 hour. |
| jercos address used 4 other times | CoinDesk | Mempool: `tx_count=15` (1 outgoing, 14 incoming). "Used 4 other times" understates by ~10. |
| 131 input addresses | Moussa 2021 | False. 131 inputs, 1 address. |
| jercos spent the BTC on a road trip | Multiple | Unverifiable from chain. His own interview is the source. |
| Hanyecz pioneered MacOS Bitcoin Core | CoinDesk | Verifiable in Bitcointalk archive. |
| Hanyecz discovered GPU mining | CoinDesk | Verifiable in Bitcointalk archive. |

## What nobody has done (our white space)

1. **Descendant tracing past 2 hops.** Allen Day stopped at 2. We go to 5.
2. **Explicit FIFO-taint methodology with documented forks.** Nobody states their convention or audits where convention forces an arbitrary call.
3. **Dormancy / wake-event catalogue.** No one has systematically asked: which descendant UTXOs are still unspent, which woke up after years, when?
4. **Anchor input composition timeline.** The 131 inputs of the anchor tx tell a story about Hanyecz's mining accumulation — first-seen block of each input, the apparent 50-BTC coinbase patterns, the 3753.88 BTC chunk. Nobody has decomposed this.
5. **Memorial dust quantification.** The recipient address has 14 funded TXOs of which 13 are unspent dust tributes accumulating since 2010. Total value, symbolic amounts (522 sats? May-22 dates?), annual cadence — none of this is published.
6. **Reproducible public repo + downloadable CSV datasets.** Allen Day's notebook is gated behind Qwiklabs; nothing else publishes the data.
7. **Honest methodology section.** Most coverage treats "the coins" as a well-defined object. We open by acknowledging the UTXO problem and choosing a convention out loud.

## Visual conventions to steal

- Anchor node red, all others blue (Allen Day) — standard in chain-analysis viz
- Edge width proportional to BTC amount (Allen Day)
- Commodity-conversion sidebar (Bitcoin Pizza Index)

## What we deliberately won't do

- Speculate about jercos's road trip beyond what's chain-verifiable
- De-anonymize clusters past widely-known endpoints
- Drag in Hanyecz's other ~90K BTC of pizza payments (scope = the famous tx)
