# IV / EV Toggle on the Pokémon Summary Screen

This document covers everything you need to understand, reproduce, or extend the IV/EV display toggle added to `src/pokemon_summary_screen.c` in the **pret/pokeemerald** decompilation.

> **Related:** [Wild Battle IV / Nature Box](wild_battle_iv_box.md) shows the *enemy's* IVs and nature during wild battles. Both features read the same `MON_DATA_*_IV` fields, but they're otherwise independent.

---

## 1. Project Context

**pokeemerald** is a byte-for-byte decompilation of Pokémon Emerald (GBA). Working from the vanilla decompilation (rather than the `pokeemerald-expansion` fork) keeps `SaveBlock1`/`SaveBlock2` at their original sizes, so existing save files load without corruption. This feature is a pure UI change — it touches only EWRAM screen state and tilemap/window rendering; it modifies no save data.

**What the feature does:**
- On the **Skills (Stats) page** of the Pokémon Summary Screen, pressing **SELECT** cycles the stat display through three modes:
  - `0` — Base stats (default, original behavior)
  - `1` — IVs, color-coded by quality
  - `2` — EVs (uniform color)
- The bottom-left label that normally reads **"Status"** changes to **"IVs"** or **"EVs"** as a mode indicator.

---

## 2. Architecture Primer

### 2.1 State machine — `sMonSummaryScreen`

All screen state lives in a single heap-allocated struct:

```c
// src/pokemon_summary_screen.c, ~line 128
static EWRAM_DATA struct PokemonSummaryScreenData { ... } *sMonSummaryScreen = NULL;
```

It is created with `AllocZeroed` in `ShowPokemonSummaryScreen` and freed on close. Every field starts at `0` on each new screen open.

### 2.2 Pages

```c
enum {
    PSS_PAGE_INFO,          // 0
    PSS_PAGE_SKILLS,        // 1  ← this is where stats live
    PSS_PAGE_BATTLE_MOVES,  // 2
    PSS_PAGE_CONTEST_MOVES, // 3
};
```

The current page is tracked in `sMonSummaryScreen->currPageIndex`.

### 2.3 Window system

The GBA has no framebuffer. Text is drawn into **window tile buffers** (EWRAM), which are then mapped onto a BG layer and DMA'd to VRAM each VBlank.

Two categories of windows are used:

| Category | Template array | Constants |
|---|---|---|
| Always-present label windows | `sSummaryTemplate` | `PSS_LABEL_WINDOW_*` (0–19) |
| Page-specific data windows | `sPageSkillsTemplate` etc. | `PSS_DATA_WINDOW_*` |

**Critical**: The `PSS_LABEL_WINDOW_*` values ARE the window IDs — they are indices into the window system corresponding to the order `InitWindows(sSummaryTemplate)` allocates them. You can pass them directly to `FillWindowPixelBuffer`, `PrintTextOnWindow`, `PutWindowTilemap`, etc.

Page-specific windows are allocated lazily via `AddWindowFromTemplateList(templateArray, index)` which checks a cache and calls `AddWindow` only once per window per page.

### 2.4 Text printing

```c
// The main helper (line ~2746)
static void PrintTextOnWindow(u8 windowId, const u8 *string,
                               u8 x, u8 y, u8 lineSpacing, u8 colorId);
```

`colorId` indexes into `sTextColors[][3]` = `{bg, fg, shadow}`. Key entries:

| colorId | Visual color (inferred) | Use |
|---|---|---|
| 0 | White | Default stat values |
| 1 | Light gray/white | Labels |
| 4 | Red / pink | Bad IVs, female symbol |
| 5 | Green | Good IVs |
| 6 | Yellow / gold | Perfect IVs |

### 2.5 Task system

Input handling and multi-frame operations run as **tasks** — entries in a fixed `gTasks[]` array, each with a function pointer and 16 `s16` data words. The main input handler is `Task_HandleInput`.

---

## 3. Struct Change — Adding `ivEvMode`

```c
// Before (line 183):
u8 filler40CA;

// After:
u8 ivEvMode; // 0=base stats, 1=IVs, 2=EVs
```

`filler40CA` was a confirmed unused padding byte at this offset. Replacing it with a named field:
- Does **not** change the struct's size or the layout of any other field.
- Starts at `0` every time a new summary screen is opened (via `AllocZeroed`).
- No save data is affected.

---

## 4. SELECT Button Handler

Added inside `Task_HandleInput`, after the existing `B_BUTTON` block:

```c
else if (JOY_NEW(SELECT_BUTTON))
{
    if (sMonSummaryScreen->currPageIndex == PSS_PAGE_SKILLS
        && !sMonSummaryScreen->summary.isEgg)
    {
        PlaySE(SE_SELECT);
        if (++sMonSummaryScreen->ivEvMode > 2)
            sMonSummaryScreen->ivEvMode = 0;
        RedrawSkillsPageStats();
    }
}
```

**Guards:**
- `currPageIndex == PSS_PAGE_SKILLS` — the toggle is meaningless on other pages.
- `!summary.isEgg` — eggs have no stats to show.

`SELECT_BUTTON` is defined as `0x0004` in `include/gba/io_reg.h`. `JOY_NEW` returns true only on the frame the button is first pressed (edge-trigger).

---

## 5. Fetching IV and EV Data

Pokémon data is stored encrypted in `struct Pokemon`. The only safe way to read it is:

```c
u32 value = GetMonData(struct Pokemon *mon, enum PokemonDataType type);
// Third argument (buffer) is optional; omit it for numeric fields.
```

All 12 IV/EV constants (from `include/pokemon.h`):

```c
// EVs (Effort Values, 0–252 each)
MON_DATA_HP_EV, MON_DATA_ATK_EV, MON_DATA_DEF_EV,
MON_DATA_SPEED_EV, MON_DATA_SPATK_EV, MON_DATA_SPDEF_EV

// IVs (Individual Values, 0–31 each)
MON_DATA_HP_IV, MON_DATA_ATK_IV, MON_DATA_DEF_IV,
MON_DATA_SPEED_IV, MON_DATA_SPATK_IV, MON_DATA_SPDEF_IV
```

The `currentMon` field in `sMonSummaryScreen` is a fully decoded `struct Pokemon` copy, so `GetMonData(&sMonSummaryScreen->currentMon, MON_DATA_HP_IV)` is safe and fast.

---

## 6. Colored Per-Line Printing

### 6.1 Why not `DynamicPlaceholderTextUtil`?

The original stats use a batch layout string:

```c
static const u8 sStatsLeftColumnLayout[] =
    _("{DYNAMIC 0}/{DYNAMIC 1}\n{DYNAMIC 2}\n{DYNAMIC 3}");
```

`DynamicPlaceholderTextUtil_ExpandPlaceholders` fills placeholders and produces one big string that `PrintTextOnWindow` renders in a **single color**. Per-value coloring requires printing each value in its own `PrintTextOnWindow` call.

### 6.2 `GetIVColorId`

```c
static u8 GetIVColorId(u8 iv)
{
    if (iv == 31) return 6; // yellow  — perfect
    if (iv > 28)  return 5; // green   — good (29–30)
    if (iv < 10)  return 4; // red     — bad  (<10)
    return 0;               // white   — normal (10–28)
}
```

Only used for IVs. EVs render in colorId `0` (white) — no quality gradient.

### 6.3 `PrintLeftColumnIVsOrEVs` and `PrintRightColumnIVsOrEVs`

Each function:
1. Gets the three relevant stat values from `currentMon`.
2. Converts each to a right-aligned decimal string.
3. Computes the pixel x-offset with `GetStringRightAlignXOffset(FONT_NORMAL, str, maxPx)`.
4. Calls `PrintTextOnWindow` three times (y = 1, 17, 33 — 16 px per stat row).

```c
// Left column (HP, ATK, DEF) — window is 6 tiles = 48px; use maxPx=44
ConvertIntToDecimalStringN(str, hpVal, STR_CONV_MODE_RIGHT_ALIGN, showIVs ? 2 : 3);
x = GetStringRightAlignXOffset(FONT_NORMAL, str, 44);
PrintTextOnWindow(windowId, str, x, 1, 0, showIVs ? GetIVColorId(hpVal) : 0);

// Right column (SpATK, SpDEF, SPD) — window is 3 tiles = 24px; use maxPx=22
ConvertIntToDecimalStringN(str, spatkVal, STR_CONV_MODE_RIGHT_ALIGN, showIVs ? 2 : 3);
x = GetStringRightAlignXOffset(FONT_NORMAL, str, 22);
PrintTextOnWindow(windowId, str, x, 1, 0, showIVs ? GetIVColorId(spatkVal) : 0);
```

Field widths: `2` for IVs (max 31), `3` for EVs (max 252).

### 6.4 Dispatch from existing functions

Rather than rewriting the full render pipeline, `PrintLeftColumnStats` and `PrintRightColumnStats` were given early-dispatch branches:

```c
static void PrintLeftColumnStats(void)
{
    if (sMonSummaryScreen->ivEvMode != 0)
    {
        PrintLeftColumnIVsOrEVs();
        return;
    }
    // ... original code ...
}
```

`BufferLeftColumnStats` (which runs before `PrintLeftColumnStats`) simply returns early when `ivEvMode != 0` — there is nothing to buffer since the print functions handle everything directly.

---

## 7. Mode Indicator

### 7.1 The window

`PSS_LABEL_WINDOW_POKEMON_SKILLS_STATUS` (= 13) is the window where `PrintPageNamesAndStats` prints the text **"Status"** at `x=2, y=1, colorId=1`. This label sits in the bottom-left of the Skills page, above the ailment sprite area.

### 7.2 `DrawIVEvModeIndicator`

```c
static void DrawIVEvModeIndicator(void)
{
    if (sMonSummaryScreen->currPageIndex != PSS_PAGE_SKILLS)
        return;
    FillWindowPixelBuffer(PSS_LABEL_WINDOW_POKEMON_SKILLS_STATUS, PIXEL_FILL(0));
    if (sMonSummaryScreen->ivEvMode == 1)
        PrintTextOnWindow(PSS_LABEL_WINDOW_POKEMON_SKILLS_STATUS,
                          sText_IVs, 2, 1, 0, 5);          // green
    else if (sMonSummaryScreen->ivEvMode == 2)
        PrintTextOnWindow(PSS_LABEL_WINDOW_POKEMON_SKILLS_STATUS,
                          sText_EVs, 2, 1, 0, 6);          // yellow
    else
        PrintTextOnWindow(PSS_LABEL_WINDOW_POKEMON_SKILLS_STATUS,
                          gText_Status, 2, 1, 0, 1);       // restore original
    ScheduleBgCopyTilemapToVram(0);
}
```

The actual ailment condition is shown as a **sprite** (separate from this text window), so replacing the "Status" text label does not hide the ailment icon.

`DrawIVEvModeIndicator` is called at the end of:
- `PrintSkillsPageText` — runs on initial page load and Pokémon change
- `RedrawSkillsPageStats` — runs on every SELECT press

---

## 8. C89 Gotcha — Declarations Before Statements

The GBA toolchain (arm-none-eabi-gcc with `-std=c89` or similar) requires **all local variable declarations to come before any executable statements** within a block. Mixing them causes:

```
syntax error before `*'
```

**Wrong** (triggers error):
```c
static void BufferLeftColumnStats(void)
{
    if (sMonSummaryScreen->ivEvMode != 0)  // ← statement
        return;
    u8 *currentHPString = Alloc(8);       // ← declaration after statement: ERROR
```

**Correct** (declarations first):
```c
static void BufferLeftColumnStats(void)
{
    u8 *currentHPString;   // declare
    u8 *maxHPString;
    u8 *attackString;
    u8 *defenseString;

    if (sMonSummaryScreen->ivEvMode != 0)  // then statements
        return;

    currentHPString = Alloc(8);            // assign separately
    ...
```

---

## 9. Call Graph

### Initial page load path

```
ShowPokemonSummaryScreen
  → CB2_InitSummaryScreen → LoadGraphics
      → PrintSkillsPageText            (case 13, currPage=SKILLS)
          → BufferLeftColumnStats      (early-return when ivEvMode!=0)
          → PrintLeftColumnStats       → PrintLeftColumnIVsOrEVs (if ivEvMode!=0)
          → BufferRightColumnStats     (early-return when ivEvMode!=0)
          → PrintRightColumnStats      → PrintRightColumnIVsOrEVs (if ivEvMode!=0)
          → PrintExpPointsNextLevel
          → DrawIVEvModeIndicator
```

### SELECT press path

```
Task_HandleInput
  → JOY_NEW(SELECT_BUTTON) + PSS_PAGE_SKILLS + !isEgg
      → ivEvMode = (ivEvMode + 1) % 3
      → RedrawSkillsPageStats
          → FillWindowPixelBuffer (clear left + right stat windows)
          → BufferLeftColumnStats  → PrintLeftColumnStats
          → BufferRightColumnStats → PrintRightColumnStats
          → CopyWindowToVram (left + right)
          → DrawIVEvModeIndicator
```

### Pokémon change path

```
Task_ChangeSummaryMon (case 11)
  → PrintPageSpecificText(currPageIndex)
      → PrintSkillsPageText            (if currPage=SKILLS)
          → ... same as initial load path above
```

---

## 10. Build and Test

From PowerShell (the toolchain lives in WSL Ubuntu; Git Bash has no `make`):

```
wsl -d Ubuntu --cd /mnt/d/pkm/pokeemerald -- make -j16
```

Expected: no errors in `src/pokemon_summary_screen.c`.

**In-game verification checklist:**

1. Open summary screen on any non-egg Pokémon → navigate to **Skills** tab.
2. Press **SELECT** → stat numbers change to IVs (0–31 range); bottom-left label reads **"IVs"** in green.
   - Confirm color coding: red for values < 10, white for 10–28, green for 29–30, yellow for value 31.
3. Press **SELECT** again → stats change to EVs (0–252 range); label reads **"EVs"** in yellow; all values are white.
4. Press **SELECT** a third time → base stats restore; label reads **"Status"** again.
5. Navigate to **Info**, **Battle Moves**, **Contest Moves** pages and press SELECT → no effect.
6. Open summary screen on an egg → press SELECT → no effect.
7. While in IV mode, press UP/DOWN to change Pokémon → new Pokémon's IVs shown with correct colors; "IVs" label persists.

---

## 11. Extending Further

### Nature-colored base stats
`PrintPageNamesAndStats` already prints stat labels at `y=1, 17, 33` in the label windows. You can reprint the nature-boosted stat label in a different color by checking `sMonSummaryScreen->summary.nature` against `gNatureStatTable` (in `src/pokemon.c`). The battle IV box already does this: see `DrawIvBoxStat` in [wild_battle_iv_box.md](wild_battle_iv_box.md#52-drawivboxstat--one-label--value) for a working example. Remember the table is indexed from `STAT_ATK`, so use `stat - 1`.

### EV color coding
Add an `EV_MAX 252` threshold check in a new `GetEVColorId(u8 ev)` function similar to `GetIVColorId`, then pass it as the colorId in `PrintRightColumnIVsOrEVs` / `PrintLeftColumnIVsOrEVs` when `showIVs == FALSE`.

### Persistent toggle across saves
`ivEvMode` currently resets on every summary screen open (it lives in `AllocZeroed` EWRAM). To persist it, store it in a spare byte of `SaveBlock2` or in a dedicated `gLastViewedStatMode` global (pattern: see `gLastViewedMonIndex` in the same file).

### Combined IV/EV display (e.g., "31/252" per stat)
The left stats window is 6 tiles wide (48 px). A "31/252" string (6 chars × ~7 px = 42 px) fits. You would need a new `PSS_DATA_WINDOW_SKILLS_STATS_IVEV` window added to `sPageSkillsTemplate` with `width=6` to replace both the left and right data windows, and print combined strings at fixed x positions.

---

## Key Symbols Quick Reference

| Symbol | File | Description |
|---|---|---|
| `sMonSummaryScreen->ivEvMode` | `pokemon_summary_screen.c:183` | Toggle state (0/1/2) |
| `Task_HandleInput` | `pokemon_summary_screen.c:~1532` | Main input handler |
| `RedrawSkillsPageStats` | `pokemon_summary_screen.c` | Clears + reprints stat windows on SELECT |
| `PrintLeftColumnIVsOrEVs` | `pokemon_summary_screen.c` | Per-line colored print, left column |
| `PrintRightColumnIVsOrEVs` | `pokemon_summary_screen.c` | Per-line colored print, right column |
| `GetIVColorId` | `pokemon_summary_screen.c` | Maps IV value → colorId |
| `DrawIVEvModeIndicator` | `pokemon_summary_screen.c` | Updates "Status"/"IVs"/"EVs" label |
| `PSS_LABEL_WINDOW_POKEMON_SKILLS_STATUS` | `pokemon_summary_screen.c:78` | Window ID 13 — the mode indicator window |
| `MON_DATA_*_IV / MON_DATA_*_EV` | `include/pokemon.h:34-52` | Enum values for `GetMonData` |
| `SELECT_BUTTON` | `include/gba/io_reg.h:701` | `0x0004` |
| `PrintTextOnWindow` | `pokemon_summary_screen.c:~2746` | Renders text into a window with colorId |
| `GetStringRightAlignXOffset` | `src/string_util.c` | Computes x for right-aligned text |
