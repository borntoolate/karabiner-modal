#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Answer "what does this key combination actually do?" against a generated rule set.

Karabiner walks the manipulator list top to bottom and takes the FIRST match,
so working this out by eye is error-prone.  This replays the same matching
rules and reports which manipulator wins -- or that none does, in which case
the key passes through to the application untouched.

    python3 shared/explain.py vim/vim-mode.json j
    python3 shared/explain.py vim/vim-mode.json j option shift
    python3 shared/explain.py vim/vim-mode.json j --var vim_visual=1
    python3 shared/explain.py vim/vim-mode.json --all j

The leader variable (vim_mode / emacs_mode) is assumed held; every other
variable defaults to 0.  Override any of them with --var name=value.
"""
import json
import sys

GENERIC = {
    "left_shift": "shift", "right_shift": "shift",
    "left_control": "control", "right_control": "control",
    "left_option": "option", "right_option": "option",
    "left_command": "command", "right_command": "command",
}


def norm(mods):
    return {GENERIC.get(m, m) for m in mods}


def matches(m, key, pressed, state):
    # `from.any: key_code` stands in for every key at once
    if "any" in m["from"]:
        if m["from"]["any"] != "key_code":
            return False
    elif m["from"].get("key_code") != key:
        return False

    spec = m["from"].get("modifiers", {})
    mandatory = norm(spec.get("mandatory", []))
    optional = norm(spec.get("optional", []))

    # every mandatory modifier must be held; mandatory ones are consumed
    if not mandatory <= pressed:
        return False
    leftover = pressed - mandatory
    if "any" not in optional and not leftover <= optional:
        return False

    for c in m.get("conditions", []):
        actual = state.get(c["name"], 0)
        if c["type"] == "variable_if" and actual != c["value"]:
            return False
        if c["type"] == "variable_unless" and actual == c["value"]:
            return False
    return True


def describe_to(m, pressed):
    """What the application ends up seeing."""
    spec = m["from"].get("modifiers", {})
    forwarded = pressed - norm(spec.get("mandatory", []))
    out = []
    for ev in m.get("to", []):
        if "key_code" in ev:
            mods = norm(ev.get("modifiers", [])) | forwarded
            prefix = "".join(sorted(
                {"command": "⌘", "shift": "⇧", "option": "⌥", "control": "⌃"}.get(x, x + "+")
                for x in mods))
            out.append(prefix + ev["key_code"])
        elif "set_variable" in ev:
            sv = ev["set_variable"]
            out.append(f"[{sv['name']}={sv['value']}]")
    return " → ".join(out) if out else "何も起きない（キーは飲み込まれます）"


def main():
    args = [a for a in sys.argv[1:]]
    show_all = "--all" in args
    args = [a for a in args if a != "--all"]

    overrides = {}
    rest = []
    for a in args:
        if a.startswith("--var"):
            continue
        if "=" in a and not a.endswith(".json"):
            k, v = a.split("=", 1)
            overrides[k] = int(v)
        else:
            rest.append(a)
    if len(rest) < 2:
        sys.exit(f"usage: {sys.argv[0]} <rules.json> <key_code> [modifier ...] "
                 f"[--var name=value] [--all]")

    path, key, pressed = rest[0], rest[1], norm(rest[2:])
    doc = json.load(open(path, encoding="utf-8"))
    manips = [m for r in doc["rules"] for m in r["manipulators"]]

    leader = "emacs_mode" if "emacs" in path else "vim_mode"
    state = {leader: 1}
    state.update(overrides)

    combo = "Caps + " + " + ".join(
        {"command": "⌘", "shift": "⇧", "option": "⌥", "control": "⌃"}.get(x, x)
        for x in sorted(pressed)) + (" + " if pressed else "") + key
    print(f"input : {combo}")
    print(f"state : {state}")
    print()

    hits = [(i, m) for i, m in enumerate(manips) if matches(m, key, pressed, state)]
    if not hits:
        print("  → マッチするルールなし。")
        print("    Caps Lock は修飾キーを出力しないので、アプリには")
        print(f"    「{' + '.join(sorted(pressed) + [key]) if pressed else key}」がそのまま届きます。")
        sys.exit(0)

    first_i, first_m = hits[0]
    print(f"  → [{first_i}] {first_m.get('description')}")
    print(f"     出力: {describe_to(first_m, pressed)}")
    if show_all and len(hits) > 1:
        print(f"\n  （後続の {len(hits) - 1} 件は評価順により発火しません）")
        for i, m in hits[1:]:
            print(f"     [{i}] {m.get('description')}")


if __name__ == "__main__":
    main()
