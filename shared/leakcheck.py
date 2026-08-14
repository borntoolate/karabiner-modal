#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Catch modifier leakage in generated Karabiner rules.

`from.modifiers.optional` carries whatever the user actually pressed straight
through to the `to` events.  That is occasionally what you want, but it is also
how `Shift + p` silently became Cmd-Shift-V ("paste and match style") instead of
Cmd-V.  Anything that should accept a modifier without emitting it must declare
it `mandatory`, which strips it from the output.

    python3 shared/leakcheck.py vim/vim-mode.json emacs/emacs-mode.json

Exits non-zero if a rule could emit a modifier it did not intend to.
"""
import json
import sys

# to-events that are allowed to inherit whatever the user pressed:
#   escape  -- Shift+Esc is harmless and the forgiving match is deliberate
#   any event that already carries left_shift (visual/mark motions add it)
ALLOWED_KEY_CODES = {"escape"}


def check(path):
    leaks = []
    doc = json.load(open(path, encoding="utf-8"))
    for rule in doc["rules"]:
        for m in rule["manipulators"]:
            optional = m["from"].get("modifiers", {}).get("optional", [])
            if "any" not in optional:
                continue
            for ev in m.get("to", []):
                if "key_code" not in ev:
                    continue
                if ev["key_code"] in ALLOWED_KEY_CODES:
                    continue
                if "left_shift" in ev.get("modifiers", []):
                    continue
                leaks.append((m.get("description", "?"), ev))
    return leaks


def main():
    targets = sys.argv[1:] or ["vim/vim-mode.json", "emacs/emacs-mode.json"]
    total = 0
    for path in targets:
        leaks = check(path)
        total += len(leaks)
        print(f"{path}: {len(leaks)} leak(s)")
        for desc, ev in leaks:
            print(f"    {desc}  ->  {ev}")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
