from slurk_setup_descil.setup_service.core import (
    create_waiting_room_tokens,
    setup_and_register_concierge,
    setup_waiting_room,
)

def test():
    assert create_waiting_room_tokens is not None
