from __future__ import annotations

import ast
from pathlib import Path

from ksef2_cli.app import app


def test_top_level_help_registers_command_groups(runner) -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "invoices" in result.output
    assert "online" in result.output
    assert "permissions" in result.output


def test_all_registered_commands_render_help(runner) -> None:
    commands: list[tuple[str, str]] = []
    for path in sorted(Path("src/ksef2_cli/commands").glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "command"
                    and decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                    and isinstance(decorator.args[0].value, str)
                ):
                    commands.append((path.stem, decorator.args[0].value))

    checks: list[tuple[str, ...]] = [("--help",)]
    checks.extend((group, "--help") for group in sorted({group for group, _name in commands}))
    checks.extend((group, name, "--help") for group, name in commands)

    failures = []
    for args in checks:
        result = runner.invoke(app, list(args))
        if result.exit_code != 0:
            failures.append((args, result.output))

    assert len(commands) == 66
    assert not failures


def test_invalid_config_file_reports_bad_parameter(runner, tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("[auth]\npoll_interval = \"fast\"\n", encoding="utf-8")

    result = runner.invoke(app, ["--config", str(config_path), "config", "path"])

    assert result.exit_code == 2
    assert "Invalid value" in result.output
    assert "poll_interval" in result.output
