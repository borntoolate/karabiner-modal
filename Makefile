SHELL := /bin/bash
PY    := python3
KDIR  := $(HOME)/.config/karabiner/assets/complex_modifications

.DEFAULT_GOAL := all
.PHONY: all vim emacs check leakcheck pdf install install-vim install-emacs clean help

## all: 両モードを再生成 → 検査 → PDF
all: vim emacs

## vim: vim-mode.json と CHEATSHEET.pdf を作り直して検査する
vim:
	cd vim && $(PY) gen.py
	$(PY) shared/validate.py vim/vim-mode.json
	$(PY) shared/make_cheatsheet_pdf.py vim/CHEATSHEET.md vim/CHEATSHEET.pdf

## emacs: emacs-mode.json と CHEATSHEET.pdf を作り直して検査する
emacs:
	cd emacs && $(PY) gen.py
	$(PY) shared/validate.py emacs/emacs-mode.json
	$(PY) shared/make_cheatsheet_pdf.py emacs/CHEATSHEET.md emacs/CHEATSHEET.pdf

## check: 生成せずに既存の JSON を検査する（順序・綴り・修飾キーの漏れ）
check:
	$(PY) shared/validate.py vim/vim-mode.json
	$(PY) shared/validate.py emacs/emacs-mode.json
	$(PY) shared/leakcheck.py vim/vim-mode.json emacs/emacs-mode.json

## leakcheck: optional:any のルールが修飾キーを出力に漏らしていないか調べる
leakcheck:
	$(PY) shared/leakcheck.py vim/vim-mode.json emacs/emacs-mode.json

## pdf: チートシートの PDF だけ作り直す
pdf:
	$(PY) shared/make_cheatsheet_pdf.py vim/CHEATSHEET.md vim/CHEATSHEET.pdf
	$(PY) shared/make_cheatsheet_pdf.py emacs/CHEATSHEET.md emacs/CHEATSHEET.pdf

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

## help: このヘルプ
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## /  /'
