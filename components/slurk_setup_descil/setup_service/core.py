import aiohttp
from slurk_setup_descil.slurk_api import (
    create_layout,
    create_room,
    create_room_token,
    create_task,
    create_user,
    set_permissions,
)


async def setup_and_register_concierge(
    uri,
    concierge_url,
    api_token,
    waiting_room_id,
    bot_ids,
    waiting_room_timeout_url,
    waiting_room_timeout_seconds,
    chat_room_timeout_url,
    chat_room_timeout_seconds,
    n_users,
    user_tokens,
    name,
):
    permissions_id = await set_permissions(uri, api_token, CONCIERGE_PERMISSIONS)
    concierge_token = await create_room_token(
        uri, api_token, permissions_id, waiting_room_id, None, None
    )

    concierge_user = await create_user(uri, api_token, name, concierge_token)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{concierge_url}/register",
            json=dict(
                api_token=api_token,
                concierge_token=concierge_token,
                concierge_user=concierge_user,
                waiting_room_id=waiting_room_id,
                bot_ids=bot_ids,
                waiting_room_timeout_url=waiting_room_timeout_url,
                waiting_room_timeout_seconds=waiting_room_timeout_seconds,
                user_tokens=user_tokens,
                chat_room_timeout_url=chat_room_timeout_url,
                chat_room_timeout_seconds=chat_room_timeout_seconds,
            ),
        ) as r:
            r.raise_for_status()
            print(r)


async def setup_waiting_room(uri, api_token, n_users, timeout_seconds):
    waiting_room_layout_id = await create_layout(uri, api_token, WAITING_ROOM_LAYOUT)
    waiting_room_id = await create_room(uri, api_token, waiting_room_layout_id)
    waiting_room_task_id = await create_task(
        uri, api_token, waiting_room_layout_id, n_users, "Waiting Room"
    )

    return waiting_room_id, waiting_room_task_id


async def create_waiting_room_tokens(uri, api_token, waiting_room_id, task_id, n_users):
    permissions_id = await set_permissions(uri, api_token, MESSAGE_PERMISSIONS)
    return [
        await create_room_token(
            uri, api_token, permissions_id, waiting_room_id, task_id, n_users
        )
        for _ in range(n_users)
    ]


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
                },
            ],
        }
    ],
    "css": {
        "header, footer": {"background": "#11915E"},
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
    "read_only": False,
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
