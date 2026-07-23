# ROADMAP — OJS Brazil Harvest

Amostra de validação: ~1,169K registros brutos, ~925K únicos (38% do universo PKP Beacon).

---

## Fase 1: Preparação e amostra de validação ✅ CONCLUÍDA

- [x] Dataset PKP Beacon v6 processado e filtrado (6.086 periódicos BR, 5.861 responsivos)
- [x] Scripts de coleta funcionais preservados em `scripts/legacy/`; orquestrador de produção em `scripts/harvest_complete.py`
- [x] Amostra de validação: 221 URLs (P1) + 63 portais por set (P2)
- [x] Documentação de resultados e erros

## Fase 1.5: Retry de erros da amostra — PARCIALMENTE CONCLUÍDA

| Etapa | Descrição | Registros | Status |
|-------|-----------|-----------|--------|
| 1 | SSL bypass (`requests.Session.request` + `verify=False`) | +54.948 | ✅ |
| 2a | Isolados — probe + timeout 600s | +8.589 | ✅ |
| 2b | Portais por set com deduplicação | +453.884 | ✅ |
| 3 | P2 sets com erro — retry com SSL bypass + timeout 600s | +4.342 | ✅ |
| 4 | USP dedicado — 194 sets, rate limiting agressivo | — | ⏳ Pendente |
| 5 | Erros não classificados — investigar caso a caso | — | ⏳ Pendente |

**Lições consolidadas:**
- SSL bypass: monkey-patch em `requests.Session.request` (não `.send`); issue [ojs-scrape#9](https://github.com/ericbrasiln/ojs-scrape/issues/9)
- `from_date` deve ser `YYYY-MM-DD` (não ano isolado) — `badArgument` caso contrário
- Portais nunca devem ser coletados integralmente se já coletados por set — duplica dados
- Maioria dos "erros" da P2 era `noRecordsMatch` (sets vazios confirmados pelo servidor) — irrecuperável
- Erros HTTP 500/403/DNS são em geral permanentes — não recuperáveis do nosso lado
- Retorno decrescente: Etapa 2b (+453K) foi a mais produtiva; Etapa 3 (+4,3K) rendeu pouco

### Etapa 4 — USP dedicado

- 194 sets da USP com timeout na P2 (rate limiting agressivo)
- Estratégia: delay 5-10s entre sets, agendar para madrugada
- Se rate limiting persistir, investigar por IP ou user-agent
- Ganho estimado: +50K-100K registros (difícil, incerto)

### Etapa 5 — Erros não classificados

- ~6 URLs + 7 erros de XML/parse não categorizados
- Rodar `ojs-scrape` manualmente, classificar caso a caso
- Ganho incerto

## Fase 2: Coleta completa (no LABHDUFBA)

- [ ] Adaptar scripts para rodar em máquina do Lab (não VPS)
- [ ] Integrar SSL bypass nos scripts de produção (não como monkey-patch separado)
- [ ] Corrigir `from_date` para `"2000-01-01"` em todos os scripts
- [ ] Rodar coleta completa: 538 portais por set → 1.439 isolados
- [ ] Estimativa: 1,8-2,0 milhões de registros, 48-72h de processamento

## Fase 3: Pós-coleta

- [ ] Deduplicação por ISSN (muitos registros aparecem em múltiplos sets)
- [ ] Validação de integridade (campos obrigatórios, datas, DOIs)
- [ ] Enriquecimento: cruzar com CrossRef, ORCID, etc.
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
| 1.5 — Retry erros (amostra) | Etapas 1-3 ✅ · Etapas 4-5 pendentes | 🔄 Parcial |
| 2 — Coleta completa | 2-3 dias (máquina Lab) | ⏳ Pendente |
| 3 — Deduplicação e validação | 2-3 dias | ⏳ Pendente |
| 4 — Publicação | 1 semana | ⏳ Pendente |