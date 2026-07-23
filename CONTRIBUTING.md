# Contribuindo

Este repositório reúne scripts e documentação para coleta de metadados OAI-PMH de periódicos OJS brasileiros.

## Regras gerais

- Trabalhe em branch própria.
- Não faça commit direto em `main`.
- Não versione dados brutos de coleta em `data/raw/`.
- Não versione saídas consolidadas em `data/derived/` sem decisão explícita.
- Preserve proveniência e checksums quando alterar dados processados.
- Antes de abrir PR, rode os testes e explique quais comandos foram executados.

## Ambiente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Testes mínimos

```bash
python3 -m pytest -q
ruff check scripts/harvest_complete.py scripts/prepare_beacon_dataset.py scripts/process_harvest.py tests
python3 -m py_compile scripts/*.py scripts/legacy/*.py tests/test_*.py
```

## Dados e privacidade

O arquivo bruto global do PKP Beacon (`beacon.tab`) não deve ser commitado.
Ele inclui `admin_email` e registros globais fora do escopo brasileiro.
Use `scripts/prepare_beacon_dataset.py --download` para reconstruir o recorte brasileiro sem campos de contato.

## Scripts legados

Scripts em `scripts/legacy/` são preservados para auditoria metodológica.
Não os use para novas coletas.
Se uma lição de um script legado ainda for necessária, porte a lógica para `scripts/harvest_complete.py` ou `scripts/process_harvest.py` com testes.
