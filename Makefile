PYTHON_VERSION=$(shell python3 --version | sed 's/Python \(3\.[0-9][0-9]*\).*/\1/')

PREFIX=~/.local
BIN_DIR=$(PREFIX)/bin
LIB_DIR=$(PREFIX)/lib/python$(PYTHON_VERSION)/site-packages

install:
	@echo $(PYTHON_VERSION)
	mkdir -p $(LIB_DIR)/ledger
	cp -Rv ./ledger/* $(LIB_DIR)/ledger/
	mkdir -p $(BIN_DIR)
	cp -v ./ui.py $(BIN_DIR)/maelkum-ledger
	chmod +x $(BIN_DIR)/maelkum-ledger
	sed -i "s/__commit__ = 'HEAD'/__commit__ = '$(shell git rev-parse HEAD)'/" $(BIN_DIR)/maelkum-ledger
	if [[ -d ~/.config/nvim ]]; then cp -v ./ledger.vim ~/.config/nvim/syntax; fi

watch-install:
	find . -name '*.py' | entr -c make install
