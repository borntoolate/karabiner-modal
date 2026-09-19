#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成した gamepad-mode.json / gamepad-device.json を karabiner.json に流し込む。

    python3 gamepad/apply.py            適用
    python3 gamepad/apply.py --dry-run  差分だけ見る
    python3 gamepad/apply.py --remove   [SN30] ルールを剥がす

vim / emacs 版が `make install-vim` で assets/complex_modifications に JSON を
置くだけなのに対し、ゲームパッド版は karabiner.json を直接書き換えます。理由は
DESIGN.md §3 にあります（スティックの効きは complex_modifications では表現できず、
karabiner.json の devices に書くしかないため）。

書き込み前に automatic_backups へバックアップを取ります。
description が `[SN30]` で始まるルールだけを入れ替えるので、Vim モードなど
既存のルールには触りません。
"""

import json
import os
import shutil
import sys
import time

PREFIX = "[SN30]"
HERE = os.path.dirname(os.path.abspath(__file__))
KARABINER = os.environ.get(
    "KARABINER_JSON", os.path.expanduser("~/.config/karabiner/karabiner.json"))


def main(argv):
    mode = "apply"
    for arg in argv:
        if arg == "--dry-run":
            mode = "dry"
        elif arg == "--remove":
            mode = "remove"
        else:
            sys.exit("不明な引数: %s" % arg)

    if not os.path.isfile(KARABINER):
        sys.exit("karabiner.json が見つかりません: %s" % KARABINER)

    with open(KARABINER, encoding="utf-8") as fh:
        config = json.load(fh)

    profiles = config.get("profiles", [])
    profile = next((p for p in profiles if p.get("selected")),
                   profiles[0] if profiles else None)
    if profile is None:
        sys.exit("プロファイルが見つかりません")

    cm = profile.setdefault("complex_modifications", {})
    existing = cm.get("rules", [])
    kept = [r for r in existing
            if not str(r.get("description", "")).startswith(PREFIX)]
    removed = len(existing) - len(kept)

    added = 0
    settings_count = 0
    if mode == "remove":
        new_rules = kept
    else:
        with open(os.path.join(HERE, "gamepad-mode.json"), encoding="utf-8") as fh:
            generated = json.load(fh)["rules"]
        new_rules = generated + kept
        added = len(generated)

        with open(os.path.join(HERE, "gamepad-device.json"), encoding="utf-8") as fh:
            spec = json.load(fh)
        want = spec["identifiers"]
        devices = profile.setdefault("devices", [])
        entry = next(
            (d for d in devices
             if d.get("identifiers", {}).get("vendor_id") == want["vendor_id"]
             and d.get("identifiers", {}).get("product_id") == want["product_id"]),
            None)
        if entry is None:
            entry = {"identifiers": dict(want), "ignore": False}
            devices.append(entry)
        entry.update(spec["settings"])
        settings_count = len(spec["settings"])

    print("karabiner.json       : %s" % KARABINER)
    print("置き換える %s ルール : %d 件" % (PREFIX, removed))
    print("投入する %s ルール   : %d 件" % (PREFIX, added))
    print("スティック設定       : %d 項目" % settings_count)
    print("そのまま残すルール   : %d 件" % len(kept))
    for r in kept:
        print("    · %s" % r.get("description", "(no description)"))

    if mode == "dry":
        print("\n--dry-run なので書き込みませんでした。")
        return 0

    backup_dir = os.path.join(os.path.dirname(KARABINER), "automatic_backups")
    os.makedirs(backup_dir, exist_ok=True)
    backup = os.path.join(
        backup_dir, "karabiner_before_sn30_%s.json" % time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(KARABINER, backup)
    print("\nバックアップ         : %s" % backup)

    cm["rules"] = new_rules
    tmp = KARABINER + ".sn30.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(config, fh, ensure_ascii=False, indent=4)
        fh.write("\n")
    os.replace(tmp, KARABINER)
    print("書き込み完了         : Karabiner が自動で読み直します")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
