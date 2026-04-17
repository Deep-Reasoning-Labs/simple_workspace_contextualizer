#!/usr/bin/env python3

import argparse
import html
import os
from pathlib import Path

BASE_GLOBS: list[str] = [
    "**/*.md",
    "**/*.py",
    "**/*.js",
    "**/*.ts",
    "**/*.tsx",
    "**/*.jsx",
    "**/*.java",
    "**/*.go",
    "**/*.rs",
    "**/*.c",
    "**/*.cc",
    "**/*.cpp",
    "**/*.h",
    "**/*.hpp",
    "**/*.cs",
    "**/*.rb",
    "**/*.php",
    "**/*.swift",
    "**/*.kt",
    "**/*.kts",
    "**/*.scala",
    "**/*.sh",
    "**/*.bash",
    "**/*.zsh",
    "**/*.json",
    "**/*.yaml",
    "**/*.yml",
    "**/*.toml",
    "**/*.xml",
    "**/*.html",
    "**/*.css",
    "**/*.sql",

    # toolchain / repo config
    "Makefile",
    "**/Makefile",
    "Dockerfile",
    "**/Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "pyproject.toml",
    "requirements.txt",
    "requirements-*.txt",
    "setup.py",
    "setup.cfg",
    "tox.ini",
    ".python-version",
    ".pre-commit-config.yaml",
    ".editorconfig",
    ".gitignore",
    ".gitattributes",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "tsconfig.json",
    "jest.config.js",
    "jest.config.ts",
    "vite.config.ts",
    "vite.config.js",
    "webpack.config.js",
    "webpack.config.ts",
    "rollup.config.js",
    "rollup.config.ts",
    "eslint.config.js",
    "eslint.config.mjs",
    ".eslintrc",
    ".eslintrc.json",
    ".eslintrc.js",
    ".prettierrc",
    ".prettierrc.json",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradle.properties",
    "Gemfile",
    "Gemfile.lock",
]

IGNORE_GLOBS: set[str] = {
    "**/.git",
    "**/.hg",
    "**/.svn",
    "**/.idea",
    "**/.vscode",
    "**/.mypy_cache",
    "**/.pytest_cache",
    "**/.ruff_cache",
    "**/.tox",
    "**/.nox",
    "**/__pycache__",
    "**/.venv",
    "**/venv",
    "**/env",
    "**/site-packages",
    "**/site-packages",
    "**/node_modules",
    "**/node_modules",
    "**/dist",
    "**/dist",
    "**/build",
    "**/build",
    "**/target",
    "**/target",
    "**/coverage",
    "**/coverage",
    "**/.coverage",
    "**/.next",
    "**/.nuxt",
    "**/.terraform",
    "**/.serverless",
    "**/.cache",
    "**/vendor",
    "**/vendor",
    "**/out",
    "**/out",
    "**/bin",
    "**/bin",
    "**/obj",
    "**/obj",
    "**/.eggs",
    "**/*.egg-info",
    "**/*.egg-info",
    "**/*.dist-info",
    "**/*.dist-info",
    "**/pip-wheel-metadata",
    "**/pip-wheel-metadata",
    "**/__pypackages__",

    "**/*.env",
    "**/*.env.*",
    "**/*~",
    "**/*#",
    "**/.DS_Store",
    "**/.gitignore",
}


class Args(argparse.Namespace):
    root: str
    override: bool
    globs: list[str]
    ignore: list[str]

    def __init__(self) -> None:
        super().__init__()
        self.root = ""
        self.override = False
        self.globs = []
        self.ignore = []


def matches_any_glob(root: Path, path: Path, patterns: list[str] | set[str]) -> bool:
    rel: Path = path.relative_to(root)
    return any(rel.full_match(pattern) for pattern in patterns)

def is_ignored(root: Path, path: Path, ignore_globs: list[str] | set[str]) -> bool:
    return matches_any_glob(root, path, ignore_globs)


def iter_files(root: Path, respect_ignores: bool, ignore_globs: list[str] | set[str]) -> list[Path]:
    files: list[Path] = []

    for dirpath_str, dirnames, filenames in os.walk(root):
        dirpath: Path = Path(dirpath_str)

        if respect_ignores:
            dirnames[:] = sorted(
                name
                for name in dirnames
                if not is_ignored(root, dirpath / name, ignore_globs)
            )
            filenames = sorted(
                name
                for name in filenames
                if not is_ignored(root, dirpath / name, ignore_globs)
            )
        else:
            dirnames.sort()
            filenames.sort()

        for name in filenames:
            files.append((dirpath / name).resolve())

    return files

def collect_files(
    root: Path,
    base_globs: list[str],
    user_globs: list[str],
    ignore_globs: list[str] | set[str],
) -> list[Path]:
    base_matches: set[Path] = set()
    user_matches: set[Path] = set()

    if base_globs:
        for path in iter_files(root, respect_ignores=True, ignore_globs=ignore_globs):
            if matches_any_glob(root, path, base_globs):
                base_matches.add(path)

    for pattern in user_globs:
        for path in root.glob(pattern):
            if path.is_file():
                user_matches.add(path.resolve())

    all_matches: set[Path] = base_matches | user_matches
    return sorted(all_matches, key=lambda path: path.relative_to(root).as_posix())


def tree_lines(root: Path, ignore_globs: list[str] | set[str]) -> list[str]:
    lines: list[str] = [f"{root.name}/"]

    def walk(directory: Path, prefix: str) -> None:
        dir_entries: list[Path] = sorted(
            (
                path for path in directory.iterdir()
                if not is_ignored(root, path, ignore_globs)
            ),
            key=lambda path: (not path.is_dir(), path.name.lower(), path.name),
        )

        for index, path in enumerate(dir_entries):
            is_last: bool = index == len(dir_entries) - 1
            branch: str = "└── " if is_last else "├── "
            suffix: str = "/" if path.is_dir() else ""

            lines.append(f"{prefix}{branch}{path.name}{suffix}")

            if path.is_dir():
                child_prefix: str = prefix + ("    " if is_last else "│   ")
                walk(path, child_prefix)

    walk(root, "")
    return lines

def xml_cdata(text: str) -> str:
    return text.replace("]]>", "]]]]><![CDATA[>")

def print_file_contents(root: Path, files: list[Path]) -> None:
    print("  <file_contents>")

    for path in files:
        rel_path: str = path.relative_to(root).as_posix()
        escaped_rel_path: str = html.escape(rel_path, quote=True)
        text: str = path.read_text(encoding="utf-8", errors="replace")
        cdata_text: str = xml_cdata(text)

        print(f'    <file path="{escaped_rel_path}"><![CDATA[')
        print(cdata_text, end="" if cdata_text.endswith("\n") else "\n")
        print("]]></file>")

    print("  </file_contents>")


def parse_args() -> Args:
    parser = argparse.ArgumentParser(
        description="Serialize a code repository into XML-like workspace context for LLM input."
    )
    _ = parser.add_argument("root", help="Root project directory")
    _ = parser.add_argument(
        "--override",
        action="store_true",
        help="Ignore the built-in base glob patterns",
    )
    _ = parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="GLOB",
        help="Additional ignore globs. May be provided multiple times.",
    )
    _ = parser.add_argument(
        "globs",
        nargs="*",
        help="Additional file glob patterns to include in <file_contents>",
    )
    return parser.parse_args(namespace=Args())


def main() -> None:
    args: Args = parse_args()

    root: Path = Path(args.root).resolve()
    base_globs: list[str] = [] if args.override else BASE_GLOBS
    user_globs: list[str] = list(args.globs)
    ignore_globs: list[str] = [*IGNORE_GLOBS, *args.ignore]

    files: list[Path] = collect_files(
        root,
        base_globs,
        user_globs,
        ignore_globs,
    )

    print("<workspace_context>")

    print("  <file_tree>")
    for line in tree_lines(root, ignore_globs):
        print(f"    {line}")
    print("  </file_tree>")

    print_file_contents(root, files)

    print("</workspace_context>")


if __name__ == "__main__":
    main()
