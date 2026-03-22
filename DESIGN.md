# Design System Document: The Cinematic Flux

## 1. Overview & Creative North Star
**Creative North Star: "The Digital Projection"**
This design system moves away from the static, "boxy" nature of traditional dashboards. Instead, it treats the media downloader as a premium screening room. The interface should feel like light projected onto deep glass—fluid, immersive, and high-contrast. 

We break the "template" look through **Intentional Asymmetry**. Rather than a rigid 12-column grid, we use expansive negative space (e.g., `spacing.20`) to let high-priority downloads "breathe," while secondary stats are tucked into offset, nested containers. The goal is an editorial feel where the content (the media) is the hero, and the UI is the sophisticated lens through which it is viewed.

---

## 2. Colors & Surface Architecture
The palette is rooted in a deep, "Midnight Ink" base (`surface`) with high-energy "Signal" accents (`secondary`).

### The "No-Line" Rule
**Strict Mandate:** Designers are prohibited from using 1px solid borders to define sections. Layout boundaries must be established exclusively through:
*   **Background Shifts:** Placing a `surface-container-low` card against a `surface` background.
*   **Tonal Transitions:** Using the `surface-container` tiers to imply depth.

### Surface Hierarchy & Nesting
Treat the UI as a physical stack of semi-transparent materials.
*   **Base Level:** `surface` (#020a2f) — The infinite background.
*   **Primary Sectioning:** `surface-container-low` (#050f38) — Large structural areas (e.g., the sidebar).
*   **Interactive Cards:** `surface-container` (#091542) — The standard container for download items.
*   **Active/Elevated Elements:** `surface-container-high` (#0e1b4c) — Hover states or high-priority alerts.

### The "Glass & Gradient" Rule
To achieve a "Signature" feel, floating headers and navigation bars must use **Glassmorphism**. Apply `surface` at 70% opacity with a `backdrop-filter: blur(20px)`. 
*   **Signature Textures:** Use a linear gradient on primary action buttons, transitioning from `primary` (#85adff) to `primary-container` (#6e9fff) at a 135-degree angle. This adds a "lithographic" depth that flat hex codes lack.

---

## 3. Typography
We utilize a dual-typeface system to balance technical precision with editorial elegance.

*   **Display & Headlines (Plus Jakarta Sans):** Chosen for its wide stance and modern geometric terminals. Use `display-lg` for dashboard welcomes and `headline-sm` for media titles. High-contrast sizing (e.g., jumping from a `display-md` title to `body-sm` metadata) is encouraged to create a sophisticated, "magazine-style" hierarchy.
*   **Body & Labels (Manrope):** A highly legible sans-serif used for technical data. Use `label-md` for bitrates and file sizes to ensure absolute clarity amidst the vibrant UI.
*   **Visual Soul:** Always set `title-lg` headers in `on-surface-variant` (#a1a9d5) to prevent the screen from feeling "too white," reserving pure `on-surface` (#e1e4ff) for active headlines only.

---

## 4. Elevation & Depth
In this design system, "Up" is defined by light and clarity, not by shadows.

### The Layering Principle
Depth is achieved by "stacking" tones. A `surface-container-lowest` (#000000) drawer sliding over a `surface` (#020a2f) background creates a natural, heavy "sink" that draws the eye without a single line of CSS border.

### Ambient Shadows
If an element must float (e.g., a context menu):
*   **Blur:** `40px` to `60px`.
*   **Opacity:** 15%.
*   **Color:** Use a tinted version of the background (`#000000`) rather than grey. This ensures the shadow feels like a "light occlusion" rather than a dirty smudge.

### The "Ghost Border" Fallback
If contrast testing fails, use a "Ghost Border": `outline-variant` (#3d466c) at **15% opacity**. It should be felt, not seen.

---

## 5. Components

### Download Cards (The Signature Component)
*   **Constraint:** No dividers. Use `spacing.6` of vertical white space to separate items.
*   **Progress Indicators:** Use the `secondary` (#ff716a) accent for progress bars. The track should be `surface-variant` (#142156) at 40% opacity. 
*   **Corner Radius:** Apply `rounded-xl` (1.5rem) to the outer container and `rounded-md` (0.75rem) to inner media thumbnails.

### Buttons
*   **Primary:** Gradient fill (`primary` to `primary-container`). `rounded-full`. 
*   **Secondary/Tertiary:** No background. Use `on-surface` text with a subtle `surface-bright` hover state.

### Status Chips
*   **Active:** `tertiary-container` (#f199f7) text on a `surface-container-highest` background.
*   **Error:** `error` (#ff716c) text. No background container—just the icon and text to maintain a clean "editorial" aesthetic.

### Input Fields
*   Avoid the "box" look. Use a `surface-container-lowest` fill with a `rounded-lg` corner. On focus, transition the background to `surface-container-high` and glow the `on-surface-variant` label.

---

## 6. Do's and Don'ts

### Do
*   **Do** use asymmetrical layouts. A 30/70 split for the dashboard is more sophisticated than a 50/50 split.
*   **Do** use `tertiary` (#fbabff) for "Finished" or "Complete" states to provide a vibrant, "pop-art" contrast to the deep blues.
*   **Do** lean into `rounded-xl` for large dashboard tiles; it softens the technical nature of a "downloader."

### Don't
*   **Don't** use 100% opaque borders. They break the "projection" illusion.
*   **Don't** use standard "YouTube Red" (#FF0000). Use our `secondary` (#ff716a) which is tuned for dark-mode retinal comfort.
*   **Don't** crowd the interface. If the user has 20 downloads, use a "Focus Mode" where only the top 3 are expanded with full metadata, while the rest are collapsed into `surface-container-low` strips.

---

## 7. Interaction Micro-animations
*   **The "Ooze" Effect:** When a download completes, the progress bar should expand into a subtle glow that fills the entire card background momentarily using `secondary_dim` at 10% opacity, before settling back to the default surface state.
*   **Parallax Hover:** Cards should have a subtle 2-degree tilt and 5px XY translation on hover to reinforce the "floating glass" physical model.