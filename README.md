# Projeto Aplicado III — Certificados de Calibração

**Automação da emissão de certificados de calibração — Schulz S.A.**
UniSENAI/SC · 2026.2 · Prof. MSc. Hugo Menezes Barra

Grupo 39: Nícolas Kretzschmar Lange · Rodrigo Mainardes Ribeiro

## AV04 — Plataforma Web de Gestão na AWS

A AV04 integra o diagnóstico (AV01), a arquitetura serverless (AV02) e o motor de cálculo (AV03) numa
plataforma web publicada na AWS, dentro da Camada Gratuita:

- **Login** no Amazon Cognito (sem autocadastro; token só em memória).
- **Processar planilha:** upload direto ao S3 por URL pré-assinada → o evento dispara a `fn-ingestao`, que
  roda o núcleo da AV03 → DynamoDB → a `fn-certificado` gera o PDF com QR Code → resultado na tela.
- **Histórico** com indicadores de gestão (envios, emitidos, `APROVADO`, `REPROVADO`, rejeitadas) e
  download do certificado.
- **Verificação pública** em `/verificar/<token>`, aberta pelo QR Code no celular, sem login; confere o
  SHA-256 do PDF no próprio aparelho.
- **Idempotência:** o mesmo arquivo nunca gera dois certificados (`DUPLICADA`, RN-20).

Tudo em `us-east-2` (D-022): 5 funções Lambda, 3 buckets S3 privados, DynamoDB provisionado, Cognito, um
HTTP API e uma fila SQS de falhas. A interface é servida pelo próprio HTTP API, pela `fn-web`
([D-027](docs/decisoes.md)), sem CloudFront. Documentos da entrega:

| Documento | Arquivo |
| --- | --- |
| Relatório Técnico Integrado (PDF) | [`docs/av04/AV4_Projeto_Aplicado_III.pdf`](docs/av04/AV4_Projeto_Aplicado_III.pdf) (fonte: [`AV4_fonte.md`](docs/av04/AV4_fonte.md)) |
| Matriz de Rastreabilidade de Requisitos | [`docs/av04/matriz-rastreabilidade.md`](docs/av04/matriz-rastreabilidade.md) |
| Casos de teste e evidências | [`docs/av04/evidencias.md`](docs/av04/evidencias.md) |
| Roteiro do vídeo | [`docs/av04/roteiro-video.md`](docs/av04/roteiro-video.md) |
| Decisões D-001 a D-027 | [`docs/decisoes.md`](docs/decisoes.md) |

### Deploy do zero

Pré-requisitos: conta AWS no plano gratuito (com MFA e AWS Budgets configurados antes de tudo), AWS CLI
v2 com um perfil de deploy, AWS SAM CLI, JDK 21, Node.js 22+ e Bash (Git Bash no Windows).

```bash
aws configure --profile pa3           # região us-east-2, saída json
./mvnw test                           # 154 testes, 1 pulado
node --test infra/fn-web/index.test.mjs
infra/deploy.sh                       # back-end: JAR + sam validate + sam deploy
infra/deploy-web.sh                   # interface: build da SPA + sync no bucket web; imprime a URL
infra/smoke.sh                        # pipeline de ponta a ponta na nuvem (CT-401 a CT-408)
infra/smoke-web.sh                    # interface publicada (CT-410, CT-414)
```

`PERFIL`, `REGIAO` e `STACK` (padrões `pa3`, `us-east-2`, `pa3-av04`) podem ser trocados por variável de
ambiente. Usuários são criados pelo administrador (`cognito-idp admin-create-user` com `email`, `name` e
`admin-set-user-password --permanent`; comandos no [roteiro do vídeo](docs/av04/roteiro-video.md)). A URL
da plataforma é a saída `UrlPlataforma` do stack. Para remover tudo: esvazie os buckets e rode
`sam delete --stack-name pa3-av04 --profile pa3 --region us-east-2`.

Para desenvolver a tela contra a nuvem: `infra/gerar-env-web.sh && cd web && npm ci && npm run dev`
(http://localhost:5173, origem liberada no CORS).

## O problema

A Schulz Metrologia leva ~13 dias entre medir um dispositivo na MMC e emitir o certificado
de calibração. O caminho hoje é uma cadeia de planilhas Excel acopladas por cópia manual:
28 valores transportados à mão por certificado, cálculo não validado, sem trilha de auditoria.
O diagnóstico completo é o da AV01, que não está neste repositório porque cita arquivos reais
da empresa.

## O que o MVP faz (AV03)

Aplicação web que recebe a planilha de medições (`.xlsx`), valida o arquivo contra o
[contrato da planilha](docs/av03/contrato-planilha.md) (regras R01 a R15) e calcula, para cada
ponto de ensaio:

- a **média** das leituras;
- o **erro sistemático** (média − valor de referência);
- o **status**: `DENTRO_DA_TOLERANCIA` se |erro| ≤ LEA, senão `FORA_DA_TOLERANCIA`.

O **parecer** é `APROVADO` se todos os pontos estão dentro da tolerância e `REPROVADO` se algum
não está. O resultado aparece na tela e na API (JSON).

Os cálculos usam `BigDecimal`: média com escala 10 (`HALF_EVEN`), comparação com o LEA sem
arredondamento prévio; média e erro são exibidos com 5 casas.

Stack: Java 17, Spring Boot 4.1, Apache POI 5.5 ([D-011](docs/decisoes.md)). O núcleo de
cálculo e de leitura não depende do Spring ([D-012](docs/decisoes.md)), para rodar também na
função serverless da arquitetura da AV02.

## Requisitos

- JDK 17 ou superior (`java -version`).
- Maven não precisa estar instalado: o projeto usa o Maven Wrapper (`mvnw`). O primeiro build
  baixa as dependências e precisa de internet.

## Como rodar

```bash
./mvnw -pl app-local -am spring-boot:run   # Windows: mvnw.cmd ...
```

Abra <http://localhost:8080/>, escolha uma planilha de `nucleo/src/test/resources/planilhas/`
(por exemplo, `ok-reprovado.xlsx`) e clique em **Processar**.

## Como testar

```bash
./mvnw test                     # Windows: mvnw.cmd test
```

Resultado esperado num clone limpo: `Tests run: 71, Failures: 0, Errors: 0, Skipped: 1`.
O teste pulado (`PoiStrictTest.xssfWorkbookRecusaStrictReal`) usa uma planilha real da
empresa, mantida fora do Git; a mesma verificação roda com o arquivo sintético
`inv-R03-strict.xlsx`.

## API

`POST /api/calibracoes/processamento` — `multipart/form-data`, campo `arquivo`.

```bash
curl -i -F arquivo=@nucleo/src/test/resources/planilhas/ok-aprovado.xlsx \
  http://localhost:8080/api/calibracoes/processamento
```

Resposta (trecho):

```json
{
  "parecer": "APROVADO",
  "pontos": [
    {
      "caracteristica": "Diâmetro eixo",
      "leituras": [4.13, 4.14],
      "valorReferencia": 4.12,
      "media": 4.13500,
      "erroSistematico": 0.01500,
      "lea": 0.03,
      "status": "DENTRO_DA_TOLERANCIA"
    }
  ]
}
```

| Código | Quando |
| ------ | ------ |
| 200 | Planilha processada, com parecer `APROVADO` ou `REPROVADO` (reprovação é resultado, não erro) |
| 400 | Planilha fora do contrato (lista `erros` com linha, coluna, regra e mensagem) ou requisição sem a parte `arquivo` |
| 413 | Arquivo acima de 5 MB |
| 415 | Requisição que não é `multipart/form-data` |
| 500 | Erro inesperado: a resposta traz só um `id`, que liga ao registro no log |

Os erros seguem o formato `application/problem+json` (RFC 9457). Exemplos de todas as
respostas estão em `docs/av03/evidencias/respostas/`.

## Planilhas de exemplo

`nucleo/src/test/resources/planilhas/` tem 7 planilhas válidas (`ok-*`) e 14 inválidas (`inv-*`,
cada uma violando uma regra do contrato). Os valores esperados de cada uma, calculados de forma
independente do Java, estão em `docs/av03/oraculo-planilhas.md`.

Formato resumido: aba `Medicoes`; colunas `Caracteristica`, `ValorReferencia`, `Leitura1`,
`Leitura2`… (no mínimo duas), `ToleranciaSuperior` e `ToleranciaInferior`; números digitados
como número, sem fórmulas. Detalhes no [contrato](docs/av03/contrato-planilha.md).

As planilhas são geradas por `ferramentas/gerar_planilhas.py` (Python 3 com `openpyxl`;
LibreOffice opcional). A exceção é `inv-R03-strict.xlsx`, salva no Excel desktop, porque o
`openpyxl` não grava o formato Strict.

## Estrutura

```
nucleo/        Java puro, sem Spring nem AWS (D-012, D-017); só depende do POI
  src/main/java/br/senai_pa3/
    dominio/     cálculo e regras metrológicas
    ingestao/    leitura e validação da planilha (Apache POI); Medidor (SHA-256 e tamanho)
  src/test/      testes do núcleo e planilhas sintéticas (publicadas como test-jar)
app-local/     tela e API da AV03 sobre o núcleo (Spring Boot)
  src/main/java/br/senai_pa3/
    aplicacao/   orquestração; SHA-256 e tamanho do arquivo no log
    web/         endpoint REST, DTOs e tratamento de erros
  src/main/resources/static/   interface (HTML, CSS e JavaScript, sem bibliotecas)
funcoes/       funções Lambda em Java: fn-ingestao, fn-certificado (PDF + QR), fn-api; JAR sombreado
web/           Plataforma Web (React + Vite): login, processamento, histórico, verificação pública
infra/         template SAM, fn-web (Node.js, serve a SPA) e scripts de deploy e de teste na nuvem
docs/decisoes.md             registro de decisões do projeto
docs/av02/                   relatório da AV02 (arquitetura em nuvem)
docs/av03/                   guia, contrato da planilha, oráculo e evidências de teste
docs/av04/                   relatório, matriz, evidências, roteiro do vídeo, guia e modelo de dados
diagramas/                   diagramas de arquitetura (.drawio, .png, .svg)
ferramentas/                 gerador das planilhas sintéticas e do PDF do relatório (relatorio/)
```

## Dados e LGPD

Todas as planilhas versionadas são sintéticas. Os arquivos operacionais cedidos pela Schulz
(planilhas de cálculo, relatório da MMC e certificado emitido) **não são versionados**: contêm
dados de clientes e dados pessoais de técnicos (nome e matrícula), risco apontado no próprio
diagnóstico da AV01 (RA-11, RA-12, RNF-07).

A aplicação não grava o nome nem o conteúdo do arquivo enviado. O log registra apenas o
SHA-256 e o tamanho, para rastreabilidade.

## Limitações conhecidas (AV04)

A tela local da AV03 (`app-local`) continua sem persistência nem login; na nuvem, a AV04 resolve os dois.
Ficam no roadmap ([D-018](docs/decisoes.md)): aprovação do signatário (RN-12), numeração sequencial e
S3 Object Lock, tabela de auditoria somente de inserção, incerteza de medição (R-46 a R-50), MFA e troca de
senha no primeiro acesso, região `sa-east-1` em conta paga. O histórico mostra só os 20 envios mais
recentes do usuário. Detalhes na §11 do relatório.

## Entregas

| #    | Tema                                                    | Data       | Status       |
| ---- | ------------------------------------------------------- | ---------- | ------------ |
| AV01 | Identificação do problema e levantamento de requisitos | 15/09/2026 | Entregue     |
| AV02 | Arquitetura em nuvem                                    | 02/10/2026 | Entregue     |
| AV03 | MVP parte 1 — aplicação transacional                    | 15/10/2026 | Entregue     |
| AV04 | MVP parte 2 — web/mobile e validação                    | 29/10/2026 | Código pronto; faltam deploy e vídeo |
| AV05 | Documentação técnica do MVP e ROI                       | 19/11/2026 | —            |
| AV06 | Pitch técnico-comercial                                 | 03/12/2026 | —            |
