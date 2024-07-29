from contextlib import asynccontextmanager

import aiohttp


@asynccontextmanager
async def get(*a, **kw):
    print("GET", a, kw, flush=True)
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=10)
    ) as session:
        async with session.get(*a, **kw) as resp:
            yield resp


@asynccontextmanager
async def post(api_token, endpoint, json):
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(endpoint, headers=headers, json=json) as resp:
            yield resp


@asynccontextmanager
async def delete(*a, **kw):
    print("DELETE", a, kw, flush=True)
    async with aiohttp.ClientSession() as session:
        async with session.delete(*a, **kw) as resp:
            yield resp


async def set_permissions(api_token, permissions):
    async with post(api_token, "/slurk/api/permissions", permissions) as r:
        r.raise_for_status()
        return (await r.json())["id"]


async def create_user(api_token, name, token_id):
    async with post(
        api_token, "/slurk/api/users", dict(name=name, token_id=token_id)
    ) as r:
        r.raise_for_status()
        return (await r.json())["id"]


async def create_room_token(api_token, permissions_id, room_id, task_id, n_users):
    async with post(
        api_token,
        "/slurk/api/tokens",
        dict(
            permissions_id=permissions_id,
            room_id=room_id,
            registrations_left=n_users,
            task_id=task_id,
        ),
    ) as r:
        r.raise_for_status()
        return (await r.json())["id"]


async def create_layout(api_token, layout):
    async with post(api_token, "/slurk/api/layouts", layout) as r:
        r.raise_for_status()
        return (await r.json())["id"]


async def create_room(api_token, layout_id):
    async with post(api_token, "/slurk/api/rooms", dict(layout_id=layout_id)) as r:
        return (await r.json())["id"]


async def create_task(api_token, layout_id, num_users, name):
    async with post(
        api_token,
        "/slurk/api/tasks",
        {"name": name, "num_users": num_users, "layout_id": layout_id},
    ) as r:
        r.raise_for_status()
        return (await r.json())["id"]


async def get_api_token():
    return "00000000-0000-0000-0000-000000000000"
