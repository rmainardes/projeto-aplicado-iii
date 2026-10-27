# Matriz de Rastreabilidade de Requisitos — AV04

Liga cada requisito da AV01 à decisão ou ao passo da arquitetura da AV02, ao componente que o
implementa, ao teste automatizado ou caso de teste (CT) que o prova e à evidência. Os requisitos **não**
atendidos aparecem com o motivo e o destino no roadmap. Os códigos de CT estão em
[`evidencias.md`](evidencias.md); os testes automatizados rodam com `./mvnw test` (154 testes Java) e
`node --test infra/fn-web/index.test.mjs` (8 testes da `fn-web`).

Legenda da situação: **Atendido** · **Parcial** (com o que falta) · **Fora do recorte** (D-018, roadmap) ·
**Fora do escopo** (definição da empresa).

## 1. Itens do roteiro da AV04

| Item do roteiro | Onde é atendido | Evidência |
| --- | --- | --- |
| Integrar AV01–AV03 numa Plataforma Web de Gestão | `web/` (login, processamento, histórico com indicadores, verificação pública) sobre o núcleo da AV03 (`nucleo/`) e o pipeline da AV02 (`funcoes/`) | CT-401 a CT-418 |
| Publicar na AWS, estritamente na Camada Gratuita | Stack SAM `infra/template.yaml`: só serviços na cota permanente ou nos créditos do plano gratuito, sem fatura (D-006, D-022, D-027) | CT-415, CT-416, §8 do relatório |
| Relatório Técnico Integrado (PDF) | `docs/av04/AV4_fonte.md` → `ferramentas/relatorio/gerar-relatorio.mjs` | PDF no AVA |
| Roteiro de deploy na nuvem | Relatório §6 e README ("Deploy do zero") | `infra/deploy.sh`, `infra/deploy-web.sh` |
| Matriz de Rastreabilidade de Requisitos | Este arquivo (relatório §10) | — |
| Código-fonte do front-end no GitHub público | `web/` | Link no cabeçalho do relatório |
| Scripts serverless de deploy | `infra/template.yaml`, `infra/deploy.sh`, `infra/deploy-web.sh`, `infra/smoke.sh`, `infra/smoke-web.sh` | CT-401 a CT-410 |
| Vídeo narrado no YouTube | Roteiro em `docs/av04/roteiro-video.md` | Link no cabeçalho do relatório |

## 2. Requisitos funcionais (RF)

| Req. (AV01) | Resumo | Arquitetura (AV02) | Componente | Teste / CT | Evidência | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| RF-01 | Entrada única pelo upload da planilha | E1–E2, DE-01/DE-02 | `FnApi` (`POST /uploads`, URL PUT pré-assinada), `S3UrlsPreassinadas`, `Processamento.jsx` | `FnApiTest`, `S3UrlsPreassinadasTest`; CT-401 | `respostas/cenario1-1-uploads.txt`, `tela/t11-1-enviando.jpg` | Atendido (PUT no lugar do POST, D-018) |
| RF-02 | Validação estrutural do arquivo | E5 | `LeitorPlanilhaPoi` (R01–R09) | `LeitorPlanilhaPoiInvalidosTest`, `PoiStrictTest`; CT-405 | `respostas/cenario3-2-estado.txt` | Atendido |
| RF-03, RF-04 | Saneamento e rejeição com motivo visível | E6, quarentena ≠ falha (§3.1.3) | `ErroValidacao` (linha, coluna, regra), estado `REJEITADA`, `Erros` em `Resultado.jsx` | `LeitorPlanilhaPoiInvalidosTest`, `FnIngestaoTest`; CT-405 | `tela/t11-5-rejeitada.jpg` | Atendido (registro no DynamoDB no lugar do prefixo `quarentena/`, D-018) |
| RF-05 | Persistência transacional do processamento | E9, §3.2 | `RepositorioCalibracoesDynamoDb` (`TransactWriteItems` + sentinela) | `RepositorioCalibracoesDynamoDbTest`, `RepositorioCalibracoesTest`; CT-408 | `respostas/cenario6-simultaneos.txt` | Atendido |
| RF-06, RF-07 | Cálculo de média e erro sistemático | E7 | `CalculadoraMetrologica` (`BigDecimal`, escala 10, `HALF_EVEN`) | `CalculadoraMetrologicaTest`, `ResultadoPontoTest`; CT-401 | `docs/av03/oraculo-planilhas.md` | Parcial: incerteza, *k* e *veff* (R-46 a R-50) no roadmap (D-018) |
| RF-08, RF-09 | Conformidade por ponto e parecer global | E8 | `ResultadoPonto` (`DENTRO_DA_TOLERANCIA`/`FORA_DA_TOLERANCIA`), `ResultadoCalibracao` (`APROVADO`/`REPROVADO`) | `ResultadoCalibracaoTest`; CT-401 | `tela/t11-3-aprovado.jpg`, `tela/t11-4-reprovado.jpg` | Parcial: bloqueio por padrão vencido fora do recorte |
| RF-10, RF-11 | Geração do certificado em PDF | E10, `fn-certificado` | `GeradorCertificado` (PDFBox 3, QR com ZXing), `FnCertificado` | `GeradorCertificadoTest`, `FnCertificadoTest`; CT-402 | `evidencias/certificado-ok-reprovado.pdf` | Atendido (layout simplificado, divergência de PV-14) |
| RF-12 | Aprovação pelo signatário antes da emissão | E11, RN-12 | — | — | — | Fora do recorte (D-018): emissão automática, prevista por configuração na D-010 |
| RF-13 | Emissão com hash e token de verificação | E12 | `FnCertificado` (`sha256Pdf`, `TOKEN#` com `SecureRandom`) | `FnCertificadoTest`; CT-403 | `respostas/cenario1-4-verificacao.txt` | Parcial: sem numeração sequencial (RN-14) e sem Object Lock |
| RF-14 | Trilha de auditoria | Tabela `auditoria` (§3.2.2) | Estados com instante e `sub` no item; logs só com id, SHA-256, tamanho e resultado | `FnIngestaoTest` (log); CT-409 | `respostas/log-fn-ingestao.txt` | Parcial: tabela `auditoria` somente de inserção (T19) no roadmap |
| RF-15 | Consulta de calibrações e download do certificado | Passo 10 | `GET /calibracoes`, `GET /calibracoes/{id}`, `GET /calibracoes/{id}/pdf`; `Historico.jsx` | `FnApiTest`; CT-402, CT-411 | `respostas/t12-historico.txt`, `tela/t12-2-lista.jpg` | Atendido (só os 20 mais recentes do usuário) |
| RF-16 | Verificação pública de autenticidade | Passo 10, D-015 | `GET /verificacao/{token}` (sem login), QR no PDF, `Verificacao.jsx` (conferência do hash do PDF no navegador) | `FnApiTest`; CT-403, CT-412 | `respostas/cenario1-4-verificacao.txt`; `tela/ct-412-qr-celular-4g.png` | Atendido |
| RF-19 | Exportação para o LightLab | — | — | — | — | Fora do escopo (DE-01) |
| RF-20 | Painel operacional | GSI2 | Indicadores do histórico (envios, emitidos, `APROVADO`, `REPROVADO`, rejeitadas, em andamento) | CT-411 | `tela/ct-411-1-historico-indicadores.png` | Parcial: indicadores sobre os envios do usuário, sem visão global por estado |
| RF-22 | Histórico de tendência por instrumento | GSI1 | — | — | — | Fora do recorte: sem cadastro de instrumento na planilha da AV03 |

## 3. Requisitos não funcionais (RNF)

| Req. (AV01) | Resumo | Arquitetura (AV02) | Componente | Teste / CT | Evidência | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| RNF-01, RNF-02 | Importar e calcular em até 5 s; PDF em até 3 s | §3.1.3 (desempenho) | Lambdas de 1 024 MB, leitura em memória (D-023) | CT-401 (*polling* até `EMITIDA`) | Duração no CloudWatch (vídeo) | Parcial: tempo com partida a frio não medido formalmente |
| RNF-03 | Integridade verificável do certificado | Hash + verificação pública | `sha256Pdf` gravado; conferência do arquivo em `Verificacao.jsx` | CT-403, CT-412 | `respostas/cenario1-4-verificacao.txt` | Atendido (sem Object Lock) |
| RNF-04 | Registro imutável | Object Lock + `auditoria` | Versionamento dos buckets; transições condicionais | `RepositorioCalibracoesTest` | `template.yaml` | Parcial: Object Lock e `auditoria` no roadmap |
| RNF-05 | Autenticação e sessão expirável | Cognito + autorizador JWT, token de 60 min | `UserPool`, `Api.Auth`, `cognito.js` (token só em memória) | CT-406, CT-418 | `respostas/cenario4-sem-token.txt`, `tela/t10-login.jpg` | Parcial: sem MFA/TOTP (D-018) |
| RNF-06 | Criptografia em trânsito e em repouso | §4.2 | SSE-S3, `DenyInsecureTransport`, HTTPS do API Gateway, HSTS da `fn-web` | CT-414 | `respostas/web-interface.txt` | Atendido (SSE-S3 em vez de KMS, D-009) |
| RNF-07 | Minimização de dados pessoais (LGPD) | §4.2.5, RN-35 | `sub` opaco nas tabelas; nome só no PDF (D-025); logs sem nome de arquivo nem `sub` | `FnIngestaoTest`, `FnCertificadoTest`; CT-409 | `respostas/log-fn-ingestao.txt` | Atendido (região `us-east-2`, ver §7 do relatório) |
| RNF-08, RNF-09 | Cálculo determinístico, versionado e com precisão | §3.2.4 | `BigDecimal`, valores gravados como texto (D-023) | `CalculadoraMetrologicaTest`, `MapeadorItemCalibracaoTest` | `docs/av03/oraculo-planilhas.md` | Atendido |
| RNF-10 | Recuperação de falhas | DLQ + alarmes | 2 novas tentativas, `FilaFalhas` (SQS) | `FnIngestaoTest` (exceção → DLQ) | `template.yaml` | Parcial: alarmes do CloudWatch não criados; budgets via SNS |
| RNF-12 | Sem infraestrutura local nem add-in | Serverless | Lambda, S3, DynamoDB, Cognito, HTTP API | CT-410 | URL da plataforma | Atendido |
| RNF-13 | Arquivos OOXML Strict | Contrato de entrada | R03 detecta Strict e rejeita com mensagem | `PoiStrictTest` | `docs/av03/evidencias/respostas/inv-R03-strict.txt` | Parcial: rejeita com orientação em vez de ler (limite do POI) |
| RNF-15 | Usabilidade em tablet e acessibilidade | — | Alvos de 44 px, contraste AA, layout de 768 px e de celular | CT-413 | `tela/t11-7-tablet-768.jpg`, `tela/t12-5-lista-736px.jpg` | Atendido |

## 4. Regras de negócio e definições da empresa

| Regra | Resumo | Componente | Teste / CT | Situação |
| --- | --- | --- | --- | --- |
| RN-12 | Aprovador diferente do executante | — | — | Fora do recorte (D-018) |
| RN-14 | Numeração anual sem lacuna | — | — | Fora do recorte (D-018) |
| RN-20 | Mesmo arquivo não gera dois certificados | Sentinela `HASH#` em transação | `RepositorioCalibracoesTest`, `RepositorioCalibracoesDynamoDbTest`; CT-404, CT-408 | Atendido |
| RN-22 | Original importado preservado | Bucket de entrada versionado, retenção de 5 anos | CT-416 | Atendido |
| RN-26 | Nada é digitado: o dado vem do arquivo | Upload + leitura da planilha | CT-401 | Atendido |
| RN-35 | Dados pessoais mínimos | `sub` opaco; nome só no PDF | CT-409 | Atendido |
| DE-02 | Upload dispara a função | Evento `s3:ObjectCreated` → `fn-ingestao` → destino → `fn-certificado` | CT-401 | Atendido |
| DE-03 | Autoria pela autenticação, sem ICP-Brasil | "Gerado por" lido do Cognito (D-025) | `FnCertificadoTest`; CT-402 | Atendido |
| DE-04 | Retenção de 5 anos com ciclo de vida | Regras de ciclo de vida (365 d → `GLACIER_IR`, expiração em 1 825 d) | CT-416 | Atendido |

## 5. Resumo

Do recorte da AV04 (D-018: passos 1–7 e 10 da AV02), todos os RF aparecem nesta matriz com componente,
teste e evidência. Ficam no roadmap, com motivo declarado: aprovação do signatário (RF-12, RN-12),
numeração sequencial e Object Lock (RF-13, RN-14, RNF-04), tabela de auditoria (RF-14), incerteza de
medição (RF-06/07), tendência por instrumento (RF-22) e MFA (RNF-05). Fora do escopo por definição da
empresa: LightLab (RF-19, DE-01) e ICP-Brasil (DE-03).
