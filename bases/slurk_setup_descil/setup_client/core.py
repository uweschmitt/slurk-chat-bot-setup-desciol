import os
import traceback
import uuid
from typing import List

import aiohttp
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slurk_setup_descil.slurk_api import (
    create_layout,
    create_room,
    create_room_token,
    create_task,
    create_user,
    get_api_token,
    set_permissions,
)

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

    user_tokens = [
        await create_room_token(api_token, waiting_room_id, task_id, n_users)
        for _ in range(n_users)
    ]

    request_id = uuid.uuid1().hex
    await setup_and_register_concierge(
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


async def setup_and_register_concierge(
    api_token,
    waiting_room_id,
    task_room_id,
    bot_ids,
    redirect_url,
    timeout_waiting_room,
    n_users,
    user_tokens,
    name,
):
    permissions_id = await set_permissions(api_token, CONCIERGE_PERMISSIONS)
    concierge_token = await create_room_token(
        api_token, permissions_id, waiting_room_id, None, None
    )

    concierge_user = await create_user(api_token, name, concierge_token)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{CONCIERGE_URL}/register",
            json=dict(
                api_token=api_token,
                concierge_user=concierge_user,
                concierge_token=concierge_token,
                task_room_id=task_room_id,
                waiting_room_id=waiting_room_id,
                bot_ids=bot_ids,
                redirect_url=redirect_url,
                timeout_waiting_room=timeout_waiting_room,
                user_tokens=user_tokens,
            ),
        ) as r:
            r.raise_for_status()
            print(r)


async def setup_waiting_room(api_token, n_users):
    layout_id = await create_layout(api_token, WAITING_ROOM_LAYOUT)
    waiting_room_id = await create_room(api_token, layout_id)
    task_layout_id = await create_layout(api_token, SIMPLE_LAYOUT)
    task_room_id = await create_room(api_token, task_layout_id)
    task_id = await create_task(api_token, task_layout_id, n_users, "Room")

    return waiting_room_id, task_room_id, task_id


WAITING_ROOM_LAYOUT = {
    "title": "Waiting Room",
    "subtitle": "waiting for other players...",
    "html": [
        {
            "layout-type": "div",
            "id": "image-area",
            "layout-content": [
                {
                    "layout-type": "image",
                    "id": "current-image",
                    "src": "https://media.giphy.com/media/tXL4FHPSnVJ0A/giphy.gif",
                    "width": 500,
                    "height": 400,
                }
            ],
        },
        # {
        # "layout-type": "script",
        # "id": "",
        # "layout-content": 'window.location.replace("http://stackoverflow.com");',
        # },
    ],
    "css": {
        "header, footer": {"background": "#115E91"},
        "#image-area": {"align-content": "left", "margin": "50px 20px 15px"},
    },
    "scripts": {
        "incoming-text": "markdown",
        "incoming-image": "display-image",
        "submit-message": "send-message",
        "print-history": "markdown-history",
    },
    "show_users": False,
    "show_latency": False,
    "read_only": True,
}


SIMPLE_LAYOUT = {
    "title": "Room",
    "scripts": {
        "incoming-text": "display-text",
        "incoming-image": "display-image",
        "submit-message": "send-message",
        "print-history": "plain-history",
    },
    "show_latency": False,
}

MESSAGE_PERMISSIONS = {"send_message": True}


CONCIERGE_PERMISSIONS = {
    "api": True,
    "send_html_message": True,
    "send_privately": True,
    "broadcast": True,
}
