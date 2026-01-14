import datetime
import json
import logging
import uuid

from fastapi import BackgroundTasks
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import desc, func, select

from core.agent_context import AgentContext
from core.agent_prompt import AGENT_SYSTEM_PROMPT, AGENT_USER_PROMPT
from core.db import db_session, async_session_maker
from db_models.models import ChatHistory, UserThread, PresetQuestion
from utils.R import R
from utils.abs_path import abs_path

logger = logging.getLogger(__name__)


async def chat(ctx: AgentContext, background_tasks: BackgroundTasks, question, thread_id, hotel_id, user_id):
    is_new_session = not bool(thread_id)
    thread_id = thread_id if thread_id else str(uuid.uuid4())
    thread_id_json = json.dumps({"type": 'meta', 'thread_id': thread_id}, ensure_ascii=False)
    yield f"data: {thread_id_json}\n\n"

    current_time = datetime.datetime.now().strftime("%Y-%m-%d")
    inputs = {
        "messages": [
            SystemMessage(
                id="sys_prompt", content=AGENT_SYSTEM_PROMPT.format(hotel_id)
            ),
            HumanMessage(
                content=AGENT_USER_PROMPT.format(current_time, hotel_id, user_id, question)
            ),
        ]
    }
    agent_config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,
    }
    ai_output = ""
    # todo: 生产环境需要把异常捕获还原
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
                payload = json.dumps({'type': 'delta', "text": chunk.content}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        elif kind == "on_chat_model_end":
            chunk = event["data"]["output"]
            langgraph_node = event["metadata"]["langgraph_node"]
            # if chunk.content and langgraph_node != "router":
            # logger.info(f"[AI说]: {chunk.content}")
        # --- 场景 2: 捕获工具调用 (可选，用于调试或前端展示 loading) ---
        elif kind == "on_tool_start":
            tool_name = event["name"]
            tool_inputs = event["data"].get("input")
            # logger.info(f"[正在调用工具]: {tool_name} 参数: {tool_inputs}")
            # yield f"data: {json.dumps({"text": ' 正在调用工具...'}, ensure_ascii=False)}\n\n"

        # --- 场景 3: 捕获工具返回结果 (可选) ---
        elif kind == "on_tool_end":
            # 有些工具输出可能很长，截断打印日志
            output = str(event["data"].get("output"))
            # logger.info(f"[工具返回]: {output[:100]}...")

        # except Exception as e:
        #     # yield f"data: {json.dumps({'error': str(e)})}\n\n"
        #     logger.error(e)
        #     yield f"data: {json.dumps({'type': 'delta','error': str(e)})}\n\n"
        # finally:
        # 流式结束
    if is_new_session:
        background_tasks.add_task(
            save_title,
            llm=ctx.llm,
            question=question,
            answer=ai_output,
            user_id=user_id,
            thread_id=thread_id,
            hotel_id=hotel_id
        )
    # 存储进数据库
    history_id = None
    if ai_output:
        async with async_session_maker() as session:
            new_history = ChatHistory(question=question, answer=ai_output, user_id=user_id, thread_id=thread_id)
            session.add(new_history)
            await session.commit()
            await session.refresh(new_history)
            history_id = new_history.id
    if history_id:
        history_id_json = json.dumps({"type": 'meta', 'history_id': history_id}, ensure_ascii=False)
        yield f"data: {history_id_json}\n\n"
    yield "data: [DONE]\n\n"


async def generate_session_title(llm: BaseChatModel, question: str, answer: str) -> str:
    """
    根据用户的第一条消息生成简短的会话标题。
    """

    # 1. 定义 Prompt
    # 关键点：限制字数，强制要求不加标点，不加解释
    prompt = ChatPromptTemplate.from_template(
        """
        你是一个专业的对话总结助手。请根据用户的输入内容，生成一个极简短的会话标题。

        要求：
        1. 长度控制在 10-15 个字以内。
        2. 不要包含任何标点符号（如句号、引号）。
        3. 不要包含“标题”、“关于”等前缀词。
        4. 如果输入是无意义的问候（如“你好”），返回“新会话”。
        5. 直接输出结果，不要有任何客套话。

        用户输入: {question}
        AI输出：{answer}
        """
    )

    # 2. 组装链 (Prompt -> LLM -> String)
    # 使用 StrOutputParser 直接拿回字符串，而不是 AIMessage 对象
    chain = prompt | llm | StrOutputParser()

    try:
        # 3. 执行
        title = await chain.ainvoke({"question": question, 'answer': answer})

        # 4. 兜底清洗 (防止 LLM 还是加了引号或空格)
        return title.strip().strip('"').strip("《").strip("》")

    except Exception as e:
        print(f"生成标题失败: {e}")
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
