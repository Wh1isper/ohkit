"""Run with configured Claude credentials; see --help and docs/claude.md."""

import argparse
import asyncio

from claude_agent_sdk import ClaudeAgentOptions

from ohkit import ApprovalChoice, ApprovalRequest, ContentEvent, Handlers
from ohkit.backends.claude import Claude


async def deny(request: ApprovalRequest) -> ApprovalChoice:
    return next(choice for choice in request.choices if choice.kind == "decline")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", required=True, help="Native Claude project directory")
    parser.add_argument("--prompt", default="Describe this project without changing files.")
    args = parser.parse_args()
    options = ClaudeAgentOptions(tools=["Read", "Glob", "Grep"], permission_mode="default")
    handlers = Handlers(approval=deny)
    async with Claude(options=options) as backend:
        thread = await backend.new_thread(cwd=args.cwd)
        async with thread.stream(args.prompt, handlers=handlers) as run:
            async for event in run:
                if isinstance(event, ContentEvent) and event.channel == "assistant":
                    print(event.text, end="", flush=True)
            result = await run.result()
        print("\nOutcome:", result.outcome)
        if result.outcome == "completed":
            print((await thread.run("Summarize that in one sentence.", handlers=handlers)).output)


if __name__ == "__main__":
    asyncio.run(main())
