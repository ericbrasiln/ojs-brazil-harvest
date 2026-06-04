# Resultados da Coleta OAI-PMH — Amostra de Validação

**Período:** 2026-05-31 a 2026-06-03  
**Dataset fonte:** PKP Beacon v6 (6.086 OJS Brasil, 5.861 responsivos)  
**Scripts:** `scripts/harvest_batch.py` (P1), `scripts/harvest_by_set.py` (P2)

---

## Resumo Consolidado (Passada 1 + Passada 2)

| Métrica | Passada 1 (integral) | Passada 2 (por set) | Total |
|---------|---------------------|---------------------|-------|
| Targets tentados | 221 URLs | 2.361 sets (59 portais) | — |
| ✅ Sucesso | 70 (32%) | 1.828 (77%) | 1.898 |
| ⏱ Timeout | 63 (28%) | 307 (13%) | 370 |
| ❌ Erro | 88 (40%) | 226 (10%) | 314 |
| **Registros coletados** | **48.298** | **599.684** | **647.982** |

| Métrica de disco | Valor |
|------------------|-------|
| Registros em disco | 856.085 |
| Arquivos JSON | 2.097 |
| Tamanho em disco | 3,5 GB |
| Potencial do dataset PKP | 2.445.213 registros |
| Cobertura do potencial | **35%** |

---

## Diagnóstico: portal vs. periódico isolado (Passada 1)

| Tipo | Tentados | Sucesso | Taxa |
|------|----------|---------|------|
| Periódicos isolados | 166 | 69 | **42%** |
| Portais multi-revista | 55 | 1 | **2%** |

**Conclusão:** a coleta integral serve para periódicos isolados, mas é ineficaz para portais. A Passada 2 por set confirmou que os mesmos portais que falhavam na P1 rendem 77% de sucesso quando coletados set por set.

---

## Evolução das coletas (Passada 1)

| Run (seed) | Targets | OK | Erro | Timeout | Registros |
|------------|---------|----|------|---------|-----------|
| 130833 (s1, n5) | 5 | 3 | 1 | 1 | 4.065 |
| 154841 (s2, n100) | 91 | 40 | 24 | 27 | 56.239 |
| 192035 (s3, n200) | 144 | 60 | 49 | 35 | 59.363 |
| 001302 (s4, n400) | 205 | 92 | 66 | 47 | 89.021 |
| 055940 (s4, n400, resume) | 221 | 70 | 88 | 63 | 48.298 |

Notas: cada run usa `--sample` com seeds diferentes, então as URLs não são as mesmas. A última run (055940) usou `--resume` e processou targets que não tinham sido tentados nas runs anteriores.

---

## Passada 2 — Classificação dos portais

| Categoria | Qtd | Descrição |
|-----------|-----|-----------|
| Todos sets OK | 6 | Coleta completa sem falhas |
| Parcialmente OK | 46 | Alguns sets falharam, maioria OK |
| 100% falha | 7 | Nenhum set coletado (incl. USP com 194 sets) |

---

## Top 10 portais por volume (Passada 2)

| Portal | Sets OK | Registros |
|--------|---------|-----------|
| Portal de Conteúdo da SBC | 177/188 | 34.498 |
| SEER UFRGS | 79/99 | 38.508 |
| Biblioteca Digital Periódicos UFPR | 65/79 | 21.145 |
| Portal de Periódicos da UFPB | 80/104 | 20.415 |
| Periódicos da UFES | 70/100 | 18.549 |
| Periódicos da UFF | 64/72 | 19.422 |
| Portal de Periódicos UFSC | 39/50 | 24.523 |
| Portal de Periódicos UFPE | 62/70 | 12.949 |
| Portal de Periódicos da UFU | 21/47 | 4.947 |
| Portal de Periódicos Unicamp | 33/33 | 38.104 |

---

## Estatísticas dos periódicos com sucesso (Passada 1)

- Média: 690 registros/periódico
- Mediana: 293 registros/periódico
- Mínimo: 5 registros
- Máximo: 4.596 registros

---

## Próximos passos

Detalhados em `docs/ROADMAP.md`.