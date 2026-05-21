"""Streamlit chat demo for the nagoya-bus-mcp MCP server."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any

import streamlit as st
from agents import Agent, OpenAIChatCompletionsModel, Runner
from agents.mcp import MCPServerStdio
from dotenv import load_dotenv
from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent

load_dotenv()

AGENT_INSTRUCTIONS = (
    "You are a Nagoya City bus assistant. Help with station lookups, "
    "timetables, route guidance, and real-time approach information. "
    "Prefer using MCP tools for authoritative answers. Ask clarifying "
    "questions when a station name or route is ambiguous. The output "
    "should be in Markdown format."
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-5-mini"

MCP_SERVER_PARAMS = {
    "command": "uv",
    "args": ["run", "nagoya-bus-mcp"],
}

TOOL_CATALOG = [
    ("get_station_number", "バス停名からバス停番号を検索(あいまい一致あり)"),
    ("get_timetable", "バス停番号から系統別の時刻表を取得"),
    ("get_approach_for_route", "系統コードから走行中バスの位置と通過情報を取得"),
    ("get_approach_for_station", "バス停番号から接近中のバス情報を取得"),
]

EXAMPLE_PROMPTS = [
    "名古屋駅のバスの接近情報を教えて",
    "新栄町の平日の時刻表を教えて",
    "栄から名古屋駅に行くバスはありますか?",
]


@dataclass
class ToolSegment:
    name: str
    arguments: str = ""
    output: str = ""
    done: bool = False


@dataclass
class AssistantTurn:
    segments: list[Any] = field(default_factory=list)


def _render_assistant_turn(turn: AssistantTurn) -> None:
    for seg in turn.segments:
        if isinstance(seg, str):
            if seg:
                st.markdown(seg)
        elif isinstance(seg, ToolSegment):
            label = f"🔧 `{seg.name}`"
            with st.expander(label, expanded=False):
                st.caption("Arguments")
                st.code(_pretty_json(seg.arguments), language="json")
                if seg.output:
                    st.caption("Result")
                    st.code(_pretty_json(seg.output), language="json")


def _pretty_json(raw: str) -> str:
    if not raw:
        return ""
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        return raw


def _build_agent_input(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for msg in messages:
        if msg["role"] == "user":
            history.append({"role": "user", "content": msg["content"]})
        else:
            turn: AssistantTurn = msg["content"]
            text = "".join(s for s in turn.segments if isinstance(s, str))
            if text:
                history.append({"role": "assistant", "content": text})
    return history


async def run_turn(
    history: list[dict[str, str]],
    text_placeholder: st.delta_generator.DeltaGenerator,
    tool_container: st.delta_generator.DeltaGenerator,
) -> AssistantTurn:
    turn = AssistantTurn()
    text_buffer = ""
    active_tools: dict[str, tuple[ToolSegment, Any]] = {}

    async with MCPServerStdio(
        name="Nagoya Bus MCP",
        params=MCP_SERVER_PARAMS,
        client_session_timeout_seconds=30,
    ) as server:
        client = AsyncOpenAI(
            base_url=os.environ.get("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL),
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        model = OpenAIChatCompletionsModel(
            model=os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL),
            openai_client=client,
        )
        agent = Agent(
            name="Nagoya Bus Assistant",
            model=model,
            instructions=AGENT_INSTRUCTIONS,
            mcp_servers=[server],
        )

        result = Runner.run_streamed(agent, input=history)

        async for event in result.stream_events():
            if event.type == "raw_response_event":
                if isinstance(event.data, ResponseTextDeltaEvent):
                    text_buffer += event.data.delta
                    text_placeholder.markdown(text_buffer)
            elif event.type == "run_item_stream_event":
                item = event.item
                if item.type == "tool_call_item":
                    raw = item.raw_item
                    name = getattr(raw, "name", "tool")
                    arguments = getattr(raw, "arguments", "") or ""
                    call_id = getattr(raw, "call_id", None) or getattr(
                        raw, "id", name
                    )
                    seg = ToolSegment(name=name, arguments=arguments)
                    status = tool_container.status(
                        f"🔧 Calling `{name}`…", expanded=False
                    )
                    with status:
                        st.caption("Arguments")
                        st.code(_pretty_json(arguments), language="json")
                    active_tools[call_id] = (seg, status)
                    turn.segments.append(seg)
                elif item.type == "tool_call_output_item":
                    raw = item.raw_item
                    call_id = (
                        raw.get("call_id")
                        if isinstance(raw, dict)
                        else getattr(raw, "call_id", None)
                    )
                    output = item.output
                    output_str = (
                        output if isinstance(output, str) else json.dumps(output)
                    )
                    if call_id in active_tools:
                        seg, status = active_tools.pop(call_id)
                        seg.output = output_str
                        seg.done = True
                        with status:
                            st.caption("Result")
                            st.code(_pretty_json(output_str), language="json")
                        status.update(
                            label=f"🔧 `{seg.name}`", state="complete"
                        )

    if text_buffer:
        turn.segments.append(text_buffer)
        text_placeholder.markdown(text_buffer)
    return turn


def _check_api_key() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        st.error(
            "`OPENROUTER_API_KEY` is not set. Copy `.env.example` to `.env` "
            "and fill in your OpenRouter API key, then restart the app."
        )
        st.stop()


def _render_sidebar() -> None:
    with st.sidebar:
        st.subheader("LLM")
        st.markdown(
            f"OpenRouter · `{os.environ.get('OPENROUTER_MODEL', DEFAULT_MODEL)}`"
        )
        st.subheader("MCP server")
        st.code("uv run nagoya-bus-mcp", language="shell")
        st.subheader("Tools")
        for name, desc in TOOL_CATALOG:
            st.markdown(f"- `{name}` — {desc}")
        st.subheader("Examples")
        for example in EXAMPLE_PROMPTS:
            if st.button(example, use_container_width=True):
                st.session_state.pending_prompt = example
                st.rerun()


def main() -> None:
    st.set_page_config(page_title="Nagoya Bus MCP Demo", page_icon="🚌")
    st.title("🚌 Nagoya Bus MCP Demo")
    st.caption(
        "OpenAI Agents SDK + `nagoya-bus-mcp` over stdio. "
        "Ask about Nagoya City bus stops, timetables, and live approach info."
    )

    _check_api_key()
    _render_sidebar()

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.markdown(msg["content"])
            else:
                _render_assistant_turn(msg["content"])

    prompt = st.chat_input("名古屋市バスについて質問してください…")
    if not prompt and st.session_state.pending_prompt:
        prompt = st.session_state.pending_prompt
        st.session_state.pending_prompt = None

    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        tool_container = st.container()
        text_placeholder = st.empty()
        history = _build_agent_input(st.session_state.messages)
        try:
            turn = asyncio.run(
                run_turn(history, text_placeholder, tool_container)
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Agent run failed: {exc}")
            st.session_state.messages.pop()
            return

    st.session_state.messages.append({"role": "assistant", "content": turn})


if __name__ == "__main__":
    main()
