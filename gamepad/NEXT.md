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
- **口述の手順を足した**（2026-09-20）。R2 + L2 = `dictate`（どのアプリでも）、
  TextEdit が前面のときだけ R2 + 十字 ↑ ↓ ← → / Start = `refine code` / `research` /
  `doc` / `ticket` / `message`。`shell_command` で prompt-refiner を直接呼ぶ。
  実機未確認（下記「やること 3」）
- **Claude Desktop 層とブラウザの追加、⌘N のグローバル化**（2026-09-20）。Claude Desktop は
  独立した R2 層（サーフェス切り替え ⌘⌥←→、サイドバー ⌘B、新規セッション ⌘N、前後の
  セッション ⌘⇧[ ]、パレット ⌘K、右に新しいセッション ⌃⌘\、R2 + 左スティック押込 =
  ⌥クリックで分割ビューに開く）。ブラウザは R2 + ↑ = ⌘L、↓ = ⌥⌘B。R2 + 右スティック押込は
  どのアプリでも ⌘N。実機未確認（下記「やること 4」）
- ルール 13 本 / manipulator 175 件
- 長押しで繰り返すのは矢印と削除だけ（`repeat: false` が既定。`hold:` で押しっぱなし）
- スティックは左右で挙動を変えてある（下記「やること 1」）
- マニュアルは `CHEATSHEET.md`（生成物。PDF の元）

`karabiner.json` には反映済みです（`make install-gamepad`、2026-09-20）。直前の状態は
`~/.config/karabiner/automatic_backups/karabiner_before_sn30_<日時>.json` にあります。

---

## やること 1 — 固定ベースを実機で確かめる

固定ベースで一通り操作できることと、L2 で音声入力が始まることは確認済み（2026-09-19）。
残りは修飾キーの合成の細部。`DESIGN.md` §9 の「未確認」を上から順に。特に:

| 確認 | 期待 | 外れたら |
|---|---|---|
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

- **R2 の上書きは既定のある 10 枠 + 既定のない左スティック押込**（`MOD_DEFAULT` のうち
  `MOD_LOCKED` 以外と `MOD_APP_ONLY`）。アプリを足すときは `APPS` に `mod` だけ書く。単押しは変えない
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

## やること 3 — 口述の手順を実機で確かめる

配線は済んでいます（2026-09-20）。起点は R2 + L2（prompt-refiner の `dictate`）で、
整形ボタンはそれが開く TextEdit にだけあります。`make gamepad` / `make check` は通り、
`karabiner.json` にも入れてあります。**実機では未確認**なので、一連の流れを一度通してください。

### 何を送るか

| 操作 | ボタン | Karabiner が出すもの |
|---|---|---|
| 下書きを開く | R2 + L2（どのアプリでも） | `shell_command: $HOME/bin/dictate >/dev/null`（新しい `draft-<日時>.md` を作って TextEdit を前面に） |
| 口述の開始 / 終了 | L2 | `consumer_key_code: dictation`（マイクキー。押すたびにトグル） |
| すべて選択 | R2 + A（TextEdit） | `⌘A` |
| コピー | Select（−） | `⌘C` |
| 整形（Claude Code 向け） | R2 + 十字 ↑（TextEdit） | `shell_command: $HOME/bin/refine code >/dev/null` |
| 整形（調査・壁打ち向け） | R2 + 十字 ↓（TextEdit） | `... refine research ...` |
| 整形（文章作成の依頼） | R2 + 十字 ←（TextEdit） | `... refine doc ...` |
| 整形（起票文） | R2 + 十字 →（TextEdit） | `... refine ticket ...` |
| 清書（送信メッセージ） | R2 + Start（TextEdit） | `... refine message ...` |
| 貼り付け先へ | ハート | `⌘Tab` |
| 貼り付け | Start（＋） | `⌘V` |

`dictate` / `refine` は `/bin/sh -c` で走ります。`refine` はクリップボードを読んで `claude -p` で
整形し、クリップボードへ書き戻します。始まると通知「整形中…」、終わると「整形完了 — ⌘V で
貼り付け」が出ます。生と整形後は `~/prompt-log/` に残ります。TextEdit 以外では R2 + 十字 /
Start は既定（PgUp / PgDn / 単語移動 / 書式なし貼り付け）のままです。

### 試す順

1. どのアプリからでもよいので R2 + L2。TextEdit が空の `draft-<日時>.md` で前面に来る
2. L2 → 喋る → L2
3. R2 + A → Select → R2 + 十字 ↑
4. 「整形完了」の通知を待って、ハートで貼り付け先へ → Start

| 症状 | 見るところ |
|---|---|
| R2 + L2 で TextEdit が開かない | `~/.local/share/karabiner/log/console_user_server.log` に `shell_command stderr:` があるか。EventViewer で L2 がマイクキー（dictation）になっていたら R2 の `sn30_mod` が立っていない |
| R2 + 十字が PgUp などになる | 前面が TextEdit ではない（`com.apple.TextEdit`）。Karabiner の EventViewer → Frontmost Application で bundle id を確認 |
| 通知が何も出ない | 上のログに `shell_command stderr:` があるか。`refine` の `die()` は stderr に出る |
| 「入力が空です」 | ⌘C が届いていない。R2 + A か Select が押せていない |
| 「claude コマンドが見つかりません」 | `refine` が足す PATH（`~/.local/bin` `/opt/homebrew/bin` `/usr/local/bin`）に `claude` がない |
| 「整形中…」のあと「整形完了」が来ない | 整形中にもう一度整形ボタン・R2 + L2・⌥⌘V / ⌥⌘1〜5 を押した。Karabiner は `shell_command` を同時に1つしか走らせず、次で前を強制終了する |
| Start で生の文が貼られる | 通知を待たずに押した。整形は数秒〜十数秒かかる |

### やらなかったこと

- ⌘A ⌘C ⌘V を整形ボタンに畳み込む。`shell_command` は即座に走り、キーイベントは
  あとから届くので、⌘C より先にクリップボードを読みうる。まとめるなら prompt-refiner 側に
  `--grab`（osascript で ⌘A ⌘C を打ってから読む）のような口を足す。あちらの CLAUDE.md の
  作法（`make test`、モード追加は6か所）に従う。⌘S → `refine --from draft` も同じ賭け
- prompt-refiner のホットキー ⌥⌘V / ⌥⌘1 を送る。Karabiner は自分の出力を再 manipulate しない
- 整形ボタンを TextEdit 以外にも置く。5 モードぶんの枠がなく、他アプリでは R2 + A が
  ⌘A でないので、どのみちキーボードが要る。そちらは ⌥⌘1〜5 のまま
- `dictate --keep`（前の口述に言い足す）のボタン。要るならキーボードから

---

## やること 4 — Claude Desktop 層・ブラウザ層・⌘N を実機で確かめる

配線は済んでいて `make gamepad` / `make check` は通り、`karabiner.json` にも入れてあります
（2026-09-20）。次の順で確かめてください。キーは Desktop 2.2553.1 の `app.asar` と Web 層の
ショートカット一覧から取った実物ですが、**ボタンからは一度も押していません**（`DESIGN.md` §9）。

| 確認 | ボタン | 期待 | 外れたら |
|---|---|---|---|
| サーフェスの切り替え | R2 + 十字 ← / → | Chat ↔ Cowork ↔ Code が1つずつ動く。長押しで連打にならない | `once:` が効いていない。EventViewer で ⌘⌥← が1回だけ出ているか |
| サイドバー | R2 + 十字 ↑ | 表示 / 非表示が反転する | 効かなければ ⌘. に差し替え（Web 層の同じ機能。`CLAUDE_DESKTOP_APP["mod"]["UP"]`） |
| 新規セッション | R2 + A、R2 + 右スティック押込 | Code タブなら新規セッション、Chat タブなら新規チャット | — |
| 前後のセッション | R2 + L / R | サイドバーの1つ上 / 下のセッションに移る | 効かなければ ⌃⇧Tab / ⌃Tab（既定）に戻す |
| 分割ビュー（新規） | R2 + 十字 ↓ | 右に新しいセッションの列ができる | View → Split View に項目があるか確認 |
| 分割ビュー（既存） | サイドバーの項目を指して R2 + 左スティック押込 | そのセッションが分割ビューで開く | 押込でポインタが跳ねて隣を掴む → deadzone を 0.12 に。⌥ が付いていない → EventViewer で button1 の前に left_option が出ているか |
| パレット | R2 + Start | 「セッションを検索 / 開始」が開く | — |
| 権限プロンプト | ハート + A / B | 今回は許可 / 拒否 | 許可が ⌘Enter でなく Enter のプロンプトもある（プランモードの承認）。A だけで足りることもある |
| ブラウザ | R2 + 十字 ↑ / ↓ | アドレスバーが選択される / ブックマークの一覧がタブに開く | Chrome の一覧は押込 2 回で開く。A は名前の変更、X / Y は削除 |
| ⌘N | R2 + 右スティック押込（TextEdit / VS Code） | 新しい書類 / ファイル | 押込で右スティックが傾いてスクロールしても ⌘N は出る |

### 見送ったもの（要るなら）

- **返事待ちのセッションへ飛ぶ** `open "claude://code/needs-input"`（Dock メニューの "Sessions
  Waiting for You" と同じ）。`shell_command` になり、整形中に押すと `refine` が消えるので置いて
  いない。要るなら `CLAUDE_DESKTOP_APP["mod"]["DOWN"]` を `shell("open claude://code/needs-input")`
  に差し替える（`DESIGN.md` §5 / §8）
- **メニューバーにフォーカス** ⌃F2（macOS のキーボードショートカット）。十字と A でどのメニュー
  項目にも届くので、ブックマークの一覧や Go メニューの Chat / Cowork / Code にも使える。
  R2 層に空きがないので置いていない
- ⌘⇧N「同じ設定で新規セッション」、⌘⇧⌫「セッションをアーカイブ」、⌘⇧D / ⌘J / ⌘⇧B の
  ペイン切り替え。どれも Web 層に定義がある。枠を空けるなら R2 + B（⌘W）から

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
  10 枠と左スティック押込だけ。`MOD_LOCKED` の枠を上書きすると `gen.py` が止まる。机に向かうアプリだけ
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
- [to.shell_command](https://karabiner-elements.pqrs.org/docs/json/complex-modifications-manipulator-definition/to/shell-command/) —
  環境変数は `$HOME` などごく少数。同時に走るのは1つだけ。実装は
  `src/apps/ConsoleUserServer/include/console_user_server/shell_command_handler.hpp`（`/bin/sh -c`）
- [game_pad_stick_converter.hpp（v16.3.0）](https://github.com/pqrs-org/Karabiner-Elements/blob/v16.3.0/src/apps/CoreService/include/core_service/daemon/device_grabber_details/game_pad_stick_converter.hpp) —
  300 ms のハードコードと、ナッジ / 連続移動の切り替えはここ
- `generic_desktop` を `from` に書けることは公式ドキュメントに記載がない。実機で確認済み
  （`DESIGN.md` §2）
