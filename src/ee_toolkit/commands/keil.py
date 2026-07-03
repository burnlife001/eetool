"""Keil MDK project commands.

Generates PowerShell build/flash/both scripts from templates stored as
package data, and bootstraps a new Keil project layout.
"""

from __future__ import annotations

import argparse
import re
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


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register ``ee keil ...`` subcommands."""
    parser = subparsers.add_parser("keil", help="Keil MDK tools")
    sub = parser.add_subparsers(dest="keil_command", required=True)

    init = sub.add_parser("init", help="Initialize a Keil project layout")
    init.add_argument(
        "dir",
        nargs="?",
        default=".",
        help="Project directory containing a .uvprojx file (default: cwd)",
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


def render_template(template_name: str, project_path: str | Path) -> Path:
    """Render a PowerShell template next to the .uvprojx file.

    Returns the path of the generated script.
    """
    uv4 = find_uv4()
    project = Path(project_path)
    project_name = project.stem
    output_name = parse_output_name(project)

    template = files("ee_toolkit.data.keil").joinpath(template_name)
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
    """Dispatch the ``ee keil`` subcommand."""
    if args.keil_command == "init":
        return init_project(args.dir)
    if args.keil_command in TEMPLATES:
        render_template(TEMPLATES[args.keil_command], args.project)
        return 0
    return 1


# Reserved for future use: expose the OutputName tag regex for callers that
# want to grep uvprojx files without parsing XML.
OUTPUT_NAME_RE = re.compile(r"<OutputName>\s*([^<]+?)\s*</OutputName>")
