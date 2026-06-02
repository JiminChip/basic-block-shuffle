# Design

## Goal

Provide whole-program basic-block layout shuffling. The wrapper composes existing LLVM 18+ features:

```text
source/object inputs
        |
        v
bbshuffle-clang / bbshuffle-clang++
        |
        v
stock clang + stock lld
        |
        v
ELF binary with shuffled .text* input-section layout
```

## Flag Mapping

When shuffling is enabled, compile actions receive:

```text
-fbasic-block-sections=all
-funique-basic-block-section-names
```

Link actions receive:

```text
-fuse-ld=lld
-Wl,--shuffle-sections=<glob>=<seed>
```

The default glob is `.text*` and the default seed is `1` for reproducible
builds.

## Action Detection

The wrapper keeps the decision simple:

- source compile or compile+link: add compile flags
- object-only link: add link flags only
- `-c`, `-S`, `-E`, `-M`, `-MM`: do not add link flags
- `--version`, `--help`, and `-print-*`: pass through unchanged

Wrapper-only options are stripped before invoking real clang.


## Limitations

This is layout obfuscation. It raises the cost of static layout analysis but
does not transform control-flow semantics. LTO is not officially supported in
this version; the wrapper warns when `-flto` is detected and continues.
