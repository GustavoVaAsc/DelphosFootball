---
name: react-bits
description: Use when adding an animated UI component, text effect, cursor/hover effect, interactive component, or WebGL/canvas background to a React project via React Bits (reactbits.dev / DavidHDev/react-bits) — or when asked to recall/write a React Bits component's code, props, or install steps.
---

# React Bits Skill

A comprehensive guide and tool router for integrating components from **React Bits** (https://reactbits.dev, created by @DavidHDev), an open-source library of 100+ animated, interactive, and customizable React components.

## Core Rules

1. **Do Not Hallucinate Code from Memory:** Component internals, dependencies (`motion` vs `framer-motion`, `three.js`, `@react-spring/web`), and props change frequently. Always use verified installation commands or fetch live code from the registry:
   - Endpoint pattern: `https://reactbits.dev/r/<ComponentName>-<Variant>.json`
2. **Four Available Variants:**
   - `TS-TW`: TypeScript + Tailwind CSS (Recommended default for modern Next.js/Vite projects)
   - `JS-TW`: JavaScript + Tailwind CSS
   - `TS-CSS`: TypeScript + Vanilla CSS / CSS Modules
   - `JS-CSS`: JavaScript + Vanilla CSS / CSS Modules
3. **Respect Project Stack:**
   - Detect if the user's project uses Tailwind (`tailwind.config.js` / `@tailwindcss/vite`) and TypeScript (`tsconfig.json`).
   - Match the target variant accordingly.

## Installation Methods

### 1. Via shadcn CLI
```bash
npx shadcn@latest add @react-bits/<ComponentName>-<Variant>
# Example:
npx shadcn@latest add @react-bits/BlurText-TS-TW
npx shadcn@latest add @react-bits/SpotlightCard-TS-TW
```

### 2. Via jsrepo CLI
```bash
npx jsrepo@latest add https://reactbits.dev/r/<ComponentName>-<Variant>
# Example:
npx jsrepo@latest add https://reactbits.dev/r/Aurora-TS-TW
```

### 3. Direct JSON Registry Inspection
Fetch `https://reactbits.dev/r/<ComponentName>-<Variant>.json` to inspect:
- `files`: The source code of the component.
- `dependencies`: Required npm packages (e.g. `motion`, `lucide-react`, `three`).
- `devDependencies`: Required development dependencies.

## Component Catalog

### 1. Text Animations
- `BlurText`: Smooth blur-in revealing letters or words.
- `SplitText`: Staggered letter, word, or line reveals.
- `ShinyText`: Subtle shimmer / gloss sweep across typography.
- `DecryptedText`: Cyberpunk-style decryption scramble effect on hover/view.
- `GradientText`: Animated looping gradient color text.
- `RotatingText`: Flip / carousel transition between rotating text words.
- `TrueFocus`: Spotlight/focus blur box tracking hovered words.
- `VariableProximity`: Typography that scales/weights as the cursor nears.
- `GlitchText` / `FuzzyText`: High-energy glitch and analog static text effects.
- `ScrollVelocity`: Marquee text that speeds up based on scroll momentum.
- `CountUp`: Smooth numeric count-up animation with formatting.

### 2. Backgrounds & Canvas
- `Aurora`: Fluid multi-color northern lights ambient background.
- `Hyperspeed`: Starfield / highway light-trail warp drive canvas.
- `LiquidChrome`: Interactive metallic chrome fluid simulation.
- `Particles`: Configurable floating particle mesh with mouse interaction.
- `Squares`: Isometric or orthogonal animated interactive grid tiles.
- `Waves`: Harmonic wave canvas responding to cursor movements.
- `GridDistortion`: Interactive cursor mesh distortion effect.
- `Iridescence`: Shimmering oil-slick iridescent organic background.

### 3. Interactive Components & Cards
- `SpotlightCard`: Bento/card component with a radial spotlight following cursor.
- `TiltedCard`: 3D parallax tilt card responding to mouse position.
- `PixelCard`: Pixelated hover reveal and border animation.
- `ReflectiveCard`: Metallic card with dynamic specular light reflection.
- `Stack` / `ScrollStack`: Card deck stack that fans out or transitions on scroll.
- `DecayCard`: Physical decay / spring interaction on drag.
- `ElasticSlider`: Satisfying springy elastic drag slider.

### 4. Micro-Interactions & Cursors
- `BlobCursor`: Organic fluid gooey blob that smoothly trails the pointer.
- `Magnet`: Elements magnetically attracted to the cursor on proximity.
- `SplashCursor`: Fluid dynamics liquid splash under the mouse.
- `ClickSpark`: Micro spark burst particle effect on user click.
- `StarBorder`: Pulsing neon star particle gradient moving along borders.
