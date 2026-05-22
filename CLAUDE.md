# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A Streamlit chat demo for the [`nagoya-bus-mcp`](https://pypi.org/project/nagoya-bus-mcp/) MCP server, built for a demo at Open Source Conference 2026 Nagoya. The whole app is `app.py`; user-facing strings and the README are in Japanese.

## Commands

```shell
uv sync                          # install dependencies (incl. dev group)
uv run streamlit run app.py      # run the app at http://localhost:8501
uv run nagoya-bus-mcp            # run the MCP server standalone (app launches this internally)

uv run pre-commit run ruff-check    # lint (ruff selects ALL; see pyproject ignores). ruff is not a direct dep — invoke it via pre-commit
uv run pre-commit run ruff-format   # format
uv run ty check                     # type check (ty, Astral's type checker; ty is a dev dep so it runs directly)
uv run pre-commit run --all-files   # run every hook (ruff, ty, file hygiene) against all files
```

Requires Python 3.14. There is no test suite. `OPENROUTER_API_KEY` must be set in `.env` (copy `.env.example`); the app calls `st.stop()` with an error if it is missing.

## Architecture

The data flow per chat turn: Streamlit UI → OpenAI Agents SDK `Runner` → `OpenAIChatCompletionsModel` pointed at **OpenRouter** (not OpenAI) → tool calls dispatched to the **`nagoya-bus-mcp`** server over stdio.

Key design points to understand before editing `app.py`:

- **MCP connection is per-turn, not persistent.** `run_turn()` opens a fresh `MCPServerStdio` (`uv run nagoya-bus-mcp`) inside an `async with` for each message and tears it down when the turn ends. The whole turn runs under a single `asyncio.run()` call from synchronous Streamlit code.
- **Model provider is OpenRouter via the OpenAI-compatible API.** `AsyncOpenAI` is constructed with `base_url=OPENROUTER_BASE_URL` and `OPENROUTER_API_KEY`. Override the model with `OPENROUTER_MODEL` (default `openai/gpt-5-mini`). The agent's available tools come entirely from the MCP server, not from code in this repo.
- **Streaming drives the UI.** `Runner.run_streamed` yields events: `RawResponsesStreamEvent` carrying `ResponseTextDeltaEvent` deltas append to the chat bubble; `RunItemStreamEvent` of type `tool_call_item` / `tool_call_output_item` render each MCP call and its result into an inline `st.status` expander. Tool calls are correlated across the two events by `call_id`.
- **Conversation state is a list of typed segments.** An assistant message is an `AssistantTurn` whose `segments` interleave `str` (text) and `ToolSegment` (a tool call) so the rendering preserves call order. `_render_assistant_turn()` replays them on rerun.
- **History sent to the model is text-only.** `_build_agent_input()` flattens each `AssistantTurn` to its concatenated text and *drops* the `ToolSegment` entries, so prior tool calls/results are not replayed back to the model on the next turn.

`AGENT_INSTRUCTIONS` in `app.py` is the system prompt and encodes demo-specific assumptions — notably that the user's nearest stop is 吹上 (Fukiage) and that internal route codes must be hidden from output. Edit these strings when changing demo behavior.
