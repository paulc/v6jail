
SOURCES := $(wildcard Makefile setup.py v6jail/*.py)

.PHONY: shiv
shiv: bin/v6

bin/v6: ${SOURCES}
	@shiv -p '/usr/bin/env -S python3 -sE' --compile-pyc --compressed -e v6jail.cli:cli -o bin/v6 .

.PHONY: upload-shiv
upload-shiv: shiv
ifeq ($(UPLOAD),)
	$(error Must specify variable UPLOAD=<rsync destination>)
endif
	rsync -av bin/v6 ${UPLOAD} 

