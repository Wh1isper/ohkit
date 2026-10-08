---
title: Getting started
description: Install the pre-alpha bootstrap and check its version.
---

## Requirements

Use Python 3.13 or newer. The Python distribution has no runtime dependencies. Documentation tools are separate development dependencies.

## Install the bootstrap

The current release is a pre-release. Include `--pre` when installing it:

```bash
python -m pip install --pre ohkit
```

Check the installed version:

```python
import ohkit

print(ohkit.__version__)
```

This verifies installation only. The package does not yet run Codex, ACP agents, or Claude.

## Follow the design

Read the [application-hosted executor example](examples/application-hosted-executor.md) for the intended integration boundary. It is a conceptual example, not code that can run against the bootstrap.

The [specifications](https://github.com/Wh1isper/ohkit/tree/main/spec) define the accepted execution and Workspace contracts. Executable examples and backend compatibility ranges will accompany their implementations.
