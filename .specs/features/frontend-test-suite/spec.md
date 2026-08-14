# Frontend Test Suite — Spec

Mini-feature fora do `tasks.md` original (escopo revisitado pelo usuário). Repo alvo: `frontend/` (`ticket-sales-platform-web`). Cobertura básica com Vitest + React Testing Library sobre três telas com regras de negócio na UI, mockando a camada `src/api/*.ts` por módulo e deixando os hooks reais de `src/api/hooks/` (AD-009) rodarem por cima.

## AC-01 — Setup

WHEN o repo tem Vitest + React Testing Library configurado THEN `npm run test` roda a suíte (via `vitest run`) sem erro de configuração (ambiente `jsdom`, arquivo de setup carregando `@testing-library/jest-dom`).

## AC-02 — Checkout (`src/features/booking/CheckoutPage.tsx`)

- AC-02a: WHEN o pagamento é processado com um cartão terminado em `0000` THEN a tela mostra o texto "Pagamento recusado" e oferece um botão "Tentar novamente".
- AC-02b: WHEN o pagamento é aprovado (qualquer outro cartão) THEN a tela navega para `/tickets/:ticketId` (o ingresso pago).
- AC-02c: WHEN a reserva (`ticket.expires_at`) está no passado THEN a tela mostra "Reserva expirada" em vez do formulário de pagamento.

## AC-03 — Cancelamento (`src/features/tickets/TicketDetailPage.tsx`, fluxo T31)

- AC-03a: WHEN o usuário clica em "Cancelar ingresso" THEN a tela pede confirmação explícita ("Tem certeza que deseja cancelar este ingresso?") antes de executar o cancelamento.
- AC-03b: WHEN o cancelamento é confirmado e a API responde com sucesso THEN o status exibido na tela atualiza para refletir o novo status do ticket (ex.: "Cancelado").
- AC-03c: WHEN a API rejeita o cancelamento (ex.: 422, fora da janela permitida) THEN a tela mostra a mensagem de erro **vinda da API** (`error.message`), não uma mensagem genérica fixa no código.

## AC-04 — Portaria (`src/features/gate/GatePage.tsx`)

WHEN o operador valida um código digitado manualmente (câmera fora de escopo — não testável em jsdom) THEN a tela renderiza o banner correspondente ao `GateResult` retornado pela API, para os 4 valores possíveis:

- AC-04a: `VALID` → banner mostra "VÁLIDO" (mais assento/cliente quando presentes na resposta).
- AC-04b: `INVALID` → banner mostra "INVÁLIDO".
- AC-04c: `ALREADY_USED` → banner mostra "JÁ UTILIZADO".
- AC-04d: `WRONG_EVENT` → banner mostra "EVENTO ERRADO".

## Fora de escopo (deliberado)

Todas as outras telas do repo web (auth, listagem/detalhe de evento, organizador, transferência, leitura de QR por câmera na portaria) — verificadas manualmente contra o backend real, não cobertas por teste automatizado nesta rodada (decisão do usuário: "cobrir o básico").

## Gate Check Commands

- Quick: `npm run test` (dentro de `frontend/`)
- Build (última task): `npm run build && npm run lint && npm run test` (dentro de `frontend/`)
