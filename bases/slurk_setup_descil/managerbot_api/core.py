import asyncio
import os

from aiohttp import web
from slurk_setup_descil.managerbot import Managerbot

SLURK_HOST = os.environ.get("SLURK_HOST", "http://localhost")
SLURK_PORT = os.environ.get("SLURK_PORT", "8088")


app = web.Application()
routes = web.RouteTableDef()

_async_tasks = dict()


@routes.post("/register")
async def register(request):
    config = await request.json()
    bot = Managerbot(
        config,
        SLURK_HOST,
        SLURK_PORT,
    )
    task = asyncio.create_task(bot.run())
    _async_tasks[id(bot)] = task
    return web.Response()


app.add_routes(routes)
