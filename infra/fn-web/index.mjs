// fn-web (D-027): serve a SPA (web/dist) a partir do bucket web privado, pelo próprio HTTP API.
// Substitui o CloudFront da D-016, que no plano gratuito exige WAF em us-east-1 (D-026).
//
// Só lê o bucket web. Caminho sem extensão é rota da SPA (/, /verificar/<token>) e recebe o
// index.html; arquivo inexistente com extensão recebe 404. Nada de log de caminho: a rota
// /verificar/<token> carrega o token do certificado.
//
// O SDK v3 já vem no runtime nodejs22.x: nenhuma dependência é empacotada. É importado sob
// demanda para o teste (index.test.mjs) rodar sem ele, com um leitor falso.
let leitorS3;

/** Lê um objeto do bucket web; devolve Buffer ou null se a chave não existe. */
async function lerDoBucket(chave) {
  if (!leitorS3) {
    const { GetObjectCommand, S3Client } = await import('@aws-sdk/client-s3');
    const cliente = new S3Client({});
    leitorS3 = { cliente, GetObjectCommand };
  }
  try {
    const objeto = await leitorS3.cliente.send(
      new leitorS3.GetObjectCommand({ Bucket: process.env.BUCKET_WEB, Key: chave }));
    return Buffer.from(await objeto.Body.transformToByteArray());
  } catch (e) {
    if (e?.name === 'NoSuchKey' || e?.$metadata?.httpStatusCode === 404) {
      return null;
    }
    throw e;
  }
}

const TIPOS = {
  html: 'text/html; charset=utf-8',
  js: 'text/javascript; charset=utf-8',
  css: 'text/css; charset=utf-8',
  json: 'application/json; charset=utf-8',
  svg: 'image/svg+xml',
  png: 'image/png',
  ico: 'image/x-icon',
  txt: 'text/plain; charset=utf-8',
  woff2: 'font/woff2',
};
const TEXTO = new Set(['html', 'js', 'css', 'json', 'svg', 'txt']);

// connect-src: a própria API (mesma origem), o Cognito e os buckets por URL pré-assinada.
const CABECALHOS_SEGURANCA = {
  'Content-Security-Policy': [
    "default-src 'self'",
    "connect-src 'self' https://*.amazonaws.com",
    "img-src 'self' data: blob:",
    "style-src 'self'",
    "script-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
  ].join('; '),
  'Strict-Transport-Security': 'max-age=31536000',
  'X-Content-Type-Options': 'nosniff',
  // O token de verificação está no caminho: não vaza por Referer.
  'Referrer-Policy': 'no-referrer',
  'X-Frame-Options': 'DENY',
};

/** Caminho da requisição → chave no bucket. Exportada para o teste. */
export function chaveDe(caminho) {
  const limpo = decodeURIComponent(caminho || '/').replace(/^\/+/, '');
  const ultimo = limpo.split('/').pop();
  if (limpo === '' || !ultimo.includes('.')) {
    return { chave: 'index.html', spa: true };
  }
  // Chave de S3 é literal ("../" não sai do bucket), mas recusamos para não confundir ninguém.
  if (limpo.split('/').some((parte) => parte === '..' || parte === '')) {
    return null;
  }
  return { chave: limpo, spa: false };
}

function extensao(chave) {
  return chave.slice(chave.lastIndexOf('.') + 1).toLowerCase();
}

function resposta(status, corpo, cabecalhos = {}) {
  return {
    statusCode: status,
    headers: { 'Content-Type': 'text/plain; charset=utf-8', ...CABECALHOS_SEGURANCA, ...cabecalhos },
    body: corpo,
  };
}

/** Lógica da função; o leitor é injetável para o teste. */
export async function tratar(evento, ler) {
  if (evento.requestContext?.http?.method !== 'GET') {
    return resposta(405, 'Método não permitido.');
  }
  let alvo;
  try {
    alvo = chaveDe(evento.rawPath);
  } catch {
    alvo = null; // decodeURIComponent com % malformado
  }
  if (!alvo) {
    return resposta(404, 'Não encontrado.');
  }
  try {
    const bytes = await ler(alvo.chave);
    if (bytes === null) {
      return resposta(404, alvo.spa ? 'Interface não publicada. Rode infra/deploy-web.sh.' : 'Não encontrado.');
    }
    const ext = extensao(alvo.chave);
    // index.html sempre revalida (aponta para os assets com hash); assets do Vite têm hash no nome.
    const cache = alvo.chave.startsWith('assets/') ? 'public, max-age=31536000, immutable' : 'no-cache';
    const texto = TEXTO.has(ext);
    return {
      statusCode: 200,
      headers: {
        ...CABECALHOS_SEGURANCA,
        'Content-Type': TIPOS[ext] ?? 'application/octet-stream',
        'Cache-Control': cache,
      },
      body: texto ? bytes.toString('utf8') : bytes.toString('base64'),
      isBase64Encoded: !texto,
    };
  } catch (e) {
    console.error(JSON.stringify({ erro: e?.name ?? 'desconhecido' }));
    return resposta(500, 'Erro ao carregar a interface.');
  }
}

// Só (evento, contexto): o runtime nodejs passa o callback como terceiro argumento, e um parâmetro
// extra com valor padrão receberia o callback no lugar do leitor do S3.
export const handler = (evento) => tratar(evento, lerDoBucket);
