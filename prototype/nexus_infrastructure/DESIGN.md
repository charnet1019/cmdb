# Design System Specification: The Architectural Intelligence

## 1. Overview & Creative North Star
### Creative North Star: "The Digital Architect"
In the complex world of Enterprise CMDB (Configuration Management Database), data is often chaotic. This design system moves beyond the "standard utility" look to become **The Digital Architect**. It treats IT infrastructure management not as a series of rows and columns, but as a structured, high-end editorial experience. 

We break the "template" look by utilizing **Intentional Asymmetry** and **Tonal Depth**. By moving away from rigid 1px borders and moving toward a layered, "glass-on-paper" aesthetic, we convey a sense of authoritative calm. The system feels premium because it prioritizes breathing room (`Spacing Scale 8+`) and sophisticated typographic scales, ensuring that even the most complex data schema feels curated and intentional.

---

## 2. Colors & Surface Philosophy
The palette is rooted in a deep, trustworthy blue, but its application is nuanced. We avoid "flat" design in favor of "environmental" design.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders to define sections. Layout boundaries must be created through:
1.  **Background Color Shifts:** Placing a `surface_container_low` card on a `surface` background.
2.  **Tonal Transitions:** Using the hierarchy of `surface_container` tokens to define nested importance.

### Surface Hierarchy & Nesting
Treat the UI as physical layers.
*   **Base Layer:** `surface` (#f7f9fc) – The foundational canvas.
*   **Sectional Layer:** `surface_container_low` (#f2f4f7) – Used for the sidebar or large grouping areas.
*   **Object Layer:** `surface_container_lowest` (#ffffff) – Used for primary content cards and data tables to provide maximum "lift."
*   **Interaction Layer:** `surface_container_high` (#e6e8eb) – Used for hover states and active menu selections.

### The "Glass & Gradient" Rule
To elevate the CMDB beyond a generic dashboard:
*   **Floating Elements:** Use `surface_container_lowest` with a 80% opacity and a `backdrop-blur: 12px` for floating modals or nested menus.
*   **Signature Textures:** For primary CTAs and high-level Dashboard "Total Asset" cards, use a subtle linear gradient from `primary` (#005daa) to `primary_container` (#0075d5) at a 135-degree angle. This adds "visual soul" and professional polish.

---

## 3. Typography: Editorial Authority
We use a dual-font strategy to balance technical precision with executive-level presentation.

*   **Display & Headline (Manrope):** Chosen for its geometric modernism. Use `display-md` for high-level dashboard metrics to give them an "editorial" feel.
*   **Body & Labels (Inter):** Chosen for its extreme legibility at small sizes. All technical data, CI (Configuration Item) details, and form labels must use Inter.

**Hierarchy as Identity:**
*   **The Power Gap:** Create high contrast between `headline-lg` (Title of the Page) and `body-sm` (Meta-data). This "High-Low" pairing mimics high-end architectural magazines, making the enterprise data feel premium.

---

## 4. Elevation & Depth: Tonal Layering
Traditional drop shadows are often messy. We achieve depth through **Environmental Lighting**.

*   **The Layering Principle:** Place a `surface_container_lowest` card (Pure White) on top of a `surface_container_low` background. The subtle 2-3% difference in hex value creates a natural edge without a line.
*   **Ambient Shadows:** When an element must "float" (e.g., a complex nested menu), use a shadow with a blur of `24px` and an opacity of `4%`. Use a tint of the `on_surface` color (`#191c1e`) to ensure the shadow looks like natural light occlusion.
*   **The "Ghost Border" Fallback:** If accessibility requires a container edge, use the `outline_variant` token at **15% opacity**. High-contrast, 100% opaque borders are strictly forbidden.

---

## 5. Components

### Buttons
*   **Primary:** Gradient fill (`primary` to `primary_container`), `xl` roundedness (0.75rem). No border.
*   **Secondary:** `surface_container_high` fill with `on_secondary_container` text.
*   **Tertiary:** Ghost style. No background, `primary` text, `md` roundedness for the hover state.

### Data Tables (The CMDB Core)
*   **Layout:** Forbid internal vertical divider lines.
*   **Separation:** Use a `1px` `outline_variant` at 10% opacity for horizontal rows only.
*   **Header:** `surface_container_low` background with `label-md` typography in `on_surface_variant`.

### Complex Forms
*   **Inputs:** Use `surface_container_lowest` for the field background to "pop" against `surface_container_low` page sections.
*   **Focus State:** A 2px "Halo" using `primary` at 20% opacity, rather than a solid color change.

### Status Tags (CIs & Assets)
*   **Logic:** Don't use heavy solid colors. Use a "Soft Fill" approach: a 10% opacity version of the status color (e.g., `error_container`) with high-contrast text (`on_error_container`).

### Stat Cards (Dashboard)
*   **Style:** Large `display-sm` numbers. Use `tertiary` (#934600) for "Warning/Attention" metrics to provide a sophisticated alternative to standard "Danger Red."

---

## 6. Do’s and Don’ts

### Do:
*   **DO** use white space as a structural element. If you think you need a line, try adding `Spacing 8` (1.75rem) instead.
*   **DO** use `xl` roundedness (0.75rem) for main content cards to soften the enterprise feel.
*   **DO** nest `surface_container_lowest` elements inside `surface_container_low` areas to create logical grouping.

### Don’t:
*   **DON’T** use pure black (#000000) for text. Always use `on_surface` or `on_surface_variant`.
*   **DON’T** use default 1px borders. If a container feels "lost," adjust the background color of the parent container instead.
*   **DON’T** crowd the sidebar. Use `title-sm` for categories and `body-md` for items, ensuring at least `Spacing 4` between links.