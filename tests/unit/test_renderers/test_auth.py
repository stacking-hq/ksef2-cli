import pytest

from ksef2_cli.renderers.auth import mask_token


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("eyJhbGci-middle-secret-P_eA", "eyJhbGci…P_eA"),
        ("access-token", "access-t…oken"),
        ("short", "**********"),
        ("", "**********"),
    ],
)
def test_mask_token(token: str, expected: str) -> None:
    assert mask_token(token) == expected
