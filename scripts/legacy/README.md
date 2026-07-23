# Scripts legados

Estes scripts documentam as passadas amostrais e as tentativas de recuperação executadas entre maio e junho de 2026.

Eles foram preservados para auditoria metodológica dos resultados históricos. **Não devem ser usados para iniciar uma nova coleta.**

A coleta de produção usa exclusivamente:

```bash
python3 scripts/harvest_complete.py --resume -v
```

## Inventário

| Script | Uso histórico | Situação |
|---|---|---|
| `harvest_batch.py` | Primeira coleta integral por URL e amostras com seeds | Substituído pelas fases 1 e 2 do orquestrador |
| `harvest_by_set.py` | Segunda passada por set nos portais com timeout | Substituído pela fase 1 |
| `retry_ssl.py` | Recuperação com monkey-patch de SSL | Obsoleto após `--no-verify-ssl` no `ojs-scrape` |
| `retry_with_probe.py` | Protótipo de probe e retry de erros | Substituído pelos scripts específicos e pela fase 3 |
| `retry_isolated.py` | Retry dos periódicos isolados com probe alive/slow/dead | Parcialmente substituído pela fase 3; probe ainda não portado |
| `retry_portals_by_set.py` | Retry de portais sem duplicar sets já coletados | Substituído pelas fases 1 e 3 |
| `retry_p2_errors.py` | Retry final com filtros de USP, `noRecordsMatch` e erros 500 permanentes | Parcialmente substituído pela fase 3; filtros ainda não portados |

## Limitações

- Alguns scripts aplicam monkey-patch global em `requests` para ignorar certificados SSL.
- Os nomes de saída não têm o identificador estável usado pelo orquestrador atual.
- Os scripts dependem de arquivos de resultado específicos das coletas históricas.
- Eles não recebem as mesmas correções, testes ou garantias de retomada do código de produção.

Antes de remover definitivamente `retry_isolated.py` e `retry_p2_errors.py`, portar para o orquestrador as estratégias de probe e classificação de falhas permanentes.

Os caminhos antigos são mantidos nas páginas de resultados como registro histórico, com o prefixo atual `scripts/legacy/`.
