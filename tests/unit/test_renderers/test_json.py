import json
from datetime import UTC, datetime

from ksef2.domain.models.invoices import ExportHandle
from ksef2.domain.models.tokens import GenerateTokenResponse

from ksef2_cli.commands.invoices.models import ExportHandleSaved, ExportPaths
from ksef2_cli.config import (
    CliConfig,
    ProfileAuthConfig,
    ProfileAuthType,
    ProfileConfig,
)
from ksef2_cli.renderers.json import json_renderer
from ksef2_cli.results import (
    ActionResult,
    CertificateRevoked,
    ConfigInitialized,
    ConfigPathResult,
    ConfigShowResult,
    CurrentSessionTerminated,
    FocusedResult,
    LimitReset,
    LimitUpdated,
    ProductionRateLimitsSet,
    SavedFile,
    SessionClosed,
)


def test_json_renderer_dumps_pydantic_models_and_lists() -> None:
    result = GenerateTokenResponse(reference_number="token-ref", token="secret")

    assert json.loads(json_renderer.render(result)) == {
        "reference_number": "token-ref",
        "token": "secret",
    }
    assert json.loads(json_renderer.render([result])) == [
        {
            "reference_number": "token-ref",
            "token": "secret",
        }
    ]


def test_json_renderer_delegates_focused_result_to_payload() -> None:
    focused = FocusedResult(
        payload={"created_at": datetime(2026, 1, 2, tzinfo=UTC)},
        items=["text-only"],
    )

    assert json.loads(json_renderer.render(focused)) == {
        "created_at": "2026-01-02T00:00:00Z",
    }


def test_json_renderer_delegates_focused_result_to_model_payload(tmp_path) -> None:
    focused = FocusedResult(
        payload=ExportPaths(
            reference_number="export-ref", paths=[tmp_path / "out.xml"]
        ),
        items=[str(tmp_path / "out.xml")],
    )

    assert json.loads(json_renderer.render(focused)) == {
        "reference_number": "export-ref",
        "paths": [str(tmp_path / "out.xml")],
    }


def test_action_result_json_uses_booleans() -> None:
    result = ActionResult(reference_number="token-ref", revoked=True)

    assert json.loads(json_renderer.render(result)) == {
        "reference_number": "token-ref",
        "revoked": True,
    }


def test_cli_action_models_json_use_booleans() -> None:
    assert json.loads(json_renderer.render(LimitUpdated(kind="api"))) == {
        "kind": "api",
        "updated": True,
    }
    assert json.loads(json_renderer.render(LimitReset(kind="session"))) == {
        "kind": "session",
        "reset": True,
    }
    assert json.loads(json_renderer.render(ProductionRateLimitsSet())) == {
        "api_rate_limits": "production",
    }
    assert json.loads(
        json_renderer.render(SessionClosed(reference_number="session-ref"))
    ) == {
        "reference_number": "session-ref",
        "closed": True,
    }
    assert json.loads(json_renderer.render(CurrentSessionTerminated())) == {
        "terminated_current": True,
    }
    assert json.loads(
        json_renderer.render(
            CertificateRevoked(serial_number="ABCDEF1234567890", reason="superseded")
        )
    ) == {
        "serial_number": "ABCDEF1234567890",
        "reason": "superseded",
        "revoked": True,
    }


def test_config_result_models_json(tmp_path) -> None:
    config = CliConfig(
        active_profile="demo",
        profiles={
            "demo": ProfileConfig(
                environment="test",
                nip="5261040828",
                auth=ProfileAuthConfig(
                    type=ProfileAuthType.token,
                    token_env="KSEF2_DEMO_TOKEN",
                    context_type="nip",
                ),
            )
        },
    )

    assert json.loads(
        json_renderer.render(
            ConfigPathResult(path=tmp_path / "config.toml", exists=False, loaded=False)
        )
    ) == {
        "path": str(tmp_path / "config.toml"),
        "exists": False,
        "loaded": False,
    }

    shown = json.loads(
        json_renderer.render(
            ConfigShowResult(path=tmp_path / "config.toml", exists=True, config=config)
        )
    )
    assert shown["path"] == str(tmp_path / "config.toml")
    assert shown["exists"] is True
    assert shown["config"]["active_profile"] == "demo"
    assert shown["config"]["profiles"]["demo"]["nip"] == "5261040828"
    assert (
        shown["config"]["profiles"]["demo"]["auth"]["token_env"]
        == "KSEF2_DEMO_TOKEN"
    )

    initialized = json.loads(
        json_renderer.render(
            ConfigInitialized(
                path=tmp_path / "config.toml", mode="0600", config=config
            )
        )
    )
    assert initialized["path"] == str(tmp_path / "config.toml")
    assert initialized["mode"] == "0600"
    assert initialized["config"]["active_profile"] == "demo"


def test_saved_file_json_uses_bytes_alias(tmp_path) -> None:
    result = SavedFile(path=tmp_path / "invoice.xml", size=123)

    assert json.loads(json_renderer.render(result)) == {
        "path": str(tmp_path / "invoice.xml"),
        "bytes": 123,
    }


def test_export_handle_json_uses_base64_and_omits_empty_handle_file(tmp_path) -> None:
    handle = ExportHandle(reference_number="export-ref", aes_key=b"abc", iv=b"def")

    assert json.loads(json_renderer.render(ExportHandleSaved.from_handle(handle))) == {
        "reference_number": "export-ref",
        "aes_key": "YWJj",
        "iv": "ZGVm",
    }
    assert json.loads(
        json_renderer.render(
            ExportHandleSaved.from_handle(handle, handle_file=tmp_path / "handle.json")
        )
    ) == {
        "reference_number": "export-ref",
        "aes_key": "YWJj",
        "iv": "ZGVm",
        "handle_file": str(tmp_path / "handle.json"),
    }


def test_export_paths_json_omits_empty_handle_file(tmp_path) -> None:
    assert json.loads(
        json_renderer.render(
            ExportPaths(reference_number="export-ref", paths=[tmp_path / "out.xml"])
        )
    ) == {
        "reference_number": "export-ref",
        "paths": [str(tmp_path / "out.xml")],
    }
