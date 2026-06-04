# Plano de Ação — Retry de Erros da Amostra

**Branch:** `fix/retry-errors`  
**Objetivo:** Recuperar o máximo de registros dos targets que falharam na amostra, testando as estratégias antes de escalar para o universo completo.

---

## Visão geral dos 684 problemas

| Categoria | Qtd | Prioridade | Ganho estimado |
|-----------|-----|------------|---------------|
| P1 isolados: SSL | 13 | Alta | +5K-10K registros |
| P1 isolados + portais: HTTP 102 | 34 | Alta | +10K-20K |
| P1 isolados: timeout (240s) | 29 | Alta | +5K-15K |
| P2 sets: erro (226) | 226 | Média | +20K-40K |
| P2 sets: timeout não-USP (113) | 113 | Média | +10K-30K |
| P2 sets: USP timeout (194) | 194 | Baixa | +50K-100K (difícil) |
| DNS/ConnectionError | 14 | Ignorar | 0 |
| XML/Parse | 7 | Baixa | incerto |
| Unclassified | 8 | Baixa | investigar |

---

## Etapa 1 — SSL bypass (13 isolados + 4 portais)

**O que fazer:**
- Implementar flag `--no-verify-ssl` em `harvest_batch.py` e `harvest_by_set.py`
- O `ojs-scrape` não tem essa flag — setar `PYTHONHTTPSVERIFY=0` no subprocesso
- Extrair as 17 URLs com erro SSL do `harvest_results`
- Rodar retry apenas nessas URLs

**Script necessário:**
- `scripts/retry_ssl.py` — lê URLs com erro SSL dos resultados, roda `ojs-scrape` com `PYTHONHTTPSVERIFY=0`

**Verificação:** comparar registros novos vs. os 17 URLs esperados

---

## Etapa 2 — Retry P1 isolados com timeout 600s (29 URLs + 22 HTTP 102)

**O que fazer:**
- Extrair as 29 URLs com timeout e as 22 com HTTP 102 da P1
- Rodar `harvest_batch.py` com `--timeout 600` apenas nessas URLs
- As 13 com ConnectTimeout provavelmente vão falhar de novo, mas tentamos

**Script necessário:**
- `scripts/retry_timeouts.py` — lê URLs com timeout/HTTP 102, roda com timeout 600s

**Verificação:** quantas passam de timeout 240s → 600s

---

## Etapa 3 — Retry P2 sets com erro e timeout (226 + 113 não-USP)

**O que fazer:**
- Extrair os 226 sets com erro e 113 com timeout (excluindo USP) do `harvest_by_set_results`
- Executar `harvest_by_set.py` com `--timeout 300 --delay 2` apenas nesses sets
- Implementar filtragem de sets específicos (não reprocessar os que já deram OK)

**Modificação necessária:**
- `harvest_by_set.py`: aceitar lista de sets para retry via `--retry-from <arquivo>`
- Melhorar captura de stderr (aumentar de 500 para 2000 chars) para classificar erros

**Verificação:** comparar taxa de sucesso com a primeira tentativa

---

## Etapa 4 — USP dedicado (194 sets)

**O que fazer:**
- Tentar coleta com delay 5-10s entre sets
- Agendar para horário de madrugada (2h-6h BRT)
- Se rate limiting persistir, investigar se é por IP ou por user-agent

**Script necessário:**
- `scripts/harvest_usp.py` — coleta dedicada para o portal da USP com delay alto

**Verificação:** se pelo menos 1 set coletar com sucesso, o rate limiting pode ser contornado com delay

---

## Etapa 5 — Investigar erros não classificados (8 URLs + 7 XML)

**O que fazer:**
- Rodar `ojs-scrape` manualmente em cada URL, capturando stderr completo
- Classificar o tipo real de erro
- Decidir tratamento caso a caso

---

## Ordem de execução

1. **Etapa 1** (SSL) — mais fácil, ganho garantido
2. **Etapa 2** (P1 timeouts) — simples, timeout maior
3. **Etapa 3** (P2 retry) — precisa modificar script, maior volume
4. **Etapa 5** (investigar unclassified) — informa se precisamos de tratamento especial
5. **Etapa 4** (USP) — mais incerto, por último

Cada etapa gera um relatório incremental atualizando `docs/error_report.md`.