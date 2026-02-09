import json
import logging
from typing import Annotated, Literal, TypedDict

import tiktoken
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, trim_messages, ToolMessage, AIMessage
from langgraph.constants import END
from langgraph.graph import StateGraph, add_messages
from langgraph.prebuilt import ToolNode

from core.agent_context import AgentContext
from core.agent_prompt import AGENT_SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT, ROUTER_PROMPT, SUMMARY_SYSTEM_PROMPT
from core.agent_tools import pms_query_mysql, pms_search_vector
from schemas.pms_agent_schema import parse_route
from utils.utils import get_valid_json

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    # add_messages 是 LangGraph 的黑魔法：
    # 当节点返回新的 message 时，它不是覆盖，而是 append（追加）到列表里
    messages: Annotated[list[BaseMessage], add_messages]
    next_node: str


class AgentInstance:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        # self.llm = ChatDeepSeek(model="deepseek-chat", temperature=0.1)
        self.llm_with_tools = None

    def init_tools_and_llm(self, ctx: AgentContext):
        tools = [pms_query_mysql, pms_search_vector(ctx)]
        self.llm_with_tools = self.llm.bind_tools(tools)
        return tools

    def use_trimmer(self, messages):
        system_message = [m for m in messages if isinstance(m, SystemMessage)]
        other_messages = [m for m in messages if not isinstance(m, SystemMessage)]

        question = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                question = msg
                break

        trimmed_messages = trim_messages(
            other_messages,
            strategy="last",
            token_counter=self.count_tokens,
            # token_counter=len,
            max_tokens=6000,
            include_system=False,
            # 确保对话从 Human 开始
            # start_on="human",
            # 允许部分修剪（通常设为 False 以保证完整性）
            allow_partial=False
        )

        valid_messages = []
        active_tool_call_ids = set()
        for i, msg in enumerate(trimmed_messages):
            if isinstance(msg, AIMessage):
                if msg.tool_calls:
                    if i + 1 < len(trimmed_messages):
                        next_msg = trimmed_messages[i + 1]
                        current_tool_call_ids = {call['id'] for call in msg.tool_calls}
                        if isinstance(next_msg, ToolMessage):
                            if next_msg.tool_call_id in current_tool_call_ids:
                                valid_messages.append(msg)
                                active_tool_call_ids = current_tool_call_ids
                else:
                    valid_messages.append(msg)
            elif isinstance(msg, ToolMessage):
                if msg.tool_call_id in active_tool_call_ids:
                    valid_messages.append(msg)
            elif isinstance(msg, HumanMessage):
                valid_messages.append(msg)
                if isinstance(msg, HumanMessage):
                    active_tool_call_ids = set()

        if question and question not in valid_messages:
            valid_messages = [question, *valid_messages]

        return system_message + valid_messages

    async def chat_node(self, state: AgentState):
        messages = state['messages']
        messages = [m for m in messages if not isinstance(m, SystemMessage)]
        messages = [SystemMessage(content=CHAT_SYSTEM_PROMPT), *messages]

        messages_without_tool = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                continue
            elif isinstance(msg, AIMessage) and msg.tool_calls:
                continue
            else:
                messages_without_tool.append(msg)

        clean_messages = self.use_trimmer(messages_without_tool)

        response = await self.llm.ainvoke(clean_messages)
        self.print_message(clean_messages + [response])
        return {"messages": [response]}

    async def router_node(self, state: AgentState):
        needed_messages = []
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                content = msg.content or ""
                marker = "用户问题："
                if marker in content:
                    content = content.split(marker, 1)[-1].strip()
                needed_messages.append(HumanMessage(content=content))
            elif isinstance(msg, AIMessage):
                if not msg.tool_calls:
                    needed_messages.append(msg)

            if len(needed_messages) >= 3:
                break
        resp = await self.llm.ainvoke([SystemMessage(content=ROUTER_PROMPT), *reversed(needed_messages)])

        parsed = parse_route((resp.content or "").strip())
        if not parsed:
            # 重试一次：更强约束
            resp2 = await self.llm.ainvoke([SystemMessage(content=ROUTER_PROMPT + "\n再次强调：只能输出 JSON。"), *reversed(needed_messages)])
            parsed = parse_route((resp2.content or "").strip())

        if not parsed:
            return {"next_node": "chat_agent"}  # 回退

        return {"next_node": "rag_sql_agent" if parsed.route == "SQL" else "chat_agent"}

    async def agent_node(self, state: AgentState):
        messages = state["messages"]
        messages = [m for m in messages if not isinstance(m, SystemMessage)]
        messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT), *messages]

        clean_messages = self.use_trimmer(messages)
        response = await self.llm_with_tools.ainvoke(clean_messages)
        if response.response_metadata.get('finish_reason') == 'stop':
            self.print_message(clean_messages + [response])

        return {"messages": [response]}

    async def summarize_node(self, state: AgentState):
        # 取最后一个用户问题
        question = None
        for m in reversed(state["messages"]):
            if isinstance(m, HumanMessage):
                question = m.content
                break

        # 取 SQL Agent 最后一次“非tool_calls”的 AIMessage 作为中间JSON
        payload = None
        for m in reversed(state["messages"]):
            m_content = (m.content or '').strip()
            if isinstance(m, AIMessage) and not m.tool_calls and m_content:
                logger.warning(f'回答：{m_content}')
                payload = get_valid_json(m_content)
                logger.warning(f'解析内容：{payload}')
                break

        if not payload or not isinstance(payload, dict):
            # 中间结果缺失，按失败处理
            return {"messages": [AIMessage(content="暂无相关数据，请点击消息下方👎️反馈给我们")]}

        inp = [
            SystemMessage(content=SUMMARY_SYSTEM_PROMPT),
            HumanMessage(content=f"用户问题：{question}\n\n中间数据：{json.dumps(payload, ensure_ascii=False)}")
        ]
        resp = await self.llm.ainvoke(inp)
        return {"messages": [resp]}

    @staticmethod
    def should_continue(state: AgentState) -> Literal["tools", "summarize"]:
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return "summarize"

    def build(self, ctx: AgentContext, checkpointer=None):
        tools = self.init_tools_and_llm(ctx)
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("rag_sql_agent", self.agent_node)
        workflow.add_node("chat_agent", self.chat_node)
        workflow.add_node("router", self.router_node)
        workflow.add_node("summarize", self.summarize_node)

        tool_node = ToolNode(tools)
        workflow.add_node("tools", tool_node)

        workflow.set_entry_point("router")
        workflow.add_conditional_edges(
            "router",
            lambda state: state["next_node"],  # 读取 next_node 字段
            {
                "rag_sql_agent": "rag_sql_agent",
                "chat_agent": "chat_agent"
            }
        )
        workflow.add_conditional_edges(
            "rag_sql_agent",
            self.should_continue,
            {"tools": "tools", "summarize": "summarize"}
        )
        workflow.add_edge("tools", "rag_sql_agent")
        workflow.add_edge("chat_agent", END)
        workflow.add_edge("summarize", END)

        app = workflow.compile(checkpointer=checkpointer)
        return app

    @staticmethod
    def count_tokens(messages: list[BaseMessage]) -> int:
        """
        使用 cl100k_base (GPT-4标准) 估算 DeepSeek 的 Token 数
        """
        encoding = tiktoken.get_encoding("cl100k_base")
        num_tokens = 0
        for m in messages:
            # 每条消息的基础开销 (OpenAI 标准通常是 3 token: <|start|>, role, <|end|>)
            num_tokens += 3

            # 计算内容的 token
            # 注意：这里要做个判空，因为有些 ToolMessage content 可能是 None
            content = m.content or ""
            num_tokens += len(encoding.encode(str(content)))

            # 如果有 tool_calls (AI 正在呼叫工具)，这些也要算 token
            if hasattr(m, "tool_calls") and m.tool_calls:
                for tool_call in m.tool_calls:
                    # 简单估算：函数名 + 参数 json 的长度
                    num_tokens += len(encoding.encode(str(tool_call)))

        return num_tokens

    @staticmethod
    def print_message(msg_list):
        for i, msg in enumerate(msg_list):
            msg_type = msg.type.upper()
            logger.info(f'*****************[{i + 1}]  {msg_type}*******************')

            content = msg.content
            tool_calls = hasattr(msg, "tool_calls")
            if isinstance(msg, AIMessage):
                if len(content) > 1:
                    logger.info(msg)
                if tool_calls and len(msg.tool_calls) > 0:
                    logger.info(f"调用工具{msg.tool_calls[0]['name']}: {msg.tool_calls}")
            elif isinstance(msg, ToolMessage):
                logger.info(msg)
            else:
                logger.info(f"{content[:200]}...")
