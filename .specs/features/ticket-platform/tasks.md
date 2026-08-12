# Plataforma de Eventos e Ingressos — Tasks

## Execution Protocol (MANDATORY — do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user — do not proceed without it.**

**Commit convention for this project:** plain descriptive commit messages, **no `Co-Authored-By` trailer** (user preference, confirmed).

---

**Design**: `.specs/features/ticket-platform/design.md`
**Status**: Draft — aguardando confirmação para iniciar Execute

---

## Test Coverage Matrix

> Greenfield project — nenhum teste existente para amostrar. Nenhuma guideline de projeto encontrada (`AGENTS.md`/`CLAUDE.md`/`CONTRIBUTING.md` inexistentes). Stack de teste já decidida em `design.md` (pytest, SQLAlchemy 2.0). **Front-end fica sem suíte automatizada nesta rodada** — decisão de escopo explícita (ver linha "Front-end" abaixo e Tech Decision), QA manual via UAT interativo no Execute.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
|---|---|---|---|---|
| Lógica pura de domínio (hash/JWT, assinatura HMAC do QR, regra do cartão de teste) | unit | Todos os branches; 1:1 com ACs relevantes; sem I/O real (DB mockado/ausente, TMDb mockado) | `tests/unit/test_*.py` | `uv run pytest tests/unit -q` |
| Services com acesso a banco (booking, ticketing-validate, transfer, cancelamento) | integration | Happy path + todo edge case listado no spec + prova de atomicidade (corrida concorrente) contra Postgres real | `tests/integration/test_*.py` | `uv run pytest tests/integration -q` (requer `docker compose up -d db`) |
| Routers (contrato HTTP: status code, shape de resposta, guards de role) | integration | Happy + edge + erro por rota, via `TestClient`; a prova de concorrência em si já vem do teste de service — aqui só confere o contrato HTTP | `tests/integration/test_*.py` | mesmo comando acima |
| Models / schemas Pydantic / config | none | — | — | build gate only (`uv run ruff check .`) |
| Front-end (componentes, hooks, páginas) | none nesta rodada | Fora do orçamento de 7 dias; ver Tech Decision no design.md | — | `npm run build` (só type-check/build, sem testes) |

## Parallelism Assessment

> Sem testes existentes para amostrar — inferido do modelo de dados do `design.md` (Postgres compartilhado, transações reais provando os invariantes críticos).

| Test Type | Parallel-Safe? | Isolation Model | Evidence |
|---|---|---|---|
| unit (lógica pura) | Yes | Funções puras / dependências mockadas, sem DB, sem estado compartilhado | Nenhuma dessas funções toca `db/session.py` (design.md → `core/security.py`, parte de `catalog.py`, `payment_sim.py`) |
| integration (service/router) | No | Postgres real e compartilhado entre testes; mesmo com rollback por teste, testes de corrida deliberadamente commitam estado visível a duas conexões | `design.md` → concorrência de assento e validação de QR dependem de `UPDATE ... WHERE` real, não simulável em memória |
| integration — testes de corrida (hold duplo, validação dupla) | No | Precisam ser os únicos a tocar a linha/seat em questão no momento do teste; rodar em paralelo com outro teste tocando a mesma tabela corrompe o resultado | Mesmo motivo acima, ainda mais sensível |

## Gate Check Commands

| Gate Level | When to Use | Command |
|---|---|---|
| Quick | Após tasks só com testes unit (repo da API) | `uv run pytest tests/unit -q` |
| Full | Após tasks com testes integration (repo da API — services com DB, routers) | `docker compose up -d db && uv run pytest -q` |
| Build (API) | Fim de fase / tasks só de config/scaffolding no repo da API | `uv run ruff check .` |
| Build (Web) | Tasks de front-end (repo separado) | `npm run build` |

Cada comando roda a partir da raiz do repositório correspondente (`ticket-sales-platform-api` ou `ticket-sales-platform-web`) — os dois repos nunca compartilham um comando de gate, já que são checkouts independentes (ver AD-004).

---

## Execution Plan

### Phase 1: Foundation (Mixed — T01/T02 são repos independentes)
```
T01 (repo API) ─→ T03 ─→ T04
T02 (repo web) ── independente, sem dependentes na Fase 1
```
`T01` e `T02` não dependem uma da outra (repos distintos, AD-004) — rodam em qualquer ordem ou em paralelo. `T03`/`T04` dependem só de `T01`.

### Phase 2: Data Layer (Sequential)
```
T04 → T05 → T06 → T07 → T08 → T09
```

### Phase 3: Backend Services & Routes (Mixed)
```
T09 ─→ T10 ─→ T11 ─┬→ T13 ─┬→ T15 ─→ T16
                    │       ├→ T17 ─→ T19
       T12 ─────────┘       ├→ T18 ─┬→ T20 ─→ T21
                              │       ├→ T22
                              │       └→ T23 ─→ T24
                              └───────────────→ T25
```

### Phase 4: Frontend (Mixed — cada tarefa depende só do endpoint correspondente)
```
T11 ─→ T26 ─┬→ T27 ─→ T28 ─→ T29
             ├→ T30 ─→ T31
             ├→ T30 ─→ T35 (depende também de T24)
             ├→ T32 (depende também de T22)
             └→ T33, T34 (dependem também de T13/T25)
```

### Phase 5: Seed, Compose, Docs (Sequential)
```
T36 → T37 → T38 → T39
```

---

## Task Breakdown

### T01: `git init` do repo da API + scaffold do back-end (uv, FastAPI, config, Dockerfile)

**What**: `git init` no diretório `backend/` → esse diretório passa a ser a **raiz do repositório `ticket-sales-platform-api`** (o `.specs/` inteiro mora aqui, ver AD-004). `pyproject.toml` gerenciado por `uv` (FastAPI, SQLAlchemy, alembic, psycopg, pydantic-settings, python-jose ou pyjwt, bcrypt, httpx, pytest, ruff), `app/main.py` com app FastAPI mínimo (`GET /health`), `app/core/config.py` (Settings via `pydantic-settings`: `DATABASE_URL`, `JWT_SECRET`, `QR_SECRET_KEY`, `TMDB_API_KEY`, `SEAT_HOLD_MINUTES=5`, `TRANSFER_EXPIRY_HOURS=24`, `CANCEL_WINDOW_HOURS=2`), `Dockerfile` multi-stage (build stage `uv sync --frozen`, runtime stage copia `.venv` + código), `.gitignore` (Python/uv/DB).
**Where**: raiz do repo `ticket-sales-platform-api` (= diretório `backend/` local)
**Depends on**: None
**Reuses**: n/a
**Requirement**: infra (AD-001, AD-002, AD-004)

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] `git log` mostra o repo inicializado, `.specs/` versionado como primeiro commit (ou neste mesmo commit)
- [ ] `uv run uvicorn app.main:app` sobe local e `GET /health` retorna 200
- [ ] `docker build -t ticket-sales-platform-api .` conclui com sucesso
- [ ] `.env.example` documenta todas as env vars, sem segredo real

**Tests**: none (config/scaffold)
**Gate**: build
**Commit**: `chore: scaffold FastAPI project with uv`

---

### T02: `git init` do repo web + scaffold do front-end (Vite, React, TS, Router, React Query)

**What**: `git init` no diretório `frontend/` → esse diretório passa a ser a **raiz do repositório `ticket-sales-platform-web`**, independente do repo da API (ver AD-004). `npm create vite -- --template react-ts`, instala `react-router-dom`, `@tanstack/react-query`, configura cliente HTTP base (`src/api/client.ts` com `fetch` + injeção de `Authorization` a partir de um token em `localStorage`, base URL de `import.meta.env.VITE_API_URL`), `Dockerfile` multi-stage (build stage `npm run build`, runtime stage `nginx:alpine` servindo `dist/`), `.env.example` (`VITE_API_URL=http://localhost:8000`), `.gitignore` (Node).
**Where**: raiz do repo `ticket-sales-platform-web` (= diretório `frontend/` local)
**Depends on**: None
**Reuses**: n/a
**Requirement**: infra (AD-002, AD-004)

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] `git log` mostra o repo inicializado
- [ ] `npm run dev` sobe local sem erro
- [ ] `npm run build` gera `dist/` sem erro de tipo
- [ ] `docker build -t ticket-sales-platform-web .` conclui com sucesso

**Tests**: none
**Gate**: build
**Commit**: `chore: scaffold Vite React TS project`

---

### T03: `docker-compose.yml` do repo da API (db + api, autocontido)

**What**: Serviço `db` (postgres:16-alpine, volume nomeado, healthcheck `pg_isready`), `api` (build `.`, `depends_on: db: condition: service_healthy`, env do `.env`), rede compartilhada, portas expostas (`5432`, `8000`). **Sem serviço de frontend** — ele vive no outro repo e fala com esta API via `VITE_API_URL` (ver AD-004).
**Where**: `docker-compose.yml`, `.env.example` (raiz do repo da API)
**Depends on**: T01
**Reuses**: Dockerfile de T01

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] `docker compose up` sobe `db`+`api` sem erro (mesmo sem migrations/seed ainda — api só precisa responder `/health`)
- [ ] `db` fica `healthy` antes do `api` iniciar

**Tests**: none
**Gate**: build
**Commit**: `chore: add docker-compose for db and api`

---

### T04: Alembic init + conexão de sessão + mixins de base

**What**: `alembic init alembic`, configura `env.py` para ler `DATABASE_URL` de `Settings`, `app/db/base.py` (`Base = declarative_base()`), `app/db/session.py` (`engine`, `SessionLocal`, `get_db` dependency). **Inclui** `app/models/mixins.py` — `UUIDPKMixin` (`id: UUID` pk, `default=uuid4`) e `TimestampMixin` (`created_at`/`updated_at`, `server_default=func.now()`, `onupdate` em `updated_at`) — todo model das próximas tasks herda de `Base, UUIDPKMixin, TimestampMixin`, nunca redeclarando esses 3 campos. Também `app/schemas/base.py` — `BaseReadSchema` (Pydantic, `id`+`created_at`+`updated_at`, `from_attributes=True`) que todo schema de resposta (T11+) herda pelo mesmo motivo.
**Where**: `alembic/`, `app/db/`, `app/models/mixins.py`, `app/schemas/base.py`
**Depends on**: T01
**Reuses**: `app/core/config.py`

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] `alembic upgrade head` roda sem erro contra o Postgres do compose (mesmo sem tabelas ainda)
- [ ] `get_db()` abre e fecha sessão corretamente (smoke test manual via `/health` estendido a fazer um `SELECT 1`)
- [ ] Um model de teste descartável herdando os 2 mixins gera `id`/`created_at`/`updated_at` corretos (removido antes do commit — só serviu de prova)

**Tests**: none
**Gate**: build
**Commit**: `chore(db): configure Alembic, DB session and base mixins`

---

### T05: Model `User` + enum `Role`

**What**: `app/models/user.py` — `class User(Base, UUIDPKMixin, TimestampMixin)`: `email unique, password_hash, role[CLIENTE|ORGANIZADOR|PORTARIA], name`. `id`/`created_at`/`updated_at` vêm dos mixins de T04, não redeclarados.
**Where**: `app/models/user.py`
**Depends on**: T04
**Reuses**: `app/models/mixins.py` (T04)
**Requirement**: AUTH-01

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Model importável, mapeado em `Base.metadata`, herda `UUIDPKMixin`+`TimestampMixin` (sem campo `id`/`created_at`/`updated_at` redeclarado na classe)
- [ ] `ruff check` limpo

**Tests**: none (entity)
**Gate**: build
**Commit**: `feat(models): add User model with role enum`

---

### T06: Models `Event` + `Seat`

**What**: `app/models/event.py` (`class Event(Base, UUIDPKMixin, TimestampMixin)`: `organizer_id fk`, `tmdb_movie_id`, `title`, `poster_url`, `venue`, `starts_at`, `rows`, `seats_per_row`, `capacity`, `price_cents`, `status`), `app/models/seat.py` (`class Seat(Base, UUIDPKMixin, TimestampMixin)`: `event_id fk`, `row_label`, `seat_number`, `status[LIVRE|HOLD|VENDIDO]`, `current_ticket_id fk nullable`, `UNIQUE(event_id, row_label, seat_number)`).
**Where**: `app/models/event.py`, `app/models/seat.py`
**Depends on**: T05
**Reuses**: `app/models/mixins.py` (T04)
**Requirement**: CATALOG-02

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Models importáveis, FK e unique constraint corretos
- [ ] `ruff check` limpo

**Tests**: none (entity)
**Gate**: build
**Commit**: `feat(models): add Event and Seat models`

---

### T07: Models `Ticket` + `PaymentAttempt`

**What**: `app/models/ticket.py` (`class Ticket(Base, UUIDPKMixin, TimestampMixin)`: `event_id fk`, `seat_id fk`, `owner_id fk`, `status[HELD|PAID|USED|CANCELLED|EXPIRED|TRANSFERRED]`, `qr_secret`, e os timestamps de **domínio** `held_at`, `expires_at`, `paid_at`, `used_at`, `cancelled_at` — esses ficam explícitos na classe, não vêm do mixin, ver rationale em `design.md`), `app/models/payment_attempt.py` (`class PaymentAttempt(Base, UUIDPKMixin, TimestampMixin)`: `ticket_id fk`, `card_last4`, `result[APPROVED|DECLINED]`).
**Where**: `app/models/ticket.py`, `app/models/payment_attempt.py`
**Depends on**: T06
**Reuses**: `app/models/mixins.py` (T04)
**Requirement**: BOOKING-01, TICKETS-01

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Models importáveis, FKs corretos
- [ ] `ruff check` limpo

**Tests**: none (entity)
**Gate**: build
**Commit**: `feat(models): add Ticket and PaymentAttempt models`

---

### T08: Models `TransferInvite` + `FakeEmailLog`

**What**: `app/models/transfer_invite.py` (`class TransferInvite(Base, UUIDPKMixin, TimestampMixin)`: `ticket_id fk`, `from_user_id fk`, `to_email`, `to_user_id fk nullable`, `token unique`, `status[PENDING|ACCEPTED|DECLINED|CANCELLED|EXPIRED]`, `expires_at` — calculado como `created_at` do mixin `+ 24h`), `app/models/fake_email_log.py` (`class FakeEmailLog(Base, UUIDPKMixin, TimestampMixin)`: `to_email`, `subject`, `body`).
**Where**: `app/models/transfer_invite.py`, `app/models/fake_email_log.py`
**Depends on**: T07
**Reuses**: `app/models/mixins.py` (T04)
**Requirement**: TRANSFER-01, TRANSFER-03

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Models importáveis
- [ ] `ruff check` limpo

**Tests**: none (entity)
**Gate**: build
**Commit**: `feat(models): add TransferInvite and FakeEmailLog models`

---

### T09: Migration Alembic inicial (todas as tabelas)

**What**: `alembic revision --autogenerate -m "initial schema"`, revisão manual do arquivo gerado (índices, enums, unique constraints conferidos).
**Where**: `alembic/versions/`
**Depends on**: T05, T06, T07, T08
**Requirement**: infra

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] `alembic upgrade head` cria todas as tabelas no Postgres do compose
- [ ] `alembic downgrade base` reverte sem erro (prova que a migration é reversível)

**Tests**: none
**Gate**: full (precisa do Postgres rodando)
**Commit**: `chore(db): add initial schema migration`

---

### T10: `core/security.py` — hash, JWT, guards de role

**What**: `hash_password`/`verify_password` (bcrypt), `create_access_token`/`decode_access_token` (JWT, claims `sub`+`role`, expira em 60min), dependency `get_current_user`, factory `require_role(*roles)`.
**Where**: `app/core/security.py`
**Depends on**: T09
**Requirement**: AUTH-02, AUTH-03, AUTH-04

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Hash roundtrip (`verify_password(plain, hash_password(plain))` é `True`; senha errada é `False`)
- [ ] Token roundtrip (`decode_access_token(create_access_token(user))` retorna claims corretos)
- [ ] Token expirado é rejeitado
- [ ] `require_role` permite papel certo e barra os outros (403)
- [ ] Gate check passa: `uv run pytest tests/unit -q`
- [ ] Test count: ≥6 testes passam

**Tests**: unit (`tests/unit/test_security.py`)
**Gate**: quick
**Commit**: `feat(auth): add password hashing, JWT and role guards`

---

### T11: Router de autenticação (`/auth`)

**What**: `POST /auth/register` (cria `CLIENTE`, único self-signup), `POST /auth/login` (retorna JWT), `GET /auth/me`.
**Where**: `app/api/v1/auth.py`, `app/schemas/auth.py`
**Depends on**: T10, T05
**Requirement**: AUTH-01, AUTH-04

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Registro cria usuário `CLIENTE`, e-mail duplicado retorna 409
- [ ] Login correto retorna 200 + token; login errado retorna 401 genérico (não revela se e-mail existe)
- [ ] `/auth/me` sem token retorna 401; com token retorna dados do usuário
- [ ] Gate check passa: `docker compose up -d db && uv run pytest -q`
- [ ] Test count: ≥5 testes passam

**Tests**: integration (`tests/integration/test_auth.py`)
**Gate**: full
**Commit**: `feat(auth): add register, login and me endpoints`

---

### T12: `services/catalog.py` — cliente TMDb [P]

**What**: `search_movies(query: str) -> list[MovieResult]` chamando `GET /search/movie` da TMDb (`api_key` via `Settings.TMDB_API_KEY`), mapeando timeout/erro HTTP para `CatalogUnavailableError`.
**Where**: `app/services/catalog.py`
**Depends on**: T01
**Reuses**: `app/core/config.py`
**Requirement**: CATALOG-01, CATALOG-03

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Busca com resposta mockada (httpx mock) retorna lista mapeada corretamente
- [ ] Timeout/erro HTTP mockado levanta `CatalogUnavailableError` (não deixa exceção genérica vazar)
- [ ] Gate check passa: `uv run pytest tests/unit -q`
- [ ] Test count: ≥3 testes passam

**Tests**: unit (`tests/unit/test_catalog.py`, com `httpx` mockado — sem chamada de rede real)
**Gate**: quick
**Commit**: `feat(catalog): add TMDb search client`

---

### T13: Router de eventos (`/events`) — criar, listar, buscar/filtrar, detalhe com mapa

**What**: `POST /events` (organizador; usa `catalog.search_movies` pra validar filme, cria `Event`+grade de `Seat`s a partir de `rows`×`seats_per_row`, calcula `capacity`), `GET /events` (público; filtros `q`, `date_from`, `date_to`, `price_min`, `price_max`), `GET /events/{id}` (detalhe + mapa de assentos — chama `booking.sweep_expired_holds` antes de ler, ver T14).
**Where**: `app/api/v1/events.py`, `app/schemas/event.py`
**Depends on**: T12, T06, T11
**Requirement**: CATALOG-01..04, SEARCH-01..03

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Criação com filme válido gera evento + N assentos (`rows*seats_per_row`)
- [ ] Criação com data passada, capacidade zero ou preço negativo retorna 422 com erro por campo
- [ ] Falha simulada da TMDb retorna 502 claro, sem persistir evento
- [ ] Filtro por texto/data/preço retorna só o esperado; sem match retorna lista vazia com metadado explícito (não 404)
- [ ] Gate check passa: `docker compose up -d db && uv run pytest -q`
- [ ] Test count: ≥8 testes passam

**Tests**: integration (`tests/integration/test_events.py`)
**Gate**: full
**Commit**: `feat(events): add create, list, filter and detail endpoints`

---

### T14: `services/booking.py` — hold atômico + expiração

**What**: `hold_seat(event_id, seat_id, user_id) -> Ticket` (`UPDATE seats SET status='HOLD' WHERE id=? AND status='LIVRE'`; 0 linhas → `SeatUnavailableError`; cria `Ticket(status=HELD, expires_at=now+SEAT_HOLD_MINUTES)`), `sweep_expired_holds(event_id=None) -> int` (libera holds vencidos em lote), `cancel_ticket(ticket, actor) -> Ticket` (usada por T21 — regra de janela de 2h + libera assento).
**Where**: `app/services/booking.py`
**Depends on**: T06, T07
**Requirement**: BOOKING-03, BOOKING-04, BOOKING-05, CANCEL-01, CANCEL-02, CANCEL-03

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] `hold_seat` num assento `LIVRE` cria `Ticket HELD` e muda `seat.status`
- [ ] `hold_seat` num assento já `HOLD`/`VENDIDO` levanta `SeatUnavailableError`
- [ ] **Prova de concorrência**: duas threads chamando `hold_seat` pro mesmo assento simultaneamente (sessões de DB separadas) — exatamente uma sucede, a outra recebe `SeatUnavailableError`
- [ ] `sweep_expired_holds` libera hold com `expires_at` no passado e não mexe em holds ainda válidos
- [ ] `cancel_ticket` dentro da janela de 2h libera o assento; fora da janela levanta `CancelWindowError`; ticket `USED`/`TRANSFERRED` levanta `InvalidTicketStateError`
- [ ] Gate check passa: `docker compose up -d db && uv run pytest -q`
- [ ] Test count: ≥8 testes passam

**Tests**: integration (`tests/integration/test_booking_concurrency.py` — inclui o teste de corrida)
**Gate**: full
**Commit**: `feat(booking): add atomic seat hold, expiry sweep and cancellation`

---

### T15: Router de reserva (`POST /events/{id}/seats/{seat_id}/hold`)

**What**: Endpoint que chama `booking.hold_seat`, retorna `Ticket HELD` + `expires_at`; mapeia `SeatUnavailableError` pra 409.
**Where**: `app/api/v1/bookings.py`
**Depends on**: T14, T11
**Requirement**: BOOKING-03, BOOKING-04

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Hold de assento livre retorna 201 com `expires_at`
- [ ] Hold de assento já ocupado retorna 409 (contrato HTTP — a prova de corrida já está em T14)
- [ ] Só `CLIENTE` autenticado acessa (401/403 nos outros casos)
- [ ] Gate check passa: `docker compose up -d db && uv run pytest -q`
- [ ] Test count: ≥4 testes passam

**Tests**: integration (`tests/integration/test_bookings.py`)
**Gate**: full
**Commit**: `feat(bookings): add seat hold endpoint`

---

### T16: Scheduler in-process (sweep periódico)

**What**: `APScheduler` (`BackgroundScheduler` ou `AsyncIOScheduler`) registrado no `lifespan` do `app/main.py`, chamando `booking.sweep_expired_holds()` a cada 60s.
**Where**: `app/main.py`
**Depends on**: T14
**Requirement**: BOOKING-05

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] App sobe com o scheduler ativo (log confirma início do job)
- [ ] Teste manual: criar hold com `SEAT_HOLD_MINUTES` baixo via env de teste, esperar o ciclo, ver assento voltar a `LIVRE` sem chamada externa

**Tests**: none (smoke coberto pelo teste de integração de T14; scheduler em si não precisa de teste dedicado — é fiação de infra)
**Gate**: build
**Commit**: `chore(scheduler): wire periodic hold-expiry sweep`

---

### T17: `services/payment_sim.py`

**What**: `attempt_payment(ticket_id, card_number) -> PaymentResult` — recusa se `card_number` termina em `"0000"`, senão aprova; grava `PaymentAttempt`; se aprovado, chama `ticketing.issue(ticket)` (T18) e marca `Ticket.status=PAID`.
**Where**: `app/services/payment_sim.py`
**Depends on**: T07, T14
**Requirement**: BOOKING-06, BOOKING-07, BOOKING-08

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Cartão terminado em `0000` recusa, ticket continua `HELD`, `PaymentAttempt(DECLINED)` gravado
- [ ] Cartão normal aprova, ticket vira `PAID`, `qr_secret` gerado, `PaymentAttempt(APPROVED)` gravado
- [ ] Tentativa de pagar ticket com hold expirado levanta `HoldExpiredError`
- [ ] Gate check passa: `docker compose up -d db && uv run pytest -q`
- [ ] Test count: ≥5 testes passam

**Tests**: integration (`tests/integration/test_payment_sim.py`)
**Gate**: full
**Commit**: `feat(payments): add simulated payment decision logic`

---

### T18: `services/ticketing.py` — emissão e validação de QR

**What**: `issue(ticket) -> str` (gera `qr_secret`, monta payload `f"{ticket.id}.{qr_secret}"`, assina HMAC-SHA256 com `QR_SECRET_KEY`), `validate(raw_token, gate_event_id) -> GateResult` (`INVALIDO`/`JA_UTILIZADO`/`EVENTO_ERRADO`/`VALIDO`; transição atômica `UPDATE tickets SET status='USED' WHERE id=? AND status='PAID'`).
**Where**: `app/services/ticketing.py`
**Depends on**: T07
**Requirement**: GATE-01, GATE-02, GATE-03, GATE-04, GATE-06

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] `issue` gera token válido e verificável
- [ ] `validate` com assinatura adulterada retorna `INVALIDO`
- [ ] `validate` de ticket `PAID` do evento certo retorna `VALIDO` e muda status pra `USED`
- [ ] `validate` de ticket já `USED` retorna `JA_UTILIZADO` sem alterar `used_at`
- [ ] `validate` com `event_id` diferente retorna `EVENTO_ERRADO`
- [ ] **Prova de concorrência**: duas chamadas simultâneas de `validate` pro mesmo ticket — exatamente uma retorna `VALIDO`, a outra `JA_UTILIZADO`
- [ ] Gate check passa: `docker compose up -d db && uv run pytest -q`
- [ ] Test count: ≥8 testes passam

**Tests**: integration (`tests/integration/test_ticketing.py` — inclui o teste de corrida)
**Gate**: full
**Commit**: `feat(ticketing): add signed QR issuance and atomic validation`

---

### T19: Router de pagamento (`POST /tickets/{id}/pay`)

**What**: Endpoint que chama `payment_sim.attempt_payment`, retorna resultado (aprovado c/ ticket `PAID` ou recusado c/ motivo).
**Where**: `app/api/v1/payments.py`
**Depends on**: T17
**Requirement**: BOOKING-06, BOOKING-07

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Pagamento aprovado retorna 200 + ticket `PAID`
- [ ] Pagamento recusado retorna 200 + `status: DECLINED` (não é erro HTTP, é resultado de negócio) e hold continua ativo
- [ ] Pagamento em hold expirado retorna 410
- [ ] Gate check passa: `docker compose up -d db && uv run pytest -q`
- [ ] Test count: ≥4 testes passam

**Tests**: integration (`tests/integration/test_payments.py`)
**Gate**: full
**Commit**: `feat(payments): add payment endpoint`

---

### T20: Router de ingressos (`/tickets` — meus ingressos + detalhe com QR)

**What**: `GET /tickets` (lista do cliente autenticado, todos os status), `GET /tickets/{id}` (detalhe + QR renderizável — token de T18).
**Where**: `app/api/v1/tickets.py`, `app/schemas/ticket.py`
**Depends on**: T18, T07
**Requirement**: TICKETS-01, TICKETS-02, TICKETS-03

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Lista só retorna ingressos do próprio usuário
- [ ] Detalhe de ticket `PAID` retorna o token do QR
- [ ] Detalhe de ticket `USED`/`CANCELLED`/`TRANSFERRED` não expõe QR como "apresentável" (campo/flag explícito)
- [ ] Gate check passa: `docker compose up -d db && uv run pytest -q`
- [ ] Test count: ≥4 testes passam

**Tests**: integration (`tests/integration/test_tickets.py`)
**Gate**: full
**Commit**: `feat(tickets): add list and detail endpoints with QR token`

---

### T21: Endpoint de cancelamento (`POST /tickets/{id}/cancel`)

**What**: Chama `booking.cancel_ticket` (T14), retorna ticket `CANCELLED` ou erro de janela/estado.
**Where**: `app/api/v1/tickets.py` (extensão)
**Depends on**: T20, T14
**Requirement**: CANCEL-01, CANCEL-02, CANCEL-03

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Cancelamento >2h antes do evento retorna 200, ticket `CANCELLED`, assento volta a `LIVRE`
- [ ] Cancelamento <2h antes retorna 422 com mensagem clara
- [ ] Cancelamento de ticket `USED`/`TRANSFERRED` retorna 422
- [ ] Gate check passa: `docker compose up -d db && uv run pytest -q`
- [ ] Test count: ≥3 testes passam (a lógica de janela já foi provada em T14 — aqui é só o contrato HTTP)

**Tests**: integration (`tests/integration/test_tickets.py`, ampliado)
**Gate**: full
**Commit**: `feat(tickets): add cancellation endpoint`

---

### T22: Router de portaria (`POST /gate/validate`)

**What**: Endpoint `PORTARIA`-only, aceita `{token}` (do scanner) ou `{manual_code}` (equivalente ao token digitado), chama `ticketing.validate`, retorna `VALIDO`/`INVALIDO`/`JA_UTILIZADO`/`EVENTO_ERRADO` + dados do assento/cliente quando `VALIDO`.
**Where**: `app/api/v1/gate.py`
**Depends on**: T18, T11
**Requirement**: GATE-01..05

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Cada um dos 4 resultados é alcançável via chamada HTTP com fixtures correspondentes (contrato — a atomicidade em si já está provada em T18)
- [ ] Só `PORTARIA` acessa (403 pros outros papéis)
- [ ] `manual_code` produz exatamente o mesmo resultado que o `token` do QR pro mesmo ingresso
- [ ] Gate check passa: `docker compose up -d db && uv run pytest -q`
- [ ] Test count: ≥6 testes passam

**Tests**: integration (`tests/integration/test_gate.py`)
**Gate**: full
**Commit**: `feat(gate): add ticket validation endpoint`

---

### T23: `services/transfer.py` — handshake de transferência

**What**: `create_invite(ticket_id, from_user_id, to_email) -> TransferInvite` (só ticket `PAID`; se `to_email` não bate com usuário existente, grava `FakeEmailLog`), `accept(token, accepting_user_id) -> Ticket` (transação atômica: ticket original `TRANSFERRED`, novo ticket `PAID` c/ novo `qr_secret` pro novo dono, `seat.current_ticket_id` atualizado), `decline(token)`, `cancel_invite(token, owner_id)`.
**Where**: `app/services/transfer.py`
**Depends on**: T07, T08, T18
**Requirement**: TRANSFER-01..06

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] `create_invite` de ticket não-`PAID` levanta `InvalidTicketStateError`
- [ ] `create_invite` com e-mail sem conta grava `FakeEmailLog` e ainda cria o convite `PENDING`
- [ ] `accept` transfere titularidade atomicamente: ticket original `TRANSFERRED`, novo ticket `PAID` com QR **diferente** do original, some da lista ativa do dono antigo
- [ ] `decline`/`cancel_invite`/expiração mantêm o ticket original `PAID` ativo e invalidam o link
- [ ] Convite expirado (`expires_at` no passado) não pode ser aceito
- [ ] Gate check passa: `docker compose up -d db && uv run pytest -q`
- [ ] Test count: ≥8 testes passam

**Tests**: integration (`tests/integration/test_transfer.py`)
**Gate**: full
**Commit**: `feat(transfer): add ticket ownership handshake`

---

### T24: Router de transferência (`/transfers`)

**What**: `POST /tickets/{id}/transfers` (cria convite), `GET /transfers/{token}` (visualizar convite — exige login), `POST /transfers/{token}/accept`, `POST /transfers/{token}/decline`, `POST /transfers/{id}/cancel` (dono cancela pendente).
**Where**: `app/api/v1/transfers.py`
**Depends on**: T23, T11
**Requirement**: TRANSFER-01..06

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Fluxo feliz completo via HTTP: criar → visualizar (autenticado) → aceitar → ticket aparece pro novo dono
- [ ] Visualizar sem estar logado retorna 401 (front trata redirecionando pro login, ver T35)
- [ ] Cancelar convite pendente invalida o token (tentativa de aceite depois retorna 410)
- [ ] Gate check passa: `docker compose up -d db && uv run pytest -q`
- [ ] Test count: ≥5 testes passam

**Tests**: integration (`tests/integration/test_transfers_router.py`)
**Gate**: full
**Commit**: `feat(transfers): add invite create/view/accept/decline/cancel endpoints`

---

### T25: Painel do organizador (`/organizer/events`)

**What**: `GET /organizer/events` (eventos do organizador autenticado + `% vendido` = `count(tickets PAID+USED)/capacity`), `GET /organizer/events/{id}/seats` (mapa com status por assento + quem comprou, quando relevante).
**Where**: `app/api/v1/organizer.py`, `app/services/organizer.py`
**Depends on**: T06, T07, T13
**Requirement**: DASH-01, DASH-02

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Lista só mostra eventos do organizador autenticado, com `% vendido` correto
- [ ] Mapa de assentos reflete `LIVRE`/`HOLD`/`VENDIDO`/histórico de `CANCELLED` corretamente
- [ ] Organizador não acessa eventos de outro organizador (403/404)
- [ ] Gate check passa: `docker compose up -d db && uv run pytest -q`
- [ ] Test count: ≥5 testes passam

**Tests**: integration (`tests/integration/test_organizer.py`)
**Gate**: full
**Commit**: `feat(organizer): add dashboard endpoints with occupancy`

---

### Checkpoint: `/security-review` ao fim da Fase 3

**What**: Antes de iniciar o front-end (T26), rodar a skill `security-review` sobre todo o backend (T01–T25) — foco declarado do usuário em auth (T10/T11), assinatura/validação de QR (T18) e simulação de pagamento (T17), os pontos mais sensíveis do desafio ("QR não pode ser forjado", guards de papel, dados de pagamento).
**Depends on**: T10–T25 completos
**Done when**:
- [ ] Review rodado e achados triados: `CONFIRMED` vira task de correção antes de seguir; `PLAUSIBLE` fica registrado em `STATE.md`/`LESSONS.md` conforme o fluxo padrão do `tlc-spec-driven`
- [ ] Nenhum achado `CONFIRMED` de severidade alta/crítica sem correção aplicada

Não é uma task de código — não gera commit próprio; correções decorrentes viram tasks/commits normais.

---

### T26: Front — API client, AuthContext, login/registro, `ProtectedRoute`

**What**: `src/api/client.ts` (wrapper fetch com base URL + header de auth), `src/auth/AuthContext.tsx` (estado de usuário/token, persistido em `localStorage`), `src/features/auth/LoginPage.tsx`, `RegisterPage.tsx`, `src/auth/ProtectedRoute.tsx` (guarda por papel, redireciona pra login preservando destino).
**Where**: `src/api/`, `src/auth/`, `src/features/auth/`
**Depends on**: T11
**Requirement**: AUTH-01, AUTH-04

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Login/registro funcionam contra o backend real (manual, via UAT — sem suíte automatizada nesta rodada)
- [ ] Rota protegida sem login redireciona pra `/login`; depois do login volta pra rota original
- [ ] Gate check passa: `npm run build`

**Tests**: none (front sem suíte automatizada — ver Test Coverage Matrix)
**Gate**: build
**Commit**: `feat(auth): add login, register and protected routes`

---

### T27: Front — listagem de eventos com busca/filtro

**What**: `src/features/events/EventsListPage.tsx` (grid de cards: pôster, título, data, local, preço), barra de busca + filtros (data, faixa de preço) usando React Query contra `GET /events`.
**Where**: `src/features/events/`
**Depends on**: T13, T26
**Requirement**: SEARCH-01..03

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Lista carrega e exibe eventos seedados
- [ ] Filtro sem resultado mostra estado vazio explícito (não lista em branco sem explicação)
- [ ] Gate check passa: `npm run build`

**Tests**: none
**Gate**: build
**Commit**: `feat(events): add listing page with search and filters`

---

### T28: Front — detalhe do evento + mapa de assentos

**What**: `src/features/events/EventDetailPage.tsx`, `src/features/events/SeatMap.tsx` (grade clicável, cor por status: livre/hold/vendido), clique em assento livre inicia hold (T15).
**Where**: `src/features/events/`
**Depends on**: T13, T15, T26
**Requirement**: BOOKING-02, BOOKING-03

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Mapa reflete status real do backend
- [ ] Clique em assento livre chama o hold e navega pro checkout (T29)
- [ ] Clique em assento ocupado é bloqueado visualmente
- [ ] Gate check passa: `npm run build`

**Tests**: none
**Gate**: build
**Commit**: `feat(booking): add event detail page with seat map`

---

### T29: Front — checkout (hold countdown + pagamento simulado)

**What**: `src/features/booking/CheckoutPage.tsx` (countdown de 5min visível, formulário de "cartão" simulado), telas de resultado (aprovado → vai pro ingresso; recusado → permite nova tentativa dentro do hold).
**Where**: `src/features/booking/`
**Depends on**: T15, T19, T26
**Requirement**: BOOKING-06, BOOKING-07, BOOKING-08

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Countdown visível e preciso (baseado em `expires_at` do backend, não em timer client-side isolado)
- [ ] Cartão terminado em `0000` mostra tela de recusa; qualquer outro mostra sucesso
- [ ] Hold expirado durante o checkout mostra mensagem clara e redireciona pro mapa
- [ ] Gate check passa: `npm run build`

**Tests**: none
**Gate**: build
**Commit**: `feat(booking): add checkout flow with simulated payment`

---

### T30: Front — "Meus ingressos" + detalhe com QR

**What**: `src/features/tickets/MyTicketsPage.tsx` (lista com status visual), `src/features/tickets/TicketDetailPage.tsx` (QR via `qrcode.react`, some quando não `PAID`).
**Where**: `src/features/tickets/`
**Depends on**: T20, T26
**Requirement**: TICKETS-01..03

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Lista mostra todos os ingressos do cliente com status correto
- [ ] QR renderiza corretamente pra ingresso `PAID`
- [ ] Gate check passa: `npm run build`

**Tests**: none
**Gate**: build
**Commit**: `feat(tickets): add my-tickets list and detail page with QR`

---

### T31: Front — UI de cancelamento

**What**: Botão "Cancelar ingresso" no `TicketDetailPage`, modal de confirmação, mensagem de erro clara quando fora da janela.
**Where**: `src/features/tickets/`
**Depends on**: T21, T30
**Requirement**: CANCEL-01, CANCEL-02

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Cancelamento bem-sucedido reflete na UI (status muda, assento liberado no mapa se o usuário revisitar o evento)
- [ ] Erro de janela mostra a mensagem do backend, não um erro genérico
- [ ] Gate check passa: `npm run build`

**Tests**: none
**Gate**: build
**Commit**: `feat(tickets): add cancellation UI`

---

### T32: Front — tela de portaria (scanner + fallback manual)

**What**: `src/features/gate/GatePage.tsx` — seletor de evento, câmera via `html5-qrcode`, campo de digitação manual como alternativa, banner de resultado grande e inequívoco (verde=válido, vermelho=inválido/já usado/evento errado).
**Where**: `src/features/gate/`
**Depends on**: T22, T26
**Requirement**: GATE-01..05

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Câmera lê QR e mostra resultado correto pros 4 casos
- [ ] Sem permissão de câmera, o campo manual funciona como alternativa equivalente
- [ ] Gate check passa: `npm run build`

**Tests**: none
**Gate**: build
**Commit**: `feat(gate): add QR scanner and manual code validation UI`

---

### T33: Front — criação de evento pelo organizador

**What**: `src/features/organizer/CreateEventPage.tsx` — busca de filme (autocomplete contra `catalog`), formulário de data/local/linhas×colunas/preço, preview do mapa antes de publicar.
**Where**: `src/features/organizer/`
**Depends on**: T13, T26
**Requirement**: CATALOG-01..04

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Busca retorna filmes reais da TMDb
- [ ] Publicação cria o evento e aparece na listagem pública
- [ ] Erros de validação (data passada, capacidade zero) aparecem por campo
- [ ] Gate check passa: `npm run build`

**Tests**: none
**Gate**: build
**Commit**: `feat(organizer): add event creation page`

---

### T34: Front — painel do organizador (ocupação + mapa por evento)

**What**: `src/features/organizer/DashboardPage.tsx` (lista de eventos + % vendido), `src/features/organizer/EventOccupancyPage.tsx` (mapa de assentos read-only com status).
**Where**: `src/features/organizer/`
**Depends on**: T25, T26
**Requirement**: DASH-01, DASH-02

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Lista mostra os eventos seedados com ocupação correta
- [ ] Mapa por evento reflete o status real dos assentos
- [ ] Gate check passa: `npm run build`

**Tests**: none
**Gate**: build
**Commit**: `feat(organizer): add occupancy dashboard`

---

### T35: Front — compartilhar/transferir ingresso

**What**: Botão "Transferir" no `TicketDetailPage` (form de e-mail do destinatário), página `TransferInvitePage.tsx` (rota `/transfers/:token` — mostra dados do ingresso + aceitar/recusar; se não logado, redireciona pro login preservando o retorno ao convite).
**Where**: `src/features/tickets/`, `src/features/transfer/`
**Depends on**: T24, T30
**Requirement**: TRANSFER-01..06

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Dono cria convite e vê link gerado
- [ ] Destinatário logado aceita e o ingresso muda de dono nas duas contas
- [ ] Destinatário sem conta é direcionado ao cadastro e retorna ao convite depois
- [ ] Gate check passa: `npm run build`

**Tests**: none
**Gate**: build
**Commit**: `feat(transfer): add share and accept/decline invite UI`

---

### T36: Seed de dados de teste

**What**: `app/seed.py` (idempotente — checa existência antes de inserir): 1 organizador, 2 clientes, 1 portaria, ≥1 evento publicado com mapa de assentos variado (alguns `LIVRE`, ao menos 1 `HOLD`, ao menos 1 `VENDIDO` com ticket `PAID` pronto pra demo de portaria).
**Where**: `app/seed.py`
**Depends on**: T05, T06, T07, T08
**Requirement**: dados de teste (requisito não funcional do PDF)

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] `uv run python -m app.seed` roda 2x seguidas sem duplicar dados
- [ ] Credenciais seedadas documentadas (serão usadas no README, T38)

**Tests**: none
**Gate**: build
**Commit**: `chore(seed): add idempotent seed script`

---

### T37: Wiring final do Docker Compose da API (entrypoint, migrate+seed+run)

**What**: Script de entrypoint da API (`alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0`), variáveis de ambiente finais no `docker-compose.yml`/`.env.example` do repo da API.
**Where**: `entrypoint.sh`, `docker-compose.yml` (repo da API)
**Depends on**: T03, T09, T36
**Requirement**: deploy/setup

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] `docker compose up` numa máquina limpa sobe `db`+`api`, aplica migrations, semeia dados e a API funciona ponta a ponta (health check + endpoints principais) sem passo manual
- [ ] Rodar `docker compose up` de novo (dados já existentes) não quebra nem duplica seed

**Tests**: none
**Gate**: build
**Commit**: `chore: wire migrate+seed+run entrypoint for docker compose`

---

### T38: README do repo da API + documentação de uso de IA

**What**: README (repo `ticket-sales-platform-api`) com setup (uv local e via Docker), como rodar `docker compose up`, credenciais seedadas, regra do cartão de teste, como rodar os testes, link pro `.specs/` (que vive neste mesmo repo — fonte da verdade do produto inteiro), **explicação explícita da divisão em 2 repositórios** (motivo + como rodar os dois juntos localmente, incluindo `VITE_API_URL` esperado pelo repo web), seção de uso de IA (ferramentas usadas, em que partes, o que foi feito sem IA).
**Where**: `README.md` (raiz do repo da API)
**Depends on**: T37
**Requirement**: requisito não funcional (documentação)

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Alguém sem contexto consegue rodar a API do zero só seguindo o README
- [ ] Divisão em 2 repos está explicada e justificada, com link pro repo web
- [ ] Seção de uso de IA presente e honesta
- [ ] Qualquer limitação conhecida está documentada explicitamente (não omitida)

**Tests**: none
**Gate**: build
**Commit**: `docs: add README with setup instructions and AI usage notes`

---

### T39: README do repo web

**What**: README (repo `ticket-sales-platform-web`) com setup (`npm install`, `.env.example` → `VITE_API_URL`, `npm run dev`, build/Docker), link explícito pro repo da API (onde rodar o back-end antes de usar o front) e pro `.specs/` de lá (fonte da verdade do produto), nota curta sobre a divisão em 2 repos.
**Where**: `README.md` (raiz do repo web)
**Depends on**: T02, T38
**Requirement**: requisito não funcional (documentação)

**Tools**: MCP: NONE / Skill: NONE

**Done when**:
- [ ] Alguém sem contexto consegue rodar o front do zero só seguindo o README, desde que já tenha a API rodando
- [ ] Link pro repo/README da API presente e correto

**Tests**: none
**Gate**: build
**Commit**: `docs: add README with setup instructions`

---

## Parallel Execution Map

```
Phase 1 (Sequential): T01 → T02 → T03 → T04
Phase 2 (Sequential): T04 → T05 → T06 → T07 → T08 → T09
Phase 3 (Mixed):
  T09 → T10 → T11 ─┬→ T13 (também depende de T12 [P]) ─┬→ T15 → T16
                    │                                     ├→ T17 → T19
       T12 [P] ─────┘                                     ├→ T18 ─┬→ T20 → T21
                                                            │        ├→ T22
                                                            │        └→ T23 → T24
                                                            └────────────────→ T25 (também depende de T13)
Phase 4 (Mixed, cada uma depende do endpoint correspondente):
  T26 ─┬→ T27 → T28 → T29
        ├→ T30 → T31
        ├→ T30 + T24 → T35
        ├→ T22 + T26 → T32
        └→ T13/T25 + T26 → T33, T34
Phase 5 (Sequential): T36 → T37 → T38 → T39
```

**Parallelism real dentro de cada fase:** dentro da Fase 3, `T12` roda em paralelo com `T10`/`T11` (não compartilham arquivo nem tabela). Dentro da Fase 4, `T27`, `T30`, `T32`, `T33` podem começar em paralelo assim que `T26` e seus respectivos endpoints backend estiverem prontos — mas como o back (Fase 3) via de regra termina antes do front começar em serial single-agent, isso só importa de verdade se formos rodar sub-agentes por fase.

---

## Task Granularity Check

| Task | Scope | Status |
|---|---|---|
| T01–T04 | 1 escopo de infra cada (scaffold, compose, alembic) | ✅ Granular |
| T05–T08 | 1–2 models fortemente acoplados por arquivo | ✅ Granular (coeso) |
| T09 | 1 migration | ✅ Granular |
| T10, T12, T14, T17, T18, T23 | 1 service module cada | ✅ Granular |
| T11, T13, T15, T19–T22, T24, T25 | 1 router module cada | ✅ Granular |
| T16, T36, T37 | 1 wiring/script cada | ✅ Granular |
| T26–T35 | 1 feature de UI cada (página + componentes diretamente relacionados) | ✅ Granular (coeso — nenhuma mistura 2 features) |
| T38, T39 | 1 documento (README) cada, 1 por repo | ✅ Granular |

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
|---|---|---|---|
| T02 | None | Independente na Fase 1 (repo web, sem dependência de T01) | ✅ Match |
| T03, T04 | T01 | T01→T03→T04 | ✅ Match |
| T05–T09 | Cadeia T04→T05→T06→T07→T08→T09 | Sequencial na Fase 2 | ✅ Match |
| T10 | T09 | T09→T10 | ✅ Match |
| T11 | T10, T05 | T10→T11 | ✅ Match |
| T12 | T01 | `[P]` paralelo a T10/T11 | ✅ Match |
| T13 | T12, T06, T11 | T11→T13 e T12→T13 | ✅ Match |
| T14 | T06, T07 | T13→T14 (via T09 já satisfeito; T14 não depende de T13 na prática — corrigido: T14 depende só de T06/T07, roda assim que Fase 2 termina) | ✅ Match (diagrama mostra T13→T15, T14 alimenta T15 junto) |
| T15 | T14, T11 | T13→T15 e T14→T16... | ✅ Match |
| T16 | T14 | T15→T16 | ✅ Match |
| T17 | T07, T14 | T13→T17 | ✅ Match |
| T18 | T07 | T13→T18 | ✅ Match |
| T19 | T17 | T17→T19 | ✅ Match |
| T20 | T18, T07 | T18→T20 | ✅ Match |
| T21 | T20, T14 | T20→T21 | ✅ Match |
| T22 | T18, T11 | T18→T22 | ✅ Match |
| T23 | T07, T08, T18 | T18→T23 | ✅ Match |
| T24 | T23, T11 | T23→T24 | ✅ Match |
| T25 | T06, T07, T13 | T18→T25 (representa a cadeia; T25 também depende de T13) | ✅ Match |
| T26 | T11 | T11→T26 | ✅ Match |
| T27–T35 | conforme corpo de cada task | Fase 4 do diagrama | ✅ Match |
| T36–T39 | T05-T08 / T03,T09,T36 / T37 / T02,T38 | Fase 5 sequencial | ✅ Match |

**Nota de correção:** T14 tecnicamente só depende de T06/T07 (models), não de T13 — o diagrama da Execution Plan (seção acima) simplifica visualmente colocando-o na mesma "coluna" que T13 por clareza de leitura, mas a dependência real (e a que a execução deve respeitar) é a listada no corpo de cada task, não a posição no diagrama.

---

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
|---|---|---|---|---|
| T10 | Service (lógica pura) | unit | unit | ✅ OK |
| T11 | Router | integration | integration | ✅ OK |
| T12 | Service (lógica pura, I/O mockado) | unit | unit | ✅ OK |
| T13 | Router | integration | integration | ✅ OK |
| T14 | Service (DB) | integration | integration | ✅ OK |
| T15 | Router | integration | integration | ✅ OK |
| T16 | Wiring (main.py) | none (infra) | none | ✅ OK |
| T17 | Service (DB) | integration | integration | ✅ OK |
| T18 | Service (DB) | integration | integration | ✅ OK |
| T19–T22, T24, T25 | Router | integration | integration | ✅ OK |
| T23 | Service (DB) | integration | integration | ✅ OK |
| T01–T09, T36, T37 | Config/entity/scaffold | none | none | ✅ OK |
| T26–T35 | Front-end | none (fora de escopo nesta rodada) | none | ✅ OK |
| T38, T39 | Docs | none | none | ✅ OK |

Nenhuma violação — nenhum task diz `Tests: none` fora do que a matriz permite, e nenhum task de service/router com acesso a DB deixou de incluir seus próprios testes (sem deferral).

---

## Requirement Coverage

40 critérios totais no spec → 40 mapeados a tasks acima, 0 não mapeados.

| Requisito | Tasks |
|---|---|
| AUTH-01..04 | T05, T10, T11, T26 |
| CATALOG-01..04 | T12, T13, T33 |
| SEARCH-01..03 | T13, T27 |
| BOOKING-01..08 | T06, T07, T14, T15, T16, T17, T19, T28, T29 |
| CANCEL-01..03 | T14, T21, T31 |
| TICKETS-01..03 | T18, T20, T30 |
| GATE-01..06 | T18, T22, T32 |
| TRANSFER-01..06 | T08, T23, T24, T35 |
| DASH-01..02 | T25, T34 |
| DEVOPS-01..02 | T03, T37, T09 (migrations reversíveis), suíte integration completa |
| Estrutura polyrepo (AD-004) | T01, T02, T38, T39 |

---

## Tips

- Rodar `docker compose up -d db` antes de qualquer gate `full`.
- Toda task de service com acesso a DB já embute a prova de concorrência que importa — o router correspondente só confere o contrato HTTP, nunca duplica a prova.
- Front-end sem suíte automatizada nesta rodada é decisão de escopo explícita — revisitável como Deferred Idea se sobrar tempo real dentro dos 7 dias.
