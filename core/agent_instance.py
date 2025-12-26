from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage, RemoveMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import StateGraph, add_messages
from langgraph.prebuilt import ToolNode

from utils.abs_path import abs_path
from utils.agent_tools import agent_search_vector, agent_query_mysql


class AgentState(TypedDict):
    # add_messages 是 LangGraph 的黑魔法：
    # 当节点返回新的 message 时，它不是覆盖，而是 append（追加）到列表里
    messages: Annotated[list[BaseMessage], add_messages]


class AgentInstance:
    def __init__(self):
        self.llm = ChatDeepSeek(model="deepseek-chat", temperature=0.6)
        self.tools = [agent_query_mysql, agent_search_vector]
        self.llm_with_tools = self.llm.bind_tools(self.tools)

    def agent_node(self, state: AgentState):
        messages = state["messages"]
        response = self.llm_with_tools.invoke(messages)
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

    @staticmethod
    def memory_management_node(state: AgentState):
        messages = state["messages"]

        # 如果消息超过 50 条
        if len(messages) > 50:
            # 计算需要删除多少条（保留最新的 50 条）
            # 注意：通常要保留第1条 SystemMessage，所以切片逻辑要小心
            num_to_remove = len(messages) - 50

            # 获取要删除的消息的 ID
            ids_to_remove = [m.id for m in messages[:num_to_remove]]

            # 返回 RemoveMessage 操作，LangGraph 会在 Checkpoint 中真正删除这些消息
            return {"messages": [RemoveMessage(id=m_id) for m_id in ids_to_remove]}

        return {}  # 什么都不做

    def build(self):
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("rag_sql_agent", self.agent_node)

        tool_node = ToolNode(self.tools)
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

        app = workflow.compile()
        return app

    def draw(self, file_name):
        workflow = self.build()
        img = workflow.get_graph().draw_mermaid_png()
        img_path = abs_path(f"../asset/graph_pic/{file_name}.png")
        with open(img_path, "wb") as f:
            f.write(img)


if __name__ == '__main__':
    pass
