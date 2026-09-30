---
name: ui-graphics-assets
description: Create or edit pokeemerald UI graphics - PNG tilesets and sprites, JASC .pal palettes, and .bin tilemaps (text box frames, healthboxes, battle backgrounds, menu panels). Covers GBA format constraints, how the build converts assets (INCGFX, graphics_file_rules.mk), palette slots, and checking the result visually. Use when changing or adding any image, palette or tilemap used by a screen.
---

# UI graphics assets

## Format rules (the build rejects or garbles anything else)
- **PNG, indexed color.** 4bpp = at most **16 colors**; 8bpp only where the code loads 8bpp (rare in UI).
- **Palette index 0 is transparent** (BG and OBJ alike). Keep it an unused "key" color, and never paint visible pixels with it.
- Width and height must be **multiples of 8** (tiles are 8×8).
- Colors are stored as 15-bit (5 bits per channel), so the 8-bit values are truncated. Pick colors that survive `>> 3`.
- Pixels sharing one 4bpp palette must use the same 16-color palette. Keep the PNG's palette order equal to the in-game palette,
  because the index matters, not the RGB.
- Fonts are 2bpp PNGs in `graphics/fonts/`: 0 = background, 1 = foreground, 2 = shadow.

## How assets get into the ROM
- Most assets are converted on demand by `INCGFX_U32/U16/U8("path.png", ".4bpp.lz", "<gbagfx args>")` in `src/graphics.c`
  (and other data files). Extensions: `.4bpp` / `.8bpp` tiles, `.gbapal` palette, `.lz` LZ77 compressed, `.bin` tilemap.
  Args like `-mwidth 8 -mheight 4` set the metatile (sprite frame) size in tiles, so the PNG stays a visual layout.
- Special cases are rules in `graphics_file_rules.mk`, e.g. `textbox.gbapal` is `textbox_0.gbapal` + `textbox_1.gbapal`
  concatenated (two 16-color banks → BG palette slots 0 and 1). If a `.gbapal` is built from several `.pal` files, edit the sources.
- `.pal` files are JASC text (`JASC-PAL`, `0100`, count, then `R G B` lines 0–255).
- Tilemaps (`.bin`): 16-bit entries = tile index (bits 0–9) | hflip (10) | vflip (11) | palette bank (12–15).
  Maps wider/taller than 32 tiles are stored as 32×32 screenblocks. Edit them with **Tilemap Studio** (GBA 4bpp mode).
  Never hand-edit the binary.

## Where a screen's assets are loaded (to know slots and sizes)
Grep the screen's code for `LZDecompressVram(..., BG_CHAR_ADDR(n))` (tiles → char base n),
`CopyToBgTilemapBuffer` / `BG_SCREEN_ADDR` (tilemaps), `LoadPalette` / `LoadCompressedPalette(..., BG_PLTT_ID(n), size)`
(BG palette slot n, size/32 banks) and `OBJ_PLTT_ID` / sprite palette tags for sprites.
Adding tiles to a tileset can collide with window `baseBlock` ranges in the same char base. Check them with
`python .claude/skills/add-ui-window/window_vram.py <file>`.

## Workflow
1. Copy the existing asset and edit it in an indexed-color editor (Aseprite, GraphicsGale, or GIMP in indexed mode) without
   changing the palette order. Keep the same dimensions unless the code (sheet size, OAM shape, tilemap) changes with it.
2. Check the file: `python -c "import struct;d=open('path.png','rb').read();print(struct.unpack('>IIBB',d[16:26]))"` prints
   (width, height, bitdepth, colortype). You want colortype 3 (palette) and bitdepth 4 or 8.
3. Preview it with no build. `../gba-ui-preview` renders battle assets straight from the PNG/.pal/.bin and hot-reloads when you save.
   Run its check with a screenshot: `cd ../gba-ui-preview && python .claude/skills/preview-check/check.py pokeemerald-battle.json --screenshot <png>`.
   Magenta pixels there mean palette index/bank problems.
4. Build (build-rom skill) and confirm in the emulator.
