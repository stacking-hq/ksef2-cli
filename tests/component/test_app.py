import ast
from pathlib import Path

from ksef2_cli.app import app


def test_top_level_help_registers_command_groups(runner) -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "invoices" in result.output
    assert "online" in result.output
    assert "profile" in result.output
    assert "permissions" in result.output


def test_all_registered_commands_render_help(runner) -> None:
    commands: list[tuple[str, str]] = []
    for path in sorted(Path("src/ksef2_cli/commands").rglob("*.py")):
        if path.name == "__init__.py":
            continue
        relative_path = path.relative_to("src/ksef2_cli/commands")
        group = "invoices" if relative_path.parts[0] == "invoices" else path.stem
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                if _registered_command_name(node) is not None:
                    commands.append((group, _registered_command_name(node)))
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
                    commands.append((group, decorator.args[0].value))

    checks: list[tuple[str, ...]] = [("--help",)]
    checks.extend(
        (group, "--help") for group in sorted({group for group, _name in commands})
    )
    checks.extend((group, name, "--help") for group, name in commands)

    failures = []
    for args in checks:
        result = runner.invoke(app, list(args))
        if result.exit_code != 0:
            failures.append((args, result.output))

    assert len(commands) == 75
    assert not failures


def _registered_command_name(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Expr):
        return None
    call = node.value
    if not isinstance(call, ast.Call):
        return None
    register_call = call.func
    if not isinstance(register_call, ast.Call):
        return None
    command_attr = register_call.func
    if not isinstance(command_attr, ast.Attribute):
        return None
    if command_attr.attr != "command" or not register_call.args:
        return None
    name = register_call.args[0]
    if isinstance(name, ast.Constant) and isinstance(name.value, str):
        return name.value
    return None


def test_invalid_config_file_reports_bad_parameter(runner, tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('active_profile = "missing"\n', encoding="utf-8")

    result = runner.invoke(app, ["--config", str(config_path), "config", "path"])

    assert result.exit_code == 2
    assert "Invalid value" in result.output
    assert "Active profile" in result.output
