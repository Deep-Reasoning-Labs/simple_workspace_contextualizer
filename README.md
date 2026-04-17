# simple-workspace-contextualizer

A small CLI for serializing a source repository into a structured, LLM-friendly context format.

It prints:

- a filtered file tree for the workspace
- the full contents of selected files
- stable XML-like wrapper tags so the output can be pasted directly into an LLM prompt

The intended use case is: "take a repo and turn it into a single prompt payload that gives an LLM useful project context."

## Why this exists

LLMs usually perform better when they can see:

- the repository structure
- the important source files
- toolchain and config files
- README / markdown documentation
- the exact source text, without reformatting or lossy transformations

This tool packages that information into one stream.

## Features

- Recursively prints a workspace file tree
- Includes common source files by default
- Includes common toolchain / config files by default
- Supports additional user-supplied glob patterns
- Supports `--override` to disable the built-in file selection globs
- Supports `--ignore GLOB` to add extra ignore globs, one per flag occurrence
- Hides ignored paths from the file tree
- Allows user-supplied globs to explicitly include ignored files in the emitted file contents
- Produces a simple structured output format that is easy to paste into an LLM

## Installation

### From PyPI

```bash
pip install simple-workspace-contextualizer
```

### Local development

```bash
git clone <your-repo-url>
cd simple-workspace-contextualizer
python -m pip install -e .
```

This installs the CLI command:

```bash
swc
```

If you expose an additional alias, document it here too:

```bash
simple_workspace_contextualizer
```

## Requirements

- Python 3.13+

## Usage

```bash
swc ROOT [--override] [--ignore GLOB]... [GLOB ...]
```

### Arguments

#### `ROOT`
Root project directory to scan.

#### `--override`
Disable the built-in default include globs.

When `--override` is present, only the user-supplied globs are used for `<file_contents>`.

#### `--ignore GLOB`
Add one extra ignore glob pattern.

This option may be provided multiple times. Each `--ignore` consumes exactly one glob. Ignore globs affect:

- the emitted `<file_tree>`
- files selected by the built-in default include globs

User-supplied positional include globs still override ignore rules for `<file_contents>`.

Examples:

```bash
swc . --ignore ".venv/**"
swc . --ignore ".venv/**" --ignore "dist/**"
swc . --ignore ".env" "**/*.custom"
```

In the last example, `.env` is ignored and `**/*.custom` is treated as a positional include glob, not another ignore glob.


#### `GLOB ...`
Zero or more additional file glob patterns to include in `<file_contents>`.

These user globs are additive by default, and they can explicitly include files that would otherwise be ignored.

## Examples

Serialize a repo with the default built-in file patterns:

```bash
swc .
```

Add a few extra file patterns:

```bash
swc . "docs/**/*.txt" "proto/**/*.proto"
```

Only include files matching your own globs:

```bash
swc . --override "src/**/*.py" "tests/**/*.py"
```

Add extra ignore rules on top of the built-in ignore list:

```bash
swc . --ignore ".venv/**" --ignore "dist/**"
```

Combine extra ignore rules with explicit include globs:

```bash
swc . --ignore "**/*.min.js" "**/*.map" "src/**/*.ts"
```

Explicitly include something under an otherwise ignored path:

```bash
swc . ".venv/lib/python3.13/site-packages/pip-25.3.dist-info/LICENSE.txt"
```

## Output format

The tool emits XML-like structured text:

```xml
<workspace_context>
  <file_tree>
    ...
  </file_tree>
  <file_contents>
    <file path="src/example.py">
      ...
    </file>
    <file path="pyproject.toml">
      ...
    </file>
  </file_contents>
</workspace_context>
```

### Semantics

- `<file_tree>` contains the filtered directory tree
- `<file_contents>` contains the full contents of selected files
- each `<file>` element has a `path` attribute relative to the workspace root

## File selection model

The set of files included in `<file_contents>` is:

1. the built-in default glob set
2. plus any user-supplied globs

If `--override` is used, the built-in default glob set becomes empty.

So the effective rule is:

- default mode: `default globs ∪ user globs`
- override mode: `user globs`

## Ignore behavior

Ignored paths are hidden from the file tree and excluded from files selected by the built-in default glob set.

You can also add extra ignore rules with `--ignore`.

However, user-supplied positional include globs are allowed to explicitly include ignored files.

That means:

- ignored paths do **not** appear in `<file_tree>`
- ignored files do **not** get included by default
- `--ignore` adds more ignore rules on top of the built-in ignore list
- ignored files **can** still appear in `<file_contents>` if the user explicitly requests them with a positional glob

This is intentional: it keeps the default output clean while still allowing targeted overrides.

## Default included files

The built-in include globs are aimed at "files that are useful to show an LLM."

They include:

- source files such as Python, JavaScript, TypeScript, Go, Rust, Java, C/C++, shell, SQL, and others
- markdown files
- common toolchain and config files such as:
  - `Makefile`
  - `Dockerfile`
  - `pyproject.toml`
  - `requirements.txt`
  - `package.json`
  - `tsconfig.json`
  - `go.mod`
  - `Cargo.toml`
  - `pom.xml`
  - Gradle files
  - common lint / formatter config files

## Typical ignored paths

The ignore list is intended to filter out noisy or generated content such as:

- VCS metadata
- editor / IDE folders
- caches
- virtual environments
- `node_modules`
- build outputs
- coverage artifacts
- generated packaging metadata

Examples include:

- `.git/`
- `.venv/`
- `node_modules/`
- `dist/`
- `build/`
- `__pycache__/`
- `*.egg-info/`
- `*.dist-info/`

You can add more patterns at runtime with repeated `--ignore GLOB` flags.

## Example workflow with an LLM

Generate workspace context:

```bash
swc . > workspace_context.xml
```

Then paste that output into your LLM prompt along with a task, for example:

> Here is the current repository context. Please explain the architecture, identify likely entry points, and suggest how to add feature X.

## Design goals

- Minimal dependencies
- Easy to inspect
- Easy to pipe to stdout
- Easy to compose with shell tooling
- Optimized for LLM context generation rather than archival fidelity

## Non-goals

- Full XML document modeling
- Perfect reproduction of every file in a repository
- Preserving large binary assets
- Replacing dedicated indexing or retrieval systems

## Limitations

- Large repositories can produce very large outputs
- The default globs are heuristic, not exhaustive
- Ignored paths are policy-driven and may need adjustment for your codebase
- Prompt quality still depends on what files are included

## Development

Run locally:

```bash
python -m simple_workspace_contextualizer.cli .
```

Or, if installed in editable mode:

```bash
swc .
```
