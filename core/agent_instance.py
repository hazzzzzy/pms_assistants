from typing import Annotated, Literal, TypedDict

import tiktoken
from langchain_core.messages import BaseMessage, trim_messages
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import StateGraph, add_messages
from langgraph.prebuilt import ToolNode

from core.agent_context import AgentContext
from core.agent_tools import build_agent_query_mysql, build_agent_search_vector


class AgentState(TypedDict):
    # add_messages 是 LangGraph 的黑魔法：
    # 当节点返回新的 message 时，它不是覆盖，而是 append（追加）到列表里
    messages: Annotated[list[BaseMessage], add_messages]


class AgentInstance:
    def __init__(self):
        self.llm = ChatDeepSeek(model="deepseek-chat", temperature=0.6)
        self.llm_with_tools = None

    def init_tools_and_llm(self, ctx: AgentContext):
        tools = [build_agent_query_mysql(ctx), build_agent_search_vector(ctx)]
        self.llm_with_tools = self.llm.bind_tools(tools)
        return tools

    async def agent_node(self, state: AgentState):
        messages = state["messages"]
        # 定义修剪器
        trimmer = trim_messages(
            messages,
            # 策略：保留最后面的消息
            strategy="last",

            # 关键技巧：我们将 Token 计数器定义为 "每条消息算 1 个 Token"
            # 这样 max_tokens=10 就等于 "保留 10 条消息"
            # 如果你想按真实 Token 限制（比如 4000 token），这里换成 llm.get_num_tokens
            token_counter=self.count_tokens,
            max_tokens=5000,

            # 必须保留系统提示词！
            include_system=True,

            # 确保对话从 Human 开始（为了整洁，可选）
            # start_on="human",

            # 允许部分修剪（通常设为 False 以保证完整性）
            allow_partial=False
        )

        response = await self.llm_with_tools.ainvoke(trimmer)
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

        tool_node = ToolNode(tools)
        workflow.add_node("tools", tool_node)
        # workflow.add_node("summary", summary_node)

        # 设置入口
        workflow.set_entry_point("rag_sql_agent")

        # 添加条件边：AI 思考完后，决定是去查库(tools)还是结束(END)
        workflow.add_conditional_edges(
            "rag_sql_agent",
            self.should_continue,
        )

        # 添加普通边：工具查完后，必须把结果扔回给 AI，让它继续思考
        workflow.add_edge("tools", "rag_sql_agent")
        # workflow.add_edge("summary", END)  # 答案生成完 -> 结束

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
    # def draw(self, file_name):
    #     workflow = self.build()
    #     img = workflow.get_graph().draw_mermaid_png()
    #     img_path = abs_path(f"../asset/graph_pic/{file_name}.png")
    #     with open(img_path, "wb") as f:
    #         f.write(img)
