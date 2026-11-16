# MarketDesk evening office pack

Original programmatic pixel art in `../pixel-agents/assets/furniture/MARKETDESK_PACK/premium/`.
41 transparent PNG furnishing/architecture modules, two textile textures,
a seamless 192 x 96 honey-oak floor and a transparent 16 x 24 amber luminaire.
Native dimensions and collision footprints are preserved. No reference-image background is used.

Regenerate from repository root:
`node internships_project/city_assets/marketdesk_pack/generate_premium.mjs`

Run this after the legacy `generate_assets.mjs` if rebuilding the entire base pack.
The premium generator is idempotent and updates the existing manifest paths.

Includes oak workstations, blue-grey upholstered seating with linen cushions, plant-decorated tables, bookcases,
career/economic boards, servers, panoramic glazing and sixteen glass junctions.
Textiles are nonblocking floor overlays; furniture keeps its original collision data.
Generated sprites use `_night_v4.png` paths to invalidate previously cached images.
The renderer combines these assets with contact shadows and cached, room-clipped
amber/cyan lightmaps, including parquet reflections. There is no global darkening
overlay. Three additional luminaires illuminate the central lounge. These decorative lighting layers do not modify
collisions, agent status or task execution. Oak grain stays aligned across rooms.
The generator uses source-over alpha compositing, so translucent texture details
never punch holes through an opaque furnishing or rug.
The latest set includes two new furniture entries: a four-chair Research meeting
table and a five-chair Network conference table. They replace objects within
the existing validated footprints. Desks include warm lamps; the executive desk
uses walnut, with four supervision screens above it. Research and Outreach boards
have distinct economic-chart and messaging artwork. Window panes use skyline
night silhouettes and restrained reflections. Upholstery uses sage linen and
blue-grey fabric, while the executive desk has walnut drawers and a leather inset.
These drawn screen graphics are decorative,
not live market data; the connected Market Brief widget remains separate.

Validation: frontend build checks asset dimensions, furniture bounds, overlaps,
and bidirectional paths to all seven fixed workstations. `preview-premium.mjs`
serves the actual renderer on localhost:7877 with empty data and no backend calls.
It is a visual fixture, not a substitute for authenticated integration testing.

`check-night-lighting-browser.mjs` checks the command center at desktop/mobile sizes
and samples the lightmap to verify amber illumination, preserved unlit areas and
restored canvas compositing. The surrounding UI uses deep navy and saturated blue
selection states. Palette sampling of the supplied Cozy Night Office reference
(16-level RGB quantization) found dominant interface bins #001020/#001030 and
warm wood bins #A06030/#C07030. Copper/honey oak and stronger orange light pools
use those hues while retaining readable foreground text and unlit floor detail.

Desk rendering correction (2026-11-01): rasterize sprites at native resolution,
then scale once with nearest-neighbor sampling. Drawing individual pixels at a
fractional zoom introduced translucent seams and washed out the entire palette.
A Chromium regression using a solid 32 x 16 sprite found 0/831/1075/1440 damaged
pixels at zoom 1/1.37/1.61/2.25 before the fix, and zero at every scale afterwards.
Small monitor plots now calculate their vertical range from the actual available
height; fixed margins previously flattened the curves. Desks use copper oak,
walnut and dark navy bezels. Amber light pools are smaller and more saturated,
and cyan spill falls below the screens instead of whitening their faces.
The loader versions only MarketDesk pack images to refresh the regenerated PNGs.

Validation after this correction: TypeScript/build, all seven workstation routes,
Chromium raster and lightmap assertions, and desktop/mobile browser checks passed.
Visual capture: `artifacts/command-center/wide-chat.png` (frontend test fixture;
no live market collection or LLM call). The reference is an art-direction target,
not an exact match for the native-resolution Pixel Agents sprites.

Interior and furnishings pass (2026-11-01): the six lower window modules now use
the new `MD_INTERIOR_GLASS_BAND` asset, with transparent glazing, mullions and
frosted stripes instead of an exterior skyline. Upper facade windows remain.
New upholstery drawings add padded backrests, armrests, feet and cushions to the
sofa, chaise and armchair; rugs have woven borders, corner motifs and fringe.
Server racks now have beveled cabinets, rack-mounted modules, vents and LEDs.
The Career board has distinct tracking columns and cards; its cabinet includes
folders, drawers and handles. Screen, board and server light pools remain purely
decorative and never represent real task status or live data.

Furniture footprints are unchanged. Build validation passed for all seven
workstations (14 bidirectional engine routes). Chromium checks passed at
1920x1080, 1366x768 and 390x844, including navigation, layout and lighting checks.
The wide capture was visually inspected; browser checks use isolated fixture
data and do not exercise live AI calls or external collections.
