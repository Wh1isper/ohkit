# ohkit

A unified Python API for coding agents.

## Status

ohkit is a pre-alpha Python library. This initial distribution establishes the package, engineering conventions, and release pipeline. It does not yet implement agent backends or a public execution API.

The repository, Python distribution, and import package are all named `ohkit`. Python 3.13 or newer is required. The bootstrap package has no runtime dependencies.

## Development

```bash
git clone https://github.com/converge-ai-labs/ohkit.git
cd ohkit
make install
make check-all
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution and validation rules, [DEVELOPMENT.md](DEVELOPMENT.md) for engineering standards, and [spec/README.md](spec/README.md) for accepted contracts.

## Documentation

- [Documentation index](docs/README.md)
- [Release procedure](docs/releasing.md)
- [Security policy](SECURITY.md)

## License

[Apache License 2.0](LICENSE).
