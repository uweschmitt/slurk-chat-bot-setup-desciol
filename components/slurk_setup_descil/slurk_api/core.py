import os
from contextlib import asynccontextmanager

import aiohttp


@asynccontextmanager
async def get(api_token, uri):
    headers = {
        "Authorization": f"Bearer {api_token}",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(uri, headers=headers) as resp:
            yield resp


@asynccontextmanager
async def post(api_token, uri, json=None):
    print(repr(api_token), repr(uri), repr(json), flush=True)
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(uri, headers=headers, json=json) as resp:
            yield resp


@asynccontextmanager
async def delete(api_token, uri, etag=None):
    headers = {
        "Authorization": f"Bearer {api_token}",
    }
    if etag:
        headers["If-Match"] = etag
    async with aiohttp.ClientSession() as session:
        async with session.delete(uri, headers=headers) as resp:
            yield resp


async def set_permissions(uri, api_token, permissions):
    async with post(api_token, uri + "/slurk/api/permissions", permissions) as r:
        r.raise_for_status()
        return (await r.json())["id"]


async def create_user(uri, api_token, name, token_id):
    async with post(
        api_token, uri + "/slurk/api/users", dict(name=name, token_id=token_id)
    ) as r:
        r.raise_for_status()
        return (await r.json())["id"]


async def create_room_token(
    uri, api_token, permissions_id, room_id, task_id=None, n_users=None
):
    json = dict(
        permissions_id=permissions_id,
        room_id=room_id,
    )
    if task_id is not None:
        json["task_id"] = task_id
    if n_users is not None:
        json["registrations_left"] = n_users
    async with post(api_token, uri + "/slurk/api/tokens", json) as r:
        r.raise_for_status()
        return (await r.json())["id"]


async def create_layout(uri, api_token, layout):
    async with post(api_token, uri + "/slurk/api/layouts", layout) as r:
        r.raise_for_status()
        return (await r.json())["id"]


async def create_room(uri, api_token, layout_id):
    async with post(
        api_token, uri + "/slurk/api/rooms", dict(layout_id=layout_id)
    ) as r:
        return (await r.json())["id"]


async def create_task(uri, api_token, layout_id, num_users, name):
    async with post(
        api_token,
        uri + "/slurk/api/tasks",
        {"name": name, "num_users": num_users, "layout_id": layout_id},
    ) as r:
        r.raise_for_status()
        return (await r.json())["id"]


async def get_api_token():
    return os.environ.get("ADMIN_TOKEN", "00000000-0000-0000-0000-000000000000")


async def redirect_user(
    slurk_uri, token, user_id, task_id, from_room_id, to_room_id, sio
):
    """
    for eacch user create room with layout
    add users to the rooms
    show message
    """

    print(user_id, flush=True)
    etag = await get_user_etag(slurk_uri, token, user_id)
    await remove_user_from_room(slurk_uri, token, user_id, from_room_id, etag)
    await add_user_to_room(slurk_uri, token, user_id, to_room_id)
    await sio.emit("room_created", {"room": to_room_id, "task": task_id})


async def remove_user_from_room(slurk_uri, token, user_id, room_id, etag):
    """Remove user from (waiting) room.

    :param user_id: Identifier of user.
    :type user_id: int
    :param room_id: Identifier of room.
    :type room_id: int
    :param etag: Used for request validation.
    :type etag: str
    """
    async with delete(
        token,
        f"{slurk_uri}/slurk/api/users/{user_id}/rooms/{room_id}",
        etag=etag,
    ) as response:
        if not response.ok:
            response.raise_for_status()


async def create_forward_room(slurk_uri, token, forward_url):
    ROOM_LAYOUT = {
        "title": "Forward Room",
        "subtitle": "Timeout....",
        "html": [
            {
                "layout-type": "script",
                "id": "",
                "layout-content": f"window.location.replace({forward_url!r} + '?token=' + token.id);",
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

    async with post(token, f"{slurk_uri}/slurk/api/layouts", ROOM_LAYOUT) as r:
        r.raise_for_status()
        rj = await r.json()
        layout_id = rj["id"]

    async with post(
        token, f"{slurk_uri}/slurk/api/rooms", dict(layout_id=layout_id)
    ) as r:
        return (await r.json())["id"]


async def get_user_etag(slurk_uri, token, user):
    async with get(token, f"{slurk_uri}/slurk/api/users/{user}") as response:
        if not response.ok:
            response.raise_for_status()
        return response.headers["ETag"]


async def add_user_to_room(slurk_uri, token, user_id, room_id):
    """Let user join task room.

    :param user_id: Identifier of user.
    :type user_id: int
    :param room_id: Identifier of room.
    :type room_id: int
    """
    async with post(
        token,
        f"{slurk_uri}/slurk/api/users/{user_id}/rooms/{room_id}",
    ) as response:
        if not response.ok:
            response.raise_for_status()
        return response.headers["ETag"]


async def setup_chat_room(uri, api_token, n_users):
    chat_layout_id = await create_layout(uri, api_token, CHAT_LAYOUT)
    chat_room_id = await create_room(uri, api_token, chat_layout_id)
    chat_task_id = await create_task(uri, api_token, chat_layout_id, n_users, "Room")
    return chat_room_id, chat_task_id


CHAT_LAYOUT = {
    "title": "Room",
    "scripts": {
        "incoming-text": "display-text",
        "incoming-image": "display-image",
        "submit-message": "send-message",
        "print-history": "plain-history",
        "typing-users": "typing-users",
    },
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
