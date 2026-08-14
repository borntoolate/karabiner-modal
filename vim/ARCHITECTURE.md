# 設定ファイルの仕組み

`vim-mode.json` が何をどうやって実現しているかの解説です。
自分で割り当てを増やしたり変えたりするときの下敷きにしてください。

---

## 0. ファイル構成

| ファイル | 役割 |
|---|---|
| `vim/vim-mode.json` | Karabiner に読ませる設定本体（**これだけあれば動く**） |
| `vim/gen.py` | `vim-mode.json` を生成する Python スクリプト |
| `vim/CHEATSHEET.md` | キー割り当て早見表（`CHEATSHEET.pdf` の元） |
| `vim/ARCHITECTURE.md` | この文書 |
| `vim/LIMITATIONS.md` | macOS 側の制約と、実装を見送ったもの |
| `shared/validate.py` | 綴り間違いと到達不能ルールの検出 |
| `shared/leakcheck.py` | 修飾キーが出力に漏れていないかの検出 |
| `../README.md` | 導入手順 |

`vim-mode.json` は 90 個超のルールが並んだ手書きにはつらいサイズなので、
`gen.py` から生成しています。**JSON を直接編集しないでください。**
次に `make` を走らせた時点で消えます。

この文書の内容は **Emacs 版（`../emacs/`）にもそのまま当てはまります。**
リーダーの作り方、`mandatory` と `optional` の違い、2ストロークの状態機械、
評価順の考え方は完全に共通です。

---

## 1. Karabiner の設定構造

Complex Modifications の設定ファイルは、こういう入れ子になっています。

```
{
  "title": "...",                 ← Karabiner の一覧に出る名前
  "rules": [
    {
      "description": "...",       ← Enable ボタンの隣に出る説明
      "manipulators": [ ... ]     ← 実際の変換規則の配列
    }
  ]
}
```

**manipulator** が変換規則1件です。最小構成はこれだけ。

```json
{
  "type": "basic",
  "from": { "key_code": "h" },
  "to":   [ { "key_code": "left_arrow" } ]
}
```

### 評価順が最重要

Karabiner は manipulators を**配列の先頭から順に見て、最初にマッチしたものを採用**します。
以降のルールは見ません。

この性質のせいで、**広く一致するルールを先に置くと、後ろの狭いルールが永久に発火しなくなります。**
`validate.py` はまさにこれを検出するために書いてあります。

この設定では、狭いもの → 広いもの、の順で並べてあります。

```
ビジュアルモード専用のルール（条件が多い＝狭い）
  ↓
2ストロークの2打目（変数が立っているときだけ＝狭い）
  ↓
Shift 付きのルール（mandatory 指定＝狭い）
  ↓
素のルール（広い）
```

---

## 2. 中核：リーダーキーを「修飾キー」ではなく「変数」で作る

### 何が問題だったか

素直にやるなら Caps Lock を Hyper（⌃⌥⇧⌘ の同時押し）に変換して、
`Hyper + h` を ← にする、という手があります。よくある手法です。

しかしこれだと **Shift も Control も Hyper の一部として消費されてしまいます。**
Vim の記法は `⇧4` = `$`、`⌃f` = 1画面下 のように修飾キーを前提にしているので、
それらが全部潰れると `$` も `C-f` も `V` も表現できなくなります。

### 採った方法

Caps Lock を修飾キーにするのをやめ、**押している間だけ立つフラグ（変数）**にしました。

```json
{
  "type": "basic",
  "from": { "key_code": "caps_lock", "modifiers": { "optional": ["any"] } },
  "to": [ { "set_variable": { "name": "vim_mode", "value": 1 } } ],
  "to_after_key_up": [
    { "set_variable": { "name": "vim_mode",   "value": 0 } },
    { "set_variable": { "name": "vim_visual", "value": 0 } },
    { "set_variable": { "name": "vim_g",      "value": 0 } },
    { "set_variable": { "name": "vim_d",      "value": 0 } },
    { "set_variable": { "name": "vim_y",      "value": 0 } }
  ]
}
```

1行ずつ読むとこうです。

- **`to`** — Caps Lock を押した瞬間に `vim_mode` を 1 にする。
  ここでキーを一切送っていないので、Caps Lock 本来の大文字ロックは発生しません。
- **`to_after_key_up`** — Caps Lock を離したときに全変数を 0 に戻す。
  これが後始末です。2ストロークの途中やビジュアルモード中に指を離しても、
  状態が残って次の操作を汚すことがありません。

**単押しで何も起きないのは、`to_if_alone` を書いていないからです。**
`to` が変数をセットするだけでキーを送らず、`to_after_key_up` がそれを戻すので、
Caps Lock をポンと叩いても外から観測できる出力はゼロになります。
Karabiner がキー自体は消費しているため、大文字ロックも発生しません。

単押しに何か割り当てたい場合は `to_if_alone` を足します。
`gen.py` の `TAP_ACTION` に key_code を書けば生成されます（`None` なら何もしない）。

```python
TAP_ACTION = "escape"     # 単押しで Esc
TAP_ACTION = None         # 単押しで何もしない（現在の設定）
```

そして他のすべてのルールに、この条件を付けます。

```json
"conditions": [ { "type": "variable_if", "name": "vim_mode", "value": 1 } ]
```

### この方式の利点

- **修飾キーを1つも消費しない。** Shift も Control も Option も、Vim の記法どおりに使えます。
- **macOS の標準ショートカットを1つも潰さない。** ⌘ も ⌃ も ⌥ も触っていないため。
- リーダーを別のキーに変えるのが、この1つの manipulator の差し替えだけで済む。

---

## 3. Shift は選択ではない

**この設定で Shift は「選択」を意味しません。** Vim の記法どおりの
大文字・記号を表します。

```
Caps + ⇧4    →  $  （行末へ）
Caps + ⇧g    →  G  （文書の末尾へ）
Caps + ⇧v    →  V  （行単位のビジュアルモード）
Caps + ⇧d    →  D  （行末まで削除）
```

選択は Vim と同じく**ビジュアルモード**で行います。これは単なる方針の問題ではなく、
設計を素直にします。以前は Shift を選択に使っていたため、

- `$` を `⇧4` で打てず、素の `4` に逃がす必要があった
- `⇧g` が `G`（末尾へ）と「選択しながら右」で衝突していた
- `J`（行連結）や `V`（行ビジュアル）を入れる場所がなかった

という歪みが出ていました。Shift を解放したことで全部解消しています。

### Karabiner の `from.modifiers`

| 指定 | 意味 | `to` への影響 |
|---|---|---|
| `mandatory` | この修飾キーが押されていないとマッチしない | **`to` からは取り除かれる** |
| `optional` | 押されていてもいなくてもマッチする | **押されていれば `to` に引き継がれる** |
| （省略） | 修飾キーが1つも押されていないときだけマッチ | — |

この設定では `mandatory` を使い分けて、`plain` / `shift` / `ctrl` の3系統を
別々の manipulator として生成しています。

```python
NONE  = {"optional": ["caps_lock"]}                          # 素押し
SHIFT = {"mandatory": ["shift"],   "optional": ["caps_lock"]}
CTRL  = {"mandatory": ["control"], "optional": ["caps_lock"]}
```

`mandatory` に指定した修飾キーは**出力から取り除かれる**のがポイントです。
`Caps + ⇧4` の Shift は消費され、出力は ⌘→ だけになります。
これをやらないと ⌘⇧→ になって、意図せず選択になってしまいます。

### `optional: ["any"]` を意図的に避けている理由

`optional: ["any"]` にすると、押された修飾キーが**そのまま出力に運ばれます。**
これは便利な反面、事故のもとです。たとえば `p`（貼り付け）を

```json
{ "from": { "key_code": "p", "modifiers": { "optional": ["any"] } },
  "to":   [ { "key_code": "v", "modifiers": ["left_command"] } ] }
```

と書くと、`Caps + ⇧p`（Vim の `P`）が **⌘⇧V** になります。
macOS ではこれは「ペーストしてスタイルを合わせる」で、別のコマンドです。

そのため貼り付けやビジュアルモードの操作キーは、`SHIFT` と `NONE` の
2本に分けて明示的に書いてあります。`gen.py` を書き換えたあとは

```bash
make vim        # 再生成 + 検査 + PDF（リポジトリのルートで）
```

に加えて、`optional: ["any"]` のルールが余計な修飾キーを漏らしていないかを
確認すると安全です。

### `^` `$` `(` は Shift 付きと素の数字キーの両方を受ける

`⇧4` = `$` が本来の記法ですが、行末移動は頻繁に使うので
素の `4` でも同じ動作にしてあります。Shift は `mandatory` で消費されるため、
どちらの経路でも出力は同じ ⌘→ です。

`MOVES` テーブルで `"both"` と指定すると、この2本が自動生成されます。

---

## 4. 2ストローク（`gg` / `dd` / `yy`）の状態機械

`dd` のように同じキーを2回打つコマンドは、**1打目で状態を作り、2打目でそれを消費**します。

### 1打目：武装する

```json
{
  "from": { "key_code": "d", "modifiers": { "optional": ["caps_lock"] } },
  "to":   [ { "set_variable": { "name": "vim_d", "value": 1 } } ],
  "conditions": [ vim_mode == 1, vim_d != 1 ],
  "to_delayed_action": {
    "to_if_invoked":  [ { "set_variable": { "name": "vim_d", "value": 0 } } ],
    "to_if_canceled": [ { "set_variable": { "name": "vim_d", "value": 0 } } ]
  },
  "parameters": { "basic.to_delayed_action_delay_milliseconds": 800 }
}
```

`to_delayed_action` が時限装置です。

- **`to_if_invoked`** — 押してから 800 ミリ秒、**他のキーが押されなかった**場合に発火。
  → 時間切れなので変数を 0 に戻す。
- **`to_if_canceled`** — 800 ミリ秒経つ前に**別のキーが押された**場合に発火。
  → 別のコマンドに移ったので変数を 0 に戻す。

どちらに転んでも 0 に戻るので、**変数が立ちっぱなしになる経路が存在しません。**
ここを雑にやると「なぜか勝手に行が消える」設定ができあがります。

### 2打目：消費する

```json
{
  "from": { "key_code": "d", "modifiers": { "optional": ["caps_lock"] } },
  "to": [
    { "key_code": "left_arrow", "modifiers": ["left_command"] },   ← 行頭へ
    { "key_code": "down_arrow", "modifiers": ["left_shift"] },     ← 次の行頭まで選択
    { "key_code": "x",          "modifiers": ["left_command"] },   ← 切り取り
    { "set_variable": { "name": "vim_d", "value": 0 } }
  ],
  "conditions": [ vim_mode == 1, vim_d == 1 ]
}
```

`to` は配列なので、**複数のキーを順番に送れます。** `dd` はこれを使って
「行頭へ → 次の行頭まで選択 → ⌘X」という3手で1行切り取りを実現しています。
改行まで含めて選択されるので、Vim の `dd` と同じく行そのものが消えます。

`yy` も同じ手順で ⌘C にし、最後に ← を送って選択を解除しています。

### 並べる順序

**必ず「2打目（消費側）」を「1打目（武装側）」より前**に置きます。
逆にすると、`vim_d != 1` の条件が付いた武装側が先にマッチして、
2打目が永久に発火しません。`validate.py` はこの種の事故を検出します。

### `d` は単独では何もしない

1打目は変数をセットするだけでキーを送りません。Vim の `d` が
オペレーターであって単独では削除しないのと同じ挙動です。

---

## 5. ビジュアルモード（`v` / `V`）

**選択はすべてここに集約されています。** Shift は選択に使いません。

### 実装

`vim_visual` 変数を `v` でトグルし、移動系のルールを**2セット**用意します。

```json
// ビジュアル版（条件が多い＝狭いので先に置く）
{ "from": { "key_code": "h", "modifiers": { "optional": ["caps_lock"] } },
  "to":   [ { "key_code": "left_arrow", "modifiers": ["left_shift"] } ],
  "conditions": [ vim_mode == 1, vim_visual == 1 ] }

// 通常版（後ろに置く）
{ "from": { "key_code": "h", "modifiers": { "optional": ["caps_lock"] } },
  "to":   [ { "key_code": "left_arrow" } ],
  "conditions": [ vim_mode == 1 ] }
```

`vim_visual` が立っているときだけ Shift が出力に足されます。
`MOVES` テーブルの全エントリについて、`gen.py` がこの2本を自動生成します。
`ctrl` 系（`C-f` など）にもビジュアル版があるので、
ビジュアルモード中の `C-f` は「1画面分を選択しながらスクロール」になります。

### `V`（行単位）

`⇧v` は「現在行を選択した状態でビジュアルモードに入る」動作です。

```json
{ "from": { "key_code": "v", "modifiers": { "mandatory": ["shift"] } },
  "to": [
    { "key_code": "left_arrow", "modifiers": ["left_command"] },   // 行頭へ
    { "key_code": "down_arrow", "modifiers": ["left_shift"] },     // 次の行頭まで選択
    { "set_variable": { "name": "vim_visual", "value": 1 } }
  ] }
```

このあと `j` を押すと `⇧↓` が足されて、さらに1行ずつ伸びていきます。

### 操作キー

ビジュアルモード中は `y` `d` `x` `c` `p` が専用の動作（コピー／切り取り／置換）に
差し替わり、実行後は自動でモードを抜けます。
これらは Shift 付きと素押しを別々の manipulator にしてあります
（`optional: ["any"]` だと `⇧p` が ⌘⇧V になってしまうため。前述）。

---

## 6. 変数の一覧

| 変数 | 意味 | 立つタイミング | 落ちるタイミング |
|---|---|---|---|
| `vim_mode` | Vim モード中 | Caps Lock 押下 | Caps Lock 解放 |
| `vim_visual` | ビジュアルモード中 | `v` / `⇧v` | `v` / `Esc` / 操作実行 / Caps Lock 解放 |
| `vim_g` | `g` プレフィックス武装中 | `g` | 2打目 / 800ms 経過 / 他キー / Caps Lock 解放 |
| `vim_d` | `d` プレフィックス武装中 | `d` | 同上 |
| `vim_y` | `y` プレフィックス武装中 | `y` | 同上 |
| `vim_colon` | `:` プレフィックス武装中 | `⇧;` | 同上 |

すべて Caps Lock を離した時点でリセットされるので、
「変な状態のまま固まった」ときは **Caps Lock をいったん離せば必ず復帰します。**

---

## 7. カスタマイズ手順

### 移動キーを足す・変える

`gen.py` の `MOVES` テーブルを編集します。
`(押すキー, 種別, 送るキー, 修飾キー, 説明)` の順です。

```python
MOVES = [
    ("h", "plain", "left_arrow",  [],               "h: left"),
    ("4", "both",  "right_arrow", ["left_command"], "$: end of line"),
    ("f", "ctrl",  "page_down",   [],               "C-f: page down"),
    #     ↑ 種別   ↑ 送るキー     ↑ 一緒に押す修飾キー
]
```

種別は4つです。

| 種別 | 押し方 | 生成される manipulator |
|---|---|---|
| `plain` | `Caps + キー` | 1本 |
| `shift` | `Caps + ⇧ + キー` | 1本 |
| `both` | どちらでも | 2本 |
| `ctrl` | `Caps + ⌃ + キー` | 1本（評価順で先頭側に置かれる） |

ここに追加すれば、**通常版とビジュアルモード版の両方が自動で生成されます。**
Shift や Control は `mandatory` で消費されるので、出力に漏れません。

`ctrl` 系だけは、ビジュアルモードの操作キー（`d` `x` など）に
食われないよう意図的に前方へ配置しています。生成順は `gen.py` の
セクション2とセクション6に分かれているので、そこを崩さないでください。

### 2連打の待ち時間を変える

`gen.py` 冒頭の `PREFIX_DELAY`（ミリ秒）。既定は 800 です。
取りこぼすなら伸ばす、暴発するなら縮めます。

### リーダーキーを Caps Lock 以外にする

`gen.py` の caps_lock の manipulator で `"key_code": "caps_lock"` を
`"right_command"` などに変えます。ただし修飾キーをリーダーにすると、
**そのキーを使った macOS 標準ショートカットが右手側で効かなくなります**
（右⌘なら ⌘H / ⌘W / ⌘L など）。Caps Lock を選んだのはこれを避けるためです。

修飾キーをリーダーにする場合は `TAP_ACTION` も合わせて調整してください。
右⌘をリーダーにするなら `TAP_ACTION = "right_command"` にしておくと、
単押しで普通の ⌘ として振る舞います。

### 単押しの動作を変える

`gen.py` 冒頭の `TAP_ACTION` を書き換えて再生成します。

```python
TAP_ACTION = None         # 何も起きない（現在の設定）
TAP_ACTION = "escape"     # Esc
TAP_ACTION = "japanese_eisuu"  # 英数キー
TAP_ACTION = "japanese_kana"   # かなキー
```

`None` のときは `to_if_alone` そのものが出力されません。

### 再生成と検査

```bash
make vim     # 再生成 + 検査 + PDF（リポジトリのルートで）
make check   # 検査だけ
```

`validate.py` が見ているのは主に2点です。

1. **key_code / modifier の綴り間違い。**
   Karabiner は知らない key_code を黙って無視するので、
   タイポがあると「なぜかそのキーだけ効かない」という分かりにくい形で現れます。
2. **到達不能なルール。**
   前述の評価順の事故です。「広いルールが先にあるせいで、後ろの狭いルールが
   絶対に発火しない」組み合わせを総当たりで検出します。

Karabiner 側で設定を再読み込みするには、Complex Modifications の
Enable を一度外して入れ直すか、Karabiner-Elements を再起動してください。

---

## 8. Vim と macOS の対応表

内部でどのキーストロークに翻訳しているかの一覧です。

| Vim | macOS | Cocoa のコマンド |
|---|---|---|
| `h` `j` `k` `l` | ← ↓ ↑ → | `moveLeft:` ほか |
| `w` `W` `e` `E` | ⌥→ | `moveWordForward:` |
| `b` `B` | ⌥← | `moveWordBackward:` |
| `0` `^` | ⌘← | `moveToLeftEndOfLine:` |
| `$` | ⌘→ | `moveToRightEndOfLine:` |
| `(` `{` | ⌥↑ | `moveToBeginningOfParagraph:` |
| `)` `}` | ⌥↓ | `moveToEndOfParagraph:` |
| `gg` | ⌘↑ | `moveToBeginningOfDocument:` |
| `G` | ⌘↓ | `moveToEndOfDocument:` |
| `C-f` `C-d` | Page Down | `scrollPageDown:` |
| `C-b` `C-u` | Page Up | `scrollPageUp:` |
| ビジュアルモード中 | 同じキー + ⇧ | `move...AndModifySelection:` |
| `V` | ⌘← → ⇧↓ | — |
| `x` | Delete | — |
| `X` | Backspace | — |
| `D` | ⌘⇧→ → Backspace | — |
| `dd` | ⌘← → ⇧↓ → ⌘X | — |
| `yy` `Y` | ⌘← → ⇧↓ → ⌘C → ← | — |
| `J` | ⌘→ → Delete | — |
| `o` | ⌘→ → Enter | — |
| `O` | ⌘← → Enter → ↑ | — |
| `p` `P` | ⌘V | — |
| `u` / `C-r` `U` | ⌘Z / ⌘⇧Z | — |
| `/` `?` | ⌘F | — |
| `n` / `N` | ⌘G / ⌘⇧G | — |
| `:w` `:q` `:x` | ⌘S / ⌘W / ⌘S→⌘W | — |

macOS のテキスト入力はほぼすべて Cocoa の共通処理を通るため、
これらのキーストロークは Safari でも Mail でも Xcode でも Slack でも同じように効きます。
逆に、Cocoa を使っていないアプリ（一部のゲーム、Java 製アプリ、
リモートデスクトップ内など）では期待通りに動かないことがあります。

---

## 参考リンク

- [complex_modifications manipulator definition](https://karabiner-elements.pqrs.org/docs/json/complex-modifications-manipulator-definition/)
- [from.modifiers](https://karabiner-elements.pqrs.org/docs/json/complex-modifications-manipulator-definition/from/modifiers/)
- [to_delayed_action](https://karabiner-elements.pqrs.org/docs/json/complex-modifications-manipulator-definition/to-delayed-action/)
- [conditions](https://karabiner-elements.pqrs.org/docs/json/complex-modifications-manipulator-definition/conditions/)
