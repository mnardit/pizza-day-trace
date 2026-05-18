# Codex Visualization Review

Review target: live article at `https://max.nardit.com/articles/tracing-the-pizza-day-bitcoins` and the four React components in `personal-site/src/components/pizza-day/`.

Visual checks used the deployed markup plus headless Chrome screenshots at roughly desktop article width and narrow mobile width.

## A. AnchorComposition

**HIGH** - The component still has a max-row clipping problem. The grid revision fixed the center bucket column, but the bar rows still allocate `width: 100%` to the maximum bar and then place a fixed numeric label beside it inside the same flex cell. In the live desktop screenshot, the left max count reads as `11` rather than `111`, and the right outlier value is clipped after `3,7...` by the rounded figure wrapper. On narrow mobile, several right-side value labels are cut off. This makes the headline "111 crumbs / one outlier" visually fragile exactly where it should be most legible.

**MEDIUM** - The dual-axis concept is good and mostly tells the intended story: one long gray count bar for the 0.01 BTC crumbs, one dominant green value bar for the 3,753.88 BTC outlier, and mid-sized amber value bars for the chunky inputs. Once the clipping is ignored, the count-vs-value mismatch reads as data rather than wrong direction because the headers are clear and the left/right axes mirror each other. The smallest count bars, however, are hairlines; the one-input rows depend more on the printed count than the mark.

**MEDIUM** - The emerald "FEE PAID 0.99 BTC" emphasis is not fully earned. It is an interesting article detail, but in this figure the main analytical claim is input composition. Emerald already marks the value outlier, so the fee stat competes with the outlier and implies a second primary takeaway. The fee can stay, but it would be better as neutral text or a subtler accent.

**LOW** - Light-mode contrast is mostly acceptable, but the lightest marks are marginal. `bg-zinc-300` on `bg-zinc-50/70` is visible but quiet, and `bg-amber-300/70` for the single 50-100 BTC row is nearly a tick mark. The amber rows are otherwise readable; the bigger contrast issue is clipping, not color.

## B. UtxoDescendantGraph

**LOW** - The top-down depth axis reads clearly. The graph now fits the article column and the structure is understandable: split, linked branch, convergence, split, horizon. The right-margin depth labels are only partly useful. "depth 0 · anchor", "depth 3 · consolidation", and "depth 5 · horizon" reinforce the story, but plain "depth 1/2/4" labels add little and are faint enough to become background texture.

**LOW** - The larger depth-3 consolidation node reads as the fulcrum, not as arbitrary inconsistent sizing. It has two incoming edges, two outgoing edges, a label, and a fuchsia legend entry, so the increased radius/glow is supported by structure and story.

**LOW** - Edge routing is clean. I did not see crossings, and arrowheads make source/target direction clear. The long diagonal from the right depth-1 P2PK node to the consolidation node is the only edge that asks the eye to travel far, but it still lands unambiguously.

**LOW** - The depth-5 horizon grouping is acceptable. `1KcAt5...` at x=110 sits under the 5,500 BTC / `1B7cet...` parent at x=180, while the 3,500 and 2,000 BTC horizon nodes sit under the 4,500 BTC / `1NX8uq...` parent. The spacing does not falsely attach `1KcAt5...` to the right branch.

**MEDIUM** - Address labels are readable at the deployed desktop article size, but marginal on mobile. The SVG scales the 11px monospace text down with the full 620x960 viewBox, so short addresses are recognizable on desktop and merely inspectable on narrow screens. This is acceptable for decorative orientation, but not if the addresses are meant to be read as primary labels.

## C. PizzaTimeline

**LOW** - The spine + dot + gap-pill pattern communicates "five events with one large dormancy" well. It is much clearer than proportional horizontal time for the first-hour cluster. The reader sees three quick early events, one highlighted gap, then the consolidation and final horizon split.

**LOW** - The DORMANCY pill is visually proportional to its narrative importance without being oversold. It uses the same pill size as the other gaps but adds fuchsia color and the word `DORMANCY`, which is the right level of emphasis for a qualitative event feed. It does not pretend to be a scaled time axis.

**MEDIUM** - The event terminology is slightly uneven. `Anchor`, `1st split`, and `Final split` are structural; `Reshuffle` is more interpretive; `Consolidation + spend` is accurate but overloaded. `Final split` can also sound final in absolute terms even though it is final only before the chosen depth horizon. The labels work, but a tighter set such as "Anchor", "First split", "Linked hop", "Consolidation spend", "Horizon split" would be more consistent.

## D. DepositsTable

**MEDIUM** - The log-scale spark column is defensible but not essential. Log scale avoids reducing the 546-sat rows to invisible slivers, but the figure's main story is the recurrence of dust-limit deposits, not magnitude comparison across orders of magnitude. A linear scale would better dramatize how tiny the dust rows are relative to 141,482 sats, while the current log scale makes tiny and medium deposits look closer than they are. If the column stays, it needs the table values and notes to carry the interpretation.

**LOW** - The May-22 anniversary rows are obvious without being noisy. The row tint, green spark, and explicit "May-22 anniversary" text make the signal redundant in a good way. This is not color-only signaling.

**MEDIUM** - The spark column is the least earned column. Date and value are necessary; Note explains dust and anniversary status; the spark adds a small visual rhythm but little forensic meaning. On narrow mobile the table also becomes cramped and right-side notes are clipped by the figure, so the optional visual column is the first thing I would sacrifice.

## E. Cross-cutting

**LOW** - The four figures share a coherent visual language. The rounded wrapper, bordered figcaption, uppercase eyebrow, zinc background, muted body copy, and small mono data labels make them feel like a set. The graph is more saturated and glowy than the table, but it has more topology to carry, so the difference feels purposeful rather than like a different author.

**HIGH** - Narrow-width overflow remains a cross-cutting risk. The live mobile screenshot shows clipped figure content in `AnchorComposition`, clipped table notes, and generally constrained right edges. Some of this may be exacerbated by long inline article code spans, but the figures themselves should not depend on horizontal overflow being available inside an `overflow-hidden` wrapper.

**MEDIUM** - Accessibility is mixed. `UtxoDescendantGraph` has an SVG `aria-label`; the timeline uses real list markup; the deposits table is real tabular data with text labels for the anniversary rows. But the chart-like information in `AnchorComposition` is not available as a semantic table or accessible description, and the decorative spark bars are not marked hidden. The graph's `aria-label` is too generic to communicate the important structure to a screen reader. Color is usually backed by text labels, but the graph variants still rely heavily on color plus legend association.

**MEDIUM** - Contrast is generally acceptable in both palettes, but the faintest supporting labels are too faint to matter. The graph depth labels and guide lines are barely legible in light mode; that is fine if they are decorative, but then they should be treated as decoration. The table and timeline body text hold up better.

**LOW** - The data supports a few additions that would help the article without adding much weight: a total unspent post-2010 deposit sum in the deposits caption, explicit percentage labels for the anchor outlier and crumb count, and a small "horizon means trace stop, not unspent today" note near the graph legend. The prose covers these points, but the figures would stand better when skimmed.

One-line verdict: strong third-iteration direction, but `AnchorComposition` and narrow-width clipping need another pass before the visual set is publication-grade.
