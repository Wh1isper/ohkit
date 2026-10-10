"""Run with an installed/authenticated agent; see --help and docs/acp.md."""

import argparse
import asyncio
import os

from ohkit import ApprovalChoice, ApprovalRequest, ContentEvent, Handlers
from ohkit.backends.acp import ACP, ACPOptions


async def deny(request: ApprovalRequest) -> ApprovalChoice:
    for choice in request.choices:
        assert choice.native is not None
        data = choice.native.decode()
        assert isinstance(data, dict)
        if data["kind"] in ("reject_once", "reject_always"):
            return choice
    raise ValueError("Agent offered no rejection choice")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", required=True, help="Native agent's project directory")
    parser.add_argument("--prompt", default="Describe this project without changing files.")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Agent executable and arguments, after --")
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("Provide an ACP agent command after --")
    # Forward only credentials/configuration deliberately chosen by this application.
    env = tuple((key, os.environ[key]) for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL") if key in os.environ)
    async with ACP(options=ACPOptions(command=tuple(command), env=env)) as backend:
        thread = await backend.new_thread(cwd=args.cwd)
        handlers = Handlers(approval=deny)
        async with thread.stream(args.prompt, handlers=handlers) as run:
            async for event in run:
                if isinstance(event, ContentEvent) and event.channel == "assistant":
                    print(event.text, end="", flush=True)
            result = await run.result()
        print("\nOutcome:", result.outcome)
        if result.outcome == "completed" and thread.capabilities.resume:
            resumed = await backend.resume(thread.ref, cwd=args.cwd)
            print((await resumed.run("Summarize that in one sentence.", handlers=handlers)).output)


if __name__ == "__main__":
    asyncio.run(main())
