# The catalog store (waitlist site, phase 2): design

Date: 2026-10-16. Status: built by Claude on the owner's brief ("a big catalog, a proper store,
Seth Rogen's Houseplant as inspiration, feels like a site of the year page; the products don't look
good, make them awesome"). The owner opted out of questions; the calls below are Claude's.

## Intent

TikTok viewers land from the bio link on a phone. The site should feel like a real, desirable
store with a lot to look at, while staying honest: nothing is sold yet, every product is a
reservation (the waitlist), and the images are renders. Reservations tell the owner what to print.

## Concept

**The Try Solarpunk catalog, volume one.** A 1970s mail-order catalog (Whole Earth Catalog,
Houseplant's warmth) built as a modern site:

- Catalog numbers (No. 001...) are real structure: objects are 001-013, merch 101-109, kits 201-202.
- Products are shot like Houseplant's: one object on a coloured paper sweep, low sun through leaves.
- One signature moment: the hero is the logo as a place (flat ink-outlined sun, rays, hills and
  clouds) over a field of real WebGL grass you can push around; tapping grows flowers.
- The page is a feed that ends: the footer is a sunset and says "The end."

## Products

Redesigned: the Hibernator (now a quilted "sleeping bag" with an ink-rimmed sun badge) and the
Eyelid (the opening is a lid line with an ink liner and lashes, so the sleeve is one big closed eye).

New objects: the Infinite Scroll (fidget wheel), the Sundial (worked out for 40.7 N), the Sunup
(alarm clock shaped like the logo), the Greenhouse (planter with a phone basement), the Kids' Table
(six phones face each other at dinner, a dishes spinner), the Bunk (phone bed), the Doghouse,
the Crypt (limited Halloween coffin), Do Something Else Dice, the Thumb Stone, Moss Head (a planter
of the mascot). Merch: two tees, a crewneck, the Moss beanie, a cap, tote, stickers, socks, poster.
Kits: Starter, Lights Out.

Second line (October 2026), each named after the phone habit it replaces: Followers (birdhouse
with a living roof and its first follower, a printed finch), Group Chat (bee hotel shaped like a
speech bubble, in blue bubble and green bubble), The Feed (bird feeder shaped like a phone, the
seed is the content), Pull to Refresh (yo-yo), Loading (spinning top with a loading spinner),
Dark Mode (chamberstick with a crescent moon handle), Push Notifications (six fridge magnets),
Cloud Storage (pen pot), Captcha (sliding tile puzzle), Inbox Zero (letter tray with a 0 badge),
Hashtags (plant markers), Reactions (cookie cutters), Time Out (corner shelf and dunce cap for
the phone), Incubator (seed starter), Airplane Mode (boomerang), Screen Time (20 minute sand
timer). New category "Fire escape" for the outdoor ones. Kits: Fire Escape, Game Night.

Prices are Claude's proposal (lib/catalog.js), to be confirmed by the owner before launch.

## How it is built

- `products/blender/` (local only, gitignored like the CAD): every product is parametric signed-
  distance CAD in Blender's Python (numpy + OpenVDB), so parts are watertight and printable.
  `render.py` renders shots in Cycles; `batch.sh` renders every colourway.
- `site/build/images.mjs` turns renders into AVIF/WebP at 400/800/1200 px plus a manifest with the
  backdrop colour. Products without a render are left off the site automatically.
- `site/build/build.mjs` (plain Node + esbuild + sharp, no framework) renders every page from
  `lib/catalog.js` into `dist/`, bundles CSS/JS with hashed names, and makes share images.
- JS: the bag (localStorage), colour picker, reserve flow, GSAP + ScrollTrigger + Lenis for a few
  orchestrated motions, and the three.js meadow loaded after first paint.

## Contract kept

`POST /api/join` and the `signups` table are unchanged. The allowed product ids are now the catalog
slugs plus the old `merch` and the new `everything` (footer sign-up). The bag sends one signup per
product. Old URLs keep working: `/hibernator`, `/eyelid`, `/merch`. `?v=` source tracking rides on
every internal link as before.

## Quality floor

Mobile first (TikTok in-app browsers), no horizontal scroll at 390 px, reduced motion respected
(meadow wind off, view transitions off), keyboard focus visible, works without JS (product pages
fall back to the plain waitlist form). Page weight before first paint ~250 kB gzipped including
fonts; the meadow (145 kB) loads after.
