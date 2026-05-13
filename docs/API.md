# SmartCourse API Reference

All routes live under `/api/v1/`. Login uses OAuth2 password flow (form data); everything else uses JSON.

Interactive docs are available at [http://localhost:8000/docs](http://localhost:8000/docs) when the server is running.

---

## Auth

### Register

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@test.com",
    "password": "secret123",
    "full_name": "Alice",
    "role": "instructor"
  }'
```

Roles: `student` | `instructor` | `admin`. Password minimum 8 characters.

### Login → get JWT token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice@test.com&password=secret123"
```

Response:
```json
{ "access_token": "eyJhbGciOi...", "token_type": "bearer" }
```

Use the token on every protected endpoint via `Authorization: Bearer <token>`.

---

## Users

### Get own profile

```bash
curl http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN"
```

### Update own profile

```bash
curl -X PATCH http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "full_name": "Alice Updated" }'
```

Both `full_name` and `password` are optional — send only what you want to change.

### Get user by ID (admin only)

```bash
curl http://localhost:8000/api/v1/users/$USER_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Courses

### Create a course (instructor only)

```bash
curl -X POST http://localhost:8000/api/v1/courses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Intro to Distributed Systems",
    "description": "Foundations of scalable backend design",
    "max_students": 50
  }'
```

Course starts in `draft` status.

### List published courses (paginated)

```bash
curl "http://localhost:8000/api/v1/courses?limit=20&offset=0" \
  -H "Authorization: Bearer $TOKEN"
```

`limit` must be between 1 and 100. Only `published` courses are returned.

### Get a single course

```bash
curl http://localhost:8000/api/v1/courses/$COURSE_ID \
  -H "Authorization: Bearer $TOKEN"
```

Drafts and archived courses are visible only to the owner or admins; others get 404.

### Update a course (owner or admin only)

```bash
curl -X PATCH http://localhost:8000/api/v1/courses/$COURSE_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "status": "published" }'
```

Allowed status transitions: `draft → published`, `draft → archived`, `published → archived`. Anything else returns 409.

### Soft-delete (archive) a course

```bash
curl -X DELETE http://localhost:8000/api/v1/courses/$COURSE_ID \
  -H "Authorization: Bearer $TOKEN"
```

Sets `status = archived` rather than deleting — preserves enrollment and progress history.

---

## Modules

### Add a module to a course

```bash
curl -X POST http://localhost:8000/api/v1/courses/$COURSE_ID/modules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "title": "Module 1: Foundations", "order_index": 0 }'
```

`order_index` must be unique per course (DB-enforced, returns 409 on duplicates).

### List modules of a course

```bash
curl http://localhost:8000/api/v1/courses/$COURSE_ID/modules \
  -H "Authorization: Bearer $TOKEN"
```

Returned in ascending `order_index` order.

---

## Lessons

### Add a lesson to a module

```bash
curl -X POST http://localhost:8000/api/v1/courses/$COURSE_ID/modules/$MODULE_ID/lessons \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Intro video",
    "order_index": 0,
    "content_type": "video",
    "content_url": "https://cdn.example.com/intro.mp4",
    "duration_seconds": 600
  }'
```

`content_type` values: `video` | `text` | `pdf`. All content fields are optional except `title` and `order_index`.

---

## Error responses

All errors follow FastAPI's default shape:

```json
{ "detail": "Human-readable message" }
```

| Code | Meaning |
|---|---|
| 401 | Missing or invalid JWT, or wrong login credentials |
| 403 | Authenticated but lacks role / ownership |
| 404 | Resource not found (or hidden — draft courses look 404 to non-owners) |
| 409 | Conflict — duplicate email, invalid status transition, duplicate `order_index` |
| 422 | Pydantic validation failure (bad payload, wrong types, missing fields) |
| 500 | Unexpected server error — always logged with full traceback |
