# Backlog — Eventos da Vida

Lista de melhorias a abordar em sessões futuras. Cada item deve ser movido para "Feito" com a data quando for implementado.

## Por fazer

### 1) Colocar foto nos eventos
- `image_url` já existe no schema e já é mostrado no dashboard quando preenchido.
- O que falta: uma forma fiável de obter a imagem automaticamente via cron (a 1ª tentativa com `web_extract` nas páginas fonte não encontrou imagens).
- Opções a explorar:
  - Usar a Open Graph image (`og:image`) da página fonte via scraping direto (requests + BeautifulSoup) em vez de `web_extract`.
  - Fallback: imagem genérica por categoria (concerto 🎸 / cultural 🖼️ / viagem ✈️) quando não há foto real.
  - Permitir ao utilizador colar a foto manualmente ao aceitar um evento (já é possível no formulário manual).

### 2) Criar filtros no dashboard
- Filtrar por: tipo de evento (concerto/cultural/viagem), intervalo de datas, preço (grátis/pago/máximo), distância a Lisboa (ex: só <50km).
- Implementação sugerida: querystring na rota `/` (ex: `/?category=concert&max_price=20&max_distance=100`) + formulário de filtros no topo do dashboard + os filtros devem compor com a query SQL existente em `relevant_pending_query_rows`.
- Considerar guardar o último filtro usado (cookie ou localStorage) para não ter de reconfigurar sempre.

### 3) Alterar título da página
- ✅ Decidido: "Agenda Família Faria Valadão" — atualizado em `templates/base.html`.

### 4) Alterar layout inicial
- Repensar o dashboard atual (regras no topo, recomendações, próximos eventos, formulário manual).
- Possíveis direções: cards maiores com foto em destaque, vista de calendário em vez de lista para "próximos eventos", agrupar recomendações por categoria em abas/secções separadas, mover o formulário manual para uma página/modal próprio.
- Sem decisão tomada ainda — a abordar em sessão dedicada com mockup/feedback iterativo.

## Feito
- 2026-10-14 — Título da página alterado para "Agenda Família Faria Valadão".
