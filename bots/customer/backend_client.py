from typing import Any

import httpx


class BackendError(Exception):
    def __init__(self, status_code: int, code: str, message: str, support_offer: bool) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.support_offer = support_offer


class BackendClient:
    """Thin HTTP client. The bot holds no business logic; the Backend decides everything."""

    def __init__(self, base_url: str, service_token: str) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"X-Service-Token": service_token},
            timeout=15.0,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise BackendError(503, "unavailable", "سرویس موقتاً در دسترس نیست. لطفاً کمی بعد دوباره تلاش کنید.", False) from exc

        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = {}
            message = body.get("message") or "خطایی رخ داد. لطفاً دوباره تلاش کنید."
            raise BackendError(
                response.status_code,
                body.get("code", "error"),
                message,
                bool(body.get("support_offer", False)),
            )
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    async def venue(self) -> dict:
        return await self._request("GET", "/internal/venue")

    async def quote(self, payload: dict) -> dict:
        return await self._request("POST", "/internal/quote", json=payload)

    async def create_reservation(self, payload: dict) -> dict:
        return await self._request("POST", "/internal/reservations", json=payload)

    async def list_reservations(self, phone: str) -> list[dict]:
        return await self._request("GET", f"/internal/customers/{phone}/reservations")

    async def upload_receipt(self, public_code: str, data: bytes, content_type: str, telegram_user_id: int) -> None:
        await self._request(
            "POST",
            f"/internal/reservations/{public_code}/receipts",
            files={"file": ("receipt", data, content_type)},
            data={"telegram_user_id": str(telegram_user_id)},
        )

    async def cancel(self, public_code: str, telegram_user_id: int) -> dict:
        return await self._request(
            "POST",
            f"/internal/reservations/{public_code}/cancel",
            json={"telegram_user_id": telegram_user_id},
        )

    async def open_support(self, telegram_user_id: int, reason: str = "درخواست پشتیبانی") -> dict:
        return await self._request("POST", "/internal/support/open",
                                   json={"telegram_user_id": telegram_user_id, "reason": reason})

    async def support_message(self, telegram_user_id: int, text: str) -> None:
        await self._request("POST", "/internal/support/messages",
                            json={"telegram_user_id": telegram_user_id, "text": text})

    async def close_support(self, telegram_user_id: int) -> None:
        await self._request("POST", "/internal/support/close", json={"telegram_user_id": telegram_user_id})

    async def outbox(self) -> list[dict]:
        return await self._request("GET", "/internal/support/outbox")

    async def mark_delivered(self, message_id: int) -> None:
        await self._request("POST", f"/internal/support/outbox/{message_id}/delivered")

    async def notifications(self) -> list[dict]:
        return await self._request("GET", "/internal/notifications")

    async def notification_delivered(self, notification_id: int) -> None:
        await self._request("POST", f"/internal/notifications/{notification_id}/delivered")
