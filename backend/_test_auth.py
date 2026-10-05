"""Quick smoke test for auth endpoints."""

import asyncio
import httpx

BASE = "http://127.0.0.1:8000"


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=10) as c:
        # 1) Register
        r = await c.post(
            "/api/v1/auth/register",
            json={
                "email": "smoke@test.com",
                "username": "smokeuser",
                "password": "Secure123!",
            },
        )
        print(f"REGISTER  [{r.status_code}]  {r.json()}\n")

        # 2) Login
        r = await c.post(
            "/api/v1/auth/login",
            json={"email": "smoke@test.com", "password": "Secure123!"},
        )
        print(f"LOGIN     [{r.status_code}]  {r.json()}\n")
        tokens = r.json()

        # 3) Refresh
        r = await c.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        print(f"REFRESH   [{r.status_code}]  {r.json()}\n")

        # 4) Me
        r = await c.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        print(f"ME        [{r.status_code}]  {r.json()}\n")

        # 5) Duplicate register
        r = await c.post(
            "/api/v1/auth/register",
            json={
                "email": "smoke@test.com",
                "username": "smokeuser",
                "password": "Secure123!",
            },
        )
        print(f"DUP REG   [{r.status_code}]  {r.json()}\n")

        # 6) Wrong password
        r = await c.post(
            "/api/v1/auth/login",
            json={"email": "smoke@test.com", "password": "wrong"},
        )
        print(f"BAD LOGIN [{r.status_code}]  {r.json()}\n")


asyncio.run(main())
