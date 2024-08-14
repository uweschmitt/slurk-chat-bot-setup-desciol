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
    print(repr(api_token), repr(uri), repr(json))
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
    return os.environ.get("ACCESS_TOKEN", "00000000-0000-0000-0000-000000000000")
