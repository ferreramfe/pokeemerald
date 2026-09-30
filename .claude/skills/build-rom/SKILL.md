---
name: build-rom
description: Build pokeemerald.gba in this repo (toolchain in WSL Ubuntu) and diagnose build errors. Use after any C, header, graphics or data change, when the user asks to build/compile/make the ROM, or when a build fails.
---

# Building the ROM

The toolchain (agbcc, arm-none-eabi binutils, make) lives in **WSL Ubuntu**. Git Bash has no usable `make`.

## Command
From **PowerShell** (preferred):
```
wsl -d Ubuntu --cd /mnt/d/mathe/pkm/projects/pokeemerald -- make -j16
```
From **Git Bash**, disable MSYS path rewriting, or `/mnt/...` gets mangled into `Wsl/ERROR_PATH_NOT_FOUND`:
```
MSYS_NO_PATHCONV=1 wsl -d Ubuntu --cd /mnt/d/mathe/pkm/projects/pokeemerald -- make -j16
```
An incremental build takes about 40 s. Output is `pokeemerald.gba` in the repo root. `make compare` is meaningless here because the ROM is modified.
Use a long timeout (10 min) for clean builds. Don't run `make clean` unless the user asks or the build is truly stuck on stale objects.

## Reading the result
- The end of the output shows `--print-memory-usage`. **Watch EWRAM (~95%) and IWRAM (~94%)**. New `EWRAM_DATA` /
  `IWRAM_DATA` variables eat that margin, and overflow is a link error (`region 'ewram' overflowed`). Report the new
  percentages when you add state.
- Success ends with `gbafix pokeemerald.gba -p`. Check the exit code is 0.

## Common errors
| Error | Cause / fix |
|---|---|
| `syntax error before '*'` / `parse error before` a type | C89: a declaration after a statement. Move all locals to the top of the block. |
| `initializer element is not constant` / errors on a `_("...")` argument | `_()` is only valid as an array initializer: `static const u8 sText[] = _("...");` |
| `implicit declaration of function` | Missing prototype. Add it to the matching `include/*.h` and include that header. |
| `undefined reference to gSomething` | Graphics/data declared `extern` but not defined (check `src/graphics.c` INCGFX line), or a `static` used across files. |
| `region 'ewram' overflowed` | Too much new EWRAM. Shrink it, reuse struct filler bytes, or move data to `const` (ROM). |
| gbagfx / PNG errors | The image isn't indexed, has >16 colors for 4bpp, or its size isn't a multiple of 8. See the ui-graphics-assets skill. |
| `character not in charmap` (preproc) | A string uses a char missing from `charmap.txt`. Use an existing char or `{NAME}` code. |

## After building
- Tell the user where the ROM is and what to test. Give them the feature's in-game checklist.
- For UI changes, the layout can be checked without an emulator in `../gba-ui-preview`, but only the ROM proves behavior.
