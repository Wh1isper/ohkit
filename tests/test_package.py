from importlib.metadata import metadata, version
from importlib.resources import files

import ohkit


def test_version_matches_installed_distribution() -> None:
    assert ohkit.__version__ == version("ohkit")


def test_distribution_is_independent_and_typed() -> None:
    assert metadata("ohkit")["Name"] == "ohkit"
    requirements = metadata("ohkit").get_all("Requires-Dist", [])
    assert requirements and all(
        "extra == 'codex-websocket'" in requirement or 'extra == "codex-websocket"' in requirement
        for requirement in requirements
    )
    assert not any("a13n" in requirement or "pydantic" in requirement for requirement in requirements)
    assert files("ohkit").joinpath("py.typed").is_file()
