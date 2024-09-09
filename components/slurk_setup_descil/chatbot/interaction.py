from . import polybox_prompt, prompt_from_external_api
from .gpt_bot import gpt_bot

"""
0=EchoBot
1=GptBot1 / chatbot baseline
2=GptBot2 / repetition
3=GptBot3 / imitation -> Bot gets prompt from slurkexp.
4=GptBot4 / personalization
5=GptBot5 / combination
"""

# completion = client.chat.completions.create()
stop = "\n"


async def echo_bot(past_messages, room_number):
    if past_messages:
        return past_messages[-1]["text"]
    return None


bot_variants = {
    0: echo_bot,
    1: gpt_bot(1),
    2: gpt_bot(2),
    3: gpt_bot(prompt_from_external_api.fetch_prompt(3)),
    4: gpt_bot(prompt_from_external_api.fetch_prompt(4)),
    5: gpt_bot(prompt_from_external_api.fetch_prompt(5)),
    6: gpt_bot(6),
    7: gpt_bot(polybox_prompt.fetch_prompt),
}


async def generate_bot_message(bot_id, past_messages, room_number):
    return await bot_variants[bot_id](past_messages, room_number)
