# Evidências da AV04 — casos de teste na nuvem e na tela

**Linha de base.** Stack `pa3-av04`, região `us-east-2`, conta dedicada no plano gratuito (D-006, D-022).
Back-end implantado em 25/10/2026 (T08) e reimplantado na T12; interface servida pela `fn-web` a partir
da versão que introduz a D-027 (27/10/2026). Registre aqui o commit e a data do último deploy:

| Item | Valor |
| --- | --- |
| Commit implantado | `219631f` |
| Data do deploy (`infra/deploy.sh` + `infra/deploy-web.sh`) | 27/10/2026 |
| URL da plataforma (saída `UrlPlataforma`) | https://n0jdkil21h.execute-api.us-east-2.amazonaws.com/ |

🔒 Nenhuma evidência traz JWT, URL pré-assinada, token de verificação real, número da conta, e-mail
pessoal ou dado real da Schulz. As respostas gravadas pelos scripts passam por `jq`/`sed` antes de irem ao
disco.

## Testes automatizados (sem AWS)

| Suíte | Comando | Resultado (27/10/2026) |
| --- | --- | --- |
| Java (`nucleo`, `app-local`, `funcoes`) | `./mvnw test` | 154 testes, 0 falhas, 1 pulado (69 + 15 + 70) |
| `fn-web` | `node --test infra/fn-web/index.test.mjs` | 8 testes, 0 falhas |
| Front-end | `cd web && npm run build` | build sem erro (Vite 8.3.5) |

O teste pulado (`PoiStrictTest.xssfWorkbookRecusaStrictReal`) depende de uma planilha real da empresa,
mantida fora do Git; a mesma verificação roda com `inv-R03-strict.xlsx`.

## Casos de teste na nuvem

| ID | Cenário | Como reproduzir | Esperado | Evidência | Situação |
| --- | --- | --- | --- | --- | --- |
| CT-401 | Envio normal (`ok-reprovado.xlsx`) até `EMITIDA` | `infra/smoke.sh` | `EMITIDA`, `REPROVADO`, um ponto `FORA_DA_TOLERANCIA` | `respostas/cenario1-*.txt` | ✅ 25/10 |
| CT-402 | Download do PDF com "Gerado por" do Cognito | `infra/smoke.sh` | 200, `%PDF-`, nome lido por `AdminGetUser` | `respostas/certificado-nuvem.pdf` | ✅ 25/10 |
| CT-403 | Verificação pública sem login | `infra/smoke.sh` | 200; `sha256Pdf` = SHA-256 do PDF baixado; sem `sub` | `respostas/cenario1-4-verificacao.txt` | ✅ 25/10 |
| CT-404 | Mesmo arquivo de novo (idempotência, RN-20) | `infra/smoke.sh` | `DUPLICADA`; `/pdf` → 409 | `respostas/cenario2-*.txt` | ✅ 25/10 |
| CT-405 | Planilha inválida (`inv-multiplos-erros.xlsx`) | `infra/smoke.sh` | `REJEITADA` com R10, R11, R14 | `respostas/cenario3-*.txt` | ✅ 25/10 |
| CT-406 | Sem token e com token inválido | `infra/smoke.sh` | 401 na borda | `respostas/cenario4-sem-token.txt` | ✅ 25/10 |
| CT-407 | Id inexistente; arquivo acima de 5 MB | `infra/smoke.sh` | 404; 413 | `respostas/cenario5-*.txt` | ✅ 25/10 |
| CT-408 | Dois envios simultâneos do mesmo hash | `infra/smoke.sh` | um `EMITIDA` e um `DUPLICADA` | `respostas/cenario6-simultaneos.txt` | ✅ 25/10 |
| CT-409 | Logs sem dado pessoal | CloudWatch, grupo `/aws/lambda/pa3-av04-fn-ingestao` | só `uploadId`, SHA-256, bytes, resultado | `respostas/log-fn-ingestao.txt` | ✅ 25/10 |
| CT-410 | Interface servida pela `fn-web` em HTTPS | `infra/smoke-web.sh` | `/` e `/verificar/<token>` → 200 HTML; asset inexistente → 404; HTTP simples recusado | `respostas/web-interface.txt` | ✅ 27/10 |
| CT-411 | Histórico e indicadores de gestão | Tela, aba **Histórico** | lista do mais recente ao mais antigo; indicadores batem com a lista | `respostas/t12-historico.txt`, `tela/t12-*.jpg` | ✅ 25/10 (lista); ⏳ indicadores na nuvem |
| CT-412 | QR Code do PDF aberto no celular por 4G | Ler o QR do certificado emitido | página `/verificar/<token>` com parecer e hash; conferência do PDF → "Arquivo íntegro" | print do celular / vídeo | ⏳ após o deploy da D-027 |
| CT-413 | Tablet (768 px) e celular (375 px) | DevTools | sem rolagem lateral; alvos de 44 px | `tela/t11-7-tablet-768.jpg`, `tela/t12-5-lista-736px.jpg` | ✅ 25/10 (tablet); ✅ 27/10 (verificação a 375 px, local) |
| CT-414 | Cabeçalhos de segurança da interface | `infra/smoke-web.sh` | CSP, HSTS, `nosniff`, `no-referrer`, `DENY` | `respostas/web-interface.txt` | ✅ 27/10 |
| CT-415 | Custo dentro do plano gratuito | Console: *Billing → Free Tier*, *Cost Explorer* | US$ 0,00 faturado; só consumo de créditos | print em `tela/` | ⏳ |
| CT-416 | Ciclo de vida de 5 anos (DE-04) | `aws s3api get-bucket-lifecycle-configuration` | `GLACIER_IR` aos 365 d; expiração aos 1 825 d | relatório §6 (T08) | ✅ 25/10 |
| CT-417 | URL pré-assinada expirada | Repetir o `PUT` 6 min depois do `POST /uploads` | 403 do S3 (`Request has expired`) | — | ⏳ opcional |
| CT-418 | Envio de outro usuário | `FnApiTest` (`estado_deOutroSubOuInexistente_ambos404IguaisSem403`) | 404 idêntico ao inexistente | `./mvnw test` | ✅ 27/10 |

**Como fechar os ⏳:** depois do deploy, rode `infra/smoke.sh` (refaz CT-401 a CT-408), `infra/smoke-web.sh`
(CT-410 e CT-414), abra a URL da plataforma numa aba anônima, processe `ok-aprovado.xlsx`, baixe o PDF e
leia o QR com o celular fora do Wi-Fi (CT-412). Grave essas etapas no vídeo (roteiro em
[`roteiro-video.md`](roteiro-video.md)) e tire o print do painel do plano gratuito (CT-415).
