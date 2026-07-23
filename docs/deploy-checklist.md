# Checklist de Deploy — Coleta Completa no LABHDUFBA

## Pré-requisitos na máquina do LABHDUFBA

### 1. Ambiente Python

```bash
# Verificar Python 3.12+
python3 --version

# Instalar ojs-scrape (do fonte ou PyPI)
pip install ojs-scrape
# OU instalar da última versão do repo:
# pip install git+https://github.com/ericbrasiln/ojs-scrape.git

# Verificar instalação
ojs-scrape --help
# Confirmar que --no-verify-ssl aparece na ajuda
```

### 2. Clonar o repositório

```bash
git clone https://github.com/ericbrasiln/ojs-brazil-harvest.git
cd ojs-brazil-harvest
```

### 3. Verificar dataset de entrada

```bash
# Confirmar que o recorte brasileiro do PKP Beacon está presente
ls -la data/processed/ojs_brazil_pkp_beacon.json
# Deve ter ~4.7MB, 6.086 entradas

# Se for necessário reconstruir a partir do PKP Beacon v6:
python3 scripts/prepare_beacon_dataset.py --download
```

Ver `docs/data_provenance.md` para fonte, checksum e campos preservados.

### 4. Verificar espaço em disco

```bash
# Estimativa: 8-12 GB para ~2M registros
df -h .
# Recomendado: 20 GB livres
```

## Execução

### Coleta completa (recomendado)

```bash
# Executar todas as fases com resumabilidade
PYTHONUNBUFFERED=1 python3 -u scripts/harvest_complete.py --resume -v 2>&1 | tee data/logs/harvest_complete_$(date +%Y%m%d).log
```

### Por fases (controle granular)

```bash
# Fase 1: Portais por set (538 portais, ~1-3h)
PYTHONUNBUFFERED=1 python3 -u scripts/harvest_complete.py --phase 1 --resume -v

# Fase 2: Isolados (1.439 URLs, ~6-12h)
PYTHONUNBUFFERED=1 python3 -u scripts/harvest_complete.py --phase 2 --resume -v

# Fase 3: Retry de falhas (timeout 600s, ~2-4h)
PYTHONUNBUFFERED=1 python3 -u scripts/harvest_complete.py --phase 3 --resume -v
```

### USP dedicado (se a Fase 1 não cobrir)

```bash
# Rate limiting agressivo — executar de madrugada
PYTHONUNBUFFERED=1 python3 -u scripts/harvest_complete.py --phase 1 --resume --delay-usp 10 -v
```

## Monitoramento

### Verificar progresso

```bash
# Checkpoint
cat data/raw/harvest_complete_checkpoint.json | python3 -m json.tool

# Contar arquivos coletados
ls data/raw/*.json | wc -l

# Tamanho em disco
du -sh data/raw/

# Logs em tempo real
tail -f data/logs/harvest_complete_*.log
```

### Retomar após interrupção

```bash
# O --resume retoma do checkpoint automaticamente
PYTHONUNBUFFERED=1 python3 -u scripts/harvest_complete.py --resume -v
```

## Pós-coleta

### Consolidar resultados

```bash
# Contar registros totais
python3 -c "
import json, glob
total = 0
for f in glob.glob('data/raw/*.json'):
    if f.startswith('data/raw/phase') or f.startswith('data/raw/harvest_complete'):
        continue
    try:
        with open(f) as fh:
            d = json.load(fh)
            total += len(d) if isinstance(d, list) else 1
    except: pass
print(f'Total de registros: {total:,}')
"

# Verificar duplicações (por ISSN)
python3 -c "
import json, glob
from collections import Counter
issns = Counter()
for f in glob.glob('data/raw/*.json'):
    if 'phase' in f or 'harvest_complete' in f: continue
    try:
        with open(f) as fh:
            for a in json.load(fh):
                for i in a.get('identifiers', []):
                    if 'issn' in i.lower(): issns[i] += 1
    except: pass
dups = {k:v for k,v in issns.items() if v > 1}
print(f'ISSNs duplicados: {len(dups)}')
print(f'Overlapping rate: {sum(dups.values()) / max(len(issns),1) * 100:.1f}%')
"
```

## Estrutura de saída esperada

```
data/raw/
├── portal_de_periodicos_da_ufba__afroasia.json     # Set individual
├── portal_de_periodicos_da_ufba__diadorim.json
├── revista_abphe.json                               # Periódico isolado
├── ...
├── phase1_results.json                              # Resultados da Fase 1
├── phase2_results.json                              # Resultados da Fase 2
├── phase3_results.json                              # Resultados da Fase 3
└── harvest_complete_checkpoint.json                 # Checkpoint
data/logs/
└── harvest_complete_YYYYMMDD_HHMMSS.log
```