# OJS Brazil Harvest

Coleta massiva de metadados de periódicos brasileiros hospedados em plataformas OJS (Open Journal Systems), usando o pacote [ojs-scrape](https://pypi.org/project/ojs-scrape/) e o dataset [PKP Beacon](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/OCZNVY) como fonte das URLs.

O projeto coleta **apenas metadados** (via protocolo OAI-PMH) — **sem download de PDFs**.

## Motivação

Mapear a produção acadêmica brasileira veiculada em periódicos OJS, extraindo dados estruturados (títulos, autores, palavras-chave, datas, DOIs) para análise bibliométrica e historiográfica.

## Status

**Amostra de validação concluída** — ~1,169K registros brutos (~925K únicos), 38% do potencial. Estratégia validada e script orquestrador pronto para coleta completa. Ver `docs/harvest_results.md`, `docs/ROADMAP.md` e `scripts/harvest_complete.py`.

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
│   ├── raw/            # Dados brutos coletados (JSON por periódico/set)
│   ├── processed/      # PKP Beacon filtrado, listas de URLs
│   └── logs/           # Logs de execução
├── scripts/            # Scripts de coleta e processamento
│   ├── harvest_batch.py      # Coleta integral (Passada 1)
│   └── harvest_by_set.py     # Coleta por set (Passada 2)
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

# Coleta em lote (periódicos isolados, sem set)
python scripts/harvest_batch.py --sample 400 --seed 4 \
  --skip-unresponsive --resume --timeout 180 --verbose

# Coleta por set (portais multi-revista)
python scripts/harvest_by_set.py --timeout 120 --resume --verbose
```

## Estratégia de coleta

1. **Portais → coleta por set primeiro** — descobrir sets via `ListSets`, coletar cada revista individualmente (77% de sucesso na amostra)
2. **Periódicos isolados → coleta integral** — funciona para ~42% dos casos
3. **Retry** — SSL bypass, timeout 600s, delay 2s
4. **Portais agressivos** — delay alto, horário de madrugada

Ver `docs/methodology.md` para detalhes.

## Documentação

- `docs/project_summary.md` — apresentação do projeto para o LABHDUFBA
- `docs/methodology.md` — metodologia e parâmetros de coleta
- `docs/harvest_results.md` — resultados consolidados da amostra
- `docs/error_report.md` — análise detalhada dos erros
- `docs/ROADMAP.md` — próximos passos e cronograma

## Referências

- Khanna, S., Ball, J., Alperin, J. P., & Willinsky, J. (2022). Recalibrating the Scope of Scholarly Publishing: A Modest Step in a Vast Decolonization Process. *Quantitative Science Studies*. DOI: [10.1162/qss_a_00228](https://doi.org/10.1162/qss_a_00228)

## Licença

MIT. Dados do PKP Beacon: CC0 1.0 Universal.