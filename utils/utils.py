import json
import logging
from typing import Annotated

from fastapi import Header
from pydantic import BaseModel, ConfigDict, Field

from .R import R

logger = logging.getLogger(__name__)


class AuthContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hotel_id: int = Field(..., ge=1)
    uid: int = Field(..., ge=1)


def get_user_info_from_headers(
        hotel_id: Annotated[int | None, Header(alias="hotel_id")] = None,
        uid: Annotated[int | None, Header(alias="uid")] = None,
) -> AuthContext:
    if hotel_id is None or uid is None:
        raise R.fail('请求头中无hotel_id或uid')
        # raise HTTPException(status_code=401, detail="missing hotel_i or uid in headers")
    return AuthContext(hotel_id=hotel_id, uid=uid)


def get_valid_json(string: str) -> dict:
    try:
        first_index = string.index('{')
        last_index = string.rindex('}')
        if first_index == -1 or last_index == -1 or first_index > last_index:
            logger.error('未在agent节点返回内容中匹配到json格式的数据')
            raise Exception
        valid_json_string = string[first_index:last_index + 1]
        valid_json = json.loads(valid_json_string)
        return valid_json
    except Exception as e:
        logger.error(str(e))
        return '数据处理出错，请联系管理员'
