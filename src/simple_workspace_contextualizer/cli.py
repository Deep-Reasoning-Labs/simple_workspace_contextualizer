#!/usr/bin/env python3

import argparse
import html
import shlex
import sys
from pathlib import Path

from pathspec import PathSpec


class Args(argparse.Namespace):
    force: list[str]
    ignore: list[str]
    no_load: bool
    save: bool
    patterns: list[str]

    def __init__(self) -> None:
        super().__init__()
        self.force = []
        self.ignore = []
        self.no_load = False
        self.save = False
        self.patterns = []

class PreArgs(argparse.Namespace):
    no_load: bool

    def __init__(self) -> None:
        super().__init__()
        self.no_load = False
        
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        allow_abbrev=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Serialize the current repository into workspace context.\n"
            "- The current working directory is treated as the project root.\n"
            "- Tree visibility starts from .gitignore rules plus implicit .git exclusion.\n"
            "- Argument patterns add files to <file_contents>.\n"
            "- --force PATH overrides ignore/prune behavior from .gitignore.\n"
            "- .swc_args is loaded automatically unless --no-load / -nl is provided.\n"
            "- --save writes the effective args back to .swc_args after a successful run.\n"
            "- IMPORTANT: Single-quote any pattern containing wildcard or special characters.\n"
            "- Examples: '*.py', '*-requirements.txt', '!strange_file_name.txt'"
        ),
    )
    _ = parser.add_argument(
        "--force",
        action="append",
        default=[],
        help=(
            "Force-include an exact file path or directory path, relative to the "
            "current project root. May be provided multiple times."
        ),
    )
    _ = parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help=(
            "Gitignore-style pattern to exclude from both <file_tree> and "
            "<file_contents>. May be provided multiple times."
            "  IMPORTANT: Single-quote any pattern containing wildcard or special characters.\n"
            "  Examples: '*.py', '*-requirements.txt', '!strange_file_name.txt'\n"
        ),
    )
    _ = parser.add_argument(
        "--no-load",
        "-nl",
        action="store_true",
        help="Do not load preset args from .swc_args.",
    )
    _ = parser.add_argument(
        "--save",
        action="store_true",
        help="Save the effective args to .swc_args after a successful run.",
    )
    _ = parser.add_argument(
        "patterns",
        nargs="*",
        help=(
            "Gitignore-style CLI patterns relative to the project root. "
            "Patterns add files to <file_contents>. "
            "  IMPORTANT: Single-quote any pattern containing wildcard or special characters.\n"
            "  Examples: '*.py', '*-requirements.txt', '!strange_file_name.txt'\n"
        ),
    )
    return parser


def parse_args(argv: list[str]) -> Args:
    parser = build_parser()
    return parser.parse_args(argv, namespace=Args())


def should_load_swc_args(raw_argv: list[str]) -> bool:
    pre_parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    _ = pre_parser.add_argument("--no-load", "-nl", action="store_true")
    namespace: PreArgs = pre_parser.parse_known_args(raw_argv, namespace=PreArgs())[0]
    return not namespace.no_load

def read_swc_args(root: Path) -> list[str]:
    swc_args_path: Path = root / ".swc_args"
    if not swc_args_path.is_file():
        return []

    raw_text: str = swc_args_path.read_text(encoding="utf-8", errors="replace").strip()
    if not raw_text:
        return []

    return shlex.split(raw_text, posix=True)


def sanitize_args_for_save(argv: list[str]) -> list[str]:
    # --save is explicitly runtime-only.
    # --no-load / -nl is also runtime-only; saving it into .swc_args would not
    # be useful because it cannot prevent loading of the file that already got loaded.
    return [
        arg
        for arg in argv
        if arg not in {"--save", "--no-load", "-nl"}
    ]


def write_swc_args(root: Path, argv: list[str]) -> None:
    swc_args_path: Path = root / ".swc_args"
    args_to_save: list[str] = sanitize_args_for_save(argv)
    serialized: str = shlex.join(args_to_save)
    _ = swc_args_path.write_text(
        serialized + ("\n" if serialized else ""),
        encoding="utf-8",
    )


def build_gitignore_spec(lines: list[str]) -> PathSpec | None:
    if not lines:
        return None

    return PathSpec.from_lines("gitignore", lines)


def read_gitignore(dir_path: Path) -> PathSpec | None:
    gitignore_path: Path = dir_path / ".gitignore"
    if not gitignore_path.is_file():
        return None

    lines: list[str] = gitignore_path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()
    return build_gitignore_spec(lines)

def normalize_force_paths(
    root: Path,
    raw_force_paths: list[str],
) -> tuple[set[Path], set[Path], set[Path]]:
    all_force_paths: set[Path] = set()
    force_dirs: set[Path] = set()
    force_files: set[Path] = set()

    for raw in raw_force_paths:
        candidate: Path = Path(raw)
        resolved: Path = (candidate if candidate.is_absolute() else root / candidate).resolve()

        try:
            _ = resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"--force path must stay inside the project root: {raw}") from exc

        if not resolved.exists():
            raise ValueError(f"--force path does not exist: {raw}")

        all_force_paths.add(resolved)
        if resolved.is_dir():
            force_dirs.add(resolved)
        else:
            force_files.add(resolved)

    return all_force_paths, force_dirs, force_files


def relative_posix(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def spec_matches(spec: PathSpec | None, root: Path, path: Path, is_dir: bool) -> bool:
    if spec is None:
        return False

    rel_path: str = relative_posix(root, path)
    candidate: str = f"{rel_path}/" if is_dir else rel_path
    return spec.match_file(candidate)


def repo_ignored(
    path: Path,
    is_dir: bool,
    scoped_specs: list[tuple[Path, PathSpec]],
) -> bool:
    ignored: bool = False

    for scope_dir, spec in scoped_specs:
        scoped_rel: str = path.relative_to(scope_dir).as_posix()
        candidate: str = f"{scoped_rel}/" if is_dir else scoped_rel
        result = spec.check_file(candidate)

        if result.index is not None and result.include is not None:
            # For gitignore-style specs:
            # - include=True means a normal ignore pattern matched -> ignored
            # - include=False means a negated pattern matched -> not ignored
            ignored = bool(result.include)

    return ignored


def dir_intersects_forced_subtree(dir_path: Path, all_force_paths: set[Path]) -> bool:
    for forced_path in all_force_paths:
        if dir_path == forced_path:
            return True
        if dir_path in forced_path.parents:
            return True
        if forced_path in dir_path.parents:
            return True
    return False


def path_is_forced(path: Path, force_dirs: set[Path], force_files: set[Path]) -> bool:
    if path in force_files or path in force_dirs:
        return True

    for forced_dir in force_dirs:
        if forced_dir in path.parents:
            return True

    return False


def scan_workspace(
    root: Path,
    user_positive_spec: PathSpec | None,
    user_negative_spec: PathSpec | None,
    all_force_paths: set[Path],
    force_dirs: set[Path],
    force_files: set[Path],
) -> tuple[set[Path], set[Path], set[Path]]:
    visible_dirs: set[Path] = {root}
    visible_files: set[Path] = set()
    selected_files: set[Path] = set()

    def walk_dir(
        dir_path: Path,
        inherited_specs: list[tuple[Path, PathSpec]],
    ) -> None:
        local_spec: PathSpec | None = read_gitignore(dir_path)
        current_specs: list[tuple[Path, PathSpec]] = list(inherited_specs)

        if local_spec is not None:
            current_specs.append((dir_path, local_spec))

        entries: list[Path] = sorted(
            dir_path.iterdir(),
            key=lambda path: (not path.is_dir(), path.name),
        )

        for entry in entries:
            forced_path: bool = path_is_forced(entry, force_dirs, force_files)

            # Git effectively treats .git as out of scope for normal traversal.
            if (entry.name == ".git" or entry.name == ".gitignore" or entry.name == ".swc_args") and not forced_path:
                continue

            if entry.is_dir() and not entry.is_symlink():
                forced_dir: bool = dir_intersects_forced_subtree(entry, all_force_paths)

                if not forced_dir:
                    if repo_ignored(entry, is_dir=True, scoped_specs=current_specs):
                        continue
                    if spec_matches(user_negative_spec, root, entry, is_dir=True):
                        continue

                visible_dirs.add(entry)
                walk_dir(entry, current_specs)
                continue

            if not entry.is_file():
                continue

            if forced_path:
                visible_files.add(entry)
                if spec_matches(user_negative_spec, root, entry, is_dir=False):
                    continue
                if spec_matches(user_positive_spec, root, entry, is_dir=False):
                    selected_files.add(entry)
                continue

            if repo_ignored(entry, is_dir=False, scoped_specs=current_specs):
                continue

            if spec_matches(user_negative_spec, root, entry, is_dir=False):
                continue

            visible_files.add(entry)

            if spec_matches(user_positive_spec, root, entry, is_dir=False):
                selected_files.add(entry)

    walk_dir(root, [])
    return visible_dirs, visible_files, selected_files


def tree_lines(root: Path, visible_dirs: set[Path], visible_files: set[Path]) -> list[str]:
    lines: list[str] = [f"{root.name}/"]

    def render_dir(dir_path: Path, depth: int) -> None:
        child_dirs: list[Path] = sorted(
            [
                child
                for child in dir_path.iterdir()
                if child.is_dir() and not child.is_symlink() and child in visible_dirs
            ],
            key=lambda path: path.name,
        )
        child_files: list[Path] = sorted(
            [
                child
                for child in dir_path.iterdir()
                if child.is_file() and child in visible_files
            ],
            key=lambda path: path.name,
        )

        entries: list[tuple[Path, bool]] = (
            [(path, True) for path in child_dirs]
            + [(path, False) for path in child_files]
        )

        for index, (entry, is_dir) in enumerate(entries):
            branch: str = "└── " if index == len(entries) - 1 else "├── "
            prefix: str = "  " * depth + branch
            lines.append(prefix + entry.name + ("/" if is_dir else ""))

            if is_dir:
                render_dir(entry, depth + 1)

    render_dir(root, 0)
    return lines


def print_file_contents(root: Path, files: list[Path]) -> None:
    print("  <file_contents>")

    for path in files:
        rel_path: str = relative_posix(root, path)
        escaped_rel_path: str = html.escape(rel_path, quote=True)
        text: str = path.read_text(encoding="utf-8", errors="replace")

        print(f'    <file path="{escaped_rel_path}">')
        print(text, end="" if text.endswith("\n") else "\n")
        print("    </file>")

    print("  </file_contents>")

def validate_include_patterns(patterns: list[str]) -> None:
    for pattern in patterns:
        if pattern.startswith("!"):
            raise SystemExit(
                f"Negated patterns are no longer supported as positional arguments: {pattern}\n" +
                f"Use --ignore {pattern[1:]!s} instead."
            )

def main() -> None:
    root: Path = Path.cwd().resolve()

    raw_argv: list[str] = list(sys.argv[1:])
    preset_argv: list[str] = read_swc_args(root) if should_load_swc_args(raw_argv) else []
    effective_argv: list[str] = preset_argv + raw_argv

    args: Args = parse_args(effective_argv)

    validate_include_patterns(args.patterns)

    user_positive_spec = build_gitignore_spec(list(args.patterns))
    user_negative_spec = build_gitignore_spec(list(args.ignore))

    try:
        all_force_paths, force_dirs, force_files = normalize_force_paths(root, list(args.force))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    visible_dirs, visible_files, selected_files = scan_workspace(
        root=root,
        user_positive_spec=user_positive_spec,
        user_negative_spec=user_negative_spec,
        all_force_paths=all_force_paths,
        force_dirs=force_dirs,
        force_files=force_files,
    )

    print("<workspace_context>")

    print("  <file_tree>")
    for line in tree_lines(
        root=root,
        visible_dirs=visible_dirs,
        visible_files=visible_files,
    ):
        print(f"    {line}")
    print("  </file_tree>")

    selection_requested: bool = bool(args.patterns)
    if selection_requested:
        print_file_contents(
            root,
            sorted(selected_files, key=lambda path: relative_posix(root, path)),
        )

    print("</workspace_context>")

    if not raw_argv and not preset_argv:
        print(
            "Tip: pass space-separated .gitignore-style globs to include file contents, " +
            "for example: swc 'src/**/*.py' 'README.md'"
        )

    if args.save:
        write_swc_args(root, effective_argv)


if __name__ == "__main__":
    main()
