import asyncio
import logging
import os
import time

import aiohttp
import socketio
from slurk_setup_descil.slurk_api import (
    create_forward_room,
    create_room_token,
    create_user,
    get,
    redirect_user,
    set_permissions,
    setup_chat_room,
)

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

_async_tasks = dict()

CHATBOT_URL = os.environ.get("CHATBOT_URL", "http://localhost:84")
MANAGERBOT_URL = os.environ.get("MANAGERBOT_URL", "http://localhost:84")


class ConciergeBot:
    def __init__(self, config, host, port):
        """This bot lists users joining a designated
        waiting room and sends a group of users to a task room
        as soon as the minimal number of users needed for the
        task is reached.

        :param config: configuration dict from REST endpoint
        :param host: Full URL including protocol and hostname.
        :type host: str
        :param port: Port used by the slurk chat server.
        :type port: int
        """

        self.api_token = config["api_token"]
        self.concierge_token = config["concierge_token"]
        self.concierge_user = config["concierge_user"]
        self.waiting_room_id = config["waiting_room_id"]
        self.bot_ids = config["bot_ids"]
        self.redirect_url = config["waiting_room_timeout_url"]
        self.timeout = config["waiting_room_timeout_seconds"]
        self.user_tokens = config["user_tokens"]
        self.chat_room_timeout_seconds = config["chat_room_timeout_seconds"]
        self.chat_room_timeout_url = config["chat_room_timeout_url"]

        self.num_users = len(self.user_tokens)
        self.number_users_in_room_missing = self.num_users
        self.timeout_manager_active = False
        self.room_timeout_happened = False

        self.tasks = dict()
        self.uri = host
        if port is not None:
            self.uri += f":{port}"
        sio = self.sio = socketio.AsyncClient()

        LOG.debug(
            f"Running concierge bot on {self.uri} with token {self.concierge_token}"
        )

        self.redirect_room_id = None

        @sio.event
        async def status(data):
            print("STATUS GOT", data)
            if data["type"] == "join":
                user = data["user"]
                task = await self.get_user_task(user)
                if self.room_timeout_happened:
                    await self.redirect_user(user["id"], self.redirect_room_id)
                if task:
                    await self.user_task_join(user, task, data["room"])
            elif data["type"] == "leave":
                user = data["user"]
                task = await self.get_user_task(user)
                if task:
                    await self.user_task_leave(user, task)

    async def timeout_manager(self):
        started = time.time()
        while time.time() < started + self.timeout:
            if self.number_users_in_room_missing <= 0:
                print("ROOM COMPLETE!", flush=True)
                return
            await asyncio.sleep(0.5)

        self.room_timeout_happened = True
        await self.redirect_users_timeout()

    async def redirect_user(self, user_id, task_id, to_room):
        """
        for eacch user create room with layout
        add users to the rooms
        show message
        """
        await redirect_user(
            self.uri,
            self.concierge_token,
            user_id,
            task_id,
            self.waiting_room_id,
            to_room,
            self.sio,
        )

        print("REDIRECTED USER", flush=True)

    async def redirect_users_timeout(self):
        """
        for eacch user create room with layout
        add users to the rooms
        show message
        """

        for users_in_task in self.tasks.values():
            for user_id, task_id in users_in_task.items():
                await self.sio.emit(
                    "text",
                    {
                        "message": (
                            "## We could not fill the waiting room with sufficient number of\n"
                            "participants you will be forwarded in a few seconds"
                        ),
                        "broadcast": False,
                        "receiver_id": user_id,
                        "room": self.waiting_room_id,
                        "html": True,
                    },
                    callback=self.message_callback,
                )

        await asyncio.sleep(3)

        for users_in_task in self.tasks.values():
            for user_id, task_id in users_in_task.items():
                await self.redirect_user(user_id, task_id, self.redirect_room_id)

        print("REDIRECTED USERS AFTER TIMEOUT", flush=True)

    async def fetch_user_token(self, user_id):
        async with get(
            self.api_token, f"{self.uri}/slurk_api/users/{user_id}"
        ) as response:
            if not response.ok:
                LOG.error(f"Could not get user: {response.status_code}")
                response.raise_for_status()
            return (await response.json())["token_id"]

    async def run(self):
        # establish a connection to the server
        await self.sio.connect(
            self.uri,
            headers={
                "Authorization": f"Bearer {self.concierge_token}",
                "user": str(self.concierge_user),
            },
            namespaces="/",
        )

        self.redirect_room_id = await create_forward_room(
            self.uri, self.concierge_token, self.redirect_url
        )

        # wait until the connection with the server ends
        await self.sio.wait()

    @staticmethod
    async def message_callback(success, error_msg=None):
        """Is passed as an optional argument to a server emit.

        Will be invoked after the server has processed the event,
        any values returned by the event handler will be passed
        as arguments.

        :param success: `True` if the message was successfully sent,
            else `False`.
        :type success: bool
        :param error_msg: Reason for an insuccessful message
            transmission. Defaults to None.
        :type status: str, optional
        """
        if not success:
            print(f"Could not send message: {error_msg}", flush=True)
            LOG.error(f"Could not send message: {error_msg}")
        else:
            LOG.debug("Sent message successfully.")
            print("Sent message successfully.", flush=True)

    async def get_user_task(self, user):
        """Retrieve task assigned to user.

        :param user: Holds keys `id` and `name`.
        :type user: dict
        """
        async with get(
            self.concierge_token, f'{self.uri}/slurk/api/users/{user["id"]}/task'
        ) as response:
            if not response.ok:
                LOG.error(f"Could not get task: {response.status_code}")
                response.raise_for_status()
            LOG.debug("Got user task successfully.")
            return await response.json()

    async def user_task_join(self, user, task, room):
        """A connected user and their task are registered.

        Once the final user necessary to start a task
        has entered, all users for the task are moved to
        a dynamically created task room.

        :param user: Holds keys `id` and `name`.
        :type user: dict
        :param task: Holds keys `date_created`, `date_modified`, `id`,
            `layout_id`, `name` and `num_users`.
        :type task: dict
        :param room: Identifier of a room that the user joined.
        :type room: str
        """
        task_id = task["id"]
        user_id = user["id"]
        user_name = user["name"]
        # register task together with the user_id
        self.tasks.setdefault(task_id, {})[user_id] = room
        LOG.info(
            f"TASK_ID {task_id}   NUM_USERS {task['num_users']}  TASKS {self.tasks}"
        )

        self.number_users_in_room_missing -= 1
        if not self.timeout_manager_active:
            t = asyncio.create_task(self.timeout_manager())
            _async_tasks[id(t)] = t
            self.timeout_manager_active = True

        await self.sio.emit(
            "text",
            {
                "message": f"## Hello, {user_name}!\n\n"
                + (
                    f"### We are waiting for {self.number_users_in_room_missing} user(s) to join before we continue"
                    if self.number_users_in_room_missing > 0
                    else ""
                ),
                "receiver_id": user_id,
                "room": room,
                "html": True,
            },
            callback=self.message_callback,
        )

        if self.number_users_in_room_missing > 0:
            return

        try:
            print("SETUP ROOM", flush=True)
            chat_room_id, _ = await setup_chat_room(
                self.uri, self.api_token, self.num_users
            )
            print("REGISTER MANAGERBOT", flush=True)
            await self.setup_and_register_managerbot(chat_room_id)
            print("REGISTER CHATBOT", flush=True)
            await self.setup_and_register_chatbot(chat_room_id)
        except:
            import traceback

            traceback.print_exc()
            raise

        await asyncio.sleep(1)

        for user_id, old_room_id in list(self.tasks[task_id].items()):
            await self.sio.emit(
                "text",
                {
                    "message": "## room complete, you will be forwarded soon",
                    "receiver_id": user_id,
                    "room": room,
                    "html": True,
                },
                callback=self.message_callback,
            )
        await asyncio.sleep(2)

        user_ids = sorted(self.tasks[task_id].keys())
        for user_id in user_ids:
            await self.redirect_user(user_id, task_id, chat_room_id)

        del self.tasks[task_id]
        await self.disconnect()

    async def setup_and_register_chatbot(self, chat_room_id):
        permissions = {
            "api": True,
            "send_html_message": True,
            "send_message": True,
            "send_privately": True,
            "broadcast": True,
        }
        permissions_id = await set_permissions(self.uri, self.api_token, permissions)
        bot_token = await create_room_token(
            self.uri, self.api_token, permissions_id, chat_room_id, None, None
        )

        bot_name = "ChatBot"

        bot_user = await create_user(self.uri, self.api_token, bot_name, bot_token)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CHATBOT_URL}/register",
                json=dict(
                    bot_token=bot_token,
                    bot_user=bot_user,
                    bot_name=bot_name,
                    api_token=self.api_token,
                    chat_room_id=chat_room_id,
                    bot_ids=self.bot_ids,
                    num_users=self.num_users,
                ),
            ) as r:
                r.raise_for_status()
                print(r)

    async def setup_and_register_managerbot(self, chat_room_id):
        permissions = {
            "api": True,
            "send_html_message": True,
            "send_privately": True,
            "broadcast": True,
        }
        permissions_id = await set_permissions(self.uri, self.api_token, permissions)
        bot_token = await create_room_token(
            self.uri, self.api_token, permissions_id, chat_room_id, None, None
        )

        bot_name = "Manager"

        bot_user = await create_user(self.uri, self.api_token, bot_name, bot_token)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{MANAGERBOT_URL}/register",
                json=dict(
                    api_token=self.api_token,
                    bot_token=bot_token,
                    bot_user=bot_user,
                    bot_name=bot_name,
                    chat_room_id=chat_room_id,
                    bot_ids=self.bot_ids,
                    chat_room_timeout_url=self.chat_room_timeout_url,
                    chat_room_timeout_seconds=self.chat_room_timeout_seconds,
                    num_users=self.num_users,
                ),
            ) as r:
                r.raise_for_status()
                print(r)

    async def disconnect(self):
        _async_tasks.pop(self, None)
        await self.sio.disconnect()

    async def user_task_leave(self, user, task):
        """The task entry of a disconnected user is removed.

        :param user: Holds keys `id` and `name`.
        :type user: dict
        :param task: Holds keys `date_created`, `date_modified`, `id`,
            `layout_id`, `name` and `num_users`.
        :type task: dict
        """
        task_id = task["id"]
        user_id = user["id"]
        if task_id in self.tasks and user_id in self.tasks[task_id]:
            del self.tasks[task["id"]][user["id"]]
