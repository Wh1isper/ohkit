# ohkit

A unified Python programming interface for agent harnesses.

## Status

ohkit is a pre-alpha Python library. This checkout implements typed asynchronous Thread/Run execution and a concrete Codex app-server control backend: streaming, result-only execution, active steering, cancellation, native history resume/fork, and typed approvals/questions. It does not implement caller-supplied Workspace I/O, an executor bridge, ACP, or Claude adapters. Earlier published bootstrap releases expose metadata only; these source capabilities are not a claim of a new release.

The repository, Python distribution, and import package are all named `ohkit`. Python 3.13 or newer is required. Both owned stdio control and connections to caller-owned WebSocket services are available in the default installation. Codex must be installed separately and configured for its native model provider.

The [architecture specifications](spec/README.md) own the execution model and future Workspace boundary. The [getting-started guide](docs/getting-started.md) and [Codex guide](docs/codex.md) describe runnable source APIs and the tested native version, rather than promising compatibility with every upstream release.

## Quick start

Install this checkout with `python -m pip install .`, then use a configured Codex executable on `PATH`:

```python
import asyncio

from ohkit.backends.codex import Codex


async def main() -> None:
    async with Codex() as backend:
        thread = await backend.new_thread(cwd="/path/to/project")
        result = await thread.run("Explain the project without changing files.")
        print(result.outcome, result.output)


asyncio.run(main())
```

The native harness owns tools, filesystem access, sandbox policy, and credentials. Entering `Codex()` owns one stdio app-server process; it is not a portable Workspace or application sandbox.

## Development

```bash
git clone https://github.com/Wh1isper/ohkit.git
cd ohkit
make install
make check-all
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution and validation rules, [DEVELOPMENT.md](DEVELOPMENT.md) for engineering standards, and [spec/README.md](spec/README.md) for accepted contracts.

## Documentation

- [Documentation index](docs/index.md)
- [Documentation build and deployment](docs/documentation.md)
- Canonical site: [ohkit.wh1isper.top](https://ohkit.wh1isper.top/)
- [Release procedure](docs/releasing.md)
- [Security policy](SECURITY.md)

## License

[MIT License](LICENSE).
