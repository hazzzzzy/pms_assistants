from typing import Annotated

from fastapi import Header
from pydantic import BaseModel, ConfigDict, Field

from utils.R import R


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
