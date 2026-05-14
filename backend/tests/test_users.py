async def test_register_creates_user(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "new@test.com", "password": "secret123", "role": "student"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@test.com"
    assert body["role"] == "student"
    assert body["is_active"] is True
    assert "hashed_password" not in body  # never leak password hash


async def test_register_duplicate_email_returns_409(client):
    payload = {"email": "dup@test.com", "password": "secret123", "role": "student"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


async def test_register_invalid_role_returns_422(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "x@test.com", "password": "secret123", "role": "superadmin"},
    )
    assert resp.status_code == 422


async def test_register_short_password_returns_422(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "x@test.com", "password": "short", "role": "student"},
    )
    assert resp.status_code == 422


async def test_register_invalid_email_returns_422(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "secret123", "role": "student"},
    )
    assert resp.status_code == 422


async def test_login_returns_token(client, student_headers):
    # student_headers fixture already logged in; just verify token format
    assert student_headers["Authorization"].startswith("Bearer ey")


async def test_login_wrong_password_returns_401(client, student_headers):
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "student@test.com", "password": "wrong"},
    )
    assert resp.status_code == 401


async def test_login_unknown_user_returns_401(client):
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "nobody@test.com", "password": "secret123"},
    )
    assert resp.status_code == 401


async def test_get_me_returns_profile(client, student_headers):
    resp = await client.get("/api/v1/users/me", headers=student_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "student@test.com"


async def test_get_me_without_token_returns_401(client):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


async def test_patch_me_updates_name(client, student_headers):
    resp = await client.patch(
        "/api/v1/users/me",
        headers=student_headers,
        json={"full_name": "New Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "New Name"


async def test_get_user_by_id_non_admin_returns_403(client, student_headers):
    me = await client.get("/api/v1/users/me", headers=student_headers)
    user_id = me.json()["id"]
    resp = await client.get(f"/api/v1/users/{user_id}", headers=student_headers)
    assert resp.status_code == 403
