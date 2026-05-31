# OJS Brazil Harvest

Coleta massiva de metadados de periódicos brasileiros hospedados em plataformas OJS (Open Journal Systems), usando o pacote [ojs-scrape](https://pypi.org/project/ojs-scrape/) e o dataset [PKP Beacon](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/OCZNVY) como fonte das URLs.

O projeto coleta **apenas metadados** (via protocolo OAI-PMH) — **sem download de PDFs**.

## Motivação

Mapear a produção acadêmica brasileira veiculada em periódicos OJS, extraindo dados estruturados (títulos, autores, palavras-chave, datas, DOIs) para análise bibliométrica e historiográfica.

## Dataset PKP Beacon

- **Fonte:** Khanna, S.; Raoni, J.; Smecher, A.; Alperin, J.P.; Ball, J.; Willinsky, J. (2025). "Details of publications using software by the Public Knowledge Project". Harvard Dataverse, V6. DOI: [10.7910/DVN/OCZNVY](https://doi.org/10.7910/DVN/OCZNVY)
- **Licença:** CC0 1.0 Universal
- **Dados:** 87.170 instalações OJS/OMP/OPS no mundo
- **Atualização:** Novembro 2025

### Periódicos brasileiros no dataset

- **6.086 periódicos OJS** com `country_consolidated = BR`
- **5.861** com endpoint OAI-PMH responsivo
- **2.445.213 registros** (artigos) no total
- **2.127 OAI URLs únicas** (muitos periódicos compartilham domínios multi-journal SEER)

## Estrutura do projeto

```
ojs-brazil-harvest/
├── config/           # Listas de periódicos e configurações de coleta
│   └── journals_list.txt
├── data/
│   ├── raw/          # Dados brutos do PKP Beacon (beacon.tab, PDFs)
│   ├── processed/   # Dados filtrados (ojs_brazil_pkp_beacon.json, URL list)
│   └── logs/        # Logs de execução
├── scripts/          # Scripts de coleta e processamento
├── docs/             # Data Dictionary, metodologia
├── requirements.txt
└── README.md
```

## Requisitos

- Python 3.12+
- [ojs-scrape](https://pypi.org/project/ojs-scrape/)

```bash
pip install -r requirements.txt
```

## Uso

```bash
# Coleta de um único periódico
ojs-scrape "https://periodicos.ufba.br/index.php/afroasia" \
  --from 2000 --until 2026 -o data/raw/afroasia

# Coleta em lote (script a ser criado)
python scripts/harvest_batch.py
```

## Referências

- Khanna, S., Ball, J., Alperin, J. P., & Willinsky, J. (2022). Recalibrating the Scope of Scholarly Publishing: A Modest Step in a Vast Decolonization Process. *Quantitative Science Studies*. DOI: [10.1162/qss_a_00228](https://doi.org/10.1162/qss_a_00228)

## Licença

MIT

Dados do PKP Beacon: CC0 1.0 Universal