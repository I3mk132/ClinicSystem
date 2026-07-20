"""
Thin async client over the clinic backend's public REST API.

This is the bot's ONLY window into clinic data. Every method authenticates with
the tenant's X-API-Key, so the backend resolves the clinic from the key itself
(never a header the model could influence). The bot has no DB access.
"""
from datetime import date, time
from typing import Any, Optional

import httpx

from app.config import settings


class ClinicApiError(Exception):
    """Raised when the public API returns a 4xx/5xx. `detail` is safe to surface."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{status_code}: {detail}")


class ClinicApiClient:
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._base = settings.CLINIC_API_BASE_URL.rstrip("/")

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        headers = {"X-API-Key": self._api_key}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.request(method, f"{self._base}{path}", headers=headers, **kwargs)
        if resp.status_code >= 400:
            detail = _extract_detail(resp)
            raise ClinicApiError(resp.status_code, detail)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    # ---- read-only catalog ------------------------------------------------
    async def list_departments(self) -> list[dict]:
        return await self._request("GET", "/public/departments")

    async def list_doctors(self, department_id: Optional[int] = None) -> list[dict]:
        params = {"department_id": department_id} if department_id is not None else None
        return await self._request("GET", "/public/doctors", params=params)

    async def get_available_slots(self, doctor_id: int, target_date: date) -> list[dict]:
        return await self._request(
            "GET",
            f"/public/doctors/{doctor_id}/available-slots",
            params={"date": target_date.isoformat()},
        )

    # ---- booking (phone-scoped) ------------------------------------------
    async def book_appointment(
        self,
        *,
        doctor_id: int,
        department_id: int,
        appointment_date: date,
        start_time: time,
        patient_full_name: str,
        patient_phone: str,
        notes: Optional[str] = None,
    ) -> dict:
        body = {
            "doctor_id": doctor_id,
            "department_id": department_id,
            "appointment_date": appointment_date.isoformat(),
            "start_time": start_time.strftime("%H:%M:%S"),
            "patient_full_name": patient_full_name,
            "patient_phone": patient_phone,
            "notes": notes,
        }
        return await self._request("POST", "/public/appointments", json=body)

    async def list_appointments(self, phone: str) -> list[dict]:
        return await self._request("GET", "/public/appointments", params={"phone": phone})

    async def cancel_appointment(self, appointment_id: int, phone: str) -> dict:
        return await self._request(
            "POST", f"/public/appointments/{appointment_id}/cancel", params={"phone": phone}
        )

    async def reschedule_appointment(
        self, appointment_id: int, phone: str, appointment_date: date, start_time: time
    ) -> dict:
        body = {
            "appointment_date": appointment_date.isoformat(),
            "start_time": start_time.strftime("%H:%M:%S"),
        }
        return await self._request(
            "POST",
            f"/public/appointments/{appointment_id}/reschedule",
            params={"phone": phone},
            json=body,
        )


def _extract_detail(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict) and "detail" in data:
            d = data["detail"]
            return d if isinstance(d, str) else str(d)
    except Exception:
        pass
    return f"Request failed ({resp.status_code})"
