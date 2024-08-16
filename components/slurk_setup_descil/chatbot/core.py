# University of Potsdam
"""Chatbot agent that both administers an interaction and acts as the
interacting player.
"""

import asyncio
import logging
import os
import random

import socketio

from .config import TASK_GREETING, TIME_CLOSE
from .interaction import generate_bot_message

LOG = logging.getLogger(__name__)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Chatbot:
    def __init__(self, config, host, port):
        """Serves as a template for task bots.
        :param task: Task ID
        :type task: str
        """
        self.bot_token = config["bot_token"]
        self.api_token = config["api_token"]
        self.bot_user = config["bot_user"]
        self.task_room_id = str(config["task_room_id"])

        self.uri = host
        if port is not None:
            self.uri += f":{port}"
        self.uri += "/slurk/api"
        self.sio = socketio.AsyncClient()

        self.players_per_room = dict()
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
            if data["type"] != "join":
                return

            user = data["user"]
            room_id = data["room"]
            user_id = user["id"]

            if user_id == self.bot_user:
                await asyncio.sleep(1.0 + random.random() * 5)
                for line in TASK_GREETING:
                    print("  ", line, flush=True)
                    await self.sio.emit(
                        "text",
                        {
                            "message": line,
                            "room": room_id,
                            "html": True,
                            "broadcast": True,
                        },
                    )
                    await asyncio.sleep(0.5 + random.random() * 0.5)

            self.players_per_room.setdefault(room_id, []).append(
                {"msg_n": 0, "status": "ready", **user}
            )

        @self.sio.event
        async def text_message(data):
            """Triggered once a text message is sent (no leading /).

            Count user text messages.
            If encountering something that looks like a command
            then pass it on to be parsed as such.
            """
            LOG.debug(f"Received a message from {data['user']['name']}.")
            print(f"Received a message from {data['user']['name']}.")

            room_id = data["room"]
            user_id = data["user"]["id"]
            if room_id not in self.message_history:
                self.message_history[room_id] = []

            print(repr(user_id), repr(self.bot_user), flush=True)
            if user_id == self.bot_user:
                return

            # if the message is part of the main discussion count it
            for usr in self.players_per_room[room_id]:
                if usr["id"] == user_id and usr["status"] == "ready":
                    usr["msg_n"] += 1
                elif usr["id"] == user_id and usr["status"] == "done":
                    logging.debug("Not answering due to done user!")
                    return

            user_message = data["message"]
            self.message_history[room_id].append(
                {"sender": data["user"]["name"], "text": user_message}
            )

            # feed message to language model and get response
            answer = await generate_bot_message(self.message_history[room_id])
            if answer is None:
                logging.debug("Not answering due to no answer!")
                return
            self.message_history[room_id].append({"sender": "Ash", "text": answer})
            logging.debug(f"Got text: {user_message}")

            logging.debug(f"Answering with: {answer}")

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

        # remove any task room specific objects
        self.players_per_room.pop(room_id)

    async def room_to_read_only(self, room_id):
        """Set room to read only."""

        """
        response = requests.patch(
            f"{self.uri}/rooms/{room_id}/attribute/id/text",
            json={"attribute": "readonly", "value": "True"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        # self.request_feedback(response, "set room to read_only")

        response = requests.patch(
            f"{self.uri}/rooms/{room_id}/attribute/id/text",
            json={"attribute": "placeholder", "value": "This room is read-only"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        # self.request_feedback(response, "inform user that room is read_only")

        """
        pass
