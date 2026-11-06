# Backlog — Eventos da Vida

Lista de melhorias a abordar em sessões futuras. Cada item deve ser movido para "Feito" com a data quando for implementado.

## Por fazer

### 4) Alterar layout inicial
- Repensar o dashboard atual (regras no topo, filtros, lista de eventos, formulário manual).
- Possíveis direções: cards maiores com foto em destaque, vista de calendário em vez de lista para eventos aceites, agrupar recomendações por categoria em abas/secções separadas, mover o formulário manual para uma página/modal próprio.
- Sem decisão tomada ainda — a abordar em sessão dedicada com mockup/feedback iterativo.
- Relacionado com o item 7 (ecrã de calendário).

### 8) Caixa de calendário em todos os campos de data
- Todos os campos de data (`<input type="date">`) devem abrir a caixa de calendário nativa ao clicar em qualquer ponto do campo, não só no ícone.
- Verificar se já está aplicado em todos os pontos (filtros, modal do calendário, formulário manual) ou se falta em algum.

### 9) Evitar eventos duplicados na importação
- A BD tem eventos repetidos. Ao importar (via `/api/events`, cron de procura), detetar e ignorar duplicados antes de inserir (ex: mesmo título + data, ou título muito semelhante + data próxima).
- Também considerar uma limpeza pontual dos duplicados já existentes na BD.

### 10) Procurar foto na web quando o evento não tem imagem própria
- Quando um evento não tem imagem própria (cai no fallback SVG por categoria), fazer pesquisa na web para encontrar uma foto real do evento ou do artista/local associado, em vez de ficar só com o SVG genérico.

## Feito
- 2026-10-17 — Item 7 (ecrã de calendário): já estava implementado em sessão anterior não registada no backlog — rota `/calendario`, grid de 3 meses, legenda aceite/pendente, clique no dia abre modal com detalhe completo. Confirmado em produção (200 OK).
- 2026-10-15 — Item 6 (ação "Adiar"): botão "Adiar N dias" na UI (default 14), coluna `snoozed_until`, e reativação automática para `pending` quando a data passa (sem afetar pesos de preferência).
- 2026-10-14 — Título da página alterado para "Agenda Família Faria Valadão".
- 2026-10-14 — Imagens de fallback por categoria (SVG) + cron tenta extrair `og:image` via curl (opção 3 original: colar foto manualmente já era possível).
- 2026-10-14 — Filtros no dashboard: estado (proposto/aceite/rejeitado/adiado), categoria, intervalo de datas, preço máximo, distância máxima, só grátis.
- 2026-10-14 — Item 5 (mostrar detalhes completos nos eventos aceites) resolvido como efeito colateral dos filtros: a lista agora é unificada e qualquer estado mostra o card completo (foto, link, preço, distância, hora).
