from fastapi import APIRouter
from pydantic import BaseModel

# 创建路由器，相当于 flask_blueprint = Blueprint(...)
user_router = APIRouter(prefix="/agent", tags=["Text2SQL"])


class AgentRequest(BaseModel):
    query: str


@user_router.post("/generate")
async def generate(req: AgentRequest):
    return {"msg": f"正在为 '{req.query}' 生成 SQL..."}


@user_router.post("/execute")
async def execute(sql: str):
    return {"msg": f"正在执行 SQL: {sql}"}
