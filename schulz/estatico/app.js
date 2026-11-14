'use strict';

// Interface da versão local. Sem bibliotecas; todo texto vindo da API entra por textContent
// (nunca innerHTML), então nome de característica com "<" não vira marcação.

const ROTULOS = {
  APROVADO: 'Aprovado',
  REPROVADO: 'Reprovado',
  DENTRO_DA_TOLERANCIA: 'Dentro da tolerância',
  FORA_DA_TOLERANCIA: 'Fora da tolerância',
  EMITIDA: 'Certificado emitido',
  REJEITADA: 'Planilha rejeitada',
  DUPLICADA: 'Arquivo já enviado',
};
const MINUTOS_MANUAL = 53; // esforço manual por certificado: soma das etapas P-06 a P-18 da AV01

const $ = (id) => document.getElementById(id);

function el(tag, texto, classe) {
  const e = document.createElement(tag);
  if (texto !== undefined && texto !== null) e.textContent = texto;
  if (classe) e.className = classe;
  return e;
}

function selo(valor) {
  const ok = valor === 'APROVADO' || valor === 'DENTRO_DA_TOLERANCIA';
  const span = el('span', null, `status ${ok ? 'ok' : 'falha'}`);
  span.append(el('span', valor, 'enum'), el('span', ROTULOS[valor] || '', 'rotulo'));
  return span;
}

function mensagem(texto, erro = false) {
  const m = $('mensagem');
  m.textContent = texto || '';
  m.classList.toggle('erro', erro);
}

function limparResultado() {
  ['secao-parecer', 'secao-tabela', 'secao-erros'].forEach((id) => { $(id).hidden = true; });
  $('tabela-pontos').tBodies[0].replaceChildren();
  $('tabela-erros').tBodies[0].replaceChildren();
  mensagem('');
}

function mostrarPontos(pontos) {
  const corpo = $('tabela-pontos').tBodies[0];
  pontos.forEach((p, i) => {
    const tr = document.createElement('tr');
    tr.append(
      el('td', String(i + 1), 'num'),
      el('td', p.caracteristica),
      el('td', p.leituras.join('; ')),
      el('td', p.exibicao.media, 'num'),
      el('td', p.exibicao.valorReferencia, 'num'),
      el('td', p.exibicao.erroSistematico, 'num'),
      el('td', p.exibicao.lea, 'num'),
    );
    const td = document.createElement('td');
    td.append(selo(p.status));
    tr.append(td);
    corpo.append(tr);
  });
  $('secao-tabela').hidden = false;
}

function mostrarErros(erros) {
  const corpo = $('tabela-erros').tBodies[0];
  erros.forEach((e) => {
    const tr = document.createElement('tr');
    tr.append(el('td', e.linha ?? '—'), el('td', e.coluna ?? '—'), el('td', e.regra, 'enum'), el('td', e.mensagem));
    corpo.append(tr);
  });
  $('secao-erros').hidden = false;
}

function mostrarEmitida(r) {
  const secao = $('secao-parecer');
  const aprovado = r.parecer === 'APROVADO';
  secao.className = `parecer ${aprovado ? 'ok' : 'falha'}`;
  $('parecer-enum').textContent = r.parecer;
  $('parecer-rotulo').textContent = ROTULOS[r.parecer];
  $('link-certificado').href = r.certificado.url;
  $('link-verificacao').href = r.certificado.urlVerificacao;
  const segundos = (r.duracaoMs / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 2 });
  $('ganho').textContent = `Validado, calculado e emitido em ${segundos} s. `
    + `No fluxo manual (AV01), o mesmo certificado consome cerca de ${MINUTOS_MANUAL} minutos de transcrição e conferência.`;
  secao.hidden = false;
  mostrarPontos(r.pontos);
}

async function lerJson(resposta) {
  try {
    return await resposta.json();
  } catch {
    return null;
  }
}

async function enviar(evento) {
  evento.preventDefault();
  const arquivo = $('arquivo').files[0];
  if (!arquivo) return;
  limparResultado();
  const botao = $('botao-enviar');
  botao.disabled = true;
  botao.textContent = 'Processando…';
  try {
    const dados = new FormData();
    dados.append('arquivo', arquivo);
    const resposta = await fetch('/api/calibracoes/processamento', { method: 'POST', body: dados });
    const corpo = await lerJson(resposta);
    if (resposta.ok && corpo) {
      if (corpo.estado === 'EMITIDA') {
        mensagem(`Certificado emitido. Identificador: ${corpo.id}`);
        mostrarEmitida(corpo);
      } else if (corpo.estado === 'DUPLICADA') {
        const o = corpo.original;
        mensagem(`Este arquivo já foi enviado (mesmo SHA-256). Nenhum certificado novo foi gerado; `
          + `exibindo o envio original ${corpo.idOriginal}.`);
        if (o && o.estado === 'EMITIDA') mostrarEmitida(o);
        if (o && o.estado === 'REJEITADA') mostrarErros(o.erros);
      }
    } else if (resposta.status === 400 && corpo && corpo.erros) {
      mensagem(`${corpo.title}: ${corpo.detail}`, true);
      mostrarErros(corpo.erros);
    } else if (corpo && corpo.detail) {
      mensagem(`${corpo.detail}${corpo.id ? ` (id ${corpo.id})` : ''}`, true);
    } else {
      mensagem(`Falha inesperada (HTTP ${resposta.status}).`, true);
    }
  } catch {
    mensagem('Não foi possível falar com o servidor. Ele ainda está aberto?', true);
  } finally {
    botao.disabled = false;
    botao.textContent = 'Processar';
  }
}

async function carregarHistorico() {
  const resposta = await fetch('/api/calibracoes');
  const corpo = await lerJson(resposta);
  if (!resposta.ok || !corpo) return;
  const nomes = {
    envios: 'Envios', emitidos: 'Certificados emitidos', aprovados: 'APROVADO', reprovados: 'REPROVADO',
    rejeitadas: 'Planilhas rejeitadas', duplicadas: 'Reenvios bloqueados',
  };
  const caixa = $('indicadores');
  caixa.replaceChildren(...Object.entries(nomes).map(([chave, nome]) => {
    const d = el('div', null, 'indicador');
    d.append(el('span', String(corpo.indicadores[chave]), 'valor'), el('span', nome, 'nome'));
    return d;
  }));
  const tbody = $('tabela-historico').tBodies[0];
  tbody.replaceChildren(...corpo.calibracoes.map((c) => {
    const tr = document.createElement('tr');
    const data = new Date(c.criadoEm).toLocaleString('pt-BR');
    const tdParecer = document.createElement('td');
    if (c.parecer) tdParecer.append(selo(c.parecer)); else tdParecer.textContent = '—';
    const tdCert = document.createElement('td');
    if (c.certificado) {
      const a = el('a', 'PDF', 'secundario-link');
      a.href = c.certificado.url;
      tdCert.append(a);
    } else {
      tdCert.textContent = c.estado === 'REJEITADA' ? `${c.quantidadeErros} erro(s)` : '—';
    }
    tr.append(el('td', data), el('td', c.estado, 'enum'), tdParecer,
      el('td', `${c.sha256Planilha.slice(0, 16)}…`, 'hash'), el('td', `${c.duracaoMs} ms`, 'num'), tdCert);
    return tr;
  }));
}

async function carregarExemplos() {
  const resposta = await fetch('/api/exemplos');
  const corpo = await lerJson(resposta);
  if (!resposta.ok || !corpo) return;
  $('lista-exemplos').replaceChildren(...corpo.exemplos.map((e) => {
    const li = document.createElement('li');
    const a = el('a', e.nome, 'secundario-link');
    a.href = e.url;
    li.append(a);
    return li;
  }));
}

function trocarAba(alvo) {
  document.querySelectorAll('nav.abas [role="tab"]').forEach((aba) => {
    const ativa = aba.id === alvo;
    aba.setAttribute('aria-selected', String(ativa));
    $(aba.getAttribute('aria-controls')).hidden = !ativa;
  });
  if (alvo === 'aba-historico') carregarHistorico();
  if (alvo === 'aba-exemplos') carregarExemplos();
}

document.addEventListener('DOMContentLoaded', () => {
  $('form-planilha').addEventListener('submit', enviar);
  document.querySelectorAll('nav.abas [role="tab"]').forEach((aba) => {
    aba.addEventListener('click', () => trocarAba(aba.id));
  });
});
