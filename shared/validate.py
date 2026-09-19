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
f1 f2 f3 f4 f5 f6 f7 f8 f9 f10 f11 f12
f13 f14 f15 f16 f17 f18 f19 f20
keypad_0 keypad_1 keypad_2 keypad_3 keypad_4
keypad_5 keypad_6 keypad_7 keypad_8 keypad_9 keypad_enter
""".split())

VALID_MODIFIERS = set("""
left_command left_control left_option left_shift
right_command right_control right_option right_shift
command control option shift fn caps_lock any
""".split())

VALID_COND_TYPES = {"variable_if", "variable_unless", "frontmost_application_if",
                    "frontmost_application_unless", "device_if", "device_unless"}

# `from.any` matches every event of the named kind instead of one key_code.
VALID_ANY = {"key_code", "consumer_key_code", "pointing_button"}

# `to` に書ける consumer_key_code。ゲームパッドの L2 が音声入力のマイクキーを送る。
VALID_CONSUMER_KEYS = {"dictation", "mute", "volume_increment", "volume_decrement",
                       "play_or_pause", "fastforward", "rewind",
                       "scan_next_track", "scan_previous_track", "eject",
                       "display_brightness_increment", "display_brightness_decrement"}

# ゲームパッド（SN30 Pro）の from / to に出てくるイベント。
# DirectInput のパッドのボタンは pointing_button として、十字キーは
# generic_desktop として届く（Karabiner-EventViewer で実測）。
VALID_POINTING_BUTTONS = {"button%d" % i for i in range(1, 33)}
VALID_GENERIC_DESKTOP = {"dpad_up", "dpad_down", "dpad_left", "dpad_right"}

errors, warnings = [], []
TARGET = sys.argv[1] if len(sys.argv) > 1 else "vim-mode.json"
doc = json.load(open(TARGET, encoding="utf-8"))

assert "title" in doc and "rules" in doc, "top-level keys missing"
manips = [m for rule in doc["rules"] for m in rule["manipulators"]]


def modspec(m):
    mods = m["from"].get("modifiers")
    if mods is None:
        return (frozenset(), frozenset())
    return (frozenset(mods.get("mandatory", [])), frozenset(mods.get("optional", [])))


for i, m in enumerate(manips):
    tag = f"[{i}] {m.get('description', '?')}"
    if m.get("type") != "basic":
        errors.append(f"{tag}: type != basic")
    if "any" in m["from"]:
        if m["from"]["any"] not in VALID_ANY:
            errors.append(f"{tag}: bad from.any {m['from']['any']!r}")
        if "key_code" in m["from"]:
            errors.append(f"{tag}: from has both any and key_code")
    elif "pointing_button" in m["from"]:
        if m["from"]["pointing_button"] not in VALID_POINTING_BUTTONS:
            errors.append(
                f"{tag}: bad from.pointing_button {m['from']['pointing_button']!r}")
    elif "generic_desktop" in m["from"]:
        if m["from"]["generic_desktop"] not in VALID_GENERIC_DESKTOP:
            errors.append(
                f"{tag}: bad from.generic_desktop {m['from']['generic_desktop']!r}")
    else:
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
            elif "pointing_button" in ev:
                if ev["pointing_button"] not in VALID_POINTING_BUTTONS:
                    errors.append(
                        f"{tag}: bad {bucket} pointing_button "
                        f"{ev['pointing_button']!r}")
            elif "consumer_key_code" in ev:
                if ev["consumer_key_code"] not in VALID_CONSUMER_KEYS:
                    errors.append(
                        f"{tag}: bad {bucket} consumer_key_code "
                        f"{ev['consumer_key_code']!r}")
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
    """条件の同一性。variable 系は name/value、アプリ / デバイス系は識別子で比べる。"""
    out = []
    for c in m.get("conditions", []):
        if "name" in c:
            out.append((c["type"], c["name"], c.get("value")))
        else:
            ident = c.get("bundle_identifiers") or c.get("identifiers") or []
            out.append((c["type"], json.dumps(ident, sort_keys=True), None))
    return frozenset(out)


def fromkey(m):
    """('any', kind) for a from.any manipulator, else (kind, value)."""
    if "any" in m["from"]:
        return ("any", m["from"]["any"])
    for kind in ("pointing_button", "generic_desktop"):
        if kind in m["from"]:
            return (kind, m["from"][kind])
    return ("key", m["from"].get("key_code"))


def key_subsumes(a, b):
    """a's from-key matches every event b's from-key matches."""
    if a == b:
        return True
    # `any: key_code` stands in front of every individual key
    return a == ("any", "key_code") and b[0] == "key"


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
        if not key_subsumes(fromkey(mi), fromkey(mj)):
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
