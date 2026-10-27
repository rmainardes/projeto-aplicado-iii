# CLAUDE.md — Projeto Aplicado III (certificados de calibração, Schulz S.A.)

Projeto acadêmico em grupo (Grupo 39: Rodrigo e Nicolas). MVP que lê a planilha de medições, calcula média, erro
sistemático, status por ponto e parecer, e emite o certificado em PDF. Contexto de medical device /
ISO/IEC 17025: validação de entrada, tratamento de exceções e LGPD vêm antes de conveniência.

## Entrega em andamento

**AV04 — Plataforma Web e deploy na AWS (prazo qui 29/10/2026).** Guia mestre:
`docs/av04/guia-av04.md`. Cada sessão executa **uma** tarefa (`Txx`) do guia. Leia a seção da tarefa
e só os arquivos listados em **Contexto**; não leia o guia da AV03 inteiro nem os relatórios em
DOCX/PDF sem necessidade.

## Como trabalhar

- Português nas respostas; código, identificadores e termos técnicos em inglês quando forem do
  ecossistema. Direto: solução primeiro, justificativa depois.
- Cada tarefa tem um modo no guia:
  - 🧑‍🏫 **Instrutivo:** não escreva o código. Explique o conceito, faça no máximo 3 perguntas,
    deixe o Rodrigo escrever e revise o `git diff` com no máximo 3 pontos (✅ certo, 🔧 corrigir,
    📚 aprender). Ajuste mecânico depois de duas rodadas: pode aplicar e explicar.
  - 🛠 **Delegado:** escreva o código; mostre o diff e explique o que não for óbvio antes do commit.
- **Avise antes de adicionar qualquer biblioteca externa** (a lista aprovada está na D-019). Confira
  versões no Maven Central/npm no dia; nada de versão de memória.
- Afirmação sobre algo pós-2023 (Spring Boot 4, cotas e preços da AWS, runtimes do Lambda):
  verifique na documentação oficial e cite a URL.
- Commits e push: só quando o Rodrigo pedir. Mensagem em português, no imperativo.
- Decisão que fecha escopo ou arquitetura vira `D-0xx` em `docs/decisoes.md` (formato existente;
  decisão revista não é apagada, recebe status `Substituída`). As já tomadas não se reabrem sem
  motivo novo.

## Ao concluir uma tarefa

1. `./mvnw test` verde (e `npm run build` se mexeu em `web/`). Verde antigo não vale: rode de novo.
2. Confira o **Aceite** da tarefa, um item por vez, com comando ou evidência.
3. No guia: marque `[x]`, escreva a nota `> **Concluída em dd/mm.** ...` e atualize a linha do
   Registro de progresso.
4. Acrescente o trecho do relatório em `docs/av04/AV4_fonte.md`, na seção indicada em **Relatório**.
5. Proponha a mensagem de commit.

## Regras invioláveis 🔒

- Arquivos reais da Schulz (`*.xlsx`, `*.xlsm`, certificados em PDF da pasta-mãe) **nunca** entram
  no Git, em teste versionado, em log ou em evidência. Só planilhas sintéticas de `planilhas/`.
- Nunca gravar nem logar nome do arquivo enviado, conteúdo bruto, JWT, URL pré-assinada, chave de
  acesso ou número da conta AWS. Log: id, SHA-256, tamanho, resultado.
- Usuário nas tabelas só pelo `sub` do Cognito (opaco); nome de exibição só no PDF.
- `nucleo/` não importa Spring nem AWS (D-012). Domínio sem anotação de framework.
- Valores metrológicos em `BigDecimal`, comparação com `compareTo`, sem arredondar antes de
  comparar; média com escala 10 `HALF_EVEN`; 5 casas só na exibição.
- Os enums `DENTRO_DA_TOLERANCIA`, `FORA_DA_TOLERANCIA`, `APROVADO`, `REPROVADO` aparecem
  literalmente no código, na API e na tela.
- Erros HTTP em `application/problem+json`; 500 devolve só um `id` que liga ao log.
- Credenciais AWS só no perfil `pa3` do AWS CLI. Região `us-east-2` (D-022). Nada de NAT Gateway, KMS com
  chave própria, DynamoDB sob demanda, RDS ou recurso ligado 24 h (custo R$ 0,00, D-006/D-007/D-009).

## Stack e armadilhas conhecidas

- Java 17 (bytecode; JDK 21 local), Spring Boot 4.1.1, Maven Wrapper, Apache POI 5.5.1, Jackson 3.
- Boot 4: `@WebMvcTest`/`@AutoConfigureMockMvc` em `org.springframework.boot.webmvc.test.autoconfigure`;
  `@MockitoBean` em `org.springframework.test.context.bean.override.mockito`.
- MockMvc não aplica o limite do multipart (413 só se prova com `curl`) e não segue o *forward* da
  welcome page.
- `jsonPath` compara número como `double`: escala só se prova no texto cru da resposta.
- POI não lê OOXML Strict (R03). Contrato da planilha: `docs/av03/contrato-planilha.md` (R01–R15).
- Lambda: runtime `java21` com bytecode 17 (D-020); JAR sombreado do módulo `funcoes`.

## Comandos

```bash
./mvnw test                                  # todos os módulos
./mvnw -pl app-local -am spring-boot:run     # tela da AV03 em http://localhost:8080/
./mvnw -pl funcoes -am package               # JAR das funções Lambda
cd web && npm run dev                        # front-end contra a API na nuvem
infra/deploy.sh / infra/deploy-web.sh / infra/smoke.sh
```

## Mapa

- `docs/decisoes.md` — decisões D-001 em diante.
- `docs/av02/AV2_Grupo39_fonte.md` — arquitetura em nuvem (fluxo §1.1, serviços §1.2, cotas §2,
  pipeline §3.1, modelo DynamoDB §3.2, IAM e LGPD §4). Leia só a seção pedida.
- `docs/av03/` — contrato, oráculo, evidências e guia da AV03 (só como modelo).
- `docs/av04/` — guia, modelo de dados, evidências, matriz e fonte do relatório da AV04.
