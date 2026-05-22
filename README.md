# 🚌 名古屋市バスMCPサーバーデモ

[`nagoya-bus-mcp`](https://pypi.org/project/nagoya-bus-mcp/) MCPサーバーのデモ用 Streamlit チャットアプリです。オープンソースカンファレンス2026 Nagoya でのデモ向けに作成しました。名古屋市バスについて質問すると、エージェントが動作する様子と各 MCP ツール呼び出しがインラインで表示されます。

このアプリは [OpenRouter](https://openrouter.ai/) API（デフォルトモデル: `openai/gpt-5-mini`）に対して OpenAI Agents SDK を使用し、同じ `uv` 環境から stdio 経由で `nagoya-bus-mcp` を起動します。

## セットアップ

```shell
uv sync
cp .env.example .env   # OPENROUTER_API_KEY を設定してください
```

`.env` の `OPENROUTER_MODEL` を変更することで、OpenRouter 上の他のモデルを試せます（例: `anthropic/claude-sonnet-4.6`、`google/gemini-2.5-pro`）。

## 実行

```shell
uv run streamlit run app.py
```

アプリは <http://localhost:8501> で起動します。サイドバーのサンプルプロンプトを試すか、`名古屋駅のバスの接近情報を教えて` のように自由に質問してください。

## 仕組み

- `app.py` はチャットのターンごとに `uv run nagoya-bus-mcp` への `MCPServerStdio` 接続を開きます。
- `Agent`（OpenAI Agents SDK）は OpenRouter（`https://openrouter.ai/api/v1`）を向いた `OpenAIChatCompletionsModel` で構築され、`Runner.run_streamed` でストリーミングされます。
- テキストのデルタはチャットバブルにストリームされ、各ツール呼び出しと結果はインラインの展開パネルに表示されるため、MCP のやり取りをユーザーが確認できます。
