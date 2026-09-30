---
name: document-feature
description: Write or update the docs for a custom pokeemerald feature in docs/features/ following this repo's convention (one file per feature, index table in docs/features/README.md, updated in the same commit as the code), and prepare the gitmoji-style commit. Use after implementing or changing any custom feature, or when the user asks to document or commit one.
---

# Documenting a custom feature

Convention (from `docs/features/README.md`): **one file per feature, and when a feature's code changes, its doc is
updated in the same commit.** Good examples: `wild_battle_iv_box.md` (new component) and `iv_ev_summary_screen.md`
(changes to an existing screen). Match their tone and depth.

## File: `docs/features/<snake_case_name>.md`
Use this structure. Skip sections that don't apply, but keep the order:
1. `# Title`. One paragraph on what the player sees and how to trigger it (button, screen, conditions).
   Add an ASCII mockup of the UI when it's visual, then a **Files touched** table (`File | Change`).
2. **How the underlying system works**: the one or two engine concepts a reader needs first
   (e.g. BG0's scrolled pages and `tilemapTop`, the summary screen's window/task system).
3. One section per piece of the change, in the order a reader would implement it: IDs/constants → templates
   (with the `baseBlock` / VRAM reasoning and the output of `window_vram.py` if relevant) → palette (slot and why it's free)
   → drawing functions → state and input → lifecycle hooks (a table of where it's redrawn/reset and why).
   Show the real code snippets.
4. **Gotchas**: every bug hit during development and the rule that prevents it (C89 declarations, `_()` literals,
   StringCopy vs StringAppend, overlapping text rows, transparent index 0, ...).
5. **Build and test**: the WSL build command from the build-rom skill, then a numbered **in-game checklist** covering
   show/hide, every screen transition that rebuilds VRAM (menus, new turn, new battle), edge cases (trainer vs wild,
   doubles, eggs), and unchanged behavior of any input you reused.
6. **Quick reference**: a table of `Symbol | File | Purpose`.
7. Optional **Extending further**: ideas and where they'd hook in.

Keep claims true to the code. After editing code, re-read the doc's snippets and numbers (coordinates, baseBlock ranges,
palette slots, line references) and fix any drift.

## Index: `docs/features/README.md`
Add or update the row: `| <what the player gets (how to trigger)> | [file.md](file.md) | \`main files\` |`.
Keep its **Building** section's command correct:
`wsl -d Ubuntu --cd /mnt/d/mathe/pkm/projects/pokeemerald -- make -j16`.

## Commit (only when the user asks)
The history uses gitmoji subjects:
- `:sparkles:` new feature, e.g. ``:sparkles: Adds feature to show `IV` and `nature` in wild battles``
- `:memo:` docs only, `:bug:` fix, `:recycle:` refactor, `:art:` graphics/assets, `:lipstick:` UI polish.

Stage the code **and** its doc together. Never commit the built ROM or build outputs (`pokeemerald.gba`, `.elf`, `.map`,
`build/`) unless the user explicitly asks.
