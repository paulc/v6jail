
SOURCES = v6jail/__init__.py v6jail/cli.py v6jail/config.py v6jail/host.py v6jail/jail.py v6jail/util.py

.PHONY: shiv
shiv: bin/v6

bin/v6: ${SOURCES}
	@shiv -p '/usr/bin/env python3' -e v6jail.cli:cli -o bin/v6 .

.PHONY: upload-shiv
upload-shiv: shiv
ifeq ($(UPLOAD),)
	$(error Must specify variable UPLOAD=<rsync destination>)
endif
	rsync -av bin/v6 ${UPLOAD} 

