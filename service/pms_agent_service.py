import datetime
import io
import json
import logging
import uuid

import pandas as pd
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import desc, func, select, text

from config.config import settings
from core.agent_context import AgentContext
from core.agent_prompt import USER_PROMPT, TITLE_GENERATE_SYSTEM_PROMPT, ROUTER_PROMPT
from core.db import db_session, assistants_async_session_maker, pms_async_session_maker
from db_models.models import ChatHistory, UserThread, PresetQuestion
from utils.R import R
from utils.abs_path import abs_path

logger = logging.getLogger(__name__)


async def parse_excel(file):
    file_name, file_context, err = None, '', None
    try:
        if file:
            file_name = file.filename
            if not file_name.endswith(('.xlsx', '.xls')):
                raise Exception('只支持 xlsx/xls 文件')

            content = await file.read()
            if len(content) > settings.MAX_FILE_SIZE_BYTES:
                raise Exception(f"文件实际大小超过限制 ({settings.MAX_FILE_SIZE_BYTES / (1024 * 1024)} MB)")

            # 解析 Excel
            df = pd.read_excel(io.BytesIO(content))
            df = df.fillna("")  # 填充空值
            file_md = df.to_markdown(index=False)

            file_context = f"用户上传的文件内容:\n{file_md}\n"
    except Exception as e:
        err = str(e)
    return file_name, file_context, err


async def chat(ctx: AgentContext, file, question, thread_id, hotel_id, user_id):
    file_name, file_content, err = await parse_excel(file)
    if err:
        yield f"data: {json.dumps({'type': 'delta', "text": err}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return
    is_new_session = not bool(thread_id)
    thread_id = thread_id if thread_id else str(uuid.uuid4())
    thread_id_json = json.dumps({"type": 'meta', 'thread_id': thread_id}, ensure_ascii=False)
    yield f"data: {thread_id_json}\n\n"

    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inputs = {
        "messages": [
            SystemMessage(
                id="sys_prompt", content=ROUTER_PROMPT
            ),
            HumanMessage(
                content=USER_PROMPT.format(current_time, hotel_id, user_id, file_content, question)
            ),
        ]
    }
    agent_config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,
    }
    ai_output = ""
    try:
        async for event in ctx.graph.astream_events(
                inputs, version="v2", config=agent_config
        ):
            kind = event["event"]
            # --- 场景 1: 捕获 LLM 的流式吐字 (打字机效果) ---
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                langgraph_node = event["metadata"].get("langgraph_node", "")
                # 过滤掉工具调用的参数生成过程 (agent 思考参数时 content 为空)
                if chunk.content and langgraph_node in {"summarize", "chat_agent"}:
                    ai_output += chunk.content
                    yield f"data: {json.dumps({'type': 'delta', "text": chunk.content}, ensure_ascii=False)}\n\n"
                # elif chunk.content and langgraph_node == 'rag_sql_agent':
                #     yield f"data: {json.dumps({'type': 'processing', "text": '正在整理结果'}, ensure_ascii=False)}\n\n"

            # elif kind == "on_chat_model_end":
            #     chunk = event["data"]["output"]
            #     langgraph_node = event["metadata"]["langgraph_node"]
            # if chunk.content and langgraph_node != "router":
            #     logger.info(chunk)
            # --- 场景 2: 捕获工具调用 (可选，用于调试或前端展示 loading) ---
            elif kind == "on_tool_start":
                # tool_name = event["name"]
                # tool_inputs = event["data"].get("input")
                # logger.info(f"[正在调用工具]: {tool_name} 参数: {tool_inputs}")
                yield f"data: {json.dumps({'type': 'processing', "text": '正在查询数据'}, ensure_ascii=False)}\n\n"

            # --- 场景 3: 捕获工具返回结果 (可选) ---
            elif kind == "on_tool_end":
                # 有些工具输出可能很长，截断打印日志
                # output = str(event["data"].get("output"))
                yield f"data: {json.dumps({'type': 'processing', "text": '正在校验数据'}, ensure_ascii=False)}\n\n"

        if is_new_session:
            await save_title(llm=ctx.llm,
                             question=question,
                             answer=ai_output,
                             user_id=user_id,
                             thread_id=thread_id,
                             hotel_id=hotel_id)

        # 存储进数据库
        history_id = None
        if ai_output:
            async with assistants_async_session_maker() as session:
                new_history = ChatHistory(question=question, answer=ai_output, thread_id=thread_id, file_name=file_name)

                session.add(new_history)
                await session.commit()
                await session.refresh(new_history)
                history_id = new_history.id
        if history_id:
            history_id_json = json.dumps({"type": 'meta', 'history_id': history_id}, ensure_ascii=False)
            yield f"data: {history_id_json}\n\n"
    except Exception as e:
        logger.error(e, exc_info=True)
        yield f"data: {json.dumps({'type': 'delta', 'text': '\n\n[系统] 服务端发生异常，请稍后重试。'})}\n\n"
    finally:
        yield "data: [DONE]\n\n"


async def generate_session_title(llm: BaseChatModel, question: str, answer: str) -> str:
    """
    根据用户的第一条消息生成简短的会话标题。
    """

    prompt = ChatPromptTemplate.from_template(TITLE_GENERATE_SYSTEM_PROMPT)

    # 2. 组装链 (Prompt -> LLM -> String)
    # 使用 StrOutputParser 直接拿回字符串，而不是 AIMessage 对象
    chain = prompt | llm | StrOutputParser()

    try:
        # 3. 执行
        title = await chain.ainvoke({"question": question, 'answer': answer})

        # 4. 兜底清洗 (防止 LLM 还是加了引号或空格)
        return title.strip().strip('"').strip("《").strip("》")

    except Exception as e:
        logger.error(f"生成标题失败: {e}", exc_info=True)
        # 如果 LLM 挂了，返回默认标题，不影响主流程
        return question[:15] if question else "新会话"


async def draw(ctx: AgentContext, file_name):
    img = ctx.graph.get_graph().draw_mermaid_png()
    img_path = abs_path(f"../asset/graph_pic/{file_name}.png")
    with open(img_path, "wb") as f:
        f.write(img)
    return R.success()


async def save_title(llm: BaseChatModel, question: str, answer: str, user_id: int, thread_id: str, hotel_id: int):
    question = question[:100] if question else '用户问题为空'
    answer = answer[:100] if answer else 'AI回复为空'
    title = await generate_session_title(llm=llm, question=question, answer=answer)
    async with db_session() as session:
        new_thread = UserThread(user_id=user_id, thread_id=thread_id, title=title, hotel_id=hotel_id)
        session.add(new_thread)


async def get_history_feed(history_id: int | None = None, limit: int = 10, thread_id: str | None = None):
    async with db_session() as session:
        history_stmt = select(ChatHistory).where(ChatHistory.thread_id == thread_id).order_by(desc(ChatHistory.created_at),
                                                                                              desc(ChatHistory.id)).limit(limit + 1)
        if history_id:
            history_stmt = history_stmt.where(ChatHistory.id < history_id)
        history = await session.execute(history_stmt)
        history = history.scalars().all()

        has_more = False
        if len(history) > limit:
            has_more = True
            history = history[:-1]

        return R.success(
            {
                'data': history,
                'has_more': has_more
            }
        )


async def get_history_table(limit: int = 10, page: int = 1):
    async with db_session() as session:
        history_stmt = select(ChatHistory).order_by(desc(ChatHistory.created_at), desc(ChatHistory.id)).limit(limit).offset(limit * (page - 1))
        history = await session.execute(history_stmt)
        history = history.scalars().all()

        total_count_stmt = select(func.count()).select_from(ChatHistory)
        total_count = await session.execute(total_count_stmt)
        total_count = total_count.scalar()
        return R.success(
            {
                'data': history,
                'total_count': total_count
            }
        )


async def get_feedback(history_id: int, feedback: int = 0):
    async with db_session() as session:
        history_stmt = select(ChatHistory).where(ChatHistory.id == history_id)
        history = await session.execute(history_stmt)
        history = history.scalar_one_or_none()
        if history:
            history.feedback = feedback
            return R.success()
        else:
            return R.fail('未找到对应消息记录')


async def get_user_thread(user_id: int, hotel_id: int, limit: int = 10, before_id: int = None):
    async with db_session() as session:
        thread_stmt = select(UserThread).where(UserThread.user_id == user_id, UserThread.hotel_id == hotel_id)
        if before_id is not None:
            thread_stmt = thread_stmt.where(UserThread.id < before_id)

        thread_stmt = thread_stmt.order_by(UserThread.created_at.desc()).limit(limit + 1)
        thread = await session.execute(thread_stmt)
        thread = thread.scalars().all()

        has_more = False
        if len(thread) > limit:
            has_more = True
            thread = thread[:-1]
        return R.success({
            'data': thread,
            'has_more': has_more
        })


async def get_preset_question(limit: int = 10, page: int = 1):
    async with db_session() as session:
        preset_question_stmt = select(PresetQuestion).order_by(PresetQuestion.created_at.desc()).offset((page - 1) * limit).limit(limit)
        preset_question = await session.scalars(preset_question_stmt)
        preset_question = preset_question.all()

        total_count_stmt = select(func.count()).select_from(PresetQuestion)
        total_count = await session.execute(total_count_stmt)
        total_count = total_count.scalar()

        return R.success({
            'data': preset_question,
            'total_count': total_count
        })


async def get_all_user():
    # 阶段 1：获取去重后的 user_id
    async with assistants_async_session_maker() as session:
        all_user_stmt = select(UserThread.user_id).distinct()
        result = await session.execute(all_user_stmt)
        all_user = result.scalars().all()

    if not all_user:
        return R.success({'data': [], 'total_count': 0})

    # 阶段 2：跨库查询 staff 信息
    async with pms_async_session_maker() as pms_session:
        # 使用 text() 并通过参数绑定防止注入
        # 注意：部分驱动支持 tuple(all_user) 直接映射到 IN (:ids)
        sql = text("SELECT id, name FROM tb_staff WHERE id IN :user_ids")
        pms_result = await pms_session.execute(sql, {"user_ids": tuple(all_user)})

        # 转换为字典列表
        staff_list = [
            {"id": row.id, "name": row.name}
            for row in pms_result.mappings()
        ]

    return R.success({
        'data': staff_list,
        'total_count': len(staff_list)
    })
