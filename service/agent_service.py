import datetime
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from core.agent_context import AgentContext
from core.agent_prompt import AGENT_SYSTEM_PROMPT, AGENT_USER_PROMPT
from utils.abs_path import abs_path

logger = logging.getLogger(__name__)


async def chat(ctx: AgentContext, question, thread_id, hotel_id, uid):
    current_time = datetime.datetime.now().strftime('%Y-%m-%d')
    inputs = {
        "messages": [
            SystemMessage(id="sys_prompt", content=AGENT_SYSTEM_PROMPT.format(hotel_id)),
            HumanMessage(content=AGENT_USER_PROMPT.format(current_time, hotel_id, uid, question))
        ]
    }
    agent_config = {
        'configurable': {
            'thread_id': thread_id
        },
        "recursion_limit": 50,
    }
    ai_output = ''
    # try:
    async for event in ctx.graph.astream_events(inputs, version="v2", config=agent_config):
        kind = event["event"]
        # if kind != "on_chat_model_stream":
        #     logger.info(event)
        # --- 场景 1: 捕获 LLM 的流式吐字 (打字机效果) ---
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            langgraph_node = event["metadata"]["langgraph_node"]
            # logger.info(chunk)
            # 过滤掉工具调用的参数生成过程 (agent 思考参数时 content 为空)
            if chunk.content and langgraph_node != 'router':
                # if chunk.content:
                # 直接 yield 纯文本，由 FastAPI 的 EventSourceResponse 自动封装格式
                # 或者手动封装成 data: {char}\n\n
                payload = json.dumps({"text": chunk.content}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        elif kind == 'on_chat_model_end':
            chunk = event["data"]["output"]
            langgraph_node = event["metadata"]["langgraph_node"]
            if chunk.content and langgraph_node != 'router':
                logger.info(f'[AI说]: {chunk.content}')
                ai_output += chunk.content
        # --- 场景 2: 捕获工具调用 (可选，用于调试或前端展示 loading) ---
        elif kind == "on_tool_start":
            tool_name = event['name']
            tool_inputs = event['data'].get('input')
            logger.info(f"[正在调用工具]: {tool_name} 参数: {tool_inputs}")
            # yield f"data: {json.dumps({"text": ' 正在调用工具...'}, ensure_ascii=False)}\n\n"

        # --- 场景 3: 捕获工具返回结果 (可选) ---
        elif kind == "on_tool_end":
            # 有些工具输出可能很长，截断打印日志
            output = str(event['data'].get('output'))
            logger.info(f"[工具返回]: {output[:100]}...")

        # except Exception as e:
        #     # yield f"data: {json.dumps({'error': str(e)})}\n\n"
        #     logger.error(e)
        #     yield f"data: {json.dumps({'text': str(e)})}\n\n"
        # finally:
        # 流式结束
        yield "data: [DONE]\n\n"
    # 存储进数据库
    # sss


async def draw(ctx: AgentContext, file_name):
    img = ctx.graph.get_graph().draw_mermaid_png()
    img_path = abs_path(f"../asset/graph_pic/{file_name}.png")
    with open(img_path, "wb") as f:
        f.write(img)
