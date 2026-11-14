'use strict';

// Página pública de verificação. O hash do PDF é calculado no próprio aparelho quando o navegador
// oferece Web Crypto (localhost ou HTTPS); pela rede local em HTTP, o navegador do celular não
// oferece, e o PDF é conferido pelo servidor.

const $ = (id) => document.getElementById(id);
const ROTULOS = { APROVADO: 'Aprovado', REPROVADO: 'Reprovado' };
const token = decodeURIComponent(location.pathname.split('/').pop() || '');
let registrado = null;

function aviso(id, texto, erro = false) {
  const m = $(id);
  m.textContent = texto;
  m.classList.toggle('erro', erro);
}

async function consultar() {
  try {
    const resposta = await fetch(`/api/verificacao/${encodeURIComponent(token)}`);
    if (!resposta.ok) {
      aviso('mensagem', 'Certificado não encontrado. Confira o QR Code ou o endereço.', true);
      return;
    }
    const c = await resposta.json();
    registrado = c.sha256Pdf;
    $('secao-certificado').className = `parecer ${c.parecer === 'APROVADO' ? 'ok' : 'falha'}`;
    $('parecer-enum').textContent = c.parecer;
    $('parecer-rotulo').textContent = ROTULOS[c.parecer] || '';
    $('dado-id').textContent = c.id;
    $('dado-emissao').textContent = new Date(c.emitidoEm).toLocaleString('pt-BR');
    $('dado-hash').textContent = c.sha256Pdf;
    $('secao-certificado').hidden = false;
    $('form-conferir').hidden = false;
    aviso('mensagem', 'Certificado autêntico: emitido por este sistema e registrado.');
  } catch {
    aviso('mensagem', 'Não foi possível consultar o servidor.', true);
  }
}

async function hashLocal(arquivo) {
  const bytes = await arquivo.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('');
}

async function conferir(evento) {
  evento.preventDefault();
  const arquivo = $('arquivo').files[0];
  if (!arquivo) return;
  try {
    let confere;
    if (window.isSecureContext && crypto.subtle) {
      confere = (await hashLocal(arquivo)) === registrado;
    } else {
      const dados = new FormData();
      dados.append('arquivo', arquivo);
      const resposta = await fetch(`/api/verificacao/${encodeURIComponent(token)}/conferencia`,
        { method: 'POST', body: dados });
      confere = resposta.ok && (await resposta.json()).confere;
    }
    if (confere) {
      aviso('resultado-conferencia', 'O arquivo confere: é idêntico ao certificado emitido.');
    } else {
      aviso('resultado-conferencia', 'O arquivo NÃO confere: foi alterado ou não é este certificado.', true);
    }
  } catch {
    aviso('resultado-conferencia', 'Não foi possível conferir o arquivo.', true);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  $('form-conferir').addEventListener('submit', conferir);
  consultar();
});
