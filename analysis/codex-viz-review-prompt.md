# Codex review: pizza-day article visualizations

You are reviewing four data visualizations embedded in the live article at
**https://max.nardit.com/articles/tracing-the-pizza-day-bitcoins**. The article
is a forensic UTXO trace of the famous 10,000 BTC pizza transaction. The
visualizations are TypeScript React components living in:

- `/home/yahont/projects/personal-site/src/components/pizza-day/AnchorComposition.tsx`
- `/home/yahont/projects/personal-site/src/components/pizza-day/UtxoDescendantGraph.tsx`
- `/home/yahont/projects/personal-site/src/components/pizza-day/PizzaTimeline.tsx`
- `/home/yahont/projects/personal-site/src/components/pizza-day/DepositsTable.tsx`

(All four are also accessible via the deployed HTML at the URL above. Use
`curl` if you want to look at the rendered markup.)

**Do not modify any files.** Produce a written critique.

## Context

These are the second iteration. The first was inline JSX inside an MDX file;
two of the four rendered as empty containers because MDX choked on
`{[...].map(...)}` expressions. The four current components have replaced that
inline code and are registered in
`/home/yahont/projects/personal-site/src/app/[locale]/articles/[slug]/page.tsx`.

After deploy, three problems were found visually and a third revision shipped:

1. `AnchorComposition` had `grid-cols-[1fr_auto_1fr]` which let the count/value
   labels wrap onto a new line when there was not enough room. The current
   version uses `minmax(0,1fr)_8.5rem_minmax(0,1fr)` with `shrink-0` on the
   text labels.
2. `UtxoDescendantGraph` was originally horizontal with `min-w-[760px]` and
   spilled past the 672 px article column. The current version is **vertical**
   (viewBox 620x960, depth flows top to bottom).
3. `PizzaTimeline` was originally proportional-time horizontal, which crammed
   the first three milestones (all inside one hour) into one point. The current
   version is a **vertical event feed**: dots on a left spine, milestone label
   to the right, a labelled "gap" pill between consecutive events with a fuchsia
   "DORMANCY" pill for the 45-day stretch.

## What to critique

For each of the four components, in this order:

### A. AnchorComposition
- Does the dual-axis (count vs BTC value) actually tell the "few chunks, one
  outlier, 111 crumbs" story at a glance?
- Are the bar widths legible? Any rows where the bar reads as wrong direction
  (count vs value mismatch)?
- The "FEE PAID 0.99 BTC" stat is highlighted emerald. Is that earned, or does
  it pull attention from the more substantive numbers?
- Light-mode contrast: any of the amber/zinc tones invisible on the light
  background?

### B. UtxoDescendantGraph (vertical)
- Layout: does the top-down depth axis read clearly? Are the depth labels on
  the right margin doing useful work or just clutter?
- The depth-3 consolidation node is drawn larger and has more glow. Does that
  read as "this is the fulcrum" or as inconsistent sizing?
- Edge routing: are any arrows ambiguous about source/target? Any edges
  crossing each other?
- The three depth-5 horizon nodes: 110, 380, 510 X positions. Is `1KcAt5…`
  visually grouped with the right parent (`1B7cet…`)?
- Address text under each node is monospaced. Is it readable at the SVG size
  the article actually renders?

### C. PizzaTimeline (vertical event feed)
- Does the spine + dot + gap-pill pattern actually communicate "five events
  with one big dormancy in the middle"?
- The DORMANCY pill: is the visual weight proportional to its importance in
  the story, or oversold?
- Are the milestone labels (Anchor / 1st split / Reshuffle / Consolidation +
  spend / Final split) consistent in terminology, or do any of them sound
  off?

### D. DepositsTable
- The log-scale spark column: is log scale the right call, or does linear
  scale tell the dust-limit story better?
- Anniversary rows are tinted emerald. Are they obvious enough without
  being noisy?
- Any column that adds clutter without earning its space?

### E. Cross-cutting

- Consistency: do all four figures share a coherent visual language
  (rounded-2xl wrapper, figcaption with eyebrow + body, uppercase tracking,
  zinc-on-zinc tone palette)? Or do they look like they were built by four
  different people?
- Accessibility: aria labels on the SVGs, color-only signaling vs labels,
  contrast on dark and light backgrounds.
- Anything missing that the data clearly supports and the article would
  benefit from?

## Output

Save a Markdown report to
`/home/yahont/projects/pizza-day-trace/analysis/codex-viz-review.md`.
Sections A–E. Severity: CRITICAL / HIGH / MEDIUM / LOW. End with a
one-line verdict.
