import os
from functools import partial

import aiohttp


async def _fetch_prompt(variant, room_number):
    base_url = os.environ.get(
        "PROMPT_API_URL",
        "https://slurkexp.vlab.ethz.ch/api/fullprompt/",
        json=dict(variant=variant),
    ).rstrip("/")

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{base_url}/{room_number}", json="") as resp:
            if resp.status != 200:
                print("REQUEST TO FETCH PROMPT FAILED", resp.reason)
                return ""
            data = await resp.json()
            print("GOT PROMPT DATA", repr(data))
            return data["prompt"]


async def fetch_prompt(variant):
    return partial(fetch_prompt, variant=variant)
