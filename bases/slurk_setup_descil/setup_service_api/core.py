import os
import traceback
import uuid
from typing import List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slurk_setup_descil.setup_service import (
    create_waiting_room_tokens,
    setup_and_register_chatbot,
    setup_and_register_concierge,
    setup_waiting_room,
)
from slurk_setup_descil.slurk_api import get_api_token

app = FastAPI()

SLURK_HOST = os.environ.get("SLURK_HOST", "http://ssdm-docker-dev.ethz.ch:8088")
CONCIERGE_URL = os.environ.get("CONCIERGE_URL", "http://localhost:83")
CHATBOT_URL = os.environ.get("CHATBOT_URL", "http://localhost:84")


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
    waiting_room_timeout_url: str = "https://sis.id.ethz.ch"
    waiting_room_timeout_seconds: int = 5
    experiment_timeout_url: str = "https://sis.id.ethz.ch"
    experiment_timeout_seconds: int = 20
    api_token: str = "666"


@app.post("/setup")
async def setup(setup_data: SetupData):
    """
    setup an experiment with *n_users* using a bot *bot_id*.
    """
    api_token = await get_api_token()
    submittted_api_token = setup_data.api_token
    if api_token != submittted_api_token:
        raise HTTPException(status_code=401, detail="api token invalid.")

    n_users = setup_data.n_users
    bot_ids = setup_data.bot_ids
    waiting_room_timeout_url = setup_data.waiting_room_timeout_url
    waiting_room_timeout_seconds = setup_data.waiting_room_timeout_seconds
    experiment_timeout_url = setup_data.experiment_timeout_url
    experiment_timeout_seconds = setup_data.experiment_timeout_seconds

    print("TOKEN", api_token, flush=True)

    waiting_room_id, task_room_id, task_id = await setup_waiting_room(
        SLURK_HOST, api_token, n_users
    )

    user_tokens = await create_waiting_room_tokens(
        SLURK_HOST, api_token, waiting_room_id, task_id, n_users
    )

    request_id = uuid.uuid1().hex
    await setup_and_register_concierge(
        SLURK_HOST,
        CONCIERGE_URL,
        api_token,
        waiting_room_id,
        task_room_id,
        bot_ids,
        waiting_room_timeout_url,
        waiting_room_timeout_seconds,
        experiment_timeout_url,
        experiment_timeout_seconds,
        n_users,
        user_tokens,
        f"concierge_bot_{request_id}",
    )

    await setup_and_register_chatbot(
        SLURK_HOST,
        CHATBOT_URL,
        "bot",
        api_token,
        task_room_id,
    )

    return dict(
        user_tokens=user_tokens,
        request_id=request_id,
        task_id=task_id,
        task_room_id=task_room_id,
        waiting_room_id=waiting_room_id,
    )
