# Backlog — Eventos da Vida

Lista de melhorias a abordar em sessões futuras. Cada item deve ser movido para "Feito" com a data quando for implementado.

## Por fazer

### 4) Alterar layout inicial
- Repensar o dashboard atual (regras no topo, filtros, lista de eventos, formulário manual).
- Possíveis direções: cards maiores com foto em destaque, vista de calendário em vez de lista para eventos aceites, agrupar recomendações por categoria em abas/secções separadas, mover o formulário manual para uma página/modal próprio.
- Sem decisão tomada ainda — a abordar em sessão dedicada com mockup/feedback iterativo.
- Relacionado com o item 7 (ecrã de calendário).

### 6) Ação "Adiar" além de Aceitar/Rejeitar
- Hoje cada recomendação só tem 2 ações (Aceitar / Rejeitar).
- Adicionar uma 3ª ação "Adiar": mantém o evento como pendente mas sem afetar os pesos de preferência, e idealmente reaparece mais tarde (ex: esconder por N dias, ou baixar a prioridade sem penalizar o tag).
- O filtro de estado "Adiado" já existe no dashboard (status=snoozed) à espera desta implementação — falta: botão "Adiar" na UI, nova coluna `snoozed_until` na tabela `events`, e lógica para o evento voltar a aparecer como pendente quando a data passar.

### 7) Ecrã de calendário (3 meses)
- Novo ecrã/rota (ex: `/calendario`) com vista de calendário de 3 meses (mês atual + 2 seguintes).
- Dias com eventos ACEITES aparecem marcados; dias com PROPOSTAS pendentes aparecem a amarelo.
- Tooltip ao passar o rato num dia: nome do(s) evento(s) e características principais (categoria, hora, preço).
- Clicar no dia abre o card completo do evento (modal ou navega para a vista de detalhe).
- Vai precisar de uma rota de detalhe de evento por id (hoje não existe, só existe a listagem).

## Feito
- 2026-10-14 — Título da página alterado para "Agenda Família Faria Valadão".
- 2026-10-14 — Imagens de fallback por categoria (SVG) + cron tenta extrair `og:image` via curl (opção 3 original: colar foto manualmente já era possível).
- 2026-10-14 — Filtros no dashboard: estado (proposto/aceite/rejeitado/adiado*), categoria, intervalo de datas, preço máximo, distância máxima, só grátis. (*adiado ainda sem forma de lá chegar — ver item 6).
- 2026-10-14 — Item 5 (mostrar detalhes completos nos eventos aceites) resolvido como efeito colateral dos filtros: a lista agora é unificada e qualquer estado mostra o card completo (foto, link, preço, distância, hora).
