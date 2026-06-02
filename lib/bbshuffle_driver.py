#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


DEFAULT_ENABLED = True
DEFAULT_SEED = "1"
DEFAULT_SECTION_GLOB = ".text*"
SOURCE_EXTS = (".c", ".cc", ".cpp", ".cxx", ".c++", ".C")
OBJECT_EXTS = (".o", ".a", ".so", ".lo")
COMPILE_ONLY_FLAGS = {"-c", "-S", "-E", "-M", "-MM"}
PASSTHROUGH_EXACT = {"--version", "--help", "-help"}
SKIP_NEXT_OPTIONS = {
    "-o",
    "-x",
    "-I",
    "-L",
    "-l",
    "-isystem",
    "-include",
    "-imacros",
    "-idirafter",
    "-iquote",
    "-isysroot",
    "-target",
    "--target",
    "-Xclang",
    "-Xlinker",
    "-Xassembler",
    "-Xpreprocessor",
    "-MF",
    "-MT",
    "-MQ",
}


class UsageError(Exception):
    pass


@dataclass(frozen=True)
class CommandPlan:
    argv: list[str]
    enabled: bool
    print_command: bool
    warnings: list[str]


def main(argv: Sequence[str] | None = None, mode: str | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    mode = mode or infer_mode(argv[0])

    try:
        plan = build_command(argv[1:], os.environ, mode)
    except UsageError as exc:
        print(f"bbshuffle: error: {exc}", file=sys.stderr)
        return 2

    for warning in plan.warnings:
        print(f"bbshuffle: warning: {warning}", file=sys.stderr)

    if plan.print_command:
        print(shlex.join(plan.argv))
        return 0

    if os.environ.get("BBSHUFFLE_VERBOSE", "").lower() in {"1", "true", "yes", "on"}:
        print(f"bbshuffle: exec {shlex.join(plan.argv)}", file=sys.stderr)

    return subprocess.call(plan.argv)


def infer_mode(program: str) -> str:
    return "clang++" if Path(program).name.endswith("++") else "clang"


def build_command(
    args: Sequence[str], env: Mapping[str, str] | None = None, mode: str = "clang"
) -> CommandPlan:
    env = {} if env is None else dict(env)
    clean_args, enabled, seed, section_glob, print_command = parse_wrapper_args(args, env)
    real_compiler = choose_real_compiler(mode, env)

    if is_passthrough(clean_args):
        return CommandPlan([real_compiler] + clean_args, enabled, print_command, [])

    validate_seed(seed)
    validate_section_glob(section_glob)

    warnings: list[str] = []
    injected: list[str] = []

    if enabled:
        if has_lto(clean_args):
            warnings.append("LTO (-flto) is not officially supported; continuing")

        if has_non_lld_linker(clean_args):
            raise UsageError("-fuse-ld must use lld when BB shuffle is enabled")

        if has_source_input(clean_args):
            if not has_basic_block_sections(clean_args):
                injected.append("-fbasic-block-sections=all")
            if not has_unique_basic_block_section_names(clean_args):
                injected.append("-funique-basic-block-section-names")

        if should_link(clean_args):
            if not has_fuse_ld(clean_args):
                injected.append("-fuse-ld=lld")
            if not has_shuffle_sections(clean_args):
                injected.append(f"-Wl,--shuffle-sections={section_glob}={seed}")

    return CommandPlan([real_compiler] + injected + clean_args, enabled, print_command, warnings)


def parse_wrapper_args(
    args: Sequence[str], env: Mapping[str, str]
) -> tuple[list[str], bool, str, str, bool]:
    enabled = parse_bool(env.get("BBSHUFFLE"), DEFAULT_ENABLED, "BBSHUFFLE")
    seed = env.get("BBSHUFFLE_SEED", DEFAULT_SEED)
    section_glob = env.get("BBSHUFFLE_SECTION_GLOB", DEFAULT_SECTION_GLOB)
    print_command = False
    clean_args: list[str] = []

    for arg in args:
        if arg == "--bbshuffle":
            enabled = True
        elif arg == "--no-bbshuffle":
            enabled = False
        elif arg.startswith("--bbshuffle-seed="):
            seed = arg.split("=", 1)[1]
        elif arg == "--bbshuffle-seed":
            raise UsageError("expected --bbshuffle-seed=<int>")
        elif arg.startswith("--bbshuffle-section-glob="):
            section_glob = arg.split("=", 1)[1]
        elif arg == "--bbshuffle-section-glob":
            raise UsageError("expected --bbshuffle-section-glob=<glob>")
        elif arg == "--bbshuffle-print-command":
            print_command = True
        elif arg == "--bbshuffle-help":
            print(HELP_TEXT)
            raise SystemExit(0)
        else:
            clean_args.append(arg)

    return clean_args, enabled, seed, section_glob, print_command


def parse_bool(value: str | None, default: bool, name: str) -> bool:
    if value is None or value == "":
        return default
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise UsageError(f"{name} must be one of 0, 1, true, false, yes, no, on, off")


def choose_real_compiler(mode: str, env: Mapping[str, str]) -> str:
    if mode == "clang++":
        return env.get("BBSHUFFLE_REAL_CLANGXX") or "clang++"
    return env.get("BBSHUFFLE_REAL_CLANG") or "clang"


def validate_seed(seed: str) -> None:
    if seed == "":
        raise UsageError("seed must not be empty")
    try:
        int(seed, 10)
    except ValueError as exc:
        raise UsageError("seed must be an integer") from exc


def validate_section_glob(section_glob: str) -> None:
    if not section_glob:
        raise UsageError("section glob must not be empty")
    if "=" in section_glob:
        raise UsageError("section glob must not contain '='")


def is_passthrough(args: Sequence[str]) -> bool:
    return any(
        arg in PASSTHROUGH_EXACT or arg.startswith("-print-") or arg.startswith("--print-")
        for arg in args
    )


def should_link(args: Sequence[str]) -> bool:
    if any(arg in COMPILE_ONLY_FLAGS for arg in args):
        return False
    return has_any_input(args)


def has_any_input(args: Sequence[str]) -> bool:
    return any(True for _ in positional_args(args))


def has_source_input(args: Sequence[str]) -> bool:
    return any(is_source_path(arg) for arg in positional_args(args))


def positional_args(args: Sequence[str]) -> Iterable[str]:
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in SKIP_NEXT_OPTIONS:
            skip_next = True
            continue
        if arg == "-":
            yield arg
            continue
        if arg.startswith("-"):
            continue
        yield arg


def is_source_path(arg: str) -> bool:
    if arg == "-":
        return True
    return any(arg.endswith(ext) for ext in SOURCE_EXTS)


def has_basic_block_sections(args: Sequence[str]) -> bool:
    return any(arg.startswith("-fbasic-block-sections=") for arg in args)


def has_unique_basic_block_section_names(args: Sequence[str]) -> bool:
    return any(
        arg in {"-funique-basic-block-section-names", "-fno-unique-basic-block-section-names"}
        for arg in args
    )


def has_fuse_ld(args: Sequence[str]) -> bool:
    return any(arg.startswith("-fuse-ld=") or arg == "-fuse-ld" for arg in args)


def has_non_lld_linker(args: Sequence[str]) -> bool:
    for index, arg in enumerate(args):
        value: str | None = None
        if arg.startswith("-fuse-ld="):
            value = arg.split("=", 1)[1]
        elif arg == "-fuse-ld" and index + 1 < len(args):
            value = args[index + 1]

        if value is not None and Path(value).name not in {"lld", "ld.lld"}:
            return True
    return False


def has_shuffle_sections(args: Sequence[str]) -> bool:
    return any("--shuffle-sections" in arg for arg in args)


def has_lto(args: Sequence[str]) -> bool:
    return any(arg == "-flto" or arg.startswith("-flto=") for arg in args)


HELP_TEXT = """\
bbshuffle wrapper options:
  --bbshuffle                     Enable basic-block shuffle injection
  --no-bbshuffle                  Disable basic-block shuffle injection
  --bbshuffle-seed=<int>          Set lld shuffle seed (default: 1)
  --bbshuffle-section-glob=<glob> Set lld section glob (default: .text*)
  --bbshuffle-print-command       Print final compiler command and exit
  --bbshuffle-help                Show this help and exit

Environment:
  BBSHUFFLE=0|1
  BBSHUFFLE_SEED=<int>
  BBSHUFFLE_SECTION_GLOB=<glob>
  BBSHUFFLE_REAL_CLANG=<path>
  BBSHUFFLE_REAL_CLANGXX=<path>
  BBSHUFFLE_VERBOSE=0|1
"""
