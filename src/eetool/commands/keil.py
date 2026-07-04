"""Keil MDK project commands.

Generates PowerShell build/flash/both scripts from templates stored as
package data, and bootstraps a new Keil project layout.

Two entry points:
- :func:`init_project` — render the three ``__*.ps1`` templates next to the
  .uvprojx file (lightweight, no project analysis).
- :func:`setup_project` — run the full 8-step keil-init pipeline: parse
  .uvprojx, detect vendor/RTOS zones, write ``.claude/CLAUDE.md``,
  install a restricted-zones pre-commit hook, and wire it into
  ``.git/hooks/pre-commit``.
"""

from __future__ import annotations

import argparse
import re
import shutil
import xml.etree.ElementTree as ET
from importlib.resources import files
from pathlib import Path

# PowerShell templates shipped with the package (see data/keil/*.ps1).
TEMPLATES = {
    "gen-build": "__build.ps1",
    "gen-flash": "__download.ps1",
    "gen-build-flash": "__build_and_download.ps1",
}

# Default Keil install locations searched for UV4.exe.
UV4_SEARCH_PATHS = [
    Path("C:/Keil_v5/UV4/UV4.exe"),
    Path("D:/Keil_v5/UV4/UV4.exe"),
]

#: Vendor / toolchain top-level directories that count as restricted-zone A.
#: Detection is exact-name match at depth 0 or 1.
VENDOR_DIRS = ("Device", "Drivers", "Library", "Libraries", "Middleware", "ThirdParty")

#: Keil build artifacts that should never be committed.
BUILD_ARTIFACT_PATTERNS = ("Objects", "Listings")

#: Recognised RTOS / state-machine framework directory names. Each match
#: promotes the entire directory to restricted-zone B (framework core).
FRAMEWORK_DIRS = {
    "FreeRTOS": "RTOS kernel — tasks / queues / scheduler core",
    "RT-Thread": "RTOS kernel — threads / IPC / scheduler core",
    "QP": "QP-nano/QP framework — event engine + state machines",
    "CMSIS": "CMSIS-RTOS abstraction — RTX / osWait wrappers",
}

#: Keil IDE project files that must never be hand-edited.
KEIL_PROJECT_FILES = (".uvprojx", ".uvoptx", ".uvguix")


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register ``eetool keil ...`` subcommands."""
    parser = subparsers.add_parser("keil", help="Keil MDK tools")
    sub = parser.add_subparsers(dest="keil_command", required=True)

    init = sub.add_parser(
        "init",
        help="Render __build.ps1 / __download.ps1 / __build_and_download.ps1",
    )
    init.add_argument(
        "dir",
        nargs="?",
        default=".",
        help="Project directory containing a .uvprojx file (default: cwd)",
    )

    setup = sub.add_parser(
        "setup",
        help=(
            "Full keil-init pipeline: build scripts + .claude/CLAUDE.md + "
            "pre-commit hook + settings.json + install to .git/hooks"
        ),
    )
    setup.add_argument(
        "dir",
        nargs="?",
        default=".",
        help="Project directory containing a .uvprojx file (default: cwd)",
    )
    setup.add_argument(
        "--framework",
        action="append",
        default=None,
        metavar="NAME",
        help=(
            "Mark a directory as restricted-zone B (framework core). "
            "Repeatable, e.g. --framework FreeRTOS --framework QP"
        ),
    )
    setup.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without touching any files",
    )

    for name, help_text in (
        ("gen-build", "Generate __build.ps1 for a Keil project"),
        ("gen-flash", "Generate __download.ps1 for a Keil project"),
        ("gen-build-flash", "Generate __build_and_download.ps1 for a Keil project"),
    ):
        gen = sub.add_parser(name, help=help_text)
        gen.add_argument("--project", required=True, help="Path to .uvprojx file")


def find_uv4() -> Path:
    """Return the first existing UV4.exe path, or raise FileNotFoundError."""
    for path in UV4_SEARCH_PATHS:
        if path.exists():
            return path
    raise FileNotFoundError(
        "UV4.exe not found. Checked: " + ", ".join(str(p) for p in UV4_SEARCH_PATHS)
    )


def parse_output_name(uvprojx_path: Path) -> str:
    """Extract <OutputName> from .uvprojx; fall back to the project stem."""
    try:
        root = ET.parse(uvprojx_path).getroot()
    except ET.ParseError:
        return uvprojx_path.stem
    # Keil uvprojx uses XML namespaces; the OutputName tag sits under TargetAds.
    for elem in root.iter():
        if elem.tag.endswith("OutputName") and elem.text:
            return elem.text.strip()
    return uvprojx_path.stem


def parse_uvprojx_meta(uvprojx_path: Path) -> dict:
    """Extract chip + toolchain metadata from a .uvprojx file.

    Returns a dict with keys:
      - device (str): <Device> tag, e.g. "STM32F103C8".
      - pcc_used (str): <pCCUsed> tag, e.g. "ARMCC 5.06 update 7 (build 960)".
      - output_name (str): <OutputName> tag, or the project stem.

    Missing / unparseable fields are returned as empty strings.
    """
    meta = {"device": "", "pcc_used": "", "output_name": uvprojx_path.stem}
    try:
        root = ET.parse(uvprojx_path).getroot()
    except ET.ParseError:
        return meta

    for elem in root.iter():
        tag = elem.tag.split("}")[-1]  # strip namespace
        text = (elem.text or "").strip()
        if tag == "Device" and not meta["device"]:
            meta["device"] = text
        elif tag == "pCCUsed" and not meta["pcc_used"]:
            meta["pcc_used"] = text
        elif tag == "OutputName" and text:
            meta["output_name"] = text
    return meta


def detect_vendor_dirs(project_dir: Path) -> list[str]:
    """Return existing vendor / toolchain top-level directory names.

    Looks for :data:`VENDOR_DIRS` entries at the project root and one level
    deep. Returns directory names relative to ``project_dir`` (e.g.
    ``"Drivers/"`` or ``"foo/Device/"``).
    """
    found: list[str] = []
    for entry in VENDOR_DIRS:
        if (project_dir / entry).is_dir():
            found.append(entry + "/")
            continue
        # depth-1: subprojects may nest vendor dirs under e.g. "bsp/Drivers"
        for child in project_dir.iterdir():
            if not child.is_dir():
                continue
            if (child / entry).is_dir():
                found.append(f"{child.name}/{entry}/")
    return sorted(set(found))


def detect_framework_dirs(project_dir: Path, extra: list[str] | None = None) -> dict[str, str]:
    """Detect RTOS / framework core directories and their rationale.

    Returns ``{relative_dir: description}``. Built-in :data:`FRAMEWORK_DIRS`
    entries are detected by exact-name match at any depth (capped at 3 to
    keep the scan bounded). Names listed in ``extra`` (via ``--framework``)
    are registered verbatim — even if the directory does not yet exist on
    disk — so users can pre-declare restricted zones before pulling the
    framework code in.
    """
    detected: dict[str, str] = {}
    # First: scan for built-in framework names that actually exist.
    for name in FRAMEWORK_DIRS:
        description = FRAMEWORK_DIRS[name]
        for path in project_dir.glob(f"**/{name}"):
            if not path.is_dir():
                continue
            rel = path.relative_to(project_dir)
            if len(rel.parts) > 3:
                continue
            detected[str(rel.as_posix()) + "/"] = description
    # Then: user-declared names (--framework Foo Bar Baz).
    for name in extra or []:
        if name in FRAMEWORK_DIRS:
            key = name + "/"
            if key not in detected:
                detected[key] = FRAMEWORK_DIRS[name]
        else:
            detected[name + "/"] = "Framework core (user-specified)"
    return detected


def detect_startup_files(project_dir: Path) -> list[str]:
    """Return project-relative paths of any ``startup_*.s`` files."""
    return sorted(
        str(p.relative_to(project_dir).as_posix())
        for p in project_dir.rglob("startup_*.s")
    )


def build_restricted_regex(
    vendor_dirs: list[str],
    framework_dirs: dict[str, str],
    startup_files: list[str],
) -> str:
    """Assemble a single ``grep -E`` regex matching all restricted-zone paths.

    Includes:
      - vendor HAL dirs (Device/, Drivers/, …)
      - framework core dirs (FreeRTOS/, QP/, …)
      - startup_*.s files (matched by basename glob)
      - Keil project files (*.uvprojx, *.uvoptx, *.uvguix)
      - build artifacts (Objects/, Listings/) — usually .gitignored but a
        useful belt-and-braces guard.
    """
    patterns: list[str] = []
    for d in vendor_dirs:
        patterns.append(re.escape(d))
    for d in framework_dirs:
        patterns.append(re.escape(d))
    patterns.append(r".*startup_.*\.s$")
    for ext in KEIL_PROJECT_FILES:
        patterns.append(re.escape(ext) + r"$")
    for d in BUILD_ARTIFACT_PATTERNS:
        patterns.append(re.escape(d) + r"/")
    patterns.sort(key=len, reverse=True)
    return "^(" + "|".join(patterns) + ")"


# ---------------------------------------------------------------------------
# File templates
# ---------------------------------------------------------------------------


CLAUDE_MD_TEMPLATE = """\
# CLAUDE.md — {project_name}

> Firmware for **{device}** ({toolchain}).
> Built with Keil MDK v5. {framework_note}

## 🚫 禁区 A — 供应商/工具链（禁止修改）

| 路径 | 原因 |
|------|------|
{vendor_rows}

## 🚫 禁区 B — 框架核心（禁止修改）{framework_section_header}

| 文件 | 作用 |
|------|------|
{framework_rows}

## ✅ 允许修改范围

| 目录 | 说明 |
|------|------|
{app_rows}

## 编译与烧录

```powershell
pwsh ./{uvprojx_dir}/__build.ps1
pwsh ./{uvprojx_dir}/__download.ps1
pwsh ./{uvprojx_dir}/__build_and_download.ps1
```

## 记忆要点

- RAM/Flash 限制见 `__build.log` 末尾
- 不要绕过 `.git/hooks/pre-commit`（同步源在 `.claude/hooks/pre-commit`）
"""


PRE_COMMIT_TEMPLATE = """\
#!/bin/bash
# pre-commit — restricted-zones enforcer for {project_name}
# Source of truth: .claude/hooks/pre-commit
# Sync command:    cp .claude/hooks/pre-commit .git/hooks/pre-commit
# Do NOT edit .git/hooks/pre-commit directly — your changes will be lost.

set -euo pipefail

# Restricted-zones regex. Generated by `eetool keil setup`; edit and re-run
# that command if your project structure changes.
RESTRICTED='{restricted_regex}'

STAGED_COUNT=$(git diff --cached --name-only --diff-filter=AM -z | wc -c)
if [ "$STAGED_COUNT" -eq 0 ]; then exit 0; fi

BLOCKED=$(git diff --cached --name-only --diff-filter=AM -z | grep -z -E "$RESTRICTED" | tr '\\0' '\\n' || true)

if [ -n "$BLOCKED" ]; then
  echo "========================================="
  echo "  BLOCKED — 以下文件在禁区内，禁止修改"
  echo "========================================="
  echo "$BLOCKED"
  echo ""
  echo "禁区包括: 供应商 HAL 目录 | Keil 工程配置 | 启动文件 | 框架核心"
  echo "如需修改禁区文件 → 创建 issue 由人工审批。禁止 agent 自行绕过。"
  exit 1
fi

exit 0
"""


SETTINGS_JSON = """\
{
  "hooks": {
    "pre-commit": "bash .claude/hooks/pre-commit"
  }
}
"""


def _detect_application_dirs(project_dir: Path, restricted: set[str]) -> list[tuple[str, str]]:
    """List project-root directories that are NOT in any restricted zone.

    Returns ``[(name, role_guess)]``; the role guess is a hint that the
    user is expected to edit in the rendered CLAUDE.md.
    """
    ROLE_HINTS = {
        "src": "Application source",
        "app": "Application code",
        "bsp": "Board support package (project-specific)",
        "user": "User / application modules",
        "main": "Main program entry",
    }
    apps: list[tuple[str, str]] = []
    for child in sorted(project_dir.iterdir()):
        if not child.is_dir():
            continue
        name = child.name + "/"
        if name in restricted or child.name in {".git", ".claude"}:
            continue
        role = ROLE_HINTS.get(child.name, "Application module")
        apps.append((name, role))
    return apps


def render_claude_md(
    project_name: str,
    device: str,
    toolchain: str,
    vendor_dirs: list[str],
    framework_dirs: dict[str, str],
    app_dirs: list[tuple[str, str]],
    uvprojx_dir: str,
) -> str:
    """Render the .claude/CLAUDE.md body."""
    if framework_dirs:
        framework_section_header = ""
        framework_rows = "\n".join(
            f"| `{d}` | {desc} |" for d, desc in sorted(framework_dirs.items())
        )
        framework_note = "集成 RTOS/状态机框架。"
    else:
        framework_section_header = " _(本项目无框架核心)_"
        framework_rows = "| _(无)_ | _/_ |"
        framework_note = "裸机（Bare-metal）。"

    vendor_rows = "\n".join(
        f"| `{d}` | 供应商 HAL/工具链目录 |" for d in vendor_dirs
    ) or "| _(无)_ | _/_ |"

    app_rows = "\n".join(f"| `{d}` | {role} |" for d, role in app_dirs) or "| _(无)_ | _/_ |"

    return CLAUDE_MD_TEMPLATE.format(
        project_name=project_name,
        device=device or "(未检测到 <Device>)",
        toolchain=toolchain or "(未检测到 <pCCUsed>)",
        framework_note=framework_note,
        vendor_rows=vendor_rows,
        framework_section_header=framework_section_header,
        framework_rows=framework_rows,
        app_rows=app_rows,
        uvprojx_dir=uvprojx_dir,
    )


def render_pre_commit(project_name: str, restricted_regex: str) -> str:
    return PRE_COMMIT_TEMPLATE.format(
        project_name=project_name,
        restricted_regex=restricted_regex,
    )


# ---------------------------------------------------------------------------
# Setup pipeline
# ---------------------------------------------------------------------------


def setup_project(
    directory: str,
    framework: list[str] | None = None,
    dry_run: bool = False,
) -> int:
    """Run the full keil-init pipeline against ``directory``.

    Steps:
      1. Locate the .uvprojx (single match required).
      2. Parse chip/toolchain metadata.
      3. Detect vendor HAL dirs + RTOS/framework dirs + startup_*.s.
      4. Generate the three PowerShell templates next to the .uvprojx.
      5. Write ``.claude/CLAUDE.md`` with restricted-zone tables.
      6. Write ``.claude/hooks/pre-commit`` with the RESTRICTED regex.
      7. Write ``.claude/settings.json``.
      8. Install the hook: copy ``.claude/hooks/pre-commit`` → ``.git/hooks/pre-commit``.

    With ``dry_run=True`` prints the planned writes and exits 0 without
    touching the filesystem (useful for review before commit).
    """
    target = Path(directory).resolve()
    uvprojx = sorted(target.glob("*.uvprojx"))
    if not uvprojx:
        print(f"No .uvprojx found in {directory}")
        return 1
    if len(uvprojx) > 1:
        print(f"Multiple .uvprojx files found in {directory}; expected exactly one.")
        return 1

    uvprojx_path = uvprojx[0]
    meta = parse_uvprojx_meta(uvprojx_path)

    vendor_dirs = detect_vendor_dirs(target)
    framework_dirs = detect_framework_dirs(target, framework)
    startup_files = detect_startup_files(target)
    restricted_regex = build_restricted_regex(vendor_dirs, framework_dirs, startup_files)
    restricted_set = set(vendor_dirs) | set(framework_dirs.keys())
    app_dirs = _detect_application_dirs(target, restricted_set)

    project_name = uvprojx_path.stem
    uvprojx_dir = "."

    claude_dir = target / ".claude"
    hooks_dir = claude_dir / "hooks"
    claude_md_path = claude_dir / "CLAUDE.md"
    hook_src_path = hooks_dir / "pre-commit"
    settings_path = claude_dir / "settings.json"
    git_hook_path = target / ".git" / "hooks" / "pre-commit"

    claude_md_body = render_claude_md(
        project_name=project_name,
        device=meta["device"],
        toolchain=meta["pcc_used"],
        vendor_dirs=vendor_dirs,
        framework_dirs=framework_dirs,
        app_dirs=app_dirs,
        uvprojx_dir=uvprojx_dir,
    )
    hook_body = render_pre_commit(project_name, restricted_regex)

    planned = [
        ("__build.ps1 / __download.ps1 / __build_and_download.ps1", uvprojx_path.parent),
        (".claude/CLAUDE.md", claude_md_path),
        (".claude/hooks/pre-commit", hook_src_path),
        (".claude/settings.json", settings_path),
        (".git/hooks/pre-commit (installed)", git_hook_path),
    ]
    if dry_run:
        print("Dry run — the following files would be written:")
        for label, path in planned:
            print(f"  • {label}  →  {path}")
        print("\nRestricted-zones regex:")
        print(f"  {restricted_regex}")
        print("\nDetected:")
        print(f"  device:    {meta['device'] or '(unknown)'}")
        print(f"  toolchain: {meta['pcc_used'] or '(unknown)'}")
        print(f"  output:    {meta['output_name']}")
        print(f"  vendor:    {vendor_dirs or '(none)'}")
        print(f"  framework: {list(framework_dirs.keys()) or '(none)'}")
        print(f"  app:       {[d for d, _ in app_dirs] or '(none)'}")
        return 0

    # Step 4: render PowerShell templates
    for template_name in TEMPLATES.values():
        render_template(template_name, str(uvprojx_path))

    # Step 5-7: write Claude Code scaffolding
    hooks_dir.mkdir(parents=True, exist_ok=True)
    claude_md_path.write_text(claude_md_body, encoding="utf-8", newline="\n")
    hook_src_path.write_text(hook_body, encoding="utf-8", newline="\n")
    if not hook_src_path.read_bytes().endswith(b"\n"):
        hook_src_path.write_bytes(hook_src_path.read_bytes() + b"\n")
    settings_path.write_text(SETTINGS_JSON, encoding="utf-8", newline="\n")

    # Step 8: install hook
    if git_hook_path.parent.is_dir():
        shutil.copy2(hook_src_path, git_hook_path)
        try:
            git_hook_path.chmod(0o755)
        except (OSError, NotImplementedError):
            pass  # Windows: git bash invocation handles executable bit
        print(f"[ok] installed hook → {git_hook_path}")
    else:
        print(
            f"[skip] {git_hook_path.parent} does not exist; "
            "run `git init` first or copy .claude/hooks/pre-commit manually."
        )

    print(f"[ok] setup complete for {project_name}")
    print(f"     device:    {meta['device'] or '(unknown)'}")
    print(f"     toolchain: {meta['pcc_used'] or '(unknown)'}")
    print(f"     restricted-zones: {len(vendor_dirs) + len(framework_dirs)} paths")
    print()
    print("Next steps:")
    print("  1. Review .claude/CLAUDE.md — edit the application-dir table.")
    print("  2. Verify the hook blocks restricted edits:")
    print("       echo '// test' >> Device/foo.h")
    print("       git add Device/foo.h && git commit -m x")
    print("     Expected: commit rejected.")
    print("  3. git add .claude/ __build.ps1 __download.ps1 __build_and_download.ps1")
    print("  4. git commit -m 'init: keil project scaffolding'")
    return 0


# ---------------------------------------------------------------------------
# Legacy init (unchanged behaviour) + template rendering
# ---------------------------------------------------------------------------


def render_template(template_name: str, project_path: str | Path) -> Path:
    """Render a PowerShell template next to the .uvprojx file.

    Returns the path of the generated script.
    """
    uv4 = find_uv4()
    project = Path(project_path)
    project_name = project.stem
    output_name = parse_output_name(project)

    template = files("eetool.data.keil").joinpath(template_name)
    text = template.read_text(encoding="utf-8")
    text = text.replace("{{UV4_PATH}}", str(uv4))
    text = text.replace("{{PROJECT_NAME}}", project_name)
    text = text.replace("{{OUTPUT_NAME}}", output_name)

    out_path = project.parent / template_name
    out_path.write_text(text, encoding="utf-8", newline="\n")
    return out_path


def init_project(directory: str) -> int:
    """Bootstrap a Keil project: render all three PowerShell templates."""
    target = Path(directory)
    uvprojx = sorted(target.glob("*.uvprojx"))
    if not uvprojx:
        print(f"No .uvprojx found in {directory}")
        return 1
    for template_name in TEMPLATES.values():
        render_template(template_name, str(uvprojx[0]))
    return 0


def run(args: argparse.Namespace) -> int:
    """Dispatch the ``eetool keil`` subcommand."""
    if args.keil_command == "init":
        return init_project(args.dir)
    if args.keil_command == "setup":
        return setup_project(args.dir, framework=args.framework, dry_run=args.dry_run)
    if args.keil_command in TEMPLATES:
        render_template(TEMPLATES[args.keil_command], args.project)
        return 0
    return 1


# Reserved for future use: expose the OutputName tag regex for callers that
# want to grep uvprojx files without parsing XML.
OUTPUT_NAME_RE = re.compile(r"<OutputName>\s*([^<]+?)\s*</OutputName>")