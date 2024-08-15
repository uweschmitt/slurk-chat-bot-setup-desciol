import logging
import os
import re
from random import randint
from time import sleep

from bots.chatbot.lib.prompti import prompts
from openai import AzureOpenAI, OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
model = "gpt-3.5-turbo-1106"

if os.getenv("USE_AZURE_OPENAI"):
    model = "css-openai-gpt35"
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2023-12-01-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    )

# completion = client.chat.completions.create()
stop = "\n"


def generate_bot_message(past_messages):
    bot_messages = []
    bot_messages.append({"role": "system", "content": str(prompts)})

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

    response = client.chat.completions.create(
        model=model,
        messages=bot_messages + [question_message],
        # this is recieving our prompt based on the question parameter and start sequence
        temperature=0.9,  # temperature designates how creative you want the chatbot to be on a scale of 0-1
        max_tokens=80,  # max_tokens states how long the answer can be
        # top_p=1,  # top_p is another creativity measure, but should be set to 1 when temperature is in use
        # frequency_penalty=0,
        # presence_penalty=0.1,
        stop=[stop],
    )
    answer = response.choices[0].message.content

    logging.debug("Checking if answer is yes or no: " + answer)

    if answer.lower() == "yes":
        logging.debug("Answering yes")
        sleep(randint(6, 12))
        response = client.chat.completions.create(
            model=model,
            messages=bot_messages,
            # this is recieving our prompt based on the question parameter and start sequence
            temperature=0.9,  # temperature designates how creative you want the chatbot to be on a scale of 0-1
            max_tokens=80,  # max_tokens states how long the answer can be
            # top_p=1,  # top_p is another creativity measure, but should be set to 1 when temperature is in use
            # frequency_penalty=0,
            # presence_penalty=0.1,
            stop=[stop],
        )

        answer = response.choices[0].message.content
        # if answer.startswith('^[a-zA-Z]:\s*(.*)'):
        #     answer = answer[5:]

        answer = re.sub(r"^[a-zA-Z]*:\s*", "", answer)

        return answer
    else:
        logging.debug("Irrelevant answer, not answering")

        return None
