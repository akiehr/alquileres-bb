#!/usr/bin/env python3
"""
Genera alquileres.html a partir de vistas.json.

    python hacer_html.py            # lee ./vistas.json, escribe ./alquileres.html
    python hacer_html.py otro.json  # o el archivo que le pases

Los datos quedan embebidos en el HTML, así que el archivo funciona offline y
se puede mandar por mail. También acepta que le arrastres un vistas.json
nuevo encima para actualizarlo sin regenerarlo.
"""

import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))

RE_CIUDAD = re.compile(r"\s*,?\s*Bah[íi]a Blanca\s*$", re.I)
RE_PREFIJO = re.compile(r"^\s*(Casa|Duplex|Departamento|PH)\s+en\s+Alquiler\s*(en\s+)?", re.I)
RE_ALTURA = re.compile(r"\d{1,5}\s*$")


def barrio_de(titulo):
    """El sitio arma el título como 'Casa en Alquiler en CALLE 123, Barrio, Bahía Blanca'.
    El barrio es el último tramo — salvo cuando no lo cargaron y queda la dirección."""
    t = RE_PREFIJO.sub("", RE_CIUDAD.sub("", (titulo or "").strip()))
    partes = [x.strip() for x in t.split(",") if x.strip()]
    if not partes:
        return None
    ultimo = partes[-1]
    if len(partes) == 1 or RE_ALTURA.search(ultimo):
        return None          # es la calle, no un barrio
    return ultimo


def direccion_de(titulo):
    t = RE_PREFIJO.sub("", RE_CIUDAD.sub("", (titulo or "").strip()))
    partes = [x.strip() for x in t.split(",") if x.strip()]
    return partes[0] if partes else (titulo or "")


def main():
    origen = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "vistas.json")
    if not os.path.exists(origen):
        sys.exit(f"no encuentro {origen} — corré primero alertas_alquiler.py")

    with open(origen, encoding="utf-8") as f:
        estado = json.load(f)

    items = []
    for v in estado.get("propiedades", {}).values():
        items.append({**v,
                      "barrio": barrio_de(v.get("titulo")),
                      "calle": direccion_de(v.get("titulo"))})
    items.sort(key=lambda x: (x["precio"] is None, x["precio"] or 0))

    datos = {"actualizado": estado.get("actualizado"), "items": items}
    # El JSON va embebido dentro de un <script>. Si un título trajera la
    # secuencia </script>, cerraría el bloque y el resto se interpretaría
    # como HTML. Escapamos < > & como \uXXXX: sigue siendo JSON válido.
    blob = (json.dumps(datos, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("&", "\\u0026").replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029"))

    salida = os.path.join(AQUI, "alquileres.html")
    with open(salida, "w", encoding="utf-8") as f:
        f.write(PLANTILLA.replace("/*__DATOS__*/null", blob))
    print(f"{len(items)} propiedades -> {salida}")


PLANTILLA = r"""<!DOCTYPE html>
<html lang="es-AR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alquileres · Bahía Blanca</title>
<style>
:root{
  --paper:#E6E8E3; --surface:#FBFCFA; --line:#CBD1C9;
  --ink:#18201B; --muted:#6E7A72; --signal:#17594A; --oxide:#A63A1E;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
}
*{box-sizing:border-box}
html,body{margin:0}
body{
  background:var(--paper); color:var(--ink); font-family:var(--sans);
  font-size:15px; line-height:1.45; -webkit-font-smoothing:antialiased;
  padding:0 20px 80px;
}
.wrap{max-width:1080px;margin:0 auto}

/* ---- encabezado ---- */
header{padding:36px 0 20px}
.eyebrow{
  font-family:var(--mono); font-size:10.5px; letter-spacing:.18em;
  text-transform:uppercase; color:var(--muted);
}
h1{
  font-size:clamp(30px,5vw,44px); font-weight:800; letter-spacing:-.035em;
  margin:6px 0 0; line-height:1;
}
.sub{color:var(--muted); font-size:13px; margin-top:8px}
.sub b{color:var(--ink); font-weight:600}

/* ---- histograma / filtro de precio ---- */
.panel{
  background:var(--surface); border:1px solid var(--line);
  border-radius:3px; padding:18px 20px 14px; margin-bottom:14px;
}
.panel-cab{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.panel-cab .lbl{font-family:var(--mono);font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.rango{font-family:var(--mono);font-size:14px;font-weight:600;font-variant-numeric:tabular-nums}
#bars{display:flex;align-items:flex-end;gap:2px;height:76px}
#bars .b{flex:1;background:var(--line);border-radius:1px 1px 0 0;min-height:2px;cursor:pointer;transition:background .12s}
#bars .b.on{background:var(--signal)}
#bars .b:hover{background:var(--ink)}
.rangewrap{position:relative;height:26px;margin-top:6px}
.rangewrap .rail{position:absolute;top:11px;left:0;right:0;height:3px;background:var(--line);border-radius:2px}
.rangewrap .fill{position:absolute;top:11px;height:3px;background:var(--signal);border-radius:2px}
.rangewrap input{
  position:absolute;top:0;left:0;width:100%;height:26px;margin:0;
  -webkit-appearance:none;appearance:none;background:none;pointer-events:none;
}
.rangewrap input::-webkit-slider-thumb{
  -webkit-appearance:none;pointer-events:auto;width:16px;height:16px;border-radius:50%;
  background:var(--surface);border:2px solid var(--signal);cursor:grab;margin-top:0;
}
.rangewrap input::-moz-range-thumb{
  pointer-events:auto;width:14px;height:14px;border-radius:50%;
  background:var(--surface);border:2px solid var(--signal);cursor:grab;
}
.escala{display:flex;justify-content:space-between;font-family:var(--mono);font-size:10px;color:var(--muted);margin-top:2px}

/* ---- controles ---- */
.controles{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:16px}
input[type=search],select{
  font:inherit;font-size:13.5px;padding:8px 11px;border:1px solid var(--line);
  border-radius:3px;background:var(--surface);color:var(--ink);
}
input[type=search]{flex:1 1 240px;min-width:0}
.chips{display:flex;gap:0;border:1px solid var(--line);border-radius:3px;overflow:hidden;background:var(--surface)}
.chip{
  font-family:var(--mono);font-size:11.5px;padding:8px 11px;border:0;background:none;
  color:var(--muted);cursor:pointer;border-right:1px solid var(--line);
}
.chip:last-child{border-right:0}
.chip[aria-pressed=true]{background:var(--signal);color:#fff}
:focus-visible{outline:2px solid var(--signal);outline-offset:2px}

/* ---- listado ---- */
.meta{font-family:var(--mono);font-size:11.5px;color:var(--muted);margin:0 0 10px;letter-spacing:.04em}
.fila{
  display:grid;grid-template-columns:60px 132px 62px 1fr auto;gap:16px;align-items:center;
  padding:11px 16px;background:var(--surface);border:1px solid var(--line);
  border-bottom:0;text-decoration:none;color:inherit;
}
.thumb{
  width:60px;height:46px;object-fit:cover;border-radius:2px;display:block;
  background:var(--line) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236E7A72' stroke-width='1.5'%3E%3Cpath d='M3 10.5 12 4l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z'/%3E%3C/svg%3E") center/22px no-repeat;
}
.fila:first-of-type{border-radius:3px 3px 0 0}
.fila:last-of-type{border-bottom:1px solid var(--line);border-radius:0 0 3px 3px}
.fila:hover{background:#F1F4F0}
.precio{font-family:var(--mono);font-size:15px;font-weight:600;font-variant-numeric:tabular-nums;letter-spacing:-.02em;white-space:nowrap}
.precio.nada{color:var(--muted);font-weight:400;font-size:12.5px}
.dorm{font-family:var(--mono);font-size:12px;color:var(--muted);white-space:nowrap}
.calle{font-weight:600;letter-spacing:-.01em}
.barrio{color:var(--muted);font-size:13px}
.agencia{font-size:11.5px;color:var(--muted);text-align:right;max-width:210px}
.nueva{
  display:inline-block;font-family:var(--mono);font-size:9px;letter-spacing:.12em;
  background:var(--oxide);color:#fff;padding:2px 5px;border-radius:2px;
  vertical-align:2px;margin-left:7px;
}
.vacio{padding:48px 16px;text-align:center;color:var(--muted);background:var(--surface);border:1px solid var(--line);border-radius:3px}
footer{margin-top:26px;font-family:var(--mono);font-size:10.5px;color:var(--muted);letter-spacing:.04em}
#drop{position:fixed;inset:0;background:rgba(23,89,74,.92);color:#fff;display:none;
  align-items:center;justify-content:center;font-family:var(--mono);font-size:14px;letter-spacing:.1em;z-index:9}
body.dragging #drop{display:flex}
@media (max-width:720px){
  .fila{grid-template-columns:52px 1fr auto;gap:3px 11px;align-items:start}
  .thumb{grid-row:1/span 3;width:52px;height:52px;align-self:center}
  .precio{grid-row:1;grid-column:2;font-size:17px}
  .dorm{grid-row:1;grid-column:3;text-align:right}
  .info{grid-column:2/-1}
  .agencia{grid-column:2/-1;text-align:left;max-width:none}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>
<div id="drop">SOLTÁ EL VISTAS.JSON PARA ACTUALIZAR</div>
<div class="wrap">

<header>
  <div class="eyebrow">Casas en alquiler · Bahía Blanca</div>
  <h1>Qué hay dando vueltas</h1>
  <div class="sub" id="cabecera"></div>
</header>

<div class="panel">
  <div class="panel-cab">
    <span class="lbl">Precio mensual · cada barra es un tramo</span>
    <span class="rango" id="rangoTxt"></span>
  </div>
  <div id="bars"></div>
  <div class="rangewrap">
    <div class="rail"></div><div class="fill" id="fill"></div>
    <input type="range" id="rmin"><input type="range" id="rmax">
  </div>
  <div class="escala"><span id="escIzq"></span><span id="escDer"></span></div>
</div>

<div class="controles">
  <input type="search" id="q" placeholder="Buscar calle, barrio o inmobiliaria…">
  <div class="chips" id="chipsDorm"></div>
  <select id="barrio"></select>
  <select id="orden">
    <option value="precio">Precio: menor primero</option>
    <option value="-precio">Precio: mayor primero</option>
    <option value="-dorm">Más dormitorios</option>
    <option value="-nuevo">Publicadas hace menos</option>
    <option value="barrio">Barrio A–Z</option>
  </select>
  <div class="chips">
    <button class="chip" id="tConsultar" aria-pressed="true">A consultar</button>
    <button class="chip" id="tDolar" aria-pressed="true">U$S</button>
  </div>
</div>

<p class="meta" id="meta"></p>
<div id="lista"></div>
<footer id="pie"></footer>

</div>
<script>
let DATOS = /*__DATOS__*/null;

const $ = s => document.querySelector(s);
const nf = new Intl.NumberFormat('es-AR');

/* Los títulos e inmobiliarias vienen scrapeados de un tercero: nunca los
   metemos crudos en innerHTML. esc() para texto, href() para URLs
   (además bloquea esquemas raros tipo javascript:). */
const esc = s => String(s ?? '').replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const href = u => /^https?:\/\//i.test(u || '') ? esc(u) : '#';

const money = (m,p) => p==null ? null : (m==='U$S'?'U$S ':'$ ') + nf.format(p);
const corto = n => n>=1e6 ? (n/1e6).toFixed(n>=1e7?0:1).replace('.',',')+'M' : Math.round(n/1000)+'k';

const estado = {q:'', dorms:new Set(), barrio:'', orden:'precio',
                min:0, max:0, consultar:true, dolar:true};
let PESOS = [], LIM = [0,0], BUCKETS = [], NUEVO_DESDE = 0;

/* --- arranque / recarga --- */
function iniciar(){
  const items = DATOS.items;
  PESOS = items.filter(x=>x.moneda==='$' && x.precio).map(x=>x.precio).sort((a,b)=>a-b);
  LIM = [PESOS[0]||0, PESOS[PESOS.length-1]||0];
  estado.min = LIM[0]; estado.max = LIM[1];

  const ref = DATOS.actualizado ? new Date(DATOS.actualizado) : new Date();
  NUEVO_DESDE = ref.getTime() - 7*864e5;

  const fecha = DATOS.actualizado
    ? new Date(DATOS.actualizado).toLocaleString('es-AR',{day:'numeric',month:'long',hour:'2-digit',minute:'2-digit'})
    : '—';
  $('#cabecera').innerHTML = `<b>${items.length}</b> publicaciones · ${new Set(items.map(x=>x.inmobiliaria)).size} inmobiliarias · datos del ${fecha}`;

  const rmin=$('#rmin'), rmax=$('#rmax');
  for(const r of [rmin,rmax]){ r.min=LIM[0]; r.max=LIM[1]; r.step=10000; }
  rmin.value=LIM[0]; rmax.value=LIM[1];
  $('#escIzq').textContent='$'+corto(LIM[0]);
  $('#escDer').textContent='$'+corto(LIM[1]);

  // chips de dormitorios, solo los que existen
  const dd=[...new Set(items.map(x=>x.dormitorios).filter(Boolean))].sort((a,b)=>a-b);
  $('#chipsDorm').innerHTML = dd.map(d=>`<button class="chip" data-d="${d}" aria-pressed="false">${d} dorm</button>`).join('');
  $('#chipsDorm').querySelectorAll('.chip').forEach(b=>b.onclick=()=>{
    const d=+b.dataset.d;
    estado.dorms.has(d) ? estado.dorms.delete(d) : estado.dorms.add(d);
    b.setAttribute('aria-pressed', estado.dorms.has(d));
    pintar();
  });

  // barrios ordenados por cantidad
  const cnt={};
  items.forEach(x=>{ if(x.barrio) cnt[x.barrio]=(cnt[x.barrio]||0)+1; });
  const bs=Object.entries(cnt).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]));
  $('#barrio').innerHTML = '<option value="">Todos los barrios</option>' +
    bs.map(([b,n])=>`<option value="${esc(b)}">${esc(b)} (${n})</option>`).join('');

  construirBarras();
  pintar();
}

function construirBarras(){
  const N=26, [lo,hi]=LIM, paso=(hi-lo)/N || 1;
  BUCKETS = Array.from({length:N},(_,i)=>({a:lo+i*paso, b:lo+(i+1)*paso, n:0}));
  PESOS.forEach(p=>{ BUCKETS[Math.min(N-1, Math.floor((p-lo)/paso))].n++; });
  const tope=Math.max(...BUCKETS.map(b=>b.n));
  $('#bars').innerHTML = BUCKETS.map((b,i)=>
    `<div class="b" data-i="${i}" style="height:${Math.max(3, Math.sqrt(b.n/tope)*100)}%"
      title="${b.n} entre $${corto(b.a)} y $${corto(b.b)}"></div>`).join('');
  $('#bars').querySelectorAll('.b').forEach(el=>el.onclick=()=>{
    const b=BUCKETS[+el.dataset.i];
    estado.min=Math.round(b.a); estado.max=Math.round(b.b);
    $('#rmin').value=estado.min; $('#rmax').value=estado.max;
    pintar();
  });
}

/* --- filtrado --- */
function filtrar(){
  const q=estado.q.toLowerCase();
  return DATOS.items.filter(x=>{
    if(q && !((x.titulo||'')+' '+(x.inmobiliaria||'')+' '+(x.barrio||'')).toLowerCase().includes(q)) return false;
    if(estado.dorms.size && !estado.dorms.has(x.dormitorios)) return false;
    if(estado.barrio && x.barrio!==estado.barrio) return false;
    if(x.precio==null) return estado.consultar;
    if(x.moneda==='U$S') return estado.dolar;
    return x.precio>=estado.min && x.precio<=estado.max;
  });
}

function ordenar(a){
  const ts=x=>x.visto_desde?new Date(x.visto_desde).getTime():0;
  const p=x=>x.precio==null?Infinity:x.precio;
  const f={
    'precio':(u,v)=>p(u)-p(v),
    '-precio':(u,v)=>(p(v)===Infinity?-1:p(v))-(p(u)===Infinity?-1:p(u)),
    '-dorm':(u,v)=>(v.dormitorios||0)-(u.dormitorios||0)||p(u)-p(v),
    '-nuevo':(u,v)=>ts(v)-ts(u)||p(u)-p(v),
    'barrio':(u,v)=>(u.barrio||'zzz').localeCompare(v.barrio||'zzz')||p(u)-p(v),
  }[estado.orden];
  return a.sort(f);
}

function pintar(){
  // barras encendidas según el rango
  $('#bars').querySelectorAll('.b').forEach((el,i)=>{
    const b=BUCKETS[i];
    el.classList.toggle('on', b.b>=estado.min && b.a<=estado.max);
  });
  const span=(LIM[1]-LIM[0])||1;
  $('#fill').style.left = ((estado.min-LIM[0])/span*100)+'%';
  $('#fill').style.width = ((estado.max-estado.min)/span*100)+'%';
  $('#rangoTxt').textContent = `$${nf.format(estado.min)} — $${nf.format(estado.max)}`;

  const r=ordenar(filtrar());
  const conPrecio=r.filter(x=>x.precio&&x.moneda==='$').map(x=>x.precio).sort((a,b)=>a-b);
  const med=conPrecio.length?conPrecio[Math.floor(conPrecio.length/2)]:null;
  $('#meta').textContent = `${r.length} de ${DATOS.items.length}` +
    (med?` · mediana $${nf.format(med)}`:'');

  $('#lista').innerHTML = r.length ? r.map(x=>{
    const nueva = x.nueva_en && new Date(x.nueva_en).getTime()>=NUEVO_DESDE;
    const pr = money(x.moneda,x.precio);
    const thumb = x.imagen
      ? `<img class="thumb" src="${href(x.imagen)}" loading="lazy" alt=""
             onerror="this.removeAttribute('src')">`
      : `<span class="thumb"></span>`;
    return `<a class="fila" href="${href(x.url)}" target="_blank" rel="noopener">
      ${thumb}
      <span class="precio ${pr?'':'nada'}">${esc(pr||'a consultar')}</span>
      <span class="dorm">${x.dormitorios?esc(x.dormitorios)+' dorm':'—'}</span>
      <span class="info"><span class="calle">${esc(x.calle||x.titulo)}</span>${nueva?'<span class="nueva">NUEVA</span>':''}
        <br><span class="barrio">${esc(x.barrio||'sin barrio')}</span></span>
      <span class="agencia">${esc(x.inmobiliaria||'')}</span>
    </a>`;
  }).join('') : `<div class="vacio">Nada entra en ese filtro. Ampliá el rango de precio o limpiá la búsqueda.</div>`;

  $('#pie').textContent = 'Arrastrá un vistas.json nuevo sobre esta ventana para actualizar los datos.';
}

/* --- eventos --- */
$('#q').oninput = e => { estado.q=e.target.value; pintar(); };
$('#barrio').onchange = e => { estado.barrio=e.target.value; pintar(); };
$('#orden').onchange = e => { estado.orden=e.target.value; pintar(); };
$('#rmin').oninput = e => { estado.min=Math.min(+e.target.value, estado.max); e.target.value=estado.min; pintar(); };
$('#rmax').oninput = e => { estado.max=Math.max(+e.target.value, estado.min); e.target.value=estado.max; pintar(); };
for(const [id,k] of [['#tConsultar','consultar'],['#tDolar','dolar']]){
  $(id).onclick = () => { estado[k]=!estado[k]; $(id).setAttribute('aria-pressed',estado[k]); pintar(); };
}

/* --- soltar un vistas.json nuevo --- */
addEventListener('dragover', e=>{ e.preventDefault(); document.body.classList.add('dragging'); });
addEventListener('dragleave', e=>{ if(e.relatedTarget===null) document.body.classList.remove('dragging'); });
addEventListener('drop', e=>{
  e.preventDefault(); document.body.classList.remove('dragging');
  const f=e.dataTransfer.files[0]; if(!f) return;
  const fr=new FileReader();
  fr.onload = () => {
    try{
      const j=JSON.parse(fr.result);
      const items=Object.values(j.propiedades||{});
      if(!items.length) throw 0;
      DATOS={actualizado:j.actualizado, items:items.map(v=>({...v, ...partir(v.titulo)}))};
      estado.q=''; $('#q').value=''; estado.dorms.clear(); estado.barrio='';
      iniciar();
    }catch(err){ alert('Ese archivo no parece un vistas.json válido.'); }
  };
  fr.readAsText(f);
});

/* mismo criterio de barrio que el generador de Python */
function partir(t){
  t=(t||'').replace(/\s*,?\s*Bah[íi]a Blanca\s*$/i,'')
           .replace(/^\s*(Casa|Duplex|Departamento|PH)\s+en\s+Alquiler\s*(en\s+)?/i,'');
  const p=t.split(',').map(s=>s.trim()).filter(Boolean);
  const ult=p[p.length-1]||'';
  return {calle:p[0]||t, barrio:(p.length>1 && !/\d{1,5}\s*$/.test(ult)) ? ult : null};
}

iniciar();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
