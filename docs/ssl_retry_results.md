# Etapa 1 — SSL Bypass Retry — Resultado

**Data:** 2026-06-04
**Branch:** `fix/retry-errors`
**Script histórico:** `scripts/legacy/retry_ssl.py`

## Resumo

| Métrica | Valor |
|---------|-------|
| URLs SSL tentadas | 29 (26 isolados, 3 portais) |
| Targets com sucesso | 37 (31 novos + 6 já existiam) |
| Registros recuperados | **54.948** |
| Erros HTTP (servidor) | 15 |
| Erros OAI-PMH | 5 |
| SSL persistente | 1 |
| XML inválido | 1 |

## Solução técnica

O `ojs-scrape` não suporta `verify=False`. O bypass SSL requer monkey-patch em `requests.Session.request`:
```python
_original_request = requests.Session.request
def _patched_request(self, method, url, **kwargs):
    kwargs.setdefault('verify', False)
    return _original_request(self, method, url, **kwargs)
requests.Session.request = _patched_request
```
Nota: patch em `Session.send` **não funciona** — o `verify` deve ser injetado no nível de `request()`, antes da chamada ao adapter.

Bug secundário corrigido: `from_date="2000"` causa `badArgument` em 18/29 URLs. Formato correto: `"2000-01-01"`.

## Top resultados

| Portal/Revista | Registros |
|---------------|-----------|
| Portal UFPE | 23.246 |
| Portal Ufac | 4.627 |
| UNICENTRO | 3.803 |
| Revistas SPGG | 3.316 |
| Portal UFRPE | 3.258 |
| Portal UNIVASF | 1.535 |
| Portal UENP | 1.454 |
| FATEC Guarulhos | 1.051 |

## Erros não recuperáveis

- **15 HTTP 500**: servidores com erro interno (UFMG, UnB, UNICAMP InPEC, Mackenzie, UEFS, etc.)
- **5 OAI-PMH**: `noRecordsMatch` ou `noSetSubset` em sets vazios
- **1 SSL persistente**: portalgt.idp.edu.br
- **1 XML inválido**: coffeescience.ufla.br

## Arquivo de resultados

`data/raw/retry_ssl_results_20260604_135838.json`