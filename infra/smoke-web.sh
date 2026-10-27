#!/usr/bin/env bash
# Confere a interface publicada (T14, D-027) e grava as evidências CT-410 e CT-414 em
# docs/av04/evidencias/respostas/web-*.txt. Só curl, sem login: nada de JWT nem URL pré-assinada.
# Uso: infra/smoke-web.sh   (depois de infra/deploy.sh e infra/deploy-web.sh)
set -euo pipefail
cd "$(dirname "$0")/.."

PERFIL="${PERFIL:-pa3}"
REGIAO="${REGIAO:-us-east-2}"
STACK="${STACK:-pa3-av04}"
SAIDA=docs/av04/evidencias/respostas
mkdir -p "$SAIDA"
FALHAS=0

URL=$(aws --profile "$PERFIL" --region "$REGIAO" cloudformation describe-stacks --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='UrlPlataforma'].OutputValue" --output text)
URL="${URL%/}"
mascarar() { sed -E 's/[0-9]{12}/<conta>/g; s/^(x-amz-apigw-id|apigw-requestid|x-amzn-requestid):.*/\1: <omitido>/I'; }

confere() { # descrição, esperado, obtido
  if [ "$2" = "$3" ]; then echo "  ok   $1: $3"; else echo "  FALHA $1: esperado '$2', obtido '$3'"; FALHAS=$((FALHAS + 1)); fi
}
status() { curl -s -o /dev/null -w '%{http_code}' "$1"; }
cabecalho() { curl -s -D - -o /dev/null "$1" | tr -d '\r' | grep -i "^$2:" | head -1 | cut -d' ' -f2- ; }

echo "== Interface em $URL"
confere "GET / (HTTPS)" 200 "$(status "$URL/")"
confere "Content-Type do /" "text/html; charset=utf-8" "$(cabecalho "$URL/" content-type)"
confere "rota da SPA /verificar/<token> recebe o index.html" 200 "$(status "$URL/verificar/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")"
confere "asset inexistente" 404 "$(status "$URL/assets/nao-existe.js")"
confere "API continua com autorizador (GET /calibracoes sem token)" 401 "$(status "$URL/calibracoes")"
confere "verificação pública com token inexistente" 404 "$(status "$URL/verificacao/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")"
confere "HTTP simples não existe no API Gateway" 000 "$(curl -s -o /dev/null -m 10 -w '%{http_code}' "${URL/https:/http:}/" || true)"

ASSET=$(curl -s "$URL/" | grep -o '/assets/index-[A-Za-z0-9_-]*\.js' | head -1)
confere "asset JS do index.html" 200 "$(status "$URL$ASSET")"
confere "cache do asset" "public, max-age=31536000, immutable" "$(cabecalho "$URL$ASSET" cache-control)"

echo "== Cabeçalhos de segurança"
for c in content-security-policy strict-transport-security x-content-type-options referrer-policy x-frame-options; do
  v=$(cabecalho "$URL/" "$c")
  if [ -n "$v" ]; then echo "  ok   $c: $v"; else echo "  FALHA $c ausente"; FALHAS=$((FALHAS + 1)); fi
done

{
  echo "# CT-410 / CT-414 — interface servida pela fn-web ($(date -u +%Y-%m-%dT%H:%MZ))"
  echo "## GET /"
  curl -s -D - -o /dev/null "$URL/" | tr -d '\r' | mascarar
  echo "## GET /verificar/<token>"
  curl -s -D - -o /dev/null "$URL/verificar/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" | tr -d '\r' | head -1
  echo "## GET /calibracoes sem token"
  curl -s -i "$URL/calibracoes" | tr -d '\r' | head -1
} >"$SAIDA/web-interface.txt"

echo
if [ "$FALHAS" -eq 0 ]; then echo "Tudo certo. Evidência: $SAIDA/web-interface.txt"; else echo "$FALHAS falha(s)."; exit 1; fi
