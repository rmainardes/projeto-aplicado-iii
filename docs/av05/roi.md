# Estudo de ROI — tabelas geradas por `python ferramentas/roi.py`

## Tempo por certificado, etapa a etapa (AV01 §1.1.4)

| Etapa | Atividade | Manual (min) | Automatizado (min) | O que muda |
| --- | --- | ---: | ---: | --- |
| P-06 | Gerar o relatório da MMC no Excel | 1 | 1 | mantida: é a origem da planilha |
| P-07 | Digitar metrologista, MMC e fornecedor | 2 | 0 | autoria pela autenticação do usuário |
| P-08 | Salvar o relatório como .xlsx | 1 | 1 | mantida: salvar no formato do contrato |
| P-09 | Transpor os 28 valores para a planilha de cálculo | 10 | 0 | leitura automática (ingestão) |
| P-10 | Informar o padrão por código | 1 | 1 | mantida: fora do escopo do MVP |
| P-11 | Digitar temperatura e observações | 2 | 2 | mantida: fora do escopo do MVP |
| P-12 | Cálculo nas fórmulas do Excel | 0 | 0 | motor validado contra o oráculo |
| P-13 | Conferir valores do certificado contra a MMC | 10 | 1 | 15 regras validadas pelo sistema; revisão da tela |
| P-14 | Selecionar o signatário pelo índice | 1 | 0 | autoria pela autenticação |
| P-15 | Revisar e assinar o certificado | 15 | 5 | revisão de layout fixo, sem transcrição a conferir |
| P-16 | Exportar o PDF | 3 | 0 | PDF gerado automaticamente |
| P-17 | Lançar resultado no LightLab | 5 | 5 | mantida: sem integração (D-002) |
| P-18 | Arquivar planilha e PDF | 2 | 0 | armazenado com retenção de 5 anos |
| Novo | Enviar a planilha e ler o resultado | 0 | 1 | upload na interface |
| **Total** | **Ciclo do certificado** | **53** | **17** | **−68%** |
| | Bloco absorvido pelo sistema (transcrição, conferência, cálculo, PDF, arquivo) | 28 | 2 | −93% |

## Premissas operacionais (cenário base)

| Premissa | Valor | Origem |
| --- | --- | --- |
| Volume de certificados/ano (V) | 137 | AV01: certificado nº 00091 em 26/08/2026, extrapolado [PREMISSA] |
| Tempo manual por certificado | 53 min | AV01, soma de P-06 a P-18 [PREMISSA] |
| Tempo automatizado por certificado | 17 min | tabela acima; processamento da máquina < 1 s (§6) |
| Custo da hora técnica (C) | R$ 75,00 | AV01, metrologista com encargos [PREMISSA] |
| Retrabalho (reemissões) antes → depois | 10,0% → 2,0% | AV01 [PREMISSA]; residual: erro de medição |
| Custo de uma reemissão | R$ 99,38 | 1,5 × tempo manual × C (AV01) |
| Infraestrutura em nuvem | R$ 0,00/ano | Free Tier/plano gratuito, US$ 0,00 no Cost Explorer (CT-415); versão local sem servidor |
| Manutenção e suporte | R$ 1.440,00/ano | 2 h/mês × R$ 60,00 [PREMISSA] |

## Investimento

| Item | Cálculo | Valor |
| --- | --- | ---: |
| Desenvolvimento (AV02–AV05) | 180 h × R$ 60,00 | R$ 10.800,00 |
| Validação do software pelo laboratório (ISO/IEC 17025 §7.11.2) | 16 h × R$ 75,00 | R$ 1.200,00 |
| Implantação e treinamento | 10 h × R$ 75,00 | R$ 750,00 |
| Infraestrutura (nuvem Free Tier / computador existente) | — | R$ 0,00 |
| **Investimento econômico (como se contratado)** | | **R$ 12.750,00** |
| **Desembolso efetivo da Schulz** (desenvolvimento feito na parceria acadêmica) | | **R$ 1.950,00** |

## Tabela comparativa: fluxo manual × automatizado (cenário base, por ano)

| Indicador | Manual | Automatizado | Diferença |
| --- | ---: | ---: | ---: |
| Horas técnicas | 121,0 h | 38,8 h | **82,2 h economizadas** |
| Custo das horas técnicas | R$ 9.076,25 | R$ 2.911,25 | R$ 6.165,00 |
| Reemissões/ano | 13,7 | 2,7 | 11,0 |
| Custo do retrabalho | R$ 1.361,44 | R$ 272,29 | R$ 1.089,15 |
| Infraestrutura em nuvem | — | R$ 0,00 | — |
| **Economia Bruta Anual (OPEX Saved)** | | | **R$ 7.254,15** |
| (−) Manutenção e suporte | | R$ 1.440,00 | −R$ 1.440,00 |
| **Economia Líquida Anual** | | | **R$ 5.814,15** |

## ROI e payback (cenário base)

ROI % = (Economia Líquida − Investimento) / Investimento × 100, com a economia líquida acumulada no horizonte.

| Visão do investimento | Investimento | ROI 12 meses | ROI 36 meses | ROI 60 meses | Payback |
| --- | ---: | ---: | ---: | ---: | ---: |
| Econômico (contratado) | R$ 12.750,00 | −54,4% | 36,8% | 128,0% | 26,3 meses |
| Desembolso efetivo da Schulz | R$ 1.950,00 | 198,2% | 794,5% | 1.390,8% | 4,0 meses |

Memória de cálculo (visão econômica, 12 meses): (R$ 5.814,15 − R$ 12.750,00) / R$ 12.750,00 × 100 = −54,4%; payback = R$ 12.750,00 / (R$ 5.814,15 / 12) = 26,3 meses.

## Sensibilidade

| Cenário | Certificados/ano | Custo-hora | Min. manual → automatizado | Retrabalho | Economia líquida/ano | Payback (econômico) | ROI 36 m (econômico) | Payback (desembolso) |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |
| Conservador | 100 | R$ 60,00 | 53 → 22 | 5,0% → 2,0% | R$ 1.898,50 | 80,6 meses | −55,3% | 12,3 meses |
| Base | 137 | R$ 75,00 | 53 → 17 | 10,0% → 2,0% | R$ 5.814,15 | 26,3 meses | 36,8% | 4,0 meses |
| Otimista (outras famílias de instrumentos) | 274 | R$ 90,00 | 53 → 17 | 10,0% → 1,0% | R$ 16.296,70 | 9,4 meses | 283,5% | 1,4 meses |

Ponto de equilíbrio: com as demais premissas do cenário base, o investimento econômico se paga em 12 meses a partir de **268 certificados/ano**, e em 24 meses a partir de **148**.
