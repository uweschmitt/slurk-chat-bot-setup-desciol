# University of Potsdam
"""Chatbot agent that both administers an interaction and acts as the
interacting player.
"""

import logging
import os
import random
import string
from time import sleep

import requests

from .config import TASK_GREETING, TIME_CLOSE
from .interaction import generate_bot_message
from .templates import TaskBot

LOG = logging.getLogger(__name__)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Chatbot(TaskBot):
    """A bot that talks to a user by calling some chatbot API"""

    """The ID of the room where users for this task are waiting."""
    waiting_room = None

    def __init__(self, *args, **kwargs):
        """This bot interacts with 1 human player by calling an API to carry
        out the actual interaction

        :param players_per_room: Each room is mapped to a list of
            users. Each user is represented as a dict with the
            keys 'name', 'id', 'msg_n' and 'status'.
        :type players_per_room: dict
        """
        super().__init__(*args, **kwargs)
        self.players_per_room = dict()
        self.message_history = dict()

    def register_callbacks(self):
        @self.sio.event
        def joined_room(data):
            """Triggered once after the bot joins a room."""

            # read out task greeting
            # ask players to send /ready
            sleep(4)  # avoiding namespace errors
            for line in TASK_GREETING:
                self.sio.emit(
                    "text",
                    {
                        "message": line,
                        "room": 2,
                        "html": True,
                        "broadcast": True,
                    },
                )
                sleep(0.5)

        @self.sio.event
        def status(data):
            """Triggered if a user enters or leaves a room."""
            # check whether the user is eligible to join this task
            task = requests.get(
                f"{self.uri}/users/{data['user']['id']}/task",
                headers={"Authorization": f"Bearer {self.token}"},
            )
            self.request_feedback(task, "set task instruction title")
            if not task.json() or task.json()["id"] != int(self.task_id):
                return

        @self.sio.event
        def text_message(data):
            """Triggered once a text message is sent (no leading /).

            Count user text messages.
            If encountering something that looks like a command
            then pass it on to be parsed as such.
            """
            LOG.debug(f"Received a message from {data['user']['name']}.")

            room_id = data["room"]
            user_id = data["user"]["id"]
            if room_id not in self.message_history:
                self.message_history[room_id] = []

            # filter irrelevant messages
            if user_id == self.user:
                logging.debug("Not answering due to own message!")
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
            answer = self._interaction_loop(self.message_history[room_id])
            if answer is None:
                logging.debug("Not answering due to no answer!")
                return
            self.message_history[room_id].append({"sender": "Ash", "text": answer})
            logging.debug(f"Got text: {user_message}")

            logging.debug(f"Answering with: {answer}")

            self.sio.emit(
                "text",
                {
                    "message": answer,
                    "receiver_id": user_id,
                    "html": True,
                    "room": room_id,
                    "broadcast": True,
                },
            )

        @self.sio.event
        def command(data):
            """Parse user commands."""
            LOG.debug(
                f"Received a command from {data['user']['name']}: {data['command']}"
            )
            room_id = data["room"]
            user_id = data["user"]["id"]

            self.sio.emit(
                "text",
                {
                    "message": "You provided a command message starting with '/'. Commands are not enabled for this chat.",
                    "room": room_id,
                    "receiver_id": user_id,
                },
            )

    def join_task_room(self):
        """Let the bot join an assigned task room."""

        def join(data):
            if self.task_id is None or data["task"] != self.task_id:
                return

            room_id = data["room"]

            LOG.debug(f"A new task room was created with id: {data['task']}")
            LOG.debug(f"This bot is looking for task id: {self.task_id}")

            self.move_divider(room_id, 70, 30)

            self.players_per_room[room_id] = []
            for usr in data["users"]:
                self.players_per_room[room_id].append(
                    {**usr, "msg_n": 0, "status": "ready"}
                )

            response = requests.post(
                f"{self.uri}/users/{self.user}/rooms/{room_id}",
                headers={"Authorization": f"Bearer {self.token}"},
            )
            self.request_feedback(response, f"let {self.__class__.__name__} join room")

        return join

    def _interaction_loop(self, room_message_history):
        """

        :param message: The user message will be given as input to the external
            LM via an API that then provides a response.
        :type message: str
        :return: answer(str): the answer to give to the user. Can be formatted.
        """
        answer = generate_bot_message(
            room_message_history
        )  # check f thread safe and same bot goes to many rooms.
        return answer

    def confirmation_code(self, room_id, status, receiver_id=None):
        """Generate a code that will be sent to each player."""
        kwargs = dict()
        # either only for one user or for both
        if receiver_id is not None:
            kwargs["receiver_id"] = receiver_id

        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        # post code to logs
        response = requests.post(
            f"{self.uri}/logs",
            json={
                "event": "confirmation_log",
                "room_id": room_id,
                "data": {"status_txt": status, "code": code},
                **kwargs,
            },
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.request_feedback(response, "post code to logs")

        self.sio.emit(
            "text",
            {
                "message": "Please enter the following token into the field on "
                "the HIT webpage, and close this browser window. ",
                "room": room_id,
                **kwargs,
            },
        )
        self.sio.emit(
            "text",
            {"message": f"Here is your token: {code}", "room": room_id, **kwargs},
        )
        return code

    def close_game(self, room_id):
        """Erase any data structures no longer necessary."""
        self.sio.emit(
            "text",
            {
                "message": "You will be moved out of this room "
                f"in {TIME_CLOSE*2*60}-{TIME_CLOSE*3*60}s.",
                "room": room_id,
            },
        )
        sleep(2)
        self.sio.emit(
            "text",
            {"message": "Make sure to save your token before that.", "room": room_id},
        )
        sleep(TIME_CLOSE * 2 * 60)
        self.room_to_read_only(room_id)

        # remove users from room
        for usr in self.players_per_room[room_id]:
            response = requests.get(
                f"{self.uri}/users/{usr['id']}",
                headers={"Authorization": f"Bearer {self.token}"},
            )
            self.request_feedback(response, "get user")
            etag = response.headers["ETag"]

            response = requests.delete(
                f"{self.uri}/users/{usr['id']}/rooms/{room_id}",
                headers={"If-Match": etag, "Authorization": f"Bearer {self.token}"},
            )
            self.request_feedback(response, "remove user from task room")

        # remove any task room specific objects
        self.players_per_room.pop(room_id)

    def room_to_read_only(self, room_id):
        """Set room to read only."""
        response = requests.patch(
            f"{self.uri}/rooms/{room_id}/attribute/id/text",
            json={"attribute": "readonly", "value": "True"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.request_feedback(response, "set room to read_only")

        response = requests.patch(
            f"{self.uri}/rooms/{room_id}/attribute/id/text",
            json={"attribute": "placeholder", "value": "This room is read-only"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.request_feedback(response, "inform user that room is read_only")
