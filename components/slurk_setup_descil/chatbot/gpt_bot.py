import asyncio
import logging
import os
import re
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime
from functools import partial

from openai import AsyncAzureOpenAI

from .prompti import prompts

client = None


def connect():
    global client
    if client is None:
        client = AsyncAzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        )
    return client


def gpt_bot(variant):
    return partial(_gpt_bot, variant=variant)


async def _gpt_bot(past_messages, room_number, variant):
    bot_messages = []
    print("VARIANT", variant, flush=True)

    if callable(variant):
        prompt = await variant(room_number)
    else:
        prompt = prompts.get(variant, "")

    bot_messages.append({"role": "system", "content": prompt})

    for msg in past_messages:
        if msg["sender"] == "Ash":
            bot_role = "assistant"
        else:
            bot_role = "user"
        bot_messages.append(
            {"role": bot_role, "content": msg["sender"] + ": " + msg["text"]}
        )

    question_message = {
        "role": "user",
        "content": "You are a human participant in a chat."
        "You are eager to engage in the discussion with the other people."
        "Based on the previous messages, do you think you want to answer now? "
        "Please answer only yes or no."
        "You most of the times want to answer when you are asked a question."
        "You can also answer when you want to add something to the discussion."
        "You can also answer when you want to ask a question."
        "You can also answer when you want to make a comment."
        "You can also answer when you want to make a suggestion."
        "You can also answer when you want to make a remark."
        "You can also answer when you want to make a statement."
        "You can also answer when you want to make a contribution."
        "You can also answer when you want to make a point."
        "You can also answer when you want to make a proposal."
        "You can also answer when you want to make a request."
        "You must not answer to irrelevant messages."
        "You must not answer to messages that ar off topic."
        "You must not answer to messages that are not related to the discussion."
        "You must not answer like a bot or an assistant."
        "You must answer like a human."
        "You must answer in 1-2 sentences"
        "Avoid being too friendly."
        "Avoid being too formal."
        "Avoid answering in sophisticated language."
        "Avoid answering in academic language."
        "Make spelling mistakes."
        "Speak only English.",
    }

    model = os.environ.get("AZURE_OPENAI_MODEL", "css-openai-gpt35")
    temperature = float(os.environ.get("AZURE_OPENAI_MODEL_TEMPERATURE", "0.9"))
    max_tokens = int(os.environ.get("AZURE_OPENAI_MODEL_MAX_TOKENS", "80"))

    client = connect()

    now = datetime.now

    print(now(), "ASK", flush=True)
    response = await client.chat.completions.create(
        model=model,
        messages=[question_message],
        # this is recieving our prompt based on the question parameter and start sequence
        temperature=temperature,  # temperature designates how creative you want the chatbot to be on a scale of 0-1
        max_tokens=max_tokens,  # max_tokens states how long the answer can be
        # top_p=1,  # top_p is another creativity measure, but should be set to 1 when temperature is in use
        # frequency_penalty=0,
        # presence_penalty=0.1,
        stop=["\n"],
    )
    answer = response.choices[0].message.content
    print(now(), "ANSWER", answer, flush=True)

    if answer.lower().rstrip(".") != "yes":
        logging.debug("Irrelevant answer, not answering")

        return answer

    logging.debug("Answering yes")
    response = await client.chat.completions.create(
        model=model,
        messages=bot_messages,
        # this is recieving our prompt based on the question parameter and start sequence
        temperature=temperature,  # temperature designates how creative you want the chatbot to be on a scale of 0-1
        max_tokens=max_tokens,  # max_tokens states how long the answer can be
        # top_p=1,  # top_p is another creativity measure, but should be set to 1 when temperature is in use
        # frequency_penalty=0,
        # presence_penalty=0.1,
        stop=["\n"],
    )

    answer = response.choices[0].message.content
    answer = re.sub(r"^[a-zA-Z]*:\s*", "", answer)

    return answer


def test():
    from openai import AzureOpenAI

    from . import env

    client = AzureOpenAI(
        api_key=env.AZURE_OPENAI_API_KEY,
        api_version=env.AZURE_OPENAI_API_VERSION,
        azure_endpoint=env.AZURE_OPENAI_ENDPOINT,
    )
    temperature = 0.9
    max_tokens = 80

    response = client.chat.completions.create(
        model=env.AZURE_OPENAI_MODEL,
        messages=[
            {"role": "user", "content": "What do you think about global warming?"}
        ],
        # this is recieving our prompt based on the question parameter and start sequence
        temperature=temperature,  # temperature designates how creative you want the chatbot to be on a scale of 0-1
        max_tokens=max_tokens,  # max_tokens states how long the answer can be
        # top_p=1,  # top_p is another creativity measure, but should be set to 1 when temperature is in use
        # frequency_penalty=0,
        # presence_penalty=0.1,
        stop=["\n"],
    )
    return response.json()


if __name__ == "__main__":

    async def inner():
        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        future = loop.run_in_executor(executor, test)
        results = await asyncio.gather(future)
        print(results[0])

    loop = asyncio.get_event_loop()
    tasks = [loop.create_task(inner())]
    loop.run_until_complete(asyncio.wait(tasks))
    loop.close()
