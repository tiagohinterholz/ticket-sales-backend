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

## Handoff

- **Feature**: ticket-platform (`.specs/features/ticket-platform/`, vive no repo `ticket-sales-platform-api` — ver AD-004)
- **Phase / Task**: Tasks aprovadas (T01–T39, 5 fases, execução via 1 sub-agente por fase — usuário confirmou). Dois repos git já inicializados e com primeiro commit. Próximo: disparar o worker da Fase 1 (T01 scaffold+git da API já parcialmente feito manualmente — falta o conteúdo real de T01/T02: pyproject/uv, FastAPI mínimo, Vite scaffold, Dockerfiles).
- **Completed**: spec.md, context.md, design.md, tasks.md; `git init` dos 2 repos (`backend/` = `ticket-sales-platform-api`, `frontend/` = `ticket-sales-platform-web`); primeiro commit em cada um (`.specs/`+`.gitignore` na API, `.gitignore` no web)
- **In-progress**: nenhum arquivo em edição
- **Next step**: disparar sub-agente da Fase 1 (T01: scaffold FastAPI/uv/Dockerfile no repo API; T02: scaffold Vite/React/Router/React Query/Dockerfile no repo web; T03/T04 na sequência)
- **Blockers**: none
- **Uncommitted files**: none (working tree limpa em ambos os repos após o commit inicial)
- **Branch**: `main` em ambos os repos
