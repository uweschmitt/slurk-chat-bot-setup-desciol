import asyncio
import logging
import time

import socketio
from slurk_setup_descil.slurk_api import delete, get, post

LOG = logging.getLogger(__name__)

_async_tasks = dict()


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
        self.concierge_token = config["concierge_token"]
        self.api_token = config["api_token"]
        self.concierge_user = str(config["concierge_user"])
        self.waiting_room_id = str(config["waiting_room_id"])
        self.bot_ids = config["bot_ids"]
        self.redirect_url = config["redirect_url"]
        self.timeout = config["timeout_waiting_room"]
        self.user_tokens = config["user_tokens"]
        self.number_users_in_room_missing = len(self.user_tokens)
        self.timeout_manager_active = False

        self.tasks = dict()
        self.uri = host
        if port is not None:
            self.uri += f":{port}"
        self.uri += "/slurk/api"
        sio = self.sio = socketio.AsyncClient()

        LOG.debug(
            f"Running concierge bot on {self.uri} with token {self.concierge_token}"
        )

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
            if self.number_users_in_room_missing <= 0:
                print("ROOM COMPLETE!", flush=True)
                return
            await asyncio.sleep(0.1)

        await self.redirect_users()

    async def redirect_users(self):
        """
        for eacch user create room with layout
        add users to the rooms
        show message
        """
        await self.sio.emit(
            "text",
            {
                "message": (
                    "## We could not fill the waiting room with sufficient number of\n"
                    "participants you will be forwarded in a few seconds"
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
                room_id = await self.create_forward_room()
                etag = await self.get_user(user_id)
                await self.remove_user_from_room(user_id, self.waiting_room_id, etag)
                await self.add_user_to_room(user_id, room_id)
                await self.sio.emit("room_created", {"room": room_id, "task": task_id})

    async def create_forward_room(self):
        ROOM_LAYOUT = {
            "title": "Forward Room",
            "subtitle": "Timeout....",
            "html": [
                {
                    "layout-type": "script",
                    "id": "",
                    "layout-content": f"window.location.replace({self.redirect_url!r});",
                },
            ],
            "css": {
                "header, footer": {"background": "#115E91"},
                "#image-area": {"align-content": "left", "margin": "50px 20px 15px"},
            },
            "scripts": {
                "incoming-text": "markdown",
                "incoming-image": "display-image",
                "submit-message": "send-message",
                "print-history": "markdown-history",
            },
            "show_users": False,
            "show_latency": False,
            "read_only": True,
        }

        async with post(self.concierge_token, f"{self.uri}/layouts", ROOM_LAYOUT) as r:
            r.raise_for_status()
            rj = await r.json()
            layout_id = rj["id"]

        async with post(
            self.concierge_token, f"{self.uri}/rooms", dict(layout_id=layout_id)
        ) as r:
            return (await r.json())["id"]

    async def fetch_user_token(self, user_id):
        async with get(self.api_token, f"{self.uri}/users/{user_id}") as response:
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
                "user": self.concierge_user,
            },
            namespaces="/",
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
            self.concierge_token, f'{self.uri}/users/{user["id"]}/task'
        ) as response:
            if not response.ok:
                LOG.error(f"Could not get task: {response.status_code}")
                response.raise_for_status()
            LOG.debug("Got user task successfully.")
            return await response.json()

    async def get_user(self, user):
        async with get(self.concierge_token, f"{self.uri}/users/{user}") as response:
            if not response.ok:
                LOG.error(f"Could not get user: {response.status_code}")
                response.raise_for_status()
            return response.headers["ETag"]

    async def create_room(self, layout_id):
        """Create room for the task.

        :param layout_id: Unique key of layout object.
        :type layout_id: int
        """
        json = {"layout_id": layout_id}

        async with post(self.concierge_token, f"{self.uri}/rooms", json) as response:
            if not response.ok:
                LOG.error(f"Could not create task room: {response.status_code}")
                response.raise_for_status()
            LOG.debug("Created room successfully.")
            return await response.json()

    async def add_user_to_room(self, user_id, room_id):
        """Let user join task room.

        :param user_id: Identifier of user.
        :type user_id: int
        :param room_id: Identifier of room.
        :type room_id: int
        """
        async with post(
            self.concierge_token,
            f"{self.uri}/users/{user_id}/rooms/{room_id}",
        ) as response:
            if not response.ok:
                LOG.error(f"Could not let user join room: {response.status_code}")
                response.raise_for_status()
            LOG.debug("Sending user to new room was successful.")
            return response.headers["ETag"]

    async def remove_user_from_room(self, user_id, room_id, etag):
        """Remove user from (waiting) room.

        :param user_id: Identifier of user.
        :type user_id: int
        :param room_id: Identifier of room.
        :type room_id: int
        :param etag: Used for request validation.
        :type etag: str
        """
        async with delete(
            self.concierge_token,
            f"{self.uri}/users/{user_id}/rooms/{room_id}",
            etag=etag,
        ) as response:
            if not response.ok:
                LOG.error(f"Could not remove user from room: {response.status_code}")
                response.raise_for_status()
            LOG.debug("Removing user from room was successful.")

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

        if len(self.tasks[task_id]) == task["num_users"]:
            session_id = None

            new_room = await self.create_room(task["layout_id"])
            # list cast necessary because the dictionary is actively altered
            # due to parallely received "leave" events
            for user_id, old_room_id in list(self.tasks[task_id].items()):
                await self.sio.emit(
                    "text",
                    {
                        "message": "## room complete, forward soon",
                        "receiver_id": user_id,
                        "room": room,
                        "html": True,
                    },
                    callback=self.message_callback,
                )

                await asyncio.sleep(3)

                etag = await self.get_user(user_id)
                await self.remove_user_from_room(user_id, old_room_id, etag)
                await self.add_user_to_room(user_id, new_room["id"])
            del self.tasks[task_id]
            await self.sio.emit(
                "room_created", {"room": new_room["id"], "task": task_id}
            )

            LOG.info(f"Created session {session_id}")
            await self.disconnect()

        else:
            await self.sio.emit(
                "text",
                {
                    "message": f"### Hello, {user_name}!\n\n"
                    "I am looking for a partner for you, it might take "
                    "some time, so be patient, please...",
                    "receiver_id": user_id,
                    "room": room,
                    "html": True,
                },
                callback=self.message_callback,
            )

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
