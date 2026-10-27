#!/usr/bin/env bash
# Publica a interface (T14): gera web/.env das saídas do stack, compila a SPA e sincroniza web/dist
# com o bucket web privado, que a fn-web serve pelo HTTP API (D-027). Rode depois de infra/deploy.sh.
# Credenciais só pelo perfil pa3 (D-022).
set -euo pipefail
cd "$(dirname "$0")/.."

PERFIL="${PERFIL:-pa3}"
REGIAO="${REGIAO:-us-east-2}"
STACK="${STACK:-pa3-av04}"
export PERFIL REGIAO STACK

saida() {
  aws --profile "$PERFIL" --region "$REGIAO" cloudformation describe-stacks --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

BUCKET_WEB=$(saida BucketWeb)
URL=$(saida UrlPlataforma)
if [ -z "$BUCKET_WEB" ] || [ "$BUCKET_WEB" = "None" ] || [ -z "$URL" ] || [ "$URL" = "None" ]; then
  echo "Saídas BucketWeb/UrlPlataforma ausentes: rode infra/deploy.sh primeiro." >&2
  exit 1
fi

infra/gerar-env-web.sh
(cd web && npm ci && npm run build)

# Assets primeiro e index.html por último: quem abrir a página no meio do envio não pega um
# index.html apontando para um asset que ainda não chegou. --delete remove os assets antigos.
aws --profile "$PERFIL" --region "$REGIAO" s3 sync web/dist "s3://$BUCKET_WEB" --exclude index.html --delete --only-show-errors
aws --profile "$PERFIL" --region "$REGIAO" s3 cp web/dist/index.html "s3://$BUCKET_WEB/index.html" \
  --content-type 'text/html; charset=utf-8' --only-show-errors

# Conferência: a raiz tem de responder 200 com HTML.
STATUS=$(curl -s -o /dev/null -w '%{http_code}' "$URL")
echo "Interface publicada: $URL (HTTP $STATUS)"
[ "$STATUS" = "200" ]
