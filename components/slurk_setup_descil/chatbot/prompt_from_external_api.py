import os

import aiohttp


async def fetch_prompt(room_number):
    base_url = os.environ.get(
        "PROMPT_API_URL", "https://slurkexp.vlab.ethz.ch/api/fullprompt/"
    ).rstrip("/")

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{base_url}/{room_number}", json="") as resp:
            if resp.status != 200:
                print("REQUEST TO FETCH PROMPT FAILED", resp.reason)
                return ""
            data = await resp.json()
            print("GOT PROMPT DATA", repr(data))
            return data["prompt"]
