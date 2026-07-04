"""Tests for eetool.commands.keil."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from eetool.commands.keil import (
    FRAMEWORK_DIRS,
    add_subparser,
    build_restricted_regex,
    detect_framework_dirs,
    detect_startup_files,
    detect_vendor_dirs,
    find_uv4,
    init_project,
    parse_output_name,
    parse_uvprojx_meta,
    render_claude_md,
    render_pre_commit,
    render_template,
    run,
    setup_project,
)


# ---------- find_uv4 ----------


def test_find_uv4_returns_first_existing(monkeypatch, tmp_path):
    fake = tmp_path / "UV4.exe"
    fake.write_text("")
    missing = tmp_path / "missing.exe"
    monkeypatch.setattr(
        "eetool.commands.keil.UV4_SEARCH_PATHS", [missing, fake]
    )
    assert find_uv4() == fake


def test_find_uv4_raises_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "eetool.commands.keil.UV4_SEARCH_PATHS",
        [tmp_path / "a.exe", tmp_path / "b.exe"],
    )
    with pytest.raises(FileNotFoundError, match="UV4.exe"):
        find_uv4()


# ---------- parse_output_name ----------


def test_parse_output_name_from_uvprojx(tmp_path):
    uvprojx = tmp_path / "proj.uvprojx"
    uvprojx.write_text(
        '<?xml version="1.0"?><Project>'
        "<OutputName>my_fw</OutputName>"
        "</Project>",
        encoding="utf-8",
    )
    assert parse_output_name(uvprojx) == "my_fw"


def test_parse_output_name_falls_back_to_stem_on_broken_xml(tmp_path):
    uvprojx = tmp_path / "broken.uvprojx"
    uvprojx.write_text("<not-xml", encoding="utf-8")
    assert parse_output_name(uvprojx) == "broken"


def test_parse_output_name_falls_back_when_tag_missing(tmp_path):
    uvprojx = tmp_path / "no_tag.uvprojx"
    uvprojx.write_text("<Project></Project>", encoding="utf-8")
    assert parse_output_name(uvprojx) == "no_tag"


# ---------- render_template ----------


def test_render_template_replaces_placeholders(tmp_path):
    uvprojx = tmp_path / "foo.uvprojx"
    uvprojx.write_text(
        '<?xml version="1.0"?><Project><OutputName>foo_axf</OutputName></Project>',
        encoding="utf-8",
    )
    with patch(
        "eetool.commands.keil.find_uv4",
        return_value=Path("C:/Keil_v5/UV4/UV4.exe"),
    ):
        out = render_template("__build.ps1", str(uvprojx))
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    # Project stem from .uvprojx filename, output name from <OutputName> tag.
    assert 'foo.uvprojx' in text  # template literal .uvprojx after substitution
    assert "foo_axf.axf" in text  # OutputName from uvprojx
    assert "C:\\Keil_v5\\UV4\\UV4.exe" in text
    # No placeholder should remain
    for ph in ("{{UV4_PATH}}", "{{PROJECT_NAME}}", "{{OUTPUT_NAME}}"):
        assert ph not in text


def test_render_template_uses_stem_when_no_output_name(tmp_path):
    uvprojx = tmp_path / "bare.uvprojx"
    uvprojx.write_text("<Project></Project>", encoding="utf-8")
    with patch(
        "eetool.commands.keil.find_uv4",
        return_value=Path("C:/Keil_v5/UV4/UV4.exe"),
    ):
        out = render_template("__download.ps1", str(uvprojx))
    text = out.read_text(encoding="utf-8")
    # When <OutputName> is missing the stem is reused.
    assert 'bare.uvprojx' in text
    assert "{{PROJECT_NAME}}" not in text
    assert "{{OUTPUT_NAME}}" not in text


# ---------- init_project ----------


def test_init_project_renders_all_three(tmp_path):
    uvprojx = tmp_path / "initme.uvprojx"
    uvprojx.write_text(
        "<Project><OutputName>app</OutputName></Project>", encoding="utf-8"
    )
    with patch(
        "eetool.commands.keil.find_uv4",
        return_value=Path("C:/Keil_v5/UV4/UV4.exe"),
    ):
        rc = init_project(str(tmp_path))
    assert rc == 0
    for fname in ("__build.ps1", "__download.ps1", "__build_and_download.ps1"):
        assert (tmp_path / fname).exists()


def test_init_project_no_uvprojx(tmp_path, capsys):
    rc = init_project(str(tmp_path))
    assert rc == 1
    assert "No .uvprojx" in capsys.readouterr().out


# ---------- run dispatcher ----------


def test_run_dispatches_gen_build():
    args = argparse.Namespace(
        keil_command="gen-build", project="C:/fake/proj.uvprojx", dir=None
    )
    with patch("eetool.commands.keil.render_template") as mock_render:
        assert run(args) == 0
        mock_render.assert_called_once_with("__build.ps1", "C:/fake/proj.uvprojx")


def test_run_dispatches_gen_flash():
    args = argparse.Namespace(
        keil_command="gen-flash", project="C:/fake/proj.uvprojx", dir=None
    )
    with patch("eetool.commands.keil.render_template") as mock_render:
        assert run(args) == 0
        mock_render.assert_called_once_with("__download.ps1", "C:/fake/proj.uvprojx")


def test_run_dispatches_gen_build_flash():
    args = argparse.Namespace(
        keil_command="gen-build-flash", project="C:/fake/proj.uvprojx", dir=None
    )
    with patch("eetool.commands.keil.render_template") as mock_render:
        assert run(args) == 0
        mock_render.assert_called_once_with(
            "__build_and_download.ps1", "C:/fake/proj.uvprojx"
        )


def test_run_dispatches_init():
    args = argparse.Namespace(keil_command="init", project=None, dir="/tmp/x")
    with patch("eetool.commands.keil.init_project", return_value=0) as mock_init:
        assert run(args) == 0
        mock_init.assert_called_once_with("/tmp/x")


def test_run_unknown_returns_1():
    args = argparse.Namespace(keil_command="bogus", project=None, dir=None)
    assert run(args) == 1


# ---------- add_subparser registration ----------


def test_add_subparser_registers_keil():
    from argparse import ArgumentParser

    parser = ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    add_subparser(sub)
    # argparse: invoke the keil subcommand to ensure it parses cleanly.
    parsed = parser.parse_args(["keil", "gen-build", "--project", "p.uvprojx"])
    assert parsed.command == "keil"
    assert parsed.keil_command == "gen-build"
    assert parsed.project == "p.uvprojx"


# ---------- parse_uvprojx_meta ----------


SAMPLE_UVPROJX = """\
<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Targets>
    <Target>
      <TargetName>Target 1</TargetName>
      <ToolsetNumber>0x4</ToolsetNumber>
      <ToolsetName>ARM-MDK</ToolsetName>
      <pCCUsed>ARMCC 5.06 update 7 (build 960)</pCCUsed>
      <uAC6>1</uAC6>
      <TargetOption>
        <TargetCommonOption>
          <Device>STM32F103C8</Device>
          <Vendor>STMicroelectronics</Vendor>
          <Cpu>IRAM(0x20000000,0x5000) IRAM2(0x10000000,0x10000)</Cpu>
          <OutputName>my_fw</OutputName>
        </TargetCommonOption>
      </TargetOption>
    </Target>
  </Targets>
</Project>
"""


def test_parse_uvprojx_meta_extracts_chip_and_toolchain(tmp_path):
    uvprojx = tmp_path / "p.uvprojx"
    uvprojx.write_text(SAMPLE_UVPROJX, encoding="utf-8")
    meta = parse_uvprojx_meta(uvprojx)
    assert meta["device"] == "STM32F103C8"
    assert "ARMCC 5.06" in meta["pcc_used"]
    assert meta["output_name"] == "my_fw"


def test_parse_uvprojx_meta_falls_back_on_broken_xml(tmp_path):
    uvprojx = tmp_path / "broken.uvprojx"
    uvprojx.write_text("<not-xml", encoding="utf-8")
    meta = parse_uvprojx_meta(uvprojx)
    assert meta == {"device": "", "pcc_used": "", "output_name": "broken"}


def test_parse_uvprojx_meta_returns_stem_when_tags_missing(tmp_path):
    uvprojx = tmp_path / "bare.uvprojx"
    uvprojx.write_text("<Project></Project>", encoding="utf-8")
    meta = parse_uvprojx_meta(uvprojx)
    assert meta["device"] == ""
    assert meta["pcc_used"] == ""
    assert meta["output_name"] == "bare"


# ---------- detect_vendor_dirs ----------


def test_detect_vendor_dirs_finds_top_level(tmp_path):
    (tmp_path / "Device").mkdir()
    (tmp_path / "Drivers").mkdir()
    (tmp_path / "src").mkdir()
    found = detect_vendor_dirs(tmp_path)
    assert "Device/" in found
    assert "Drivers/" in found
    assert "src/" not in found


def test_detect_vendor_dirs_finds_nested(tmp_path):
    (tmp_path / "bsp").mkdir()
    (tmp_path / "bsp" / "Drivers").mkdir()
    found = detect_vendor_dirs(tmp_path)
    assert "bsp/Drivers/" in found


def test_detect_vendor_dirs_empty_when_no_vendor_dirs(tmp_path):
    (tmp_path / "src").mkdir()
    assert detect_vendor_dirs(tmp_path) == []


# ---------- detect_framework_dirs ----------


def test_detect_framework_dirs_finds_known(tmp_path):
    (tmp_path / "FreeRTOS").mkdir()
    (tmp_path / "src").mkdir()
    found = detect_framework_dirs(tmp_path)
    assert "FreeRTOS/" in found
    assert "RTOS kernel" in found["FreeRTOS/"]


def test_detect_framework_dirs_includes_user_extra(tmp_path):
    found = detect_framework_dirs(tmp_path, extra=["my_qp_port"])
    assert "my_qp_port/" in found
    assert "user-specified" in found["my_qp_port/"]


def test_detect_framework_dirs_bounds_depth(tmp_path):
    deep = tmp_path / "a" / "b" / "c" / "d" / "FreeRTOS"
    deep.mkdir(parents=True)
    # depth 4 from tmp_path is too deep; should be skipped
    found = detect_framework_dirs(tmp_path)
    assert "a/b/c/d/FreeRTOS/" not in found


# ---------- detect_startup_files ----------


def test_detect_startup_files_finds_match(tmp_path):
    (tmp_path / "Device").mkdir()
    (tmp_path / "Device" / "startup_stm32f103.s").write_text("")
    (tmp_path / "startup_extra.s").write_text("")
    files = detect_startup_files(tmp_path)
    assert "Device/startup_stm32f103.s" in files
    assert "startup_extra.s" in files


# ---------- build_restricted_regex ----------


def test_build_restricted_regex_includes_all_zones():
    rx = build_restricted_regex(
        vendor_dirs=["Device/", "Drivers/"],
        framework_dirs={"FreeRTOS/": "rtos"},
        startup_files=["Device/startup_stm32.s"],
    )
    assert rx.startswith("^(")
    assert "Device/" in rx
    assert "Drivers/" in rx
    assert "FreeRTOS/" in rx
    assert "startup_" in rx
    assert "uvprojx" in rx
    assert "Objects/" in rx
    assert "Listings/" in rx


# ---------- render_claude_md ----------


def test_render_claude_md_lists_vendor_and_app_dirs():
    body = render_claude_md(
        project_name="my_fw",
        device="STM32F103C8",
        toolchain="ARMCC 5.06",
        vendor_dirs=["Device/", "Drivers/"],
        framework_dirs={"FreeRTOS/": "RTOS kernel"},
        app_dirs=[("src/", "Application source")],
        uvprojx_dir=".",
    )
    assert "my_fw" in body
    assert "STM32F103C8" in body
    assert "`Device/`" in body
    assert "`FreeRTOS/`" in body
    assert "`src/`" in body
    assert "RTOS kernel" in body


def test_render_claude_md_handles_no_framework():
    body = render_claude_md(
        project_name="bare",
        device="nrf52",
        toolchain="ARMCC",
        vendor_dirs=[],
        framework_dirs={},
        app_dirs=[],
        uvprojx_dir=".",
    )
    assert "本项目无框架核心" in body
    assert "裸机" in body


# ---------- render_pre_commit ----------


def test_render_pre_commit_embeds_regex():
    body = render_pre_commit("my_fw", r"^(Device/|.*\.uvprojx$)")
    assert "my_fw" in body
    assert "RESTRICTED='^(Device/|.*\\.uvprojx$)'" in body
    assert "exit 1" in body
    assert "BLOCKED" in body


# ---------- setup_project: dry-run ----------


def test_setup_project_dry_run_writes_nothing(tmp_path, capsys):
    (tmp_path / "p.uvprojx").write_text(SAMPLE_UVPROJX, encoding="utf-8")
    with patch("eetool.commands.keil.find_uv4", return_value=Path("C:/fake/UV4.exe")):
        rc = setup_project(str(tmp_path), dry_run=True)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Dry run" in out
    assert "STM32F103C8" in out
    # nothing written
    assert not (tmp_path / ".claude").exists()
    assert not (tmp_path / "__build.ps1").exists()


def test_setup_project_dry_run_with_framework(tmp_path, capsys):
    (tmp_path / "p.uvprojx").write_text(SAMPLE_UVPROJX, encoding="utf-8")
    (tmp_path / "FreeRTOS").mkdir()
    with patch("eetool.commands.keil.find_uv4", return_value=Path("C:/fake/UV4.exe")):
        rc = setup_project(str(tmp_path), framework=["FreeRTOS"], dry_run=True)
    assert rc == 0
    out = capsys.readouterr().out
    assert "FreeRTOS/" in out


# ---------- setup_project: full pipeline ----------


@pytest.fixture
def fake_keil_project(tmp_path):
    """Build a realistic project layout in tmp_path and return the path."""
    (tmp_path / "p.uvprojx").write_text(SAMPLE_UVPROJX, encoding="utf-8")
    (tmp_path / "Device").mkdir()
    (tmp_path / "Device" / "stm32f1xx.h").write_text("// vendor")
    (tmp_path / "Device" / "startup_stm32f103.s").write_text("// startup")
    (tmp_path / "Drivers").mkdir()
    (tmp_path / "Drivers" / "stm32f1xx_hal.c").write_text("// hal")
    (tmp_path / "FreeRTOS").mkdir()
    (tmp_path / "FreeRTOS" / "tasks.c").write_text("// rtos")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.c").write_text("// app")
    (tmp_path / "src" / "app.c").write_text("// app")
    return tmp_path


def test_setup_project_full_pipeline_writes_all_files(fake_keil_project, tmp_path):
    proj = fake_keil_project
    (proj / ".git" / "hooks").mkdir(parents=True)
    with patch("eetool.commands.keil.find_uv4", return_value=Path("C:/fake/UV4.exe")):
        rc = setup_project(str(proj), framework=["FreeRTOS"])
    assert rc == 0

    # Step 4: PowerShell templates
    for fname in ("__build.ps1", "__download.ps1", "__build_and_download.ps1"):
        assert (proj / fname).exists()

    # Step 5: CLAUDE.md
    claude_md = (proj / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "STM32F103C8" in claude_md
    assert "`Device/`" in claude_md
    assert "`FreeRTOS/`" in claude_md
    assert "`src/`" in claude_md

    # Step 6: pre-commit hook
    hook = (proj / ".claude" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert "RESTRICTED=" in hook
    assert "Device/" in hook
    assert "FreeRTOS/" in hook

    # Step 7: settings.json
    settings = (proj / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert '"pre-commit"' in settings

    # Step 8: hook installed
    git_hook = proj / ".git" / "hooks" / "pre-commit"
    assert git_hook.exists()
    assert git_hook.read_bytes() == (proj / ".claude" / "hooks" / "pre-commit").read_bytes()


def test_setup_project_skips_hook_install_when_no_git(tmp_path, capsys):
    """If .git/hooks is missing, the pipeline should warn and skip — not error."""
    (tmp_path / "p.uvprojx").write_text(SAMPLE_UVPROJX, encoding="utf-8")
    (tmp_path / "src").mkdir()
    with patch("eetool.commands.keil.find_uv4", return_value=Path("C:/fake/UV4.exe")):
        rc = setup_project(str(tmp_path))
    assert rc == 0
    out = capsys.readouterr().out
    assert "[skip]" in out
    # But the source hook in .claude/hooks/ is still written
    assert (tmp_path / ".claude" / "hooks" / "pre-commit").exists()


def test_setup_project_no_uvprojx(tmp_path, capsys):
    rc = setup_project(str(tmp_path))
    assert rc == 1
    assert "No .uvprojx" in capsys.readouterr().out


def test_setup_project_multiple_uvprojx_rejected(tmp_path, capsys):
    (tmp_path / "a.uvprojx").write_text("<Project></Project>", encoding="utf-8")
    (tmp_path / "b.uvprojx").write_text("<Project></Project>", encoding="utf-8")
    rc = setup_project(str(tmp_path))
    assert rc == 1
    assert "Multiple" in capsys.readouterr().out


def test_setup_project_run_dispatch():
    args = argparse.Namespace(
        keil_command="setup",
        dir="/tmp/x",
        framework=["FreeRTOS"],
        dry_run=True,
    )
    with patch("eetool.commands.keil.setup_project", return_value=0) as mock_setup:
        assert run(args) == 0
        mock_setup.assert_called_once_with("/tmp/x", framework=["FreeRTOS"], dry_run=True)


# ---------- add_subparser: setup registration ----------


def test_add_subparser_registers_setup():
    from argparse import ArgumentParser

    parser = ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    add_subparser(sub)
    parsed = parser.parse_args(["keil", "setup", "/tmp/x", "--framework", "FreeRTOS", "--dry-run"])
    assert parsed.keil_command == "setup"
    assert parsed.dir == "/tmp/x"
    assert parsed.framework == ["FreeRTOS"]
    assert parsed.dry_run is True
