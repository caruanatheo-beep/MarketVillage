# MarketDesk Pixel Floor asset pack

This directory contains the source generator for the original MarketDesk City furniture pack. It writes transparent, nearest-neighbour pixel PNGs at the game's native 16 px tile scale into `city_assets/pixel-agents/assets/furniture/MARKETDESK_PACK/`.

## Included assets

- **Global Markets:** four-screen trading station and market ticker.
- **Research:** analytics workstation and economic chart board.
- **Tech Lab:** coding workstation and server rack.
- **Career Desk:** offer-review workstation and opportunities board.
- **Network:** collaboration workstation and meeting table.
- **Outreach:** communications workstation, contact dashboard and desk phone.
- **Head of Desk:** six-screen executive console, supervision wall, executive library and chair.

The PNGs are drawn from pixel primitives in `generate_assets.mjs`; they are not resized Pixel Agents furniture. The JSON manifest records each sprite's pixel dimensions, tile footprint, placement flags and collision behavior. Wall displays use `backgroundTiles: 1`, so their artwork appears on the wall while the tile remains walkable. Workstations and floor furniture use their defined footprints for collision and pathfinding.

## Regenerate

From the repository root, run:

```powershell
node internships_project/city_assets/marketdesk_pack/generate_assets.mjs
node internships_project/city_assets/marketdesk_pack/validate_assets.mjs
```

The React renderer loads the manifest and PNGs through `/city/pixel-assets/furniture/MARKETDESK_PACK/`.
