import asyncio
import logging
import time

import socketio
from slurk_setup_descil.slurk_api import create_forward_room, get, redirect_user

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

_async_tasks = dict()


class Managerbot:
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
        self.managerbot_token = config["bot_token"]
        self.managerbot_user = config["bot_user"]
        self.chat_room_id = config["chat_room_id"]
        self.bot_ids = config["bot_ids"]
        self.redirect_url = config["chat_room_timeout_url"]
        self.timeout = config["chat_room_timeout_seconds"]
        self.num_users = config["num_users"]

        self.number_users_in_room_missing = self.num_users
        self.timeout_manager_active = False

        self.bot_name = "ManagerBot"

        self.tasks = dict()
        self.uri = host
        if port is not None:
            self.uri += f":{port}"
        sio = self.sio = socketio.AsyncClient()

        self.redirect_room_id = None

        @sio.event
        async def status(data):
            LOG.info(f"STATUS {data}")
            if data["type"] == "join":
                user = data["user"]
                task = await self.get_user_task(user)
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
            await asyncio.sleep(1.0)

        await self.redirect_users_timeout()

    async def redirect_user(self, user_id, task_id, to_room):
        """
        for eacch user create room with layout
        add users to the rooms
        show message
        """
        await redirect_user(
            self.uri,
            self.managerbot_token,
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
        await self.sio.emit(
            "text",
            {
                "message": (
                    "## Thank you for participating in the chat,  of\n"
                    "you will be forwarded in a few seconds to the final survey."
                ),
                "broadcast": True,
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
        print("CONNECT", flush=True)
        await self.sio.connect(
            self.uri,
            headers={
                "Authorization": f"Bearer {self.managerbot_token}",
                "user": str(self.managerbot_user),
            },
            namespaces="/",
        )
        print("CONNECTED", flush=True)

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
            self.managerbot_token, f'{self.uri}/slurk/api/users/{user["id"]}/task'
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
        # register task together with the user_id
        self.tasks.setdefault(task_id, {})[user_id] = room

        if not self.timeout_manager_active:
            t = asyncio.create_task(self.timeout_manager())
            _async_tasks[id(t)] = t
            self.timeout_manager_active = True

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
