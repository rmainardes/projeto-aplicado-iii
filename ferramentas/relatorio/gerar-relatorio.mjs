// Gera o relatório de uma entrega: docs/avNN/AVN_fonte.md → HTML → PDF.
//
// Uso (na raiz do repositório):
//   cd ferramentas/relatorio && npm ci && node gerar-relatorio.mjs        # AV04 (padrão)
//   cd ferramentas/relatorio && npm ci && node gerar-relatorio.mjs av05   # AV05
// Saída: docs/avNN/AVN_Projeto_Aplicado_III.pdf (e o .html intermediário, fora do Git).
//
// O PDF é impresso pelo Chrome ou Edge em modo headless (sem pandoc nem LibreOffice). Para usar outro
// navegador: NAVEGADOR="/caminho/do/chrome" node gerar-relatorio.mjs
// O marcador <!-- incluir: arquivo.md --> na fonte é trocado pelo arquivo (a matriz, na §10).
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { marked } from 'marked';

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const ENTREGA = (process.argv[2] || 'av04').toLowerCase();
if (!/^av0\d$/.test(ENTREGA)) {
  console.error(`Entrega inválida: ${ENTREGA} (use av04, av05...)`);
  process.exit(1);
}
const N = ENTREGA.slice(-1);
const PASTA = path.join(RAIZ, 'docs', ENTREGA);
const FONTE = path.join(PASTA, `AV${N}_fonte.md`);
const HTML = path.join(PASTA, `AV${N}_Projeto_Aplicado_III.html`);
const PDF = path.join(PASTA, `AV${N}_Projeto_Aplicado_III.pdf`);

function incluir(texto) {
  return texto.replace(/<!--\s*incluir:\s*([\w./-]+)\s*-->/g, (_, arquivo) => {
    const incluido = readFileSync(path.join(PASTA, arquivo), 'utf8')
      .replace(/^# .*\n/m, '') // o título do arquivo já é o da seção
      .replace(/^(#{2,5}) /gm, '#$1 '); // um nível abaixo da seção que o inclui
    return incluido.trim();
  });
}

function semComentarios(texto) {
  return texto.replace(/<!--[\s\S]*?-->/g, '');
}

const CSS = `
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10pt; line-height: 1.45; color: #1f2937; }
h1 { font-size: 18pt; color: #1e3a8a; margin: 0 0 4pt; }
h2 { font-size: 13.5pt; color: #1e3a8a; border-bottom: 1.5px solid #1d4ed8; padding-bottom: 2pt; margin-top: 18pt; break-after: avoid; }
h3 { font-size: 11.5pt; color: #1e3a8a; margin-top: 12pt; break-after: avoid; }
h4 { font-size: 10.5pt; margin-top: 10pt; break-after: avoid; }
p { text-align: justify; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 8.3pt; break-inside: auto; }
tr { break-inside: avoid; }
th, td { border: 1px solid #cbd5e1; padding: 3pt 4pt; vertical-align: top; text-align: left; }
th { background: #f1f5f9; }
code { font-family: Consolas, "Courier New", monospace; font-size: 8.5pt; background: #f1f5f9; padding: 0 2px; overflow-wrap: anywhere; }
pre { background: #f8fafc; border: 1px solid #e2e8f0; padding: 6pt; font-size: 7.6pt; line-height: 1.3; white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; padding: 0; font-size: inherit; }
a { color: #1d4ed8; overflow-wrap: anywhere; }
img { max-width: 100%; max-height: 105mm; display: block; margin: 6pt auto 2pt; border: 1px solid #e2e8f0; }
img + em, p > em:only-child { display: block; text-align: center; font-size: 8.5pt; color: #4b5563; }
h1 + p + table td:first-child { width: 28%; }
h1 + p + table th { display: none; }
`;

const markdown = semComentarios(incluir(readFileSync(FONTE, 'utf8')));
const corpo = marked.parse(markdown, { gfm: true });
const documento = `<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>AV0${N} — Projeto Aplicado III — Grupo 39</title>
<style>${CSS}</style></head>
<body>${corpo}</body></html>`;
writeFileSync(HTML, documento);
console.log(`HTML: ${path.relative(RAIZ, HTML)}`);

const candidatos = [
  process.env.NAVEGADOR,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
].filter(Boolean);
const navegador = candidatos.find((c) => existsSync(c));
if (!navegador) {
  console.error('Chrome/Edge não encontrado. Abra o HTML e imprima em PDF, ou defina NAVEGADOR.');
  process.exit(1);
}
execFileSync(navegador, [
  '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
  `--print-to-pdf=${PDF}`, pathToFileURL(HTML).href,
], { stdio: 'ignore' });
console.log(`PDF:  ${path.relative(RAIZ, PDF)}`);
