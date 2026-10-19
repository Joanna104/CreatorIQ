"""Request-ID middleware (pure ASGI, so it also covers responses to unhandled errors).

Every response carries an ``X-Request-ID`` header. A client-supplied id is reused only if it
is short and made of safe characters; otherwise a fresh one is generated. Error bodies repeat
the id so a user-reported failure can be matched to a log line.
"""

import re
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADER_NAME = "X-Request-ID"
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(HEADER_NAME)
        request_id = incoming if incoming and _SAFE_ID.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if HEADER_NAME not in headers:
                    headers[HEADER_NAME] = request_id
            await send(message)

        await self.app(scope, receive, send_with_request_id)
