# SmartCourse Frontend

React + Vite + TypeScript single-page app for the SmartCourse platform. It is a
thin client over the FastAPI backend — all business rules (ownership, role
checks, capacity, idempotency) stay on the server.

## Run

```bash
npm install
cp .env.example .env     # optional — defaults work for local dev
npm run dev              # http://localhost:5173
```

The backend must be running on `http://localhost:8000`. The Vite dev server
proxies every `/api/*` request to it (see `vite.config.ts`), so the browser
talks to a single origin and there is no CORS preflight in development.

```bash
npm run build            # type-check (tsc -b) + production bundle into dist/
npm run preview          # serve the production build locally
```

## Auth & role model

The backend is **stateless JWT** — there is no server session. The frontend
mirrors that:

- **Login** posts the OAuth2 password form to `/api/v1/auth/login` and receives
  a JWT. The token is stored in `localStorage` (`smartcourse_token`).
- An axios **request interceptor** attaches `Authorization: Bearer <token>` to
  every call.
- **Role is never read from the token on the client.** Right after
  authenticating, `AuthContext` calls `/users/me` and keeps the returned `User`
  (including `role`) in React state. Authorization-relevant UI is driven by that
  record, and the backend re-checks every request regardless.
- An axios **response interceptor** clears the token on any `401` and the route
  guards (`ProtectedRoute`) redirect to `/login`.

This keeps the client honest: a tampered token gets rejected by the backend, and
the UI only ever reflects what `/users/me` and the protected endpoints allow.

## Structure

```
src/
  api/         axios client (client.ts) + typed wrappers: auth, courses, enrollments
  auth/        AuthContext — login/logout, current user, 401 handling
  components/  Layout (nav), ProtectedRoute (auth + role guard), ui (badges/banners/etc.)
  pages/       one file per route; course-detail/ holds CourseDetailPage subcomponents
```

## Pages by role

| Route | Student | Instructor / Admin |
|---|---|---|
| `/courses` | Browse published courses; "Enrolled" markers | Browse published courses |
| `/courses/:id` | Enroll, view curriculum, mark lessons complete, see progress | Add modules/lessons, publish (Temporal), archive |
| `/my-courses` | — | Create courses; list all own courses (any status) |
| `/my-enrollments` | Enrollments + progress bars | — |
| `/profile` | View account, update name/password | same |

`types.ts` mirrors the backend Pydantic schemas by hand — the backend is the
source of truth, so keep them in sync when schemas change.
