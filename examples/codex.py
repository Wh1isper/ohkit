"""Run: uv run python examples/codex.py (requires configured Codex 0.161.0)."""

import asyncio

from ohkit import ApprovalChoice, ApprovalRequest, ContentEvent, Handlers
from ohkit.backends.codex import Codex


async def deny(request: ApprovalRequest) -> ApprovalChoice:
    return next(choice for choice in request.choices if choice.kind in ("decline", "cancel"))


async def main() -> None:
    async with Codex() as backend:
        thread = await backend.new_thread()
        async with thread.stream(
            "Describe this project without making changes.", handlers=Handlers(approval=deny)
        ) as run:
            async for event in run:
                if isinstance(event, ContentEvent) and event.channel == "assistant":
                    print(event.text, end="", flush=True)
            result = await run.result()
        print("\nOutcome:", result.outcome)
        resumed = await backend.resume(thread.ref)
        follow_up = await resumed.run("Summarize that in one sentence.", handlers=Handlers(approval=deny))
        print(follow_up.output)


if __name__ == "__main__":
    asyncio.run(main())
