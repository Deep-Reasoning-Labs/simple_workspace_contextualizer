# simple-workspace-contextualizer

`swc` serializes a repository into a compact XML-like format that is easy to paste into an LLM.

It is designed for fast repository inspection:

- the current working directory is treated as the project root
- `.gitignore` files are respected
- ignored directories are pruned eagerly for performance
- `<file_tree>` is always printed
- `<file_contents>` is only printed when you explicitly request files with include patterns


Example:

```
swc

<workspace_context>
  <file_tree>
    swe-bench-pro-harness/
    ├── README.md
    ├── evaluate.sh
    ├── inference.sh
    ├── setup_evaluation.sh
    └── setup_inference.sh
  </file_tree>
  <file_contents>
    <file path="README.md">
      ...
    </file>
    <file path="evaluate.sh">
      ...
    </file>
    <file path="inference.sh">
      ...
    </file>
    <file path="setup_evaluation.sh">
      ...
    </file>
    <file path="setup_inference.sh">
      ...
    </file>
  </file_contents>
</workspace_context>
```

## Installation

If installing from pip:

```bash
pip install simple-workspace-contextualizer
```

If installing from a local checkout:

```bash
pip install -e .
```

This installs the commands:

```bash
simple_workspace_contextualizer
swc
```

## Basic usage

Run from the project root:

```bash
swc
```

This prints:

- `<workspace_context>`
- `<file_tree>`
- `</workspace_context>`

and does **not** print `<file_contents>`.

To include file contents, pass one or more gitignore-style include patterns:

```bash
swc '*.py'
swc 'src/**/*.py' README.md
swc 'docs/**/*.md' pyproject.toml
```

IMPORTANT: single-quote patterns that include special characters like '*' or '!'.

## Output format

`swc` prints XML-like output in this shape:

```xml
<workspace_context>
  <file_tree>
    ...
  </file_tree>
  <file_contents>
    <file path="relative/path.py">
      ...
    </file>
  </file_contents>
</workspace_context>
```

Notes:

- `<file_tree>` is always present
- `<file_contents>` is only present when include patterns were supplied
- file paths are always relative to the current project root

## Ignore behavior

`swc` discovers `.gitignore` files in the repository and applies them relative to the directory that contains each `.gitignore`.

This means:

- root `.gitignore` patterns apply from the repo root
- nested `subdir/.gitignore` patterns apply from `subdir/`
- ignored directories are pruned immediately during traversal for performance
- `.git` is implicitly excluded

If no `.gitignore` files exist, then there are no repository ignore rules other than the implicit `.git` exclusion.

## Include patterns

Positional arguments are **gitignore-style include patterns**.

They do **not** affect traversal of ignored directories. They only select files for `<file_contents>` from the files that were actually traversed.

Examples:

```bash
swc '*.md'
swc 'src/**/*.py'
swc 'src/**/*.py' tests/test_smoke.py
```

## `--ignore`

Use `--ignore` to exclude files or directories from both `<file_tree>` and `<file_contents>`.

`--ignore` accepts gitignore-style patterns and may be provided multiple times.

Examples:

```bash
swc --ignore subsets
swc --ignore 'subsets/**'
swc --ignore '*.md'
swc --ignore 'docs/**/*.md'
swc --ignore 'build/'
```

`--ignore` is useful for trimming noisy files from the output even when they are not ignored by `.gitignore`.

`--ignore` prunes file traversal early, so it is also useful for large directories that would otherwise make file traversal slow.

## `--force`

Use `--force` to override ignored traversal for an exact file path or directory path.

`--force` is **not** a glob. It must be a real path inside the current project root.

This is primarily useful when a directory is ignored by `.gitignore` and would otherwise be pruned by an ignore pattern before `swc` could inspect it.

Examples:

```bash
swc --force .venv
swc --force generated 'generated/**/*.ts'
swc --force subsets 'subsets/**/*.txt'
```

Behavior:

- if `--force` points to a directory, that subtree is traversed even if it is ignored
- if `--force` points to a file, that file is allowed through even if it is ignored
- `--ignore` still has higher practical priority for exclusion behavior during output filtering

## `.swc_args`

You can create a file named `.swc_args` in the project root containing default `swc` arguments.

The file is a single line of space-separated arguments.

Example:

```text
--ignore subsets 'src/**/*.py' 'README.md'
```

When present, `swc` loads `.swc_args` automatically and prepends those arguments before the command-line arguments you typed.

That means you can saved and re-use common patterns and just type `swc` to repeat those queries.

Your explicit command-line arguments are appended after the saved `.swc_args` arguments so you can still refine the query.

### Disable loading

Use either of these to skip `.swc_args` loading:

```bash
swc --no-load
swc -nl
```

## `--save`

Use `--save` to save the current effective arguments back to `.swc_args`.

The save only happens after a successful run.

Examples:

```bash
swc --ignore subsets 'src/**/*.py' --save
swc --force generated 'generated/**/*.ts' --save
```

Notes:

- `--save` itself is not written into `.swc_args`
- `--no-load` / `-nl` are also not written into `.swc_args`

## Shell quoting tip

If a pattern contains shell wildcard characters, **single-quote it**.

Examples:

```bash
swc '*.py'
swc --ignore '*-requirements.txt'
swc 'docs/**/*.md'
```

Why this matters:

- unquoted wildcards are expanded by your shell **before** `swc` sees them
- this can change the meaning of the command
- single quotes are the safest default

For example:

```bash
swc --ignore '*-requirements.txt'
```

is correct, but:

```bash
swc --ignore *-requirements.txt
```

may be expanded by the shell into multiple filenames before `swc` starts.

## Recommended workflow

### 1. Inspect the tree

```bash
swc
```

### 2. Add the files you want as context

```bash
swc 'src/**/*.py' 'README.md'
```

### 3. Trim noisy areas if needed

```bash
swc --ignore 'tests/fixtures/**' 'src/**/*.py'
```

### 4. Force a normally ignored subtree if needed

```bash
swc --force generated 'generated/**/*.ts'
```

### 5. Save a standing query

```bash
swc --ignore subsets 'src/**/*.py' 'README.md' --save
```

Then later:

```bash
swc
```

will automatically reuse those saved defaults unless you pass `--no-load`.

## Example commands

```bash
swc
swc '*.md'
swc 'src/**/*.py' 'README.md'
swc --ignore subsets 'src/**/*.py'
swc --ignore 'build/' --ignore '*.log' 'src/**/*.py'
swc --force generated 'generated/**/*.ts'
swc --no-load 'src/**/*.py'
swc 'src/**/*.py' --save
```

## Summary

- run `swc` from the project root
- `.gitignore` controls baseline traversal
- `<file_tree>` is always printed
- `<file_contents>` is opt-in
- use positional patterns to include file contents
- use `--ignore` to remove things from output
- use `--force` to traverse ignored paths
- use `.swc_args` and `--save` for standing queries
- single-quote any pattern containing wildcard characters
