import asyncio
import logging
import os

from aiohttp import web
from slurk_setup_descil.concierge_plus import ConciergeBot

LOG = logging.getLogger(__name__)


SLURK_HOST = os.environ.get("SLURK_HOST", "http://localhost")
SLURK_PORT = os.environ.get("SLURK_PORT", "8088")


app = web.Application()
routes = web.RouteTableDef()

async_tasks = dict()


@routes.post("/register")
async def register(request):
    concierge_config = await request.json()
    for p in asyncio.all_tasks():
        print("REST HANDLER", p, flush=True)
    print("CONFIG", concierge_config, flush=True)
    bot = ConciergeBot(
        concierge_config,
        SLURK_HOST,
        SLURK_PORT,
    )
    task = asyncio.create_task(bot.run())
    async_tasks[id(bot)] = task
    return web.Response()


app.add_routes(routes)
