# Wild Battle IV / Nature Box

During wild battles, pressing **SELECT** on the FIGHT/BAG/POKéMON/RUN menu shows or hides a panel under the enemy healthbox. The panel shows the opposing Pokémon's **nature** and all six **IVs**. It's styled like the healthbox: a cream fill, a dark 2px rounded border and a drop shadow at the bottom-right. The stat the nature raises is drawn in **red**, and the one it lowers in **blue**.

The box starts **hidden** at the start of every battle. Once shown, it stays shown for the rest of that battle, turn after turn, until SELECT is pressed again.

```
┌──────────────────────┐
│ ADAMANT          IVs │
│ HP  31  ATK 31  DEF 31│
│ SPA 31  SPD 31  SPE 31│
└──────────────────────┘▒
```

`SPD` = Sp. Def, `SPE` = Speed. These abbreviations keep the three columns inside the 100px box.

Files touched:

| File | Change |
|---|---|
| `include/constants/battle.h` | `B_WIN_ENEMY_IV` window ID |
| `src/battle_bg.c` | Window template in `sStandardBattleWindowTemplates` |
| `src/battle_main.c` | Palette, colors, strings, `sShowEnemyIVBox`, `DrawIvBoxFrame`, `DrawIvBoxStat`, `DrawEnemyIVs`, `ToggleEnemyIVBox`, and the turn-start hooks |
| `include/battle_main.h` | `DrawEnemyIVs` and `ToggleEnemyIVBox` prototypes |
| `src/battle_controller_player.c` | SELECT handler on the action menu |
| `src/reshow_battle_screen.c` | Redraws the box after returning from the Bag/Party menu |

The feature is UI-only. It reads data with `GetMonData` and changes no save data.

---

## 1. How battle BG0 works (read first)

The GBA has two rendering systems:

- **Sprites (OAM):** Pokémon, healthboxes, HP bars and the menu cursor. They sit at fixed screen coordinates.
- **Background layers (BG0–BG3):** text and panels, drawn into tile grids. BG0 is the battle UI layer.

BG0 uses a **32×64-tile** tilemap (`screenSize = 2`). The game packs three "screens" into it and scrolls `gBattle_BG0_Y` to pick one:

| Battle phase | `gBattle_BG0_Y` | Visible tilemap rows |
|---|---|---|
| Battle messages | `0` | 0–19 |
| Action selection (FIGHT/BAG/POKéMON/RUN) | `160` | 20–39 |
| Move selection | `320` | 40–59 |

So **`tilemapTop` is not a screen coordinate**. For the box to show during action selection, use:

```
tilemapTop  = screen_y_pixels / 8 + 20
tilemapLeft = screen_x_pixels / 8
```

Because of this, the box (when toggled on) only appears on the action menu. During messages, animations and move selection it's scrolled off-screen automatically, with no extra code.

---

## 2. Window ID

`include/constants/battle.h`, after `B_WIN_VS_OUTCOME_RIGHT`:

```c
#define B_WIN_ENEMY_IV           24
```

---

## 3. Window template

`src/battle_bg.c`, inside `sStandardBattleWindowTemplates`, before `DUMMY_WIN_TEMPLATE`:

```c
[B_WIN_ENEMY_IV] = {
    .bg = 0,
    .tilemapLeft = 1,     // screen x = 8px
    .tilemapTop = 26,     // screen y = (26 - 20) * 8 = 48px during action selection
    .width = 13,          // 104px: 100px box + 3px shadow + 1px spare
    .height = 5,          // 40px:  36px box + 3px shadow + 1px spare
    .paletteNum = 12,     // custom palette, see section 4
    .baseBlock = 0x01f8,  // 65 tiles -> 0x01F8-0x0238
},
```

### Choosing `baseBlock`

The window needs `width × height` = **65 tiles**. They must not overlap any BG0 window that is drawn while the box is on screen, or while it stays in VRAM:

| Window | baseBlock | Tile range |
|---|---|---|
| `B_WIN_MSG` | `0x0090` | `0x0090`–`0x00F7` |
| `B_WIN_ACTION_MENU` | `0x0190` | `0x0190`–`0x01BF` |
| `B_WIN_ACTION_PROMPT` | `0x01C0` | `0x01C0`–`0x01F7` |
| **`B_WIN_ENEMY_IV`** | **`0x01F8`** | **`0x01F8`–`0x0238`** |
| `B_WIN_PP` | `0x0290` | `0x0290`–`0x0297` |
| `B_WIN_MOVE_NAME_1..4` | `0x0300`–`0x0330` | `0x0300`–`0x033F` |

Free space between the action prompt and the PP window is `0x01F8`–`0x028F` (152 tiles). The earlier `0x0250` base only had room for 64 tiles before `B_WIN_PP`. A 13×5 window there would have had its last tile overwritten whenever the move menu opened.

---

## 4. Palette

The box loads its own 16-color palette into **BG palette slot 12**. Other battle code doesn't use this slot:

| Slot | Used by |
|---|---|
| 0–1 | Textbox |
| 2–4 | Battle environment |
| 5 | Window text (`gBattleWindowTextPalette`) |
| 6 | VS frame |
| 7 | Battle Arena |
| 8–11 | Battler palettes copied for animations |
| **12** | **IV box** |

```c
#define IVBOX_PAL_SLOT  12

static const u16 sIvBoxPalette[16] =
{
    [IVBOX_COLOR_TRANSPARENT] = RGB(0, 0, 0),     // index 0 = see-through
    [IVBOX_COLOR_FILL]        = RGB(31, 31, 26),  // cream, like the healthbox
    [IVBOX_COLOR_BORDER]      = RGB(5, 7, 5),     // dark outline
    [IVBOX_COLOR_SHADOW]      = RGB(10, 13, 11),  // drop shadow
    [IVBOX_COLOR_TEXT]        = RGB(8, 8, 8),
    [IVBOX_COLOR_TEXT_SHADOW] = RGB(26, 26, 20),
    [IVBOX_COLOR_UP]          = RGB(28, 5, 4),    // nature-boosted stat
    [IVBOX_COLOR_UP_SHADOW]   = RGB(31, 20, 18),
    [IVBOX_COLOR_DOWN]        = RGB(5, 9, 28),    // nature-lowered stat
    [IVBOX_COLOR_DOWN_SHADOW] = RGB(20, 23, 31),
    [IVBOX_COLOR_LABEL]       = RGB(11, 15, 12),  // muted stat labels
};
```

`RGB()` takes 5-bit channels (0–31). Edit these values to recolor the box.

`DrawEnemyIVs` calls `LoadPalette` every time it runs. The palette therefore comes back after anything that reloads BG palettes, such as the Bag/Party menu.

Text color triples are `{background, foreground, shadow}` palette indices. The background is always `IVBOX_COLOR_FILL`, so glyph cells blend into the box:

```c
static const u8 sIvBoxTextColors[]  = {IVBOX_COLOR_FILL, IVBOX_COLOR_TEXT,  IVBOX_COLOR_TEXT_SHADOW};
static const u8 sIvBoxLabelColors[] = {IVBOX_COLOR_FILL, IVBOX_COLOR_LABEL, IVBOX_COLOR_TEXT_SHADOW};
static const u8 sIvBoxUpColors[]    = {IVBOX_COLOR_FILL, IVBOX_COLOR_UP,    IVBOX_COLOR_UP_SHADOW};
static const u8 sIvBoxDownColors[]  = {IVBOX_COLOR_FILL, IVBOX_COLOR_DOWN,  IVBOX_COLOR_DOWN_SHADOW};
```

---

## 5. Drawing

All drawing lives in `src/battle_main.c`, just above `TurnValuesCleanUp`.

### 5.1 `DrawEnemyIVs` — entry point

0. If `sShowEnemyIVBox` is `FALSE`, clears the window to transparent, uploads it and returns. That's how the box is hidden: it's the same window, just blank.
1. Finds the active enemy with `gEnemyParty[gBattlerPartyIndexes[GetBattlerAtPosition(B_POSITION_OPPONENT_LEFT)]]`, not a hard-coded `gEnemyParty[0]`.
2. Loads the palette.
3. Clears the window to transparent, then fills the 100×36 box area with cream.
4. Prints the nature name (`gNatureNamePointers[nature]`, from `pokemon_summary_screen.h`) top-left, and "IVs" right-aligned with `GetStringWidth`.
5. Prints six stats in a 3×2 grid via `DrawIvBoxStat`, with columns at x = 5 / 36 / 67 and rows at y = 13 / 23.
6. Draws the frame **last**, so no text cell can paint over the border.
7. `PutWindowTilemap` + `CopyWindowToVram(..., COPYWIN_FULL)`.

All text uses `FONT_SMALL_NARROW` (max glyph ≈ 5×8 px) and `TEXT_SKIP_DRAW`, so it renders instantly into the buffer. A single `CopyWindowToVram` at the end uploads everything.

### 5.2 `DrawIvBoxStat` — one label + value

```c
static void DrawIvBoxStat(const u8 *label, u8 stat, u32 iv, u8 nature, u8 x, u8 y)
```

- The label is drawn at `x` and the value right-aligned (2 digits) at `x + 16`.
- For any stat other than HP, `gNatureStatTable[nature][stat - 1]` sets the color: `> 0` = red, `< 0` = blue, `0` = default. The table is indexed from `STAT_ATK` and excludes HP, hence the `- 1`.
- When the stat is neutral, the label uses the muted label color and the value uses the dark text color. When it's affected, both use the nature color.

### 5.3 `DrawIvBoxFrame` — healthbox-style border

Uses only `FillWindowPixelRect`:

1. Shadow strips: bottom (`x=3, y=36, w=100, h=3`) and right (`x=100, y=3, w=3, h=36`).
2. Four 2px border edges, inset by 1px at the ends. This leaves the outer corner pixels transparent, which gives the rounded look.
3. Single pixels at each inner corner to round the inside.

Box size is controlled by `IVBOX_WIDTH` (100), `IVBOX_HEIGHT` (36) and `IVBOX_SHADOW` (3). If you enlarge the box, also grow the window template's `width` / `height` and re-check the `baseBlock` range.

---

## 6. The SELECT toggle

### 6.1 State

```c
// src/battle_main.c, after sFlickerArray
EWRAM_DATA static bool8 sShowEnemyIVBox = FALSE;
```

`BattleStartClearSetData` resets it to `FALSE`, so every battle starts with the box hidden. It costs 1 byte of EWRAM, which is already 95% full, so keep additions this small.

### 6.2 `ToggleEnemyIVBox`

```c
bool8 ToggleEnemyIVBox(void)
{
    if (gBattleTypeFlags & BATTLE_TYPE_TRAINER)
        return FALSE;

    sShowEnemyIVBox = !sShowEnemyIVBox;
    DrawEnemyIVs();
    return TRUE;
}
```

It returns `FALSE` in trainer battles, so the caller can skip the sound effect. Pressing SELECT there does nothing at all.

### 6.3 Input

`HandleInputChooseAction` in `src/battle_controller_player.c` is the action-menu input handler. A new branch goes after the existing `START_BUTTON` one (START swaps HP bars and HP text):

```c
else if (JOY_NEW(SELECT_BUTTON))
{
    if (ToggleEnemyIVBox())
        PlaySE(SE_SELECT);
}
```

SELECT was unused on the action menu. It stays **move swapping** in the move menu (`HandleInputChooseMove`), which is untouched. The toggle doesn't use up the player's turn: it's just a redraw, and no action is sent to the battle engine.

In double battles, both of the player's Pokémon use this handler, so SELECT works while choosing for either one.

---

## 7. Lifecycle hooks

Besides the toggle, `DrawEnemyIVs` is called in three places, each guarded by `!(gBattleTypeFlags & BATTLE_TYPE_TRAINER)`:

| Where | When |
|---|---|
| `TryDoEventsBeforeFirstTurn` (`battle_main.c`) | Right after `gBattleMainFunc = HandleTurnActionSelectionState` — turn 1 |
| `BattleTurnPassed` (`battle_main.c`) | Same assignment — every later turn. Also repairs tiles that animations may have overwritten. If the box is shown, it stays shown |
| `CB2_ReshowBattleScreenAfterMenu`, case 19 (`reshow_battle_screen.c`) | After returning from the Bag/Party/summary menus. That path clears all VRAM and re-inits windows, so without this hook a shown box vanished until the next turn |

Each hook respects `sShowEnemyIVBox`, so a hidden box stays hidden. `DrawEnemyIVs` is non-static and declared in `include/battle_main.h` so `reshow_battle_screen.c` can call it (it gets the prototype via `battle.h`).

---

## 8. Gotchas

- **`StringCopy` vs `StringAppend`.** The first version built one long string and used `StringCopy` for the last (Speed) segment. That wiped the buffer, so only Speed was shown. The current code prints each stat separately, so this can't happen again.
- **`_("...")` literals can't be function arguments.** The macro expands to an array initializer. Declare them as `static const u8 sText_X[] = _("...");` first.
- **C89 declarations.** Declare all locals at the top of a block, before any statement. agbcc rejects mixed declarations.
- **Palette index 0 is transparent on BGs.** That's why the window is cleared with `PIXEL_FILL(0)` before the box is drawn: the area outside the rounded corners and shadow shows the battle background.
- **Double wild battles:** only the left opponent is shown.

---

## 9. Build and test

From PowerShell (the toolchain lives in WSL Ubuntu):

```
wsl -d Ubuntu --cd /mnt/d/pkm/pokeemerald -- make -j16
```

In-game checklist:

1. Start a wild battle → no box on the action menu.
2. Press SELECT → the box appears under the enemy healthbox with the nature and six IVs, and a select sound plays.
3. The nature's raised stat is red and its lowered stat is blue. Neutral natures (Hardy, Docile, Serious, Bashful, Quirky) show no colored stat.
4. Press SELECT again → the box disappears. Press it once more → it's back.
5. With the box shown, pick FIGHT → the box disappears. Press B → it returns intact.
6. Open BAG or POKéMON and back out → the box is in the same state (shown or hidden) as before.
7. Use a move with the box shown → it's hidden during messages and animations, and still shown on the next turn.
8. Start a new wild battle → the box starts hidden again.
9. In the move menu, SELECT still swaps moves.
10. Trainer battle → SELECT does nothing, and no sound plays.

---

## 10. Quick reference

| Symbol | File | Purpose |
|---|---|---|
| `B_WIN_ENEMY_IV` | `include/constants/battle.h` | Window ID (24) |
| `sStandardBattleWindowTemplates[B_WIN_ENEMY_IV]` | `src/battle_bg.c` | Position, size, palette, VRAM tiles |
| `IVBOX_PAL_SLOT`, `sIvBoxPalette` | `src/battle_main.c` | BG palette 12 contents |
| `IVBOX_WIDTH` / `IVBOX_HEIGHT` / `IVBOX_SHADOW` | `src/battle_main.c` | Box geometry in pixels |
| `sShowEnemyIVBox` | `src/battle_main.c` | Shown/hidden flag, reset each battle |
| `ToggleEnemyIVBox` | `src/battle_main.c` | Flips the flag and redraws; `FALSE` in trainer battles |
| `HandleInputChooseAction` | `src/battle_controller_player.c` | Action-menu input; SELECT branch |
| `DrawEnemyIVs` | `src/battle_main.c` | Entry point (draws or clears) |
| `DrawIvBoxStat` | `src/battle_main.c` | One label/value with nature coloring |
| `DrawIvBoxFrame` | `src/battle_main.c` | Border, rounded corners, shadow |
| `gNatureStatTable` | `src/pokemon.c` | Nature → +1/0/−1 per stat (ATK, DEF, SPE, SPA, SPD) |
| `gNatureNamePointers` | `src/data/text/nature_names.h` | Nature name strings |
