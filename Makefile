
SOURCES := $(wildcard Makefile setup.py preamble.py v6jail/*.py)
$(info $(SOURCES))

.PHONY: shiv
shiv: bin/v6

bin/v6: ${SOURCES}
	@/usr/local/bin/shiv --python '/usr/local/bin/python3 -sE' \
		  --compile-pyc \
		  --compressed \
		  --preamble ./preamble.py \
		  --entry-point v6jail.cli:cli \
		  --output-file bin/v6 \
		  .

.PHONY: upload-shiv
upload-shiv: shiv
ifeq ($(UPLOAD),)
	$(error Must specify variable UPLOAD=<rsync destination>)
endif
	rsync -av bin/v6 ${UPLOAD} 

