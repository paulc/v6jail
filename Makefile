
SOURCES := $(wildcard Makefile setup.py preamble.py v6jail/*.py)
$(info $(SOURCES))

.PHONY: shiv
shiv: bin/v6

bin/v6: ${SOURCES}
	@/bin/mkdir -p bin
	@/usr/bin/env shiv --python '/usr/local/bin/python3 -sE' \
		  --compile-pyc \
		  --compressed \
		  --preamble ./shiv/preamble.py \
		  --entry-point v6jail.cli:cli \
		  --output-file bin/v6 \
		  .

.PHONY: upload-shiv
upload-shiv: shiv
ifeq ($(UPLOAD),)
	$(error Must specify variable UPLOAD=<rsync destination>)
endif
	rsync -av bin/v6 ${UPLOAD} 

clean:
	rm -f ./bin/* ./dist/* ./v6jail/__pycache__/* ./v6jail.egg-info/*

