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
    concierge_url,
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
            f"{concierge_url}/register",
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


async def create_waiting_room_tokens(api_token, waiting_room_id, task_id, n_users):
    return [
        await create_room_token(api_token, waiting_room_id, task_id, n_users)
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
                }
            ],
        },
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
