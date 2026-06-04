# ROADMAP — OJS Brazil Harvest

Próximas etapas do projeto, com base nos resultados da amostra de validação (~910K registros, 37% do potencial).

---

## Fase 1: Preparação para coleta completa ✅ CONCLUÍDA

- [x] Dataset PKP Beacon processado e filtrado
- [x] Scripts de coleta funcionais (harvest_batch.py, harvest_by_set.py)
- [x] Amostra de validação coletada (5 seeds, 221 URLs)
- [x] Coleta por set nos portais amostrais (59 portais, 2.361 sets)
- [x] Documentação de resultados e erros

## Fase 1.5: Retry de erros da amostra 🔄 EM ANDAMENTO

- [x] **Etapa 1 — SSL bypass:** 54.948 registros recuperados de 29 URLs; monkey-patch funcional; issue aberta no ojs-scrape
- [ ] **Etapa 2 — Timeout 600s:** retry de 29 URLs com timeout + 22 HTTP 102
- [ ] **Etapa 3 — Retry P2 sets:** 226 sets com erro + 113 sets com timeout (não-USP)
- [ ] **Etapa 4 — USP dedicado:** 194 sets, delay 5-10s, madrugada
- [ ] **Etapa 5 — Investigar unclassified:** 6 URLs + 7 XML errors

## Fase 2: Coleta completa (no LABHDUFBA)

- [ ] Adaptar scripts para rodar em máquina do Lab (não VPS)
- [ ] Integrar SSL bypass nos scripts de produção (não como monkey-patch separado)
- [ ] Corrigir `from_date` para `"2000-01-01"` em todos os scripts
- [ ] Rodar coleta completa: 538 portais por set → 1.439 isolados
- [ ] Estimativa: 1,8-2,0 milhões de registros, 48-72h de processamento

## Fase 3: Pós-coleta

- [ ] Deduplicação por ISSN (muitos registros aparecem em múltiplos sets)
- [ ] Validação de integridade (campos obrigatórios, datas, DOIs)
- [ ] Enriquecimento: cruzar com base CrossRef, ORCID, etc.
- [ ] Consolidar resultados de todas as fases (P1 + P2 + SSL + retry)

## Fase 4: Publicação

- [ ] Dataset final em Zenodo ou Dataverse (DOI)
- [ ] Relatório de infraestrutura dos periódicos OJS brasileiros
- [ ] Artigo metodológico
- [ ] Repositório GitHub público com scripts e documentação

---

## Cronograma estimado

| Fase | Duração estimada | Status |
|------|-----------------|--------|
| 1.5 — Retry erros (amostra) | 1-2 dias | 🔄 Etapa 1 concluída |
| 2 — Coleta completa | 2-3 dias (máquina Lab) | ⏳ Pendente |
| 3 — Deduplicação e validação | 2-3 dias | ⏳ Pendente |
| 4 — Publicação | 1 semana | ⏳ Pendente |