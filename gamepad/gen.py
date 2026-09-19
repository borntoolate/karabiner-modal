#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
8BitDo SN30 Pro をサブ入力デバイスにする Karabiner ルールの生成器。

    cd gamepad && python3 gen.py

出力（すべて生成物。手で編集しないこと）:
    gamepad-mode.json    complex_modifications のルール
    gamepad-device.json  スティックの効き（karabiner.json の devices に入る）
    CHEATSHEET.md        マニュアル。PDF の元

vim / emacs 版と違い、このモードは Caps Lock を使いません。リーダーは
コントローラーそのものです。キーボードのキーは一つも潰しません。

--------------------------------------------------------------------------
実機実測値（Karabiner-EventViewer、8Bitdo SN30 Pro / D-input / Bluetooth）:
    A=button1  B=button2  X=button4  Y=button5
    L=button7  R=button8  L2=button9 R2=button10
    Select=button11  Start=button12  ハート=button13
    左スティック押込=button14  右スティック押込=button15
    十字キー = generic_desktop dpad_up / dpad_down / dpad_left / dpad_right
    （button3 / button6 は存在しない）

Karabiner は DirectInput のパッドしか扱えない（X-input は非対応と公式が明記）。
コントローラーは Start + B で D-input にしておくこと。

`generic_desktop` を from に書けることは実機で確認済み（dpad_up → F18 が
EventViewer に出ることを確認）。公式ドキュメントには記載がない。
--------------------------------------------------------------------------
"""

import json
import os
import sys

# ===========================================================================
# デバイス
# ===========================================================================
DEVICE = {"vendor_id": 11720, "product_id": 24833, "is_game_pad": True}

# ===========================================================================
# スティックの効き
#
# Karabiner はスティックを2通りの方法で動かす（16.3.0 の
# game_pad_stick_converter.hpp で確認。DESIGN.md §6）。
#   1. ナッジ   … 傾きが「増えた」ぶん × flick だけ、HID レポートが届くたびに動く。
#                 待ちはない。戻す動きと、傾きを保ったままの回転では動かない
#   2. 連続移動 … 傾きが continued_movement_absolute_magnitude_threshold 以上に
#                 なるとタイマーが回り、倒している間ずっと動き続ける
#
# 連続移動のタイマーは開始間隔が 300 ms にハードコードされている。しきい値を
# 超えた瞬間にナッジは止まり、300 ms 後に最初の連続移動イベントが出て、そこから
# interval_milliseconds ごとになる。この 300 ms はどの設定でも消せない。
# deadzone と threshold を同じ値にすると、倒した瞬間にこの空白が始まる。
# それが「倒してから動き出すまでの待ち」の正体だった。
#
# 左スティックはしきい値を高くして初動をナッジに任せ、いっぱいに倒して保持した
# ときだけ連続移動に入る形にしてある。右スティックは比較用に低いままにしてある
# （倒して 300 ms 後から動き続ける）。どちらが体に合うかは実機で決める。
#
# タイマーは両スティックで1本を共有する。片方が連続移動している間、もう片方は
# ナッジも連続移動も出ない。
# ===========================================================================
_XY_FORMULA = """\
var m:= 0;

if (continued_movement == false) {{
  m := delta_magnitude * {flick};
}} else if (absolute_magnitude < 1.5) {{
  m := absolute_magnitude * {slow};
}} else if (absolute_magnitude < 2) {{
  m := absolute_magnitude * {mid};
}} else {{
  m := absolute_magnitude * {fast};
}};

{trig}(radian) * m;
"""

_WHEEL_FORMULA = """\
var m := 0;

if (abs(cos(radian)) {cmp} abs(sin(radian))) {{
  if (continued_movement == false) {{
    m := delta_magnitude * {flick};
  }} else {{
    m := absolute_magnitude * {hold};
  }};
}};

{trig}(radian) * m;
"""

# カーソル速度。Karabiner 既定は 16 / 8 / 12 / 24。
#   flick … ナッジの係数。いっぱいまで倒すと (threshold − deadzone) × flick ピクセル
#   slow  … 連続移動の係数。傾き × slow ピクセルが interval ごとに出る
#   mid / fast … 傾きは 1.0 で頭打ちなので単独では発火しない。連続移動中に
#                もう片方のスティックも倒すと、その傾きが足されて効く
XY_SPEED = {"flick": 150, "slow": 13, "mid": 24, "fast": 40}

# スクロール速度。Karabiner 既定は 1 / 0.1。
WHEEL_SPEED = {"flick": 1.0, "hold": 0.15}

DEVICE_SETTINGS = {
    # --- 左スティック（カーソル）: ナッジ + いっぱいに倒して保持で連続移動 ---
    "game_pad_xy_stick_deadzone": 0.05,
    "game_pad_xy_stick_delta_magnitude_detection_threshold": 0.005,
    # ここ以上に倒して 300 ms 保持すると連続移動。下げるほど早く入るが、
    # 超えた瞬間からナッジが止まって 300 ms の空白ができる
    "game_pad_xy_stick_continued_movement_absolute_magnitude_threshold": 0.9,
    "game_pad_xy_stick_continued_movement_interval_milliseconds": 10,
    "game_pad_stick_x_formula": _XY_FORMULA.format(trig="cos", **XY_SPEED),
    "game_pad_stick_y_formula": _XY_FORMULA.format(trig="sin", **XY_SPEED),
    # --- 右スティック（スクロール）: 倒して 300 ms 後から連続移動 ---
    "game_pad_wheels_stick_deadzone": 0.05,
    "game_pad_wheels_stick_delta_magnitude_detection_threshold": 0.005,
    "game_pad_wheels_stick_continued_movement_absolute_magnitude_threshold": 0.05,
    "game_pad_wheels_stick_continued_movement_interval_milliseconds": 10,
    "game_pad_stick_vertical_wheel_formula":
        _WHEEL_FORMULA.format(cmp="<", trig="sin", **WHEEL_SPEED),
    "game_pad_stick_horizontal_wheel_formula":
        _WHEEL_FORMULA.format(cmp=">", trig="cos", **WHEEL_SPEED),
    # 左右のスティックの役割が逆に感じたら True
    "game_pad_swap_sticks": False,
}

# ===========================================================================
# 物理ボタン -> HID イベント（実測値。いじらない）
# ===========================================================================
BTN = {
    "A":      ("pointing_button", "button1"),
    "B":      ("pointing_button", "button2"),
    "X":      ("pointing_button", "button4"),
    "Y":      ("pointing_button", "button5"),
    "L":      ("pointing_button", "button7"),
    "R":      ("pointing_button", "button8"),
    "L2":     ("pointing_button", "button9"),
    "R2":     ("pointing_button", "button10"),
    "SELECT": ("pointing_button", "button11"),
    "START":  ("pointing_button", "button12"),
    "HEART":  ("pointing_button", "button13"),
    "L3":     ("pointing_button", "button14"),
    "R3":     ("pointing_button", "button15"),
    "UP":     ("generic_desktop", "dpad_up"),
    "DOWN":   ("generic_desktop", "dpad_down"),
    "LEFT":   ("generic_desktop", "dpad_left"),
    "RIGHT":  ("generic_desktop", "dpad_right"),
}

# 早見表での表示名と並び順
LABEL = {
    "A": "A", "B": "B", "X": "X", "Y": "Y",
    "UP": "十字 ↑", "DOWN": "十字 ↓", "LEFT": "十字 ←", "RIGHT": "十字 →",
    "L": "L", "R": "R", "L2": "L2", "R2": "R2",
    "SELECT": "Select（−）", "START": "Start（＋）", "HEART": "ハート",
    "L3": "左スティック押込", "R3": "右スティック押込",
}
ORDER = ["A", "B", "X", "Y",
         "UP", "DOWN", "LEFT", "RIGHT",
         "L", "R",
         "SELECT", "START", "HEART",
         "L3", "R3"]

# ===========================================================================
# 役割
#
#   単押しは全アプリで固定（キーボードとマウスの代わり）。アプリごとに変えて
#   よいのは R2 を押しながらの層だけ。理由は DESIGN.md §5。
#
#   L とハートは本物の修飾キー。押している間 ⇧ / ⌘ が立つので、十字・クリック・
#   Enter・スクロールと勝手に合成される（L + 十字 = 選択、ハート + L3 = ⌘クリック）。
#   そのために全ルールの from.modifiers を optional: ["any"] にしてある。
#   押されている修飾キーはそのまま to に運ばれる。vim 版では事故だが、ここでは狙い。
#
#   値は ("キー指定", "早見表に出す説明") の組。
#     "escape"                    単キー
#     "cmd+shift+open_bracket"    修飾キー付き（cmd / shift / opt / ctrl / fn）
#     "escape escape"             スペース区切りで連続入力
#     "click:button1"             マウスクリックを送る
#     "hold:spacebar"             押している間だけ押しっぱなしにする
# ===========================================================================
# L2 = 音声入力の開始 / 終了。
# Apple のキーボードのマイクキー（F5）と同じ HID イベント（consumer usage
# "dictation"）を送る。macOS の音声入力はこれで起動・終了するので、システム設定の
# ショートカット（⌘ を2回など）には依存しない。トグルなので押している間ではなく、
# 押すたびに開始 / 終了（DESIGN.md §5）。
VOICE_BUTTON = "L2"
VOICE_KEY = {"consumer_key_code": "dictation"}

# R2 押しっぱなし = レイヤー2 修飾
MOD_BUTTON = "R2"
MOD_VAR = "sn30_mod"

# 押している間だけ立つ本物の修飾キー。lazy なので単押しでは何も出ない。
SHIFT_BUTTON = "L"
CMD_BUTTON = "HEART"
# ハートを単押ししたとき（他のボタンを押さずに離したとき）
APP_SWITCH = ("cmd+tab", "直前のアプリへ。押したまま R で順送り")

# 単押し。全アプリで同じ。
BASE = {
    "A":      ("return_or_enter", "Enter / 決定"),
    "B":      ("escape", "Esc / 中断"),
    "X":      ("delete_forward", "Delete（前方削除）"),
    "Y":      ("delete_or_backspace", "Backspace"),
    "UP":     ("up_arrow", "↑"),
    "DOWN":   ("down_arrow", "↓"),
    "LEFT":   ("left_arrow", "←"),
    "RIGHT":  ("right_arrow", "→"),
    "R":      ("tab", "Tab（次の要素へ）。L + R で ⇧Tab"),
    "SELECT": ("cmd+c", "コピー"),
    "START":  ("cmd+v", "貼り付け"),
    "L3":     ("click:button1", "左クリック"),
    "R3":     ("click:button2", "右クリック"),
}

# 修飾キーとの組み合わせで得られるもの（早見表に載せる。ルールは作らない）
COMBOS = [
    ("L + 十字", "選択を伸ばす（⇧矢印）"),
    ("L + 左スティック押込", "⇧クリック（範囲選択）"),
    ("L + A", "⇧Enter（送信せずに改行）"),
    ("L + R", "⇧Tab（前の要素へ。Claude Code では権限モードの切り替え）"),
    ("L + 右スティック", "横スクロール"),
    ("ハート + R", "⌘Tab を続けて送る。ハートを離すまでスイッチャーが出たまま"),
    ("ハート + 十字 ←→", "行頭 / 行末（⌘矢印）"),
    ("ハート + 十字 ↑↓", "文頭 / 文末"),
    ("ハート + Y", "行頭まで削除（⌘Backspace）"),
    ("ハート + 左スティック押込", "⌘クリック"),
    ("ハート + 右スティック", "⌘スクロール（対応アプリでズーム）"),
    ("ハート + L + 十字", "行末 / 行頭まで選択"),
]

# R2 を押しながら。アプリ別に上書きできるのはこの層だけ。
MOD_DEFAULT = {
    "A":      ("cmd+a", "すべて選択"),
    "B":      ("cmd+w", "閉じる"),
    "X":      ("cmd+shift+z", "やり直す"),
    "Y":      ("cmd+z", "取り消す"),
    "UP":     ("page_up", "1画面ぶん上へ"),
    "DOWN":   ("page_down", "1画面ぶん下へ"),
    "LEFT":   ("opt+left_arrow", "1単語左へ"),
    "RIGHT":  ("opt+right_arrow", "1単語右へ"),
    "L":      ("ctrl+shift+tab", "前のタブ"),
    "R":      ("ctrl+tab", "次のタブ"),
    "SELECT": ("cmd+x", "切り取り"),
    "START":  ("cmd+shift+v", "書式なしで貼り付け"),
    "HEART":  ("cmd+spacebar", "Spotlight / ランチャー"),
}
# アプリ別に上書きできない枠。編集の芯はどのアプリでも同じ場所にある。
MOD_LOCKED = {"X", "Y", "SELECT", "HEART"}

# ===========================================================================
# アプリ別（R2 を押しながらの上書きだけ）
#
#   apps: frontmost_application_if の bundle_identifiers（正規表現）。
#   mod:  MOD_DEFAULT のうち MOD_LOCKED 以外を差し替える。書かないボタンは既定のまま。
#   上にあるアプリが優先。
# ===========================================================================
APPS = [
    {
        "name": "ターミナル / Claude Code",
        "apps": [
            r"^com\.apple\.Terminal$",
            r"^com\.lambdalisue\.Arto$",
            r"^com\.microsoft\.VSCode$",
            r"^com\.anthropic\.claudefordesktop$",
            r"^com\.googlecode\.iterm2$",
            r"^com\.mitchellh\.ghostty$",
            r"^dev\.warp\.Warp-Stable$",
            r"^com\.github\.wez\.wezterm$",
        ],
        "mod": {
            "A":      ("opt+return_or_enter", "改行（送信しない）"),
            "B":      ("ctrl+c", "強制中断"),
            "START":  ("cmd+k", "画面をクリア"),
        },
    },

    {
        "name": "ブラウザ",
        "apps": [
            r"^com\.google\.Chrome$",
            r"^com\.apple\.Safari$",
            r"^org\.mozilla\.firefox$",
            r"^com\.brave\.Browser$",
            r"^company\.thebrowser\.Browser$",
        ],
        "mod": {
            "A":      ("cmd+t", "新規タブ"),
            "START":  ("cmd+r", "リロード"),
            "LEFT":   ("cmd+open_bracket", "戻る"),
            "RIGHT":  ("cmd+close_bracket", "進む"),
        },
    },
]

# ===========================================================================
# 机に向かうアプリ（左手デバイス特化）
#
#   デザイン制作・音楽制作はキーボードとマウスを使う前提なので、コントローラーは
#   左手デバイスとして特化させる。ここだけは単押しも上書きできる。
#   書かないボタンは BASE / MOD_DEFAULT に落ちる（十字は矢印のまま、など）。
#   ハートは上書きできない。机に向かっていてもアプリ切り替えは要る。
#   割り当ては実機未検証の初期案（DESIGN.md §9）。
# ===========================================================================
DESK_LOCKED = {"HEART"}

DESK_APPS = [
    {
        "name": "Figma",
        "apps": [r"^com\.figma\.Desktop$"],
        "base": {
            "A":      ("return_or_enter", "中に入る / 編集"),
            "B":      ("escape", "抜ける"),
            "X":      ("v", "移動ツール"),
            "Y":      ("cmd+z", "取り消し"),
            "UP":     ("up_arrow", "1px 上へ"),
            "DOWN":   ("down_arrow", "1px 下へ"),
            "LEFT":   ("left_arrow", "1px 左へ"),
            "RIGHT":  ("right_arrow", "1px 右へ"),
            "L":      ("cmd+hyphen", "ズームアウト"),
            "R":      ("cmd+equal_sign", "ズームイン"),
            "SELECT": ("shift+1", "全体を表示"),
            "START":  ("shift+2", "選択範囲にズーム"),
        },
        "mod": {
            "A":      ("cmd+d", "複製"),
            "B":      ("cmd+shift+z", "やり直す"),
            "X":      ("cmd+g", "グループ化"),
            "Y":      ("cmd+shift+g", "グループ解除"),
            "UP":     ("shift+up_arrow", "10px 上へ"),
            "DOWN":   ("shift+down_arrow", "10px 下へ"),
            "LEFT":   ("shift+left_arrow", "10px 左へ"),
            "RIGHT":  ("shift+right_arrow", "10px 右へ"),
            "L":      ("shift+0", "100% 表示"),
            "R":      ("shift+2", "選択範囲にズーム"),
            "SELECT": ("cmd+opt+c", "プロパティをコピー"),
            "START":  ("cmd+opt+v", "プロパティを貼り付け"),
        },
    },

    {
        "name": "Photoshop",
        "apps": [r"^com\.adobe\.Photoshop"],
        "base": {
            "A":      ("b", "ブラシ"),
            "B":      ("e", "消しゴム"),
            "X":      ("cmd+z", "取り消し"),
            "Y":      ("i", "スポイト"),
            "UP":     ("opt+close_bracket", "上のレイヤーを選択"),
            "DOWN":   ("opt+open_bracket", "下のレイヤーを選択"),
            "LEFT":   ("cmd+opt+z", "段階的に戻る"),
            "RIGHT":  ("cmd+shift+z", "段階的に進む"),
            "L":      ("open_bracket", "ブラシを小さく"),
            "R":      ("close_bracket", "ブラシを大きく"),
            "SELECT": ("cmd+shift+n", "新規レイヤー"),
            "START":  ("cmd+s", "保存"),
            "L3":     ("hold:spacebar", "押している間だけ手のひらツール（パン）"),
            "R3":     ("click:button2", "右クリック（ブラシ設定）"),
        },
        "mod": {
            "A":      ("v", "移動ツール"),
            "B":      ("cmd+d", "選択を解除"),
            "X":      ("cmd+shift+i", "選択範囲を反転"),
            "Y":      ("g", "塗りつぶし"),
            "UP":     ("cmd+close_bracket", "レイヤーを前面へ"),
            "DOWN":   ("cmd+open_bracket", "レイヤーを背面へ"),
            "LEFT":   ("cmd+0", "画面に合わせる"),
            "RIGHT":  ("cmd+1", "100% 表示"),
            "L":      ("cmd+hyphen", "ズームアウト"),
            "R":      ("cmd+equal_sign", "ズームイン"),
            "SELECT": ("cmd+j", "レイヤーを複製"),
            "START":  ("cmd+shift+s", "別名で保存"),
        },
    },

    {
        "name": "Illustrator",
        "apps": [r"^com\.adobe\.illustrator"],
        "base": {
            "A":      ("v", "選択ツール"),
            "B":      ("a", "ダイレクト選択"),
            "X":      ("cmd+z", "取り消し"),
            "Y":      ("i", "スポイト"),
            "L":      ("cmd+hyphen", "ズームアウト"),
            "R":      ("cmd+equal_sign", "ズームイン"),
            "SELECT": ("cmd+g", "グループ化"),
            "START":  ("cmd+s", "保存"),
            "L3":     ("hold:spacebar", "押している間だけ手のひらツール（パン）"),
        },
        "mod": {
            "A":      ("cmd+shift+z", "やり直す"),
            "B":      ("cmd+shift+a", "選択を解除"),
            "X":      ("cmd+2", "ロック"),
            "Y":      ("cmd+opt+2", "すべてロック解除"),
            "UP":     ("shift+up_arrow", "大きく上へ"),
            "DOWN":   ("shift+down_arrow", "大きく下へ"),
            "LEFT":   ("shift+left_arrow", "大きく左へ"),
            "RIGHT":  ("shift+right_arrow", "大きく右へ"),
            "L":      ("cmd+0", "アートボードに合わせる"),
            "R":      ("cmd+1", "100% 表示"),
            "SELECT": ("cmd+shift+g", "グループ解除"),
            "START":  ("cmd+shift+s", "別名で保存"),
        },
    },

    {
        "name": "After Effects",
        "apps": [r"^com\.adobe\.AfterEffects"],
        "base": {
            "A":      ("spacebar", "再生 / 停止"),
            "B":      ("escape", "中断"),
            "X":      ("cmd+z", "取り消し"),
            "Y":      ("cmd+shift+z", "やり直す"),
            "UP":     ("up_arrow", "上のレイヤーを選択"),
            "DOWN":   ("down_arrow", "下のレイヤーを選択"),
            "LEFT":   ("page_up", "1フレーム戻る"),
            "RIGHT":  ("page_down", "1フレーム進む"),
            "L":      ("j", "前のキーフレームへ"),
            "R":      ("k", "次のキーフレームへ"),
            "SELECT": ("u", "キーフレームを表示"),
            "START":  ("cmd+s", "保存"),
            "L3":     ("spacebar", "再生 / 停止"),
        },
        "mod": {
            "A":      ("keypad_0", "プレビュー"),
            "B":      ("cmd+d", "複製"),
            "X":      ("cmd+opt+z", "段階的に戻る"),
            "Y":      ("e", "エフェクトを表示"),
            "UP":     ("cmd+up_arrow", "レイヤーを上へ"),
            "DOWN":   ("cmd+down_arrow", "レイヤーを下へ"),
            "LEFT":   ("shift+page_up", "10フレーム戻る"),
            "RIGHT":  ("shift+page_down", "10フレーム進む"),
            "L":      ("comma", "ズームアウト"),
            "R":      ("period", "ズームイン"),
            "SELECT": ("cmd+shift+s", "別名で保存"),
            "START":  ("cmd+m", "レンダーキューに追加"),
        },
    },

    {
        "name": "Logic Pro",
        "apps": [r"^com\.apple\.logic10$"],
        "base": {
            "A":      ("spacebar", "再生 / 停止"),
            "B":      ("return_or_enter", "先頭へ戻る"),
            "X":      ("r", "録音"),
            "Y":      ("cmd+z", "取り消し"),
            "UP":     ("up_arrow", "上のトラックを選択"),
            "DOWN":   ("down_arrow", "下のトラックを選択"),
            "LEFT":   ("comma", "1小節戻る"),
            "RIGHT":  ("period", "1小節進む"),
            "L":      ("c", "サイクルを ON / OFF"),
            "R":      ("z", "選択範囲にズーム / 戻す"),
            "SELECT": ("m", "ミュート"),
            "START":  ("s", "ソロ"),
        },
        "mod": {
            "A":      ("cmd+s", "保存"),
            "B":      ("cmd+shift+z", "やり直す"),
            "X":      ("cmd+r", "リージョンを繰り返す"),
            "Y":      ("cmd+b", "バウンス"),
            "UP":     ("cmd+up_arrow", "垂直ズームイン"),
            "DOWN":   ("cmd+down_arrow", "垂直ズームアウト"),
            "LEFT":   ("cmd+left_arrow", "水平ズームアウト"),
            "RIGHT":  ("cmd+right_arrow", "水平ズームイン"),
            "L":      ("o", "サイクル範囲を選択範囲に合わせる"),
            "R":      ("cmd+0", "ズームを戻す"),
            "SELECT": ("cmd+c", "コピー"),
            "START":  ("cmd+v", "貼り付け"),
        },
    },
]

# ===========================================================================
# 生成ロジック
# ===========================================================================
RULE_PREFIX = "[SN30]"

MODIFIER_ALIASES = {
    "cmd": "left_command", "command": "left_command",
    "shift": "left_shift",
    "opt": "left_option", "alt": "left_option", "option": "left_option",
    "ctrl": "left_control", "control": "left_control",
    "fn": "fn",
}

# 早見表の表記
MOD_SYMBOL = {"cmd": "⌘", "command": "⌘", "shift": "⇧", "opt": "⌥",
              "alt": "⌥", "option": "⌥", "ctrl": "⌃", "control": "⌃", "fn": "fn"}
KEY_SYMBOL = {
    "return_or_enter": "return", "delete_or_backspace": "⌫", "delete_forward": "⌦",
    "spacebar": "space", "escape": "esc", "tab": "tab",
    "up_arrow": "↑", "down_arrow": "↓", "left_arrow": "←", "right_arrow": "→",
    "page_up": "PgUp", "page_down": "PgDn",
    "open_bracket": "[", "close_bracket": "]",
    "hyphen": "-", "equal_sign": "=", "comma": ",", "period": ".",
    "keypad_0": "テンキー0",
}


def device_condition():
    return {"type": "device_if", "identifiers": [dict(DEVICE)]}


def app_condition(patterns):
    return {"type": "frontmost_application_if", "bundle_identifiers": list(patterns)}


def from_event(button):
    kind, value = BTN[button]
    # optional: any … 押されている修飾キー（L の ⇧、ハートの ⌘、実キーボード）を
    # そのまま to に運ぶ。これがないと修飾キーを握っている間はルールが一切効かない。
    return {kind: value, "modifiers": {"optional": ["any"]}}


# 押しっぱなしで繰り返してよいキー（矢印・削除・ページ送り）。それ以外は
# repeat: false にして、ボタンを長めに押しても1回しか出ないようにする。Enter や
# ⌘W がキーリピートで連打される事故を防ぐため。押している間だけ効かせたいキー
# （Photoshop の手のひらツール = スペース）は "hold:" を付ける。クリックは押している間
# ドラッグになるので対象外。
REPEAT_KEYS = {"up_arrow", "down_arrow", "left_arrow", "right_arrow",
               "page_up", "page_down", "delete_or_backspace", "delete_forward"}


def parse_to_token(token):
    if token.startswith("click:"):
        return {"pointing_button": token.split(":", 1)[1]}
    hold = token.startswith("hold:")
    if hold:
        token = token[len("hold:"):]
    parts = token.split("+")
    key, mods = parts[-1], []
    for raw in parts[:-1]:
        alias = raw.strip().lower()
        if alias not in MODIFIER_ALIASES:
            raise ValueError("未知の修飾キー: %s (in %r)" % (raw, token))
        mods.append(MODIFIER_ALIASES[alias])
    event = {"key_code": key}
    if mods:
        event["modifiers"] = mods
    if key not in REPEAT_KEYS and not hold:
        event["repeat"] = False
    return event


def parse_to(spec):
    return [parse_to_token(t) for t in spec.split() if t]


def pretty(spec):
    """'cmd+shift+open_bracket' -> '⌘⇧['  /  'escape escape' -> 'esc esc'"""
    out = []
    for token in spec.split():
        if token.startswith("click:"):
            out.append("マウス左" if token.endswith("button1") else "マウス右")
            continue
        if token.startswith("hold:"):
            token = token[len("hold:"):]
        parts = token.split("+")
        key = parts[-1]
        syms = "".join(MOD_SYMBOL.get(p.lower(), p) for p in parts[:-1])
        out.append(syms + KEY_SYMBOL.get(key, key.upper() if len(key) == 1 else key))
    return " ".join(out)


def manipulator(button, spec, conditions, description):
    return {
        "type": "basic",
        "description": description,
        "from": from_event(button),
        "to": parse_to(spec),
        "conditions": conditions,
    }


def mod_layer(app, locked=MOD_LOCKED):
    """そのアプリで効く R2 レイヤー（既定 + 上書き）。上書きした枠の集合も返す。"""
    over = app.get("mod", {})
    bad = set(over) & locked
    assert not bad, "%s: 上書きできない枠 %s" % (app["name"], sorted(bad))
    unknown = set(over) - set(MOD_DEFAULT)
    assert not unknown, "%s: R2 既定にない枠 %s" % (app["name"], sorted(unknown))
    merged = dict(MOD_DEFAULT)
    merged.update(over)
    return merged, set(over)


def desk_base_layer(app):
    """机に向かうアプリの単押し（BASE + 上書き）。上書きした枠の集合も返す。"""
    over = app.get("base", {})
    bad = set(over) & DESK_LOCKED
    assert not bad, "%s: 上書きできない枠 %s" % (app["name"], sorted(bad))
    unknown = set(over) - set(BTN)
    assert not unknown, "%s: 存在しないボタン %s" % (app["name"], sorted(unknown))
    merged = dict(BASE)
    merged.update(over)
    return merged, set(over)


def build_rules():
    dev = device_condition()
    mod_on = {"type": "variable_if", "name": MOD_VAR, "value": 1}
    mod_off = {"type": "variable_unless", "name": MOD_VAR, "value": 1}

    rules = [
        {
            "description": "%s 音声入力の開始 / 終了（L2 でマイクキー）" % RULE_PREFIX,
            "manipulators": [{
                "type": "basic",
                "description": "L2 -> マイクキー（音声入力の開始 / 終了）",
                "from": from_event(VOICE_BUTTON),
                "to": [dict(VOICE_KEY, repeat=False)],
                "conditions": [dev],
            }],
        },
        {
            "description": "%s レイヤー修飾（R2 を押している間だけ %s=1）"
                           % (RULE_PREFIX, MOD_VAR),
            "manipulators": [{
                "type": "basic",
                "description": "R2 -> %s" % MOD_VAR,
                "from": from_event(MOD_BUTTON),
                "to": [{"set_variable": {"name": MOD_VAR, "value": 1}}],
                "to_after_key_up": [{"set_variable": {"name": MOD_VAR, "value": 0}}],
                "conditions": [dev],
            }],
        },
    ]

    # アプリ別の上書き（狭い条件）を先に、既定（広い条件）をあとに積む。
    # 机に向かうアプリは単押しも上書きするので、R2 ぶんと単押しぶんを1本にまとめる。
    for app in DESK_APPS:
        mod_layer(app, DESK_LOCKED)
        desk_base_layer(app)
        appc = app_condition(app["apps"])
        manips = [
            manipulator(b, app["mod"][b][0], [dev, mod_on, appc],
                        "R2 + %s -> %s (%s)" % (LABEL[b], pretty(app["mod"][b][0]),
                                                app["mod"][b][1]))
            for b in ORDER if b in app.get("mod", {})]
        manips += [
            manipulator(b, app["base"][b][0], [dev, mod_off, appc],
                        "%s -> %s (%s)" % (LABEL[b], pretty(app["base"][b][0]),
                                           app["base"][b][1]))
            for b in ORDER if b in app.get("base", {})]
        rules.append({"description": "%s %s（左手デバイス特化）" % (RULE_PREFIX, app["name"]),
                      "manipulators": manips})

    for app in APPS:
        mod_layer(app)  # 上書きできない枠に触っていないか
        conds = [dev, mod_on, app_condition(app["apps"])]
        manips = [
            manipulator(b, app["mod"][b][0], conds,
                        "R2 + %s -> %s (%s)" % (LABEL[b], pretty(app["mod"][b][0]),
                                                app["mod"][b][1]))
            for b in ORDER if b in app["mod"]]
        rules.append({"description": "%s %s（R2 を押しながら）" % (RULE_PREFIX, app["name"]),
                      "manipulators": manips})

    rules.append({
        "description": "%s R2 を押しながら（どのアプリでも）" % RULE_PREFIX,
        "manipulators": [
            manipulator(b, MOD_DEFAULT[b][0], [dev, mod_on],
                        "R2 + %s -> %s (%s)" % (LABEL[b], pretty(MOD_DEFAULT[b][0]),
                                                MOD_DEFAULT[b][1]))
            for b in ORDER if b in MOD_DEFAULT],
    })

    # 単押し。修飾キー2つは専用の形。
    base = [
        {
            "type": "basic",
            "description": "%s -> ⇧（押している間）" % LABEL[SHIFT_BUTTON],
            "from": from_event(SHIFT_BUTTON),
            "to": [{"key_code": "left_shift", "lazy": True}],
            "conditions": [dev, mod_off],
        },
        {
            "type": "basic",
            "description": "%s -> ⌘（押している間）/ 単押しで %s (%s)"
                           % (LABEL[CMD_BUTTON], pretty(APP_SWITCH[0]), APP_SWITCH[1]),
            "from": from_event(CMD_BUTTON),
            "to": [{"key_code": "left_command", "lazy": True}],
            "to_if_alone": parse_to(APP_SWITCH[0]),
            "conditions": [dev, mod_off],
        },
    ]
    base += [
        manipulator(b, BASE[b][0], [dev, mod_off],
                    "%s -> %s (%s)" % (LABEL[b], pretty(BASE[b][0]), BASE[b][1]))
        for b in ORDER if b in BASE]
    rules.append({"description": "%s 単押し（どのアプリでも）" % RULE_PREFIX,
                  "manipulators": base})
    return rules


# ===========================================================================
# マニュアル（CHEATSHEET.md）
#
# PDF はマークダウンの表だけを拾う。1つの見出しの下に表を2つ置かないこと
# （散文が落ちて、列見出しだけが2回続く）。base / mod は ### で分ける。
# 位置図はコードブロックなので PDF には載らない。紙に要らない表は見出しの下に
# <!-- pdf: skip --> を置いて外す。
# ===========================================================================
# 位置図。日本語を混ぜると等幅でも桁がずれるので、図の中は ASCII だけにして
# 対応表を下に置く。
FIGURE = """\
   L2 ==================                        ================== R2
   L  ====================                    ==================== R
  +----------------------------------------------------------------+
  |        [UP]                                          (X)       |
  |  [LEFT] -+- [RIGHT]      SELECT   START         (Y)       (A)  |
  |       [DOWN]               (-)     (+)               (B)       |
  |                                                                |
  |                          STAR   HEART                          |
  |               (L3)                          (R3)               |
  |            left stick                    right stick           |
  +----------------------------------------------------------------+
"""


def stick_note(stick):
    """スティックの挙動を1行で。しきい値の置き方で2通りに分かれる（DESIGN.md §6）。"""
    dz = DEVICE_SETTINGS["game_pad_%s_stick_deadzone" % stick]
    th = DEVICE_SETTINGS[
        "game_pad_%s_stick_continued_movement_absolute_magnitude_threshold" % stick]
    if th <= dz:
        return "倒して 0.3 秒後から動き続ける"
    return "倒した量だけ動き、%g 以上に倒して 0.3 秒保持すると動き続ける" % th


def table(L, header, rows):
    L.append("| %s |" % " | ".join(header))
    L.append("|%s|" % "|".join("---" for _ in header))
    for row in rows:
        L.append("| %s |" % " | ".join(row))
    L.append("")


def base_rows(over, merged=None):
    """単押しの表の行。over に入っているボタンは ★ を付け、修飾キーの行を差し替える。"""
    merged = merged if merged is not None else BASE
    rows = []
    for b in ORDER:
        star = "★" if b in over else ""
        if b == SHIFT_BUTTON and b not in over:
            rows.append([LABEL[b] + " 押しっぱなし", "`⇧`",
                         "本物の修飾キー。十字・クリック・Enter と組み合わせる", star])
        elif b == CMD_BUTTON:
            rows.append([LABEL[b] + " 単押し", "`%s`" % pretty(APP_SWITCH[0]), APP_SWITCH[1], ""])
            rows.append([LABEL[b] + " 押しっぱなし", "`⌘`",
                         "本物の修飾キー。十字・クリック・スクロールと組み合わせる", ""])
        elif b in merged:
            rows.append([LABEL[b], "`%s`" % pretty(merged[b][0]), merged[b][1], star])
    return rows


def build_cheatsheet():
    s = DEVICE_SETTINGS
    L = []
    L.append("# ゲームパッド版マニュアル（8BitDo SN30 Pro）")
    L.append("")
    L.append("**このファイルは `gen.py` の生成物です。**"
             "書き換えても次の `make gamepad` で消えます。"
             "割り当てを変えるときは `gen.py` の `BASE` / `MOD_DEFAULT` / `APPS` を、"
             "スティックの効きは `DEVICE_SETTINGS` / `XY_SPEED` / `WHEEL_SPEED` を直してください。")
    L.append("")
    L.append("8BitDo SN30 Pro を Bluetooth でつないでサブ入力デバイスにします。"
             "Caps Lock は使いません。キーボードのキーは一つも潰していないので、"
             "Vim モード / Emacs モードと同時に有効にできます。")
    L.append("")
    L.append("---")
    L.append("")

    L.append("## 使い始める")
    L.append("")
    L.append("1. コントローラーを **D-input** にする: `Start + B` を3秒長押し（LED 1 が点滅）。"
             "X-input だと Karabiner のデバイス一覧に出ません")
    L.append("2. Mac と Bluetooth でペアリングする")
    L.append("3. Karabiner-Elements → **Devices** → 8Bitdo SN30 Pro の **Modify events** を ON にする")
    L.append("4. `make install-gamepad`（`karabiner.json` に直接書き込みます。剥がすときは "
             "`make uninstall-gamepad`）")
    L.append("5. システム設定 → キーボード → **音声入力** を ON にする。ショートカットの設定は"
             "何でもよい（L2 は Apple キーボードのマイクキーと同じイベントを送るので、"
             "ショートカットに依存しない）")
    L.append("6. システム設定 → キーボード → **キーボードナビゲーション** を ON にする。"
             "OFF だと Tab がテキスト欄とリストの間しか動かず、ボタンにフォーカスが移りません")
    L.append("")
    L.append("---")
    L.append("")

    L.append("## ボタンの位置")
    L.append("")
    L.append("<!-- pdf: skip -->")
    L.append("")
    L.append("```")
    L.extend(FIGURE.rstrip("\n").split("\n"))
    L.append("```")
    L.append("")
    table(L, ["図の中", "ボタン"], [
        ["`L2` / `R2`", "上側の肩ボタン（アナログトリガー）"],
        ["`L` / `R`", "手前側の肩ボタン"],
        ["`UP` `DOWN` `LEFT` `RIGHT`", "十字キー"],
        ["`SELECT` / `START`", "Select（−） / Start（＋）"],
        ["`HEART`", "ハート（♡）"],
        ["`STAR`", "星（☆）。**Turbo の機能ボタンで、Karabiner からは見えません。**"
                   "ボタンを押しながら星を押すとそのボタンに連射が付くので、触らないでください"],
        ["`L3` / `R3`", "左 / 右スティックの押し込み"],
    ])
    L.append("---")
    L.append("")

    L.append("## 常に同じもの")
    L.append("")
    table(L, ["ボタン", "動作"], [
        ["L2", "音声入力の開始 / 終了（マイクキーを送出）。押すたびに切り替わる"],
        ["R2 押しっぱなし", "レイヤー2。他のボタンの意味が変わる（下の表）"],
        ["左スティック", "マウスカーソル。%s" % stick_note("xy")],
        ["右スティック", "スクロール。%s" % stick_note("wheels")],
    ])
    L.append("---")
    L.append("")

    L.append("## 単押し（机に向かうアプリ以外はどこでも同じ）")
    L.append("")
    L.append("キーボードとマウスの代わりになる操作です。エンジニア業務とブラウジングでは"
             "アプリによって変わりません。")
    L.append("")
    table(L, ["ボタン", "送るキー", "動作"], [r[:3] for r in base_rows({})])
    L.append("---")
    L.append("")

    L.append("## 修飾キーとの組み合わせ")
    L.append("")
    L.append("L（⇧）とハート（⌘）は押している間だけ立つ本物の修飾キーなので、"
             "個別のルールなしにこう合成されます。実キーボードの修飾キーも同じように効きます。")
    L.append("")
    table(L, ["操作", "動作"], [[a, b] for a, b in COMBOS])
    L.append("---")
    L.append("")

    L.append("## R2 を押しながら（どのアプリでも）")
    L.append("")
    L.append("アプリごとに変えてよいのはこの層だけです。「上書き」が「不可」の枠は"
             "どのアプリでも同じです。")
    L.append("")
    table(L, ["ボタン", "送るキー", "動作", "上書き"],
          [["R2 + " + LABEL[b], "`%s`" % pretty(MOD_DEFAULT[b][0]), MOD_DEFAULT[b][1],
            "不可" if b in MOD_LOCKED else "可"]
           for b in ORDER if b in MOD_DEFAULT])
    L.append("---")
    L.append("")

    for app in DESK_APPS:
        L.append("## %s（左手デバイス特化）" % app["name"])
        L.append("")
        L.append("対象: `%s`" % "`, `".join(
            p.strip("^$").replace("\\.", ".") for p in app["apps"]))
        L.append("")
        L.append("机に向かって使うアプリなので、単押しもこのアプリ用です。★ が固定ベースと"
                 "違うところ。ハート（⌘Tab）は変わりません。")
        L.append("")
        L.append("### 単押し")
        L.append("")
        merged, over = desk_base_layer(app)
        table(L, ["ボタン", "送るキー", "動作", "上書き"], base_rows(over, merged))
        L.append("### R2 を押しながら")
        L.append("")
        merged, over = mod_layer(app, DESK_LOCKED)
        table(L, ["ボタン", "送るキー", "動作", "上書き"],
              [["R2 + " + LABEL[b], "`%s`" % pretty(merged[b][0]), merged[b][1],
                "★" if b in over else ""]
               for b in ORDER if b in merged])
        L.append("---")
        L.append("")

    for app in APPS:
        merged, over = mod_layer(app)
        L.append("## %s（R2 を押しながら）" % app["name"])
        L.append("")
        L.append("対象: `%s`" % "`, `".join(
            p.strip("^$").replace("\\.", ".") for p in app["apps"]))
        L.append("")
        L.append("★ が既定と違うところです。単押しは変わりません。")
        L.append("")
        table(L, ["ボタン", "送るキー", "動作", "上書き"],
              [["R2 + " + LABEL[b], "`%s`" % pretty(merged[b][0]), merged[b][1],
                "★" if b in over else ""]
               for b in ORDER if b in merged])
        L.append("---")
        L.append("")

    L.append("## スティックの効き")
    L.append("")
    L.append("<!-- pdf: skip -->")
    L.append("")
    L.append("Karabiner はスティックを2通りで動かします。傾きが増えたぶんだけその場で動く"
             "**ナッジ**と、しきい値以上に倒して保持すると動き続ける**連続移動**です。"
             "連続移動はしきい値を超えてから **0.3 秒後**に始まります。この 0.3 秒は Karabiner の"
             "ソースにハードコードされていて、どの設定でも消せません。しきい値を超えた瞬間に"
             "ナッジは止まるので、しきい値をデッドゾーンと同じにすると倒した瞬間に 0.3 秒の"
             "空白が始まります（`DESIGN.md` §6）。")
    L.append("")
    L.append("タイマーは両スティックで1本です。片方が動き続けている間、もう片方は効きません。")
    L.append("")
    table(L, ["項目", "いま", "Karabiner 既定", "効果"], [
        ["カーソル 連続移動に入るしきい値",
         "%g" % s["game_pad_xy_stick_continued_movement_absolute_magnitude_threshold"],
         "1.00", "ここ以上に倒して 0.3 秒保持で連続移動。超えた瞬間にナッジは止まる"],
        ["カーソル 連続移動の更新間隔",
         "%d ms" % s["game_pad_xy_stick_continued_movement_interval_milliseconds"],
         "20 ms", "動き出してからの粒度。動き出すまでの待ちには効かない"],
        ["カーソル デッドゾーン", "%g" % s["game_pad_xy_stick_deadzone"],
         "0.10", "下げると軽い。ドリフトが出たら 0.12〜0.2 に上げる"],
        ["カーソル速度 flick / slow",
         "%s / %s" % (XY_SPEED["flick"], XY_SPEED["slow"]), "16 / 8",
         "flick = ナッジ（傾きの増分 × flick px）/ slow = 連続移動（傾き × slow px を更新ごと）"],
        ["スクロール 連続移動に入るしきい値",
         "%g" % s["game_pad_wheels_stick_continued_movement_absolute_magnitude_threshold"],
         "1.00", "デッドゾーンと同じ値なら、倒して 0.3 秒後から動き続ける"],
        ["スクロール 連続移動の更新間隔",
         "%d ms" % s["game_pad_wheels_stick_continued_movement_interval_milliseconds"],
         "10 ms", "動き出してからの粒度"],
        ["スクロール デッドゾーン", "%g" % s["game_pad_wheels_stick_deadzone"],
         "0.10", "下げると軽い。ドリフトが出たら上げる"],
        ["スクロール速度 flick / hold",
         "%s / %s" % (WHEEL_SPEED["flick"], WHEEL_SPEED["hold"]), "1 / 0.1",
         "flick = ナッジ / hold = 連続移動"],
    ])
    L.append("`mid` / `fast` は、連続移動中にもう片方のスティックも倒したときだけ効きます"
             "（傾きは 1.0 で頭打ちで、そこにもう片方の傾きが足されるため）。")
    L.append("")
    L.append("---")
    L.append("")

    L.append("## ボタンと HID イベントの対応")
    L.append("")
    L.append("Karabiner-EventViewer で実機から取得した値です。並びが連番ではないので、"
             "推測でルールを書くとずれます。")
    L.append("")
    table(L, ["ボタン", "イベント"],
          [[LABEL[b], "`%s: %s`" % BTN[b]] for b in BTN]
          + [["星", "何も出ない（Turbo の機能ボタン）"]])
    L.append("`button3` と `button6` はこのコントローラーには存在しません。"
             "十字キーだけ種別が `generic_desktop` です。`from` に書けることは公式ドキュメントに"
             "記載がありませんが、実機で確認しています。")
    L.append("")
    L.append("---")
    L.append("")

    L.append("## 注意")
    L.append("")
    L.append("- **エンジニア業務とブラウジングでは単押しを変えません。** アプリ固有の操作は"
             " `gen.py` の `APPS` に R2 の上書きとして足します（9 枠まで。取り消し / やり直し /"
             " 切り取り / Spotlight は上書き不可）。机に向かうアプリだけ `DESK_APPS` で単押しも"
             "上書きします。ハートはどこでも ⌘Tab です")
    L.append("- **長押しで繰り返すのは矢印・PgUp / PgDn・Backspace / Delete だけです。**"
             "他のボタンは押し続けても1回しか出ません。⇧Tab は L を先に押してから R です")
    L.append("- **作り直した割り当ては実機未検証です。** 送るキーはこの表のとおりなので、"
             "動きが違うときは `DESIGN.md` §9 と突き合わせてください")
    L.append("- **A ボタンは実マウスの左クリックと同じイベント**（`button1`）です。"
             "すべてのルールに `device_if` が必要で、付け忘れるとトラックパッドのクリックが"
             "死にます。JSON を手で書かず、必ず `gen.py` から生成してください")
    L.append("- EventViewer は Karabiner が変換したあとのイベントを表示します。"
             "ルールのあるボタンを押すと、ボタン番号ではなく送ったキーが出ます")
    L.append("")
    return "\n".join(L) + "\n"


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    rules = build_rules()

    with open(os.path.join(here, "gamepad-mode.json"), "w", encoding="utf-8") as fh:
        json.dump({"title": "8BitDo SN30 Pro（gen.py の生成物。直接編集しないこと）",
                   "rules": rules}, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    with open(os.path.join(here, "gamepad-device.json"), "w", encoding="utf-8") as fh:
        json.dump({"identifiers": dict(DEVICE), "settings": DEVICE_SETTINGS},
                  fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    with open(os.path.join(here, "CHEATSHEET.md"), "w", encoding="utf-8") as fh:
        fh.write(build_cheatsheet())

    total = sum(len(r["manipulators"]) for r in rules)
    print("gamepad-mode.json    : ルール %d 件 / manipulator %d 件" % (len(rules), total))
    print("gamepad-device.json  : スティック設定 %d 項目" % len(DEVICE_SETTINGS))
    print("CHEATSHEET.md        : マニュアル（PDF の元）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
