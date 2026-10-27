// Testes da fn-web sem AWS: node --test infra/fn-web/
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { chaveDe, handler, tratar } from './index.mjs';

const ARQUIVOS = {
  'index.html': Buffer.from('<!doctype html><title>SPA</title>'),
  'assets/index-abc123.js': Buffer.from('console.log(1)'),
  'favicon.png': Buffer.from([0x89, 0x50, 0x4e, 0x47]),
};
const lerFalso = async (chave) => ARQUIVOS[chave] ?? null;
const get = (rawPath) => ({ rawPath, requestContext: { http: { method: 'GET' } } });

test('rotas da SPA recebem o index.html', () => {
  assert.deepEqual(chaveDe('/'), { chave: 'index.html', spa: true });
  assert.deepEqual(chaveDe('/verificar/AbCdEf0123456789AbCdEf0123456789'), { chave: 'index.html', spa: true });
  assert.deepEqual(chaveDe('/assets/index-abc123.js'), { chave: 'assets/index-abc123.js', spa: false });
});

test('caminho com .. ou barra dupla é recusado', () => {
  assert.equal(chaveDe('/assets/../segredo.txt'), null);
  assert.equal(chaveDe('/assets//x.js'), null);
});

test('serve o index.html com no-cache e cabeçalhos de segurança', async () => {
  const r = await tratar(get('/verificar/qualquer'), lerFalso);
  assert.equal(r.statusCode, 200);
  assert.equal(r.headers['Content-Type'], 'text/html; charset=utf-8');
  assert.equal(r.headers['Cache-Control'], 'no-cache');
  assert.equal(r.headers['Referrer-Policy'], 'no-referrer');
  assert.match(r.headers['Content-Security-Policy'], /frame-ancestors 'none'/);
  assert.equal(r.isBase64Encoded, false);
  assert.match(r.body, /SPA/);
});

test('asset com hash recebe cache longo', async () => {
  const r = await tratar(get('/assets/index-abc123.js'), lerFalso);
  assert.equal(r.statusCode, 200);
  assert.match(r.headers['Cache-Control'], /immutable/);
  assert.equal(r.headers['Content-Type'], 'text/javascript; charset=utf-8');
});

test('binário vai em base64', async () => {
  const r = await tratar(get('/favicon.png'), lerFalso);
  assert.equal(r.isBase64Encoded, true);
  assert.deepEqual(Buffer.from(r.body, 'base64'), ARQUIVOS['favicon.png']);
});

test('asset inexistente → 404; SPA não publicada → 404 com instrução', async () => {
  assert.equal((await tratar(get('/assets/nao-existe.js'), lerFalso)).statusCode, 404);
  const vazio = await tratar(get('/'), async () => null);
  assert.equal(vazio.statusCode, 404);
  assert.match(vazio.body, /deploy-web/);
});

test('% malformado → 404; método diferente de GET → 405', async () => {
  assert.equal((await tratar(get('/%E0%A4%A'), lerFalso)).statusCode, 404);
  const post = { rawPath: '/', requestContext: { http: { method: 'POST' } } };
  assert.equal((await tratar(post, lerFalso)).statusCode, 405);
});

test('falha do S3 → 500 sem detalhe', async () => {
  const original = console.error;
  console.error = () => {};
  try {
    const r = await tratar(get('/'), async () => { throw Object.assign(new Error('x'), { name: 'AccessDenied' }); });
    assert.equal(r.statusCode, 500);
    assert.doesNotMatch(r.body, /AccessDenied/);
  } finally {
    console.error = original;
  }
});

test('handler exportado aceita só (evento, contexto): o terceiro argumento do runtime é o callback', () => {
  assert.ok(handler.length <= 2);
});
