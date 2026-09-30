"""List WindowTemplate arrays with their VRAM tile ranges, overlaps and free gaps.

    python .claude/skills/add-ui-window/window_vram.py src/battle_bg.c
    python .claude/skills/add-ui-window/window_vram.py src/battle_bg.c --array sStandardBattleWindowTemplates --need 90

Tiles of a window = width * height, placed at baseBlock (in tiles) inside the BG's char base.
Windows whose BGs share a charBaseIndex share tile space, so they are grouped by char base when a
BgTemplate array in the same file says so (otherwise by bg number).
Run from the repo root.
"""
import argparse
import ast
import glob
import operator
import os
import re
import sys

FIELDS = ["bg", "tilemapLeft", "tilemapTop", "width", "height", "paletteNum", "baseBlock"]
BG_FIELDS = ["bg", "charBaseIndex", "mapBaseIndex", "screenSize", "paletteMode", "priority", "baseTile"]
TILES_PER_CHARBLOCK = 512  # 16 KB / 32 bytes per 4bpp tile


def strip_comments(src):
    src = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


class Defines:
    def __init__(self, sources):
        self.raw = {}
        for src in sources:
            for name, val in re.findall(r"^[ \t]*#[ \t]*define[ \t]+(\w+)(?![\w(])[ \t]*(.*?)[ \t]*$", src, re.M):
                self.raw.setdefault(name, val)
            for body in re.findall(r"\benum\b\s*\w*\s*\{([^}]*)\}", src, re.S):
                n = 0
                for item in (i.strip() for i in body.split(",")):
                    if not item:
                        continue
                    name, _, expr = item.partition("=")
                    name = name.strip()
                    if expr.strip():
                        v = self.eval(expr)
                        n = v if isinstance(v, int) else n
                    self.raw.setdefault(name, str(n))
                    n += 1

    def eval(self, expr, depth=0):
        ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
               ast.FloorDiv: operator.floordiv, ast.LShift: operator.lshift, ast.RShift: operator.rshift,
               ast.BitOr: operator.or_, ast.BitAnd: operator.and_, ast.USub: operator.neg}
        text = re.sub(r"\b(0[xX][0-9a-fA-F]+|\d+)[uUlL]+\b", r"\1", expr.strip()).replace("/", "//")

        def ev(node):
            if isinstance(node, ast.Expression):
                return ev(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, int):
                return node.value
            if isinstance(node, ast.Name) and node.id in self.raw and depth < 20:
                v = self.eval(self.raw[node.id], depth + 1)
                if isinstance(v, int):
                    return v
            if isinstance(node, ast.BinOp) and type(node.op) in ops:
                return ops[type(node.op)](ev(node.left), ev(node.right))
            if isinstance(node, ast.UnaryOp) and type(node.op) in ops:
                return ops[type(node.op)](ev(node.operand))
            raise ValueError(text)

        try:
            return ev(ast.parse(text, mode="eval"))
        except (SyntaxError, ValueError, ZeroDivisionError):
            return expr.strip()


def braced(src, i):
    """Return end index (after '}') of the brace group starting at src[i] == '{'."""
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return j + 1
    raise ValueError("unbalanced braces")


def parse_arrays(src, struct, fields, defines):
    out = {}
    for m in re.finditer(r"struct\s+" + struct + r"\s+(\w+)\s*\[[^\]]*\]\s*=\s*\{", src):
        start = m.end() - 1
        body = src[start + 1:braced(src, start) - 1]
        entries, i = [], 0
        while True:
            e = re.compile(r"(?:\[\s*([^\]]+?)\s*\]\s*=\s*)?\{").search(body, i)
            if not e:
                break
            end = braced(body, e.end() - 1)
            inner = body[e.end():end - 1]
            vals = {}
            named = re.findall(r"\.(\w+)\s*=\s*([^,]+)", inner)
            if named:
                vals = {k: defines.eval(v) for k, v in named}
            else:
                parts = [p.strip() for p in inner.split(",") if p.strip()]
                vals = {f: defines.eval(p) for f, p in zip(fields, parts)}
            line = src.count("\n", 0, start + 1 + e.start()) + 1
            entries.append({"label": e.group(1) or "[%d]" % len(entries), "line": line, **vals})
            i = end
        out[m.group(1)] = entries
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="C file with WindowTemplate arrays, e.g. src/battle_bg.c")
    ap.add_argument("--array", help="only this array")
    ap.add_argument("--need", type=int, help="find free baseBlock gaps of at least this many tiles")
    args = ap.parse_args()

    if not os.path.isfile(args.file):
        sys.exit("no such file: %s (run from the repo root)" % args.file)
    with open(args.file, encoding="utf-8", errors="replace") as f:
        src = strip_comments(f.read())
    headers = [src]
    for h in glob.glob("include/constants/*.h") + glob.glob("include/gba/*.h") + glob.glob("include/*.h"):
        with open(h, encoding="utf-8", errors="replace") as f:
            headers.append(strip_comments(f.read()))
    defines = Defines(headers)

    bgs = {}
    for entries in parse_arrays(src, "BgTemplate", BG_FIELDS, defines).values():
        for b in entries:
            if isinstance(b.get("bg"), int) and isinstance(b.get("charBaseIndex"), int):
                bgs.setdefault(b["bg"], b["charBaseIndex"])

    arrays = parse_arrays(src, "WindowTemplate", FIELDS, defines)
    if args.array:
        arrays = {k: v for k, v in arrays.items() if k == args.array}
    if not arrays:
        sys.exit("no WindowTemplate arrays found")

    for name, wins in arrays.items():
        print("\n%s  (%s)" % (name, args.file))
        print("  %-34s %3s %5s %5s %6s %4s %-15s line" % ("window", "bg", "left", "top", "w x h", "pal", "tiles"))
        good = []
        for w in wins:
            try:
                n = w["width"] * w["height"]
                rng = "0x%04X-0x%04X" % (w["baseBlock"], w["baseBlock"] + n - 1) if n else "(empty)"
                good.append(dict(w, tiles=n))
            except (KeyError, TypeError):
                rng = "?"
            print("  %-34s %3s %5s %5s %6s %4s %-15s %s" % (
                w["label"][:34], w.get("bg"), w.get("tilemapLeft"), w.get("tilemapTop"),
                "%sx%s" % (w.get("width"), w.get("height")), w.get("paletteNum"), rng, w["line"]))

        # Absolute tile address = charBase * 512 + baseBlock, so windows on different BGs that
        # share (or spill into) the same char blocks are compared correctly.
        wins_t = [w for w in good if w["tiles"]]
        absolute = all(w["bg"] in bgs for w in wins_t)
        for w in wins_t:
            w["abs"] = bgs[w["bg"]] * TILES_PER_CHARBLOCK + w["baseBlock"] if absolute else w["baseBlock"]
        if absolute:
            print("\n  char bases: %s   (addresses below are absolute tiles in BG VRAM; "
                  "a BG's baseBlock = address - charBase*512)" % ", ".join(
                      "bg%d->%d (0x%04X)" % (b, c, c * TILES_PER_CHARBLOCK) for b, c in sorted(bgs.items())))
            groups = {"all BG windows": wins_t}
        else:
            print("\n  (no BgTemplate in this file: comparing per bg, pass-through char bases unknown)")
            groups = {}
            for w in wins_t:
                groups.setdefault("bg %d" % w["bg"], []).append(w)

        for key, ws in sorted(groups.items()):
            ws.sort(key=lambda w: w["abs"])
            print("\n  %s:" % key)
            for a_i, a in enumerate(ws):
                for b in ws[a_i + 1:]:
                    if b["abs"] < a["abs"] + a["tiles"]:
                        print("    VRAM OVERLAP  %s (bg%d) and %s (bg%d) share 0x%04X-0x%04X "
                              "- fine only if never shown at the same time" % (
                                  a["label"], a["bg"], b["label"], b["bg"], b["abs"],
                                  min(a["abs"] + a["tiles"], b["abs"] + b["tiles"]) - 1))
                    if (a["bg"] == b["bg"] and a["tilemapLeft"] < b["tilemapLeft"] + b["width"]
                            and b["tilemapLeft"] < a["tilemapLeft"] + a["width"]
                            and a["tilemapTop"] < b["tilemapTop"] + b["height"]
                            and b["tilemapTop"] < a["tilemapTop"] + a["height"]):
                        print("    tilemap overlap: %s and %s cover the same bg%d cells" % (a["label"], b["label"], a["bg"]))
            gaps, cursor = [], ws[0]["abs"]
            for w in ws:
                if w["abs"] > cursor:
                    gaps.append((cursor, w["abs"] - cursor))
                cursor = max(cursor, w["abs"] + w["tiles"])
            print("    used 0x%04X-0x%04X; free gaps: %s; free after: 0x%04X+" % (
                ws[0]["abs"], cursor - 1, ", ".join("0x%04X (+%d)" % g for g in gaps) or "none", cursor))
            if args.need:
                fits = [g for g in gaps if g[1] >= args.need] + [(cursor, None)]
                print("    places for %d tiles:" % args.need)
                for start, size in fits:
                    hint = ""
                    if absolute:
                        hint = "  -> " + ", ".join("bg%d baseBlock 0x%04X" % (b, start - c * TILES_PER_CHARBLOCK)
                                                   for b, c in sorted(bgs.items())
                                                   if 0 <= start - c * TILES_PER_CHARBLOCK < 1024)
                    print("      0x%04X%s%s" % (start, "" if size else " (after last window)", hint))
    print("\nRemember: tiles at the start of the char base usually hold the BG's own tileset "
          "(e.g. the battle textbox); check its size before placing a window below the first one.")


if __name__ == "__main__":
    main()
