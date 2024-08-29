# University of Potsdam
"""Chatbot agent that both administers an interaction and acts as the
interacting player.
"""

import asyncio
import logging
import os
import random
import time

import socketio

from .config import TASK_GREETING, TIME_CLOSE
from .interaction import generate_bot_message

LOG = logging.getLogger(__name__)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


current_task = None


class Chatbot:
    def __init__(self, config, host, port):
        """Serves as a template for task bots.
        :param task: Task ID
        :type task: str
        """
        self.bot_token = config["bot_token"]
        self.api_token = config["api_token"]
        self.bot_user = config["bot_user"]
        self.bot_id = config["bot_ids"][0]
        self.chat_room_id = int(config["chat_room_id"])
        self.num_users = config["num_users"]

        self.uri = host
        if port is not None:
            self.uri += f":{port}"
        self.uri += "/slurk/api"
        self.sio = socketio.AsyncClient()

        self.players_per_room = []
        self.message_history = dict()

    async def run(self):
        """Establish a connection to the slurk chat server."""
        await self.sio.connect(
            self.uri,
            headers={
                "Authorization": f"Bearer {self.bot_token}",
                "user": str(self.bot_user),
            },
            namespaces="/",
        )
        self.register_callbacks()
        await self.sio.wait()

    def register_callbacks(self):
        @self.sio.event
        async def status(data):
            print("STATUS", data, flush=True)

            if data["type"] == "leave":
                await self.sio.emit(
                    "text",
                    {
                        "message": "user left",
                        "room": self.chat_room_id,
                        "html": True,
                        "broadcast": True,
                    },
                )
                self.num_users -= 1
                if self.num_users == 0:
                    await self.sio.emit(
                        "room_closed",
                        {
                            "message": "room_closed",
                            "room": self.chat_room_id,
                        },
                    )
                    await self.sio.disconnect()

                    print("CLOSED CHAT ROOM", flush=True)
                    return

                print("SENT MESSAGE about user leaving", self.chat_room_id, flush=True)
                return

            if data["type"] != "join":
                return

            if data["room"] != self.chat_room_id:
                return

            user = data["user"]
            user_id = user["id"]

            if user_id != self.bot_user:
                self.players_per_room.append({"msg_n": 0, "status": "ready", **user})

            if len(self.players_per_room) == self.num_users:
                for line in TASK_GREETING:
                    print(line, flush=True)
                    await self.sio.emit(
                        "text",
                        {
                            "message": line,
                            "room": self.chat_room_id,
                            "html": True,
                        },
                    )
                    await asyncio.sleep(0.5 + random.random() * 0.5)

        @self.sio.event
        async def text_message(data):
            """Triggered once a text message is sent (no leading /).

            Count user text messages.
            If encountering something that looks like a command
            then pass it on to be parsed as such.
            """
            user_id = data["user"]["id"]

            if data["room"] != self.chat_room_id:
                return

            print("USER", user_id, self.bot_user)
            # avoid ciruclar calls!
            if user_id == self.bot_user:
                print("COMES FROM BOT, SKIP", flush=True)
                return

            room_id = data["room"]
            if room_id not in self.message_history:
                self.message_history[room_id] = []

            # if the message is part of the main discussion count it
            for usr in self.players_per_room:
                if usr["id"] == user_id and usr["status"] == "ready":
                    usr["msg_n"] += 1
                elif usr["id"] == user_id and usr["status"] == "done":
                    logging.debug("Not answering due to done user!")
                    return

            user_message = data["message"]
            self.message_history[room_id].append(
                {"sender": data["user"]["name"], "text": user_message}
            )

            print("EMITTED start_typing", flush=True)
            await self.sio.emit("keypress", dict(typing=True))

            async def finish_reply():
                try:
                    await _finish_reply()
                except asyncio.CancelledError:
                    print("CANCELLATIN HAPPENED", flush=True)
                    pass

            async def _finish_reply():
                started = time.time()
                # feed message to language model and get response
                try:
                    answer = await generate_bot_message(
                        self.bot_id, self.message_history[room_id], room_id
                    )
                except:  # noqa
                    import traceback  # noqa

                    traceback.print_exc()
                    raise
                if answer is None:
                    logging.debug("Not answering due to no answer!")
                    return

                needed = time.time() - started
                self.message_history[room_id].append({"sender": "Ash", "text": answer})
                logging.debug(f"Answering with: {answer}")
                print("ANSWER", answer, flush=True)

                num_words = len(answer.split(" "))
                # average 50 words per minute typing speed (is usually between 40 and 60):
                sleep_in_seconds = num_words / 50 * 60 - needed
                print("WORDS", num_words, "SLEEP", sleep_in_seconds, flush=True)
                await asyncio.sleep(sleep_in_seconds)
                print("DONE SLEEPING", answer, flush=True)
                await self.sio.emit("keypress", dict(typing=False))
                print("EMMITED STOP TYOPING", flush=True)

                await self.sio.emit(
                    "text",
                    {
                        "message": answer,
                        "receiver_id": user_id,
                        "html": True,
                        "room": room_id,
                        "broadcast": True,
                    },
                )

            global current_task
            if current_task is not None:
                print("CANCEL TASK", current_task)
                current_task.cancel()
                print("CANCELLED")
            current_task = asyncio.create_task(finish_reply())

    async def close_game(self, room_id):
        """Erase any data structures no longer necessary."""
        await self.sio.emit(
            "text",
            {
                "message": "You will be moved out of this room "
                f"in {TIME_CLOSE*2*60}-{TIME_CLOSE*3*60}s.",
                "room": room_id,
            },
        )
        await asyncio.sleep(2)
        await self.sio.emit(
            "text",
            {"message": "Make sure to save your token before that.", "room": room_id},
        )
        await asyncio.sleep(TIME_CLOSE * 2 * 60)
        await self.room_to_read_only(room_id)
