# Backlog — Eventos da Vida

Lista de melhorias a abordar em sessões futuras. Cada item deve ser movido para "Feito" com a data quando for implementado.

## Por fazer

### 4) Alterar layout inicial
- Repensar o dashboard atual (regras no topo, filtros, lista de eventos, formulário manual).
- Possíveis direções: cards maiores com foto em destaque, vista de calendário em vez de lista para eventos aceites, agrupar recomendações por categoria em abas/secções separadas, mover o formulário manual para uma página/modal próprio.
- Sem decisão tomada ainda — a abordar em sessão dedicada com mockup/feedback iterativo.
- Relacionado com o item 7 (ecrã de calendário).

### 11) Alterar estado e data do evento a partir da vista de calendário
- No modal de detalhe de um dia no `/calendario`, permitir mudar o estado do evento (ex: aceite/rejeitado/adiado/pendente) diretamente ali, sem ter de ir ao dashboard.
- Para eventos já aceites mostrados no calendário, também poder alterar a data (tal como acontece nos outros estados/ecrãs).
- Reaproveitar a rota `set_event_status` já existente no dashboard (e a rota de correção de data via PATCH `/api/events/<id>`).

### 12) Crawler privilegiar páginas em português
- No cron de procura de eventos, quando uma fonte/resultado tiver versão em português e noutra língua, privilegiar sempre a página em português (ex: para extrair descrição, data, imagem).

### 13) Botão "Rejeitar" maior que "Aceitar"
- Nos cards de evento proposto (dashboard e calendário), o botão "Rejeitar" deve ser visualmente maior que o "Aceitar" (atualmente têm o mesmo tamanho — ver screenshot do utilizador, card "Festa do Jazz").

## Feito
- 2026-11-06 — Item 8 (caixa de calendário em todos os campos de data): faltava `onclick="showPicker()"` em 3 inputs (Aceitar no dashboard, data/data fim do formulário manual) — adicionado; o modal do calendário já tinha.
- 2026-11-06 — Item 9 (evitar duplicados na importação): `/api/events` agora deteta duplicados por título normalizado (sem acentos/pontuação) com similaridade ≥85% + mesma data (tolerância 2 dias) ou mesma cidade quando nenhum dos dois tem data; testado localmente com títulos quase-iguais. Criado `dedupe_events.py` (dry-run por omissão, `--apply` para remover) para limpar duplicados já existentes na BD — mantém o evento com status não-pending, depois o que tem imagem, depois o id mais antigo. Falta o utilizador correr `python dedupe_events.py --apply` na consola do PythonAnywhere para limpar a BD de produção.
- 2026-11-06 — Item 10 (foto via pesquisa web quando não há imagem própria): prompt do cron "Procura de Eventos" atualizado — quando a extração de `og:image`/`twitter:image` falha, faz agora uma pesquisa web por "<evento/artista> foto" antes de cair no SVG genérico.
- 2026-10-17 — Item 7 (ecrã de calendário): já estava implementado em sessão anterior não registada no backlog — rota `/calendario`, grid de 3 meses, legenda aceite/pendente, clique no dia abre modal com detalhe completo. Confirmado em produção (200 OK).
- 2026-10-15 — Item 6 (ação "Adiar"): botão "Adiar N dias" na UI (default 14), coluna `snoozed_until`, e reativação automática para `pending` quando a data passa (sem afetar pesos de preferência).
- 2026-10-14 — Título da página alterado para "Agenda Família Faria Valadão".
- 2026-10-14 — Imagens de fallback por categoria (SVG) + cron tenta extrair `og:image` via curl (opção 3 original: colar foto manualmente já era possível).
- 2026-10-14 — Filtros no dashboard: estado (proposto/aceite/rejeitado/adiado), categoria, intervalo de datas, preço máximo, distância máxima, só grátis.
- 2026-10-14 — Item 5 (mostrar detalhes completos nos eventos aceites) resolvido como efeito colateral dos filtros: a lista agora é unificada e qualquer estado mostra o card completo (foto, link, preço, distância, hora).
