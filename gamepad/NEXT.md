# ゲームパッド版の次の作業（Claude Code 引き継ぎメモ）

Mac 上のローカル Claude Code で続きをやるための申し送りです。
`karabiner-modal` のルートで `claude` を起動してください。

このファイルは作業が終わったら消してかまいません。

---

## いまの状態

`gamepad/` は動いています。`make check` は3モードとも通り、`make gamepad` は PDF まで通ります。

- **固定ベースに作り直した直後**（2026-09-19）。エンジニア業務・ブラウジングでは単押しは
  固定、R2 レイヤーだけアプリ別に上書き（ターミナル / Claude Code、ブラウザ）。
  机に向かうアプリ（Figma / Photoshop / Illustrator / After Effects / Logic）は
  `DESK_APPS` で左手デバイス特化（単押しも上書き。割り当ては未検証の初期案）。
  L / ハートは本物の修飾キー。ハートはどこでも ⌘Tab。L2 は macOS 音声入力のマイクキー
  （トグル）。設計は `DESIGN.md` §5
- ルール 11 本 / manipulator 157 件
- 長押しで繰り返すのは矢印と削除だけ（`repeat: false` が既定。`hold:` で押しっぱなし）
- スティックは左右で挙動を変えてある（下記「やること 1」）
- マニュアルは `CHEATSHEET.md`（生成物。PDF の元）

`karabiner.json` には反映済みです（2026-09-19 21:49、`make install-gamepad`）。直前の状態は
`~/.config/karabiner/automatic_backups/karabiner_before_sn30_20260919_214911.json` にあります。

`gamepad/` 一式と `CLAUDE.md` `Makefile` `README.md` `shared/validate.py`
`shared/make_cheatsheet_pdf.py` の変更は **未コミット**です。

---

## やること 1 — 固定ベースを実機で確かめる

設計は Karabiner のソースの読解に基づいていて、**実機では一度も触っていません。**
`DESIGN.md` §9 の「未確認」を上から順に。特に:

| 確認 | 期待 | 外れたら |
|---|---|---|
| L2 | macOS の音声入力が始まる。もう一度で終わる | `consumer_key_code: dictation` が仮想キーボード経由で効いていない。代替は `to` を `right_command` 2回（システム設定のショートカットに合わせる） |
| R を押してから L | 何も起きない（Tab は1回だけ）。⇧Tab は L → R の順 | 仕様。`DESIGN.md` §5 |
| L を握って十字 | 選択が伸びる | `L -> ⇧` の `lazy` を外す（`build_rules()`） |
| L を握って左スティック押込 | ⇧クリック | 同上 |
| ハート単押し | 直前のアプリへ | `to_if_alone` のタイムアウト（既定 1 秒）内に離しているか |
| ハートを押したまま R を連打 | スイッチャーが出たまま順送り | ⌘ が lazy で送られていない。`lazy` を外す |
| ハートを押したまま右スティック | ズーム（対応アプリ） | lazy がスティックの動きで送られていない |
| R2 + L / R | 前 / 次のタブ | アプリが ⌃Tab に対応していない。R2 上書きで ⌘⇧[ ] にする |
| システム設定 → キーボード → キーボードナビゲーション | ON | OFF だと Tab がボタンに止まらない |

`lazy` を外す場合、L / ハートの単押しで ⇧ / ⌘ の空打ちが出ます。macOS 標準では無害です。

### 使いながら足すもの

- **R2 の上書きは 9 枠まで**（`MOD_DEFAULT` のうち `MOD_LOCKED` 以外）。アプリを足すときは
  `APPS` に `mod` だけ書く。単押しは変えない
- ブラウザの DevTools（⌘⌥I）、VS Code のコマンドパレット（⌘⇧P）は外してある。
  要るなら R2 の空き枠（↑ ↓ または B）へ
- Figma / Photoshop / Illustrator / After Effects / Logic は `DESK_APPS`（単押しも上書き）。
  机で使ってみて直す。ハート以外は全部上書きできる。書かないボタンは固定ベースに落ちる

---

## やること 2 — 左右のスティックを触り比べて、しきい値の置き方を決める

**「倒してから動き出すまでの待ちを 0 にする」は、設定では達成できません。**
Karabiner のソース（16.3.0 `game_pad_stick_converter.hpp`）を読んで確認しました。
詳細は `DESIGN.md` §6 にあります。要点だけ書きます。

- 連続移動のタイマーは **開始間隔が 300 ms にハードコード**。しきい値を超えてから
  300 ms は何も動かない。しかもその間ナッジ（倒した量だけその場で動く方式）も止まる
- これまでの調整（threshold 1.0 → 0.8 → 0.2 → 0.05）は、この 300 ms の空白が
  **どこで始まるか**を動かしていただけ
- 待ちなしで動くのはナッジだけ。ナッジの量は (threshold − deadzone) × flick

### いまの設定（触り比べ用）

| | deadzone | threshold | flick | 挙動 |
|---|---|---|---|---|
| 左（カーソル） | 0.05 | **0.9** | **150** | 倒した量だけその場で動く（いっぱいで約 130 px）。いっぱいに倒して 0.3 秒保持で動き続ける |
| 右（スクロール） | 0.05 | 0.05 | 1.0 | 倒して 0.3 秒後から動き続ける |

**両方を触って、合うほうに揃えてください。** 左が合えば右も threshold を上げて
`WHEEL_SPEED["flick"]` を増やす（例: 10〜20）。右が合えば左の threshold を 0.05 に戻す。

| 症状 | いじるもの |
|---|---|
| 軽く倒したときの動きが小さい / 大きい | `XY_SPEED["flick"]` 150 を上下 |
| いっぱいに倒しても動き続けない | threshold 0.9 → 0.85。スティックが端まで届いていない |
| 保持したときの速さが合わない | `XY_SPEED["slow"]` 13 を上下 |
| 指を離してもカーソルが動く（ドリフト） | deadzone 0.05 → 0.12〜0.2 |
| 押し込み（クリック）でポインタが跳ねる | deadzone 0.05 → 0.12 |

```bash
# gamepad/gen.py の DEVICE_SETTINGS / XY_SPEED をいじって
make gamepad && make install-gamepad
```

やらなくていいこと: USB-C の切り分け（300 ms は残る。有線は VID / PID が変わる可能性）、
`interval` を下げる（動き出してからの粒度にしか効かない）。300 ms そのものを消すには
Karabiner のソースを直すしかない（`update_continued_movement_timer()` の
`std::chrono::milliseconds(300)`）。

---

## やること 3 — prompt-refiner をコントローラーから回す（次のセッション）

`/Users/nwakahara/works/prompt-refiner` は、口述した文を Claude Code / Cowork / チャット向けの
構造化プロンプトに整形する CLI。**このリポジトリで作業する**（変えるのはコントローラー側）。
prompt-refiner 側は読むだけで足りる見込み。内蔵ディスクにあるので、このセッションから
読める。

### prompt-refiner の入口（2026-09-19 時点で確認）

| コマンド | 何をするか |
|---|---|
| `~/bin/dictate` | `~/prompt-log/draft.md` を空にして TextEdit で開く（`--keep` で残す） |
| `~/bin/refine <mode>` | **クリップボード**を読み、`claude -p` で整形し、**クリップボードへ**書き戻す。mode は `code` / `research` / `doc` / `ticket` |
| `refine <mode> --from draft` | クリップボードの代わりに `draft.md` を読む |

想定している手順は「口述 → ⌘A → ⌘C → ホットキー → ⌘V」。ホットキーは
`karabiner/prompt-refiner.json` の ⌥⌘V / ⌥⌘1〜4 で、`to` は `shell_command`。

### コントローラー側の設計メモ

- **⌥⌘1 を送っても prompt-refiner のルールは発火しない。** Karabiner は自分が出した
  イベントを再度 manipulate しない（event modification chaining）。ボタンからは
  `shell_command` で `$HOME/bin/refine code` を直接呼ぶ。`gen.py` の `parse_to_token()` に
  `"shell:..."` の形を足し、`validate.py` に `shell_command` を教える
- ホットキーから呼ばれる `refine` は非ログインシェル。`claude` の場所とロケールは
  `refine` 自身が補うので、`shell_command` 側の配慮は要らない
- 手順をボタンに落とすと: L2（口述開始）→ 喋る → L2（終了）→ R2 + A（⌘A）→ Select（⌘C）→
  [整形ボタン] → Start（⌘V）。整形ボタンの置き場は R2 レイヤーに空きがない
  （`MOD_DEFAULT` は 13 枠すべて使用）。候補は `R2 + 左 / 右スティック押込`——押し込みで
  ポインタが跳ねても、整形はクリップボードを読むだけなので困らない。モードは code と
  research の2つに絞るか、`ticket` / `doc` は Raycast 側に残す
- 「⌘A → ⌘C → refine」を1ボタンにまとめるのは競合に注意。Karabiner の `to` は
  キーイベントを順に出すが、`shell_command` は即座に走り、`refine` はその場で
  `pbpaste` する。⌘C がアプリに届く前に読む可能性がある。まとめるなら prompt-refiner に
  `--grab`（osascript で ⌘A ⌘C を打ってから読む）のような口を足す。それは
  prompt-refiner 側の作業で、あちらの CLAUDE.md の作法（`make test`、モード追加は4か所）に従う
- ⌘V の自動化も同じ。整形が終わるのは数秒後で、その間にフォーカスが動く

### 手順

1. `prompt-refiner/README.md` と `CLAUDE.md` を読む（変更はしない）
2. `gen.py` に `shell:` トークンを足して `validate.py` を通す
3. 整形ボタンを R2 + スティック押込に置く。`make gamepad && make install-gamepad`
4. 実機で L2 → 口述 → R2 + A → Select → 整形 → Start の一連を試す
5. ⌘A ⌘C ⌘V を省きたくなったら、そのときに prompt-refiner 側のセッションを起こす

---

## このリポジトリで守ること

`CLAUDE.md` を必ず読んでから作業してください。特にゲームパッド版で効くのは:

- **`gamepad-mode.json` / `CHEATSHEET.md` / `gamepad-device.json` は生成物。**
  直接編集しない。`gen.py` を直して `make gamepad`。マニュアルの文面も `gen.py` の
  `build_cheatsheet()` にある
- **すべての manipulator に `device_if` が必要。** A ボタンは実マウスの左クリックと
  同じイベントなので、付け忘れるとトラックパッドのクリックが死ぬ（`DESIGN.md` §4）。
  `gen.py` 経由なら自動で付く
- **単押し（`BASE`）はエンジニア業務のアプリで変えない。** アプリ別は `APPS[].mod` の
  9 枠だけ。`MOD_LOCKED` の枠を上書きすると `gen.py` が止まる。机に向かうアプリだけ
  `DESK_APPS` で単押しも上書きできるが、ハート（`DESK_LOCKED`）は不可
- **`optional: ["any"]` は狙い。** 外すと L / ハートを握っている間ルールが効かなくなる
- **`make check` を通す。** エラーが出た状態で「たぶん動く」と報告しない
- **実機確認はユーザーに委ねる。** どのキーストロークに翻訳されるか（`to` の中身）を
  書いて渡す

---

## 参考

- [Karabiner リリースノート](https://karabiner-elements.pqrs.org/docs/releasenotes/) —
  ゲームパッド対応は 14.13.0、スティック設定は 15.1.0 で追加
- [Manipulator definition](https://karabiner-elements.pqrs.org/docs/json/complex-modifications-manipulator-definition/)
- [to.lazy](https://karabiner-elements.pqrs.org/docs/json/complex-modifications-manipulator-definition/to/lazy/) /
  [to_if_alone](https://karabiner-elements.pqrs.org/docs/json/complex-modifications-manipulator-definition/to-if-alone/)
- [game_pad_stick_converter.hpp（v16.3.0）](https://github.com/pqrs-org/Karabiner-Elements/blob/v16.3.0/src/apps/CoreService/include/core_service/daemon/device_grabber_details/game_pad_stick_converter.hpp) —
  300 ms のハードコードと、ナッジ / 連続移動の切り替えはここ
- `generic_desktop` を `from` に書けることは公式ドキュメントに記載がない。実機で確認済み
  （`DESIGN.md` §2）
