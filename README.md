# nagoya-bus-mcp-osc-demo

A small Streamlit chat app that demos the [`nagoya-bus-mcp`](https://pypi.org/project/nagoya-bus-mcp/) MCP server. Built for an Open Source Conference demo: ask the chat about Nagoya City buses and watch each MCP tool call render inline as the agent works.

The app uses the OpenAI Agents SDK against the [OpenRouter](https://openrouter.ai/) API (default model `openai/gpt-5-mini`) and launches `nagoya-bus-mcp` over stdio from the same `uv` environment.

## Setup

```shell
uv sync
cp .env.example .env   # then fill in OPENROUTER_API_KEY
```

Override `OPENROUTER_MODEL` in `.env` to try any other model on OpenRouter (e.g. `anthropic/claude-sonnet-4.6`, `google/gemini-2.5-pro`).

## Run

```shell
uv run streamlit run app.py
```

The app opens at <http://localhost:8501>. Try one of the example prompts in the sidebar, or ask your own question — e.g. `名古屋駅のバスの接近情報を教えて`.

## How it works

- `app.py` opens an `MCPServerStdio` connection to `uv run nagoya-bus-mcp` per chat turn.
- An `Agent` (OpenAI Agents SDK) is built with `OpenAIChatCompletionsModel` pointed at OpenRouter (`https://openrouter.ai/api/v1`) and streamed via `Runner.run_streamed`.
- Text deltas stream into the chat bubble; each tool call and result is shown in an inline expander so the audience can see the MCP exchange.
