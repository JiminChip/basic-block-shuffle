WRAPPER ?= ../../bin/bbshuffle-clang
CLANG ?= clang
OBJDUMP ?= objdump
READELF ?= readelf

CFLAGS ?= -O2
MAP_FLAGS_1 ?= -Wl,-Map,demo.shuffle.1.map
MAP_FLAGS_2 ?= -Wl,-Map,demo.shuffle.2.map

.PHONY: all clean inspect

all: demo.plain demo.o demo.shuffle.1 demo.shuffle.2

demo.plain: demo.c
	$(CLANG) $(CFLAGS) -fuse-ld=lld $< -o $@

demo.o: demo.c
	$(WRAPPER) $(CFLAGS) --bbshuffle-seed=1111 -c $< -o $@

demo.shuffle.1: demo.c
	$(WRAPPER) $(CFLAGS) --bbshuffle-seed=1111 $(MAP_FLAGS_1) $< -o $@

demo.shuffle.2: demo.c
	$(WRAPPER) $(CFLAGS) --bbshuffle-seed=2222 $(MAP_FLAGS_2) $< -o $@

inspect: all
	@echo "== object sections: demo.o =="
	$(READELF) -SW demo.o | grep -E '\.text|Name'
	@echo
	@echo "== disassembly labels: shuffled seed 1111 =="
	$(OBJDUMP) -d demo.shuffle.1 | grep -E '<(main|branchy|\.text)' | head -40
	@echo
	@echo "== map sections: shuffled seed 1111 =="
	grep -E '\.text' demo.shuffle.1.map | head -40
	@echo
	@echo "== map sections: shuffled seed 2222 =="
	grep -E '\.text' demo.shuffle.2.map | head -40

clean:
	rm -f demo.o demo.plain demo.shuffle.1 demo.shuffle.2 \
	      demo.shuffle.1.map demo.shuffle.2.map
