# Teste-Piloto OJS-Scrape: Resultados

**Data:** 2026-05-31  
**Dataset:** PKP Beacon v6 (87.170 instalações, 6.086 OJS Brasil)  
**Escopo:** 20 periódicos (3 por versão major do OJS), coleta metadata-only 2024-2025  

## Resumo Geral

| Status | Qtd | % |
|--------|-----|---|
| ✅ Sucesso | 4 | 20% |
| ⏱ Timeout (>90s) | 10 | 50% |
| ❌ Erro | 6 | 30% |

**Total de registros coletados nos sucessos:** 1.228 artigos

## Resultados por Versão

### ✅ Sucessos (4 periódicos)

| # | Versão | Periódico | Records | Tempo |
|---|--------|-----------|---------|-------|
| 02 | OJS 2.x (2.4.8.5) | Revistas da FACIT | 764 | 43.7s |
| 12 | OJS 3.3.x (3.3.0.21) | Revista Produção Online | 119 | 5.9s |
| 13 | OJS 3.3.x (3.3.0.15) | Diálogos Mediterrânicos | 41 | 4.2s |
| 17 | OJS 3.5.x (3.5.0.1) | FATEC-TQ | 304 | 36.9s |

### ⏱ Timeouts (10 periódicos — maioria portais multi-revista)

| # | Versão | Periódico | Observação |
|---|--------|-----------|------------|
| 00 | OJS 2.x (2.4.8.1) | UTFPR PERI | 142 sets, lento |
| 03 | OJS 3.0.x (3.0.2.0) | SBC | 1123 sets, portal grande |
| 05 | OJS 3.1.x (3.1.2.1) | UFMS | 488 sets, lento |
| 07 | OJS 3.1.x (3.1.2.1) | PUC Minas | XML com chars de controle inválidos |
| 09 | OJS 3.2.x (3.2.1.3) | PUC-SP | XML com chars de controle inválidos |
| 11 | OJS 3.3.x (3.3.0.21) | UFRJ | 1005 sets, lento |
| 14 | OJS 3.4.x (3.4.0.9) | UFES | 1205 sets, portal grande |
| 15 | OJS 3.4.x (3.4.0.8) | UFU | 1284 sets, portal grande |
| 16 | OJS 3.4.x (3.4.0.4) | USP | Portal enorme |
| 19 | OJS 3.5.x (3.5.0.1) | ANAP | 34 sets, mas lento |

### ❌ Erros (6 periódicos)

| # | Versão | Erro | Detalhe |
|---|--------|------|---------|
| 01 | OJS 2.x (2.4.8.2) | ConnectTimeout | IFSertãoPE — servidor não responde |
| 04 | OJS 3.0.x (3.0.2.0) | badVerb | UGB — endpoint OAI mal configurado |
| 06 | OJS 3.1.x (3.1.2.4) | 403 Forbidden | UFPel — bloqueia acesso OAI |
| 08 | OJS 3.2.x (3.2.1.1) | 500 Internal Server Error | UPF — erro no servidor OAI |
| 10 | OJS 3.2.x (3.2.1.3) | SSL cert expirado | UNIFENAS — certificado vencido |
| 18 | OJS 3.5.x (3.5.0.1) | 500 Internal Server Error | UEG — erro no servidor OAI |

## Diagnóstico Principal

### 1. Versão do OJS NÃO é o fator determinante
Periódicos funcionaram em OJS 2.x, 3.3.x e 3.5.x. Falhas ocorreram em todas as versões. O fator principal é a **infraestrutura do servidor** ( timeouts, SSL, bloqueios) e o **tamanho do repositório** (portais multi-revista com 1000+ sets).

### 2. Portais multi-revista são o gargalo
A maioria dos timeouts é de portais institucionais (USP, UFU, UFES, SBC) que agregam centenas de revistas sob um mesmo domínio. O endpoint `/index/oai` lista TODOS os registros do portal, gerando respostas enormes.

### 3. Caracteres XML inválidos
OJS 3.1.x e 3.2.x emitem ocasionalmente caracteres de controle proibidos pelo XML 1.0. O `ojs-scrape` trata isso removendo os caracteres antes do parse, mas a coleta fica mais lenta.

## Recomendações para Coleta em Escala

1. **Aumentar timeout para 300s+** em portais grandes
2. **Coletar set por set** em portais multi-revista (usar `--set` para cada revista)
3. **Retry com backoff** para erros transitórios (timeout, 500)
4. **Flag `--no-verify-ssl`** para certificados vencidos
5. **Filtrar endpoints não responsivos** (campo `unresponsive_endpoint` do dataset)
6. **Duas passadas**: primeira lista todos os sets, segunda coleta por set individual