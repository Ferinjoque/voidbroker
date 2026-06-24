# DESIGN.md — voidbroker

## Theme

Dark, justified by use: night trading, dense data, reduced glare on a large monitor. Not
dark-for-cool. The surface is a deep void-blue-black, tinted toward the brand hue.

## Color (strategy: Full palette, used semantically)

OKLCH, neutrals tinted toward void blue (265). A data-viz palette where every color carries
meaning (the product register permits this for analytics): **gold** = signal / primary,
**cyan** = void-energy / selection & volume, **green/red** = market direction, **violet** =
rivens, **amber** = catalysts (Baro). Never decoration. (This replaces the original
Restrained single-accent direction — it read as flat for a market terminal.)

```
--void-900: oklch(16% 0.02 265)   /* app background          */
--void-850: oklch(19% 0.02 265)   /* panel / nav surface     */
--void-800: oklch(23% 0.02 265)   /* raised surface, headers */
--void-700: oklch(30% 0.02 265)   /* borders, dividers       */
--ink-100:  oklch(93% 0.01 265)   /* primary text            */
--ink-400:  oklch(68% 0.015 265)  /* secondary text          */
--ink-600:  oklch(52% 0.015 265)  /* tertiary / axis labels  */

--gold:     oklch(80% 0.13 85)    /* Orokin signal accent    */
--gold-dim: oklch(70% 0.10 85)
--up:       oklch(72% 0.16 150)   /* gain / buff / opportunity*/
--down:     oklch(64% 0.18 25)    /* loss / nerf             */
--void-cyan:oklch(75% 0.11 220)   /* secondary highlight     */
```

Never `#000`/`#fff`. Every neutral tinted toward 265 (void blue).

## Typography (3 bundled variable fonts, local — no CDN)

- **Display** (`Space Grotesk Variable`): page titles + hero numerals (the countdown, vitals).
  Strong size/weight jumps for hierarchy — this is where the "bolder" lives.
- **UI/body** (`Inter Variable`): labels, descriptions, table text.
- **Data** (`JetBrains Mono Variable`, `.nums`): all prices/figures, `tabular-nums` for alignment.

## Data visualization

Tables carry their own viz, market-terminal style: inline **sparklines** (trend, auto-colored
up/down), **meter bars** (score, discount, volume — proportional, animated draw-in), and
**pills** for categorical state (buff/nerf, phase, comp count). The score meter makes the
liquidity-adjusted ranking legible at a glance.

## Layout

- Persistent left nav (sections) + top bar (archive status). Content is dense tables and a
  chart panel. Predictable grid; consistency is the affordance.
- Spacing rhythm varies by role (section gaps larger than row padding); not uniform.
- No card grids. Tables and panels, not boxes-of-everything. No nested cards.

## Components

- Tables: sticky header, zebra-free (use hairline dividers), right-aligned numerics,
  hover-row highlight, gold left text for the actionable column only.
- States: every interactive element has hover/focus/active; rows have hover + selected.
- Loading: skeleton rows, not center spinners. Empty states teach the next command.

## Motion

150–220ms, ease-out. Conveys state (hover, selection, value change flash), never decoration.
No page-load choreography.

## Bans honored

No gradient text, no side-stripe borders, no glassmorphism, no hero-metric template, no
identical card grids, no em dashes.
