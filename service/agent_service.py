import datetime
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import desc, func, select

from core.agent_context import AgentContext
from core.agent_prompt import AGENT_SYSTEM_PROMPT, AGENT_USER_PROMPT
from core.db import db_session
from db_models.models import ChatHistory
from utils.abs_path import abs_path

logger = logging.getLogger(__name__)


async def chat(ctx: AgentContext, question, thread_id, hotel_id, uid):
    current_time = datetime.datetime.now().strftime("%Y-%m-%d")
    inputs = {
        "messages": [
            SystemMessage(
                id="sys_prompt", content=AGENT_SYSTEM_PROMPT.format(hotel_id)
            ),
            HumanMessage(
                content=AGENT_USER_PROMPT.format(current_time, hotel_id, uid, question)
            ),
        ]
    }
    agent_config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,
    }
    ai_output = ""
    # try:
    async for event in ctx.graph.astream_events(
            inputs, version="v2", config=agent_config
    ):
        kind = event["event"]
        # if kind != "on_chat_model_stream":
        # logger.info(event)
        # --- 场景 1: 捕获 LLM 的流式吐字 (打字机效果) ---
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            langgraph_node = event["metadata"].get("langgraph_node", "")
            # logger.info(chunk)
            # 过滤掉工具调用的参数生成过程 (agent 思考参数时 content 为空)
            if chunk.content and langgraph_node != "router":
                ai_output += chunk.content
                payload = json.dumps({"text": chunk.content}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        elif kind == "on_chat_model_end":
            chunk = event["data"]["output"]
            langgraph_node = event["metadata"]["langgraph_node"]
            if chunk.content and langgraph_node != "router":
                logger.info(f"[AI说]: {chunk.content}")
        # --- 场景 2: 捕获工具调用 (可选，用于调试或前端展示 loading) ---
        elif kind == "on_tool_start":
            tool_name = event["name"]
            tool_inputs = event["data"].get("input")
            logger.info(f"[正在调用工具]: {tool_name} 参数: {tool_inputs}")
            # yield f"data: {json.dumps({"text": ' 正在调用工具...'}, ensure_ascii=False)}\n\n"

        # --- 场景 3: 捕获工具返回结果 (可选) ---
        elif kind == "on_tool_end":
            # 有些工具输出可能很长，截断打印日志
            output = str(event["data"].get("output"))
            logger.info(f"[工具返回]: {output[:100]}...")

        # except Exception as e:
        #     # yield f"data: {json.dumps({'error': str(e)})}\n\n"
        #     logger.error(e)
        #     yield f"data: {json.dumps({'text': str(e)})}\n\n"
        # finally:
        # 流式结束
    yield "data: [DONE]\n\n"
    # 存储进数据库
    if ai_output:
        await save_history_to_mysql(question=question, answer=ai_output, uid=uid)


async def draw(ctx: AgentContext, file_name):
    img = ctx.graph.get_graph().draw_mermaid_png()
    img_path = abs_path(f"../asset/graph_pic/{file_name}.png")
    with open(img_path, "wb") as f:
        f.write(img)


async def save_history_to_mysql(question: str, answer: str, uid: str):
    async with db_session() as session:
        # === 查询 (SELECT) ===
        # 以前: room = Room.query.filter_by(id=room_id).first()
        # 现在: 必须构建 SQL 语句 -> 执行 -> 取值

        # Step A: 构建语句 (像写原生 SQL 一样)
        new_history = ChatHistory(question=question, answer=answer, uid=uid)

        # Step B: 执行语句 (必须 await，这是 IO 操作)
        session.add(new_history)

        # Step C: 提取数据
        # scalars() 的意思是：把结果行(Row)转成对象(ORM Object)
        # first() 取第一条，one_or_none() 取一条或空
        # room = result.scalars().one_or_none()


async def get_history_from_mysql(hid: int | None = None, limit: int = 10, page: int = 1):
    async with db_session() as session:
        history_stmt = select(ChatHistory).order_by(desc(ChatHistory.created_at), desc(ChatHistory.id)).limit(limit)
        if hid:
            history_stmt = history_stmt.where(ChatHistory.id < hid)
        else:
            history_stmt = history_stmt.offset(limit * (page - 1))
        history = await session.execute(history_stmt)
        history = history.scalars().all()

        total_count_stmt = select(func.count()).select_from(ChatHistory)
        total_count = await session.execute(total_count_stmt)
        total_count = total_count.scalar()
        return {
            'history': history,
            'count': total_count
        }
