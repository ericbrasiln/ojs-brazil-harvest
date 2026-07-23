# Proveniência dos dados de entrada

## Fonte

O dataset de entrada deriva do **PKP Beacon**, publicado no Harvard Dataverse:

- Khanna, S.; Raoni, J.; Smecher, A.; Alperin, J. P.; Ball, J.; Willinsky, J. (2025). *Details of publications using software by the Public Knowledge Project*. Harvard Dataverse. DOI: [10.7910/DVN/OCZNVY](https://doi.org/10.7910/DVN/OCZNVY).
- Versão usada neste projeto: **v6.0**, publicada em 2025-11-21.
- Arquivo-fonte Dataverse: `beacon.tab`, datafile id `13173372`.
- URL tabular usada pelo script: `https://dataverse.harvard.edu/api/access/datafile/13173372`.
- SHA-256 da exportação tabular normalizada pelo Dataverse: `3f594d706d8832de6d696be74b9d30085833d6404ec3227e29871985fd4be3b0`.

## Por que `data/raw/beacon.tab` não é versionado

O arquivo bruto global possui 87.170 registros e inclui o campo `admin_email`.
Esse campo não é necessário para a coleta OAI-PMH brasileira.
Para minimizar dados pessoais e reduzir o tamanho do repositório institucional, o bruto foi removido da árvore versionada.

O repositório mantém apenas o recorte processado necessário à coleta:

- `data/processed/ojs_brazil_pkp_beacon.json`
- 6.086 registros OJS classificados como Brasil (`country_consolidated == "BR"` e `application == "ojs"`)
- sem `admin_email`

## Reproduzir o recorte brasileiro

```bash
python3 scripts/prepare_beacon_dataset.py \
  --download \
  --source data/raw/beacon.tab \
  --output data/processed/ojs_brazil_pkp_beacon.json
```

Para reproduzir a partir de um arquivo já baixado:

```bash
python3 scripts/prepare_beacon_dataset.py \
  --source data/raw/beacon.tab \
  --output data/processed/ojs_brazil_pkp_beacon.json
```

O script:

1. baixa a exportação tabular oficial do Dataverse quando `--download` é usado;
2. valida o SHA-256 da fonte;
3. filtra `application == "ojs"`;
4. filtra `country_consolidated == "BR"`;
5. remove campos de contato e campos não usados pela coleta;
6. normaliza tipos numéricos e booleanos;
7. troca múltiplos ISSNs separados por `\n` por `; `;
8. grava JSON reprodutível.

## Verificações locais

Com a fonte v6 já baixada, o recorte reconstruído foi byte a byte idêntico ao JSON versionado:

```text
sha256(data/processed/ojs_brazil_pkp_beacon.json) = a87c252e8011ec3d215b8c5ffe0879ecdd71594f9e8c07aaf72cc986eea68846
```

Os PDFs metodológicos do PKP Beacon permanecem versionados em `docs/` porque são pequenos e documentam a fonte:

- `docs/data_dictionary.pdf`
- `docs/journals_location.pdf`
