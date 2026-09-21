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
#   1. ナッジ   … 傾きが「増えた」ぶん × flick × 傾き^expo だけ、HID レポートが届くたびに
#                 動く。待ちはない。戻す動きと、傾きを保ったままの回転では動かない。
#                 傾き^expo を掛けるので、浅い傾きほど 1 レポートあたりの移動が小さい
#                 （中央付近で細かく、端で大きく。DESIGN.md §6）
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
  m := delta_magnitude * {flick} * pow(absolute_magnitude, {expo});
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

# カーソル速度。Karabiner 既定は 16 / 8 / 12 / 24（expo はこちらで足したもの。既定相当は 0）。
#   flick … ナッジの係数。傾きの増分 × flick × 傾き^expo ピクセル
#   expo  … ナッジの曲がり。0 で増分に比例（どこでも同じ粒度）、1 で傾きにも比例
#           （デッドゾーンの縁では細かく、端では大きい）。小さい対象に合わせるための
#           微調整は浅い傾きで、遠くへは深く倒すか連続移動で。
#           いっぱいまで倒したときの合計は flick × (threshold^(expo+1) − deadzone^(expo+1)) / (expo+1)
#           （150 / 0 のときの約 120 px に揃うよう、1 では 300 にしてある）
#   slow  … 連続移動の係数。傾き × slow ピクセルが interval ごとに出る
#   mid / fast … 傾きは 1.0 で頭打ちなので単独では発火しない。連続移動中に
#                もう片方のスティックも倒すと、その傾きが足されて効く
XY_SPEED = {"flick": 300, "expo": 1, "slow": 13, "mid": 24, "fast": 40}

# スクロール速度。Karabiner 既定は 1 / 0.1。
WHEEL_SPEED = {"flick": 1.0, "hold": 0.15}

DEVICE_SETTINGS = {
    # --- 左スティック（カーソル）: ナッジ + いっぱいに倒して保持で連続移動 ---
    # 0.12: 押し込み（クリック）で傾くぶんを飲み込む。expo があるので、この帯を捨てても
    # 失うナッジは 2 px ほど。まだ跳ねるなら 0.2 まで上げる（DESIGN.md §6）
    "game_pad_xy_stick_deadzone": 0.12,
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
#   L・L2・ハートは本物の修飾キー。押している間 ⇧ / ⌃ / ⌘ が立つので、十字・クリック・
#   Enter・スクロールと勝手に合成される（L + 十字 = 選択、L2 + 十字 ↑ = Mission Control、
#   ハート + L3 = ⌘クリック）。そのために全ルールの from.modifiers を optional: ["any"] にしてある。
#   押されている修飾キーはそのまま to に運ばれる。vim 版では事故だが、ここでは狙い。
#
#   値は ("キー指定", "早見表に出す説明") の組。
#     "escape"                    単キー
#     "cmd+shift+open_bracket"    修飾キー付き（cmd / shift / opt / ctrl / fn）
#     "escape escape"             スペース区切りで連続入力
#     "click:button1"             マウスクリックを送る
#     "opt+click:button1"         修飾キー付きのクリック（⌥クリックなど）
#     "hold:spacebar"             押している間だけ押しっぱなしにする
#     "once:cmd+opt+left_arrow"   矢印でも長押しで繰り返さない（切り替えに使うとき）
#     "shell:$HOME/bin/refine code"  シェルコマンドを実行する（/bin/sh -c）。
#                                 空白を含むので、他のトークンと並べられない
#     "ctrl+f2"                   F1〜F12 は fn の有無で 2 本の manipulator に展開される
#                                 （manipulators()。素の F キーはメディアキーに化けるため）
# ===========================================================================
# L2 = 押している間は ⌃、単押しで音声入力の開始 / 終了。
# ⌃ は L（⇧）・ハート（⌘）と同じ lazy な本物の修飾キー。十字と合成すると macOS の
# Mission Control（⌃↑）/ アプリケーション Exposé（⌃↓）/ スペースの移動（⌃← →）に
# なるので、そのためのルールはない（DESIGN.md §5）。
# 単押しは Apple のキーボードのマイクキー（F5）と同じ HID イベント（consumer usage
# "dictation"）を送る。macOS の音声入力はこれで起動・終了するので、システム設定の
# ショートカット（⌘ を2回など）には依存しない。トグルなので押している間ではなく、
# 押すたびに開始 / 終了。to_if_alone なので送るのは離した瞬間で、他のボタンを押さずに
# 1 秒（to_if_alone の既定）以内に離したときだけ。ハートの ⌘Tab と同じ形。
VOICE_BUTTON = "L2"
VOICE_KEY = {"consumer_key_code": "dictation"}

# R2 押しっぱなし = レイヤー2 修飾
MOD_BUTTON = "R2"
MOD_VAR = "sn30_mod"

# 押している間だけ立つ本物の修飾キー。lazy なので単押しでは何も出ない
# （L2 = ⌃ もこの仲間。上の VOICE_BUTTON）。
SHIFT_BUTTON = "L"
CMD_BUTTON = "HEART"
# ハート / L を単押ししたとき（他のボタンを押さずに離したとき）。
# L の単押しは左クリック。左スティックの押込はスティックが傾いてポインタが跳ねるので、
# 狙って押すクリックはスティックに触らない人差し指で（DESIGN.md §5）。押込のクリックも
# 残す（ドラッグは押しながら動かすしかない）。
APP_SWITCH = ("cmd+tab", "直前のアプリへ。押したまま R で順送り")
SHIFT_TAP = ("click:button1", "左クリック（スティックに触らずに。狙うクリックはこちら）")


# 口述は prompt-refiner（~/works/prompt-refiner）の2コマンドで回す。
#   dictate        新しい下書き ~/prompt-log/draft-<日時>.md を作って TextEdit で開く（口述の場）
#   refine <mode>  クリップボードを読んで claude -p で整形し、クリップボードへ書き戻す。
#                  数秒かかり、終わると通知が出る
#
# prompt-refiner は作者の非公開ツールで、このリポジトリには入っていない。ここが当てにするのは
# 上の 2 行の契約（パス・引数・クリップボード経由の入出力）だけで、生成と検査には要らない。
# 無い環境では呼ぶ 6 ボタンだけが無音で失敗する（sh のエラーが console_user_server.log に
# 残る）。呼び先を差し替える場所は shell() / refine() / DICTATE の 3 つ（README「口述の 6 ボタン」）。
#
# prompt-refiner 自身のホットキー ⌥⌘V / ⌥⌘1〜5 を送っても発火しない。Karabiner は
# 自分が出したイベントを再 manipulate しないので、ボタンからはコマンドを直接呼ぶ。
# $HOME は Karabiner が shell_command に渡す数少ない環境変数のひとつ。claude の PATH と
# ロケールは refine 自身が補うので、ここで export するものはない。環境変数を継がないので
# dictate が開くのは常に既定の TextEdit（PROMPT_REFINER_EDITOR は届かない）。
# 標準出力は捨てる。捨てないと Karabiner が console_user_server.log に先頭 256 文字を
# 記録し、整形結果（案件名を含みうる）がログに残る。エラーは stderr なので残る。
def shell(cmd):
    return "shell:%s >/dev/null" % cmd


def refine(mode):
    return shell("$HOME/bin/refine " + mode)


# R2 + L2。口述の手順の起点で、どのアプリでも同じ。
DICTATE = (shell("$HOME/bin/dictate"), "口述の下書きを開く（新しい下書きを作って TextEdit へ）")


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
    "L3":     ("click:button1", "左クリック（押している間はドラッグ）。押し込みで傾いて跳ねるので、狙うクリックは L"),
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
    ("ハート + A", "⌘Enter（Claude Desktop の権限プロンプトでは「今回は許可」。拒否は B の Esc）"),
    ("ハート + 十字 ←→", "行頭 / 行末（⌘矢印）"),
    ("ハート + 十字 ↑↓", "文頭 / 文末"),
    ("ハート + Y", "行頭まで削除（⌘Backspace）"),
    ("ハート + 左スティック押込", "⌘クリック"),
    ("ハート + 右スティック", "⌘スクロール（対応アプリでズーム）"),
    ("ハート + L + 十字", "行末 / 行頭まで選択"),
    ("L2 + 十字 ↑", "Mission Control（⌃↑）。ウィンドウを左スティックで指して押込で選ぶ、B で抜ける"),
    ("L2 + 十字 ↓", "アプリケーション Exposé（⌃↓。前面アプリのウィンドウ一覧）"),
    ("L2 + 十字 ← →", "左 / 右のスペースへ（⌃← →）"),
    ("L2 + R", "次のタブ（⌃Tab。R2 + R と同じ）。L も握れば前のタブ"),
    ("L2 + 左スティック押込", "⌃クリック（右クリックと同じコンテキストメニュー）"),
]

# R2 を押しながら。アプリ別に上書きできるのはこの層だけ。
#
# ⌘N（新規）と ⌘S（保存）はアプリ別の 8 枠の外、右 / 左スティック押込に置いてある。TextEdit /
# VS Code の新規ファイルと保存、Claude Desktop の新規セッション、ブラウザの新規ウィンドウ、
# どのアプリでも ⌘N は「新しく作る」、⌘S は「保存する」で意味が揃うので、アプリ別の枠を使わず
# グローバルにした。押し込みでポインタが跳ねてもどちらも困らない。アプリ別にすると TextEdit の
# R2 層（口述の整形で埋まっている）に置き場がなく、アプリを足すたびに配線が要る（DESIGN.md §5）。
#
# R2 + B はメニューバーへのフォーカス（macOS の ⌃F2）。コントローラーに枠のない操作は
# 全部ここから届く（十字で移動、A で開く / 決定、B で抜ける）ので、どのアプリでも同じ位置に
# 要る。上書き不可。閉じる（⌘W）はこの枠を譲り、メニューバー経由か × のクリックで代える。
MOD_DEFAULT = {
    "A":      ("cmd+a", "すべて選択"),
    "B":      ("ctrl+f2", "メニューバーにフォーカス（十字で移動、A で開く / 決定、B で抜ける）"),
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
    "L3":     ("cmd+s", "保存"),
    "R3":     ("cmd+n", "新規（新しい書類 / ウィンドウ / セッション）"),
}
# アプリ別に上書きできない枠。編集の芯と、枠のない操作への逃げ道（メニューバー）は
# どのアプリでも同じ場所にある。
MOD_LOCKED = {"B", "X", "Y", "SELECT", "HEART"}

# ===========================================================================
# アプリ別（R2 を押しながらの上書きだけ）
#
#   apps: frontmost_application_if の bundle_identifiers（正規表現）。
#   mod:  MOD_DEFAULT のうち MOD_LOCKED 以外を差し替える。書かないボタンは既定のまま。
#   上にあるアプリが優先。
# ===========================================================================
# 整形ボタンは TextEdit にだけある。R2 + L2 の dictate が必ず TextEdit を開くので、
# 口述の手順はここで完結し、全アプリの R2 層に整形の枠を固定しなくて済む（DESIGN.md §5）。
# 並びは prompt-refiner のホットキー ⌥⌘1〜5 と同じ順。他のアプリで口述した文は
# キーボードの ⌥⌘1〜5 で整形する。
# LIMITATION: モード名 5 つと並びは prompt-refiner の事実を写した固定値。あちらでモードを
# 増やしても名前を変えてもここは追従しない。同期は手作業で、prompt-refiner 側のモード追加手順が
# ここを指す逆向きの参照だけが頼り（DESIGN.md §5）。
DICTATION_APP = {
    "name": "TextEdit（口述の下書き）",
    "apps": [r"^com\.apple\.TextEdit$"],
    "mod": {
        "UP":     (refine("code"), "整形: Claude Code 向けの依頼文に（⌥⌘1）"),
        "DOWN":   (refine("research"), "整形: 調査・壁打ち向けに（⌥⌘2）"),
        "LEFT":   (refine("doc"), "整形: 文章作成の依頼に（⌥⌘3）"),
        "RIGHT":  (refine("ticket"), "整形: 起票文に（⌥⌘4）"),
        "START":  (refine("message"), "清書: Slack などに送る本文に（⌥⌘5）"),
    },
}

# Claude Desktop（Code タブで複数セッションを並列に回す前提）。キーは Desktop 2.2553.1 の
# アプリメニューと、同梱 Web 層のショートカット一覧（Help → Keyboard Shortcuts ⌘/）から
# 取った実物で、推測ではない（DESIGN.md §5）。単押しの B（Esc）は応答の停止、
# ハート + A（⌘Enter）は権限プロンプトの「今回は許可」に当たる。
# 「サーフェス」は Chat / Cowork / Code の切り替えで、macOS ではサイドバーの有無や
# 分割ビューの有無に関わらず効く。分割ビューで「既存のセッションを開く」に相当する
# キーは ⌥クリックしかない（Web 層の一覧に "alt+click" として載っている）ので、
# 左スティック押込に置く。既定の ⌘S を潰すが、Desktop には保存するものがない。
CLAUDE_DESKTOP_APP = {
    "name": "Claude Desktop",
    "apps": [r"^com\.anthropic\.claudefordesktop$"],
    "mod": {
        "A":      ("cmd+n", "新規セッション（Chat タブでは新規チャット）"),
        "UP":     ("cmd+b", "サイドバーの表示 / 非表示"),
        "DOWN":   ("ctrl+cmd+backslash", "右に新しいセッションを開く（分割ビュー）"),
        "LEFT":   ("once:cmd+opt+left_arrow", "前のサーフェス（Code → Cowork → Chat）"),
        "RIGHT":  ("once:cmd+opt+right_arrow", "次のサーフェス（Chat → Cowork → Code）"),
        "L":      ("cmd+shift+open_bracket", "前のセッション（サイドバーの1つ上）"),
        "R":      ("cmd+shift+close_bracket", "次のセッション（サイドバーの1つ下）"),
        "START":  ("cmd+k", "セッションを検索 / 開始（コマンドパレット）"),
        "L3":     ("opt+click:button1", "⌥クリック（サイドバーのセッションを分割ビューで開く）"),
    },
    "notes": [
        "既存のセッションを開くのは、サイドバーの項目を左スティックで指して左スティック押込"
        "（クリック）か、R2 + L / R で1つずつ送る。**分割ビューで開くときは R2 を握ったまま"
        "押し込む**（⌥クリック）",
        "新規セッションは R2 + A でも R2 + 右スティック押込（どのアプリでも ⌘N）でも同じ",
        "権限プロンプトは ハート + A（⌘Enter）で今回は許可、B（Esc）で拒否。"
        "Claude の応答を止めるのも B",
        "サーフェスの切り替え（⌘⌥←→）と分割ビュー（⌃⌘\\）は Code タブ以外でも押せるが、"
        "分割ビューは Code タブにしかない",
        "セッション番号で飛ぶ ⌘1〜9、Changes / ターミナル / ブラウザのペイン切り替え"
        "（⌘⇧D / ⌘J / ⌘⇧B）はキーボードのまま。ペインはヘッダーのアイコンをクリックしても開く",
    ],
}

APPS = [
    DICTATION_APP,
    CLAUDE_DESKTOP_APP,

    {
        "name": "ターミナル / Claude Code",
        "apps": [
            r"^com\.apple\.Terminal$",
            r"^com\.lambdalisue\.Arto$",
            r"^com\.microsoft\.VSCode$",
            r"^com\.googlecode\.iterm2$",
            r"^com\.mitchellh\.ghostty$",
            r"^dev\.warp\.Warp-Stable$",
            r"^com\.github\.wez\.wezterm$",
        ],
        # ⌃C は R2 + B に置いていた（B = Esc の「強い版」）が、R2 + B はメニューバーで
        # 固定になったので Start へ。画面のクリア（⌘K）は見た目だけの操作なので外した。
        "mod": {
            "A":      ("opt+return_or_enter", "改行（送信しない）"),
            "START":  ("ctrl+c", "強制中断"),
        },
        "notes": [
            "VS Code の新規ファイル（⌘N）と保存（⌘S）は R2 + 右 / 左スティック押込（どのアプリでも同じ）",
        ],
    },

    # ⌘L はどのブラウザでもアドレスバー（検索欄）の選択。⌥⌘B は Chrome 系では
    # ブックマーク マネージャー（新しいタブに一覧が開く）、Safari では「ブックマークを編集」
    # （同じくタブに一覧）。どちらも一覧の項目をスティックで指して開ける。
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
            "UP":     ("cmd+l", "アドレスバー（検索欄）を選択"),
            "DOWN":   ("cmd+opt+b", "ブックマークの一覧を開く（Chrome: ブックマーク マネージャー / Safari: ブックマークを編集）"),
            "LEFT":   ("cmd+open_bracket", "戻る"),
            "RIGHT":  ("cmd+close_bracket", "進む"),
        },
        "notes": [
            "ブックマークの一覧では、項目を左スティックで指してクリックで選び、**押込を2回（ダブルクリック）で開く**。"
            "A（Enter）は名前の変更になる（Chrome / Safari とも）。Chrome は ハート + A（⌘Enter）で新しいタブに開く。"
            "X / Y は選んだブックマークの削除なので押さない（消したら R2 + Y で取り消す）",
            "ブックマーク バーを常に出しておくなら ⌘⇧B（Chrome / Safari とも）。キーボードから一度切り替えれば、"
            "以後はバーの項目を1クリックで開ける",
            "新規ウィンドウは R2 + 右スティック押込（⌘N）",
        ],
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
    "open_bracket": "[", "close_bracket": "]", "backslash": "\\",
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
# ドラッグになるので対象外。矢印でも「切り替え」に使うもの（Claude Desktop の ⌘⌥←→ は
# サーフェスの切り替え）は "once:" を付けて1回だけにする。繰り返すと表示が飛ぶ。
REPEAT_KEYS = {"up_arrow", "down_arrow", "left_arrow", "right_arrow",
               "page_up", "page_down", "delete_or_backspace", "delete_forward"}


def parse_modifiers(parts, token):
    mods = []
    for raw in parts:
        alias = raw.strip().lower()
        if alias not in MODIFIER_ALIASES:
            raise ValueError("未知の修飾キー: %s (in %r)" % (raw, token))
        mods.append(MODIFIER_ALIASES[alias])
    return mods


def parse_to_token(token):
    if "click:" in token:
        # "click:button1" / "opt+click:button1"。to の modifiers は pointing_button にも
        # 効く（16.3.0 の to_event_definition.hpp。修飾キーを押してからボタンを送る）
        prefix, _, button = token.partition("click:")
        event = {"pointing_button": button}
        mods = parse_modifiers(prefix.rstrip("+").split("+"), token) if prefix else []
        if mods:
            event["modifiers"] = mods
        return event
    hold = token.startswith("hold:")
    once = token.startswith("once:")
    if hold or once:
        token = token.split(":", 1)[1]
    parts = token.split("+")
    key, mods = parts[-1], parse_modifiers(parts[:-1], token)
    event = {"key_code": key}
    if mods:
        event["modifiers"] = mods
    if (key not in REPEAT_KEYS or once) and not hold:
        event["repeat"] = False
    return event


def parse_to(spec):
    # shell: は空白を含むコマンドをそのまま渡すので、spec 全体で1イベント。
    # キーの連続入力とは混ぜない（shell_command は即座に走り、キーイベントは
    # あとから届くので、順序を当てにできない。DESIGN.md §5）
    if spec.startswith("shell:"):
        return [{"shell_command": spec[len("shell:"):].strip()}]
    return [parse_to_token(t) for t in spec.split() if t]


def pretty(spec):
    """'cmd+shift+open_bracket' -> '⌘⇧['  /  'escape escape' -> 'esc esc'
    'shell:$HOME/bin/refine code >/dev/null' -> 'refine code'"""
    if spec.startswith("shell:"):
        # パスとリダイレクトは省く。PDF の「送るキー」列は折り返さないので、
        # フルパスを入れると隣の列を押し出す。実際に走る文字列は gamepad-mode.json の to
        words = [w for w in spec[len("shell:"):].split()
                 if w[0] not in "<>" and not w.startswith("2>")]
        words[0] = os.path.basename(words[0])
        return " ".join(words)
    out = []
    for token in spec.split():
        if "click:" in token:
            prefix, _, button = token.partition("click:")
            syms = "".join(MOD_SYMBOL.get(p.lower(), p) for p in prefix.rstrip("+").split("+") if p)
            out.append(syms + ("マウス左" if button == "button1" else "マウス右"))
            continue
        if token.startswith(("hold:", "once:")):
            token = token.split(":", 1)[1]
        parts = token.split("+")
        key = parts[-1]
        syms = "".join(MOD_SYMBOL.get(p.lower(), p) for p in parts[:-1])
        default = key.upper() if len(key) == 1 or key in FKEYS else key
        out.append(syms + KEY_SYMBOL.get(key, default))
    return " ".join(out)


def manipulator(button, spec, conditions, description):
    return {
        "type": "basic",
        "description": description,
        "from": from_event(button),
        "to": parse_to(spec),
        "conditions": conditions,
    }


# F1〜F12 を送る枠は 2 本に分ける。Karabiner は複雑な変更の**後**に Function Keys の段
# （F1〜F12 ⇄ メディアキー）を掛けるので、素の f2 を送ると、macOS の「F1、F2 などのキーを
# 標準のファンクションキーとして使用」が OFF の環境では画面の明るさに化ける。公式の作法
# （"Details on changing to function keys"）どおり、その設定が OFF なら fn 付き、ON なら
# fn なしを送る。設定は変数 system.use_fkeys_as_standard_function_keys（15.2.3 以降）で
# 読める。R2 + B の ⌃F2（メニューバー）がこれに当たる。
FKEYS = {"f%d" % i for i in range(1, 13)}
FKEYS_STANDARD = "system.use_fkeys_as_standard_function_keys"


def manipulators(button, spec, conditions, description):
    """1 枠ぶんの manipulator のリスト。F1〜F12 を送る枠だけ fn の有無で 2 本になる。"""
    plain = manipulator(button, spec, conditions, description)
    if not any(ev.get("key_code") in FKEYS for ev in plain["to"]):
        return [plain]
    with_fn = dict(plain)
    with_fn["to"] = [dict(ev, modifiers=["fn"] + ev.get("modifiers", []))
                     if ev.get("key_code") in FKEYS else ev for ev in plain["to"]]
    with_fn["description"] = description + "（fn 付き。F キーがメディアキーの設定のとき）"
    with_fn["conditions"] = conditions + [
        {"type": "variable_unless", "name": FKEYS_STANDARD, "value": True}]
    plain["conditions"] = conditions + [
        {"type": "variable_if", "name": FKEYS_STANDARD, "value": True}]
    return [with_fn, plain]


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
            "description": "%s 音声入力（L2 でマイクキー、R2 + L2 で下書きを開く）" % RULE_PREFIX,
            "manipulators": manipulators(
                VOICE_BUTTON, DICTATE[0], [dev, mod_on],
                "R2 + %s -> %s (%s)" % (LABEL[VOICE_BUTTON], pretty(DICTATE[0]), DICTATE[1])
            ) + [
                {
                    "type": "basic",
                    "description": "L2 -> ⌃（押している間）/ 単押しでマイクキー（音声入力の開始 / 終了）",
                    "from": from_event(VOICE_BUTTON),
                    "to": [{"key_code": "left_control", "lazy": True}],
                    "to_if_alone": [dict(VOICE_KEY, repeat=False)],
                    "conditions": [dev, mod_off],
                },
            ],
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
            m for b in ORDER if b in app.get("mod", {})
            for m in manipulators(b, app["mod"][b][0], [dev, mod_on, appc],
                                  "R2 + %s -> %s (%s)" % (LABEL[b], pretty(app["mod"][b][0]),
                                                          app["mod"][b][1]))]
        manips += [
            m for b in ORDER if b in app.get("base", {})
            for m in manipulators(b, app["base"][b][0], [dev, mod_off, appc],
                                  "%s -> %s (%s)" % (LABEL[b], pretty(app["base"][b][0]),
                                                     app["base"][b][1]))]
        rules.append({"description": "%s %s（左手デバイス特化）" % (RULE_PREFIX, app["name"]),
                      "manipulators": manips})

    for app in APPS:
        mod_layer(app)  # 上書きできない枠に触っていないか
        conds = [dev, mod_on, app_condition(app["apps"])]
        manips = [
            m for b in ORDER if b in app["mod"]
            for m in manipulators(b, app["mod"][b][0], conds,
                                  "R2 + %s -> %s (%s)" % (LABEL[b], pretty(app["mod"][b][0]),
                                                          app["mod"][b][1]))]
        rules.append({"description": "%s %s（R2 を押しながら）" % (RULE_PREFIX, app["name"]),
                      "manipulators": manips})

    rules.append({
        "description": "%s R2 を押しながら（どのアプリでも）" % RULE_PREFIX,
        "manipulators": [
            m for b in ORDER if b in MOD_DEFAULT
            for m in manipulators(b, MOD_DEFAULT[b][0], [dev, mod_on],
                                  "R2 + %s -> %s (%s)" % (LABEL[b], pretty(MOD_DEFAULT[b][0]),
                                                          MOD_DEFAULT[b][1]))],
    })

    # 単押し。修飾キー2つは専用の形。
    base = [
        {
            "type": "basic",
            "description": "%s -> ⇧（押している間）/ 単押しで %s (%s)"
                           % (LABEL[SHIFT_BUTTON], pretty(SHIFT_TAP[0]), SHIFT_TAP[1]),
            "from": from_event(SHIFT_BUTTON),
            "to": [{"key_code": "left_shift", "lazy": True}],
            "to_if_alone": parse_to(SHIFT_TAP[0]),
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
        m for b in ORDER if b in BASE
        for m in manipulators(b, BASE[b][0], [dev, mod_off],
                              "%s -> %s (%s)" % (LABEL[b], pretty(BASE[b][0]), BASE[b][1]))]
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
    note = "倒した量だけ動き、%g 以上に倒して 0.3 秒保持すると動き続ける" % th
    if stick == "xy" and XY_SPEED["expo"] > 0:
        note += "。浅く倒すほど細かく動く（小さい対象には浅く）"
    return note


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
            rows.append([LABEL[b] + " 単押し", "`%s`" % pretty(SHIFT_TAP[0]), SHIFT_TAP[1], ""])
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
        ["L2 単押し", "音声入力の開始 / 終了（マイクキーを送出）。押すたびに切り替わる。"
                    "送るのは離した瞬間で、他のボタンを押さずに 1 秒以内に離したときだけ"],
        ["L2 押しっぱなし", "⌃（本物の修飾キー）。十字と合わせて Mission Control / アプリケーション"
                          " Exposé / スペースの移動（下の「修飾キーとの組み合わせ」）"],
        ["R2 + L2", "%s。`%s` を実行。整形はその TextEdit で（下の「口述から整形まで」）"
         % (DICTATE[1], pretty(DICTATE[0]))],
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
    L.append("L（⇧）・L2（⌃）・ハート（⌘）は押している間だけ立つ本物の修飾キーなので、"
             "個別のルールなしにこう合成されます。実キーボードの修飾キーも同じように効きます。"
             "Mission Control / アプリケーション Exposé / スペースの移動は、システム設定 → "
             "キーボード → キーボードショートカット → Mission Control の ⌃↑ / ⌃↓ / ⌃← → が"
             " ON であること（既定は ON）。")
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
    L.append("- **R2 + B のメニューバーは、コントローラーに枠のない操作への逃げ道です。**"
             " フォーカスが移ったら十字 ← → でメニューを選び、↓ か A で開き、↑ ↓ で項目を選んで"
             " A で実行、B で抜けます（macOS の ⌃F2。システム設定 → キーボード → キーボード"
             "ショートカット → キーボード の「メニューバーにフォーカスを移動」が ON であること。"
             "既定は ON）。「F1、F2 などのキーを標準のファンクションキーとして使用」が OFF の"
             "環境では fn⌃F2 を送ります（Karabiner の作法。どちらでもメニューバーに届く）。"
             "閉じる（⌘W）はこの枠を譲ったので、メニューバーの File → Close か × のクリックで")
    L.append("- R2 + %s の ⌘S と R2 + %s の ⌘N は「保存」「新規」の意味がアプリで揃うので"
             "グローバルです（TextEdit / VS Code はファイルの保存と新規、Claude Desktop は"
             "新しいセッション、ブラウザやターミナルは新しいウィンドウ）。押し込みでポインタが"
             "跳ねてもどちらも困りません。保存するものがないアプリでは ⌘S はダイアログを"
             "出すか何もしないので、出たら B（Esc）で閉じます。Claude Desktop だけは左スティック"
             "押込を ⌥クリックに上書きしています"
             % (LABEL["L3"], LABEL["R3"]))
    L.append("")
    L.append("---")
    L.append("")

    L.append("## 口述から整形まで（prompt-refiner）")
    L.append("")
    L.append("喋った文を prompt-refiner の `refine` で構造化プロンプトに整形する手順です。"
             "prompt-refiner は喋った文を `claude -p` で用途別の構造化プロンプトにする作者の"
             " CLI で、このリポジトリには入っていません（呼び出しの契約は README）。"
             "起点は R2 + L2 の `dictate` で、新しい下書き（`~/prompt-log/draft-<日時>.md`）を"
             "作って TextEdit で開きます。**整形ボタンはその TextEdit にだけあります**（R2 + 十字と"
             " Start。並びはキーボードの ⌥⌘1〜5 と同じ）。`refine` はクリップボードを読んで、"
             "整形した結果をクリップボードへ書き戻すので、選択 → コピー → 整形 → 貼り付けの"
             "形になります。整形には数秒かかり、終わると通知センターに「整形完了」が出ます。")
    L.append("")
    L.append("ボタンが実行するのは `%s` と `%s` などで、Karabiner が `/bin/sh -c` で走らせます。"
             "コマンドが無ければこの 6 ボタンだけが無音で失敗し、他のボタンは影響を受けません。"
             % (parse_to(DICTATE[0])[0]["shell_command"],
                parse_to(DICTATION_APP["mod"]["UP"][0])[0]["shell_command"]))
    L.append("")
    steps = [
        ["1. 下書きを開く", "R2 + L2", "`%s`（TextEdit が前面に来る）" % pretty(DICTATE[0])],
        ["2. 口述を始める", "L2", "マイクキー（音声入力の開始）"],
        ["3. 喋る", "—", "—"],
        ["4. 口述を終える", "L2", "マイクキー（音声入力の終了）"],
        ["5. すべて選択", "R2 + A", "`%s`" % pretty(MOD_DEFAULT["A"][0])],
        ["6. コピー", LABEL["SELECT"], "`%s`" % pretty(BASE["SELECT"][0])],
    ]
    steps += [["7%s. %s" % (chr(ord("a") + i), DICTATION_APP["mod"][b][1]), "R2 + " + LABEL[b],
               "`%s`" % pretty(DICTATION_APP["mod"][b][0])]
              for i, b in enumerate(b for b in ORDER if b in DICTATION_APP["mod"])]
    steps += [
        ["8. 「整形完了」の通知を待つ", "—", "—"],
        ["9. 貼り付け先のアプリへ", LABEL["HEART"], "`%s`" % pretty(APP_SWITCH[0])],
        ["10. 貼り付け", LABEL["START"], "`%s`" % pretty(BASE["START"][0])],
    ]
    table(L, ["手順", "ボタン", "送るもの"], steps)
    L.append("- **他のアプリで口述した文はキーボードの ⌥⌘1〜5 で整形してください。** "
             "整形ボタンは TextEdit でしか効きません。Claude Desktop、ターミナル / Claude Code、"
             "ブラウザの各グループは R2 + A も ⌘A ではないので、コントローラー"
             "だけでは完結しません")
    L.append("- **整形中にもう一度押さないでください。** Karabiner はシェルコマンドを同時に"
             "1つしか走らせず、次を押すと走っている整形が強制終了されます"
             "（R2 + L2 の `dictate` も、prompt-refiner のホットキー ⌥⌘V / ⌥⌘1〜5 も"
             "同じ枠です）。終了した整形はクリップボードに何も書きません")
    L.append("- `dictate` は毎回新しい下書きを作ります。前の口述に言い足すボタンはありません"
             "（キーボードから `dictate --keep`）")
    L.append("- ⌘A → ⌘C を整形ボタンに畳み込んでいないのは、シェルコマンドが即座に走るのに"
             "対してキーイベントはあとから届き、⌘C より先にクリップボードを読んでしまうためです"
             "（`DESIGN.md` §5）")
    L.append("")
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
        for note in app.get("notes", []):
            L.append("- " + note)
        if app.get("notes"):
            L.append("")
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
         "0.10", "押し込み（クリック）で傾くぶんを飲み込む。まだ跳ねるなら 0.2 まで上げる。"
                 "ドリフトが出ても上げる"],
        ["カーソル速度 flick / expo / slow",
         "%s / %s / %s" % (XY_SPEED["flick"], XY_SPEED["expo"], XY_SPEED["slow"]), "16 / 0 / 8",
         "flick = ナッジ（傾きの増分 × flick × 傾き^expo px）/ expo = 浅い傾きほど細かく"
         "（0 でどこでも同じ粒度）/ slow = 連続移動（傾き × slow px を更新ごと）"],
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
             " `gen.py` の `APPS` に R2 の上書きとして足します（10 枠。メニューバー / 取り消し /"
             " やり直し / 切り取り / Spotlight の 5 枠は上書き不可）。"
             "机に向かうアプリだけ `DESK_APPS` で単押しも上書きします。ハートはどこでも ⌘Tab です")
    L.append("- **長押しで繰り返すのは矢印・PgUp / PgDn・Backspace / Delete だけです。**"
             "他のボタンは押し続けても1回しか出ません。⇧Tab は L を先に押してから R です")
    L.append("- **シェルコマンド（R2 + L2 の `dictate`、TextEdit の整形）は1つずつ。**"
             " Karabiner 全体で同時に1つだけで、次を押すと走っているほうが強制終了されます。"
             "整形結果の先頭が Karabiner のログに残らないよう、標準出力は捨てています"
             "（エラーは `~/.local/share/karabiner/log/console_user_server.log` に出ます）")
    L.append("- **実機で確認済みなのは固定ベース・Claude Desktop・ブラウザの層と、R2 + B の"
             "メニューバー・R2 + 左スティック押込の ⌘S・L2 の ⌃・L 単押しのクリック・ナッジの"
             " expo です。** それ以外（机に向かうアプリ、ターミナルの R2 層の ⌃C 以外、口述の手順）は"
             "送るキーがこの表のとおりというだけなので、動きが違うときは `DESIGN.md` §9 と"
             "突き合わせてください")
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
