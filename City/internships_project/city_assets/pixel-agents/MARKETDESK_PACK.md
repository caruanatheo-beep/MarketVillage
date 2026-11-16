# MarketDesk City graphics pack

The MarketDesk additions use the current Pixel Agents renderer, furniture catalog, depth sorting, and walkable tile map.

- `MARKET_TRADING_DESK`: custom 64Ã—32 pixel workstation with four quote monitors, keyboard, phone, task lamp, cable channel, drawer fronts, and a restrained status strip. It uses the renderer's regular furniture footprint and collision handling.
- Floors: a subtle grayscale wood-plank texture for Global Markets, low-contrast carpet weaves for offices, a smooth brushed-stone corridor with no tile grid, and restrained threshold inlays at doorways. Pixel Agents applies each room's existing color tint.
- Architecture: 16 native 16-by-16 wall modules auto-connect into slim anthracite-framed glass partitions, including straight runs, ends, corners, and junctions. Matching 96-by-32 panoramic window modules align across office fronts; single and double open glass-door overlays mark existing entrances.
- Collision and movement: walls remain the same `WALL` collision cells; glass doors and windows are visual-only background overlays. The walkable openings and pathfinding grid are unchanged.
- Partitions and chairs: connected glass walls use fine continuous metal rails instead of a repeated pane grid; wider ergonomic seats are centered under the four-screen workstations while retaining a one-tile walkable footprint.
- Lighting: corridor guides and room outlines keep their cyan/violet identity with tighter, more restrained bloom for clearer room boundaries.
- Room furnishings: Pixel Agents sofas, cushioned chairs and benches, coffee tables, bookshelves, plants, lamps, whiteboards, and paintings are loaded from the bundled furniture manifests and placed in the Head of Desk, work rooms, and corridors.
- Live market and internship panels remain linked to the existing Markets and Internship Tracker endpoints; no market values are drawn into the furniture sprites.

The bundled Pixel Agents assets retain their original license and attribution in `LICENSE`, `assets/PIXEL_AGENTS_LICENSE.txt`, and `assets/ATTRIBUTION.txt`.

## Golf Practice terrace

The current Manhattan variant renders green synthetic turf from `assets/tower/turf.png`; timber and stone terrace assets are not used on the golf surface.

`assets/furniture/MARKETDESK_GOLF/` contains nine original transparent PNG sprites and its own manifest: right-facing practice mats, clubs/bag, ball basket, putting green, warm lantern, bench, planter, skyline/protective net and timber decking. Regenerate with `scripts/generate_golf_assets.py` (Pillow). Native pixel size remains 16 px per tile, without interpolation.

The five mats are reserved independently by `GolfPractice.ts`. The terrace shares the office tile map, depth sorting, character sheets, collisions and pathfinding, through a central Career Desk glass doorway. `worldGeometry.ts` removes two unused rows from Markets, Research and the atrium; the lower rooms, lights and terrace move upwards together.

Golf is explicitly ambient leisure, never a backend mission or tool call. Only agents whose latest known server state is idle/completed/cancelled and who have no queued/running/approval task may visit. Any new task interrupts the break immediately; the agent walks back to its unchanged assigned workstation. Delegation visitors take priority. Stale server state stops new breaks. No LLM call, database migration, persistent schedule or cost is added.

`npm run build` validates all furniture and 70 round-trip routes, mat reservations, swings, interruption without teleportation and stale-state handling. `check_golf_preview.py` runs the real canvas loop against the isolated browser fixture and captures desktop/mobile images without contacting external services.

## Manhattan tower architecture

`assets/tower/` contains nine original modular PNG assets generated with `scripts/generate_tower_assets.py`: three skyline buildings, a curtain-wall facade, glass railing, stairs, decorative LED sign, stone terrace and raised planter. These graphics are drawn individually by `TowerArchitecture.ts`, using the same world coordinates and camera as Pixel Agents. They are not a full-scene background image. Decorative charts do not represent live prices; the existing interactive market and opportunity panels still use their existing data connections.

Skyline and podium fronts are clipped to non-walkable sky cells. Both penthouse garden terraces are navigable extensions of the tile map; the planters sit on their parapets. Build validation checks outward and return paths for both terraces. The height is a graphical 2D illusion, not an additional simulated floor or 3D engine. No backend, database or AI tool changes are required.

## Tower identity pass — 1 November 2026

`scripts/generate_tower_identity.py` produces nine additional original, transparent PNG modules: double-height atrium, corner return, balcony glazing, hanging garden, two LED fins, lobby entry, glass bridge and protective practice net. These are drawn at native resolution with Pillow; they contain no copied reference pixels. Decorative signage contains architectural copy only, never fabricated market quotes. The existing Pixel Agents license continues to apply to its original characters and bundled furniture.

The former continuous south gallery is replaced by three short connected landings. The Tech Lab landing stays three tiles wide so agents can bypass the lounge table above it. New facade decoration occupies non-walkable surfaces; the central bridge, doors and terrace entrances retain their real navigation coordinates. Directional contact shadows are clipped to floor cells.

`scripts/verify_tower_visual.py` uses the isolated `preview-command.mjs` server on port 7878, intercepts feeds with explicitly labelled fixtures, and verifies panel pagination, keyboard navigation and metadata tooltips at 1920×1080 and 1366×768. It never invokes the backend collectors or LLMs. Final screenshots are in `artifacts/tower-ten-final-*.png`.

### Object silhouette pass

The identity generator now also writes an original stepped penthouse crown, terrace topiary and glazed entrance canopy (12 tower modules in total). Topiary is registered as `MD_TERRACE_TOPIARY` with three background rows and a blocking two-tile pot footprint; paths to both terraces remain checked. `MD_NETWORK_WORLD_MAP` adds a wall-mounted, nonblocking original graphic above the new five-seat round conference table. The furniture generator draws distinct crescent executive/trading workstations and a four-seat Research meeting table without changing their original footprints. Updated golf lamps keep their existing footprints; the light pool now matches each bulb's world position.

The fixed camera includes the projecting roof crown. Latest browser captures use `artifacts/tower-objects-final-*.png`; the earlier captures remain available for comparison.

### Perspective and structural lighting pass

`TowerPerspective.ts` applies one progressive 2D projection to the playable world and the inverse mapping to agent/workstation hit tests. The distant canyon and the two front-facing data panels remain on separate planes. Depth is simulated with converging planes, extruded slab edges, oblique side returns, full-height piers and clipped cast shadows; this is not a 3D engine. `worldGeometry.ts` also merges the redundant intermediate landing and shortens facade gaps; path validation covers the resulting grid.

The Pixel Agents renderer has an optional native-resolution static-floor cache, leaving the original rendering path available to other callers. Furniture and moving characters remain depth-sorted live; no task animation is baked. Broad lighting uses soft light plus restrained screen emission to retain material contrast. Latest verified captures: `artifacts/tower-perspective-final-*.png`.


### Compact office framing

The default console width is 340 px and the desktop header reserves 66 px. A reversible display projection compresses only the facade gaps and the outdoor practice strip; indoor room/character proportions and all navigation coordinates stay unchanged. Canvas picking applies the inverse vertical projection before the existing horizontal perspective. Billboards stay on their readable frontal plane, inside the visible map width. The native world is rendered into a taller offscreen canvas before compression to avoid clipping the golf area.

Validated with the layout build (all seven seats and 70 golf return paths), projection round trips, and browser interaction checks at 1920x1080, 1366x768 and DPR 2. Validation screenshots: `artifacts/tower-larger-offices-*.png` (isolated test fixtures).


### Golf proportion fix

Supersedes the compact office framing note: vertical display compression is removed entirely. Characters, golf mats and the entrance keep their native height at every world coordinate. The world itself now has 38 rows instead of 43: three redundant penthouse facade rows and two additional intermediary rows have been removed. Stair connectors and architecture anchors follow the same layout mapping. Regression checks assert unchanged sprite height across old compression boundaries, doorway and golf; the normal route and swing checks still run at build time.

### Connected structure repair

`TowerArchitecture.buildTowerStructure` now derives exterior edges and contiguous glass wall runs from the final tile map. It supersedes the independently positioned slab fronts, clipped full-height corridor images and per-row side returns described above. Native original modules `md_corridor_pier.png` (16x48), `md_glass_transom.png` (64x16) and `md_slab_edge.png` (64x9) are reproducible with `scripts/generate_connected_structure.py`. Final modules are cropped at junctions, never stretched. Interior glazing stops at actual doors; panorama furniture is restricted to supported north walls.

Shifted room interiors and the access gallery have continuous real floors. The wood finish uses one world-aligned surface clipped to those tiles. Build checks cover plate continuity, facade attachment, wall/door alignment, window support and agent routes. `scripts/verify_tower_visual.py` checks the actual cached canvas for transparent floor holes, loaded assets, hit tests and browser errors at 1920x1080 and 1366x768 (including DPR 2). Screenshots `artifacts/tower-connected-structure-*.png` use explicitly marked isolated fixtures, with no collection, LLM call or external message.


### Asymmetric tower layout

`worldGeometry.wingPosition` shifts the real Markets floor and furnishings two columns to the left, Research one row back, and Tech Lab one column left. Walkable connectors, shifted seat assertions and floor-clip rendering keep the visible layout consistent with collision and routing. The lower wings also have stepped floor cuts. Five original transparent modules are generated by `scripts/generate_tower_facades.py`: penthouse glazing, atrium canopy, setback balcony, facade bay, and the frontal MARKETDESK CITY sign. The data panels continue to use real server data. The engine remains 2D: glazed terraces and facade volumes suggest depth without changing agent dimensions or golf geometry.


### Glass corridors (historical, no longer rendered)

`scripts/generate_glass_corridors.py` creates two 32 x 304 pixel-art facade elevations beside the atrium. They use metal frames, blue glass, reflections and warm lights. The architecture renderer clips them to structural wall cells, leaving playable floors and doors unobscured; collision data is not altered.

Facade alignment: exterior side returns follow the outer floor boundary row by row. North glazing ends at the north edge of each shifted room. Horizontal perspective now tapers from 72% at the summit to 100% at the base; native vertical dimensions and inverse pointer transforms are preserved.

### Restrained glass partitions (supersedes flat corridor overlays)

Ten architectural corrections: (1) restore physical upper-room dividers, (2) close south room boundaries with explicit doors, (3) replace opaque blue fills with translucent blue-grey glass, (4) remove repeating diagonal reflection patterns, (5) use thin anthracite caps and sills, (6) provide all 16 connected corner/T/cross/end sprites, (7) anchor side doors on their final two-row collision openings, (8) use matching two-column portals for front entrances, (9) remove the double wall above Tech Lab and keep indoor foundations under the glazing, (10) retain actual facade attachment, depth sorting, contact shadows and path tests.

The original 16x24 `tower/md_partition_*.png` sprites are loaded by the existing Pixel Agents auto-wall renderer, with bottom anchors and live character occlusion. Four door sprites have native front/side proportions. The generator asserts translucent panes and clear portal centres; layout checks assert physical walls, passages, supported windows and all seven workstation/golf routes. Browser checks also verify that the old flat pier/transom overlays are no longer loaded. New material URLs use `partitions-5` to invalidate old cached drawings. No backend changes or real LLM calls are part of this visual pass.

### Connected office boundaries ? 2 November 2026

Partitions close their corners on the final projected grid, including the south office boundary. Front and side portals occupy the actual navigation openings; the Research/gallery and Interview/Innovation passages now have explicit frames. City glass doors use the same bottom anchor as raised wall tiles, and the generated frames share rail heights and full-width endpoints. `check-layout.mjs` verifies door jamb neighbours, passable openings, sprite anchors and corner cells alongside all nine workstation routes. `scripts/generate_connected_structure.py` checks translucent glass, clear openings and rail alignment.

### Visual readability pass ? 2 November 2026

Five applied priorities: quieter skyline contrast; softer amber lighting and screen reflections; screen-space room plaques that stay legible under perspective; a cyan name/position marker following the selected agent; compact empty cockpit states to leave room for results. Selection and room labels reuse the scene projection. Lighting remains decorative, independent of mission status. Browser checks cover desktop, short viewport and mobile cockpit interactions with fixture data only.
