# CLAUDE.md

Claude Code 向けの作業ガイドです。作業を始める前に必ず読んでください。

## このリポジトリは何か

macOS 全体で Vim 風 / Emacs 風のキー操作を実現する **Karabiner-Elements の設定**です。
`vim/` と `emacs/` は**対等な2つの実装**で、どちらか一方を有効にして使い比べます。
どちらかが本命ということはありません。片方を変えたら、もう片方にも同じ配慮が必要か検討してください。

`gamepad/` は3つめのモードですが、性質が違います。**8BitDo SN30 Pro を
サブ入力デバイスにする設定**で、キーボードのキーも Caps Lock も使いません。
vim / emacs とは衝突しないので、片方を変えても `gamepad/` への配慮は不要です。
逆も同じです。固有の事情は `gamepad/DESIGN.md` にまとまっています。

## 最重要ルール

### 1. `*-mode.json` を直接編集しない

`vim/vim-mode.json` `emacs/emacs-mode.json` `gamepad/gamepad-mode.json` は**生成物**です。
必ず `gen.py` を編集して再生成してください。JSON を手で直すと次の生成で消えます。

**ゲームパッド版は `gamepad/CHEATSHEET.md`（マニュアル）と `gamepad/gamepad-device.json`
も生成物です。** 割り当てが 200 通り以上あり、早見表を手で維持するとずれるためです
（`gamepad/DESIGN.md` §7）。マニュアルの文面を変えるときも `gen.py` の
`build_cheatsheet()` を編集してください。

```bash
make            # 全モードを再生成 + 検査 + PDF
make vim        # vim だけ
make emacs      # emacs だけ
make gamepad    # ゲームパッドだけ
make check      # 検査だけ（依存ゼロ。venv も qpdf も要りません）
```

**PDF を作るときだけ外部依存があります。** 初回は次の2つが必要です。

```bash
brew install qpdf   # PDF のバイト再現性のための正規化に使う
make venv           # .venv に playwright（Chromium で組版）を用意する
```

`gen.py` `validate.py` `leakcheck.py` `explain.py` は素の `python3` だけで動きます。
`make check` を通すのに venv は不要です。

### 2. 変更後は必ず `make check` を通す

`shared/validate.py` が2種類の事故を検出します。

- **key_code / modifier の綴り間違い** — Karabiner は未知の key_code を黙って無視するので、
  タイポは「なぜかそのキーだけ効かない」という分かりにくい形で現れます
- **到達不能なルール** — Karabiner は manipulators を上から順に見て最初にマッチしたものを
  採用します。広いルールを前に置くと、後ろの狭いルールが永久に発火しません

エラーが出た状態で「たぶん動く」と報告しないでください。

### 3. 実機で動作確認できないことを正直に書く

このリポジトリを触る環境から macOS のキー入力は試せません。
**「動作を確認しました」と書かないでください。** 代わりに、

- `make check` が通ったこと
- どのキーストロークに翻訳されるか（`to` の中身）
- どのアプリで挙動が割れる可能性があるか

を書いて、実機確認はユーザーに委ねてください。

## 動かしてはいけない設計判断

過去に検討して意図的にそう決めたものです。変更を提案するのは構いませんが、
**理由を確認せずに「改善」しないでください。** 経緯は各ドキュメントにあります。

| 決定 | 理由の所在 |
|---|---|
| リーダーは Caps Lock。修飾キー（Hyper 等）にしない | `vim/ARCHITECTURE.md` §2 |
| Caps Lock 単押しは**何もしない**（`TAP_ACTION = None`） | `vim/ARCHITECTURE.md` §2 |
| `Caps + Space` は入力ソース切り替え（⌃Space）。潰さない | `docs/CONTROL-KEY.md` |
| **Vim 版で Shift は選択ではない。** Vim の記法どおりの大文字・記号 | `vim/ARCHITECTURE.md` §3 |
| Vim 版の選択はビジュアルモード（`v` / `V`）のみ | `vim/ARCHITECTURE.md` §5 |
| Emacs 版の Meta は Caps + Shift（`META_MOD = "shift"`） | `emacs/DESIGN.md` §2 |
| `dd` はクリップボードを使う（`p` で貼り戻せる） | `vim/LIMITATIONS.md` |
| **ビジュアルの `x` はクリップボードを汚さない削除**（Vim では `d` と同義） | `vim/ARCHITECTURE.md` §5 |
| 行選択（`dd` `yy` `V`）は ⌘← + ⇧↓ ではなく桁に依存しない5手 | `vim/ARCHITECTURE.md` §4 |
| `%` `H` `L` `f` `t` `.` などは実装しない | `vim/LIMITATIONS.md` |
| Figma などの除外アプリは設定しない | `COMPARISON.md` §5 |
| **ゲームパッドの全 manipulator に `device_if` を付ける** | `gamepad/DESIGN.md` §4 |
| ゲームパッド版は `karabiner.json` を直接書き換える（assets ではない） | `gamepad/DESIGN.md` §3 |
| L2 = 音声入力の開始 / 終了（マイクキー `consumer_key_code: dictation`）、R2 = レイヤー修飾 | `gamepad/DESIGN.md` §5 |
| **口述（prompt-refiner）は R2 + L2 の `dictate` が起点。整形ボタンは TextEdit 層にだけ置く。** どちらも `shell_command` で直接呼ぶ（⌥⌘V / ⌥⌘1 は送らない。Karabiner は自分の出力を再 manipulate しない）。⌘A ⌘C ⌘V は畳み込まない | `gamepad/DESIGN.md` §5 |
| **ゲームパッドの単押しは固定ベース。エンジニア業務のアプリは R2 層の 9 枠だけ上書き**（`MOD_LOCKED` は不可）。机に向かうアプリ（`DESK_APPS`）だけ単押しも特化 | `gamepad/DESIGN.md` §5 |
| ゲームパッドのハートはどのアプリでも ⌘Tab / ⌘。上書き不可（`DESK_LOCKED`） | `gamepad/DESIGN.md` §5 |
| ゲームパッドで長押しリピートするのは矢印と削除だけ（`repeat: false` が既定） | `gamepad/DESIGN.md` §5 |
| ゲームパッドの L / ハートは本物の修飾キー（全ルール `optional: ["any"]` は狙い） | `gamepad/DESIGN.md` §5 |
| **スティックの連続移動には 300 ms の空白がある。設定では消えない** | `gamepad/DESIGN.md` §6 |
| ゲームパッドの `CHEATSHEET.md` は生成物 | `gamepad/DESIGN.md` §7 |
| hjkl に転送するのは ⌥ と ⌘ だけ。⌃ は転送しない | `vim/ARCHITECTURE.md` §2b |
| **Vim 版は未定義の ⌃ / ⌥ を吸収する**（`from.any` + `to: []`） | `vim/ARCHITECTURE.md` §2c |
| **Emacs 版は ⌥ だけ吸収し、⌃ は素通りさせる** | `emacs/DESIGN.md` §7 |
| ⌘ を含む組み合わせは両版とも吸収しない | `vim/ARCHITECTURE.md` §2c |
| 修飾なし / ⇧ だけの未定義キーは保留（`Caps + i` は "i" を打つ） | `vim/ARCHITECTURE.md` §2c |

## よくある落とし穴

### `optional: ["any"]` は修飾キーを出力に漏らす

`from.modifiers.optional` に指定した修飾キーは、押されていれば**そのまま `to` に運ばれます。**
`p` → ⌘V のルールを `optional: ["any"]` で書くと、`⇧p` が **⌘⇧V**
（ペーストしてスタイルを合わせる）になります。過去に実際に混入したバグです。

Shift や Control を「受け付けるが出力しない」場合は `mandatory` を使ってください。
`mandatory` に指定した修飾キーは出力から取り除かれます。

**ゲームパッド版だけは例外です。** L / ハートを本物の ⇧ / ⌘ として合成させるために、
全ルールで `optional: ["any"]` を使っています（`gamepad/DESIGN.md` §5）。
`make leakcheck` の対象に入れていないのはそのためです。

追加・変更したら、この確認を走らせてください。

```bash
make leakcheck
```

### ⇧↓ は「桁」を覚えている

行単位の操作を「⌘← で行頭へ → ⇧↓ で次の行頭まで選択」と書きたくなりますが、
**⇧↓ は開始した桁を保ったまま下の行へ動きます。** VS Code や JetBrains 系の ⌘← は
最初の非空白文字で止まるので、インデントされたコードでは選択が次の行の同じ桁まで
伸び、次の行が短ければその行の末尾まで飲み込みます（`}` だけの行が消えます）。

行を選ぶときは `gen.py` の `SELECT_LINE`（⌘→ → ⌘← → ⌘← → ⌘⇧→ → ⇧→）を使ってください。
桁の計算がどこにも入りません。理由は `vim/ARCHITECTURE.md` §4 にあります。

### 「効かない」の原因は競合とは限らない

Caps Lock は**修飾キーを一切出力しません。** 変数を立てるだけです。
そのため明示的なルールのない組み合わせは**どれにもマッチしません。**
「競合して別の動作になる」ではなく「マッチしない」が典型的な失敗の形です。

マッチしなかったあとの行き先は、修飾キーによって2通りに分かれます。

| 押したもの | 行き先 |
|---|---|
| Vim 版で未定義の ⌃ / ⌥、Emacs 版で未定義の ⌥ | 吸収ルールが飲み込む → **何も起きない** |
| ⌘ を含むもの、修飾なし、⇧ だけ | **アプリに素通りする** |

素通りは無害ではありません。`⌃k` は macOS の「行末まで削除」、`⌥e` はアクセントの
デッドキー、素の `i` は文字 "i" の入力です。**素通りさせる判断をするときは、
そのキーが macOS で何をするかを必ず確認してください。**

判定は目視ではなく `explain.py` にやらせてください。
Karabiner と同じ順序でマッチングを再現します。

```bash
python3 shared/explain.py vim/vim-mode.json j option shift
python3 shared/explain.py vim/vim-mode.json j --var vim_visual=1
python3 shared/explain.py emacs/emacs-mode.json f
```

### 生成順を崩さない

`gen.py` はセクション番号どおりの順にマニピュレータを積んでいます。
狭い条件のものが先、広いものが後です。特に、

- ビジュアルモード / マークの版は通常版より**前**
- 2ストロークの2打目（消費側）は1打目（武装側）より**前**
- `ctrl` 系の移動はビジュアルモードの操作キーより**前**
- **吸収ルール（`from.any`）は必ず最後**。全キーを覆うので、後ろに置いたものは
  永久に発火しません。`make check` が `UNREACHABLE` で検出します

ループやテーブルに項目を足すときは、どのセクションに入るかを意識してください。

### クラウド実行の Cowork からこのリポジトリを git 操作しない

このリポジトリが外付けボリューム上にあるため、**クラウドで動く Cowork セッション**から
（デバイスブリッジ経由のマウントで）git を操作すると、`.git/index.lock` などの
ロックファイルが削除できずに残り、以降の git 操作が全部止まります。

Mac 上でネイティブに動く Claude Code なら問題ありません。ロックが残っていたら
消してください。

```bash
rm -f .git/*.lock .git/refs/heads/*.lock .git/objects/*.lock
```

### 2ストロークの変数は必ず両方の経路で 0 に戻す

`to_delayed_action` の `to_if_invoked`（時間切れ）と `to_if_canceled`（他キー押下）の
**両方**で変数をクリアします。片方を忘れると状態が立ちっぱなしになり、
「なぜか勝手に行が消える」設定ができあがります。

## ファイルの役割

```
karabiner-modal/
├── CLAUDE.md            この文書
├── README.md            入口。インストール手順と両モードの概要
├── COMPARISON.md        vim / emacs の比較と A/B テストの手順
├── Makefile             生成・検査・PDF・インストール
├── docs/
│   └── CONTROL-KEY.md   Caps Lock を Control にしていた人向けの移行メモ（両モード共通）
├── shared/
│   ├── validate.py              生成物の機械的検査（両モード共通）
│   ├── leakcheck.py             修飾キーが出力に漏れていないかの検出
│   ├── explain.py               「このキーは何になる?」を判定するデバッグ用
│   ├── make_cheatsheet_pdf.py   CHEATSHEET.md → PDF
│   └── probe_selection.js       ブラウザの選択挙動を実測する検証スクリプト
├── vim/
│   ├── gen.py           ← 編集するのはここ
│   ├── vim-mode.json    生成物
│   ├── CHEATSHEET.md    ← PDF の元。表だけが PDF に載る
│   ├── CHEATSHEET.pdf   生成物
│   ├── ARCHITECTURE.md  仕組みの解説。設計判断の記録
│   └── LIMITATIONS.md   実装しなかったものと macOS 側の制約
└── emacs/
    ├── gen.py           ← 編集するのはここ
    ├── emacs-mode.json  生成物
    ├── CHEATSHEET.md    ← PDF の元
    ├── CHEATSHEET.pdf   生成物
    └── DESIGN.md        Emacs 版固有の設計判断
```

## ドキュメントの扱い

**キー割り当てを変えたら `CHEATSHEET.md` も必ず更新してください。** PDF は
`CHEATSHEET.md` の**マークダウン表だけ**を拾って生成されるので、
散文を足しても PDF には出ません。表を直せば PDF に反映されます。

**1つの見出しの下に表を2つ置かないでください。** 散文が落ちるため、PDF では
`キー / VIM / 動作` という列見出しが2回続けて出るだけになります。
表を分けたいときは `###` で小見出しを付けてください。PDF 側は
「親セクション名 / 小見出し」という淡い見出しとして描画します
（列がまたいでも、どのセクションの続きか分かるようにするため）。

設計判断を変えたときは、理由を `ARCHITECTURE.md` / `DESIGN.md` / `LIMITATIONS.md` の
どれかに残してください。「なぜそうしなかったか」が失われると、
同じ議論を繰り返すことになります。

ドキュメントは**日本語**です。既存の文体（断定的で、トレードオフを隠さない）に合わせてください。
できないことは「できない」と書きます。

## 事実確認について

Karabiner の仕様は推測せず、公式ドキュメントを確認してください。

- [Manipulator definition](https://karabiner-elements.pqrs.org/docs/json/complex-modifications-manipulator-definition/)
- [from.modifiers](https://karabiner-elements.pqrs.org/docs/json/complex-modifications-manipulator-definition/from/modifiers/)
- [to_delayed_action](https://karabiner-elements.pqrs.org/docs/json/complex-modifications-manipulator-definition/to-delayed-action/)
- [Input event modification chaining](https://karabiner-elements.pqrs.org/docs/manual/misc/event-modification-chaining/)

ブラウザやアプリの挙動を推測で書かないでください。
`shared/probe_selection.js` のように、Playwright で実測できるものは実測してください。

## ユーザーについて

- 日本語で応答してください
- US（ANSI）配列を使っています
- Caps Lock は macOS 側の Control リマップをやめ、この設定のリーダー専用にしています
- Control は本物の Control キーで押しています
- Vim 版と Emacs 版を実際に使い比べている最中です。どちらかに肩入れしないでください
