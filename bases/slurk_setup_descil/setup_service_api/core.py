import os
import traceback
import uuid
from typing import List

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slurk_setup_descil.setup_service import (
    create_waiting_room_tokens,
    setup_and_register_concierge,
    setup_waiting_room,
)
from slurk_setup_descil.slurk_api import get_api_token

app = FastAPI()

SLURK_HOST = os.environ.get("SLURK_HOST", "http://ssdm-docker-dev.ethz.ch:8088")
TOKEN_SERVICE_URL = os.environ.get("TOKEN_SERVICE_URL", "http://localhost:83/token")
CONCIERGE_URL = os.environ.get("CONCIERGE_URL", "http://localhost:83")


@app.exception_handler(Exception)
async def http_exception_handler(request: Request, exc: Exception):
    # Do some logging here
    return JSONResponse(
        {
            "error": str(exc),
            "traceback": "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            ),
        }
    )


class SetupData(BaseModel):
    n_users: int = 2
    bot_ids: List[int] = [
        1,
    ]
    redirect_url: str = "https://sis.id.ethz.ch"
    timeout_waiting_room: int = 5


@app.post("/setup")
async def setup(setup_data: SetupData):
    """
    setup an experiment with *n_users* using a bot *bot_id*.
    """
    n_users = setup_data.n_users
    bot_ids = setup_data.bot_ids
    redirect_url = setup_data.redirect_url
    timeout_waiting_room = setup_data.timeout_waiting_room

    api_token = await get_api_token()
    waiting_room_id, task_room_id, task_id = await setup_waiting_room(
        api_token, n_users
    )

    user_tokens = create_waiting_room_tokens(
        api_token, waiting_room_id, task_id, n_users
    )

    request_id = uuid.uuid1().hex
    await setup_and_register_concierge(
        CONCIERGE_URL,
        api_token,
        waiting_room_id,
        task_room_id,
        bot_ids,
        redirect_url,
        timeout_waiting_room,
        n_users,
        user_tokens,
        f"concierge_bot_{request_id}",
    )

    return dict(
        user_tokens=user_tokens,
        request_id=request_id,
        task_id=task_id,
        task_room_id=task_room_id,
        waiting_room_id=waiting_room_id,
    )
