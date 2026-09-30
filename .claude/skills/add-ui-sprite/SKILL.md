---
name: add-ui-sprite
description: Add or change a sprite-based (OAM) UI element in pokeemerald, e.g. an icon, badge, cursor, indicator, healthbox part or anything that moves, animates or overlaps text. Covers graphics declaration (INCGFX), sprite sheets and palettes with tags, OAM shape/size, CreateSprite coordinates, priority vs BG layers, callbacks, and freeing resources. Use when the new UI piece should be a sprite rather than a window.
---

# Adding a sprite UI element

Reference code: healthboxes in `src/battle_interface.c` (`CreateBattlerHealthboxSprites`,
`InitBattlerHealthboxCoords`, `SpriteCB_HealthBoxOther`), and the VS letters in `src/battle_bg.c`.

## 1. Graphics
1. Add the PNG under `graphics/<area>/`. It must be **indexed, ≤16 colors (4bpp)**, with **index 0 = transparent**
   and width/height multiples of 8. See the ui-graphics-assets skill.
2. Declare it in `src/graphics.c`. The build converts it automatically via `INCGFX`, with no Makefile rule needed:
   ```c
   const u32 gMyIconGfx[] = INCGFX_U32("graphics/<area>/my_icon.png", ".4bpp.lz");
   const u32 gMyIconPal[] = INCGFX_U32("graphics/<area>/my_icon.png", ".gbapal.lz");
   // multi-frame / metatiled sheets: pass the frame size in tiles so the PNG stays laid out visually
   const u32 gMyBarGfx[] = INCGFX_U32("graphics/<area>/my_bar.png", ".4bpp.lz", "-mwidth 8 -mheight 4");
   ```
   `.lz` → load with `LoadCompressedSpriteSheet` / `LoadCompressedSpritePalette`. Without `.lz`, use `LoadSpriteSheet` /
   `LoadSpritePalette` (then declare as `INCGFX_U16`/`u8` arrays matching the struct).
3. Add `extern` declarations in `include/graphics.h`.

## 2. Sheet, palette, template
```c
#define TAG_MY_ICON 0x5A00   // pick an unused tag: grep "TAG_" / "0x5A00" to check
static const struct CompressedSpriteSheet sSpriteSheet_MyIcon = { gMyIconGfx, 32 * 32 / 2, TAG_MY_ICON }; // bytes = w*h/2 for 4bpp
static const struct CompressedSpritePalette sSpritePal_MyIcon = { gMyIconPal, TAG_MY_ICON };
static const struct OamData sOam_MyIcon = { .shape = SPRITE_SHAPE(32x32), .size = SPRITE_SIZE(32x32), .priority = 1 };
static const struct SpriteTemplate sSpriteTemplate_MyIcon = {
    .tileTag = TAG_MY_ICON, .paletteTag = TAG_MY_ICON, .oam = &sOam_MyIcon,
    .anims = gDummySpriteAnimTable, .images = NULL, .affineAnims = gDummySpriteAffineAnimTable,
    .callback = SpriteCallbackDummy,
};
```
- The sheet size must be the full decompressed size of all frames, or tiles get cut off / overwrite others.
- Valid OAM sizes: 8x8, 16x16, 32x32, 64x64, 16x8, 32x8, 32x16, 64x32, 8x16, 8x32, 16x32, 32x64.
  Larger art = several sprites (like the healthbox: two 64×32 sprites, the second at x+64 with `oam.tileNum += 32`).

## 3. Create, position, layer
```c
LoadCompressedSpriteSheet(&sSpriteSheet_MyIcon);
LoadCompressedSpritePalette(&sSpritePal_MyIcon);
spriteId = CreateSprite(&sSpriteTemplate_MyIcon, x, y, subpriority);
```
- `x, y` is the sprite **center** (the engine subtracts half the size), not the top-left.
- Layering: `oam.priority` 0–3 against BG priorities (lower = front). A sprite with priority p is drawn in front of
  BGs whose priority is ≥ p. Battle BG0 (the text box) is priority 0, so a priority 1 sprite goes **under** the text box
  and over the battle scene. Among sprites, lower `subpriority` is in front.
- Move with `gSprites[id].x/y` (or `x2/y2` offsets for bounce/shake). Hide with `gSprites[id].invisible = TRUE`.
- Follow another sprite with a callback, as `SpriteCB_HealthBoxOther` copies the main sprite's x+64/y.

## 4. Lifetime
- Free what you load: `DestroySpriteAndFreeResources(&gSprites[id])` frees tiles and palette by tag. Or use `DestroySprite` plus
  `FreeSpriteTilesByTag` / `FreeSpritePaletteByTag` when other sprites still use them.
- Screens that tear down and rebuild (battle → Bag/Party → back through `src/reshow_battle_screen.c`) must recreate your
  sprite and reload its sheet/palette there too.
- Palette slots: only 16 OBJ palettes exist and battle uses many (mons, healthboxes, animations). Always load by tag and
  check `IndexOfSpritePaletteTag(tag) != 0xFF`. Share palettes with a matching tag when possible.
- Sprite count and OBJ VRAM are finite. In battle, animations need headroom, so avoid permanent large sprites.

## 5. Preview, build, document
- Preview the position in `../gba-ui-preview`: add a sprite entry to the screen's config with `"center"` pulled from your code
  (`initializer` / `regex` var), then run its preview-check skill.
- Build with the build-rom skill, test in the emulator (appear, move, hide, return from menus, several battles in a row),
  and document it with the document-feature skill.
- C89: declare locals first. Keep new EWRAM state tiny (EWRAM is ~95% used).
