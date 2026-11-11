from typing import Any

import httpx


class AdminBackendError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class AdminBackend:
    """Calls the Backend admin API. Every call carries the acting Telegram ID; the Backend decides permissions."""

    def __init__(self, base_url: str, admin_token: str) -> None:
        self._http = httpx.AsyncClient(base_url=base_url.rstrip("/"),
                                       headers={"X-Admin-Token": admin_token}, timeout=15.0)

    async def close(self) -> None:
        await self._http.aclose()

    async def _request(self, actor: int, method: str, path: str, **kwargs: Any) -> Any:
        try:
            r = await self._http.request(method, path, headers={"X-Actor-Telegram-Id": str(actor)}, **kwargs)
        except httpx.HTTPError as exc:
            raise AdminBackendError(503, "سرویس موقتاً در دسترس نیست.") from exc
        if r.status_code >= 400:
            try:
                body = r.json()
            except ValueError:
                body = {}
            raise AdminBackendError(r.status_code, body.get("message") or "خطایی رخ داد.")
        if r.status_code == 204 or not r.content:
            return None
        if r.headers.get("content-type", "").startswith("application/json"):
            return r.json()
        return r.content

    async def me(self, actor: int) -> dict:
        return await self._request(actor, "GET", "/admin/me")

    async def reservations(self, actor: int, statuses: list[str]) -> list[dict]:
        return await self._request(actor, "GET", "/admin/reservations", params={"status": statuses})

    async def confirm(self, actor: int, code: str, table_ids: list[int]) -> None:
        await self._request(actor, "POST", f"/admin/reservations/{code}/confirm", json={"table_ids": table_ids})

    async def reject(self, actor: int, code: str, reason: str) -> None:
        await self._request(actor, "POST", f"/admin/reservations/{code}/reject", json={"reason": reason})

    async def verify_payment(self, actor: int, code: str, amount: int) -> None:
        await self._request(actor, "POST", f"/admin/reservations/{code}/payment/verify",
                            json={"amount_verified": amount})

    async def reject_payment(self, actor: int, code: str, reason: str) -> None:
        await self._request(actor, "POST", f"/admin/reservations/{code}/payment/reject", json={"reason": reason})

    async def receipt(self, actor: int, code: str) -> bytes:
        return await self._request(actor, "GET", f"/admin/reservations/{code}/receipt")

    async def tables(self, actor: int, space_code: str | None = None) -> list[dict]:
        params = {"space_code": space_code} if space_code else {}
        return await self._request(actor, "GET", "/admin/tables", params=params)

    async def update_table(self, actor: int, table_id: int, **fields: Any) -> None:
        await self._request(actor, "PATCH", f"/admin/tables/{table_id}", json=fields)

    async def get_setting(self, actor: int, key: str) -> dict:
        return await self._request(actor, "GET", f"/admin/settings/{key}")

    async def put_setting(self, actor: int, key: str, value: Any, expected_version: int) -> dict:
        return await self._request(actor, "PUT", f"/admin/settings/{key}",
                                   json={"value": value, "expected_version": expected_version})

    async def team(self, actor: int) -> list[dict]:
        return await self._request(actor, "GET", "/admin/team")

    async def tickets(self, actor: int, statuses: list[str]) -> list[dict]:
        return await self._request(actor, "GET", "/admin/support/tickets", params={"status": statuses})

    async def claim_ticket(self, actor: int, ticket_id: int) -> None:
        await self._request(actor, "POST", f"/admin/support/tickets/{ticket_id}/claim")

    async def reply_ticket(self, actor: int, ticket_id: int, text: str) -> None:
        await self._request(actor, "POST", f"/admin/support/tickets/{ticket_id}/reply", json={"text": text})

    async def close_ticket(self, actor: int, ticket_id: int) -> None:
        await self._request(actor, "POST", f"/admin/support/tickets/{ticket_id}/close")

    async def ticket_history(self, actor: int, ticket_id: int) -> list[dict]:
        return await self._request(actor, "GET", f"/admin/support/tickets/{ticket_id}/messages")

    async def support_report(self, actor: int) -> list[dict]:
        return await self._request(actor, "GET", "/admin/support/report")

    async def daily_report(self, actor: int) -> dict:
        return await self._request(actor, "GET", "/admin/reports/daily")

    async def monthly_excel(self, actor: int, ym: str) -> bytes:
        return await self._request(actor, "GET", "/admin/reports/monthly.xlsx", params={"ym": ym})
