import datetime
import logging

from langchain_core.messages import SystemMessage, HumanMessage

from core.agent_instance import AgentInstance
from core.agent_prompt import AGENT_SYSTEM_PROMPT, AGENT_USER_PROMPT

logger = logging.getLogger(__name__)


async def chat(question, thread_id, hotel_id, uid):
    current_time = datetime.datetime.now().strftime('%Y-%m-%d')
    graph = AgentInstance().build()
    inputs = {
        "messages": [
            SystemMessage(content=AGENT_SYSTEM_PROMPT.format(hotel_id)),
            HumanMessage(content=AGENT_USER_PROMPT.format(current_time, hotel_id, uid, question))
        ]
    }

    for event in graph.stream(inputs, config={"recursion_limit": 50}):
        # 1. 捕获 Agent 的思考与行动
        if "ReAct" in event:
            # print(event)
            message = event["ReAct"]["messages"][0]
            content = message.content
            tool_calls = message.tool_calls

            # 打印 AI 的思考文本 (如果有)
            if content:
                logger.info(f"[AI 回答]: {content}")
                yield f"data: {content}\n\n"

            # 打印 AI 决定调用的工具
            if tool_calls:
                for tc in tool_calls:
                    logger.info(f"[调用工具] {tc['name']}: {tc['args']}")

        # 2. 捕获工具的返回结果
        elif "tools" in event:
            # print('工具调用')
            # ToolNode 返回的是 ToolMessage
            message = event["tools"]["messages"][0]
            logger.info(f"[工具返回]: {message.content[:200]}...")  # 只打印前200字防止刷屏
