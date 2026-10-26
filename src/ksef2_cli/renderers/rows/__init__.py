"""Plain-text row handler registrations."""


def register_all() -> None:
    from ksef2_cli.renderers.rows import (
        auth,
        collective,
        peppol,
        results,
        sdk,
        testdata,
        tokens,
    )

    auth.register()
    collective.register()
    peppol.register()
    results.register()
    sdk.register()
    testdata.register()
    tokens.register()
