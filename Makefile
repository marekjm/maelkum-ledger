PYTHON_VERSION=$(shell python3 --version | sed 's/Python \(3\.[0-9][0-9]*\).*/\1/')

install:
	@echo $(PYTHON_VERSION)
	mkdir -p ~/.local/lib/python$(PYTHON_VERSION)/site-packages/ledger
	cp -Rv ./ledger/* ~/.local/lib/python$(PYTHON_VERSION)/site-packages/ledger/
	mkdir -p ~/.local/bin
	cp -v ./ui.py ~/.local/bin/maelkum-ledger
	chmod +x ~/.local/bin/maelkum-ledger
