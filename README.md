# OJS Brazil Harvest

Coleta massiva de metadados de periódicos brasileiros hospedados em plataformas OJS (Open Journal Systems), usando o pacote [ojs-scrape](https://pypi.org/project/ojs-scrape/) e o dataset [PKP Beacon](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/OCZNVY) como fonte das URLs.

O projeto coleta **apenas metadados** (via protocolo OAI-PMH) — **sem download de PDFs**.

## Motivação

Mapear a produção acadêmica brasileira veiculada em periódicos OJS, extraindo dados estruturados (títulos, autores, palavras-chave, datas, DOIs) para análise bibliométrica e historiográfica.

## Status

**Amostra de validação concluída** — aproximadamente 1,169 milhão de registros brutos e 925 mil registros únicos estimados, equivalentes a cerca de 38% do potencial. Estratégia validada e script orquestrador preparado para a coleta completa. Ver `docs/harvest_results.md`, `docs/ROADMAP.md` e `scripts/harvest_complete.py`.

## Dataset PKP Beacon

- **Fonte:** Khanna, S.; Raoni, J.; Smecher, A.; Alperin, J.P.; Ball, J.; Willinsky, J. (2025). "Details of publications using software by the Public Knowledge Project". Harvard Dataverse, V6. DOI: [10.7910/DVN/OCZNVY](https://doi.org/10.7910/DVN/OCZNVY)
- **Licença:** CC0 1.0 Universal
- **Brasil:** 6.086 periódicos OJS, 5.861 com endpoint OAI-PMH responsivo, 2.445.213 registros potenciais

## Estrutura do projeto

```
ojs-brazil-harvest/
├── config/             # Listas de periódicos e configurações
│   └── journals_list.txt
├── data/
│   ├── raw/            # Dados brutos locais não versionados
│   ├── processed/      # Recorte brasileiro do PKP Beacon e listas de URLs
│   ├── derived/        # Saídas consolidadas locais não versionadas
│   └── logs/           # Logs locais não versionados
├── scripts/            # Scripts de produção e preparo de dados
│   ├── harvest_complete.py        # Orquestrador canônico da coleta
│   ├── prepare_beacon_dataset.py  # Reproduz o recorte brasileiro do PKP Beacon
│   ├── process_harvest.py         # Valida, deduplica e consolida a coleta
│   └── legacy/                  # Scripts históricos preservados para auditoria
├── docs/               # Documentação do projeto
│   ├── project_summary.md    # Apresentação para o LABHDUFBA
│   ├── methodology.md         # Metodologia de coleta
│   ├── harvest_results.md     # Resultados da amostra
│   ├── error_report.md        # Relatório de erros
│   ├── pilot_results.md       # Resultados do piloto
│   ├── ROADMAP.md             # Próximas etapas
│   ├── data_dictionary.pdf   # Dicionário de dados (PKP Beacon)
│   └── journals_location.pdf # Localização dos periódicos (PKP Beacon)
├── AGENTS.md           # Guia para agentes automatizados
├── datapackage.json
├── CITATION.cff
├── LICENSE
├── CONTRIBUTING.md
├── requirements.txt
└── README.md
```

## Requisitos

- Python 3.12+
- [ojs-scrape](https://pypi.org/project/ojs-scrape/) (incluído em `requirements.txt`)

```bash
pip install -r requirements.txt
```

## Uso

```bash
# Coleta de um único periódico
ojs-scrape "https://periodicos.ufba.br/index.php/afroasia" \
  --from 2000 --until 2026 -o data/raw/afroasia

# Coleta completa recomendada
python3 scripts/harvest_complete.py --resume -v

# Reproduzir o recorte brasileiro do PKP Beacon
python3 scripts/prepare_beacon_dataset.py --download

# Validar e consolidar saídas brutas da coleta
python3 scripts/process_harvest.py --input-dir data/raw --output-dir data/derived
```

## Estratégia de coleta

1. **Portais → coleta por set primeiro** — descobrir sets via `ListSets`, coletar cada revista individualmente (77% de sucesso na amostra)
2. **Periódicos isolados → coleta integral** — funciona para ~42% dos casos
3. **Retry** — SSL bypass, timeout 600s, delay 2s
4. **Portais agressivos** — delay alto, horário de madrugada

Ver `docs/methodology.md` para detalhes.

## Pós-coleta

`scripts/process_harvest.py` consolida os JSONs brutos em `data/derived/`.

O pipeline produz:

- `articles.jsonl` — registros consolidados com `_provenance`;
- `articles.csv` — versão tabular reduzida;
- `manifest.json` — checksums das entradas e resumo da execução;
- `validation_report.json` — registros inválidos e alertas;
- `duplicate_decisions.csv` — fusões automáticas por identificador forte;
- `duplicate_candidates.json` — possíveis duplicatas para revisão humana.

A deduplicação automática usa apenas DOI, identificador OAI e URL canônica.
Similaridade textual é registrada como candidata, sem fusão automática.

Ver `docs/processing_pipeline.md`.

## Princípios FAIR

### Findable

- `CITATION.cff` descreve como citar o repositório.
- `datapackage.json` registra metadados estruturados em padrão Frictionless Data.
- `docs/data_provenance.md` registra DOI, versão e checksum da fonte PKP Beacon.

### Accessible

- Os dados processados e scripts usam formatos abertos: JSON, JSONL, CSV e Markdown.
- O bruto global com `admin_email` não é versionado; o recorte brasileiro é reproduzível por script.

### Interoperable

- O pipeline preserva campos Dublin Core/OAI-PMH extraídos pelo `ojs-scrape`.
- `docs/data_dictionary.md` documenta campos do recorte Beacon e das saídas consolidadas.

### Reusable

- A licença do código é MIT.
- O recorte PKP Beacon deriva de fonte CC0.
- Campos `rights` dos artigos são preservados porque os direitos variam por periódico.
- `scripts/process_harvest.py` registra proveniência e decisões de deduplicação.

## Documentação

- `docs/project_summary.md` — apresentação do projeto para o LABHDUFBA
- `docs/methodology.md` — metodologia e parâmetros de coleta
- `docs/data_provenance.md` — proveniência e reconstrução do recorte PKP Beacon
- `docs/processing_pipeline.md` — validação, deduplicação e consolidação pós-coleta
- `docs/data_dictionary.md` — dicionário de dados dos arquivos processados e derivados
- `docs/script_inventory.md` — classificação dos scripts de produção e legado
- `docs/harvest_results.md` — resultados consolidados da amostra
- `docs/error_report.md` — análise detalhada dos erros
- `docs/ROADMAP.md` — próximos passos e cronograma

## Referências

- Khanna, S., Ball, J., Alperin, J. P., & Willinsky, J. (2022). Recalibrating the Scope of Scholarly Publishing: A Modest Step in a Vast Decolonization Process. *Quantitative Science Studies*. DOI: [10.1162/qss_a_00228](https://doi.org/10.1162/qss_a_00228)

## Uso de inteligência artificial

Em conformidade com o Art. 9º, inciso I, alínea "c", da Portaria CNPq nº 2.664/2026, declaramos que a ferramenta de inteligência artificial generativa **Hermes Agent** foi utilizada na organização do repositório, redação de documentação, elaboração de testes e apoio à implementação dos scripts de validação e consolidação.

As decisões metodológicas, a seleção das fontes, a execução final dos testes e a responsabilidade pelo conteúdo são do pesquisador responsável.

## Licença

Código: MIT.

Recorte PKP Beacon: CC0 1.0 Universal.

Metadados OAI-PMH coletados preservam declarações de direitos heterogêneas dos periódicos de origem.
