import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.realtime import (
    EVENT_VERSION,
    RESOURCE_AFFECTS,
    ConnectionManager,
    build_event,
    publish_realtime_event,
)


def make_ws() -> MagicMock:
    """A websocket stand-in whose send_json is awaitable and observable."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


# --------------------------------------------------------------------------- #
# build_event
# --------------------------------------------------------------------------- #

class TestBuildEvent:
    def test_carries_identity_and_timing(self):
        event = build_event("sale", "created", {"id": 7})

        assert event["v"] == EVENT_VERSION
        assert event["type"] == "sale.created"
        assert event["resource"] == "sale"
        assert event["action"] == "created"
        assert event["payload"] == {"id": 7}
        assert event["event_id"]
        assert event["occurred_at"].endswith("+00:00")

    def test_event_ids_are_unique(self):
        a = build_event("sale", "created")
        b = build_event("sale", "created")
        assert a["event_id"] != b["event_id"]

    def test_empty_payload_defaults_to_dict(self):
        assert build_event("bank", "updated")["payload"] == {}

    def test_affects_defaults_from_the_resource_table(self):
        event = build_event("sale", "created", {"id": 1})
        assert set(event["affects"]) == set(RESOURCE_AFFECTS["sale"])

    def test_affects_can_be_overridden(self):
        event = build_event("sale", "created", None, affects=["sales"])
        assert event["affects"] == ["sales"]

    def test_explicit_empty_affects_is_respected(self):
        assert build_event("sale", "created", None, affects=[])["affects"] == []

    def test_unknown_resource_yields_empty_affects(self):
        assert build_event("unicorn", "created")["affects"] == []

    def test_affects_is_json_serialisable(self):
        # It travels over send_json; a tuple would not survive as a list.
        event = build_event("purchase", "created")
        assert isinstance(event["affects"], list)
        json.dumps(event)


class TestResourceAffects:
    """
    The table mirrors the frontend matrix in src/lib/query/invalidateMovement.ts.
    These invariants are what keep the two from drifting apart.
    """

    @pytest.mark.parametrize(
        "resource",
        [
            "sale", "sale_payment", "purchase", "purchase_payment",
            "expense", "transaction", "customer_payment",
            "investment", "loan",
        ],
    )
    def test_movements_touch_both_transaction_roots(self, resource):
        affects = RESOURCE_AFFECTS[resource]
        assert "transactions" in affects
        assert "transactions-head" in affects

    @pytest.mark.parametrize(
        "resource",
        [
            "sale", "sale_payment", "purchase", "purchase_payment",
            "expense", "transaction", "customer_payment", "bank",
        ],
    )
    def test_money_movements_touch_banks_and_dashboard(self, resource):
        affects = RESOURCE_AFFECTS[resource]
        assert "banks" in affects
        assert "dashboard" in affects

    def test_no_row_has_duplicates(self):
        for resource, affects in RESOURCE_AFFECTS.items():
            assert len(set(affects)) == len(affects), resource

    def test_covers_every_resource_the_services_publish(self):
        published = {
            "sale", "sale_payment", "purchase", "purchase_payment", "expense",
            "transaction", "customer", "customer_payment", "supplier",
            "product", "bank", "investment", "loan",
        }
        assert published <= set(RESOURCE_AFFECTS)


# --------------------------------------------------------------------------- #
# ConnectionManager
# --------------------------------------------------------------------------- #

class TestConnectionManager:
    async def test_connect_accepts_and_registers(self):
        mgr = ConnectionManager()
        ws = make_ws()

        await mgr.connect("global", ws)

        ws.accept.assert_awaited_once()
        assert mgr.connection_count("global") == 1

    async def test_multiple_sockets_share_a_channel(self):
        mgr = ConnectionManager()
        a, b = make_ws(), make_ws()

        await mgr.connect("global", a)
        await mgr.connect("global", b)

        assert mgr.connection_count("global") == 2

    async def test_broadcast_reaches_every_socket(self):
        mgr = ConnectionManager()
        a, b = make_ws(), make_ws()
        await mgr.connect("global", a)
        await mgr.connect("global", b)

        delivered = await mgr.broadcast("global", {"type": "sale.created"})

        assert delivered == 2
        a.send_json.assert_awaited_once_with({"type": "sale.created"})
        b.send_json.assert_awaited_once_with({"type": "sale.created"})

    async def test_broadcast_to_empty_channel_is_a_noop(self):
        mgr = ConnectionManager()
        assert await mgr.broadcast("global", {"type": "x"}) == 0

    async def test_a_failing_socket_does_not_block_the_others(self):
        mgr = ConnectionManager()
        good, bad = make_ws(), make_ws()
        bad.send_json.side_effect = RuntimeError("connection reset")
        await mgr.connect("global", bad)
        await mgr.connect("global", good)

        delivered = await mgr.broadcast("global", {"type": "sale.created"})

        assert delivered == 1
        good.send_json.assert_awaited_once()

    async def test_failing_sockets_are_dropped(self):
        mgr = ConnectionManager()
        bad = make_ws()
        bad.send_json.side_effect = RuntimeError("gone")
        await mgr.connect("global", bad)

        await mgr.broadcast("global", {"type": "x"})

        assert mgr.connection_count("global") == 0

    async def test_disconnect_removes_the_socket(self):
        mgr = ConnectionManager()
        ws = make_ws()
        await mgr.connect("global", ws)

        mgr.disconnect("global", ws)

        assert mgr.connection_count("global") == 0

    async def test_disconnect_is_idempotent(self):
        mgr = ConnectionManager()
        ws = make_ws()
        await mgr.connect("global", ws)

        mgr.disconnect("global", ws)
        mgr.disconnect("global", ws)
        mgr.disconnect("nonexistent", ws)

        assert mgr.connection_count("global") == 0

    async def test_channels_are_isolated(self):
        mgr = ConnectionManager()
        a, b = make_ws(), make_ws()
        await mgr.connect("chan-a", a)
        await mgr.connect("chan-b", b)

        await mgr.broadcast("chan-a", {"type": "x"})

        a.send_json.assert_awaited_once()
        b.send_json.assert_not_awaited()


# --------------------------------------------------------------------------- #
# publish_realtime_event
# --------------------------------------------------------------------------- #

class TestPublishRealtimeEvent:
    async def test_publishes_a_full_envelope(self, mocker):
        broadcast = mocker.patch(
            "app.core.realtime.manager.broadcast", new_callable=AsyncMock, return_value=1
        )

        await publish_realtime_event("global", "expense", "created", {"id": 3})

        channel, message = broadcast.await_args.args
        assert channel == "global"
        assert message["type"] == "expense.created"
        assert message["payload"] == {"id": 3}
        assert "transactions-head" in message["affects"]
        assert message["event_id"]

    async def test_forwards_an_explicit_affects_list(self, mocker):
        broadcast = mocker.patch(
            "app.core.realtime.manager.broadcast", new_callable=AsyncMock, return_value=0
        )

        await publish_realtime_event("global", "sale", "created", {"id": 1}, affects=["sales"])

        _, message = broadcast.await_args.args
        assert message["affects"] == ["sales"]

    async def test_zero_listeners_is_not_an_error(self, mocker):
        mocker.patch(
            "app.core.realtime.manager.broadcast", new_callable=AsyncMock, return_value=0
        )
        await publish_realtime_event("global", "bank", "updated", {"id": 1})
