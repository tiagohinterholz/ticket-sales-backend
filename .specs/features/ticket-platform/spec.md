# Plataforma de Eventos e Ingressos — Specification

Desafio Elite Dev (Verzel). Prazo: 7 dias corridos a partir de 2026-08-12 → entrega até **2026-08-19**.

## Problem Statement

Um organizador precisa publicar eventos (sessões de cinema, no nosso recorte) a partir de um catálogo externo, definindo sala, data, capacidade e preço. Um cliente precisa navegar por esses eventos, escolher assento num mapa, pagar (simulado) e receber um ingresso com QR verificável. Na entrada, a portaria precisa validar esse ingresso sem ambiguidade — e sem permitir reuso ou fraude.

## Goals

- [ ] Fluxo ponta a ponta funcionando: organizador publica → cliente reserva/paga → cliente recebe ingresso com QR → portaria valida.
- [ ] Nenhum assento pode ser vendido duas vezes, mesmo sob concorrência (dois clientes tentando o mesmo assento).
- [ ] Nenhum ingresso pode ser validado duas vezes na portaria, mesmo com o mesmo código reapresentado.
- [ ] QR code não pode ser forjado (assinatura server-side verificável).
- [ ] README permite a qualquer avaliador rodar o projeto localmente (Docker Compose) sem montar nada manualmente, com dados seedados.

## Out of Scope

| Feature | Reason |
|---|---|
| Nota fiscal | Excluído explicitamente pelo desafio |
| Revenda entre usuários (marketplace) | Excluído explicitamente pelo desafio |
| Aplicativo nativo | Excluído explicitamente pelo desafio |
| Recuperação de senha | Excluído explicitamente pelo desafio |
| Envio de ingresso por e-mail real | Excluído explicitamente pelo desafio; usamos e-mail "fake" logado (ver context.md) só para o convite de transferência a não-usuários |
| Ticketmaster Discovery (shows) | Escopo fechado em TMDb apenas — evento = sessão de filme. Reduz superfície de integração, mantém o modelo "sala + assentos" consistente ponta a ponta |
| Pista/quantidade (setor sem assento numerado) | Escopo fechado em mapa de assentos apenas — evita duplicar UI e lógica de concorrência para dois modelos de venda |
| Mapa de assentos em tempo real (websocket) | Fica como ideia para depois do MVP; ver Assumptions |
| Gateway de pagamento real (mesmo em sandbox) | Simulação própria com cartão de teste determinístico é suficiente e mais previsível para demo |
| Self-signup de Organizador/Portaria | Só Cliente se cadastra livremente; Organizador e Portaria são só seed, refletindo controle de acesso real da plataforma |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
|---|---|---|---|
| Regra do cartão de teste | Cartão terminado em `0000` → recusado; qualquer outro final → aprovado | Padrão previsível (estilo Stripe test cards), fácil de documentar no README e demonstrar os dois caminhos | y |
| Layout do mapa de assentos | Organizador define linhas × cadeiras por linha (grade retangular simples) ao criar o evento; capacidade = linhas × colunas | Sem essa regra, "capacidade" e "mapa de assentos" seriam dois campos desincronizados. Grade retangular é o padrão de cinema e é o suficiente para o desafio | n — assumido, não discutido |
| Mecanismo de assinatura do QR | Token assinado (HMAC-SHA256 ou JWT) contendo `ticket_id` + `event_id`, verificado server-side na validação; o QR nunca é a fonte de verdade sozinho — a portaria sempre confere o estado do ingresso no banco | Decisão técnica (Design), não gray area de produto — mas registrada aqui porque impacta o requisito "não pode ser forjado" | n — decisão técnica, será formalizada em design.md |
| Rate limiting / brute-force em login | Fora de escopo (N/A) | Desafio de prazo curto; não é foco de avaliação declarado no PDF | y (dimension sweep) |
| Observabilidade | Logging estruturado básico (console/arquivo) nas ações críticas: reserva, pagamento, validação de ingresso, transferência. Sem métricas/tracing dedicados | Proporcional ao escopo; evita over-engineering | y (dimension sweep) |
| Falha da API TMDb | Erro tratado com mensagem clara pro organizador na tela de criação de evento ("catálogo indisponível, tente novamente"); não derruba navegação de eventos já publicados, que não depende da TMDb em tempo real | TMDb só é chamada no momento de montar o evento; eventos publicados já têm os dados persistidos localmente | y (dimension sweep) |
| Deleção/retenção de dados | Sem TTL ou expurgo automático de eventos/reservas/ingressos passados — tudo é mantido como histórico | Fora do escopo do desafio; simplicidade | y (dimension sweep) |
| Mapa de assentos em tempo real (multi-usuário vendo o mesmo mapa atualizar ao vivo) | Não incluído no MVP; se sobrar tempo, é candidato de stretch goal via polling simples (não websocket) | Opcional listado no PDF como "considerado", não obrigatório; combo de opcionais já escolhido (busca, cancelamento, painel, Docker+testes) é ambicioso para 7 dias — priorizar profundidade sobre mais um opcional | y |

**Open questions:** nenhuma — todas resolvidas ou registradas acima.

---

## Implicit-Requirement Dimensions Sweep

| Dimensão | Cobertura |
|---|---|
| Input validation & bounds | Capacidade do evento = linhas×colunas (>0); preço ≥ 0; e-mail formato válido; senha mínimo 8 caracteres; seleção de assento não pode exceder mapa nem repetir assento já ocupado |
| Failure / partial-failure states | Falha na TMDb ao criar evento → erro claro, sem persistir evento incompleto. Falha ao confirmar pagamento → reserva expira normalmente pelo TTL, assento libera. Falha de transação no banco durante reserva → rollback completo, nenhum estado parcial (assento nunca fica "meio reservado") |
| Idempotency / retry / duplicate handling | Clique duplo em "confirmar pagamento" não gera dois ingressos — servidor idempotente por `reservation_id` (segunda chamada com reserva já paga retorna o ingresso existente, não cria outro) |
| Auth boundaries & rate limits | Guards por papel: Organizador só cria/edita/cancela os **próprios** eventos; Cliente só vê/cancela/transfere os **próprios** ingressos; Portaria só valida, não vê dados de pagamento. Rate limit: N/A (ver Assumptions) |
| Concurrency / ordering | Hold de assento por 5 min com expiração automática; troca de status do assento é transação atômica no banco (lock/constraint) — dois clientes competindo pelo mesmo assento: um ganha, outro recebe erro "assento já reservado" na hora |
| Data lifecycle / expiry | Hold de reserva expira em 5 min. Convite de transferência expira em 24h ou cancelamento manual do dono. Sem expurgo de dados históricos (ver Assumptions) |
| Observability | Ver Assumptions — logging estruturado nas ações críticas |
| External-dependency failure | Ver Assumptions — falha da TMDb tratada com mensagem clara, não derruba o resto da aplicação |
| State-transition integrity | Ingresso: `RESERVED(held)` → `PAID(valid)` → `USED` (na portaria) \| `CANCELLED` \| `EXPIRED` \| `TRANSFERRED` (vira histórico pro dono antigo, novo ingresso `PAID(valid)` pro novo dono). Transições inválidas são bloqueadas (ex.: não valida `CANCELLED`, não cancela `USED`, não paga `EXPIRED`) |

---

## User Stories

### P1: Organizador publica evento a partir do catálogo TMDb ⭐ MVP

**User Story**: Como organizador, quero montar um evento a partir de um filme do catálogo TMDb, definindo sala (mapa de assentos), data/hora, capacidade e preço, para publicá-lo aos clientes.

**Why P1**: Sem evento publicado não existe fluxo de compra — é a base de tudo.

**Acceptance Criteria**:
1. WHEN o organizador busca filmes por título na tela de criação de evento THEN o sistema SHALL consultar a API TMDb e exibir resultados com pôster, título e data de lançamento.
2. WHEN o organizador seleciona um filme e informa data/hora, local, linhas × cadeiras por linha e preço THEN o sistema SHALL criar o evento com status "publicado" e capacidade = linhas × colunas.
3. WHEN a API TMDb está indisponível ou retorna erro THEN o sistema SHALL exibir mensagem clara de falha e permitir nova tentativa, sem persistir evento incompleto.
4. WHEN o organizador tenta criar evento com data no passado, capacidade zero, ou preço negativo THEN o sistema SHALL rejeitar com mensagem de validação específica por campo.

**Independent Test**: Logar como organizador seed, criar um evento buscando um filme real na TMDb, e ver o evento aparecer na listagem pública.

---

### P1: Cliente navega, reserva assento e paga (simulado) ⭐ MVP

**User Story**: Como cliente, quero navegar pelos eventos publicados, escolher um assento no mapa e pagar de forma simulada, para garantir meu lugar.

**Why P1**: É o core transacional do produto.

**Acceptance Criteria**:
1. WHEN o cliente acessa a listagem de eventos THEN o sistema SHALL exibir todos os eventos publicados com data, local e preço.
2. WHEN o cliente abre um evento THEN o sistema SHALL exibir o mapa de assentos com status visual: livre, ocupado (pago), em hold (temporariamente indisponível).
3. WHEN o cliente seleciona um assento livre THEN o sistema SHALL colocá-lo em hold por 5 minutos, exclusivo para aquele cliente.
4. WHEN dois clientes tentam reservar o mesmo assento simultaneamente THEN o sistema SHALL garantir que apenas um consiga o hold; o outro recebe erro imediato "assento indisponível".
5. WHEN o hold expira sem pagamento confirmado THEN o sistema SHALL liberar o assento automaticamente para outros clientes.
6. WHEN o cliente confirma pagamento com um cartão de teste que não termina em `0000` THEN o sistema SHALL aprovar o pagamento, gerar o ingresso com QR assinado, e mudar o assento para "vendido".
7. WHEN o cliente confirma pagamento com um cartão de teste terminado em `0000` THEN o sistema SHALL recusar o pagamento, manter o hold ativo (dentro da janela restante) e permitir nova tentativa.
8. WHEN o hold expira durante a tela de pagamento THEN o sistema SHALL informar que o tempo esgotou e redirecionar o cliente para escolher assento novamente.

**Independent Test**: Logar como cliente seed, reservar um assento livre de um evento seedado, pagar com cartão aprovado, ver o ingresso gerado; repetir com cartão terminado em 0000 e ver a recusa.

---

### P1: Cliente vê "Meus ingressos" com QR ⭐ MVP

**User Story**: Como cliente, quero ver meus ingressos comprados com o código QR, para apresentar na entrada do evento.

**Why P1**: É a entrega final do fluxo de compra — sem isso o ingresso não existe pro cliente.

**Acceptance Criteria**:
1. WHEN o cliente acessa "Meus ingressos" THEN o sistema SHALL listar todos os ingressos com status `PAID`, `USED`, `CANCELLED`, `TRANSFERRED` (indicando claramente o estado de cada um).
2. WHEN o cliente abre um ingresso `PAID` THEN o sistema SHALL exibir o QR code gerado a partir do token assinado do ingresso.
3. WHEN o ingresso está `USED`, `CANCELLED` ou `TRANSFERRED` THEN o sistema SHALL exibir isso visualmente e não permitir apresentar o QR como válido.

**Independent Test**: Após compra bem-sucedida, abrir "Meus ingressos" e ver o QR renderizado.

---

### P1: Portaria valida ingresso ⭐ MVP

**User Story**: Como operador de portaria, quero validar o ingresso na entrada (via câmera ou código manual), para permitir ou barrar a entrada com uma resposta inequívoca.

**Why P1**: Fecha o ciclo completo do desafio — é o requisito mais citado no PDF ("não pode ser forjado", "não pode validar duas vezes").

**Acceptance Criteria**:
1. WHEN a portaria escaneia um QR válido de um ingresso `PAID` do evento correto THEN o sistema SHALL marcar o ingresso como `USED` e retornar "válido" com dados do assento/cliente.
2. WHEN a portaria escaneia um QR já usado THEN o sistema SHALL retornar "já utilizado" sem alterar o estado, mostrando quando foi validado.
3. WHEN a portaria escaneia um QR de outro evento (diferente do selecionado na tela de portaria) THEN o sistema SHALL retornar "evento errado".
4. WHEN a portaria escaneia um código inválido, corrompido ou com assinatura incorreta THEN o sistema SHALL retornar "inválido".
5. WHEN a câmera não está disponível ou falha THEN o sistema SHALL permitir digitação manual do código como alternativa equivalente.
6. WHEN dois operadores de portaria tentam validar o mesmo ingresso ao mesmo tempo THEN o sistema SHALL garantir que só a primeira validação seja aceita (transação atômica).

**Independent Test**: Validar um ingresso pago (deve dar "válido"), validar de novo o mesmo (deve dar "já utilizado"), digitar um código inventado (deve dar "inválido").

---

### P2: Autenticação com três papéis

**User Story**: Como sistema, preciso diferenciar Organizador, Cliente e Portaria, cada um só acessando o que lhe cabe.

**Why P2**: Tecnicamente é pré-requisito de tudo acima (por isso entra nas tasks desde o início), mas como "história" fica documentada à parte por atravessar todas as outras.

**Acceptance Criteria**:
1. WHEN uma pessoa se cadastra publicamente THEN o sistema SHALL criar uma conta com papel `CLIENTE` (único self-signup disponível).
2. WHEN um usuário `ORGANIZADOR` tenta acessar rotas de outro organizador ou de cliente/portaria THEN o sistema SHALL negar com 403.
3. WHEN um usuário `PORTARIA` tenta acessar dados de pagamento ou criar eventos THEN o sistema SHALL negar com 403.
4. WHEN o login falha (credenciais inválidas) THEN o sistema SHALL retornar erro genérico, sem indicar se o e-mail existe ou não.

**Independent Test**: Logar com cada um dos 3 usuários seed e confirmar que cada um só vê seu próprio menu/rotas.

---

### P2: Busca e filtro de eventos

**User Story**: Como cliente, quero filtrar eventos por data, local e faixa de preço, para achar o que me interessa mais rápido.

**Why P2**: Melhora UX real, baixo custo de implementação, alto valor percebido.

**Acceptance Criteria**:
1. WHEN o cliente digita um termo de busca THEN o sistema SHALL filtrar eventos por título do filme.
2. WHEN o cliente aplica filtro de data e/ou faixa de preço THEN o sistema SHALL retornar apenas eventos dentro dos critérios.
3. WHEN nenhum evento corresponde aos filtros THEN o sistema SHALL exibir um estado vazio claro (não uma lista vazia sem explicação).

**Independent Test**: Filtrar por um filme que não existe e ver o estado vazio; filtrar por um que existe e ver o resultado certo.

---

### P2: Cancelamento com devolução ao estoque

**User Story**: Como cliente, quero cancelar um ingresso que comprei, para liberar o assento se não vou mais usá-lo.

**Why P2**: Testa integridade de estado e concorrência; opcional escolhido explicitamente.

**Acceptance Criteria**:
1. WHEN o cliente cancela um ingresso `PAID` até 2 horas antes do horário do evento THEN o sistema SHALL mudar o ingresso para `CANCELLED` e liberar o assento de volta ao mapa como disponível.
2. WHEN o cliente tenta cancelar um ingresso a menos de 2 horas do evento THEN o sistema SHALL recusar com mensagem explicando a janela de cancelamento.
3. WHEN o cliente tenta cancelar um ingresso já `USED` ou `TRANSFERRED` THEN o sistema SHALL recusar — não é mais dele ou já foi consumido.

**Independent Test**: Cancelar um ingresso de evento futuro (>2h) e ver o assento voltar a "livre" no mapa; tentar cancelar um evento a <2h e ver a recusa.

---

### P2: Painel do organizador

**User Story**: Como organizador, quero ver meus eventos com ocupação e o mapa de assentos por evento, para acompanhar as vendas.

**Why P2**: Opcional escolhido; mostra capacidade full-stack sem ser crítico pro fluxo core.

**Acceptance Criteria**:
1. WHEN o organizador acessa o painel THEN o sistema SHALL listar seus eventos com percentual vendido (vendidos / capacidade).
2. WHEN o organizador abre o detalhe de um evento THEN o sistema SHALL exibir o mapa de assentos com status por assento (livre, hold, vendido, cancelado).

**Independent Test**: Logar como organizador seed, ver ao menos um evento com >0% de ocupação (via dados seedados) e o mapa refletindo isso.

---

### P2: Transferência de ingresso (compartilhamento) via link

**User Story**: Como cliente que não pode mais ir ao evento, quero transferir meu ingresso para outro cliente cadastrado via link, para que ele possa usar em meu lugar.

**Why P2**: É o requisito "compartilhar ingresso via link" do PDF, resolvido como handshake de titularidade (não visualização pública) por razão de segurança — ver context.md.

**Acceptance Criteria**:
1. WHEN o cliente dono de um ingresso `PAID` inicia uma transferência THEN o sistema SHALL gerar um link único de convite, válido por 24h ou até cancelamento manual.
2. WHEN o destinatário abre o link estando logado como Cliente THEN o sistema SHALL exibir os dados do ingresso e um botão de aceitar/recusar.
3. WHEN o destinatário abre o link sem estar logado ou sem conta THEN o sistema SHALL registrar um "e-mail fake" de convite (log/painel de dev) e direcionar para login/cadastro, retornando ao convite pendente após autenticar.
4. WHEN o destinatário aceita THEN o sistema SHALL, em transação atômica: marcar o ingresso original como `TRANSFERRED` (sai de "Meus ingressos" ativos do antigo dono), e criar/associar o ingresso `PAID(valid)` para o novo dono com QR próprio.
5. WHEN o destinatário recusa, ou o convite expira, ou o dono cancela antes do aceite THEN o sistema SHALL manter o ingresso original `PAID` e ativo com o dono original, invalidando o link usado.
6. WHEN o dono tenta transferir um ingresso `USED`, `CANCELLED` ou já `TRANSFERRED` THEN o sistema SHALL recusar a ação.

**Independent Test**: Cliente A transfere ingresso para Cliente B (seed); B aceita; ingresso some de "Meus ingressos" de A e aparece em "Meus ingressos" de B com QR próprio.

---

### P3: Docker Compose + testes básicos

**User Story**: Como avaliador, quero subir a aplicação inteira com um comando, e confiar que os pontos críticos têm teste automatizado.

**Why P3**: Não é feature de produto, mas pesa na avaliação técnica; opcional escolhido.

**Acceptance Criteria**:
1. WHEN o avaliador roda `docker compose up` THEN o sistema SHALL subir front-end, back-end e banco com dados seedados, prontos para uso, sem passos manuais adicionais.
2. WHEN a suíte de testes roda THEN o sistema SHALL cobrir, no mínimo: concorrência de reserva de assento (double-booking), validação de ingresso (válido/já usado/evento errado/inválido), e o fluxo de transferência.

**Independent Test**: `docker compose up` numa máquina limpa e o app funciona; `[comando de teste]` passa verde.

---

## Edge Cases

- WHEN o organizador define um mapa de assentos mas a capacidade não bate com linhas×colunas informadas THEN o sistema SHALL calcular capacidade automaticamente a partir do mapa (campo não é editável independente).
- WHEN um cliente perde conexão no meio do pagamento simulado (não confirma nem recusa) THEN o sistema SHALL tratar como não confirmado — hold expira normalmente em 5 min.
- WHEN o organizador tenta cancelar/editar um evento que já tem ingressos vendidos THEN o sistema SHALL avisar explicitamente sobre o impacto antes de confirmar (comportamento exato fica para design.md).
- WHEN a busca no TMDb não retorna nenhum filme THEN o sistema SHALL exibir estado vazio com sugestão de tentar outro termo.
- WHEN o token do QR é válido em formato mas não corresponde a nenhum ingresso no banco (ex.: ingresso de ambiente de teste antigo) THEN o sistema SHALL retornar "inválido", nunca vazar detalhe técnico do motivo.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
|---|---|---|---|
| CATALOG-01..04 | P1: Organizador publica evento | Design | Pending |
| BOOKING-01..08 | P1: Reserva e pagamento simulado | Design | Pending |
| TICKETS-01..03 | P1: Meus ingressos + QR | Design | Pending |
| GATE-01..06 | P1: Validação na portaria | Design | Pending |
| AUTH-01..04 | P2: Autenticação 3 papéis | Design | Pending |
| SEARCH-01..03 | P2: Busca e filtro | Design | Pending |
| CANCEL-01..03 | P2: Cancelamento | Design | Pending |
| DASH-01..02 | P2: Painel do organizador | Design | Pending |
| TRANSFER-01..06 | P2: Transferência de ingresso | Design | Pending |
| DEVOPS-01..02 | P3: Docker Compose + testes | Design | Pending |

**Coverage:** 40 critérios totais, 0 mapeados a tasks ainda, 40 pendentes ⚠️ (mapeamento acontece na fase Tasks)

---

## Success Criteria

- [ ] Fluxo ponta a ponta (cadastro/login → publicar evento → reservar → pagar → ver ingresso com QR → validar na portaria) roda sem erros com os dados seedados.
- [ ] Um teste automatizado de concorrência prova que o mesmo assento não é vendido duas vezes.
- [ ] Um teste automatizado prova que o mesmo ingresso não é validado duas vezes.
- [ ] `docker compose up` sobe tudo sem passos manuais extras.
- [ ] README explica setup, seed, decisões e uso de IA.
