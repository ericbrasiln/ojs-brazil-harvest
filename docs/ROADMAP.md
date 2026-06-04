# ROADMAP — OJS Brazil Harvest

Próximas etapas do projeto, com base nos resultados da amostra de validação (856K registros, 35% do potencial).

---

## Fase 1: Preparação para coleta completa

### 1.1 Adaptar scripts para máquina do LABHDUFBA

- [ ] Documentar dependências e setup (`pip install -r requirements.txt`)
- [ ] Testar `harvest_by_set.py` e `harvest_batch.py` no ambiente do Lab
- [ ] Verificar conectividade com os portais (a rede da UFBA pode ter restrições)
- [ ] Configurar execução em background (tmux/screen + nohup)

### 1.2 Implementar SSL bypass no script

- [ ] Adicionar opção `--no-verify-ssl` ao `harvest_by_set.py` e `harvest_batch.py`
- [ ] Alternativa: setar `PYTHONHTTPSVERIFY=0` antes do subprocesso
- [ ] Estimativa: +17 URLs recuperáveis, +5.000-10.000 registros

### 1.3 Melhorar captura de erros no `harvest_by_set.py`

- [ ] Aumentar limite de stderr capturado (atual: 500 chars, perde tipo de exceção)
- [ ] Classificar erros por tipo (HTTP status code, SSL, timeout, parse)
- [ ] Gerar relatório de erros automático ao final da coleta

---

## Fase 2: Coleta completa

**Onde:** máquina do LABHDUFBA (não na VPS)

### 2.1 Portais — coleta por set (538 portais)

- [ ] Rodar `harvest_by_set.py` sem `--sample` para todos os 538 portais
- [ ] Timeout 120s por set, delay 1.0s
- [ ] Usar `--resume` para tolerar interrupções
- [ ] Estimativa: ~20.000-30.000 sets, ~1.800.000 registros, ~50-80h

### 2.2 Periódicos isolados — coleta integral (1.439 URLs)

- [ ] Rodar `harvest_batch.py` sem `--sample` para os 1.439 isolados
- [ ] Timeout 300s, delay 1.0s
- [ ] Estimativa: ~600 URLs com sucesso, ~300.000 registros, ~8-12h

### 2.3 Retry — SSL bypass + timeout estendido

- [ ] Reprocessar URLs com SSL (17) e HTTP 102 (34) com bypass e timeout 600s
- [ ] Reprocessar sets com erro/timeout da Passada 2 (533 sets) com timeout 300s, delay 2s
- [ ] Estimativa: +80.000-175.000 registros

### 2.4 Portal da USP — abordagem dedicada

- [ ] Tentar delay 5-10s entre sets
- [ ] Agendar para madrugada (2h-6h BRT)
- [ ] Se rate limiting persistir: investigar proxy ou IP alternativo
- [ ] Potencial: ~50.000-100.000 registros

---

## Fase 3: Consolidação

### 3.1 Deduplicação

- [ ] Criar script de deduplicação por ISSN (periódicos que aparecem como URL isolada e dentro de portal)
- [ ] Deduplicar por DOI (artigos com mesmo DOI em fontes diferentes)
- [ ] Gerar dataset consolidado em `data/processed/ojs_brazil_consolidated.json`

### 3.2 Validação de qualidade

- [ ] Verificar completude dos campos: título, autor, data, DOI, ISSN
- [ ] Cruzar ISSNs com a lista do PKP Beacon
- [ ] Identificar registros com metadados mínimos (sem título ou sem data)
- [ ] Gerar relatório de qualidade em `docs/quality_report.md`

### 3.3 Enriquecimento

- [ ] Cruzar com base de dados Scielo/DOAJ para classificar indexação
- [ ] Adicionar versão do OJS (do PKP Beacon)
- [ ] Adicionar geolocalização das instituições (por domínio)

---

## Fase 4: Publicação

### 4.1 Dataset

- [ ] Formato: JSON + CSV (convertido a partir do JSON)
- [ ] Publicar em Zenodo ou Dataverse (com DOI)
- [ ] Metadados Dublin Core
- [ ] README com data dictionary

### 4.2 Relatório de infraestrutura

- [ ] Diagnóstico dos periódicos OJS brasileiros: versões, SSL, disponibilidade OAI-PMH
- [ ] Mapa de portais (538) e suas revistas constituintes
- [ ] Taxa de sucesso/falha por instituição

### 4.3 Artigo metodológico

- [ ] Descrever protocolo OAI-PMH em larga escala
- [ ] Lições aprendidas: rate limiting, SSL, XML inválido, paginação
- [ ] Comparar com outras iniciativas (CrossRef, Unpaywall, OpenAIRE)

---

## Cronograma estimado

| Fase | Duração estimada | Depende de |
|------|-----------------|------------|
| 1. Preparação | 1-2 semanas | Acesso ao Lab |
| 2.1 Portais por set | 3-5 dias (contínuo) | Setup no Lab |
| 2.2 Isolados | 1 dia | Setup no Lab |
| 2.3 Retry | 1-2 dias | Após 2.1+2.2 |
| 2.4 USP | 1 dia | Após 2.1 |
| 3. Consolidação | 2-3 semanas | Após Fase 2 |
| 4. Publicação | 2-4 semanas | Após Fase 3 |