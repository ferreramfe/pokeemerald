# Custom Features

Documentation for changes made on top of vanilla pret/pokeemerald. One file per feature. When you change a feature's code, update its doc in the same commit.

| Feature | Doc | Main files |
|---|---|---|
| IV/EV toggle on the Summary Screen (SELECT on the Skills page) | [iv_ev_summary_screen.md](iv_ev_summary_screen.md) | `src/pokemon_summary_screen.c` |
| Enemy IV + nature box in wild battles | [wild_battle_iv_box.md](wild_battle_iv_box.md) | `src/battle_main.c`, `src/battle_bg.c`, `src/reshow_battle_screen.c` |

## Building

From PowerShell (the toolchain lives in WSL Ubuntu):

```
wsl -d Ubuntu --cd /mnt/d/pkm/pokeemerald -- make -j16
```

Output: `pokeemerald.gba` in the repo root.
