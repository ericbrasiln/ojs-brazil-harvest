# Relatório de Erros — OJS Brazil Harvest

**Data:** 2026-06-04 (atualizado com resultados do Retry SSL)  
**Após:** Passada 1 (coleta integral) + Passada 2 (coleta por set) + Retry SSL (Etapa 1)

---

## Visão geral

| Métrica | Passada 1 | Passada 2 | Retry SSL | Total |
|---------|-----------|-----------|-----------|-------|
| Targets tentados | 221 URLs | 2.361 sets (59 portais) | 29 URLs (37 targets) | — |
| ✅ Sucesso | 70 (32%) | 1.828 (77%) | 31 (+6 skip) | — |
| ⏱ Timeout | 63 (28%) | 307 (13%) | 0 | 370 |
| ❌ Erro | 88 (40%) | 226 (10%) | 22 | 336 |
| **Registros coletados** | **48.298** | **599.684** | **54.948** | **702.930** |

---

## 1. Erros da Passada 1 — Periódicos isolados (68 URLs)

| Categoria | Qtd | Recuperável? | Estratégia | Status |
|-----------|-----|-------------|------------|--------|
| HTTP 102 Processing | 22 | Parcialmente | Retry com timeout 600s | Etapa 2 |
| SSL (certificado inválido) | 13 | ✅ Sim | Bypass SSL | ✅ Resolvido |
| ConnectTimeout | 13 | Parcialmente | Retry depois | Etapa 2 |
| XML/Parse error | 6 | Parcialmente | ojs-scrape já limpa | — |
| ConnectionError/DNS | 6 | Não | Domínio inexistente | — |
| HTTP error (genérico) | 2 | Parcialmente | Depende do código | — |
| Unclassified (traceback) | 6 | ? | Inspeção manual | Etapa 5 |

## 2. Erros da Passada 1 — Portais (20 URLs)

| Categoria | Qtd | Recuperável? | Estratégia | Status |
|-----------|-----|-------------|------------|--------|
| HTTP 102 Processing | 12 | Sim | Coletar por set (P2 tratou a maioria) | P2 |
| SSL | 4 | ✅ Sim | Bypass SSL | ✅ Resolvido |
| ConnectionError/DNS | 2 | Não | Domínio inexistente | — |
| ConnectTimeout | 1 | Parcialmente | Retry posterior | Etapa 2 |
| XML/Parse | 1 | Parcialmente | Limpeza de XML | — |

## 3. Timeouts da Passada 1 — Periódicos isolados (29 URLs)

Todos atingiram o limite de 240s. Estimativa de recuperação: ~15-20 com timeout 600s.

**Estratégia:** Retry com timeout 600s. Etapa 2.

---

## 4. Erros da Passada 2 — Sets com erro (226 sets em 20 portais)

A maioria (179/226) são erros dentro de `ojs-scrape` durante `list_records()` — provavelmente HTTP errors ou erros de parse do XML. O tempo de resposta (>5s em 223/226) indica conexão estabelecida, mas resposta falhou.

**Top portais com erros por set:**

| Portal | Total sets | OK | Erro | Timeout |
|--------|-----------|-----|------|---------|
| Periódicos da UFES | 100 | 70 | 24 | 6 |
| Portal de Periódicos da UFPB | 104 | 80 | 24 | 0 |
| OJS - UFSC | 35 | 22 | 13 | 0 |
| Portal de Conteúdo da SBC | 188 | 177 | 11 | 0 |
| SEER UFRGS | 99 | 79 | 11 | 9 |

**Estratégia:** Retry dos 226 sets com erro, timeout 300s, delay 2s. Etapa 3.

## 5. Timeouts da Passada 2 — Sets com timeout (307 sets em 30 portais)

| Portal | Sets com timeout | Total sets do portal |
|--------|-----------------|---------------------|
| Portal de Revistas da USP | **194** | 194 (100%) |
| Portal de Periódicos UFU - PPUFU | 26 | 47 |
| SEER UFRGS | 9 | 99 |
| Biblioteca Digital de Periódicos UFPR | 8 | 79 |
| Portal de Revistas Científicas da UFMT | 8 | 23 |

**USP:** 194/194 sets falharam — provavelmente rate limiting agressivo ou bloqueio de IP. Abordagem dedicada (Etapa 4).

**Outros:** Retry com timeout 300s, delay 2s. Estimativa: ~50-100 sets recuperáveis.

---

## 6. Retry SSL — Etapa 1 (RESOLVIDO)

| Métrica | Valor |
|---------|-------|
| URLs SSL tentadas | 29 (26 isolados, 3 portais) |
| Targets com sucesso | 37 (31 novos + 6 já existiam) |
| **Registros recuperados** | **54.948** |
| Erros HTTP 500 (servidor) | 15 |
| Erros OAI-PMH | 5 |
| SSL persistente | 1 (`portalgt.idp.edu.br`) |
| XML inválido | 1 (`coffeescience.ufla.br`) |

### Solução técnica

O `ojs-scrape` não suporta `verify=False`. O bypass functional requer monkey-patch em `requests.Session.request` (não em `Session.send` — que é chamado depois que o urllib3 já validou o certificado):

```python
_original_request = requests.Session.request
def _patched_request(self, method, url, **kwargs):
    kwargs.setdefault('verify', False)
    return _original_request(self, method, url, **kwargs)
requests.Session.request = _patched_request
```

Feature request registrada: [ericbrasiln/ojs-scrape#9](https://github.com/ericbrasiln/ojs-scrape/issues/9)

### Bug descoberto

`from_date="2000"` causa `OAI-PMH error [badArgument]` em 18/29 URLs. OAI-PMH exige formato `YYYY-MM-DD`. Forma correta: `from_date="2000-01-01"`. O `_record_params` do `ojs-scrape` não valida o formato — proposto como melhoria na mesma issue.

Top resultados: UFPE (23.246), Ufac (4.627), UNICENTRO (3.803), SPGG (3.316), UFRPE (3.258).

---

## 7. Resumo de recuperabilidade (atualizado)

| Categoria | Qtd | Recuperável | Estratégia | Status |
|-----------|-----|-------------|------------|--------|
| P1 isolados: SSL | 13 | ✅ | Bypass SSL | ✅ Resolvido |
| P1 portais: SSL | 4 | ✅ | Bypass SSL | ✅ Resolvido |
| P1 isolados: HTTP 102 | 22 | ⚠️ Parcial | Timeout 600s | Etapa 2 |
| P1 isolados: ConnectTimeout | 13 | ⚠️ Parcial | Retry depois | Etapa 2 |
| P1 isolados: timeout geral | 29 | ⚠️ Parcial | Timeout 600s | Etapa 2 |
| P2 sets: erro | 226 | ⚠️ Parcial | Retry timeout 300s, delay 2s | Etapa 3 |
| P2 sets: timeout (não-USP) | 113 | ⚠️ Parcial | Retry timeout 300s | Etapa 3 |
| P2 sets: USP timeout | 194 | ⚠️ Difícil | Delay 5-10s, madrugada | Etapa 4 |
| DNS/ConnectionError | 14 | ❌ Não | Domínios inexistentes | — |
| XML/Parse | 7 | ⚠️ Parcial | Melhorar tratamento | — |

**Ganho real até agora:** +54.948 registros (SSL bypass)  
**Estimativa de ganho restante:** +25.000-65.000 registros (Etapas 2-4)

---

## 8. Diagnóstico estratégico para o universo completo

1. **Coletar por set PRIMEIRO** para portais (elimina desperdício da Passada 1)
2. **Coletar integral** para periódicos isolados
3. **SSL bypass** como passo integrado (não mais categoria separada — aplicar automaticamente)
4. **Retry com timeout 600s** como segunda rodada
5. **USP e portais agressivos** requerem abordagem dedicada