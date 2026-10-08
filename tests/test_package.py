from importlib.metadata import metadata, version
from importlib.resources import files

import ohkit


def test_version_matches_installed_distribution() -> None:
    assert ohkit.__version__ == version("ohkit")


def test_distribution_is_independent_and_typed() -> None:
    assert metadata("ohkit")["Name"] == "ohkit"
    assert metadata("ohkit").get_all("Requires-Dist", []) == []
    assert files("ohkit").joinpath("py.typed").is_file()
