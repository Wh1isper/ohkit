"""Run the native integration suites against a wheel outside the source checkout."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    if not wheel.is_file():
        parser.error(f"Wheel does not exist: {wheel}")
    agent = ROOT / "tests/fixtures/acp/node_modules/@agentclientprotocol/claude-agent-acp/dist/index.js"
    if not agent.is_file():
        parser.error("Install the locked ACP fixture first: npm ci --prefix tests/fixtures/acp --ignore-scripts")
    report = ROOT / "test-results/installed-native.xml"
    report.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ohkit-consumer-") as temporary:
        work = Path(temporary)
        environment = work / "venv"
        subprocess.run(["uv", "venv", "--python", sys.executable, str(environment)], check=True)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run(
            ["uv", "pip", "install", "--python", str(python), str(wheel), "pytest>=9,<10", "pytest-timeout>=2.4,<3"],
            check=True,
        )
        tests = work / "tests"
        tests.mkdir()
        for name in ("test_codex_native.py", "test_claude_native.py", "test_acp_native.py", "test_acp.py"):
            shutil.copy2(ROOT / "tests" / name, tests / name)
        shutil.copytree(
            ROOT / "tests/fixtures", tests / "fixtures", ignore=shutil.ignore_patterns("node_modules", "__pycache__")
        )
        shutil.copytree(ROOT / "examples", work / "examples", ignore=shutil.ignore_patterns("__pycache__"))
        (work / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts/codex_protocol.py", work / "scripts/codex_protocol.py")
        (work / "protocol/codex").mkdir(parents=True)
        shutil.copy2(ROOT / "protocol/codex/manifest.json", work / "protocol/codex/manifest.json")
        (tests / "conftest.py").write_text(
            "from pathlib import Path\nimport sys\nimport ohkit\n"
            "assert Path(ohkit.__file__).is_relative_to(Path(sys.prefix)), ohkit.__file__\n"
            'print("Installed package:", ohkit.__file__)\n'
        )
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.update(OHKIT_TEST_NATIVE="1", OHKIT_TEST_ACP_NATIVE="1", OHKIT_ACP_AGENT=str(agent))
        subprocess.run(
            [
                str(python),
                "-m",
                "pytest",
                "tests",
                "--import-mode=importlib",
                "--timeout=120",
                "-q",
                f"--junitxml={report}",
            ],
            check=True,
            cwd=work,
            env=env,
        )
    print(f"Installed-wheel execution passed: {wheel.name}")


if __name__ == "__main__":
    main()
