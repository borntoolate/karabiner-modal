# karabiner-modal

macOS 全体で **Vim 風 / Emacs 風のキー操作**を実現する Karabiner-Elements の設定です。

`vim/` と `emacs/` は**対等な2つの実装**です。どちらも Caps Lock を押している間だけ
モードに入る同じ仕組みで、違うのはキー割り当てだけ。使い比べて体に合うほうを選ぶための
構成になっています。

`gamepad/` は毛色が違います。**8BitDo SN30 Pro をサブ入力デバイスにする設定**で、
キーボードのキーを一つも使いません。Caps Lock も掴まないので、Vim / Emacs モードと
**同時に有効にできます**。

```
Caps Lock 押しっぱなし  →  モードに入る（離すと自動で抜ける）
Caps Lock 単押し        →  何も起きない
Caps + Space            →  英語 / 日本語の切り替え（⌃Space）
```

macOS の標準ショートカット（⌘・⌃・⌥・fn の組み合わせ）は一つも潰していません。
US（ANSI）配列前提です。

---

## 2つのモード

| | `vim/` | `emacs/` |
|---|---|---|
| 移動 | `h` `j` `k` `l` | `C-f` `C-b` `C-n` `C-p` |
| 行頭 / 行末 | `⇧6`（`^`）/ `⇧4`（`$`） | `C-a` / `C-e` |
| 単語移動 | `w` / `b` | `M-f` / `M-b`（Caps+⇧F） |
| 選択 | ビジュアルモード `v` / `V` | マーク `M-SPC` |
| Shift の役割 | Vim の記法どおりの大文字・記号 | Meta |
| 2ストローク | `dd` `yy` `gg` `:w` | `C-x C-s` など |
| 設定ファイル | `vim/vim-mode.json` | `emacs/emacs-mode.json` |
| 早見表 | `vim/CHEATSHEET.pdf` | `emacs/CHEATSHEET.pdf` |

どちらを選ぶかの判断材料は **[COMPARISON.md](COMPARISON.md)** にまとめてあります。
同じ作業を両方でやった場合の打鍵の比較と、A/B テストの手順があります。

---

## ゲームパッド版（`gamepad/`）

8BitDo SN30 Pro を **D-input モード**（`Start + B` を3秒長押し）で Bluetooth 接続して使います。

```
左 / 右スティック                 →  マウスカーソル / スクロール
十字・A・B・X・Y・Select・Start  →  矢印・Enter・Esc・Delete・Backspace・コピー・貼り付け（全アプリ固定）
L / ハート 押しっぱなし           →  ⇧ / ⌘（本物の修飾キー。十字やクリックと合成される）
R / ハート 単押し                 →  Tab / ⌘Tab
L2                                →  音声入力の開始 / 終了（Apple キーボードのマイクキーと同じイベント）
R2 押しっぱなし                   →  レイヤー2（ここだけ前面アプリで出し分け）
R2 + L2                           →  口述の下書きを開く（prompt-refiner の dictate。TextEdit では R2 + 十字 / Start が整形）
```

音声入力と組み合わせて、楽な姿勢でのエンジニア業務とブラウジングをキーボードとマウスなしで
回す設計です。単押しはどのアプリでも同じで、R2 レイヤーだけをターミナル / Claude Code と
ブラウザで上書きしています。机に向かって使う Figma / Photoshop / Illustrator / After Effects /
Logic だけは左手デバイスとして特化させ、単押しも別の割り当てです。どこでもハートは ⌘Tab です。

```bash
make gamepad          # 再生成 + 検査 + 早見表 PDF
make install-gamepad  # karabiner.json に書き込む（GUI 操作は不要）
```

**Karabiner は DirectInput のパッドしか扱えません。** X-input モードだとデバイス一覧に
すら出ません。接続後、Karabiner-Elements → Devices で **Modify events** を ON にしてください。

使い方と割り当ての一覧は **[gamepad/CHEATSHEET.md](gamepad/CHEATSHEET.md)**（マニュアル。
ボタンの位置図つき）にあります。**[gamepad/CHEATSHEET.pdf](gamepad/CHEATSHEET.pdf)** は
その表だけを抜いた印刷用です。設計判断は **[gamepad/DESIGN.md](gamepad/DESIGN.md)** にあります。

---

## インストール

```bash
make install          # vim と emacs の JSON を Karabiner の設定ディレクトリに置く
make install-vim      # vim だけ
make install-emacs    # emacs だけ
make install-gamepad  # ゲームパッド版（karabiner.json に直接書き込む。下記参照）
```

置いたあと、Karabiner-Elements → **Complex Modifications** → **Add rule** で
使いたいほうを **Enable** します。

### ゲームパッド版だけインストール方法が違います

`make install-gamepad` は assets へのコピーではなく、`karabiner.json` を直接
書き換えます。**スティックの効き（速度・デッドゾーン）が complex_modifications では
表現できず、デバイス設定として書くしかない**ためです。理由は
[gamepad/DESIGN.md](gamepad/DESIGN.md) §3 にあります。

`[SN30]` で始まるルールだけを入れ替えるので、Vim / Emacs モードには触りません。
書き込み前に `automatic_backups/` へバックアップを取ります。剥がすときは
`make uninstall-gamepad` です。

### vim と emacs を同時に有効にしないでください

**どちらも Caps Lock を掴むので、両方 Enable にすると先に並んでいるほうだけが動きます。**
壊れはしませんが、片方が沈黙して原因が分かりにくくなります。

切り替えるときは、使わないほうを **Remove** してから、使うほうを **Add rule** してください。
JSON ファイルは残るので、付け外しは何度でもできます。

ゲームパッド版はキーボードのキーを一つも掴まないので、どちらと組み合わせても衝突しません。

### Caps Lock を Control にリマップしていた場合

Karabiner は物理キーボードを占有するため、macOS 側の「Caps Lock → Control」リマップは
効かなくなります。移行に必要な作業は **[docs/CONTROL-KEY.md](docs/CONTROL-KEY.md)** に
まとめてあります（両モード共通）。

### Caps Lock の反応が鈍い場合

システム設定 → キーボード → キーボードショートカット… → **修飾キー** を開き、
**Caps Lock キー** を **「アクションなし」** に変更してください。

---

## 開発

設定ファイルは**生成物**です。`gen.py` を編集して作り直します。

```bash
make            # 全モードを再生成 + 検査 + PDF
make vim        # vim だけ
make emacs      # emacs だけ
make gamepad    # ゲームパッドだけ
make check      # 検査だけ（綴り・評価順・修飾キーの漏れ）
make pdf        # チートシートの PDF だけ
make help       # ターゲット一覧
```

`vim-mode.json` / `emacs-mode.json` / `gamepad-mode.json` を手で編集しないでください。
次の生成で消えます。**ゲームパッド版は `CHEATSHEET.md`（マニュアル）も生成物です**
（割り当てが 200 通り以上あり、手で維持するとずれるため。理由は `gamepad/DESIGN.md` §7）。

Claude Code で作業する場合は **[CLAUDE.md](CLAUDE.md)** を先に読んでください。
守るべき設計判断と、過去に踏んだ落とし穴がまとまっています。

---

## ディレクトリ

```
.
├── CLAUDE.md            Claude Code 向けの作業ガイド
├── COMPARISON.md        vim / emacs の比較と A/B テストの手順
├── Makefile             生成・検査・PDF・インストール
├── docs/
│   └── CONTROL-KEY.md   Caps Lock → Control からの移行メモ（両モード共通）
├── shared/
│   ├── validate.py              綴り間違いと到達不能ルールの検出
│   ├── leakcheck.py             修飾キーが出力に漏れていないかの検出
│   ├── make_cheatsheet_pdf.py   CHEATSHEET.md → 印刷用 PDF
│   └── probe_selection.js       ブラウザの選択挙動の実測
├── vim/
│   ├── gen.py  vim-mode.json
│   ├── CHEATSHEET.md  CHEATSHEET.pdf
│   ├── ARCHITECTURE.md   仕組みの解説（両モード共通の土台もここ）
│   └── LIMITATIONS.md    実装しなかったものと macOS 側の制約
├── emacs/
│   ├── gen.py  emacs-mode.json
│   ├── CHEATSHEET.md  CHEATSHEET.pdf
│   └── DESIGN.md         Emacs 版固有の設計判断
└── gamepad/
    ├── gen.py                    ← 編集するのはここ（割り当て・スティック・マニュアルの文面）
    ├── gamepad-mode.json         生成物（ルール）
    ├── gamepad-device.json       生成物（スティックの効き）
    ├── CHEATSHEET.md             生成物（マニュアル。位置図つき）  CHEATSHEET.pdf（印刷用）
    ├── apply.py                  karabiner.json への流し込み
    └── DESIGN.md                 ゲームパッド版固有の設計判断
```

Karabiner の設定ファイルそのものの仕組み（変数リーダー、`mandatory` と `optional` の違い、
2ストロークの状態機械、評価順）は `vim/ARCHITECTURE.md` に書いてあります。
`emacs/` も同じ土台なので、そちらを読む前にまず目を通してください。

---

## ライセンス

[MIT License](LICENSE) です。設定ファイルもスクリプトもドキュメントも、
自由にコピー・改変して使ってください。著作権表示を残すことだけが条件です。

Karabiner-Elements 本体と公式のカスタム設定集は Unlicense（パブリックドメイン）ですが、
このリポジトリはそれらの派生物ではないため、別のライセンスを選んでいます。

---

## 参考

- [Karabiner-Elements](https://karabiner-elements.pqrs.org/)
- [Manipulator definition](https://karabiner-elements.pqrs.org/docs/json/complex-modifications-manipulator-definition/)
- [Input event modification chaining](https://karabiner-elements.pqrs.org/docs/manual/misc/event-modification-chaining/)
