"""
Oracle Opera Cloud (OHIP) REST API client for hotel PMS integration.
Connects via OAuth 2.0 client credentials, provides methods for
reservations, availability, and rate push.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any
import hashlib
import hmac
import json
import logging
import time

import httpx

logger = logging.getLogger("opera_cloud")


@dataclass
class OperaConfig:
    client_id: str
    client_secret: str
    base_url: str = "https://api-rsr.opera-api.com"
    token_url: str = "https://auth.opera-api.com/oauth/token"
    property_code: str = ""
    chain_code: str = ""
    enterprise_code: str = ""
    timeout_seconds: int = 30


@dataclass
class Reservation:
    external_id: str
    room_type_code: str
    check_in: date
    check_out: date
    booking_rate: float
    currency: str = "SAR"
    status: str = "confirmed"
    guest_name: str = ""
    adults: int = 1


@dataclass
class OperaLiveAvailability:
    date: date
    total_rooms: int
    available_rooms: int
    out_of_order: int
    occupancy_pct: float


class OperaCloudClient:
    def __init__(self, config: OperaConfig):
        self.config = config
        self._token: str | None = None
        self._token_expires_at: float = 0
        self._client = httpx.AsyncClient(
            timeout=config.timeout_seconds,
            headers={"User-Agent": "SaudiRMS/1.0"},
        )

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        try:
            resp = await self._client.post(
                self.config.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "scope": "opera-api",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            self._token_expires_at = time.time() + data.get("expires_in", 3600)
            return self._token
        except httpx.HTTPError as e:
            logger.error(f"Failed to get Opera token: {e}")
            raise

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        token = await self._get_token()
        url = f"{self.config.base_url}{path}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Opera-Property-Code": self.config.property_code,
            "Opera-Chain-Code": self.config.chain_code,
            "Opera-Enterprise-Code": self.config.enterprise_code,
        }

        try:
            resp = await self._client.request(method, url, headers=headers, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Opera API error {method} {path}: {e}")
            raise

    async def get_reservations(
        self, start_date: date, end_date: date | None = None
    ) -> list[Reservation]:
        path = "/reservations/v1/reservations"
        params = {
            "fromDate": start_date.isoformat(),
            "toDate": (end_date or start_date).isoformat(),
        }
        try:
            data = await self._request("GET", path, params=params)
            reservations = []
            for item in data.get("reservations", []):
                reservations.append(
                    Reservation(
                        external_id=item.get("reservationId", ""),
                        room_type_code=item.get("roomTypeCode", ""),
                        check_in=date.fromisoformat(item["checkIn"]),
                        check_out=date.fromisoformat(item["checkOut"]),
                        booking_rate=float(item.get("averageRate", 0)),
                        currency=item.get("currencyCode", "SAR"),
                        status=item.get("status", "confirmed"),
                        guest_name=item.get("guestName", ""),
                        adults=int(item.get("numberOfAdults", 1)),
                    )
                )
            return reservations
        except Exception as e:
            logger.error(f"Failed to fetch reservations: {e}")
            return []

    async def get_availability(self, target_date: date) -> OperaLiveAvailability | None:
        path = f"/availability/v1/properties/{self.config.property_code}/rooms"
        params = {"date": target_date.isoformat()}
        try:
            data = await self._request("GET", path, params=params)
            return OperaLiveAvailability(
                date=target_date,
                total_rooms=int(data.get("totalRooms", 0)),
                available_rooms=int(data.get("availableRooms", 0)),
                out_of_order=int(data.get("outOfOrderRooms", 0)),
                occupancy_pct=float(data.get("occupancyPercentage", 0)),
            )
        except Exception as e:
            logger.error(f"Failed to fetch availability: {e}")
            return None

    async def push_rate(
        self,
        room_type_code: str,
        rate_plan_code: str,
        rate_amount: float,
        effective_date: date,
        currency: str = "SAR",
    ) -> bool:
        path = "/rates/v1/rates"
        payload = {
            "rateUpdates": [
                {
                    "propertyCode": self.config.property_code,
                    "roomTypeCode": room_type_code,
                    "ratePlanCode": rate_plan_code,
                    "date": effective_date.isoformat(),
                    "amount": rate_amount,
                    "currencyCode": currency,
                    "source": "SAUDI_RMS",
                }
            ]
        }
        try:
            await self._request("POST", path, json=payload)
            logger.info(
                f"Rate pushed: {room_type_code} = {rate_amount} on {effective_date}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to push rate: {e}")
            return False

    async def get_room_types(self) -> list[dict]:
        path = f"/properties/v1/{self.config.property_code}/room-types"
        try:
            data = await self._request("GET", path)
            return data.get("roomTypes", [])
        except Exception as e:
            logger.error(f"Failed to fetch room types: {e}")
            return []

    async def health_check(self) -> bool:
        try:
            await self._get_token()
            return True
        except Exception:
            return False

    async def close(self):
        await self._client.aclose()
