# ShopShare marketing site

A static, zero-build marketing/landing page for ShopShare — plain HTML/CSS/JS,
using the brand logo pack in `assets/logos/` and a small Three.js scene in the
hero for the animated 3D tote-bag mark. No framework, no build step, so it
deploys on Vercel with zero configuration.

## Run locally

Any static file server works, e.g.:

```bash
cd shopshare-web
python3 -m http.server 8080
# open http://localhost:8080
```

(Opening `index.html` directly by double-clicking also works, but a local
server avoids browser restrictions on `fetch`/module-style asset loading.)

## Deploy to Vercel

**Option A — Vercel CLI**

```bash
npm i -g vercel     # one-time
cd shopshare-web
vercel               # first deploy, follow the prompts
vercel --prod         # promote to production
```

**Option B — Git-connected project (recommended for ongoing updates)**

1. Push this `shopshare-web` folder to its own GitHub repo (or a subfolder of
   an existing one — set the Vercel project's "Root Directory" accordingly).
2. In the Vercel dashboard: **Add New → Project → Import** your repo.
3. Framework preset: **Other** (it's static, no build command needed).
4. Deploy. Vercel serves `index.html` and everything under `assets/` as-is.

## Editing

- `index.html` — all page content/sections.
- `styles.css` — design tokens live at the top of the file under `:root`
  (colors, radii, shadows) — change those to re-theme the whole site.
- `script.js` — nav behavior, scroll-reveal animation, the waitlist form
  (currently front-end only — see below), and the Three.js hero scene.
- `assets/logos/` — the full SVG logo set from the brand pack (horizontal,
  stacked, mark-only, in both green and white variants).

## Waitlist form

The email waitlist form in the final CTA section (`#waitlistForm` in
`script.js`) is currently a front-end-only placeholder — it shows a
confirmation message but doesn't send the email anywhere. Wire it up to a
real backend before launch, e.g.:

- POST to a new endpoint on the existing ShopShare FastAPI backend, or
- A Vercel Serverless Function (`/api/waitlist.js`) that forwards to an email
  list provider (Mailchimp, Resend, etc.), or
- A form service like Formspree/Basin if you'd rather not write a backend.

## Notes

- The hero's 3D scene gracefully does nothing if `prefers-reduced-motion` is
  set, or if Three.js fails to load (e.g. offline) — the rest of the page is
  unaffected either way.
- Favicon and social preview images come from `assets/` (`favicon-32.png`,
  `favicon-16.png`, `apple-touch-icon.png`, `og-image-source.png`), pulled
  from the brand pack's dedicated `png/website/` folder.
