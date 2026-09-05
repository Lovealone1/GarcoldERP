from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import WebSocketDisconnect, WebSocketException, status

from app.core.security.realtime_auth import (
    GLOBAL_CHANNEL,
    WsIdentity,
    build_channel_id,
    build_channel_id_from_auth,
    get_ws_identity,
)
from app.v1_0.routers.realtime_router import websocket_realtime


def make_ws(messages: list[str] | None = None) -> MagicMock:
    """
    A websocket whose receive_text yields `messages` and then disconnects,
    mirroring how a real client eventually goes away.
    """
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()

    queue = list(messages or [])

    async def receive_text():
        if queue:
            return queue.pop(0)
        raise WebSocketDisconnect()

    ws.receive_text = AsyncMock(side_effect=receive_text)
    return ws


@pytest.fixture
def authed(mocker):
    """Patch identity resolution so the router runs without a database."""
    mocker.patch(
        "app.v1_0.routers.realtime_router.get_ws_identity",
        new_callable=AsyncMock,
        return_value=WsIdentity(sub="user-sub", user_id="user-sub"),
    )


class TestChannelResolution:
    def test_channel_is_global(self):
        # Single-company deployment: no tenant column exists to partition on.
        assert build_channel_id(WsIdentity(sub="a", user_id="a")) == GLOBAL_CHANNEL

    def test_channel_from_auth_context_matches(self):
        assert build_channel_id_from_auth(MagicMock()) == GLOBAL_CHANNEL

    def test_publishers_and_subscribers_agree_on_the_channel(self):
        # A mismatch here silently delivers every event to nobody.
        assert build_channel_id_from_auth(MagicMock()) == build_channel_id(
            WsIdentity(sub="a", user_id="a")
        )


class TestWebsocketAuth:
    async def test_rejects_a_socket_with_no_token(self, mocker):
        mocker.patch(
            "app.v1_0.routers.realtime_router.get_ws_identity",
            new_callable=AsyncMock,
            side_effect=WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION, reason="Missing token"
            ),
        )
        ws = make_ws()

        await websocket_realtime(ws)

        ws.close.assert_awaited_once_with(code=status.WS_1008_POLICY_VIOLATION)
        ws.accept.assert_not_awaited()

    async def test_rejects_an_invalid_token(self, mocker):
        mocker.patch(
            "app.v1_0.routers.realtime_router.get_ws_identity",
            new_callable=AsyncMock,
            side_effect=WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"
            ),
        )
        ws = make_ws()

        await websocket_realtime(ws)

        ws.close.assert_awaited_once()
        ws.accept.assert_not_awaited()

    async def test_accepts_an_authenticated_socket(self, authed, mocker):
        connect = mocker.patch(
            "app.v1_0.routers.realtime_router.manager.connect", new_callable=AsyncMock
        )
        mocker.patch("app.v1_0.routers.realtime_router.manager.disconnect")
        ws = make_ws()

        await websocket_realtime(ws)

        connect.assert_awaited_once()
        assert connect.await_args.args[0] == GLOBAL_CHANNEL


class TestHeartbeat:
    async def test_replies_pong_to_ping(self, authed, mocker):
        mocker.patch(
            "app.v1_0.routers.realtime_router.manager.connect", new_callable=AsyncMock
        )
        mocker.patch("app.v1_0.routers.realtime_router.manager.disconnect")
        ws = make_ws(['{"type": "ping"}'])

        await websocket_realtime(ws)

        ws.send_json.assert_awaited_once_with({"type": "pong"})

    async def test_replies_to_every_ping(self, authed, mocker):
        mocker.patch(
            "app.v1_0.routers.realtime_router.manager.connect", new_callable=AsyncMock
        )
        mocker.patch("app.v1_0.routers.realtime_router.manager.disconnect")
        ws = make_ws(['{"type": "ping"}'] * 3)

        await websocket_realtime(ws)

        assert ws.send_json.await_count == 3

    async def test_ignores_non_ping_frames(self, authed, mocker):
        mocker.patch(
            "app.v1_0.routers.realtime_router.manager.connect", new_callable=AsyncMock
        )
        mocker.patch("app.v1_0.routers.realtime_router.manager.disconnect")
        ws = make_ws(['{"type": "subscribe", "channel": "global"}'])

        await websocket_realtime(ws)

        ws.send_json.assert_not_awaited()

    async def test_malformed_frames_do_not_kill_the_socket(self, authed, mocker):
        mocker.patch(
            "app.v1_0.routers.realtime_router.manager.connect", new_callable=AsyncMock
        )
        disconnect = mocker.patch("app.v1_0.routers.realtime_router.manager.disconnect")
        ws = make_ws(["not json{{", "[1,2,3]", '{"type": "ping"}'])

        await websocket_realtime(ws)

        # Survived the junk and still answered the ping that followed.
        ws.send_json.assert_awaited_once_with({"type": "pong"})
        disconnect.assert_called_once()


class TestLifecycle:
    async def test_disconnect_unregisters_the_socket(self, authed, mocker):
        mocker.patch(
            "app.v1_0.routers.realtime_router.manager.connect", new_callable=AsyncMock
        )
        disconnect = mocker.patch("app.v1_0.routers.realtime_router.manager.disconnect")
        ws = make_ws()

        await websocket_realtime(ws)

        disconnect.assert_called_once()
        assert disconnect.call_args.args[0] == GLOBAL_CHANNEL

    async def test_unexpected_errors_still_unregister(self, authed, mocker):
        mocker.patch(
            "app.v1_0.routers.realtime_router.manager.connect", new_callable=AsyncMock
        )
        disconnect = mocker.patch("app.v1_0.routers.realtime_router.manager.disconnect")
        ws = make_ws()
        ws.receive_text = AsyncMock(side_effect=RuntimeError("transport blew up"))

        await websocket_realtime(ws)

        # A leaked entry would make every later broadcast try a dead socket.
        disconnect.assert_called_once()
        ws.close.assert_awaited_once()


class TestGetWsIdentity:
    async def test_missing_token_raises_policy_violation(self):
        ws = MagicMock()
        ws.query_params = {}

        with pytest.raises(WebSocketException) as exc:
            await get_ws_identity(ws)

        assert exc.value.code == status.WS_1008_POLICY_VIOLATION

    async def test_invalid_token_raises_policy_violation(self, mocker):
        mocker.patch(
            "app.core.security.realtime_auth.verify_token",
            new_callable=AsyncMock,
            side_effect=ValueError("bad signature"),
        )
        ws = MagicMock()
        ws.query_params = {"token": "garbage"}

        with pytest.raises(WebSocketException) as exc:
            await get_ws_identity(ws)

        assert exc.value.code == status.WS_1008_POLICY_VIOLATION

    async def test_token_without_sub_is_rejected(self, mocker):
        mocker.patch(
            "app.core.security.realtime_auth.verify_token",
            new_callable=AsyncMock,
            return_value={},
        )
        ws = MagicMock()
        ws.query_params = {"token": "t"}

        with pytest.raises(WebSocketException):
            await get_ws_identity(ws)
