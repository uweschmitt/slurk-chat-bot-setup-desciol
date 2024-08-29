import os

import aiohttp


async def fetch_prompt():
    url = os.environ.get(
        "POLYBOX_URL", "https://polybox.ethz.ch/index.php/s/MAZlGw1ZPBFYUJn/download"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            prompt = await resp.text()
            if resp.status != 200:
                print("REQUEST TO FETCH PROMPT FAILED", resp.reason)
                return ""
            print("GOT PROMPT", resp.status, repr(prompt))
            return prompt
