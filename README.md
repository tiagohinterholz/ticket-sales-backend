# ticket-sales-platform-api

Back-end da Plataforma de Eventos e Ingressos (Desafio Elite Dev — Verzel). Organizador publica sessões de filme (catálogo TMDb) com mapa de assentos; cliente reserva, paga (simulado) e recebe um ingresso com QR assinado; a portaria valida na entrada.

Este repositório é o **sistema de registro** do produto: além do código, carrega o `.specs/` completo (spec, design, tasks, decisões) — é a fonte da verdade do projeto inteiro, não só do back-end.

O front-end vive num repositório separado: **[ticket-sales-platform-web](../frontend)** (ver "Por que dois repositórios" abaixo).

## Stack

- **Python 3.12 + FastAPI**, gerenciado com [`uv`](https://docs.astral.sh/uv/)
- **PostgreSQL 16** + SQLAlchemy 2.0 + Alembic
- **Docker / Docker Compose** (Dockerfile multi-stage)
- Autenticação JWT (`PyJWT`), hash de senha (`bcrypt`)
- Integração com [TMDb](https://www.themoviedb.org/) (catálogo de filmes)
- `pytest` (133 testes: unit + integration contra Postgres real)

## Como rodar (Docker — recomendado)

1. Copie o arquivo de exemplo e preencha os segredos:

   ```bash
   cp .env.example .env
   ```

   No `.env`, gere valores reais para `JWT_SECRET` e `QR_SECRET_KEY`:

   ```bash
   openssl rand -hex 32
   ```

   E preencha `TMDB_API_KEY` com o seu **TMDb v4 Read Access Token** (não é a "API Key" v3 curta — é o token longo, em [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api), seção "API Read Access Token"). Sem uma chave válida, a criação de eventos falha com 502 (mas o resto da aplicação — navegar eventos já seedados, comprar, validar na portaria — funciona normalmente, já que só depende da TMDb no momento de *criar* um evento).

2. Suba tudo:

   ```bash
   docker compose up --build
   ```

   Isso sobe o Postgres, aplica as migrations, semeia os dados de teste (idempotente — rodar de novo não duplica nada) e inicia a API em `http://localhost:8000`. Docs interativas em `http://localhost:8000/docs`.

   O Postgres fica exposto no host na porta **5433** (não 5432, para não conflitar com um Postgres local já rodando); a porta interna do container continua 5432.

## Como rodar (local, sem Docker para a API)

Requer [`uv`](https://docs.astral.sh/uv/getting-started/installation/) instalado.

```bash
docker compose up -d db        # só o Postgres
uv sync
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --reload
```

## Dados de teste (seed)

O seed cria 2 organizadores, 4 clientes, 2 operadores de portaria e 4 eventos publicados (filmes reais via TMDb, com pôster real) com assentos em todos os estados (livre, em hold, vendido) para permitir testar o fluxo inteiro sem montar nada manualmente.

| Papel | E-mail | Senha |
|---|---|---|
| Organizador | `organizador1@ticketsales.dev` | `organizador123` |
| Organizador | `organizador2@ticketsales.dev` | `organizador123` |
| Cliente | `cliente1@ticketsales.dev` | `cliente123` |
| Cliente | `cliente2@ticketsales.dev` | `cliente123` |
| Cliente | `cliente3@ticketsales.dev` | `cliente123` |
| Cliente | `cliente4@ticketsales.dev` | `cliente123` |
| Portaria | `portaria1@ticketsales.dev` | `portaria123` |
| Portaria | `portaria2@ticketsales.dev` | `portaria123` |

O log do `docker compose up` (ou de `python -m app.seed`) imprime também o `event_id` e o **token de QR já assinado** de um ingresso `PAID` de demonstração — cole esse token direto no campo de digitação manual da tela de portaria pra testar uma validação sem precisar passar pelo fluxo de compra primeiro.

Cartão de teste: qualquer número terminado em **`0000`** é recusado; qualquer outro final é aprovado.

## Testes

```bash
uv run pytest tests/unit -q              # rápido, sem Postgres
docker compose up -d db
uv run pytest -q                          # suíte completa (133 testes)
uv run ruff check .                       # lint
```

A suíte prova, contra Postgres real com threads concorrentes de verdade (não mock): que o mesmo assento não é vendido duas vezes (`tests/integration/test_booking_concurrency.py`) e que o mesmo ingresso não é validado duas vezes na portaria (`tests/integration/test_ticketing.py`).

## Papéis e autenticação

Três papéis: `CUSTOMER` (reserva, paga, recebe ingresso), `ORGANIZER` (cria/gerencia eventos), `GATE_STAFF` (valida ingressos). Só `CUSTOMER` tem cadastro público (`POST /auth/register`); `ORGANIZER` e `GATE_STAFF` só existem via seed — reflete controle de acesso real (a plataforma concede esses papéis, não é auto-serviço).

## Documentação do processo (`.specs/`)

Este repositório versiona o processo inteiro de planejamento, não só o código final:

- [`.specs/features/ticket-platform/spec.md`](.specs/features/ticket-platform/spec.md) — requisitos, histórias de usuário priorizadas (P1/P2/P3), 40 critérios de aceitação rastreáveis
- [`.specs/features/ticket-platform/context.md`](.specs/features/ticket-platform/context.md) — decisões de produto discutidas com o usuário (ex.: por que a transferência de ingresso é um handshake autenticado, não um link público)
- [`.specs/features/ticket-platform/design.md`](.specs/features/ticket-platform/design.md) — arquitetura, alternativas avaliadas e descartadas, modelo de dados, mecanismo de QR
- [`.specs/features/ticket-platform/tasks.md`](.specs/features/ticket-platform/tasks.md) — as 39 tarefas atômicas em que a implementação foi quebrada
- [`.specs/STATE.md`](.specs/STATE.md) — log de decisões de projeto (AD-001 a AD-009+), incluindo trade-offs

## Por que dois repositórios (não um monorepo)

O desafio pede "um repositório público" (singular). Optei, junto com o usuário, por dividir back-end e front-end em dois repositórios GitHub independentes — cada um clona, sobe e roda sozinho. Motivo e trade-off completo em `AD-004` (`.specs/STATE.md`): principal ganho é cada repo ser autocontido (o back-end sobe com um `docker compose up`, sem depender de nada do front); o custo é que não existe um único `docker compose up` que suba os dois juntos — é preciso subir a API (aqui) e depois o front (`ticket-sales-platform-web`, apontando `VITE_API_URL` para `http://localhost:8000`).

## Limitações conhecidas

- **Chave da TMDb**: sem uma chave v4 válida no `.env`, `POST /events` falha com 502 ao tentar criar um evento novo — o resto da aplicação (navegar, comprar, validar) funciona normalmente com os eventos já seedados.
- **Sem endpoint de criação de `ORGANIZER`/`GATE_STAFF`**: por design (ver "Papéis e autenticação" acima) — só via seed.
- **`GATE_STAFF` é global**: não existe vínculo entre um operador de portaria e um evento/organizador específico — qualquer conta de portaria valida ingressos de qualquer evento. Não há modelo de dados para restringir isso; ficou fora do escopo do desafio.
- **Sem edição/cancelamento de evento**: não existe `PATCH`/`DELETE` em `/events` — o organizador não consegue editar ou cancelar um evento já publicado, mesmo sem ingressos vendidos. Não era um requisito obrigatório do desafio, mas fica registrado aqui.
- **CORS aberto** (`allow_origins=["*"]`) — aceitável para o escopo do desafio (auth via Bearer token, não cookie, então CSRF clássico não se aplica); em produção real restringiria à origem do front deployado.
- **`cancel_ticket`** usa leitura-depois-escrita em vez de um `UPDATE ... WHERE` atômico (diferente de `hold_seat`/`ticketing.validate`, que são atômicos por serem os invariantes centrais do desafio) — uma corrida teórica de cancelamento duplo existe, mas não é concretamente explorável dado que pagamento é simulado e o estado final é idempotente.
- **Deploy não realizado nesta rodada** — projeto está estruturado para deploy simples (Vercel para o front, Render/Railway para API+Postgres), mas não foi publicado dentro do prazo do desafio.

## Uso de IA

Ocódigo deste repositório teve auxxlio (e do `ticket-sales-platform-web`) do **Claude Code** (Anthropic), usando a skill `tlc-spec-driven` para conduzir o fluxo Specify → Design → Tasks → Execute.

O que isso significou na prática:

- **Specify**: a partir do PDF do desafio, uma conversa guiada levantou os requisitos reais — inclusive perguntas que o PDF deixa deliberadamente em aberto (regra do cartão de teste, layout do mapa de assentos, mecanismo de hold). Resultou em `spec.md` com histórias priorizadas e 40 critérios de aceitação rastreáveis.
- **Design**: três abordagens de arquitetura foram avaliadas e comparadas antes de escolher (monólito modular vs. hexagonal completo vs. microsserviços) — a escolha e o porquê de descartar as outras duas estão documentados em `design.md`.
- **Tasks**: quebra em 39 tarefas atômicas, cada uma com critério de teste derivado do spec (não da implementação), validado antes de cada commit.
- **Execute**: implementação em lotes, cada um verificado (lint + testes + revisão de adequação dos testes) antes do commit atômico correspondente.
- **Validate**: ao final, um Verifier independente (sub-agente sem contexto de quem implementou) revalidou os 40 critérios de aceitação do zero contra o código real, rodou a suíte completa e injetou falhas propositais nos pontos mais críticos (lock de assento, validação de QR, checagem de evento errado, regra do cartão, checagem de dono do ingresso) pra provar que os testes realmente pegam regressão, não só existem do lado do código. Resultado: achou 2 gaps reais (portaria não mostrava quando um ingresso já usado foi validado; organizador não escolhia o filme entre os resultados da busca, só confiava no primeiro) — ambos corrigidos e revalidados antes deste commit. Relatório completo em `.specs/features/ticket-platform/validation.md`.

**Decisões que vieram de mim (Tiago), não da ferramenta**, e que mudaram o rumo do projeto:

- Reformulei o requisito de "compartilhar ingresso via link" do PDF: recusei a leitura literal ("link público mostra o QR") por ser um furo de segurança óbvio (QR público = qualquer um entra no evento) e pedi um handshake de titularidade autenticado no lugar — é o que está implementado (`POST /tickets/{id}/transfers` → convite → aceite/recusa).
- Decidi dividir o projeto em dois repositórios GitHub (back-end/front-end) em vez do monorepo que a ferramenta vinha montando, mesmo isso divergindo da leitura literal do PDF — documentado e justificado em `AD-004`.
- Ao revisar o código gerado diretamente (não só rodando a aplicação), encontrei e mandei corrigir: duplicação de helpers de teste entre 4 arquivos do back-end (virou `tests/integration/factories.py`, `AD-007`) e o mesmo padrão de duplicação em hooks de `useQuery`/`useMutation` no front (`AD-009`); um bug real onde o QR do ingresso rotacionava (invalidando o QR anterior) toda vez que o cliente só *visualizava* o ingresso, em vez de só na emissão.
- Testei a aplicação rodando de verdade (não só os testes automatizados): peguei minha própria chave da TMDb, descobri que era do tipo v4 (Bearer token) enquanto o código esperava v3 (`api_key` na query string), e mandei corrigir — sem isso, a criação de eventos com filme real nunca teria funcionado fora dos testes com mock.
- Ajustei o volume de dados do seed (de 1 organizador/2 clientes/1 portaria/1 evento para 2/4/2/4) depois de ver o resultado rodando.
- Revisei prints reais da tela de listagem de eventos e identifiquei que os cartazes não apareciam — rastreei até dados de teste residuais no banco (criados por sessões anteriores de QA com URLs de imagem falsas) e limpei antes do seed definitivo rodar.

**O que a IA fez**: auxilio na implementacao de código (models, services, routers, migrations, testes, componentes de front-end, hooks), e toda a documentação de processo em `.specs/`, e o histórico de commits granular que reflete cada tarefa.

Não houve fluxo BMAD nem PRD separado — o próprio `.specs/` (`spec.md` → `design.md` → `tasks.md` → `STATE.md`) cumpriu esse papel e está versionado neste repositório.
