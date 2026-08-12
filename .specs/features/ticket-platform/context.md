# Plataforma de Eventos e Ingressos — Context

**Gathered:** 2026-08-12
**Spec:** `.specs/features/ticket-platform/spec.md`
**Status:** Ready for design

---

## Feature Boundary

Sistema completo de eventos e ingressos: organizador publica sessões de filme (catálogo TMDb) com mapa de assentos; cliente navega, reserva, paga (simulado) e recebe ingresso com QR; portaria valida na entrada. Auth com 3 papéis. Opcionais escolhidos: busca/filtro, cancelamento com devolução ao estoque, painel do organizador, Docker Compose + testes.

---

## Implementation Decisions

### Stack

- Back-end: **Python + FastAPI**, gerenciado com **`uv`** (não pip/poetry) — ver AD-001 em `STATE.md`
- Front-end: **Vite + React Router** (SPA)
- Banco: **PostgreSQL**
- API externa: **TMDb** apenas (evento = sessão de filme; Ticketmaster fora de escopo)
- Containerização: **Dockerfiles multi-stage** (back-end e front-end) — ver AD-002 em `STATE.md`

### Modelo de venda

- **Mapa de assentos** (cinema/teatro) — não pista/quantidade. Único modelo suportado, para não duplicar UI/lógica de concorrência.
- Organizador define o mapa como grade retangular: linhas × cadeiras por linha. Capacidade é derivada do mapa, não um campo independente.

### Pagamento simulado

- Cartão de teste determinístico: número terminado em `0000` → **recusado**; qualquer outro final → **aprovado**. Documentar isso claramente no README (é o "manual de teste" de quem for avaliar).

### Provisionamento de contas

- Só **Cliente** tem self-signup público.
- **Organizador** e **Portaria** são só via seed — reflete controle de acesso real (a plataforma concede esses papéis, não é auto-serviço).

### Hold de assento (concorrência)

- Assento selecionado entra em **hold de 5 minutos** exclusivo para o cliente que selecionou.
- Hold expira automaticamente e libera o assento se o pagamento não for confirmado a tempo.
- Troca de status do assento é transação atômica no banco — garante que dois clientes não consigam o mesmo assento.

### Cancelamento (opcional escolhido)

- Cliente pode cancelar um ingresso `PAID` até **2 horas antes** do horário do evento.
- Depois disso, cancelamento é recusado com mensagem explicando a janela.
- Ingresso `USED` ou `TRANSFERRED` nunca pode ser cancelado.

### Painel do organizador (opcional escolhido)

- Lista de eventos do organizador com **% de ocupação** (vendidos / capacidade).
- Detalhe por evento: **mapa de assentos com status** (livre / hold / vendido / cancelado).
- Edição/cancelamento de evento existente: **não incluído nesta rodada** (não foi selecionado explicitamente) — fica em Deferred Ideas.

### Transferência de ingresso (resolve o requisito "compartilhar via link" do PDF)

Decisão importante, reformulada a partir do entendimento do usuário — **não é link público de visualização**, é handshake de titularidade:

1. Dono de um ingresso `PAID` inicia transferência → sistema gera link único de convite.
2. Link expira em **24h ou quando o dono cancelar manualmente** o convite pendente.
3. Destinatário **precisa ter conta de Cliente** na plataforma para aceitar.
   - Se abrir o link **sem estar logado**, é levado para login/cadastro e volta ao convite após autenticar.
   - Se a pessoa **ainda não tem conta nenhuma**, o sistema registra um **"e-mail fake" de convite** — simulado/logado em painel de dev, não envio real via provedor (ver Rationale abaixo) — convidando a se cadastrar.
4. Ao **aceitar**: transação atômica — ingresso original vira `TRANSFERRED` (some de "Meus ingressos" ativos do antigo dono, vira histórico), novo ingresso `PAID(valid)` com QR próprio é criado para o novo dono.
5. Ao **recusar**, expirar, ou o dono **cancelar antes do aceite**: ingresso original permanece `PAID` ativo com o dono original; link antigo fica inválido.
6. Só é possível transferir ingresso `PAID` (não `USED`, `CANCELLED` ou já `TRANSFERRED`).

**Rationale para não usar e-mail real:** o PDF lista explicitamente "envio de ingresso por e-mail" em "Não precisa fazer". Montar e-mail transacional real (provedor, domínio verificado, deliverability) é infra extra que compete com o tempo dos 4 opcionais já escolhidos + TMDb + mapa de assentos + 3 papéis de auth, dentro de 7 dias corridos. Também é risco de demo: se o e-mail não chegar durante a avaliação, a impressão é pior do que nunca ter tido a feature. A simulação (mesmo espírito do pagamento simulado) comunica a intenção do fluxo sem essa fragilidade.

**Segurança:** o link/QR nunca é exposto publicamente sem autenticação — só o dono autenticado ou o destinatário autenticado interagem com o convite. Isso evita o problema óbvio: QR público = qualquer um entra no evento.

### Deploy

- Front-end: **Vercel**.
- Back-end + banco: **Render ou Railway** (Vercel não roda bem processo long-running Python + Postgres persistente).
- Prioridade: rodar bem local via Docker Compose primeiro; deploy é o último passo se sobrar tempo dentro dos 7 dias.

### Escopo de opcionais (dado o prazo de 7 dias)

Escolhidos: busca/filtro de eventos, cancelamento com devolução ao estoque, painel do organizador, Docker Compose + testes básicos.
**Não escolhidos:** mapa de assentos em tempo real (websocket) — fica em Deferred Ideas.

---

## Agent's Discretion

- Mecanismo exato de assinatura do QR (HMAC vs JWT) — decisão técnica, formalizada em `design.md`.
- Comportamento exato de "organizador edita evento com ingressos já vendidos" (edição de evento não foi escolhida como opcional; se implementada minimamente, avisar sobre impacto antes de confirmar).
- Estrutura de logging (formato, onde persiste) — proporcional ao escopo, sem over-engineering.

---

## Declined / Undiscussed Gray Areas → Assumptions

Nenhuma foi declinada — todas as gray areas identificadas foram discutidas nas rodadas de perguntas. Os pontos que ficaram como assunção de menor impacto (não geraram pergunta dedicada) estão registrados na tabela **Assumptions & Open Questions** do `spec.md`:

- Regra exata do cartão de teste (`0000` recusa).
- Layout do mapa como grade retangular simples.
- Ausência de rate limiting em login.
- Nível de observabilidade (logging básico, sem métricas/tracing).
- Sem expurgo/TTL de dados históricos.

---

## Specific References

Nenhuma referência visual específica foi pedida (ex.: "quero como o site X"). Vamos usar ingresso.com (mapa de assentos) e sympla.com.br (criação de evento/checkout) como pontos de partida conceituais, conforme sugerido no PDF — sem copiar layout.

---

## Deferred Ideas

- **Mapa de assentos em tempo real** (múltiplos clientes veem o mapa atualizar ao vivo via WebSocket/polling) — não incluído no MVP; candidato de stretch se sobrar tempo real após o combo de opcionais já escolhido.
- **Edição de evento com ingressos vendidos** (fluxo dedicado de aviso/impacto) — não foi escolhido como opcional; se o painel do organizador ficar pronto com folga de tempo, pode virar um adicional pequeno.
- **E-mail transacional real** para convite de transferência — descartado por custo/risco vs. benefício no prazo de 7 dias; ver Rationale acima.
