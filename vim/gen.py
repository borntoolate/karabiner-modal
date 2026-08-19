#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a Karabiner-Elements complex_modifications rule set:
Vim-like navigation/editing for the whole of macOS, using Caps Lock as a held leader.

Shift is NOT used for selection.  It carries its normal Vim meaning instead:
Caps+Shift+4 is "$", Caps+Shift+g is "G", Caps+Shift+v is "V", and so on.
Selection is done the way Vim does it -- with visual mode (v / V).

Assumes a US (ANSI) keyboard layout.
"""
import json

# Shown in Karabiner's rule list. Use your GitHub handle if you publish this.
MAINTAINER = "borntoolate"

PREFIX_DELAY = 800  # ms allowed between the two strokes of dd / yy / gg / :w

# What a lone tap of the leader key should send.
# None = do nothing at all.  "escape" = send Escape.  Any key_code works.
TAP_ACTION = None

VM = {"type": "variable_if", "name": "vim_mode", "value": 1}
VIS_ON = {"type": "variable_if", "name": "vim_visual", "value": 1}
VIS_OFF = {"type": "variable_unless", "name": "vim_visual", "value": 1}

# from-modifier specs
NONE = {"optional": ["caps_lock"]}                        # no modifier held
SHIFT = {"mandatory": ["shift"], "optional": ["caps_lock"]}
CTRL = {"mandatory": ["control"], "optional": ["caps_lock"]}
ANY = {"optional": ["any"]}

MODSPEC = {"plain": NONE, "shift": SHIFT, "ctrl": CTRL}


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


manipulators = []

# ---------------------------------------------------------------------------
# 1. The leader: Caps Lock held = vim mode
# ---------------------------------------------------------------------------
leader = {
    "type": "basic",
    "description": "Caps Lock: hold = Vim leader"
                   + (f" / tap = {TAP_ACTION}" if TAP_ACTION else " / tap = nothing"),
    "from": {"key_code": "caps_lock", "modifiers": {"optional": ["any"]}},
    "to": [setv("vim_mode", 1)],
    "to_after_key_up": [
        setv("vim_mode", 0),
        setv("vim_visual", 0),
        setv("vim_g", 0),
        setv("vim_d", 0),
        setv("vim_y", 0),
        setv("vim_colon", 0),
    ],
}
if TAP_ACTION:
    leader["to_if_alone"] = [{"key_code": TAP_ACTION}]
manipulators.append(leader)

CLEAR_ALL = [setv("vim_visual", 0), setv("vim_g", 0), setv("vim_d", 0),
             setv("vim_y", 0), setv("vim_colon", 0)]

# Esc: leave visual mode / abandon a pending two-stroke sequence
manipulators.append(manip(
    "escape", [key("escape")] + CLEAR_ALL, [VM], ANY,
    "esc: leave visual mode / cancel (also passes Esc through)"))

# ---------------------------------------------------------------------------
# 2. Motions.  Every entry also gets a visual-mode twin that adds Shift.
#    kind: "plain" = no modifier, "shift" = Shift held, "both" = either,
#          "ctrl"  = Control held (Vim's C-f / C-b / C-d / C-u)
# ---------------------------------------------------------------------------
MOVES = [
    # --- Control-held motions come first so visual mode cannot swallow them ---
    ("f", "ctrl",  "page_down",   [],               "C-f: page down"),
    ("b", "ctrl",  "page_up",     [],               "C-b: page up"),
    ("d", "ctrl",  "page_down",   [],               "C-d: half page down"),
    ("u", "ctrl",  "page_up",     [],               "C-u: half page up"),
    # --- the ordinary ones ---
    ("h", "plain", "left_arrow",  [],               "h: left"),
    ("j", "plain", "down_arrow",  [],               "j: down"),
    ("k", "plain", "up_arrow",    [],               "k: up"),
    ("l", "plain", "right_arrow", [],               "l: right"),
    ("0", "plain", "left_arrow",  ["left_command"], "0: true start of line"),
    ("6", "both",  "left_arrow",  ["left_command"], "^: start of line"),
    ("4", "both",  "right_arrow", ["left_command"], "$: end of line"),
    ("w", "both",  "right_arrow", ["left_option"],  "w / W: next word"),
    ("e", "both",  "right_arrow", ["left_option"],  "e / E: end of word"),
    ("b", "both",  "left_arrow",  ["left_option"],  "b / B: previous word"),
    ("9", "both",  "up_arrow",    ["left_option"],  "(: previous sentence"),
    ("0", "shift", "down_arrow",  ["left_option"],  "): next sentence"),
    ("open_bracket",  "shift", "up_arrow",   ["left_option"], "{: previous paragraph"),
    ("close_bracket", "shift", "down_arrow", ["left_option"], "}: next paragraph"),
]


def expand(kind):
    return ["plain", "shift"] if kind == "both" else [kind]


# visual twins first (narrower conditions must win)
for k, kind, code, mods, desc in MOVES:
    for sub in expand(kind):
        manipulators.append(manip(
            k, [key(code, mods + ["left_shift"])], [VM, VIS_ON], MODSPEC[sub],
            "visual " + desc))
# ...then the Control-held ones, before anything that could shadow them
for k, kind, code, mods, desc in MOVES:
    if kind == "ctrl":
        manipulators.append(manip(k, [key(code, mods)], [VM], CTRL, desc))

# C-r: redo (Vim's own redo key)
manipulators.append(manip(
    "r", [key("z", ["left_command", "left_shift"])], [VM], CTRL, "C-r: redo"))

# ---------------------------------------------------------------------------
# 2b. Modifier pass-through on hjkl.
#
# Caps Lock emits no modifier of its own -- it only flips a variable -- so
# `Caps + Option + Shift + j` matches nothing unless we say so explicitly, and
# the application just receives a literal Option-Shift-j.  These rules make the
# obvious thing happen: whatever you hold is forwarded to the arrow key, so app
# shortcuts built on arrows (VS Code duplicates a line with Option-Shift-Up or
# -Down) stay reachable from the home row.
#
# Bare Shift is deliberately NOT forwarded: Shift carries Vim's uppercase
# meaning in this config (`Shift+j` is J, join lines), not selection.
#
# Control is left out because of what it means on the key we emit.  These rules
# output an arrow, and macOS splits Control in two: `Control + letter` is a text
# command (C-a, C-e, C-k -- the Emacs-derived bindings), but `Control + arrow`
# is Mission Control and Spaces, which is not a text operation at all.  There is
# no text meaning on the arrow side to forward Control to.  Section 9 makes the
# leftover Control chords inert instead of letting them fall through.
# ---------------------------------------------------------------------------
ARROW_KEYS = [("h", "left_arrow"), ("j", "down_arrow"),
              ("k", "up_arrow"), ("l", "right_arrow")]
PASSTHROUGH = [
    (["option"],           ["left_option"],                "opt"),
    (["command"],          ["left_command"],               "cmd"),
    (["option", "shift"],  ["left_option", "left_shift"],  "opt-shift"),
    (["command", "shift"], ["left_command", "left_shift"], "cmd-shift"),
]
for _k, _arrow in ARROW_KEYS:
    for _mand, _out, _label in PASSTHROUGH:
        manipulators.append(manip(
            _k, [key(_arrow, _out)], [VM],
            {"mandatory": _mand, "optional": ["caps_lock"]},
            f"{_label}+{_k}: forward {_label} to {_arrow}"))

# ---------------------------------------------------------------------------
# Selecting "the current line, newline included".
#
# The obvious spelling is ⌘← then ⇧↓, and it is wrong.  ⇧↓ keeps the column it
# started from, so if ⌘← did not land on column 0 the selection ends at that
# same column on the NEXT line -- and if the next line is shorter, at its end.
# VS Code and JetBrains make ⌘← stop at the first non-whitespace character, so
# on indented code the selection runs past the newline and eats what follows.
# Measured in Monaco (VS Code's editor core): with the caret in
# `  position: relative;` above a `}` line, ⌘← ⇧↓ selects
# `position: relative;\n}` -- dd then deletes the closing brace as well.
#
# So: never let the column matter.
#
#   ⌘→        end of the line.  Unambiguous, and it puts the caret to the
#             right of the first non-whitespace character, which is what makes
#             the next step deterministic.
#   ⌘← ⌘←     line start.  Smart-home apps stop at the indent on the first
#             press and toggle to column 0 on the second; apps with a plain
#             line start are already there and the second press is a no-op
#             (verified in Chromium's <textarea>).
#   ⌘⇧→       select to the end of the line.  No column arithmetic involved.
#   ⇧→        one more character: the newline.  On the last line of a document
#             there is none and this simply does nothing.
#
# The worst case is an app with a smart line start that does NOT toggle: the
# indentation is left behind, but the next line is never touched.
# ---------------------------------------------------------------------------
SELECT_LINE = [key("right_arrow", ["left_command"]),
               key("left_arrow", ["left_command"]),
               key("left_arrow", ["left_command"]),
               key("right_arrow", ["left_command", "left_shift"]),
               key("right_arrow", ["left_shift"])]

# ---------------------------------------------------------------------------
# 3. Visual mode
# ---------------------------------------------------------------------------
manipulators.append(manip(
    "v", [setv("vim_visual", 0)], [VM, VIS_ON], NONE, "v: leave visual mode"))
manipulators.append(manip(
    "v", [setv("vim_visual", 1)], [VM, VIS_OFF], NONE, "v: enter visual mode"))
manipulators.append(manip(
    "v", SELECT_LINE + [setv("vim_visual", 1)],
    [VM], SHIFT, "V: line-wise visual mode (selects the current line)"))

# operators that act on the selection and then leave visual mode
# Shift/no-Shift are spelled out separately so a stray Shift cannot leak into
# the output (Cmd-Shift-V is "paste and match style", not what we want here).
#
# `x` is deliberately NOT a synonym for `d` here, which is where this parts
# company with Vim.  Vim keeps what you delete in a register, so `d` costs you
# nothing; the unnamed register is a separate box from the system clipboard.
# macOS has only the one box.  Making every deletion a Cmd-X means the ordinary
# "copy this, select the old text, get rid of it, paste" sequence loses what you
# copied halfway through.  So the two meanings get one key each: `d` and `c`
# cut (Vim's contract -- `p` pastes back what you just removed), `x` deletes and
# leaves the clipboard alone.  It matches what `x` already does outside visual
# mode, where it is a plain forward delete.
VISUAL_OPS = [
    ("y", key("c", ["left_command"]), "copy selection"),
    ("d", key("x", ["left_command"]), "cut selection"),
    ("c", key("x", ["left_command"]), "cut selection"),
    ("x", key("delete_or_backspace"),
     "delete selection without touching the clipboard"),
    ("p", key("v", ["left_command"]), "replace selection with clipboard"),
]
for k, ev, desc in VISUAL_OPS:
    for spec, label in ((NONE, k), (SHIFT, k.upper())):
        manipulators.append(manip(
            k, [ev, setv("vim_visual", 0)], [VM, VIS_ON], spec,
            f"visual {label}: {desc}"))

# ---------------------------------------------------------------------------
# 4. Two-stroke sequences: gg / dd / yy / :w
# ---------------------------------------------------------------------------
G_ON = {"type": "variable_if", "name": "vim_g", "value": 1}
G_OFF = {"type": "variable_unless", "name": "vim_g", "value": 1}
D_ON = {"type": "variable_if", "name": "vim_d", "value": 1}
D_OFF = {"type": "variable_unless", "name": "vim_d", "value": 1}
Y_ON = {"type": "variable_if", "name": "vim_y", "value": 1}
Y_OFF = {"type": "variable_unless", "name": "vim_y", "value": 1}
COLON_ON = {"type": "variable_if", "name": "vim_colon", "value": 1}
COLON_OFF = {"type": "variable_unless", "name": "vim_colon", "value": 1}


def prefix_setter(k, var, from_mods, desc):
    return manip(
        k, [setv(var, 1)],
        [VM, {"type": "variable_unless", "name": var, "value": 1}],
        from_mods, desc,
        delayed={"to_if_invoked": [setv(var, 0)],
                 "to_if_canceled": [setv(var, 0)]},
        params={"basic.to_delayed_action_delay_milliseconds": PREFIX_DELAY})


# --- : (ex command line) : second stroke -----------------------------------
COLON_COMMANDS = [
    ("w", [key("s", ["left_command"])],                        ":w: save"),
    ("q", [key("w", ["left_command"])],                        ":q: close window/tab"),
    ("x", [key("s", ["left_command"]), key("w", ["left_command"])],
     ":x: save and close"),
]
for k, to_events, desc in COLON_COMMANDS:
    manipulators.append(manip(
        k, to_events + [setv("vim_colon", 0)], [VM, COLON_ON], NONE, desc))

# --- gg / G ----------------------------------------------------------------
manipulators.append(manip(
    "g", [key("up_arrow", ["left_command", "left_shift"]), setv("vim_g", 0)],
    [VM, G_ON, VIS_ON], NONE, "visual gg: select to start of document"))
manipulators.append(manip(
    "g", [key("up_arrow", ["left_command"]), setv("vim_g", 0)],
    [VM, G_ON], NONE, "gg: go to start of document"))
manipulators.append(manip(
    "g", [key("down_arrow", ["left_command", "left_shift"])],
    [VM, G_OFF, VIS_ON], SHIFT, "visual G: select to end of document"))
manipulators.append(manip(
    "g", [key("down_arrow", ["left_command"])],
    [VM, G_OFF], SHIFT, "G: go to end of document"))

# --- dd / D ----------------------------------------------------------------
manipulators.append(manip(
    "d", SELECT_LINE + [key("x", ["left_command"]), setv("vim_d", 0)],
    [VM, D_ON], NONE, "dd: cut the whole line"))
manipulators.append(manip(
    "d",
    [key("right_arrow", ["left_command", "left_shift"]),
     key("delete_or_backspace")],
    [VM, D_OFF], SHIFT, "D: delete from cursor to end of line"))

# --- yy / Y ----------------------------------------------------------------
YANK_LINE = SELECT_LINE + [key("c", ["left_command"]), key("left_arrow")]
manipulators.append(manip(
    "y", YANK_LINE + [setv("vim_y", 0)], [VM, Y_ON], NONE,
    "yy: yank (copy) the whole line"))
manipulators.append(manip(
    "y", YANK_LINE, [VM], SHIFT, "Y: yank the whole line (same as yy)"))

# ---------------------------------------------------------------------------
# 5. Single-key editing
# ---------------------------------------------------------------------------
manipulators.append(manip(
    "x", [key("delete_or_backspace")], [VM], SHIFT, "X: backspace"))
manipulators.append(manip(
    "x", [key("delete_forward")], [VM], NONE, "x: forward delete"))
manipulators.append(manip(
    "j", [key("right_arrow", ["left_command"]), key("delete_forward")],
    [VM], SHIFT, "J: join this line with the next"))
manipulators.append(manip(
    "o", [key("right_arrow", ["left_command"]), key("return_or_enter")],
    [VM], NONE, "o: open a line below"))
manipulators.append(manip(
    "o", [key("left_arrow", ["left_command"]), key("return_or_enter"),
          key("up_arrow")],
    [VM], SHIFT, "O: open a line above"))
# Two explicit rules rather than `optional: any` -- otherwise Shift would leak
# into the output and turn P into Cmd-Shift-V ("paste and match style").
manipulators.append(manip(
    "p", [key("v", ["left_command"])], [VM], SHIFT, "P: paste"))
manipulators.append(manip(
    "p", [key("v", ["left_command"])], [VM], NONE, "p: paste"))
manipulators.append(manip(
    "u", [key("z", ["left_command", "left_shift"])], [VM], SHIFT, "U: redo"))
manipulators.append(manip(
    "u", [key("z", ["left_command"])], [VM], NONE, "u: undo"))
manipulators.append(manip(
    "a", [key("a", ["left_command"])], [VM], NONE, "a: select all"))
manipulators.append(manip(
    "slash", [key("f", ["left_command"])], [VM], SHIFT, "?: search"))
manipulators.append(manip(
    "slash", [key("f", ["left_command"])], [VM], NONE, "/: search"))
manipulators.append(manip(
    "n", [key("g", ["left_command", "left_shift"])], [VM], SHIFT,
    "N: previous match"))
manipulators.append(manip(
    "n", [key("g", ["left_command"])], [VM], NONE, "n: next match"))

# Caps Lock + Space keeps switching input sources.
manipulators.append(manip(
    "spacebar", [key("spacebar", ["left_control"])], [VM], NONE,
    "space: switch input source (control+space)"))

# ---------------------------------------------------------------------------
# 6. Plain motions (widest matchers, so they go last)
# ---------------------------------------------------------------------------
for k, kind, code, mods, desc in MOVES:
    if kind == "ctrl":
        continue
    for sub in expand(kind):
        manipulators.append(manip(k, [key(code, mods)], [VM], MODSPEC[sub], desc))

# ---------------------------------------------------------------------------
# 7. Two-stroke first strokes (armed last so their consumers above win)
# ---------------------------------------------------------------------------
manipulators.append(prefix_setter("g", "vim_g", NONE, "g: start gg"))
manipulators.append(prefix_setter("d", "vim_d", NONE, "d: start dd"))
manipulators.append(prefix_setter("y", "vim_y", NONE, "y: start yy"))
manipulators.append(prefix_setter(
    "semicolon", "vim_colon", SHIFT, ": start ex command (:w / :q / :x)"))

# ---------------------------------------------------------------------------
# 8. Close the mode: swallow every Control / Option chord we did not define.
#
# Holding Caps Lock means "I am speaking Vim".  Whatever this file does not
# define used to fall through to the application, and falling through is not
# "nothing happens" -- macOS has its own bindings underneath:
#
#   Control + letter  is the Emacs-derived text system.  C-k kills to the end
#                     of the line, C-a goes to the line start, C-v pages down,
#                     C-y pastes, C-o opens a line.  Several collide head-on
#                     with Vim's meaning for the same key: C-v is visual block
#                     in Vim, C-o walks the jump list, C-a increments a number.
#   Option + letter   is character input.  Option-s types ß, Option-p types pi,
#                     and Option-e / -i / -u / -n arm a dead key that silently
#                     eats the NEXT keystroke and turns it into an accent.
#
# Both are other keybinding systems surfacing inside this one.  `from.any`
# matches every key at once, so two manipulators close the whole class.
#
# Command is deliberately left alone.  It is the application's command system,
# it has no Vim notation to collide with, and Caps+Cmd+S should still save.
# Leaving Command out of both `mandatory` and `optional` is what excludes it:
# a chord that carries Command has a leftover modifier these rules do not
# accept, so it does not match and reaches the application untouched.
#
# These must stay LAST.  `from.any` shadows every key, so anything placed after
# them would never fire.  validate.py knows this and will say so.
# ---------------------------------------------------------------------------
SWALLOW = [
    (["control"], ["caps_lock", "shift", "option"], "Control"),
    (["option"],  ["caps_lock", "shift"],           "Option"),
]
for _mand, _opt, _label in SWALLOW:
    manipulators.append({
        "type": "basic",
        "description": f"swallow every {_label} chord this config does not define",
        "from": {"any": "key_code",
                 "modifiers": {"mandatory": _mand, "optional": _opt}},
        "to": [],
        "conditions": [VM],
    })

doc = {
    "title": "Vim Mode (Caps Lock Leader) - US layout",
    "maintainers": [MAINTAINER],
    "rules": [{
        "description": "Vim mode (Caps Lock leader) - hold Caps Lock for Vim-style "
                       "navigation & editing; selection via visual mode [US layout]",
        "manipulators": manipulators,
    }],
}

with open("vim-mode.json", "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)
    f.write("\n")

print(f"manipulators: {len(manipulators)}")
