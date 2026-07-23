# Inventário de scripts

## Produção

| Script | Função | Situação |
|---|---|---|
| `scripts/harvest_complete.py` | Orquestra a coleta completa em três fases: portais por set, isolados e retry | Entrada canônica de produção |
| `scripts/prepare_beacon_dataset.py` | Reproduz o recorte brasileiro do PKP Beacon v6 a partir do arquivo tabular oficial | Utilitário de preparo de dados |

## Legado preservado para auditoria

Os scripts abaixo foram usados nas passadas amostrais e nas recuperações documentadas em `docs/harvest_results.md`, `docs/retry_plan.md` e `docs/ssl_retry_results.md`.
Eles foram movidos para `scripts/legacy/` para evitar uso acidental em nova coleta.

| Script | Uso histórico | Substituição em produção |
|---|---|---|
| `scripts/legacy/harvest_batch.py` | Passada inicial por URL, com amostras e seeds | `harvest_complete.py`, fases 1 e 2 |
| `scripts/legacy/harvest_by_set.py` | Coleta por set dos portais com timeout | `harvest_complete.py`, fase 1 |
| `scripts/legacy/retry_ssl.py` | Recuperação de erros SSL via monkey-patch | `ojs-scrape --no-verify-ssl` e `harvest_complete.py` |
| `scripts/legacy/retry_with_probe.py` | Protótipo de probe e retry inteligente | `harvest_complete.py`, fase 3 |
| `scripts/legacy/retry_isolated.py` | Retry de periódicos isolados, precedido por probe alive/slow/dead | Parcialmente substituído pela fase 3; o probe ainda deve ser portado |
| `scripts/legacy/retry_portals_by_set.py` | Retry de portais por set sem duplicar P2 | `harvest_complete.py`, fases 1 e 3 |
| `scripts/legacy/retry_p2_errors.py` | Retry final dos erros das passadas P2 e 2b, com filtros para USP, `noRecordsMatch` e erros 500 permanentes | Parcialmente substituído pela fase 3; os filtros ainda devem ser portados |

## Decisão de curadoria

- Manter os scripts legados no repositório por enquanto, porque eles documentam a trajetória metodológica da amostra.
- Não executar scripts legados para coleta nova.
- Não exigir Ruff limpo nos legados enquanto eles estiverem preservados apenas como histórico.
- Portar para o orquestrador, antes de eventual remoção dos legados: probe alive/slow/dead e filtros de falhas permanentes.
- Revisitar no bloco de publicação se esses scripts devem ser removidos de uma versão institucional limpa ou mantidos em tag/histórico.
