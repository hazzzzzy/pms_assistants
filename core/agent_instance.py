import logging
from typing import Annotated, Literal, TypedDict

import tiktoken
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, trim_messages, ToolMessage, AIMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.constants import END
from langgraph.graph import StateGraph, add_messages
from langgraph.prebuilt import ToolNode

from core.agent_context import AgentContext
from core.agent_prompt import AGENT_SYSTEM_PROMPT, CHAT_PROMPT, ROUTER_PROMPT
from core.agent_tools import build_agent_query_mysql, build_agent_search_vector

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    # add_messages 是 LangGraph 的黑魔法：
    # 当节点返回新的 message 时，它不是覆盖，而是 append（追加）到列表里
    messages: Annotated[list[BaseMessage], add_messages]
    next_node: str


class AgentInstance:
    def __init__(self):
        self.llm = ChatDeepSeek(model="deepseek-chat", temperature=0.1)
        self.llm_with_tools = None

    def init_tools_and_llm(self, ctx: AgentContext):
        tools = [build_agent_query_mysql(ctx), build_agent_search_vector(ctx)]
        self.llm_with_tools = self.llm.bind_tools(tools)
        return tools

    def use_trimmer(self, messages):
        system_message = [m for m in messages if isinstance(m, SystemMessage)]

        question = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                question = msg
                break

        trimmed_messages = trim_messages(
            messages,
            # 策略：保留最后面的消息
            strategy="last",
            token_counter=self.count_tokens,
            # token_counter=len,
            max_tokens=6000,
            include_system=True,
            # 确保对话从 Human 开始
            # start_on="human",
            # 允许部分修剪（通常设为 False 以保证完整性）
            allow_partial=False
        )

        valid_messages = []
        for i, msg in enumerate(trimmed_messages):
            if isinstance(msg, ToolMessage):
                # tool_call_id = msg.tool_call_id
                if i - 1 > 0 and isinstance(trimmed_messages[i - 1], AIMessage) and trimmed_messages[i - 1].tool_calls:
                    # or trimmed_messages[i - 1].tool_calls[0].get('id') != tool_call_id):
                    valid_messages.append(msg)
            else:
                valid_messages.append(msg)

        other_messages = [m for m in valid_messages if not isinstance(m, SystemMessage)]
        if question and question not in valid_messages:
            final_messages = [question] + other_messages
        else:
            final_messages = other_messages
        return system_message + final_messages

    async def chat_node(self, state: AgentState):
        messages = state['messages']
        clean_messages = [m for m in messages if not isinstance(m, SystemMessage)]

        input_message = [SystemMessage(content=CHAT_PROMPT)] + clean_messages
        input_message = self.use_trimmer(input_message)

        response = await self.llm.ainvoke(input_message)
        self.print_message(input_message + [response])
        return {"messages": [response]}

    async def router_node(self, state: AgentState):
        messages = state['messages']
        question = messages[-1]
        input_message = [SystemMessage(content=ROUTER_PROMPT), question]
        response = await self.llm.ainvoke(input_message)
        result = response.content.strip().lower()
        if "sql" in result:
            return {"next_node": "rag_sql_agent"}
        else:
            return {"next_node": "chat_agent"}

    async def agent_node(self, state: AgentState):
        messages = state["messages"]
        clean_messages = [m for m in messages if not isinstance(m, SystemMessage)]

        input_message = [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + clean_messages
        input_message = self.use_trimmer(input_message)
        response = await self.llm_with_tools.ainvoke(input_message)
        if response.response_metadata.get('finish_reason') == 'stop':
            self.print_message(input_message + [response])

        return {"messages": [response]}

    @staticmethod
    def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
        messages = state["messages"]
        last_message = messages[-1]

        # 如果 LLM 的回复里包含 tool_calls，说明它想查库 -> 转去工具节点
        if last_message.tool_calls:
            return "tools"
        # print(messages)
        # 否则说明它觉得信息够了，已经生成了最终文本 -> 结束
        return "__end__"

    def build(self, ctx: AgentContext, checkpointer=None):
        tools = self.init_tools_and_llm(ctx)
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("rag_sql_agent", self.agent_node)
        workflow.add_node("chat_agent", self.chat_node)
        workflow.add_node("router", self.router_node)

        tool_node = ToolNode(tools)
        workflow.add_node("tools", tool_node)

        # 设置入口
        workflow.set_entry_point("router")

        # 条件边：根据 router 的结果跳转
        workflow.add_conditional_edges(
            "router",
            lambda state: state["next_node"],  # 读取 next_node 字段
            {
                "rag_sql_agent": "rag_sql_agent",
                "chat_agent": "chat_agent"
            }
        )

        # 添加条件边：AI 思考完后，决定是去查库(tools)还是结束(END)
        workflow.add_conditional_edges(
            "rag_sql_agent",
            self.should_continue,
        )

        # 添加普通边：工具查完后，必须把结果扔回给 AI，让它继续思考
        workflow.add_edge("tools", "rag_sql_agent")
        workflow.add_edge("chat_agent", END)  # 答案生成完 -> 结束

        app = workflow.compile(checkpointer=checkpointer)
        return app

    # 1. 定义一个独立的计数函数 (放在类外面或者静态方法都可以)
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
        # if len(msg_list) != 0:
        #     last_msg = msg_list[-1]
        #     logger.info(f'11111111111{last_msg}')
        #     if isinstance(last_msg, AIMessage):
        #         if last_msg.response_metadata.get('finish_reason') == 'stop':
        for i, msg in enumerate(msg_list):
            msg_type = msg.type.upper()
            logger.info(f'*****************[{i + 1}]  {msg_type}*******************')

            content = msg.content
            tool_calls = hasattr(msg, "tool_calls")
            if isinstance(msg, AIMessage):
                if len(content) > 1:
                    logger.info(content)
                if tool_calls and len(msg.tool_calls) > 0:
                    logger.info(f"调用工具{msg.tool_calls[0]['name']}: {msg.tool_calls}")
            else:
                logger.info(f"{content[:100]}...")
