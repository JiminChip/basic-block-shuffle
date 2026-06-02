# basic-block-shuffle

`basic-block-shuffle` is a tiny compiler wrapper for stock LLVM 18+ toolchains.
It enables whole-program basic-block layout shuffling for ELF/lld builds without
patching clang, lld, or LLVM.

The wrapper injects existing clang/lld flags:

```bash
bbshuffle-clang main.c -o main
```

becomes:

```bash
clang \
  -fbasic-block-sections=all \
  -funique-basic-block-section-names \
  -fuse-ld=lld \
  -Wl,--shuffle-sections=.text*=1 \
  main.c -o main
```

## Requirements

- Linux or WSL targeting x86_64 ELF.
- clang 18+.
- lld 18+.
- Python 3 standard library only.

## Usage

Use the wrappers directly:

```bash
basic-block-shuffle/bin/bbshuffle-clang demo.c -o demo
basic-block-shuffle/bin/bbshuffle-clang++ demo.cc -o demo
```

Or point a build system at them:

```bash
CC=/path/to/basic-block-shuffle/bin/bbshuffle-clang \
CXX=/path/to/basic-block-shuffle/bin/bbshuffle-clang++ \
make
```

For CMake:

```bash
cmake -S . -B build \
  -DCMAKE_C_COMPILER=/path/to/basic-block-shuffle/bin/bbshuffle-clang \
  -DCMAKE_CXX_COMPILER=/path/to/basic-block-shuffle/bin/bbshuffle-clang++
```

## Wrapper Options

```text
--bbshuffle
--no-bbshuffle
--bbshuffle-seed=<int>
--bbshuffle-section-glob=<glob>
--bbshuffle-print-command
--bbshuffle-help
```

Environment variables:

```text
BBSHUFFLE=0|1
BBSHUFFLE_SEED=<int>
BBSHUFFLE_SECTION_GLOB=<glob>
BBSHUFFLE_REAL_CLANG=<path>
BBSHUFFLE_REAL_CLANGXX=<path>
BBSHUFFLE_VERBOSE=0|1
```

Precedence is:

```text
CLI option > environment variable > default
```

Defaults:

```text
BBSHUFFLE=1
BBSHUFFLE_SEED=1
BBSHUFFLE_SECTION_GLOB=.text*
real clang=clang
real clang++=clang++
```

## Examples

```bash
cd basic-block-shuffle/examples/elf-lld
make
make inspect
```

The example builds a plain binary, two shuffled binaries with different seeds,
and an object file for checking emitted basic-block sections.

## Tests

Use the requested venv:

```bash
source /mnt/c/Hacking/myenv/bin/activate
python -m unittest discover -s basic-block-shuffle/tests
```

## Limitations

- ELF/lld only.
- LTO is not officially supported. The wrapper warns when `-flto` is present and
  continues.
- This is layout obfuscation only. It does not add control-flow flattening,
  instruction substitution, or opaque predicates.
