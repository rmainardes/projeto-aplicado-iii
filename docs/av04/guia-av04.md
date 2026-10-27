# Guia da AV04 — Plataforma Web e deploy em nuvem

Schulz S.A. · Automação da emissão de certificados de calibração · Prazo: **qui 29/10/2026**

Este guia divide a AV04 em tarefas pequenas, uma por sessão do Claude Code (CLI). Cada tarefa traz
o próprio contexto mínimo, então nenhuma sessão precisa da conversa anterior: o estado fica no
repositório (guia, `docs/decisoes.md`, código e commits), não no chat.

---

## 0. Como usar

**Fluxo por tarefa (uma sessão por tarefa)**

1. Abra o Claude Code na raiz do repositório e rode `/tarefa Txx` (ou cole: "Leia o
   `docs/av04/guia-av04.md` e execute a Txx").
2. A sessão lê o `CLAUDE.md` (automático), a seção da tarefa e **só** os arquivos de **Contexto**.
3. Tarefas grandes (T07, T08, T11) começam no *plan mode*: plano curto, você aprova, depois executa.
4. Ao terminar: testes verdes, **Aceite** conferido, nota de conclusão na tarefa, linha no Registro
   de progresso, trecho do relatório em `docs/av04/AV4_fonte.md` (seção indicada em **Relatório**)
   e commit.
5. `/clear` e próxima tarefa.

**Modo de cada tarefa** (troque o ícone se quiser outro modo; o prazo pesa a favor do 🛠)

- 🧑‍🏫 **Instrutivo** — você escreve; o Claude explica, faz no máximo 3 perguntas e revisa o
  `git diff` com no máximo 3 pontos (✅ certo, 🔧 corrigir, 📚 aprender). Reservado para o que
  tem valor de aprendizado ou de defesa na banca.
- 🛠 **Delegado** — o Claude escreve; você revisa o diff antes do commit e pergunta o que não
  entender. Para boilerplate, configuração e trabalho braçal.

**Legenda:** ★ caminho mínimo · ◇ reforço (só se sobrar tempo) · 🔒 segurança/LGPD (não pular)

**Cronograma (uma pessoa, dias úteis só à noite)**

| Dia         | Tarefas         | Marco                                                          |
| ----------- | --------------- | -------------------------------------------------------------- |
| Sáb 24/10   | T00 a T05       | Decisões, conta AWS pronta, projeto multimódulo, persistência  |
| Dom 25/10   | T06 a T09       | **Pipeline funcionando na nuvem via `curl`** (marco crítico)   |
| Seg 26/10   | T10 e T11       | Login e processamento na tela, rodando local contra a nuvem    |
| Ter 27/10   | T12 a T14       | Histórico, verificação pública e SPA publicada no CloudFront   |
| Qua 28/10   | T15 e T16       | Evidências, matriz de rastreabilidade e vídeo no YouTube       |
| Qui 29/10   | T17 e T18       | Relatório em PDF, revisão e envio no AVA                       |

**Ajuste de 25/10:** a T02 ficou bloqueada no sábado e foi reaberta no domingo. Ela vem antes da
T06, e todo comando AWS usa `--profile pa3 --region us-east-2` (D-022).

**Se atrasar, corte nesta ordem:** T19 (auditoria) → QR no PDF (fica só a URL impressa) →
T12 (histórico) → layout do PDF. Não se corta: Cognito, pipeline por evento, vídeo, matriz.

---

## 1. O que o roteiro pede (e o que falta nele)

| Item do roteiro                         | O que exige                                                                  | Onde está    |
| --------------------------------------- | ---------------------------------------------------------------------------- | ------------ |
| Objetivo                                | Integrar AV01–AV03 numa Plataforma Web **ou** app mobile; publicar na AWS, estritamente no Free Tier | Todo o guia |
| 1. Relatório Técnico Integrado (PDF)    | Plataforma documentada, **roteiro de deploy na AWS**, **Matriz de Rastreabilidade de Requisitos** | T15, T17 |
| 2. Repositório (GitHub público)         | Código do front-end e **scripts serverless de deploy**                       | T08, T14, T18 |
| 3. Evidência em nuvem                   | **Vídeo no YouTube com narração**, app rodando na nuvem, todos os passos; link no PDF | T16 |
| Cabeçalho obrigatório                   | UC, docente, integrantes (nome completo), link do GitHub                    | T17          |
| Seções 3 e 4 do roteiro                 | **Não constam no PDF** (pula da 2 para a 5) — perguntar (T00)                | T00          |

**Orientação do professor na AV02 (continua valendo):** upload da planilha no storage dispara a
função serverless que lê o Excel, grava no banco e gera o PDF; sem ICP-Brasil, só **autenticação
de usuário** no PDF; retenção de 5 anos com regras de ciclo de vida; custo R$ 0,00.

**Recorte desta entrega (D-018):** passos 1–7 e 10 do fluxo da AV02 (§1.1), com emissão automática
(a D-010 já previa fundir minuta e emissão por configuração). Ficam no roadmap: aprovação do
signatário e RN-12 (passo 8), numeração sequencial e Object Lock (passo 9), TOTP no Cognito,
incerteza/k/veff (R-46 a R-50).

---

## 2. Arquitetura alvo

```
 Navegador (React, CloudFront + S3 privado)
   │ 1. login ──────────────► Cognito (USER_PASSWORD_AUTH, sem segredo de cliente)
   │ 2. POST /uploads (JWT) ─► API Gateway HTTP API ─► fn-api ──► URL pré-assinada (PUT, 5 min, 5 MB)
   │ 3. PUT planilha ───────► S3 entrada  uploads/<sub>/<uploadId>.xlsx
   │                              │ 4. s3:ObjectCreated (assíncrono)
   │                              ▼
   │                         fn-ingestao ── núcleo AV03 (Java puro) ──► DynamoDB calibracoes
   │                              │ 6. destino de sucesso          (HASH# sentinela = RN-20)
   │                              ▼                     falha ──► SQS DLQ
   │                         fn-certificado ── PDFBox ──► S3 certificados  certificados/<id>.pdf
   │ 10. GET /calibracoes/{id}, /pdf (URL pré-assinada), GET /verificacao/{token} (público)
```

**Código (D-017):** Maven multimódulo — `nucleo/` (domínio + ingestão, Java puro, D-012),
`app-local/` (Spring Boot da AV03, segue rodando localmente), `funcoes/` (handlers Lambda e
adaptadores AWS), `web/` (React + Vite), `infra/` (template SAM e scripts de deploy).

---

## Fase 0 — Preparação e decisões

### [x] T00 · Perguntar ao professor o que falta no roteiro ★ 🧑‍🏫

**Contexto.** Seção 1 deste guia. PDF `~/Faculdade/Projeto aplicado III/Entrega AV4 - Plataforma Web.pdf`.

**Faça.** Mande hoje (sáb) uma mensagem curta e fechada. Sugestão:

> Professor, no roteiro da AV04 o documento passa da seção 2 para a 5. As seções 3 e 4 trazem
> requisitos ou critérios de avaliação? Se sim, pode enviá-las? Duas confirmações: (1) seguiremos
> com a Plataforma Web (não mobile), com uma página pública de verificação do certificado por QR
> Code acessível pelo celular; (2) o vídeo pode ser publicado no YouTube como "não listado"?

Não espere a resposta: até ela chegar, as premissas são as da seção 1 e viram `[PREMISSA]` no
relatório.

**Aceite.** Mensagem enviada; data registrada na nota desta tarefa.

> **Concluída em 24/10.** Perguntas enviadas ao professor em 24/10/2026; sem resposta até aqui. Na AV03 o professor já enviou arquivo com numeração de seções errada, confirmado por mensagem, sem conteúdo nas seções faltantes; por isso seguimos sem as seções 3 e 4 e as premissas da seção 1 viram `[PREMISSA]` no relatório (AV4_fonte §12).

---

### [x] T01 · Registrar as decisões D-015 a D-020 ★ 🧑‍🏫

**Contexto.** `docs/decisoes.md` (formato), seções 1 e 2 deste guia, `docs/av02/AV2_Grupo39_fonte.md`
§1.2 e §3.2.

**Conceito.** Como na AV03: decisão escrita antes do código. Cada uma em 5–8 linhas, com data,
origem "autor" e status.

**Faça.** Escreva, no formato existente:

- **D-015 · Plataforma Web, não mobile.** Público principal é o engenheiro no laboratório (upload,
  revisão, PDF). A "validação por QR Code" do roteiro entra como página pública responsiva,
  aberta pela câmera do celular a partir do QR impresso no PDF (RF-16 da AV01).
- **D-016 · Hospedagem da SPA: S3 privado + CloudFront com OAC.** A AV02 não definiu onde fica a
  interface. CloudFront tem plano gratuito (1 milhão de requisições e 100 GB/mês, sem excedente; conferido em 24/10) e dá HTTPS,
  necessário para uma tela de login. Amplify Hosting descartado (cota de 12 meses, programa antigo).
  Confirme a cota na página oficial de preços do CloudFront e cite URL e data.
- **D-017 · Maven multimódulo.** O Lambda não pode carregar o Spring (D-012). Separar `nucleo`,
  `app-local` e `funcoes` é o que prova a D-012 na prática: o mesmo núcleo, duas pontas.
- **D-018 · Recorte da AV04** (seção 1 deste guia) e divergências declaradas em relação à AV02:
  sem TOTP; sem aprovação/RN-12; sem Object Lock; URL pré-assinada **PUT** com `Content-Length`
  assinado no lugar do formulário POST (o SDK Java v2 não gera POST pré-assinado — confirme na T07);
  o arquivo inválido não é movido para `quarentena/`: a rejeição fica registrada no DynamoDB
  com os erros (linha, coluna, regra), visível na tela.
- **D-019 · Bibliotecas externas** (aviso explícito, como na AV03): `aws-lambda-java-core`,
  `aws-lambda-java-events`, AWS SDK for Java v2 (`s3`, `dynamodb`), Apache PDFBox 3, ZXing `core`
  (◇, QR), React + Vite (front-end), AWS SAM CLI (deploy). Verifique as versões no Maven Central e
  no npm no dia; não use versão de memória.
- **D-020 · Runtime `java21`, bytecode 17.** O `java17` gerenciado roda em Amazon Linux 2, cujo
  fim de vida foi 30/06/2026; a AWS recomenda migrar para runtime em AL2023. Compilar com
  `release 17` mantém a D-011 e roda no `java21` (AL2023, suporte até 2029). Fonte: página
  *Lambda runtimes* da AWS (consulte e cite a data).

**Aceite.** Seis decisões no `decisoes.md`, cada uma apontando o requisito ou a decisão anterior
que motiva.

> **Concluída em 24/10.** D-015 a D-020 em `docs/decisoes.md`. Correções ao guia, conferidas nas fontes oficiais: o plano gratuito do CloudFront é 1 milhão de requisições e 100 GB/mês (não 1 TB e 10 milhões); o fim de vida de 30/06/2026 é do Amazon Linux 2, o `java17` vai até 30/06/2027 e existe `java17.al2023`; `java21` e `java25` vão até 30/06/2029. Pendência: confirmar na T10 se o plano gratuito do CloudFront aceita OAC. Escrita delegada pelo Rodrigo por prazo; conteúdo e escolhas (java21, descartes da D-016, enquadramento da D-018) são dele.

**Relatório.** §2 (Decisões da entrega).

---

### [x] T02 · Preparar a conta AWS e as ferramentas 🔒 ★ 🛠

**Contexto.** D-006, D-022 e AV02 §2.2 (plano de monitoramento A-1/A-2).

**Faça.**

- Conta dedicada no plano gratuito (D-006), região **`us-east-2`** (D-022). Confira o saldo e a
  validade dos créditos no painel *Cost and usage* do console.
- Login humano: o login é o AWS Builder ID. Ative o MFA em https://settings.aws.com → *Manage
  security and sign-in* → *Security* → *Register device*. Nesta conta não há menu *Security
  credentials* (D-022).
- Acesso programático: em *IAM → Users*, crie `pa3-deploy` sem acesso ao console, com
  `AdministratorAccess`, e gere uma access key (*Command Line Interface*). Ative MFA no usuário se o
  console oferecer. `aws configure --profile pa3` com a chave nova, região `us-east-2`, saída `json`
  (sobrescreve a chave da conta suspensa; nunca no repositório).
- Budgets na conta nova: *Zero spend budget* (A-1) e orçamento de US$ 1/mês (A-2), alerta por
  e-mail. Os prints de 24/10 são da conta suspensa: substitua-os.
- Instale e confira: AWS CLI v2, AWS SAM CLI, Node LTS (`node -v`, `npm -v`), JDK 21.
- `.gitignore` (já cobre `.env*`, `node_modules/`, `dist/`): acrescente `.aws-sam/`; decida se o
  `samconfig.toml` entra (só se não tiver nada sensível); o `.claude/` está ignorado inteiro — para
  versionar o comando `/tarefa`, troque a linha `.claude/` por `.claude/*` e `!.claude/commands/`.

**Aceite.** `aws sts get-caller-identity --profile pa3` responde com o usuário `pa3-deploy`;
`aws dynamodb list-tables --profile pa3` responde em `us-east-2` (sem *explicit deny*);
`sam --version` responde; print dos dois budgets da conta nova (sem número de conta visível) em
`docs/av04/evidencias/tela/`.

> **Bloqueada em 24/10.** Conta original suspensa; SCP só liberava `us-east-2`; MFA não configurado. Concluído naquela data e ainda válido: CLI/SAM/Node/JDK conferidos e `.gitignore`.
>
> **Reaberta em 25/10.** Conta nova no plano gratuito (US$ 100, até 24/04/2027). Conferido no console: mesma SCP (só `us-east-2`), e em `us-east-2` abrem Lambda, S3, DynamoDB, Cognito, API Gateway e CloudFormation; CloudFront e Budgets abrem. Região decidida na D-022. MFA do AWS Builder ID ativo em 25/10 (WebAuthn e TOTP; print tarjado em `docs/av04/evidencias/tela/mfa-tarjado.png`). Falta: usuário `pa3-deploy` e perfil `pa3`, budgets e prints, Aceite.
>
> **Concluída em 25/10.** Aceite: `sts get-caller-identity` → `user/pa3-deploy`; `dynamodb list-tables` em `us-east-2` → `{"TableNames": []}`, sem *explicit deny*; SAM CLI 1.170.0. Budgets A-1 (zero spend, real > US$ 0,01) e A-2 (US$ 1/mês: real > 85% e > 100%, previsto > 100%) na conta nova. Desvio: o e-mail direto do Budgets não pode ser verificado (`notifications-contacts` negado pela SCP); os quatro alertas publicam no tópico SNS `pa3-budgets-alertas` (`us-east-2`), com assinatura por e-mail confirmada (D-022). `pa3-deploy` não tem senha de console; sem MFA, porque só usa access key (mitigação: chave só no perfil local `pa3`, desativar após a nota). Prints: `mfa-tarjado.png` e `budgets-conta-nova.png`; `Budget.png`, `Budget zero-spend.png` e `User.png` são da conta suspensa e saem do repositório.

**Relatório.** §6 (Roteiro de deploy — pré-requisitos) e §8 (Custo).

---

## Fase 1 — Back-end preparado para a nuvem

### [x] T03 · Converter para Maven multimódulo ★ 🛠

**Contexto.** `pom.xml`, `README.md` (Estrutura), D-012, D-017.

**Faça.**

- POM pai (`packaging pom`, mantendo `spring-boot-starter-parent` como pai, para herdar a gestão de
  versões) com os módulos `nucleo`, `app-local`, `funcoes`.
- `nucleo/`: `dominio/` e `ingestao/` e os testes deles; só depende do POI. As planilhas de teste
  vão para `nucleo/src/test/resources/planilhas/`.
- `app-local/`: `aplicacao/`, `web/`, `static/` e os testes Spring. Se os testes da web leem as
  planilhas, use o *test-jar* do `nucleo` ou caminho relativo — decida e explique no commit.
- Leve o cálculo de SHA-256 em streaming (`Medidor`, hoje no `ProcessamentoService`) para o
  `nucleo`: a `fn-ingestao` vai precisar dele.
- `git mv` (não copiar e apagar), para manter o histórico dos arquivos.
- Atualize o `.gitignore` (caminhos de `planilhas/` e `local/` mudaram) e o README.

**Aceite.** `./mvnw test` na raiz: **71 testes, 0 falhas, 1 pulado** (mesmo número da AV03);
`./mvnw -pl app-local spring-boot:run` abre a tela da AV03 e processa `ok-reprovado.xlsx`;
`grep -r "springframework" nucleo/` vazio.

> **Concluída em 24/10.** Módulos `nucleo`, `app-local` e `funcoes` (este ainda sem código, com `nucleo` como dependência). `git mv` em tudo; `./mvnw test`: 71 testes (56 + 15), 0 falhas, 1 pulado num clone limpo (na máquina do autor o `strict-real.xlsx` local existe e o teste roda). Os testes do `app-local` leem as planilhas pelo *test-jar* do `nucleo` (uma única cópia). `Medidor` foi para `nucleo/ingestao` sem log (o `ProcessamentoService` loga). `spring-boot-maven-plugin` com `skip` no pai e `skip=false` no `app-local`, para `-pl app-local -am spring-boot:run` funcionar.

**Relatório.** §3 (Arquitetura implementada): estrutura de módulos e prova da D-012.

---

### [x] T04 · Modelo de persistência e idempotência (RN-20) ★ 🧑‍🏫 🔒

> **Concluída em 24/10.** Modo mudou de instrutivo para delegado a pedido do Rodrigo, que decidiu as três perguntas (mesmo id; `DUPLICADA` com ponteiro; rejeitada grava a sentinela e o reenvio é curto-circuitado pelo hash). Porta `RepositorioCalibracoes` em `nucleo/persistencia`, adaptador em memória e 11 testes; `./mvnw test`: 82 testes (67 + 15), 0 falhas. `modelo-dados.md` e D-021. Pendente de validação na T06: condição do `TransactWriteItems` no DynamoDB real.

**Contexto.** AV02 §3.2 (tabela única `PK`/`SK`, sentinelas `HASH#`/`TOKEN#`, GSI2), D-007, D-014,
nota da T17 no `docs/av03/guia-av03.md`.

**Conceito.** No DynamoDB não há `UNIQUE`: a unicidade é um item-sentinela gravado **na mesma
transação** (`TransactWriteItems`) que a calibração, com `attribute_not_exists(PK)`. Se o hash já
existe, a transação inteira falha e nada fica pela metade. Checar antes com `GetItem` não basta:
dois envios simultâneos passariam os dois (corrida).

**Perguntas a responder antes de codar:**

1. O `uploadId` (gerado pela `fn-api` antes do envio) e o id da calibração são o mesmo
   identificador? O que a tela consulta enquanto o arquivo ainda está sendo processado?
2. Reenvio do mesmo arquivo: devolver a calibração original, criar um registro `DUPLICADO`
   apontando para ela, ou recusar? O que o usuário vê?
3. Planilha rejeitada: grava o hash como sentinela? (Se gravar, a versão corrigida é outro arquivo
   e outro hash; a mesma planilha errada reenviada cairia em quê?)

**Faça.**

- Porta `RepositorioCalibracoes` no `nucleo` (pacote novo, Java puro), com registro de calibração
  processada, rejeitada (com a lista de `ErroValidacao`) e emitida.
- Desenho dos itens (PK/SK, atributos, estados `PROCESSANDO`/`REJEITADA`/`PROCESSADA`/`EMITIDA`,
  quem grava cada um) numa tabela em `docs/av04/modelo-dados.md`, comparada com a AV02.
- Adaptador em memória para teste (no `nucleo/src/test`) e testes: mesmo hash duas vezes; hash
  diferente; rejeitada sem dado de negócio.
- 🔒 Nunca gravar nome do arquivo nem conteúdo bruto; usuário só pelo `sub` do Cognito (opaco);
  o nome de exibição vai só para o PDF (AV02 §4.3, RN-35).

**Aceite.** Testes verdes; `modelo-dados.md` com as respostas às 3 perguntas.

**Relatório.** §4 (Persistência e idempotência).

---

### [x] T05 · Geração do certificado em PDF ★ 🛠 (layout) / 🧑‍🏫 (conteúdo)

**Contexto.** Certificado real `Cal_1_5896_1_0 (1).pdf` (fora do Git, **só para olhar a
estrutura**), `ResultadoCalibracao`, D-003, PV-14.

**Faça.**

- Classe `GeradorCertificado` no `funcoes` com Apache PDFBox 3 (D-019), recebendo os dados
  calculados + metadados e devolvendo `byte[]`.
- Conteúdo mínimo: identificador, data/hora (America/Sao_Paulo), SHA-256 da planilha de origem,
  **"Gerado por: <usuário autenticado>"** (orientação do professor), tabela de pontos com leituras,
  referência, média, erro, LEA e status (enums literais), parecer em destaque, token de verificação
  e URL `https://<cloudfront>/verificar/<token>`.
- ◇ QR Code da URL com ZXing `core` (desenhar a matriz como retângulos no PDFBox, sem `javase`).
- Rodapé: "Documento gerado por PoC acadêmica (UniSENAI, Projeto Aplicado III) — sem validade
  metrológica". 🔒 Nenhum dado real da Schulz no teste.
- Layout simplificado, não o da Schulz: declarar como divergência de PV-14.

**Aceite.** Teste gera o PDF de `ok-reprovado.xlsx` e confere, com `PDFTextStripper`, o parecer,
o hash e um enum; PDF de exemplo salvo em `docs/av04/evidencias/` e aberto por você.

**Relatório.** §5 (Certificado gerado), com print.

> **Concluída em 24/10.** `GeradorCertificado` + `DadosCertificado` em `funcoes`
> (PDFBox 3.0.8, ZXing `core` 3.5.4, QR desenhado como retângulos). 85 testes verdes (3 novos).
> PDF de exemplo: `docs/av04/evidencias/certificado-ok-reprovado.pdf` (planilha sintética).
> Divergência de PV-14: layout simplificado, sem o formato da Schulz. PDF aberto e conferido pelo Rodrigo; print em `evidencias/tela/relatorio-pdf.png`.

---

## Fase 2 — Funções e infraestrutura

### [x] T06 · `fn-ingestao` ★ 🧑‍🏫

> **Concluída em 25/10.** Handler `FnIngestao` (S3 falso, 8 testes: válida, R10, duplicada, reentrega de duplicada, evento repetido, exceção, chave fora do padrão, log sem `sub`/chave), adaptador `RepositorioCalibracoesDynamoDb` com mapeador e `DecisorCancelamento`; `./mvnw test`: 102 testes (67 + 35), 0 falhas. D-023. **Pendente na T09:** condições do `TransactWriteItems` no DynamoDB real (roteiro: envio normal, mesmo arquivo com outro id, evento repetido, id sem item, duas invocações simultâneas do mesmo hash). T07: `fn-certificado` ignora envelope sem `calibracaoId`.

**Contexto.** `ProcessamentoService` (AV03), porta da T04, `LeitorPlanilha`, AV02 §3.1 (E3–E5).

**Faça.**

- Handler `RequestHandler<S3Event, ...>`: extrai `sub` e `uploadId` da chave, abre o objeto em
  *stream*, passa pelo `Medidor` (hash) e pelo núcleo, grava pela porta.
- Inválida → grava `REJEITADA` com os erros e **termina com sucesso** (quarentena é resultado de
  negócio, não falha — AV02 §3.1.3); não aciona o certificado. Erro inesperado → lança exceção
  (vai para a DLQ). Duplicada → conforme a resposta 2 da T04.
- Retorno no sucesso: `{ "calibracaoId": ... }` (é o que a `fn-certificado` recebe no destino).
- Log: só `uploadId`, `sha256`, `bytes`, resultado. 🔒 Nada de nome de arquivo.
- Adaptador DynamoDB real da porta (SDK v2, `TransactWriteItems`) no `funcoes`.
- Teste unitário com S3 e repositório falsos (sem AWS).

**Aceite.** Testes verdes para: válida, inválida (R10), duplicada, exceção inesperada.

**Relatório.** §3.

---

### [x] T07 · `fn-certificado` e `fn-api` ★ 🛠 (*plan mode*)

**Contexto.** T04–T06, AV02 §3.1 (E1, E2, E6, E10) e §4.1 (tabela de papéis).

**Faça.**

- `fn-certificado`: recebe o envelope do destino do Lambda (`responsePayload.calibracaoId`), carrega,
  gera o PDF (T05), grava `certificados/<id>.pdf` (SSE-S3), grava o item `TOKEN#<token>` (32
  caracteres aleatórios, `SecureRandom`) e muda o estado para `EMITIDA` com o hash do PDF.
  **Pendência da T06:** o destino OnSuccess dispara com qualquer retorno e não filtra por payload. A
  `fn-ingestao` devolve `{}` (sem `calibracaoId`) em REJEITADA e DUPLICADA; a `fn-certificado` deve
  **ignorar, com sucesso**, o envelope sem `calibracaoId`, sem tentar emitir.
- `fn-api` (um handler, roteamento por `routeKey` do evento HTTP API v2):
  - `POST /uploads` `{tamanho}` → recusa > 5 MB; devolve `uploadId` e URL **PUT** pré-assinada
    (5 min, `Content-Type` e `Content-Length` assinados) para `uploads/<sub>/<uploadId>.xlsx`.
  - `GET /calibracoes/{id}` → estado + resultado ou erros; só do próprio `sub` (senão 404, não 403,
    para não confirmar existência).
  - `GET /calibracoes/{id}/pdf` → URL GET pré-assinada de 5 min.
  - `GET /calibracoes` → ◇ (T12) últimas 20 do usuário.
  - `GET /verificacao/{token}` → **público**: identificador, data, parecer, hash do PDF. Sem nome.
  - Erros em `application/problem+json` (mesmo padrão da AV03); id malformado → 400.
- Testes unitários dos dois handlers com falsos.

**Aceite.** Testes verdes; o PDF traz "Gerado por: <nome>" lido do Cognito, sem o nome em tabela, evento ou log; nenhuma rota devolve dado de outro `sub`; `./mvnw -pl funcoes -am
package` gera um único JAR sombreado (`maven-shade-plugin`) sem classes do Spring.

**Relatório.** §3 e §7 (API).

> **Concluída em 25/10.** `FnCertificado` (9 testes: emite, nome do Cognito, rótulo neutro, falha do diretório, envelope sem `calibracaoId`, reentrega, estado errado, falha no S3, ambiente) e `FnApi` (16 testes, 5 rotas + stub 501 de `GET /calibracoes`), `S3UrlsPreassinadas` (2 testes, presigner real); porta com `buscarPorToken`; `maven-shade-plugin` 3.6.2 gera JAR único de 48 MB sem Spring. `./mvnw test`: 149 testes (68 + 15 + 66), 0 falhas. D-024, D-025. **Reaberta e refeita no mesmo dia:** o nome do "Gerado por" vem do Cognito (`AdminGetUser` pelo `sub`) na emissão, sem passar por tabela, S3 ou evento; biblioteca `cognitoidentityprovider` (D-019). **Divergência:** PUT em vez de POST pré-assinado. **Pendente na T08:** `TABELA_CALIBRACOES`, `BUCKET_ENTRADA`, `BUCKET_CERTIFICADOS`, `URL_VERIFICACAO_BASE`, `USER_POOL_ID`, permissão `cognito-idp:AdminGetUser` só para a `fn-certificado`, usuários com atributo `name`; **na T09:** provar `AdminGetUser` com o `sub` como `Username`. Handlers: handlers `br.senai_pa3.api.FnApi::handleRequest` e `br.senai_pa3.certificado.FnCertificado::handleRequest`.

---

### [x] T08 · Template SAM e deploy do back-end ★ 🛠 (*plan mode*) 🔒

**Contexto.** AV02 §1.2, §2 (cotas) e §4 (IAM, criptografia), D-004, D-007, D-008, D-009, D-016,
D-020.

**Faça** `infra/template.yaml` (+ `infra/deploy.sh`):

- **S3:** `entrada` e `certificados` com bloqueio de acesso público, `DenyInsecureTransport`, SSE-S3,
  versionamento, **ciclo de vida** (transição para classe de arquivamento em 365 dias e expiração
  em 1 825 dias — D-004) e CORS do `entrada` só para a origem do CloudFront (e `localhost` em dev).
  `web` privado, servido pelo CloudFront (OAC), com resposta 403/404 → `/index.html` (rotas da SPA).
- **DynamoDB:** `calibracoes` (+GSI2) e ◇ `auditoria`, modo **provisionado** dentro das 25 RCU/WCU.
- **Lambda:** três funções `java21`, `CodeUri` apontando para o JAR sombreado (o `sam build` não
  resolve o módulo `nucleo` sozinho), timeout 30 s, memória 1 024 MB, logs com retenção de 30 dias;
  `fn-ingestao` por evento S3 em `uploads/`, destino de sucesso → `fn-certificado`, falha → SQS DLQ.
- **Cognito:** user pool sem autocadastro, cliente público com `ALLOW_USER_PASSWORD_AUTH` e
  `ALLOW_REFRESH_TOKEN_AUTH`, token de acesso de 60 min (RNF-05).
- **HTTP API:** autorizador JWT do Cognito em todas as rotas exceto `GET /verificacao/{token}`,
  CORS, *throttling* (AV02: 10 req/s).
- **IAM:** um papel por função, só as ações da AV02 §4.1 (ex.: `fn-ingestao` com `s3:GetObject`
  só em `uploads/*`; `fn-certificado` com `cognito-idp:AdminGetUser` só no user pool, D-025). Modo
  alterado de instrutivo para delegado em 25/10: o Claude escreve; você revisa cada política.
- **Saídas** do stack: URL da API, URL do CloudFront, ids do user pool e do cliente.

Deploy: `sam deploy --guided --profile pa3 --region us-east-2` (D-022) na primeira vez.

**Aceite.** Stack `CREATE_COMPLETE`; nenhum recurso fora da lista acima (sem NAT, sem KMS próprio,
sem DynamoDB sob demanda); `aws s3api get-bucket-lifecycle-configuration` mostra a regra.

**Relatório.** §6 (Roteiro de deploy) e §4.

> **Concluída em 25/10.** `infra/template.yaml` + `infra/deploy.sh`; stack `pa3-av04` em `CREATE_COMPLETE` (us-east-2, perfil `pa3`) com 31 recursos: 3 buckets S3 + políticas, tabela `calibracoes` (5/5 + GSI2 5/5), 3 funções `java21` + 3 log groups + 3 papéis, 2 `EventInvokeConfig`, fila de falhas, user pool + cliente, HTTP API; sem NAT, KMS, WAF, EC2 nem CloudFront (D-026: o plano gratuito exige WAF em `us-east-1`; resolver na T10). `aws s3api get-bucket-lifecycle-configuration` mostra `GLACIER_IR` aos 365 dias e expiração aos 1 825. `./mvnw test`: 149 testes, 0 falhas. **Limitações registradas (§11):** sem MFA; PDFs de ~4 KB não transicionam. **Para a T09:** criar usuário com `name` e provar `AdminGetUser` com o `sub`; saída `FilaFalhas` passou a mostrar só o nome da fila (a URL trazia o número da conta; vale no próximo deploy). `infra/deploy.sh` precisa de `CONFIRMAR_CHANGESET=nao` quando rodado com `!`.

---

### [x] T09 · Teste de ponta a ponta na nuvem, sem tela ★ 🛠 🔒

**Contexto.** Saídas do stack (T08), `docs/av03/evidencias.md` (modelo de CT e laço `curl`).

**Faça** `infra/smoke.sh` (variáveis vindas das saídas do stack, nada fixo no arquivo):

1. Criar usuário de teste: `admin-create-user` + `admin-set-user-password --permanent` (evita o
   desafio `NEW_PASSWORD_REQUIRED` na primeira entrada).
2. Token via `aws cognito-idp initiate-auth --auth-flow USER_PASSWORD_AUTH`.
3. `POST /uploads` → `PUT` do `ok-reprovado.xlsx` → *polling* do `GET /calibracoes/{id}` →
   `GET .../pdf` → baixa o PDF → `GET /verificacao/{token}` sem token.
4. Repetir com o mesmo arquivo (idempotência), com `inv-multiplos-erros.xlsx` (rejeição) e sem
   token (401 na borda).

🔒 As respostas salvas em `docs/av04/evidencias/respostas/` não podem conter JWT, URL pré-assinada
(tem credencial temporária) nem número da conta: filtre com `jq` antes de gravar.

**Aceite.** Os cinco cenários com o resultado esperado; log da `fn-ingestao` no CloudWatch só com
hash e tamanho. **Marco de domingo: se isso passa, a AV04 está garantida.**

**Relatório.** §9 (Evidências).

> **Concluída em 25/10.** `infra/smoke.sh` (variáveis das saídas do stack, usuário `smoke-pa3@example.com` com `name`, senha aleatória por execução, usuário apagado ao final) passou em todas as verificações no stack `pa3-av04`: envio normal até `EMITIDA` (`REPROVADO`, só o ponto de furo B `FORA_DA_TOLERANCIA`), PDF baixado com o nome do Cognito (prova `AdminGetUser` com o `sub`), `GET /verificacao/{token}` sem token com `sha256Pdf` igual ao do arquivo baixado, mesmo arquivo → `DUPLICADA`, `inv-multiplos-erros.xlsx` → `REJEITADA` (R10, R11, R14), sem token e token inválido → 401, id sem item → 404, tamanho > 5 MB → 413, e dois envios simultâneos do mesmo hash → um `EMITIDA` e um `DUPLICADA` (condições do `TransactWriteItems` provadas no DynamoDB real). Log da `fn-ingestao`: só `uploadId`, SHA-256, bytes e resultado (verificado sem `.xlsx`, `sub` nem JWT). Respostas filtradas com `jq` em `docs/av04/evidencias/respostas/`. **Notas:** o autorizador JWT confere `aud`, então o token usado é o **ID token** (o da T10 também); o script apaga a sentinela `HASH#` dos três arquivos de teste antes de rodar, para poder repetir; a reentrega do mesmo evento S3 continua provada só nos testes unitários. `./mvnw test`: 149 testes, 0 falhas.

---

## Fase 3 — Plataforma web

### [x] T10 · Projeto React e login ★ 🛠 / 🧑‍🏫 (fluxo de token) 🔒

**Contexto.** `app-local/.../static/` (tela da AV03: reaproveitar comportamento, cores e rótulos),
saídas do stack.

**Faça.**

- `web/` com Vite + React (D-019). Sem biblioteca de roteamento nem de estado: duas ou três telas
  resolvem com estado simples e `location.pathname` para a rota pública `/verificar/<token>`.
- Configuração por `import.meta.env` (`VITE_API_URL`, `VITE_COGNITO_CLIENT_ID`, região), gerada a
  partir das saídas do stack por script; `.env` fora do Git.
- Login com `fetch` direto ao Cognito (`InitiateAuth`, `USER_PASSWORD_AUTH`), sem SDK. A senha vai
  do navegador ao Cognito por HTTPS, nunca à aplicação (AV02 §4.3).
- 🔒 Tokens **só em memória** (estado React), nunca em `localStorage`; recarregar a página pede
  login de novo — declarar. Mensagem de erro genérica para usuário/senha inválidos.

**Aceite.** `npm run dev` faz login no Cognito real e mostra o usuário; senha errada mostra erro
sem detalhe técnico.

**Relatório.** §5 (Plataforma) e §7 (Segurança).

> **Concluída em 25/10.** `web/` com Vite 8.3.5, React/React DOM 19.3.1 e `@vitejs/plugin-react` 6.1.2 (versões do npm no dia); `infra/gerar-env-web.sh` gera `web/.env` (fora do Git) das saídas do stack. `src/cognito.js` (escrita pelo Rodrigo) faz `InitiateAuth` com `fetch`, devolve o **ID token** (o autorizador confere `aud`) e trata rede, JSON inválido, HTTP de erro e 200 com desafio (`NEW_PASSWORD_REQUIRED`, mapeado a erro genérico). Provado no Chrome contra o Cognito real: senha errada mostra "Usuário ou senha inválidos." e limpa o campo; senha certa mostra o nome do usuário (`name` do ID token); recarregar pede login de novo; token só em memória (`localStorage` sem JWT; as chaves `vagas`/`selected_person` que apareceram são de outro projeto na mesma origem `localhost:5173`). Usuário de teste apagado. Evidência: `docs/av04/evidencias/tela/t10-login.jpg`. `./mvnw test`: 149 testes, 0 falhas; `npm run build` verde. **Limitações:** desafio de troca de senha não tem tela (usuários nascem com `--permanent`); sem MFA (§11).

---

### [x] T11 · Tela de processamento ★ 🛠 (*plan mode*)

**Contexto.** `app-local/.../static/app.js` e `estilo.css` (AV03), achados 11 e 12 da AV03
(corrida na troca de arquivo).

**Faça.**

- Escolher arquivo → `POST /uploads` → `PUT` na URL → *polling* com limite (ex.: a cada 1,5 s,
  até 40 s; depois, mensagem "ainda processando, consulte no histórico").
- Estados visíveis: enviando, processando, `REJEITADA` (lista de erros com linha, coluna, regra),
  resultado (tabela da AV03: enums literais, cor + rótulo, 5 casas com vírgula), botão **Baixar
  certificado**.
- Mesmas proteções da AV03: limpar ao trocar de arquivo, travar durante o envio, só texto (o React
  já escapa; não usar `dangerouslySetInnerHTML`).
- RNF-15: contraste AA, alvos de toque grandes, funciona em tablet (DevTools, 768 px).

**Aceite.** Fluxo completo local contra a nuvem com `ok-aprovado`, `ok-reprovado` e
`inv-multiplos-erros`; prints.

**Relatório.** §5, com prints.

> **Concluída em 25/10.** `web/src/Processamento.jsx` (tela), `api.js` (POST/PUT/GET e download do PDF como *blob*, porque navegar até o S3 derrubaria o token em memória) e `formato.js` (5 casas por HALF_EVEN em `BigInt` sobre o texto da API, igual ao PDF; empates conferidos contra `BigDecimal` no `jshell`). *Polling* a cada 1,5 s por até 40 s, com "Consultar de novo"; `PROCESSADA` continua esperando o PDF. A12 estendido: `AbortController` por envio cancela o polling anterior ao trocar de arquivo, sair ou desmontar a tela. Provado no Chrome contra a nuvem: `ok-aprovado` → `APROVADO`, `ok-reprovado` → `REPROVADO` (furo B `FORA_DA_TOLERANCIA`), `inv-multiplos-erros` → `REJEITADA` (R10, R11, R14), reenvio → `DUPLICADA`; troca de arquivo limpa a tela; o *blob* do PDF tem SHA-256 igual ao `sha256Pdf` do DynamoDB. Em 768 px: alvos de 44 px, sem rolagem lateral da página e tabela inteira visível (`<wbr>` após "_" no selo, enum intacto). Prints `docs/av04/evidencias/tela/t11-*.jpg`. Usuário de teste apagado. `./mvnw test`: 149 testes, 0 falhas; `npm run build` verde. **Não exercitados na nuvem:** prazo de 40 s esgotado, 401 no meio do polling e 500 (caminhos de código revisados, sem print). O Chrome abriu o diálogo "Salvar como"; o PDF salvo (`docs/av04/evidencias/certificado-3843b8f4-c7d3-4f1f-94ac-46ccf0115b9b.pdf`, `ok-aprovado`) tem SHA-256 igual ao `sha256Pdf` do DynamoDB.

---

### [x] T12 · Histórico de calibrações ◇ 🛠

**Contexto.** GSI da T04/T08, rota `GET /calibracoes` (T07).

**Faça.** Lista das últimas 20 do usuário (data, estado, parecer), clique abre o resultado. É o
que faz a plataforma ser "de gestão", e não só a tela da AV03.

**Aceite.** Lista mostra os envios da T09 e T11.

> **Concluída em 25/10.** Porta `listarDoUsuario(sub, limite)`; adaptador DynamoDB com `Query` no GSI2 (`GSI2PK = USER#<sub>`, decrescente, `Limit` 20), em memória com a mesma ordem. `GET /calibracoes` devolve `{itens: [{id, estado, atualizadoEm, parecer?}]}`, sem `sub`, `sha256` nem token, e refiltra por `sub` como defesa. Tela: abas "Processar planilha" / "Histórico" (estado simples, sem roteador); lista com data em America/Sao_Paulo, estado e parecer com enum literal + rótulo e botão **Abrir**, que reaproveita a tabela da T11 (`Resultado.jsx`); "Abrir histórico" nas mensagens de duplicada e de demora. Back-end reimplantado (`infra/deploy.sh`; só código). **Aceite adaptado:** os usuários da T09 e da T11 tinham sido apagados, e cada usuário recriado ganha `sub` novo; por desenho (dono = `sub`), aqueles envios não aparecem para ninguém. Reproduzidos com um só usuário: `MANTER_USUARIO=sim infra/smoke.sh` (todos os cenários passam, o que também prova que a `fn-api` nova não regrediu; evidências da T09 restauradas com `git restore`) e, na tela, as três planilhas da T11 mais um reenvio. A lista mostrou os 9 envios (5 da T09 + 4 da T11), do mais recente para o mais antigo. O detalhe de `EMITIDA` baixa o PDF com SHA-256 igual ao `sha256Pdf`; o de `REJEITADA` mostra R10, R11 e R14. A janela do Chrome não aceitou redimensionar desta vez, então a largura de tablet foi emulada (`main` com 736 px = 768 − 2 × 16): a tabela cabe sem rolar. Evidências: `docs/av04/evidencias/respostas/t12-historico.txt` e `docs/av04/evidencias/tela/t12-*.jpg`. `./mvnw test`: 154 testes, 0 falhas; `npm run build` verde. **Limitações:** só os 20 mais recentes, sem paginação; ordem pela última transição (`atualizadoEm`), não pela data de envio; GSI eventualmente consistente (um envio de segundos atrás pode faltar até "Atualizar").

---

### [x] T13 · Página pública de verificação (QR) ★ 🛠

**Contexto.** Rota `GET /verificacao/{token}` (T07), D-015.

**Faça.** `/verificar/<token>` sem login: identificador, data, parecer, hash do PDF e a instrução
"compare com o hash impresso no documento". Layout para celular. Token inválido → "certificado não
encontrado" (sem distinguir de token malformado).

**Aceite.** Ler o QR do PDF (ou abrir a URL impressa) com o celular abre a página certa.

> **Concluída em 27/10 (código).** `web/src/Verificacao.jsx`: `/verificar/<token>` sem login (identificador, data, parecer, SHA-256 do PDF), token malformado = inexistente, `/verificar` sem token pede o código, e conferência do PDF recebido pelo SHA-256 calculado no aparelho (Web Crypto), porque um PDF não pode conter o próprio hash: a instrução do guia ("compare com o hash impresso") foi trocada por essa conferência. Testada a 375 e 390 px com a `fn-web` real servindo `web/dist` e a resposta da CT-403 simulada (`evidencias/tela/t13-verificacao-local-390px.jpg`). **Fechada em 27/10:** QR lido num celular por dados móveis (5G, sem Wi-Fi), hash igual ao registrado e "Arquivo íntegro" (CT-412, `evidencias/tela/ct-412-qr-celular-4g.png`).

**Relatório.** §5.

---

### [ ] T14 · Publicar a SPA ★ 🛠

**Contexto.** T08 (bucket `web`, CloudFront), T10.

**Faça** `infra/deploy-web.sh`: gerar `.env` das saídas do stack → `npm ci && npm run build` →
`aws s3 sync web/dist s3://<bucket-web> --delete` → invalidação `/*` no CloudFront. Ajustar CORS da
API e do bucket `entrada` para a origem do CloudFront.

**Aceite.** Fluxo completo pela URL do CloudFront, em aba anônima, e a verificação no celular por

> **Implantada em 27/10.** CloudFront substituído pela `fn-web` no próprio HTTP API (D-027): `infra/fn-web/index.mjs` (8 testes `node:test`), rotas `GET /` e `GET /{proxy+}` sem autorizador, CORS dos buckets com a origem da API, `fn-api` com buckets pelo nome (evita ciclo; verificado), `UrlVerificacaoBase=api`. `infra/deploy-web.sh` (env → build → sync, `index.html` por último → confere 200) e `infra/smoke-web.sh` (CT-410, CT-414). **Deploy em 27/10** (commit `219631f`, perfil `pa3`): changeset sem substituição de recurso com estado; dois defeitos só visíveis na nuvem, corrigidos: o `handler` recebia o *callback* do runtime no lugar do leitor do S3 (todo `GET` dava 500; agora `tratar(evento, ler)` + `handler(evento)`, 9 testes) e faltava `s3:ListBucket` no papel da `fn-web` (asset inexistente dava 500 em vez de 404). `infra/smoke-web.sh` sem falhas (CT-410, CT-414); `infra/smoke.sh` repetido, todos os cenários passam. Base da etapa: commit `66b4d42` de Nícolas Lange.
4G (fora da rede de casa).

**Relatório.** §6.

---

## Fase 4 — Evidências, vídeo e relatório

### [x] T15 · Evidências e Matriz de Rastreabilidade ★ 🛠 / 🧑‍🏫 (matriz)

**Contexto.** `docs/av03/evidencias.md` (modelo), AV01 (RF/RNF/RN/UC — só os códigos, no
`AV2_Grupo39_fonte.md`), AV02 §5 (matriz de decisões).

**Faça.**

- `docs/av04/evidencias.md`: CT-401 em diante (nuvem: os cinco cenários da T09, tela, verificação,
  401 sem token, 404 de outro usuário, URL pré-assinada expirada, ciclo de vida, logs sem dado
  pessoal, custo). Uma linha de base: commit + data do deploy.
- **Matriz de Rastreabilidade de Requisitos** (`docs/av04/matriz-rastreabilidade.md`): requisito
  (AV01) → decisão/passo da arquitetura (AV02) → componente/classe → teste automatizado ou CT →
  evidência. Inclua os requisitos **não** atendidos, com o motivo (roadmap).
- Custo: print de *Billing/Free Tier* e do Cost Explorer com US$ 0,00 (ou só consumo de créditos),
  e das métricas de uso (invocações do Lambda, RCU/WCU) contra as cotas.

**Aceite.** Todo item do roteiro tem CT e evidência; todo RF do recorte aparece na matriz.

> **Concluída em 27/10.** `docs/av04/evidencias.md` (CT-401 a CT-418, com situação; os ⏳ fecham com o deploy e o vídeo) e `docs/av04/matriz-rastreabilidade.md` (itens do roteiro, RF, RNF, RN/DE, com os não atendidos e o motivo), incluída na §10 do relatório. Clone limpo revelou e corrigiu um defeito de portabilidade no `FnCertificado` (cliente do SDK criado antes de conferir o ambiente). `./mvnw test`: 154 testes, 0 falhas, 1 pulado.

**Relatório.** §9 e §10.

---

### [ ] T16 · Vídeo no YouTube com narração ★ 🧑‍🏫 🔒

**Contexto.** Seção 2 deste guia, T15.

**Faça.**

- Roteiro de 5–8 min em `docs/av04/roteiro-video.md`: problema (13 dias, 30 s) → arquitetura
  (diagrama) → login → upload aprovado e reprovado → PDF → QR no celular → planilha inválida →
  reenvio (idempotência) → console AWS: Lambda, DynamoDB, S3 com ciclo de vida, logs, custo zero.
- Gravar (OBS ou similar), uma tomada por bloco; publicar (não listado, se o professor aceitar).
- 🔒 Antes de gravar: nada de número de conta, e-mail pessoal, token, URL pré-assinada, chave ou
  dado real da Schulz na tela. Assista uma vez só procurando isso.

**Aceite.** Link funcionando em aba anônima.

> **Roteiro pronto em 27/10** (`docs/av04/roteiro-video.md`, 10 blocos, checklist 🔒). **Falta:** gravar e publicar.

**Relatório.** Link no cabeçalho e na §9.

---

### [ ] T17 · Relatório Técnico Integrado em PDF ★ 🧑‍🏫 (texto) / 🛠 (formatação)

**Contexto.** `docs/av04/AV4_fonte.md` (montado ao longo das tarefas), pipeline da AV03 (pandoc,
DOCX da AV2 como `--reference-doc`, `ferramentas/formatar_docx.py`, LibreOffice).

**Estrutura:** cabeçalho obrigatório (UC, docente, integrantes com nome completo, GitHub, YouTube)
· 1 Introdução e vínculo com AV01–AV03 · 2 Decisões · 3 Arquitetura implementada (diagrama
atualizado, divergências da AV02) · 4 Persistência e idempotência · 5 Plataforma Web (telas) ·
6 **Roteiro de deploy na AWS** (reprodutível do zero) · 7 Segurança e LGPD · 8 Custo e Free Tier ·
9 Evidências · 10 **Matriz de Rastreabilidade** · 11 Limitações e roadmap · 12 Premissas
(`[PREMISSA]`, `[VALIDAR]`, seções 3–4 do roteiro) · Referências.

**Aceite.** PDF aberto e lido por você; links clicáveis; nenhum dado pessoal de terceiros.

> **Gerado em 27/10.** `ferramentas/relatorio/gerar-relatorio.mjs` (Markdown → HTML → PDF pelo Chrome/Edge headless, sem pandoc). URL da plataforma preenchida e PDF regenerado em 27/10 com o deploy, os defeitos corrigidos e as Figuras 7 a 9. **Falta:** RA dos três integrantes e link do vídeo no cabeçalho de `AV4_fonte.md`, e gerar de novo.

---

### [ ] T18 · README, revisão final e envio ★ 🛠

- README: o que mudou na AV04, URL da plataforma, como fazer o deploy (resumo da §6), estrutura dos
  módulos, limitações.
- Clone limpo: `./mvnw test` verde e o `infra/deploy.sh` documentado.
- Checklist: roteiro inteiro coberto · enums literais no código, API e tela · nada real da Schulz no
  Git · repositório público · vídeo acessível · cabeçalho completo · PDF exportado com folga.
- 🔒 **Não derrubar o stack** antes da nota: o professor pode abrir a URL. Depois, `sam delete`.

---

### [ ] T19 · Trilha de auditoria ◇ 🛠 🔒

Tabela `auditoria` só de inserção (AV02 §3.2, RNF-04, RN-24): eventos `UPLOAD_AUTORIZADO`,
`PROCESSADA`, `REJEITADA`, `EMITIDA`, `PDF_BAIXADO`, com `sub`, instante e id. Papéis das funções
sem `UpdateItem`/`DeleteItem` nela.

---

## Registro de progresso

| Tarefa | Modo | Status   | Observação |
| ------ | ---- | -------- | ---------- |
| T00    | 🧑‍🏫   | Concluída | Perguntas enviadas em 24/10; sem resposta, seguimos com premissas |
| T01    | 🧑‍🏫   | Concluída | D-015 a D-020; OAC no plano gratuito a confirmar na T10 |
| T02    | 🛠   | Concluída | Conta nova, `us-east-2` (D-022); MFA no Builder ID; `pa3-deploy`; budgets via SNS |
| T03    | 🛠   | Concluída | Multimódulo; 71 testes verdes; `Medidor` no núcleo |
| T04    | 🧑‍🏫→🛠 | Concluída | Porta + adaptador em memória; 82 testes verdes; D-021; falta provar no DynamoDB (T06) |
| T05    | 🛠   | Concluída | PDF com QR; 85 testes verdes; divergência de PV-14 (layout simplificado) |
| T06    | 🧑‍🏫   | Concluída | Handler + adaptador DynamoDB; 102 testes verdes; D-023; falta provar o DynamoDB real (T09) |
| T07    | 🛠   | Concluída | fn-certificado + fn-api; 143 testes verdes; D-024; JAR sombreado 48 MB; nome via Cognito (D-025) |
| T08    | 🛠   | Concluída | Stack `pa3-av04` `CREATE_COMPLETE`; sem CloudFront (D-026); IAM delegado |
| T09    | 🛠   | Concluída | `infra/smoke.sh`: 6 cenários na nuvem passam; DynamoDB real provado; ID token no autorizador |
| T10    | 🛠/🧑‍🏫 | Concluída | `web/` com login no Cognito real (ID token em memória); `cognito.js` do Rodrigo; testado no Chrome |
| T11    | 🛠   | Concluída | Upload → S3 → polling; 4 estados provados na nuvem; HALF_EVEN igual ao PDF; 768 px sem rolagem |
| T12    | 🛠   | Concluída | GSI2 + `GET /calibracoes` + aba Histórico; 154 testes; 9 envios (T09 + T11) com o mesmo usuário |
| T13    | 🛠   | Concluída | Verificação pública + conferência do PDF no aparelho; QR lido no celular (CT-412) |
| T14    | 🛠   | Concluída | `fn-web` no HTTP API (D-027), implantada em 27/10; CT-410 e CT-414 passam |
| T15    | 🛠   | Concluída | Evidências CT-401–418 e matriz; CT-410 a CT-415 fechados em 27/10 (CT-417 opcional) |
| T16    | 🧑‍🏫   | Roteiro pronto | Falta gravar |
| T17    | 🧑‍🏫   | PDF gerado | Falta RA e link do vídeo |
| T18    | 🛠   | Pendente |            |
| T19    | 🛠   | Pendente |            |
