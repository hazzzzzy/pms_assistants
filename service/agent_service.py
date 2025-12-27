import datetime
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from core.agent_context import AgentContext
from core.agent_prompt import AGENT_SYSTEM_PROMPT, AGENT_USER_PROMPT

logger = logging.getLogger(__name__)


async def chat(ctx: AgentContext, question, thread_id, hotel_id, uid):
    current_time = datetime.datetime.now().strftime('%Y-%m-%d')
    inputs = {
        "messages": [
            SystemMessage(content=AGENT_SYSTEM_PROMPT.format(hotel_id)),
            HumanMessage(content=AGENT_USER_PROMPT.format(current_time, hotel_id, uid, question))
        ]
    }

    async for event in ctx.graph.astream_events(inputs, version="v2",
                                                config={"recursion_limit": 50}):
        # 1. 捕获 Agent 的思考与行动
        # if "rag_sql_agent" in event:
        #     # print(event)
        #     message = event["rag_sql_agent"]["messages"][0]
        #     content = message.content
        #     tool_calls = message.tool_calls
        #
        #     # 打印 AI 的思考文本 (如果有)
        #     if content:
        #         logger.info(f"[AI 回答]: {content}")
        #         yield f"data: {content}\n\n"
        #
        #     # 打印 AI 决定调用的工具
        #     if tool_calls:
        #         for tc in tool_calls:
        #             logger.info(f"[调用工具] {tc['name']}: {tc['args']}")
        #
        # # 2. 捕获工具的返回结果
        # elif "tools" in event:
        #     # print('工具调用')
        #     # ToolNode 返回的是 ToolMessage
        #     message = event["tools"]["messages"][0]
        #     logger.info(f"[工具返回]: {message.content[:200]}...")  # 只打印前200字防止刷屏
        kind = event["event"]
        # logger.info(event)
        # --- 场景 1: 捕获 LLM 的流式吐字 (打字机效果) ---
        if kind == "on_chat_model_stream":
            # 获取当前这一个 token (比如 "今", "天", "天", "气")
            chunk = event["data"]["chunk"]

            # 过滤掉工具调用的参数生成过程 (agent 思考参数时 content 为空)
            if chunk.content:
                # 直接 yield 纯文本，由 FastAPI 的 EventSourceResponse 自动封装格式
                # 或者手动封装成 data: {char}\n\n
                yield f"data: {chunk.content}\n\n"
        elif kind == 'on_chat_model_end':
            chunk = event["data"]["output"]
            if chunk.content:
                logger.info(f'[AI说]: {chunk.content}')
        # --- 场景 2: 捕获工具调用 (可选，用于调试或前端展示 loading) ---
        elif kind == "on_tool_start":
            tool_name = event['name']
            tool_inputs = event['data'].get('input')
            logger.info(f"[正在调用工具]: {tool_name} 参数: {tool_inputs}")
            # yield f"data: [正在查询数据...]\n\n"

        # --- 场景 3: 捕获工具返回结果 (可选) ---
        elif kind == "on_tool_end":
            # 有些工具输出可能很长，截断打印日志
            output = str(event['data'].get('output'))
            logger.info(f"[工具返回]: {output[:100]}...")

        # 流式结束
    yield "data: [DONE]\n\n"
