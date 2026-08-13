# STATE

## Decisions

### AD-001
- **Decision**: Back-end Python gerenciado com `uv` (Astral), não pip/poetry/pipenv.
- **Reason**: Resolução e instalação de dependências muito mais rápidas, lockfile determinístico (`uv.lock`), um único binário sem precisar de venv manual — reduz fricção de setup pra quem for avaliar o projeto.
- **Trade-off**: Ferramenta mais nova, menos onipresente que pip; exige `uv` instalado localmente para desenvolvimento fora do Docker (mas dentro do Docker é transparente).
- **Scope**: Todo o back-end (FastAPI) — Dockerfile, CI, scripts de dev, README.
- **Date**: 2026-08-12
- **Status**: active

### AD-002
- **Decision**: Dockerfile do back-end é multi-stage (build stage instala deps via `uv` + gera artefatos; runtime stage copia só o necessário, sem toolchain de build).
- **Reason**: Imagem final menor e mais rápida de subir/buildar em CI/deploy; separa claramente "o que precisa pra instalar" de "o que precisa pra rodar".
- **Trade-off**: Dockerfile um pouco mais longo/complexo que single-stage; exige atenção para copiar corretamente os artefatos entre estágios.
- **Scope**: Back-end (obrigatório); front-end também deve seguir multi-stage (build Vite → estágio estático leve) por consistência, quando o Design da infra for formalizado.
- **Date**: 2026-08-12
- **Status**: active

### AD-003
- **Decision**: Todo model SQLAlchemy herda `UUIDPKMixin` + `TimestampMixin` (`id`, `created_at`, `updated_at`) em vez de redeclarar esses campos; todo schema Pydantic de resposta herda `BaseReadSchema` pelo mesmo motivo. Timestamps que são **estado de domínio** (ex.: `Ticket.paid_at`, `Ticket.used_at`) ficam explícitos na classe — não entram no mixin genérico.
- **Reason**: Elimina repetição real (todo model precisa dos 3 campos); herança só é aplicada onde há duplicação concreta detectada, nunca especulativamente (ver `design.md` → "Onde a herança NÃO é aplicada").
- **Trade-off**: Mais um arquivo (`app/models/mixins.py`, `app/schemas/base.py`) e uma camada de indireção a menos óbvia pra quem não conhece o padrão MRO de mixins do SQLAlchemy — mitigado por comentário no próprio arquivo.
- **Scope**: Todo model e todo schema de resposta do back-end, em qualquer feature futura. Novas classes que precisem de bookkeeping padrão devem herdar os mixins, não redeclarar campos.
- **Date**: 2026-08-12
- **Status**: active

### AD-004
- **Decision**: Back-end e front-end vivem em **dois repositórios GitHub separados** (`ticket-sales-platform-api`, `ticket-sales-platform-web`), não um monorepo. `.specs/` (spec, design, tasks, context, este arquivo) vive dentro do repo da API — é o "sistema de registro" do produto. `docker-compose.yml` também vive só no repo da API e sobe `db`+`api` sozinho (autocontido); o front-end é um app Vite independente, com seu próprio `Dockerfile`, configurado via `VITE_API_URL` pra apontar pro back-end (local ou deployado).
- **Reason**: Escolha explícita do usuário. Diverge da leitura literal do PDF ("um repositório público") — motivo e trade-off precisam ficar documentados nos READMEs de ambos os repos, não escondidos.
- **Trade-off**: Nenhum `docker compose up` único sobe os 3 serviços de uma vez (perdemos essa conveniência de monorepo); avaliador precisa clonar os 2 repos e rodar cada um (API via `docker compose up`, front via `npm run dev`/`docker build` apontando `VITE_API_URL` pra API). Documentar isso com clareza extra no README de cada repo é obrigatório pra não pesar na avaliação.
- **Scope**: Estrutura de todo o projeto — nomes de repositório, localização do `.specs/`, composição do Docker Compose, estrutura de pastas (ver `design.md`).
- **Date**: 2026-08-12
- **Status**: active

### AD-005
- **Decision**: Todo enum de código (valores de `Role`, `Seat.status`, `GateResult`, etc.) usa identificadores em **inglês**, mesmo quando o domínio/prosa do produto é em português. `Role`: `CUSTOMER`/`ORGANIZER`/`GATE_STAFF` (não `CLIENTE`/`ORGANIZADOR`/`PORTARIA`). `Seat.status`: `AVAILABLE`/`HOLD`/`SOLD` (não `LIVRE`/`HOLD`/`VENDIDO`). `GateResult`: `VALID`/`INVALID`/`ALREADY_USED`/`WRONG_EVENT` (não `VALIDO`/`INVALIDO`/`JA_UTILIZADO`/`EVENTO_ERRADO`). `Ticket.status`, `PaymentAttempt.result`, `TransferInvite.status` já estavam em inglês desde o design original — ficam como estavam.
- **Reason**: Pedido explícito do usuário ao ver `Role` em português no código; aplicado por consistência a todos os outros enums do domínio para não deixar a base de código misturando os dois idiomas.
- **Trade-off**: Nenhum — é puro alinhamento de nomenclatura, já propagado em `spec.md`/`design.md`/`tasks.md` (busca+substituição) antes de qualquer código additional ser escrito sobre esses enums. Nomes de papéis em prosa (Organizador/Cliente/Portaria) continuam em português — só os identificadores de código mudam.
- **Scope**: Todo enum do back-end, em qualquer feature futura.
- **Date**: 2026-08-12
- **Status**: active

### AD-006
- **Decision**: Nenhum comentário de código (`#` inline, docstrings, banners de módulo) em nenhum arquivo do projeto — nem nos gerados por scaffolding de terceiros (ex.: templates do `npm create vite`, docstrings padrão do Alembic). Código deve se explicar por nomes claros; qualquer contexto que valeria um comentário vai pra mensagem do commit ou pra `.specs/` (design.md, este arquivo), nunca inline.
- **Reason**: Pedido explícito e enfático do usuário, repetido duas vezes.
- **Trade-off**: Racionais não-óbvios (ex.: por que a migration reordena tabelas manualmente, por que o downgrade dropa ENUMs explicitamente, por que o schema de teste não é dropado) ficam só na mensagem do commit correspondente ou em `design.md`/`STATE.md` — não no arquivo em si. Quem for ler só o código sem olhar o histórico/specs perde esse contexto; aceitável dado o pedido explícito.
- **Scope**: Todo o back-end e front-end, em qualquer feature futura.
- **Date**: 2026-08-13
- **Status**: active

### AD-007
- **Decision**: Testes de integração usam as factories compartilhadas em `tests/integration/factories.py` (`make_user`, `auth_headers`, `make_event`, `make_seat`, `make_ticket`) — nunca redeclarar `_make_user`/`_make_event`/`_make_seat`/`_make_ticket` locais em cada arquivo de teste.
- **Reason**: 4 arquivos de teste (T14, T15, T17, T19) tinham chegado com cópias quase idênticas desses helpers — apontado pelo usuário, consolidado numa única fábrica.
- **Trade-off**: `make_ticket` tem `expires_at` default `None` (não `now+5min`) — quem precisa de um ticket `HELD` com hold ainda válido deve passar `expires_at=datetime.now(UTC) + timedelta(minutes=5)` explicitamente. `make_seat` tem `status` default `AVAILABLE` — cenários que precisam de assento `HOLD`/`SOLD` passam explicitamente.
- **Scope**: Todo teste de integração futuro (T18, T20-T25, T36+) — antes de escrever um helper de setup, checar se já existe em `factories.py`; se precisar de um novo (ex.: `make_transfer_invite`), adicionar lá, não localmente.
- **Date**: 2026-08-13
- **Status**: active

### AD-008
- **Decision**: `CORSMiddleware` adicionado em `app/main.py` (`allow_origins=["*"]`) para permitir que o repo web (`ticket-sales-platform-web`, origem diferente em dev — `localhost:5173` vs API em `localhost:8000`) consiga chamar a API pelo navegador.
- **Reason**: Descoberto durante T26 (front-end) — sem isso, o preflight `OPTIONS` do browser falha antes de qualquer request chegar no servidor; nenhuma tela do front consegue falar com a API. Bloqueava literalmente o "Done when" de T26 (testar login/registro no navegador).
- **Trade-off**: `allow_origins=["*"]` é permissivo (qualquer origem pode chamar a API). Aceitável para o escopo do desafio (sem cookies de sessão — auth é via `Authorization: Bearer`, não cookie, então CSRF não se aplica da forma clássica); se fosse produção real, restringiria a origens conhecidas (domínio da Vercel do deploy, `localhost` em dev).
- **Scope**: `app/main.py`, repo da API — vale pra todo front-end que for consumir essa API.
- **Date**: 2026-08-13
- **Status**: active

### AD-009
- **Decision**: No repo web, toda chamada `useQuery`/`useMutation` do React Query vive em um hook dedicado sob `src/api/hooks/` (`useEvents`, `useEvent`, `useHoldSeat`, `useTicket`, `usePayTicket`, ...) — nunca inline dentro de um componente de página/feature. Efeitos colaterais genéricos de cache (invalidação de query relacionada) ficam no hook; efeitos específicos da tela (navegação, mensagem de erro local) são passados como callback no site de chamada (`.mutate(vars, {onSuccess, onError})`), já que React Query dispara tanto o callback do hook quanto o da chamada.
- **Reason**: `CheckoutPage` e `TicketPlaceholderPage` chegaram com o mesmo `useQuery(["ticket", id], () => getTicket(id))` copiado quase literalmente — mesmo padrão de duplicação já visto (e corrigido) nos testes do backend (AD-007). Apontado pelo usuário.
- **Trade-off**: Mais um nível de indireção (hook fino em vez de chamada direta) — aceitável, é o mesmo trade-off já aceito do lado do backend.
- **Scope**: Todo componente de página/feature do repo web, em qualquer task futura (T30+). Antes de escrever um novo `useQuery`/`useMutation`, checar se já existe um hook equivalente em `src/api/hooks/`; se não, criar lá, não inline.
- **Date**: 2026-08-13
- **Status**: active

## Handoff

- **Feature**: ticket-platform (`.specs/features/ticket-platform/`, vive no repo `ticket-sales-platform-api` — ver AD-004)
- **Phase / Task**: Tasks aprovadas (T01–T39, 5 fases, execução via 1 sub-agente por fase — usuário confirmou). Dois repos git já inicializados e com primeiro commit. Próximo: disparar o worker da Fase 1 (T01 scaffold+git da API já parcialmente feito manualmente — falta o conteúdo real de T01/T02: pyproject/uv, FastAPI mínimo, Vite scaffold, Dockerfiles).
- **Completed**: spec.md, context.md, design.md, tasks.md; `git init` dos 2 repos (`backend/` = `ticket-sales-platform-api`, `frontend/` = `ticket-sales-platform-web`); primeiro commit em cada um (`.specs/`+`.gitignore` na API, `.gitignore` no web)
- **In-progress**: nenhum arquivo em edição
- **Next step**: disparar sub-agente da Fase 1 (T01: scaffold FastAPI/uv/Dockerfile no repo API; T02: scaffold Vite/React/Router/React Query/Dockerfile no repo web; T03/T04 na sequência)
- **Blockers**: none
- **Uncommitted files**: none (working tree limpa em ambos os repos após o commit inicial)
- **Branch**: `main` em ambos os repos
