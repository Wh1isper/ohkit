from __future__ import annotations

import argparse
from pathlib import Path

from release_version import COMPONENTS, prepare_release


def main() -> None:
    parser = argparse.ArgumentParser(description="Inject a tag version into an isolated release checkout.")
    parser.add_argument("component", choices=COMPONENTS)
    parser.add_argument("version")
    args = parser.parse_args()
    try:
        prepare_release(Path.cwd(), args.version)
    except ValueError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
