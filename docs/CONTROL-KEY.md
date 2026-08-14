# Caps Lock を Control にリマップしていた人向けの移行メモ

macOS の**システム設定 → キーボード → キーボードショートカット… → 修飾キー**で
Caps Lock を Control に変更して使っていた場合、この設定を入れると
**その割り当ては効かなくなります。** その理由と、必要な移行作業をまとめます。

---

## 1. なぜ効かなくなるのか

Karabiner のイベント処理は次の順番です。

```
1. ハードウェアからイベントを取得
2. Simple Modifications
3. Complex Modifications                        ← この設定はここで動く
4. Function Keys Modifications
5. システム設定 > 修飾キー（Caps Lock → Control）  ← macOS のリマップはここ
6. 仮想キーボード経由でアプリへ送出
```

ポイントは2つです。

**Karabiner のほうが先に動きます。**
だから `from.key_code: caps_lock` を指定したこの設定のルールは、
macOS 側のリマップに関係なく正常に発火します。ここは問題ありません。

**Karabiner は物理キーボードを占有します。**
Karabiner は `kIOHIDOptionsTypeSeizeDevice` でデバイスを掴み、
すべての入力イベントを横取りします。その結果、
**物理キーボードに対する macOS 側の修飾キーリマップは適用されなくなります。**

つまり、Caps Lock が Control として振る舞う経路そのものが消えます。

> 段階5の「修飾キー」は、Karabiner が出力に使う
> **仮想キーボード（Karabiner DriverKit VirtualHIDKeyboard）** に対して適用されます。
> 物理キーボード側でいくら設定しても、掴まれている以上は無視されます。

---

## 2. やること

### (1) Control は物理の Control キーを使う

Caps Lock は Vim モードのリーダー専用になります。
⌃C、⌃A、⌃E、⌃K、⌃Tab などの Control 系ショートカットは、
キーボード左下の**本物の Control キー**で押してください。

### (2) 入力ソースの切り替えは設定済み

`Caps + Space` で ⌃Space（前の入力ソースを選択）を送るルールを入れてあります。
**指の動きは今までとまったく同じです。** 何も設定しなくてもそのまま動きます。

```json
{
  "from": { "key_code": "spacebar", "modifiers": { "optional": ["caps_lock"] } },
  "to":   [ { "key_code": "spacebar", "modifiers": ["left_control"] } ],
  "conditions": [ { "type": "variable_if", "name": "vim_mode", "value": 1 } ]
}
```

切り替えに ⌃⌥Space（入力メニューの次のソースを選択）を使っている場合は、
`gen.py` の該当行の `["left_control"]` を `["left_control", "left_option"]` に変えて
再生成してください。

### (3) システム設定の修飾キーを既定に戻す

**これはやっておいたほうがいいです。**

Karabiner 15.5.0 以降、仮想キーボードに修飾キーのリマップが残っていると
アプリ内に警告が出ます。公式の推奨は「macOS 側は既定に戻し、
修飾キーの変更はすべて Karabiner で行う」です。

1. システム設定 → キーボード → キーボードショートカット… → **修飾キー**
2. デバイスのプルダウンで **Karabiner DriverKit VirtualHIDKeyboard** を選ぶ
3. **デフォルトを復元** を押す
4. 物理キーボード側の項目でも、Caps Lock キーを **「Caps Lock」**（既定）に戻す

放置しても今回の設定は動きますが、将来 Karabiner のルールで
`caps_lock` を**出力**するようなものを足したときに、macOS 側が
それを Control に変換してしまい、原因の分かりにくい不具合になります。

> 補足：Karabiner 15.1.0 以降、仮想キーボードは Apple Aluminum USB Keyboard (A1243) と
> 同じベンダー ID を名乗るため、修飾キーの設定がその機種と共有されます。
> 心当たりのない設定が入っていることがあるので、一度確認しておくと安心です。

---

## 3. Emacs キーバインドを多用していた場合の補足

Caps Lock が指の近くにあったからこそ ⌃A / ⌃E / ⌃K を多用していた、
という場合、本物の Control キーは遠くて不便に感じるかもしれません。

ただ、**よく使う Emacs バインドの大半は Vim モード側に同等品があります。**

| Emacs | 動作 | この設定での代替 |
|---|---|---|
| `⌃A` | 行頭へ | `Caps + 6`（`^`）または `Caps + 0` |
| `⌃E` | 行末へ | `Caps + 4`（`$`） |
| `⌃F` / `⌃B` | 1文字前後 | `Caps + l` / `Caps + h` |
| `⌃N` / `⌃P` | 1行下 / 上 | `Caps + j` / `Caps + k` |
| `⌃D` | 前方削除 | `Caps + x` |
| `⌃H` | 後方削除 | `Caps + ⇧x` |
| `⌃K` | 行末まで削除 | `Caps + ⇧d` |
| `⌃Y` | 貼り付け | `Caps + p` |

移動と削除に関しては、むしろ Vim モードのほうが
ホームポジションから動かずに済みます。

一方で ⌃C（中断）、⌃Z（サスペンド）、⌃R（履歴検索）、⌃T、⌃Tab などは
Vim モードに対応物がないので、本物の Control キーを使ってください。

---

## 4. どうしても Caps Lock を Control としても使いたい場合

両立させる方法はあります。`caps_lock` の manipulator の `to` に
`left_control` を `lazy` 付きで足し、Vim 側の全ルールの
`from.modifiers` を `{"mandatory": ["control"], "optional": ["any"]}` に変更する、
という手です。mandatory 指定した修飾キーは出力から取り除かれるため、
Vim で割り当てたキーは Vim として、それ以外は Control として通ります。

```json
"to": [
  { "set_variable": { "name": "vim_mode", "value": 1 } },
  { "key_code": "left_control", "lazy": true }
]
```

ただし、この方式では **Vim で割り当てているキーの Control 版が全滅します。**

| 使えるもの | ⌃C ⌃Z ⌃R ⌃T ⌃N ⌃F ⌃S ⌃Q ⌃M ⌃I ⌃Tab ⌃Space ⌃矢印 |
|---|---|
| **使えなくなるもの** | **⌃A ⌃E ⌃K ⌃D ⌃P ⌃B ⌃H ⌃W ⌃U ⌃V ⌃Y ⌃X ⌃G ⌃L ⌃J** |

Emacs バインドの中核が軒並み失われるので、あまり得はしません。
「Vim モードのキーを減らす」か「Control は本物のキーで押す」かの
どちらかを選ぶほうが素直です。

必要になったら言ってください。設定を作り直します。

---

## 参考

- [Input event modification chaining — Karabiner-Elements](https://karabiner-elements.pqrs.org/docs/manual/misc/event-modification-chaining/)
- [Breaking changes — Karabiner-Elements](https://karabiner-elements.pqrs.org/docs/help/troubleshooting/breaking-changes/)
- [System Preferences modifier keys have no effect on grabbed devices — issue #568](https://github.com/pqrs-org/Karabiner-Elements/issues/568)
