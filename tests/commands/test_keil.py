"""Tests for ee_toolkit.commands.keil."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from ee_toolkit.commands.keil import (
    add_subparser,
    find_uv4,
    init_project,
    parse_output_name,
    render_template,
    run,
)


# ---------- find_uv4 ----------


def test_find_uv4_returns_first_existing(monkeypatch, tmp_path):
    fake = tmp_path / "UV4.exe"
    fake.write_text("")
    missing = tmp_path / "missing.exe"
    monkeypatch.setattr(
        "ee_toolkit.commands.keil.UV4_SEARCH_PATHS", [missing, fake]
    )
    assert find_uv4() == fake


def test_find_uv4_raises_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "ee_toolkit.commands.keil.UV4_SEARCH_PATHS",
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
        "ee_toolkit.commands.keil.find_uv4",
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
        "ee_toolkit.commands.keil.find_uv4",
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
        "ee_toolkit.commands.keil.find_uv4",
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
    with patch("ee_toolkit.commands.keil.render_template") as mock_render:
        assert run(args) == 0
        mock_render.assert_called_once_with("__build.ps1", "C:/fake/proj.uvprojx")


def test_run_dispatches_gen_flash():
    args = argparse.Namespace(
        keil_command="gen-flash", project="C:/fake/proj.uvprojx", dir=None
    )
    with patch("ee_toolkit.commands.keil.render_template") as mock_render:
        assert run(args) == 0
        mock_render.assert_called_once_with("__download.ps1", "C:/fake/proj.uvprojx")


def test_run_dispatches_gen_build_flash():
    args = argparse.Namespace(
        keil_command="gen-build-flash", project="C:/fake/proj.uvprojx", dir=None
    )
    with patch("ee_toolkit.commands.keil.render_template") as mock_render:
        assert run(args) == 0
        mock_render.assert_called_once_with(
            "__build_and_download.ps1", "C:/fake/proj.uvprojx"
        )


def test_run_dispatches_init():
    args = argparse.Namespace(keil_command="init", project=None, dir="/tmp/x")
    with patch("ee_toolkit.commands.keil.init_project", return_value=0) as mock_init:
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
