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

_async_tasks = dict()


@routes.post("/register")
async def register(request):
    concierge_config = await request.json()
    print("-------")
    print("CONFIG", concierge_config, flush=True)
    print("-------")
    print("HANDLER", asyncio.get_event_loop().get_exception_handler(), flush=True)
    bot = ConciergeBot(
        concierge_config,
        SLURK_HOST,
        SLURK_PORT,
    )
    task = asyncio.create_task(bot.run())
    _async_tasks[id(bot)] = task
    return web.Response()


app.add_routes(routes)
