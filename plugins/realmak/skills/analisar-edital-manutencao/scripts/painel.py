"""Painel HTML da análise de manutenção: abas, busca, filtros e ordenação.

Arquivo único, sem dependências externas; abre no modo claro e tem botão para o modo escuro.
"""

import html as _html
import json
import re

html_esc = _html.escape


def build(D, calc, destino):
    from relatorio import _fmt_campos

    tabelas = {
        "requisitos": {
            "titulo": "Matriz de requisitos de execução",
            "cols": [
                ["ID", "id"],
                ["Grupo", "chip"],
                ["Requisito", "texto"],
                ["Onde consta", "texto"],
                ["Periodicidade", "filtro"],
                ["Custo afetado", "texto"],
                ["Risco", "risco"],
                ["Pendência", "filtro"],
            ],
            "linhas": [[r[0], r[1], r[2], r[3], r[6], r[7], r[8], r[9]] for r in D["requisitos"]],
        },
        "escopo": {
            "titulo": "Atividades e horas por ano",
            "cols": [
                ["Bloco", "chip"],
                ["Tipo de carga", "chip"],
                ["Atividade", "texto"],
                ["Requisito", "texto"],
                ["Freq./ano", "num"],
                ["Volume", "num"],
                ["Tempo (h)", "num"],
                ["Horas/ano", "barra"],
                ["Profissional", "filtro"],
            ],
            "linhas": [
                [e[0], e[1], e[2], e[3], e[4], e[5], e[7], h, e[8] if len(e) > 8 else ""]
                for e, h in zip(D["escopo"], calc["horas"], strict=False)
            ],
            "soma": [7],
        },
        "pecas": {
            "titulo": "Peças, insumos e materiais",
            "cols": [
                ["Item", "texto"],
                ["Tipo", "chip"],
                ["Requisito", "texto"],
                ["Como é pago", "pago"],
                ["Regra do edital", "texto"],
                ["Observação", "texto"],
            ],
            "linhas": [[p[0], p[1], p[2], p[3], p[7], p[8]] for p in D["pecas"]],
        },
        "premissas": {
            "titulo": "Premissas do dimensionamento",
            "cols": [
                ["Premissa", "texto"],
                ["Valor", "texto"],
                ["Tipo", "chip"],
                ["O que muda se estiver errada", "texto"],
            ],
            "linhas": [list(p) for p in D["premissas"]],
        },
        "pontos": {
            "titulo": "Pontos de atenção, divergências e pendências",
            "cols": [
                ["Nº", "id"],
                ["Tipo", "chip"],
                ["Ponto de atenção", "texto"],
                ["Onde consta", "texto"],
                ["Impacto", "texto"],
                ["Providência", "texto"],
                ["Prazo", "filtro"],
            ],
            "linhas": [list(p) for p in D["pontos"]],
        },
        "documentos": {
            "titulo": "Documentos analisados",
            "cols": [
                ["ID", "id"],
                ["Documento", "texto"],
                ["Tipo", "chip"],
                ["Origem", "texto"],
                ["Data", "texto"],
            ],
            "linhas": [list(x) for x in D["documentos"]],
        },
        "checks": {
            "titulo": "Controles de integridade",
            "cols": [["Verificação", "texto"], ["Ocorrências", "num"], ["Situação", "status"]],
            "linhas": [list(c) for c in calc["checks"]],
        },
    }
    servico, grupo = [], ""
    for x in D["dados_servico"]:
        if isinstance(x, str):
            grupo = re.sub(r"^[A-Z]\.\s*", "", x)
        else:
            servico.append([grupo] + list(x))
    chaves = (
        "ident",
        "conclusao",
        "justificativa",
        "condicoes",
        "riscos",
        "decisoes",
        "conclusao_equipe",
        "testes",
        "base_carga",
        "equipe",
        "escopo_na",
        "pilulas",
        "prazos",
        "kpis_extras",
    )
    dados = {
        "D": {k: D.get(k) for k in chaves},
        "num": calc["num"],
        "carga": calc["carga"],
        "ciclo": calc["ciclo"],
        "tabelas": tabelas,
        "inventarios": calc["inventarios"],
        "servico": servico,
        "leitura": [[a, _fmt_campos(t, calc)] for a, t in D["leitura_rapida"]],
        "chave": D.get("id", "analise"),
    }
    titulo = D.get("titulo_pagina", "Análise de manutenção")
    html = APP.replace(
        "/*DADOS*/",
        "const DADOS=" + json.dumps(dados, ensure_ascii=False).replace("</", "<\\/") + ";",
    ).replace("{{TITULO}}", html_esc(titulo))
    with open(destino, "w", encoding="utf-8") as arq:
        arq.write(html)


APP = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{TITULO}}</title>
<style>
:root{--pet:#164e63;--verde:#0f766e;--azul:#bae6fd;--azul2:#e0f2fe;--fundo:#f1f5f9;--card:#fff;--linha:#e2e8f0;--tx:#1f2937;--tx2:#64748b;
 --ok:#166534;--okbg:#dcfce7;--md:#9a3412;--mdbg:#ffedd5;--al:#991b1b;--albg:#fee2e2;--amar:#fff2cc;--sombra:0 1px 2px rgba(15,23,42,.06),0 1px 3px rgba(15,23,42,.08)}
html[data-tema=escuro]{--fundo:#0b1220;--card:#111827;--linha:#273449;--tx:#e5e7eb;--tx2:#94a3b8;--azul:#164e63;--azul2:#0f2a36;--amar:#3a3215;
 --okbg:#0f2e1c;--ok:#86efac;--mdbg:#3a2210;--md:#fdba74;--albg:#3b1414;--al:#fca5a5}
*{box-sizing:border-box}
body{margin:0;background:var(--fundo);color:var(--tx);font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
header{background:var(--pet);color:#fff;padding:14px 20px 0;position:sticky;top:0;z-index:5;box-shadow:0 2px 6px rgba(0,0,0,.18);max-height:45vh;overflow-y:auto}
.topo{display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px}
/* Cabeçalho que aguenta texto longo: título e selo cortam com reticências; as pílulas têm linha própria. */
.topo h1{flex:1 1 auto;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pilulas{flex:1 1 100%;order:3;min-width:0}
.topo h1{font-size:18px;margin:0;font-weight:700;letter-spacing:.2px}
.pilulas{display:flex;flex-wrap:wrap;gap:6px}
.pilula{max-width:100%;overflow-wrap:break-word;background:rgba(255,255,255,.14);border-radius:999px;padding:2px 10px;font-size:12px}
.selo{margin-left:auto;border-radius:6px;padding:4px 10px;font-weight:700;font-size:13px;flex:0 1 auto;max-width:min(40vw,360px);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.concl .selo{max-width:100%;white-space:normal}
.selo.cond{background:#ffedd5;color:#9a3412}.selo.ok{background:#dcfce7;color:#166534}.selo.nao{background:#fee2e2;color:#991b1b}
nav{display:flex;gap:2px;overflow-x:auto;margin-top:12px;scrollbar-width:thin}
nav button{all:unset;cursor:pointer;color:#cbd5e1;padding:8px 14px;border-radius:8px 8px 0 0;font-size:13px;white-space:nowrap;display:flex;gap:6px;align-items:center}
nav button:hover{color:#fff;background:rgba(255,255,255,.08)}
nav button[aria-selected=true]{background:var(--fundo);color:var(--tx);font-weight:600}
nav .n{background:rgba(255,255,255,.18);border-radius:999px;padding:0 7px;font-size:11px}
nav button[aria-selected=true] .n{background:var(--azul);color:var(--tx)}
nav .n.alerta{background:#fca5a5;color:#7f1d1d}
main{padding:18px 20px 40px;max-width:1500px;margin:0 auto}
section[role=tabpanel]{display:none}section.ativo{display:block}
h2{font-size:15px;margin:22px 0 10px;color:var(--pet)}
html[data-tema=escuro] h2{color:#7dd3fc}
.tema{all:unset;cursor:pointer;border:1px solid rgba(255,255,255,.35);border-radius:6px;padding:3px 9px;font-size:12px;color:#fff}.tema:hover{background:rgba(255,255,255,.1)}
.grade{display:grid;gap:12px}
.kpis{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.kpi{background:var(--card);border-radius:10px;padding:12px 14px;box-shadow:var(--sombra);border-top:3px solid var(--verde)}
.kpi b{display:block;font-size:22px;font-variant-numeric:tabular-nums}
.kpi span{color:var(--tx2);font-size:12px}
.kpi small{display:block;color:var(--tx2);font-size:11px;margin-top:2px}
.kpi.alerta{border-top-color:#ea580c}
.dois{grid-template-columns:minmax(0,1.4fr) minmax(0,1fr)}
@media (max-width:900px){.dois{grid-template-columns:1fr}}
.caixa{background:var(--card);border-radius:10px;padding:14px 16px;box-shadow:var(--sombra)}
.caixa h3{margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.4px;color:var(--tx2)}
.concl{display:flex;gap:10px;align-items:center;margin-bottom:8px}
.lista-check{list-style:none;margin:0;padding:0}
.lista-check li{display:flex;gap:10px;align-items:flex-start;padding:7px 0;border-bottom:1px solid var(--linha)}
.lista-check li:last-child{border-bottom:0;top:auto}
.lista-check input{margin-top:3px;width:16px;height:16px;accent-color:var(--verde)}
.lista-check .ref{margin-left:auto;color:var(--tx2);font-size:12px;white-space:nowrap;padding-left:10px}
.lista-check li.feito span.t{text-decoration:line-through;color:var(--tx2)}
.prog{height:6px;background:var(--linha);border-radius:3px;overflow:hidden;margin:4px 0 10px}.prog i{display:block;height:100%;background:var(--verde)}
ul.rapida{margin:0;padding-left:18px}ul.rapida li{margin:4px 0}
mark{background:var(--amar);color:inherit;padding:0 2px;border-radius:2px}
.barra-ferr{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:4px 0 8px}
.barra-ferr input[type=search]{flex:1 1 240px;min-width:180px;padding:7px 10px;border:1px solid var(--linha);border-radius:8px;background:var(--card);color:var(--tx);font:inherit}
.barra-ferr select{padding:6px 8px;border:1px solid var(--linha);border-radius:8px;background:var(--card);color:var(--tx);font:inherit;font-size:13px;max-width:220px}
.barra-ferr button{padding:6px 10px;border:1px solid var(--linha);border-radius:8px;background:var(--card);color:var(--tx);cursor:pointer;font:inherit;font-size:13px}
.contagem{color:var(--tx2);font-size:12px;margin-left:auto}
.tab-wrap{background:var(--card);border-radius:10px;box-shadow:var(--sombra);overflow:auto;max-height:72vh}
table{width:100%;border-collapse:separate;border-spacing:0;font-size:13px}
th{position:sticky;top:0;background:var(--azul);color:var(--tx);text-align:left;font-weight:600;padding:8px 10px;border-bottom:1px solid var(--linha);cursor:pointer;user-select:none;white-space:nowrap;z-index:1}
th:hover{filter:brightness(.96)}
th .seta{opacity:.45;font-size:10px;margin-left:4px}
td{padding:7px 10px;border-bottom:1px solid var(--linha);vertical-align:top}
tbody tr:nth-child(even) td{background:color-mix(in srgb,var(--azul2) 35%,transparent)}
tbody tr:hover td{background:var(--azul2)}
tr.dest td{background:color-mix(in srgb,var(--verde) 14%,transparent)!important;font-weight:600}tr.dest td:first-child{box-shadow:inset 4px 0 0 var(--verde)}
td.id{white-space:nowrap;font-weight:600}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tfoot td,tfoot th{font-weight:700;background:var(--azul2);position:sticky;bottom:0;top:auto}
.chip{display:inline-block;border-radius:999px;padding:1px 9px;font-size:12px;background:var(--azul2);white-space:nowrap}
.r-Alto{background:var(--albg);color:var(--al);font-weight:600}.r-Médio{background:var(--mdbg);color:var(--md);font-weight:600}.r-Baixo{background:var(--okbg);color:var(--ok);font-weight:600}
.s-OK{background:var(--okbg);color:var(--ok);font-weight:600}.s-ALERTA{background:var(--mdbg);color:var(--md);font-weight:600}
.p-inc{background:var(--okbg);color:var(--ok)}.p-par{background:var(--azul2)}.p-nd{background:var(--mdbg);color:var(--md)}
.hbar{display:flex;align-items:center;gap:6px;justify-content:flex-end}
.hbar i{display:block;height:8px;background:var(--verde);border-radius:4px;opacity:.75}
.vazio{padding:20px;text-align:center;color:var(--tx2)}
.legenda{color:var(--tx2);font-size:12px;margin:6px 2px}
.carga{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.empilhada{display:flex;height:22px;border-radius:6px;overflow:hidden;margin:6px 0}
.empilhada i{display:block;height:100%}
.leg span{display:inline-flex;align-items:center;gap:5px;margin-right:12px;font-size:12px;color:var(--tx2)}
.leg i{width:10px;height:10px;border-radius:2px;display:inline-block}
.atalho{color:var(--tx2);font-size:11px}
kbd{border:1px solid var(--linha);border-radius:4px;padding:0 4px;font-size:11px}
@media (max-width:700px){header{position:static;padding:12px 12px 0}.topo h1{font-size:16px;flex-basis:100%}.pilulas{flex:1 0 100%}.selo{margin-left:0}main{padding:12px}.kpi b{font-size:18px}.barra-ferr select{max-width:100%;flex:1 1 140px}nav{position:sticky;top:0}}
@media print{header{position:static}nav,.barra-ferr,.atalho{display:none}section[role=tabpanel]{display:block;break-before:page}
 section[role=tabpanel]:first-of-type{break-before:auto}.tab-wrap{max-height:none;overflow:visible;box-shadow:none}
 th{position:static}body{background:#fff}}
</style>
</head>
<body>
<header>
 <div class="topo">
  <h1>Análise de manutenção · Exequibilidade operacional</h1>
  <div class="pilulas" id="pilulas"></div>
  <div class="selo" id="selo"></div>
  <button class="tema" id="tema" type="button" aria-label="Alternar tema">Modo escuro</button>
 </div>
 <nav role="tablist" id="abas"></nav>
</header>
<main id="painel"></main>
<script>
/*DADOS*/
const fmt=(v,c=1)=>typeof v==='number'?v.toLocaleString('pt-BR',{minimumFractionDigits:Number.isInteger(v)&&c===1?0:c,maximumFractionDigits:c}):(v??'');
const brl=v=>v.toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const D=DADOS.D,T=DADOS.tabelas,N=DADOS.num;
const tb=document.getElementById('tema');
const aplicaTema=t=>{document.documentElement.dataset.tema=t;tb.textContent=t==='escuro'?'Modo claro':'Modo escuro';try{localStorage.setItem('analise-tema',t)}catch(e){}};
let temaIni='claro';try{temaIni=localStorage.getItem('analise-tema')||'claro'}catch(e){};aplicaTema(temaIni);
tb.onclick=()=>aplicaTema(document.documentElement.dataset.tema==='escuro'?'claro':'escuro');
const selo=document.getElementById('selo');
selo.textContent=D.conclusao;selo.className='selo '+({'Atende':'ok','Atende com condições':'cond','Não atende':'nao'}[D.conclusao]||'cond');
document.getElementById('pilulas').innerHTML=(D.pilulas||[]).map(t=>`<span class="pilula">${esc(t)}</span>`).join('');

const alertas=T.checks.linhas.filter(r=>r[2]==='ALERTA').length;
const altos=T.requisitos.linhas.filter(r=>r[6]==='Alto').length;
const ABAS=[
 ['resumo','Resumo'],['servico','Dados do serviço'],...(DADOS.inventarios.length?[['equip','Equipamentos',DADOS.inventarios.reduce((n,g)=>n+g.total,0)]]:[]),['requisitos','Requisitos',T.requisitos.linhas.length,altos?altos+' altos':''],
 ['escopo','Escopo e carga',T.escopo.linhas.length],['dimens','Dimensionamento'],['pecas','Peças e materiais',T.pecas.linhas.length],
 ['pontos','Pontos de atenção',T.pontos.linhas.length],['documentos','Documentos',T.documentos.linhas.length],['checks','Checks',alertas?alertas+' alerta(s)':'OK']];
const nav=document.getElementById('abas'),painel=document.getElementById('painel');
ABAS.forEach(([id,nome,n,extra])=>{
 const b=document.createElement('button');b.role='tab';b.id='t-'+id;b.setAttribute('aria-controls','p-'+id);
 b.innerHTML=esc(nome)+(n!==undefined&&n!==''?` <span class="n">${n}</span>`:'')+(extra?` <span class="n ${/alerta|altos/.test(extra)?'alerta':''}">${extra}</span>`:'');
 b.onclick=()=>abrir(id);nav.appendChild(b);
 const s=document.createElement('section');s.role='tabpanel';s.id='p-'+id;s.setAttribute('aria-labelledby','t-'+id);painel.appendChild(s);
});
function abrir(id){ABAS.forEach(([a])=>{document.getElementById('t-'+a).setAttribute('aria-selected',a===id);document.getElementById('p-'+a).classList.toggle('ativo',a===id)});
 try{history.replaceState(null,'','#'+id)}catch(e){};window.scrollTo({top:0})}

// ---------- tabela genérica com busca, filtros, ordenação e totais
function tabela(alvo,cfg,opts={}){
 const cols=cfg.cols,el=document.createElement('div');alvo.appendChild(el);
 const filtraveis=cols.map((c,i)=>['chip','filtro','risco','pago','status'].includes(c[1])?i:-1).filter(i=>i>=0);
 const estado={q:'',f:{},ord:null,asc:true};
 el.innerHTML=`<div class="barra-ferr"><input type="search" placeholder="Buscar em ${esc(cfg.titulo.toLowerCase())}…" aria-label="Buscar">`+
  filtraveis.map(i=>{const vals=[...new Set(cfg.linhas.map(r=>r[i]).filter(v=>v!==null&&v!==''))].sort((a,b)=>String(a).localeCompare(String(b),'pt'));
   return `<select data-i="${i}" aria-label="Filtrar ${esc(cols[i][0])}"><option value="">${esc(cols[i][0])}: todos</option>${vals.map(v=>`<option>${esc(v)}</option>`).join('')}</select>`}).join('')+
  (cfg.destaque?`<label class="legenda"><input type="checkbox" data-dest> só ${esc(cfg.destaque.rotulo)}</label>`:'')+
  `<button type="button" data-limpar>Limpar</button><span class="contagem"></span></div><div class="tab-wrap"><table><thead><tr>`+
  cols.map((c,i)=>`<th data-i="${i}" ${['num','barra'].includes(c[1])?'style="text-align:right"':''}>${esc(c[0])}<span class="seta">↕</span></th>`).join('')+
  `</tr></thead><tbody></tbody>${cfg.soma?'<tfoot><tr></tr></tfoot>':''}</table></div>`;
 const tb=el.querySelector('tbody'),cont=el.querySelector('.contagem'),ft=el.querySelector('tfoot tr');
 const maxBar=Math.max(...cfg.linhas.map(r=>cols.reduce((m,c,i)=>c[1]==='barra'?Math.max(m,+r[i]||0):m,0)),1);
 const cel=(v,c)=>{const t=c[1];
  if(t==='num')return `<td class="num">${esc(fmt(v,Number.isInteger(v)?0:1))}</td>`;
  if(t==='barra')return `<td class="num"><div class="hbar"><i style="width:${Math.round(60*(+v||0)/maxBar)}px"></i>${esc(fmt(v))}</div></td>`;
  if(t==='risco')return `<td><span class="chip r-${esc(v)}">${esc(v)}</span></td>`;
  if(t==='status')return `<td><span class="chip s-${esc(v)}">${esc(v)}</span></td>`;
  if(t==='pago'){const k=/Incluído/.test(v)?'p-inc':/parte/.test(v)?'p-par':'p-nd';return `<td><span class="chip ${k}">${esc(v)}</span></td>`}
  if(t==='chip')return `<td><span class="chip">${esc(v)}</span></td>`;
  if(t==='id')return `<td class="id">${esc(v)}</td>`;
  return `<td>${esc(v)}</td>`};
 function render(){
  let ls=cfg.linhas.filter(r=>{
   if(estado.q&&!r.join(' ').toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu,'').includes(estado.q))return false;
   for(const[i,v]of Object.entries(estado.f))if(v&&String(r[i])!==v)return false;
   if(estado.dest&&!(+r[cfg.destaque.col]>=cfg.destaque.min))return false;return true});
  if(estado.ord!==null){const i=estado.ord;ls=[...ls].sort((a,b)=>{const x=a[i],y=b[i];const r=(typeof x==='number'&&typeof y==='number')?x-y:String(x??'').localeCompare(String(y??''),'pt',{numeric:true});return estado.asc?r:-r})}
  tb.innerHTML=ls.length?ls.map(r=>`<tr class="${cfg.destaque&&+r[cfg.destaque.col]>=cfg.destaque.min?'dest':''}">${cols.map((c,i)=>cel(r[i],c)).join('')}</tr>`).join(''):`<tr><td class="vazio" colspan="${cols.length}">Nada encontrado com esses filtros.</td></tr>`;
  cont.textContent=`${ls.length} de ${cfg.linhas.length}`;
  if(ft){
   const rotulo=cols.findIndex((_,i)=>!cfg.soma.includes(i));
   ft.innerHTML=cols.map((_,i)=>{
    if(cfg.soma.includes(i)){
     const total=ls.reduce((s,r)=>s+(+r[i]||0),0);
     const texto=esc(fmt(total,Number.isInteger(total)?0:1));
     return `<td class="num">${rotulo<0&&i===0?'Total (filtrado): ':''}${texto}</td>`;
    }
    return i===rotulo?'<th scope="row">Total (filtrado)</th>':'<td></td>';
   }).join('');
  }
  el.querySelectorAll('thead th').forEach(th=>{const i=+th.dataset.i;th.querySelector('.seta').textContent=estado.ord===i?(estado.asc?'▲':'▼'):'↕'})}
 el.querySelector('input[type=search]').oninput=e=>{estado.q=e.target.value.toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu,'');render()};
 el.querySelectorAll('select').forEach(s=>s.onchange=()=>{estado.f[s.dataset.i]=s.value;render()});
 const d=el.querySelector('[data-dest]');if(d)d.onchange=()=>{estado.dest=d.checked;render()};
 el.querySelector('[data-limpar]').onclick=()=>{estado.q='';estado.f={};estado.ord=null;estado.dest=false;el.querySelectorAll('select').forEach(s=>s.value='');el.querySelector('input[type=search]').value='';if(d)d.checked=false;render()};
 el.querySelectorAll('thead th').forEach(th=>th.onclick=()=>{const i=+th.dataset.i;if(estado.ord===i)estado.asc=!estado.asc;else{estado.ord=i;estado.asc=true}render()});
 render();return el}
const P=id=>document.getElementById('p-'+id);
const kpi=(v,r,sub='',cls='')=>`<div class="kpi ${cls}"><b>${v}</b><span>${r}</span>${sub?`<small>${sub}</small>`:''}</div>`;

// ---------- Resumo
(()=>{const s=P('resumo');
 const chave=DADOS.chave+'-condicoes';let marc={};try{marc=JSON.parse(localStorage.getItem(chave)||'{}')}catch(e){}
 s.innerHTML=`<div class="grade kpis">${kpi(fmt(N.req),'Horas requeridas / mês','Carga estimada (C)')}${kpi(fmt(N.disp),'Horas disponíveis / mês','Equipe informada (P)')}${kpi(fmt(N.cob*100)+'%','Cobertura da equipe','Disponíveis ÷ requeridas')}${kpi(fmt(N.folga),'Folga (h/mês)','Disponíveis − requeridas')}
  ${DADOS.inventarios.map(g=>kpi(g.total,esc(g.titulo),esc(g.resumo))).join('')}${(D.kpis_extras||[]).map(k=>kpi(esc(k[0]),esc(k[1]),esc(k[2]||''),k[3]?'alerta':'')).join('')}</div>
 <div class="grade dois" style="margin-top:12px">
  <div class="caixa"><h3>Conclusão</h3><div class="concl"><span class="selo ${selo.className.split(' ')[1]}">${esc(D.conclusao)}</span></div><p style="margin:0">${esc(D.justificativa)}</p>
   <h3 style="margin-top:14px">Leitura rápida</h3><ul class="rapida">${DADOS.leitura.map(([a,t])=>`<li><b>${esc(a)}:</b> ${esc(t).replace(/==(.+?)==/g,'<mark>$1</mark>')}</li>`).join('')}</ul></div>
  <div class="caixa"><h3>Condições para executar</h3><div class="prog"><i id="pg"></i></div><ul class="lista-check" id="conds"></ul>
   <p class="atalho">As marcações ficam salvas só neste navegador.</p></div></div>
 <h2>Obrigações de maior risco</h2><div id="tr"></div><h2>Pontos para a analista decidir</h2><div id="td"></div>
 <h2>Prazos de execução</h2><div id="tp"></div>`;
 const ul=s.querySelector('#conds');
 const att=()=>{const n=D.condicoes.length,k=Object.values(marc).filter(Boolean).length;s.querySelector('#pg').style.width=(100*k/n)+'%'};
 D.condicoes.forEach(([c,r],i)=>{const li=document.createElement('li');li.className=marc[i]?'feito':'';
  li.innerHTML=`<input type="checkbox" ${marc[i]?'checked':''} aria-label="Condição atendida"><span class="t">${esc(c)}</span><span class="ref">${esc(r)}</span>`;
  li.querySelector('input').onchange=e=>{marc[i]=e.target.checked;li.className=e.target.checked?'feito':'';try{localStorage.setItem(chave,JSON.stringify(marc))}catch(x){};att()};ul.appendChild(li)});att();
 tabela(s.querySelector('#tr'),{titulo:'Riscos',cols:[['Obrigação','texto'],['Requisito','texto'],['Por que é risco','texto'],['Como reduzir','texto']],linhas:D.riscos});
 tabela(s.querySelector('#td'),{titulo:'Decisões',cols:[['Ponto','texto'],['Prazo','filtro']],linhas:D.decisoes});
 tabela(s.querySelector('#tp'),{titulo:'Prazos',cols:[['Prazo','texto'],['Evento','texto'],['Onde consta','texto']],linhas:D.prazos||[]});
})();

// ---------- Dados do serviço
(()=>{const s=P('servico');s.innerHTML='<h2>Dados do serviço</h2>';tabela(s,{titulo:'Dados do serviço',cols:[['Grupo','chip'],['Campo','texto'],['Informação','texto'],['Onde consta','texto']],linhas:DADOS.servico})})();

// ---------- Equipamentos
DADOS.inventarios.forEach(g=>{
 const s=P('equip'),titulo=document.createElement('h2'),area=document.createElement('div');
 titulo.textContent=g.titulo;s.appendChild(titulo);s.appendChild(area);tabela(area,g);
});

// ---------- Requisitos, Escopo, Peças, Pontos, Documentos, Checks
(()=>{const s=P('requisitos');s.innerHTML='<h2>Requisitos de execução</h2><p class="legenda">Filtre por grupo, risco ou pendência. Clique no cabeçalho para ordenar.</p>';tabela(s,T.requisitos)})();
(()=>{const s=P('escopo');s.innerHTML='<h2>Escopo e carga de trabalho</h2><p class="legenda">O total acompanha os filtros. Horas por ano = frequência × volume × tempo.</p>';tabela(s,T.escopo);
 s.insertAdjacentHTML('beforeend',`<p class="legenda">Fora do escopo: ${esc(D.escopo_na)}</p>`)})();
(()=>{const s=P('pecas');s.innerHTML='<h2>Peças, insumos e materiais</h2>';tabela(s,T.pecas)})();
(()=>{const s=P('pontos');s.innerHTML='<h2>Pontos de atenção, divergências e pendências</h2>';tabela(s,T.pontos)})();
(()=>{const s=P('documentos');s.innerHTML='<h2>Documentos analisados</h2>';tabela(s,T.documentos)})();
(()=>{const s=P('checks');s.innerHTML=`<h2>Controles de integridade</h2><p class="legenda">Conferência das contas da análise. ${alertas?alertas+' alerta(s).':'Todos em OK.'}</p>`;tabela(s,T.checks)})();

// ---------- Dimensionamento
(()=>{const s=P('dimens'),C=DADOS.carga,tot=C['Total requerido'][1];
 const cor={'Programada':'#0f766e','Não programada':'#ea580c','Indireta':'#64748b'};
 s.innerHTML=`<h2>Carga × capacidade</h2><div class="grade dois"><div class="caixa"><h3>Carga mensal por tipo</h3>
  <div class="empilhada">${['Programada','Não programada','Indireta'].map(t=>`<i title="${t}: ${fmt(C[t][1])} h/mês" style="width:${100*C[t][1]/N.disp}%;background:${cor[t]}"></i>`).join('')}<i title="Folga" style="width:${100*N.folga/N.disp}%;background:repeating-linear-gradient(45deg,#cbd5e1,#cbd5e1 4px,#e2e8f0 4px,#e2e8f0 8px)"></i></div>
  <div class="leg">${['Programada','Não programada','Indireta'].map(t=>`<span><i style="background:${cor[t]}"></i>${t}: ${fmt(C[t][1])} h</span>`).join('')}<span><i style="background:#cbd5e1"></i>Folga: ${fmt(N.folga)} h</span></div>
  <table style="margin-top:8px"><thead><tr><th>Tipo de carga</th><th style="text-align:right">Horas/ano</th><th style="text-align:right">Horas/mês</th><th>Base</th></tr></thead><tbody>
  ${['Programada','Não programada','Indireta','Total requerido'].map(t=>`<tr><td>${t==='Total requerido'?'<b>Total</b>':t}</td><td class="num">${fmt(C[t][0])}</td><td class="num">${fmt(C[t][1])}</td><td>${esc(D.base_carga[t]||'')}</td></tr>`).join('')}</tbody></table>
  <p class="legenda">A barra inteira representa as ${fmt(N.disp)} h disponíveis por mês ${D.equipe.map(q=>` · ${esc(q[0])}: ${fmt(q[1])} × ${fmt(q[2]-q[3])} h produtivas`).join('')}.</p></div>
  <div class="caixa"><h3>Testes</h3><ul class="lista-check">
   <li><span class="t"><b>Primeiro ciclo:</b> ${esc(D.testes.ciclo[0])} — carga ${fmt(D.testes.ciclo[1])} h × capacidade ${fmt(D.testes.ciclo[2])} h</span><span class="ref"><span class="chip ${DADOS.ciclo==='Atende'?'s-OK':'s-ALERTA'}">${esc(DADOS.ciclo)}</span></span></li>
   <li><span class="t"><b>Pior SLA:</b> ${esc(D.testes.sla[0])}. ${esc(D.testes.sla[4])}</span><span class="ref"><span class="chip s-OK">${esc(D.testes.sla[3])}</span></span></li></ul>
   <h3 style="margin-top:12px">Equipe</h3><p style="margin:0">${esc(D.conclusao_equipe[1])}. ${esc(D.conclusao_equipe[2])}</p></div></div>
  <h2>Premissas</h2><div id="pm"></div>`;
 tabela(s.querySelector('#pm'),T.premissas)})();

const ini=(location.hash||'#resumo').slice(1);abrir(ABAS.some(a=>a[0]===ini)?ini:'resumo');
document.addEventListener('keydown',e=>{if(e.key==='/'&&document.activeElement.tagName!=='INPUT'){const i=document.querySelector('section.ativo input[type=search]');if(i){e.preventDefault();i.focus()}}
 if(e.altKey&&/^[1-9]$/.test(e.key)){const a=ABAS[+e.key-1];if(a)abrir(a[0])}});
</script>
</body>
</html>
"""
