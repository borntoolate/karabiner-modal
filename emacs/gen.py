#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a Karabiner-Elements complex_modifications rule set:
Emacs-like navigation/editing for the whole of macOS, using Caps Lock as a held leader.

Caps Lock held        = the Control of Emacs (C-)
Caps Lock + META_MOD  = the Meta of Emacs    (M-)
Caps Lock tapped      = nothing

Assumes a US (ANSI) keyboard layout.
"""
import json

# --- knobs -----------------------------------------------------------------
# "shift"  : M-f is Caps + Shift + f.  Selection is done with the mark only.
# "option" : M-f is Caps + Option + f. Shift stays free, so Shift also selects.
META_MOD = "shift"

# Shown in Karabiner's rule list. Use your GitHub handle if you publish this.
MAINTAINER = "borntoolate"

PREFIX_DELAY = 800   # ms allowed between C-x and its second stroke

# What a lone tap of the leader key should send. None = nothing at all.
TAP_ACTION = None
# ---------------------------------------------------------------------------

EM = {"type": "variable_if", "name": "emacs_mode", "value": 1}
MARK_ON = {"type": "variable_if", "name": "emacs_mark", "value": 1}
MARK_OFF = {"type": "variable_unless", "name": "emacs_mark", "value": 1}
X_ON = {"type": "variable_if", "name": "emacs_x", "value": 1}
X_OFF = {"type": "variable_unless", "name": "emacs_x", "value": 1}

# from-modifier specs
PLAIN = ({"optional": ["caps_lock"]} if META_MOD == "shift"
         else {"optional": ["any"]})
META = ({"mandatory": ["shift"], "optional": ["caps_lock"]} if META_MOD == "shift"
        else {"mandatory": ["option"], "optional": ["any"]})
NONE = {"optional": ["caps_lock"]}
SHIFT = {"mandatory": ["shift"], "optional": ["caps_lock"]}
ANY = {"optional": ["any"]}


def setv(name, value):
    return {"set_variable": {"name": name, "value": value}}


def key(code, mods=None):
    k = {"key_code": code}
    if mods:
        k["modifiers"] = mods
    return k


def manip(from_key, to_events, conditions, from_mods, description,
          delayed=None, params=None):
    m = {"type": "basic", "description": description,
         "from": {"key_code": from_key, "modifiers": from_mods},
         "to": to_events, "conditions": conditions}
    if delayed:
        m["to_delayed_action"] = delayed
    if params:
        m["parameters"] = params
    return m


CLEAR_ALL = [setv("emacs_mark", 0), setv("emacs_x", 0)]

manipulators = []

# ---------------------------------------------------------------------------
# 1. The leader: Caps Lock held = Emacs mode (the "C-" of Emacs)
# ---------------------------------------------------------------------------
leader = {
    "type": "basic",
    "description": "Caps Lock: hold = Emacs leader (C-)"
                   + (f" / tap = {TAP_ACTION}" if TAP_ACTION else " / tap = nothing"),
    "from": {"key_code": "caps_lock", "modifiers": {"optional": ["any"]}},
    "to": [setv("emacs_mode", 1)],
    "to_after_key_up": [
        setv("emacs_mode", 0),
        setv("emacs_mark", 0),
        setv("emacs_x", 0),
    ],
}
if TAP_ACTION:
    leader["to_if_alone"] = [{"key_code": TAP_ACTION}]
manipulators.append(leader)

# ---------------------------------------------------------------------------
# 2. C-g : keyboard-quit.  Drops the mark, drops any pending prefix, sends Esc.
# ---------------------------------------------------------------------------
manipulators.append(manip(
    "g", [key("escape")] + CLEAR_ALL, [EM], ANY, "C-g: keyboard-quit"))

# ---------------------------------------------------------------------------
# 3. The mark (set-mark).  Toggling it makes every motion extend the selection.
# ---------------------------------------------------------------------------
manipulators.append(manip(
    "spacebar", [setv("emacs_mark", 0)], [EM, MARK_ON], SHIFT,
    "M-SPC: drop the mark"))
manipulators.append(manip(
    "spacebar", [setv("emacs_mark", 1)], [EM, MARK_OFF], SHIFT,
    "M-SPC: set mark (selection follows every motion)"))

# Caps + Space keeps switching input sources, exactly as before.
manipulators.append(manip(
    "spacebar", [key("spacebar", ["left_control"])], [EM], NONE,
    "C-SPC: switch input source (control+space)"))

# ---------------------------------------------------------------------------
# 3b. Modifier pass-through on the four motion keys.
#
# Caps Lock emits no modifier of its own -- it only flips a variable -- so
# `Caps + Option + Shift + n` matches nothing unless we say so explicitly, and
# the application just receives a literal Option-Shift-n.  These rules forward
# whatever you hold to the arrow key, keeping arrow-based app shortcuts (VS
# Code duplicates a line with Option-Shift-Up or -Down) on the home row.
#
# Bare Shift is never forwarded: with META_MOD == "shift" it is Meta, and with
# META_MOD == "option" it is selection.  Option is skipped entirely when it is
# acting as Meta, otherwise M-f and this rule would fight over the same chord.
# ---------------------------------------------------------------------------
ARROW_KEYS = [("f", "right_arrow"), ("b", "left_arrow"),
              ("n", "down_arrow"), ("p", "up_arrow")]
PASSTHROUGH = [
    (["command"],          ["left_command"],               "cmd"),
    (["command", "shift"], ["left_command", "left_shift"], "cmd-shift"),
]
if META_MOD != "option":
    PASSTHROUGH = [
        (["option"],          ["left_option"],               "opt"),
        (["option", "shift"], ["left_option", "left_shift"], "opt-shift"),
    ] + PASSTHROUGH
for _k, _arrow in ARROW_KEYS:
    for _mand, _out, _label in PASSTHROUGH:
        manipulators.append(manip(
            _k, [key(_arrow, _out)], [EM],
            {"mandatory": _mand, "optional": ["caps_lock"]},
            f"{_label}+{_k}: forward {_label} to {_arrow}"))

# ---------------------------------------------------------------------------
# 4. C-x prefix: second stroke.  Must be matched before the plain bindings.
# ---------------------------------------------------------------------------
X_COMMANDS = [
    ("s", "s", ["left_command"],                 "C-x C-s: save"),
    ("f", "o", ["left_command"],                 "C-x C-f: open file"),
    ("w", "s", ["left_command", "left_shift"],   "C-x C-w: save as"),
    ("c", "q", ["left_command"],                 "C-x C-c: quit application"),
    ("k", "w", ["left_command"],                 "C-x k: close window/tab"),
    ("h", "a", ["left_command"],                 "C-x h: select all"),
    ("u", "z", ["left_command"],                 "C-x u: undo"),
    ("o", "grave_accent_and_tilde", ["left_command"], "C-x o: other window"),
]
for k, code, mods, desc in X_COMMANDS:
    manipulators.append(manip(
        k, [key(code, mods), setv("emacs_x", 0)], [EM, X_ON], NONE, desc))

# ---------------------------------------------------------------------------
# 5. Motions.  Each one gets a mark-mode twin that adds Shift.
# ---------------------------------------------------------------------------
C_MOVES = [
    ("f", "right_arrow", [],                "C-f: forward char"),
    ("b", "left_arrow",  [],                "C-b: backward char"),
    ("n", "down_arrow",  [],                "C-n: next line"),
    ("p", "up_arrow",    [],                "C-p: previous line"),
    ("a", "left_arrow",  ["left_command"],  "C-a: beginning of line"),
    ("e", "right_arrow", ["left_command"],  "C-e: end of line"),
    ("v", "page_down",   [],                "C-v: scroll up (page down)"),
]

M_MOVES = [
    ("f",      "right_arrow", ["left_option"],   "M-f: forward word"),
    ("b",      "left_arrow",  ["left_option"],   "M-b: backward word"),
    ("v",      "page_up",     [],                "M-v: scroll down (page up)"),
    ("a",      "up_arrow",    ["left_option"],   "M-a: backward sentence"),
    ("e",      "down_arrow",  ["left_option"],   "M-e: forward sentence"),
    ("comma",  "up_arrow",    ["left_command"],  "M-<: beginning of buffer"),
    ("period", "down_arrow",  ["left_command"],  "M->: end of buffer"),
]

# mark-mode twins first (narrower conditions win)
for k, code, mods, desc in M_MOVES:
    manipulators.append(manip(
        k, [key(code, mods + ["left_shift"])], [EM, MARK_ON], META,
        "mark " + desc))
for k, code, mods, desc in C_MOVES:
    manipulators.append(manip(
        k, [key(code, mods + ["left_shift"])], [EM, MARK_ON], PLAIN,
        "mark " + desc))

# ---------------------------------------------------------------------------
# 6. Meta-level editing
# ---------------------------------------------------------------------------
manipulators.append(manip(
    "d", [key("right_arrow", ["left_option", "left_shift"]),
          key("x", ["left_command"])],
    [EM], META, "M-d: kill word forward"))
manipulators.append(manip(
    "delete_or_backspace",
    [key("left_arrow", ["left_option", "left_shift"]),
     key("x", ["left_command"])],
    [EM], META, "M-DEL: kill word backward"))
manipulators.append(manip(
    "w", [key("c", ["left_command"]), setv("emacs_mark", 0)],
    [EM], META, "M-w: copy region"))

# plain meta motions
for k, code, mods, desc in M_MOVES:
    manipulators.append(manip(k, [key(code, mods)], [EM], META, desc))

# ---------------------------------------------------------------------------
# 7. Control-level editing
# ---------------------------------------------------------------------------
manipulators.append(manip(
    "w", [key("x", ["left_command"]), setv("emacs_mark", 0)],
    [EM], PLAIN, "C-w: kill region"))
manipulators.append(manip(
    "y", [key("v", ["left_command"]), setv("emacs_mark", 0)],
    [EM], PLAIN, "C-y: yank"))
manipulators.append(manip(
    "k", [key("right_arrow", ["left_command", "left_shift"]),
          key("x", ["left_command"])],
    [EM], PLAIN, "C-k: kill to end of line"))
manipulators.append(manip(
    "d", [key("delete_forward")], [EM], PLAIN, "C-d: delete char"))
manipulators.append(manip(
    "h", [key("delete_or_backspace")], [EM], PLAIN, "C-h: delete backward char"))
manipulators.append(manip(
    "o", [key("return_or_enter"), key("left_arrow")],
    [EM], PLAIN, "C-o: open line"))
manipulators.append(manip(
    "j", [key("return_or_enter")], [EM], PLAIN, "C-j: newline"))
manipulators.append(manip(
    "m", [key("return_or_enter")], [EM], PLAIN, "C-m: RET"))
manipulators.append(manip(
    "i", [key("tab")], [EM], PLAIN, "C-i: TAB"))
manipulators.append(manip(
    "s", [key("f", ["left_command"])], [EM], PLAIN, "C-s: search forward"))
manipulators.append(manip(
    "r", [key("g", ["left_command", "left_shift"])], [EM], PLAIN,
    "C-r: search backward (find previous)"))
manipulators.append(manip(
    "slash", [key("z", ["left_command"])], [EM], PLAIN, "C-/: undo"))

# plain control motions
for k, code, mods, desc in C_MOVES:
    manipulators.append(manip(k, [key(code, mods)], [EM], PLAIN, desc))

# ---------------------------------------------------------------------------
# 8. C-x prefix: first stroke (armed last so the consumers above win)
# ---------------------------------------------------------------------------
manipulators.append(manip(
    "x", [setv("emacs_x", 1)], [EM, X_OFF], NONE,
    "C-x: start two-stroke sequence",
    delayed={"to_if_invoked": [setv("emacs_x", 0)],
             "to_if_canceled": [setv("emacs_x", 0)]},
    params={"basic.to_delayed_action_delay_milliseconds": PREFIX_DELAY}))

meta_label = "Shift" if META_MOD == "shift" else "Option"
# ---------------------------------------------------------------------------
# 9. Close the mode: swallow every Option chord we did not define.
#
# Holding Caps Lock means "I am speaking Emacs".  Whatever this file does not
# define falls through to the application, and on a US layout `Option + letter`
# is character input: Option-s types ß, Option-p types pi, and Option-e / -i /
# -u / -n arm a dead key that silently eats the NEXT keystroke and turns it
# into an accent.  That is character input surfacing in the middle of a motion.
#
# Control is deliberately NOT swallowed here, and this is where the two configs
# diverge.  macOS's own Control bindings ARE the Emacs bindings -- C-a is the
# line start, C-y yanks, C-t transposes, C-o opens a line -- so a Control chord
# falling through lands on the same meaning this file gives it.  There is no
# second keybinding system surfacing, so there is nothing to close off.  The
# Vim config swallows Control precisely because there the two systems disagree.
#
# Command is left alone in both configs: it is the application's command system
# and has no Emacs notation to collide with.  Leaving Command out of both
# `mandatory` and `optional` is what excludes it -- a chord carrying Command
# has a leftover modifier this rule does not accept, so it does not match.
#
# This must stay LAST: `from.any` shadows every key.
# ---------------------------------------------------------------------------
if META_MOD != "option":
    manipulators.append({
        "type": "basic",
        "description": "swallow every Option chord this config does not define",
        "from": {"any": "key_code",
                 "modifiers": {"mandatory": ["option"],
                               "optional": ["caps_lock", "shift"]}},
        "to": [],
        "conditions": [EM],
    })

doc = {
    "title": f"Emacs Mode (Caps Lock leader, Meta = {meta_label}) - US layout",
    "maintainers": [MAINTAINER],
    "rules": [{
        "description": f"Emacs mode (Caps Lock leader) - hold Caps Lock for C-, "
                       f"add {meta_label} for M-  [US layout]",
        "manipulators": manipulators,
    }],
}

with open("emacs-mode.json", "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)
    f.write("\n")

print(f"META_MOD      : {META_MOD}")
print(f"manipulators  : {len(manipulators)}")
