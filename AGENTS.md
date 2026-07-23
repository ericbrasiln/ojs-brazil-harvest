# AGENTS.md — Guia para agentes automatizados

Este arquivo define como agentes de IA e automações devem trabalhar neste repositório.
As instruções são independentes de máquina, usuário e infraestrutura.

## Objetivo do projeto

Coletar metadados OAI-PMH de periódicos científicos brasileiros em plataformas OJS.
O universo inicial de URLs vem do recorte brasileiro do PKP Beacon v6.
A coleta usa o pacote `ojs-scrape` e não inclui PDFs ou textos completos.

## Diretório de trabalho

Use sempre a raiz do repositório como diretório de trabalho.
Use caminhos relativos ao repositório.
Não introduza caminhos absolutos, nomes de máquinas, usuários, endereços de rede ou credenciais em arquivos versionados.

## Requisitos

- Python 3.12 ou superior;
- espaço em disco compatível com uma coleta de vários gigabytes;
- acesso de rede aos endpoints OAI-PMH;
- permissão de escrita em `data/`.

Prepare um ambiente isolado:

Os exemplos usam shell POSIX e o comando `python3`.
Em outro sistema, use o launcher Python e o comando de ativação equivalentes.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Para desenvolvimento e testes:

```bash
python -m pip install -r requirements-dev.txt
```

## Regras obrigatórias

Antes de executar qualquer coleta:

1. confirme que está na raiz do repositório;
2. registre o commit com `git rev-parse HEAD`;
3. verifique `git status --short`;
4. confirme a versão do Python e as dependências;
5. verifique o espaço disponível em disco;
6. verifique se já existe uma coleta usando o mesmo diretório de saída;
7. localize e preserve checkpoints existentes;
8. execute primeiro o modo `--dry-run` em uma instalação nova.

Nunca:

- inicie duas coletas no mesmo diretório de saída;
- apague dados, logs ou checkpoints sem autorização explícita;
- versione arquivos de `data/raw/`, `data/derived/` ou logs, exceto placeholders `.gitkeep` já previstos;
- altere parâmetros metodológicos sem registrar e justificar a mudança;
- use scripts em `scripts/legacy/` para uma coleta nova;
- colete PDFs ou textos completos;
- faça push de resultados da coleta;
- apresente resultados que não foram produzidos e verificados pela execução real.

A coleta completa pode durar muitas horas.
Use um mecanismo de execução que preserve o processo e os logs mesmo se a sessão interativa terminar.
Não informe sucesso antes de o processo encerrar e os arquivos de saída serem verificados.

## Fonte de URLs

O arquivo versionado `data/processed/ojs_brazil_pkp_beacon.json` contém o recorte brasileiro do PKP Beacon v6.
Portais são identificados pela repetição de `oai_url`; não existe campo `n_journals`.

Para reconstruir o recorte a partir da fonte oficial:

```bash
python scripts/prepare_beacon_dataset.py --download
```

O arquivo global `data/raw/beacon.tab` não deve ser versionado.
Veja `docs/data_provenance.md`.

## Coleta

O orquestrador oficial é `scripts/harvest_complete.py`.
Ele executa:

1. portais, com coleta por set;
2. instalações isoladas, com coleta integral;
3. retry de falhas, com timeout ampliado e tratamento de SSL.

### Verificação sem coleta

```bash
python scripts/harvest_complete.py --dry-run
```

O `--dry-run` não deve criar ou modificar checkpoints e resultados.

### Iniciar ou retomar a coleta completa

```bash
python scripts/harvest_complete.py --resume --verbose
```

Use `--resume` como padrão para preservar o progresso.
Não remova `harvest_complete_checkpoint.json` para reiniciar uma execução sem autorização explícita.

### Executar uma fase específica

```bash
python scripts/harvest_complete.py --phase 1 --resume --verbose
```

Fases válidas: `1`, `2` e `3`.

### Parâmetros principais

- `--phase N`: executa apenas a fase indicada;
- `--resume`: retoma a partir do checkpoint;
- `--dry-run`: valida o plano sem coletar;
- `--timeout-set N`: timeout por set na fase 1;
- `--timeout-iso N`: timeout por instalação isolada na fase 2;
- `--timeout-retry N`: timeout na fase 3;
- `--delay N`: intervalo entre requisições;
- `--delay-usp N`: intervalo específico para portais da USP;
- `--skip-unresponsive` e `--no-skip-unresponsive`: controlam endpoints classificados como não responsivos.

Não reduza os delays para acelerar a coleta.
Respeite rate limiting e indisponibilidades dos servidores de origem.
Não aplique bypass de SSL fora da fase de retry prevista pelo orquestrador.

## Monitoramento e interrupção

Durante uma coleta:

- acompanhe a saída e os logs;
- verifique periodicamente o espaço em disco;
- preserve o PID ou identificador do processo;
- registre a fase e o checkpoint atuais ao relatar progresso.

Para interromper, use primeiro o mecanismo normal de encerramento do sistema ou da ferramenta de execução.
Evite encerramento forçado.
Depois da interrupção, confirme que o processo terminou e que o checkpoint continua legível.
Retome com `--resume`.

## Pós-processamento

Consolide a coleta somente após verificar os arquivos em `data/raw/`:

```bash
python scripts/process_harvest.py \
  --input-dir data/raw \
  --output-dir data/derived
```

O pipeline:

- valida arquivos e registros;
- deduplica por DOI, identificador OAI e URL canônica;
- preserva a proveniência;
- gera JSONL, CSV, manifesto, relatório de validação e tabela de decisões;
- usa título, primeiro autor e ano apenas para sugerir candidatos à revisão humana.

Após a execução, confira pelo menos:

- `data/derived/manifest.json`;
- `data/derived/validation_report.json`;
- `data/derived/duplicate_decisions.csv`;
- `data/derived/duplicate_candidates.json`.

Veja `docs/processing_pipeline.md` e `docs/data_dictionary.md`.

## Testes e verificações

Antes de propor mudanças no código:

```bash
python -m pytest -q
ruff check scripts/harvest_complete.py scripts/prepare_beacon_dataset.py scripts/process_harvest.py tests
python -m py_compile scripts/*.py scripts/legacy/*.py tests/test_*.py
python -m json.tool datapackage.json > /dev/null
```

A coleta completa não deve ser executada em CI.
Os testes usam fixtures pequenas e não dependem de dados brutos locais.

## Diretórios

- `data/raw/`: JSONs brutos e checkpoints locais, não versionados;
- `data/processed/`: fontes e listas processadas que podem ser versionadas;
- `data/derived/`: consolidação e relatórios locais, não versionados;
- `data/logs/`: logs locais, não versionados;
- `docs/`: metodologia, proveniência e documentação;
- `scripts/legacy/`: scripts históricos para auditoria, não para novas coletas.

## Relatório ao usuário

Ao concluir ou interromper uma execução, informe com dados verificados:

- commit executado;
- comando e argumentos;
- horário de início e término;
- fase concluída;
- processo ainda ativo, se houver;
- caminhos dos logs e checkpoints;
- arquivos produzidos;
- contagens reportadas pelos scripts;
- erros e limitações;
- próxima ação concreta.

Se a execução falhar, informe a falha real e preserve os artefatos necessários para diagnóstico e retomada.

## Git

- use `main` como branch base;
- trabalhe em branch própria;
- use mensagens de commit concisas;
- execute os testes antes do push;
- não faça force-push em `main`;
- não versione dados brutos, derivados, checkpoints ou logs.
