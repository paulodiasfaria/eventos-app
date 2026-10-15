# Backlog — Eventos da Vida

Lista de melhorias a abordar em sessões futuras. Cada item deve ser movido para "Feito" com a data quando for implementado.

## Por fazer

### 2) Criar filtros no dashboard
- Filtrar por: tipo de evento (concerto/cultural/viagem), intervalo de datas, preço (grátis/pago/máximo), distância a Lisboa (ex: só <50km).
- Implementação sugerida: querystring na rota `/` (ex: `/?category=concert&max_price=20&max_distance=100`) + formulário de filtros no topo do dashboard + os filtros devem compor com a query SQL existente em `relevant_pending_query_rows`.
- Considerar guardar o último filtro usado (cookie ou localStorage) para não ter de reconfigurar sempre.

### 4) Alterar layout inicial
- Repensar o dashboard atual (regras no topo, recomendações, próximos eventos, formulário manual).
- Possíveis direções: cards maiores com foto em destaque, vista de calendário em vez de lista para "próximos eventos", agrupar recomendações por categoria em abas/secções separadas, mover o formulário manual para uma página/modal próprio.
- Sem decisão tomada ainda — a abordar em sessão dedicada com mockup/feedback iterativo.
- Relacionado com o item 7 (ecrã de calendário).

### 5) Mostrar detalhes completos nos eventos aceites
- A lista "Próximos eventos aceites" hoje só mostra data/título/categoria/cidade em texto.
- Passar a mostrar também: foto (ou fallback por categoria), link da fonte, preço/grátis, distância, hora — o mesmo nível de detalhe que já existe nos cards de recomendações pendentes.

### 6) Ação "Adiar" além de Aceitar/Rejeitar
- Hoje cada recomendação só tem 2 ações (Aceitar / Rejeitar).
- Adicionar uma 3ª ação "Adiar": mantém o evento como pendente mas sem afetar os pesos de preferência, e idealmente reaparece mais tarde (ex: esconder por N dias, ou baixar a prioridade sem penalizar o tag). Precisa de um novo status ou campo `snoozed_until` na tabela `events`.

### 7) Ecrã de calendário (3 meses)
- Novo ecrã/rota (ex: `/calendario`) com vista de calendário de 3 meses (mês atual + 2 seguintes).
- Dias com eventos ACEITES aparecem marcados; dias com PROPOSTAS pendentes aparecem a amarelo.
- Tooltip ao passar o rato num dia: nome do(s) evento(s) e características principais (categoria, hora, preço).
- Clicar no dia abre o card completo do evento (modal ou navega para a vista de detalhe).
- Vai precisar de uma rota de detalhe de evento por id (hoje não existe, só existe a listagem).

## Feito
- 2026-10-14 — Título da página alterado para "Agenda Família Faria Valadão".
- 2026-10-14 — Imagens de fallback por categoria (SVG) + cron tenta extrair `og:image` via curl (opção 3 original: colar foto manualmente já era possível).
