#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mechanical checks on the generated Karabiner rule set."""
import json
import sys

VALID_KEYS = set("""
caps_lock escape return_or_enter delete_or_backspace delete_forward tab spacebar
left_arrow right_arrow up_arrow down_arrow page_up page_down home end
a b c d e f g h i j k l m n o p q r s t u v w x y z
0 1 2 3 4 5 6 7 8 9
hyphen equal_sign open_bracket close_bracket backslash semicolon quote
grave_accent_and_tilde comma period slash
left_shift right_shift left_command right_command left_option right_option
left_control right_control fn
""".split())

VALID_MODIFIERS = set("""
left_command left_control left_option left_shift
right_command right_control right_option right_shift
command control option shift fn caps_lock any
""".split())

VALID_COND_TYPES = {"variable_if", "variable_unless", "frontmost_application_if",
                    "frontmost_application_unless", "device_if", "device_unless"}

errors, warnings = [], []
TARGET = sys.argv[1] if len(sys.argv) > 1 else "vim-mode.json"
doc = json.load(open(TARGET, encoding="utf-8"))

assert "title" in doc and "rules" in doc, "top-level keys missing"
manips = doc["rules"][0]["manipulators"]


def modspec(m):
    mods = m["from"].get("modifiers")
    if mods is None:
        return (frozenset(), frozenset())
    return (frozenset(mods.get("mandatory", [])), frozenset(mods.get("optional", [])))


for i, m in enumerate(manips):
    tag = f"[{i}] {m.get('description', '?')}"
    if m.get("type") != "basic":
        errors.append(f"{tag}: type != basic")
    fk = m["from"].get("key_code")
    if fk not in VALID_KEYS:
        errors.append(f"{tag}: bad from.key_code {fk!r}")
    mand, opt = modspec(m)
    for x in mand | opt:
        if x not in VALID_MODIFIERS:
            errors.append(f"{tag}: bad from modifier {x!r}")
    # to events
    for bucket in ("to", "to_if_alone", "to_after_key_up"):
        for ev in m.get(bucket, []):
            if "key_code" in ev:
                if ev["key_code"] not in VALID_KEYS:
                    errors.append(f"{tag}: bad {bucket} key_code {ev['key_code']!r}")
                for x in ev.get("modifiers", []):
                    if x not in VALID_MODIFIERS:
                        errors.append(f"{tag}: bad {bucket} modifier {x!r}")
            elif "set_variable" in ev:
                sv = ev["set_variable"]
                if set(sv) != {"name", "value"}:
                    errors.append(f"{tag}: malformed set_variable {sv}")
            else:
                errors.append(f"{tag}: unknown {bucket} event {ev}")
    for c in m.get("conditions", []):
        if c.get("type") not in VALID_COND_TYPES:
            errors.append(f"{tag}: bad condition type {c.get('type')}")
    da = m.get("to_delayed_action")
    if da:
        if not set(da) <= {"to_if_invoked", "to_if_canceled"}:
            errors.append(f"{tag}: bad to_delayed_action keys {list(da)}")
        p = m.get("parameters", {})
        if "basic.to_delayed_action_delay_milliseconds" not in p:
            warnings.append(f"{tag}: delayed action uses the 500ms default")
    for p in m.get("parameters", {}):
        if not p.startswith("basic."):
            errors.append(f"{tag}: bad parameter name {p}")

# ---- shadowing: does an earlier manipulator make a later one unreachable? ----
def conds(m):
    return frozenset((c["type"], c["name"], c["value"]) for c in m.get("conditions", []))


def mod_subsumes(a, b):
    """a's from-modifier spec matches every event b's spec matches."""
    am, ao = a
    bm, bo = b
    if "any" in ao and not am:
        return True
    if am != bm:
        return False
    return ao >= bo


for j, mj in enumerate(manips):
    for i in range(j):
        mi = manips[i]
        if mi["from"].get("key_code") != mj["from"].get("key_code"):
            continue
        if not mod_subsumes(modspec(mi), modspec(mj)):
            continue
        # mi fires whenever mj would, if mi's conditions are implied by mj's
        if conds(mi) <= conds(mj):
            errors.append(
                f"UNREACHABLE: [{j}] {mj.get('description')}  <-- shadowed by "
                f"[{i}] {mi.get('description')}")
            break

print(f"file                 : {TARGET}")
print(f"manipulators checked : {len(manips)}")
print(f"errors               : {len(errors)}")
print(f"warnings             : {len(warnings)}")
for e in errors:
    print("  ERROR  ", e)
for w in warnings:
    print("  WARN   ", w)
sys.exit(1 if errors else 0)
