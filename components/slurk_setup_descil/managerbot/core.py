import asyncio
import logging
import time

import socketio
from slurk_setup_descil.slurk_api import (
    catch_error,
    create_forward_room,
    get,
    redirect_user,
)

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

_async_tasks = dict()


class Managerbot:
    def __init__(self, setup, host, port):
        """This bot lists users joining a designated
        waiting room and sends a group of users to a task room
        as soon as the minimal number of users needed for the
        task is reached.

        :param setup: configuration dict from REST endpoint
        :param host: Full URL including protocol and hostname.
        :type host: str
        :param port: Port used by the slurk chat server.
        :type port: int
        """

        self.setup = setup
        print("SETUP", setup, flush=True)

        self.api_token = setup["api_token"]
        self.bot_token = setup["managerbot_token"]
        self.bot_user = setup["managerbot_user"]
        self.chat_room_id = setup["chat_room_id"]
        self.bot_ids = setup["bot_ids"]
        self.redirect_url_timeout = setup["chat_room_timeout_url"]
        self.redirect_url_dropout = setup["chat_room_dropout_url"]
        self.timeout = setup["chat_room_timeout_seconds"]
        self.num_users = setup["num_users"]
        self.min_num_users_chat_room = setup["min_num_users_chat_room"]

        self.timeout_manager_active = False
        self.redirect_users_active = False

        self.bot_name = "ManagerBot"

        # self.tasks = dict()
        self.users = set()
        self.uri = host
        if port is not None:
            self.uri += f":{port}"
        sio = self.sio = socketio.AsyncClient()

        self.redirect_room_id = None

        @sio.event
        # @catch_error not working here!?
        async def status(data):
            print("MANAGER STATUS", data, flush=True)
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

    @catch_error
    async def timeout_manager(self):
        print("TIMEOUT MANAGER STARTED", flush=True)
        started = time.time()
        while time.time() < started + self.timeout:
            await asyncio.sleep(1.0)
            left = max(0, int(started + self.timeout - time.time()))
            if not self.sio.connected:
                return
            if left % 20 == 0:
                print("UPDATE MESSAGE", left, "SECONDS LEFT", flush=True)
                await self._send_message(f"{left} seconds left", 2)
            if left == 0:
                print("LEFT IS 0, BREAK", flush=True)
                break

        await self.redirect_users_timeout()

    @catch_error
    async def redirect_user(self, user_id, task_id, to_room):
        """
        for eacch user create room with layout
        add users to the rooms
        show message
        """
        await redirect_user(
            self.uri,
            self.bot_token,
            user_id,
            task_id,
            self.chat_room_id,
            to_room,
            self.sio,
        )

        print("REDIRECTED USER", flush=True)

    @catch_error
    async def _send_message(self, message, duration):
        await self.sio.emit("keypress", dict(typing=True))
        await asyncio.sleep(duration)
        await self.sio.emit("keypress", dict(typing=False))
        await self.sio.emit(
            "text",
            {
                "message": message,
                "room": self.chat_room_id,
                "html": True,
            },
            callback=self.message_callback,
        )
        await self.sio.emit("keypress", dict(typing=False))

    @catch_error
    async def redirect_users_timeout(self):
        """
        for eacch user create room with layout
        add users to the rooms
        show message
        """
        self.redirect_users_active = True
        await self._send_message(
            "I will close this room in a few seconds and forward you."
            " Thanks for participating.",
            3,
        )

        redirect_room_id = await create_forward_room(
            self.uri, self.bot_token, self.redirect_url_timeout
        )

        for (
            user_id,
            _,
            task_id,
        ) in self.users:
            print("REDIRECT", user_id)
            await self.redirect_user(user_id, task_id, redirect_room_id)

        print("REDIRECTED USERS AFTER TIMEOUT", flush=True)
        await asyncio.sleep(1)
        await self.disconnect()

    @catch_error
    async def fetch_user_token(self, user_id):
        async with get(
            self.api_token, f"{self.uri}/slurk_api/users/{user_id}"
        ) as response:
            if not response.ok:
                LOG.error(f"Could not get user: {response.status_code}")
                response.raise_for_status()
            return (await response.json())["token_id"]

    @catch_error
    async def run(self):
        # establish a connection to the server
        print("CONNECT", flush=True)
        await self.sio.connect(
            self.uri,
            headers={
                "Authorization": f"Bearer {self.bot_token}",
                "user": str(self.bot_user),
            },
            namespaces="/",
        )
        print("CONNECTED", flush=True)

        # wait until the connection with the server ends
        await self.sio.wait()

    @staticmethod
    @catch_error
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

    @catch_error
    async def get_user_task(self, user):
        """Retrieve task assigned to user.

        :param user: Holds keys `id` and `name`.
        :type user: dict
        """
        async with get(
            self.bot_token, f'{self.uri}/slurk/api/users/{user["id"]}/task'
        ) as response:
            if not response.ok:
                LOG.error(f"Could not get task: {response.status_code}")
                response.raise_for_status()
            LOG.debug("Got user task successfully.")
            return await response.json()

    @catch_error
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
        # self.tasks.setdefault(task_id, {})[user_id] = room

        if user_name in ("ChatBot", "Manager"):
            return

        print("MANAGER JOIN", user, task, room, flush=True)
        self.users.add((user_id, user_name, task_id))

        if not self.timeout_manager_active:
            t = asyncio.create_task(self.timeout_manager())
            _async_tasks[id(t)] = t
            self.timeout_manager_active = True

    @catch_error
    async def disconnect(self):
        _async_tasks.pop(self, None)
        print(flush=True)
        await self.sio.disconnect()

    @catch_error
    async def user_task_leave(self, user, task):
        """The task entry of a disconnected user is removed.

        :param user: Holds keys `id` and `name`.
        :type user: dict
        :param task: Holds keys `date_created`, `date_modified`, `id`,
            `layout_id`, `name` and `num_users`.
        :type task: dict
        """

        if self.redirect_users_active:
            return

        self.num_users -= 1
        self.users.discard((user["id"], user["name"]))

        if self.num_users > 0:
            await self._send_message(f"user {user['name']} left", 1)

        if self.num_users >= self.min_num_users_chat_room:
            return

        self.redirect_users_active = True

        if self.num_users > 0:
            await self._send_message(
                "The room has not enough participants anymore."
                " I will close the room and forward the remaining users.",
                3,
            )
            await asyncio.sleep(3)

            print("CREATE REDIRECT ROOM", flush=True)
            redirect_room_id = await create_forward_room(
                self.uri, self.bot_token, self.redirect_url_dropout
            )

            # for users_in_task in self.tasks.values():
            # for user_id, task_id in users_in_task.items():
            for user_id, _, task_id in self.users:
                print("REDIRECT", user, flush=True)
                await self.redirect_user(user_id, task_id, redirect_room_id)

            print("REDIRECTED USERS AFTER TIMEOUT", flush=True)
            await asyncio.sleep(1)

        await self.disconnect()
