SHELL := /bin/bash
PY    := python3
VENV  := .venv
VPY   := $(VENV)/bin/python
STAMP := $(VENV)/.installed
KDIR  := $(HOME)/.config/karabiner/assets/complex_modifications

.DEFAULT_GOAL := all
.PHONY: all vim emacs check leakcheck pdf venv install install-vim install-emacs \
        clean clean-venv help

## all: 両モードを再生成 → 検査 → PDF
all: vim emacs

## vim: vim-mode.json と CHEATSHEET.pdf を作り直して検査する
vim:
	cd vim && $(PY) gen.py
	$(PY) shared/validate.py vim/vim-mode.json
	$(MAKE) --no-print-directory vim/CHEATSHEET.pdf

## emacs: emacs-mode.json と CHEATSHEET.pdf を作り直して検査する
emacs:
	cd emacs && $(PY) gen.py
	$(PY) shared/validate.py emacs/emacs-mode.json
	$(MAKE) --no-print-directory emacs/CHEATSHEET.pdf

## check: 生成せずに既存の JSON を検査する（順序・綴り・修飾キーの漏れ）
check:
	$(PY) shared/validate.py vim/vim-mode.json
	$(PY) shared/validate.py emacs/emacs-mode.json
	$(PY) shared/leakcheck.py vim/vim-mode.json emacs/emacs-mode.json

## leakcheck: optional:any のルールが修飾キーを出力に漏らしていないか調べる
leakcheck:
	$(PY) shared/leakcheck.py vim/vim-mode.json emacs/emacs-mode.json

## pdf: チートシートの PDF だけ作り直す
pdf: vim/CHEATSHEET.pdf emacs/CHEATSHEET.pdf

# ---------------------------------------------------------------------------
# PDF は Python の playwright（Chromium で組版）と qpdf（バイト再現性のための
# 正規化）に依存します。gen.py / validate.py / explain.py は依存ゼロなので、
# venv は PDF のときだけ使います。`make check` は venv なしで通ります。
# ---------------------------------------------------------------------------
vim/CHEATSHEET.pdf: vim/CHEATSHEET.md $(STAMP)
	@command -v qpdf >/dev/null || { echo "qpdf がありません → brew install qpdf"; exit 1; }
	$(VPY) shared/make_cheatsheet_pdf.py $< $@

emacs/CHEATSHEET.pdf: emacs/CHEATSHEET.md $(STAMP)
	@command -v qpdf >/dev/null || { echo "qpdf がありません → brew install qpdf"; exit 1; }
	$(VPY) shared/make_cheatsheet_pdf.py $< $@

## venv: PDF 生成用の Python 環境を .venv に作る（初回のみ。qpdf は brew install qpdf）
venv: $(STAMP)

# PLAYWRIGHT_SKIP_BROWSER_GC=1 を付けています。これがないと
# `playwright install` が ~/Library/Caches/ms-playwright を掃除して、
# 「使われていない」と判断した他のツールのブラウザを消します。
$(STAMP): requirements.txt
	$(PY) -m venv $(VENV)
	$(VENV)/bin/pip install --quiet --upgrade pip
	$(VENV)/bin/pip install --quiet -r requirements.txt
	PLAYWRIGHT_SKIP_BROWSER_GC=1 $(VENV)/bin/playwright install chromium
	@touch $@
	@echo "PDF 用の環境ができました（$(VENV)）"

## install: 両方の JSON を Karabiner の設定ディレクトリに置く（有効化は手動）
install: install-vim install-emacs

install-vim:
	@mkdir -p "$(KDIR)"
	cp vim/vim-mode.json "$(KDIR)/"
	@echo "placed. Karabiner-Elements > Complex Modifications > Add rule で有効化してください"
	@echo "※ vim と emacs はどちらも Caps Lock を掴みます。同時に有効にしないでください"

install-emacs:
	@mkdir -p "$(KDIR)"
	cp emacs/emacs-mode.json "$(KDIR)/"
	@echo "placed. Karabiner-Elements > Complex Modifications > Add rule で有効化してください"
	@echo "※ vim と emacs はどちらも Caps Lock を掴みます。同時に有効にしないでください"

## clean: 生成物を消す（gen.py から作り直せます）
clean:
	rm -f vim/vim-mode.json emacs/emacs-mode.json
	rm -f vim/CHEATSHEET.pdf emacs/CHEATSHEET.pdf

## clean-venv: PDF 用の Python 環境を消す（作り直しは make venv）
clean-venv:
	rm -rf $(VENV)

## help: このヘルプ
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## /  /'
