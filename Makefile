python_version=$(shell python3 --version | sed 's/Python \(3\.[0-9][0-9]*\).*/\1/')

version_style?=auto
version_used=$(shell bash ./make-version.sh $(version_style))

PREFIX=~/.local
BIN_DIR=$(PREFIX)/bin
LIB_DIR=$(PREFIX)/lib/python$(python_version)/site-packages

install:
	@mkdir -p $(LIB_DIR)/ledger
	cp -R ./ledger/* $(LIB_DIR)/ledger/
	@mkdir -p $(BIN_DIR)
	cp ./ui.py $(BIN_DIR)/maelkum-ledger
	chmod +x $(BIN_DIR)/maelkum-ledger
	@sed -i \
		"s/__version__ = \".*\"/__version__ = \"$(version_used)\"/" \
		$(LIB_DIR)/ledger/__init__.py
	if [[ -d ~/.config/nvim ]]; then cp ./ledger.vim ~/.config/nvim/syntax; fi

watch-install:
	find . -name '*.py' | entr -c make install

format:
	@black ui.py ledger
