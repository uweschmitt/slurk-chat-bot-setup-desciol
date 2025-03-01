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
    setup,
):
    api_token = setup["api_token"]
    permissions_id = await set_permissions(uri, api_token, CONCIERGE_PERMISSIONS)
    concierge_token = await create_room_token(
        uri, api_token, permissions_id, setup["waiting_room_id"], None, None
    )

    concierge_user = await create_user(
        uri, api_token, setup["waiting_room_conciergebot_name"], concierge_token
    )
    setup["concierge_token"] = concierge_token
    setup["concierge_user"] = concierge_user

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{concierge_url}/register",
            json=setup,
        ) as r:
            r.raise_for_status()
            print(r)


async def setup_waiting_room(uri, api_token, num_users, timeout_seconds):
    waiting_room_layout_id = await create_layout(uri, api_token, WAITING_ROOM_LAYOUT)
    waiting_room_id = await create_room(uri, api_token, waiting_room_layout_id)
    waiting_room_task_id = await create_task(
        uri, api_token, waiting_room_layout_id, num_users, "Waiting Room"
    )

    return waiting_room_id, waiting_room_task_id


async def setup_chat_room(uri, api_token, num_users):
    chat_layout_id = await create_layout(uri, api_token, CHAT_LAYOUT)
    chat_room_id = await create_room(uri, api_token, chat_layout_id)
    chat_task_id = await create_task(uri, api_token, chat_layout_id, num_users, "Room")
    return chat_room_id, chat_task_id


async def create_waiting_room_tokens(
    uri, api_token, waiting_room_id, task_id, num_users
):
    permissions_id = await set_permissions(uri, api_token, MESSAGE_PERMISSIONS)
    return [
        await create_room_token(
            uri, api_token, permissions_id, waiting_room_id, task_id, num_users
        )
        for _ in range(num_users)
    ]


CHAT_LAYOUT = {
    "title": "Room",
    "scripts": {
        "incoming-text": "display-text",
        "incoming-image": "display-image",
        "submit-message": "send-message",
        "print-history": "plain-history",
        "typing-users": "typing-users",
    },
    "html": [
        {
            "layout-type": "script",
            "id": "",
            "layout-content": """
                 $("#text").focus();
                 function handle_broadcast(payload) {
                    if (payload['type'] != 'time_left_chatroom') return;
                    if (payload['room'] != self_room) return;
                    const time_left = payload['time_left'];
                    const minutes = Math.floor(time_left / 60);
                    const seconds = time_left % 60;
                    var msg = "";
                    if (minutes > 0) {
                        msg = `${minutes} minutes and ${seconds} seconds left`;
                    } else if (seconds > 0) {
                        msg = `${seconds} seconds left`;
                    }
                    else {
                        msg = '';
                    }
                    $("#subtitle")[0].innerText = msg;
                 }
                 socket.on("client_broadcast", handle_broadcast);
    """,
        },
    ],
    "css": {
        "header, footer": {"background": "#115E91"},
        "#current-users": {"color": "#EEE!important"},
        "#timeout-message": {"margin": "2em"},
        "#text": {"padding-top": "0.5em!important"},
        "#content": {"min-width": "100%!important"},
        "#sidebar": {"display": "none"},
    },
    "show_latency": False,
}


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
        },
        {
            "layout-type": "script",
            "id": "extra-script",
            "layout-content": "console.log('HI')",
        },
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
        "typing-users": "typing-users",
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
