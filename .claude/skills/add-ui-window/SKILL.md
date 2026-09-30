---
name: add-ui-window
description: Add or change a text/panel UI component drawn into a window (WindowTemplate + FillWindowPixelRect / AddTextPrinter) in pokeemerald, e.g. an info box, stat panel, extra label or custom menu on the battle screen, summary screen, bag or party menu. Covers window IDs, placement on scrolled BGs, choosing baseBlock without VRAM collisions, palette slots, drawing, show/hide toggles, redraw hooks after menus, and preview before building. Use for any new on-screen box, text or panel that isn't a sprite.
---

# Adding a window-based UI component

Worked examples in this repo, which you should read before starting:
- `docs/features/wild_battle_iv_box.md` covers a new battle window with a custom palette, a code-drawn frame, a SELECT toggle and redraw hooks.
- `docs/features/iv_ev_summary_screen.md` covers reusing summary-screen windows, per-line colored text and a mode indicator.

## 0. Decide: window or sprite?
- **Window** (this skill): text, numbers, and boxes that are drawn once and change occasionally. It lives on a BG layer and scrolls with it.
- **Sprite** (see add-ui-sprite): anything that moves, animates, bounces, or must sit over BG0 text, e.g. cursors, icons, healthboxes.

## 1. Find the screen's window + BG setup
Grep the screen's file for `struct WindowTemplate`, `struct BgTemplate`, `InitWindows`, `AddWindow`,
`LoadPalette`/`LoadCompressedPalette(..., BG_PLTT_ID(n), ...)` and the BG scroll (`gBattle_BG0_Y`, `SetGpuReg(REG_OFFSET_BGnVOFS ...)`, `ChangeBgY`).
Screens differ:
- **Battle** (`src/battle_bg.c`): one fixed array `sStandardBattleWindowTemplates`, indexed by `B_WIN_*` in
  `include/constants/battle.h`. Add your ID before the array's `DUMMY_WIN_TEMPLATE`. The arena array
  `sBattleArenaWindowTemplates` shares IDs, so check whether it needs an entry too.
- **Summary screen**: template lists such as `sPageSkillsTemplate`, used through `AddWindowFromTemplateList`.
- **Menus / other screens**: often `AddWindow(&template)` at runtime, which returns the id; free it with `RemoveWindow`.

## 2. Place it: `tilemapTop/Left` are BG tilemap cells, not screen pixels
If the BG scrolls, convert: `tilemapTop = screen_y/8 + scrollY/8`. Battle BG0 is a 32×64 map with three pages:
rows 0–19 are messages (`gBattle_BG0_Y = 0`), rows 20–39 the action menu (160), rows 40–59 the move menu (320).
A window placed on a page appears only while that page is scrolled in, with no show/hide code needed.
Size `width × height` in tiles must cover the drawn box plus any shadow.

## 3. Choose `baseBlock` (VRAM tiles): run the checker
```
python .claude/skills/add-ui-window/window_vram.py src/battle_bg.c --array sStandardBattleWindowTemplates --need <width*height>
```
It prints every window's absolute tile range, **VRAM overlaps across BGs** and free gaps, plus suggested baseBlocks.
- BGs that share a char base, or whose tiles spill into the next char block, share VRAM. In battle, BG0 tiles past
  `0x200` land on BG1/BG2's char base 1, which also holds **battle animation BG graphics** and the VS/level-up windows.
  Anything there can be overwritten during animations, so redraw your window when the turn starts (as the IV box does).
- An overlap is acceptable only if the two windows are never on screen or in VRAM at the same time. Justify it in the doc.
- Low tile numbers hold the BG's own tileset (e.g. the battle textbox tiles at the start of char base 0).
- Record the chosen range in a comment: `.baseBlock = 0x01f8,  // 90 tiles -> 0x01F8-0x0251`.

## 4. Palette
Either reuse an existing text palette slot (battle: slot 5 = `gBattleWindowTextPalette`) or load your own 16 colors:
```c
#define MYBOX_PAL_SLOT 12
static const u16 sMyBoxPalette[16] = { [0] = RGB(0, 0, 0), [1] = RGB(31, 31, 26), ... }; // 5-bit channels
LoadPalette(sMyBoxPalette, BG_PLTT_ID(MYBOX_PAL_SLOT), sizeof(sMyBoxPalette));
```
Pick a free slot. Grep `BG_PLTT_ID(` in the screen's files; the IV box doc lists battle usage (0–1 textbox,
2–4 environment, 5 text, 6 VS, 7 arena, 8–11 animations, 12 IV box). **Reload the palette in your draw function**, because menus
reload BG palettes. Index 0 is transparent on BGs. Name color indices with an enum and use them in `PIXEL_FILL()` and the text color triples.

## 5. Draw
```c
FillWindowPixelBuffer(win, PIXEL_FILL(0));                        // clear (transparent)
FillWindowPixelRect(win, PIXEL_FILL(COLOR_FILL), x, y, w, h);     // boxes, borders, shadows
AddTextPrinterParameterized4(win, FONT_SMALL_NARROW, x, y, letterSpacing, lineSpacing,
                             colors /* {bg, fg, shadow} */, TEXT_SKIP_DRAW, str);
PutWindowTilemap(win);                                             // write the window's cells into the BG tilemap
CopyWindowToVram(win, COPYWIN_FULL);                               // upload pixels + map
```
- To hide: `FillWindowPixelBuffer(win, PIXEL_FILL(0))` + `PutWindowTilemap` + `CopyWindowToVram`, or `ClearWindowTilemap(win)` + `CopyWindowToVram(win, COPYWIN_MAP)`.
- Text glyph cells paint their background color over their full height (~12–13 px for small fonts), so keep rows at least that far apart.
- Right-align text with `GetStringWidth(font, str, letterSpacing)`.
- Numbers: `ConvertIntToDecimalStringN(buf, v, STR_CONV_MODE_RIGHT_ALIGN, digits)`. Colors inline in strings: `_("{COLOR RED}{SHADOW LIGHT_RED}...")`.
- Draw frames **after** text if glyph backgrounds could cover them.

## 6. State, input, lifecycle
- Flags: `EWRAM_DATA static bool8 sShowX = FALSE;`, or a spare/`filler` field in the screen's struct (the summary screen
  reused `filler40CA`). **EWRAM is ~95% and IWRAM ~94% full**, so keep state tiny and prefer reusing filler bytes.
- Reset state where the screen or battle starts (e.g. next to `sShowEnemyIVBox = FALSE` in battle init).
- Input: add a `JOY_NEW(SELECT_BUTTON)` branch in the screen's input handler (battle action menu:
  `HandleInputChooseAction` in `src/battle_controller_player.c`). Check it doesn't steal an existing binding,
  e.g. SELECT swaps moves in the move menu. `PlaySE(SE_SELECT)` only when the action happened.
- Redraw hooks: everything that rebuilds VRAM must redraw you. For battle, that's the turn start (`BattleTurnPassed`,
  `TryDoEventsBeforeFirstTurn`) and returning from Bag/Party/Summary (`CB2_ReshowBattleScreenAfterMenu` in
  `src/reshow_battle_screen.c`). Cross-file calls need a prototype in the matching `include/*.h`.

## 7. C rules that bite (agbcc, C89)
- Declare all locals at the top of a block, before any statement.
- `_("...")` is an array initializer, not an expression, so declare `static const u8 sText_X[] = _("...");` and pass `sText_X`.
- Build strings with `StringCopy` (overwrites) vs `StringAppend` / `StringExpandPlaceholders` deliberately. Printing each piece separately is safest.
- Don't use `//`-less multi-line macros or C99 features (`for (int i...)`, `bool`, designated compound literals in code).

## 8. Preview before building
The sibling tool `../gba-ui-preview` renders the screen from source. For battle, `configs/pokeemerald-battle.json` already
shows all `sStandardBattleWindowTemplates` entries as outlines and has a "drawn panel" for the IV box.
- A new window shows up automatically as an outline. Toggle it with its swatch in the Windows list.
- To see the actual pixels of a code-drawn box, add a panel (see `gba-ui-preview/.claude/skills/mock-drawn-panel`).
- Validate + screenshot: `cd ../gba-ui-preview && python .claude/skills/preview-check/check.py pokeemerald-battle.json --mode "Text box=Action menu" --screenshot <png>`.

## 9. Finish
Build with the build-rom skill, write the in-game test checklist, and document it with the document-feature skill.
