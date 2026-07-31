#!/usr/bin/env python3
"""
Alertas manuales de alquileres — bahiablancapropiedades.com

Corrés el script y te dice QUÉ CAMBIÓ desde la última vez:
  - propiedades nuevas
  - bajas de precio
  - publicaciones que desaparecieron

Guarda el estado en vistas.json (mismo directorio). La primera corrida solo
toma la foto inicial; a partir de la segunda ya avisa novedades.

    pip install requests beautifulsoup4
    python alertas_alquiler.py --ciudad 1 --inmueble-id 1 --sin-filtro-local

Endpoint (POST, form-urlencoded):
    /web/busqueda/get/{pagina}     pagina arranca en 0
    operacion=alquiler|venta · ciudad={id} · inmueble_id[]={id} · barrio=false
    order_by=default · filtros[n][key]/[value]
El server responde JSON pero manda Content-Type: text/html, así que hay que
hacer json.loads() a mano. ciudad 1 = Bahía Blanca. inmueble_id 1 = Casa,
2 Departamento, 3 Terreno, 4 Cochera, 5 Duplex, 8 Galpón, 9 Local, 10 Oficina.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

BASE = "https://www.bahiablancapropiedades.com"
ENDPOINT = BASE + "/web/busqueda/get/{pagina}"
ESTADO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vistas.json")

TIPOS = ["Departamento", "Fondo de Comercio", "Consultorio", "Cochera", "Terreno",
         "Galpón", "Galpon", "Oficina", "Duplex", "Quinta", "Chacra", "Campo",
         "Local", "Casa", "Lote", "Edificio", "PH"]

RE_PROP = re.compile(r"/propiedad/(\d+)/([^\"'?#]*)")
RE_INMO = re.compile(r"/inmobiliarias/(\d+)/")
RE_PRECIO = re.compile(r"(U\$S|\$)\s*([\d.]+)")
RE_DORM = re.compile(r"(\d+)\s+Dormitorio")
RE_BG = re.compile(r"url\(\s*['\"]?(.*?)['\"]?\s*\)", re.I | re.S)
RE_PAGS = re.compile(r'data-pagina="(\d+)"')
RE_TOTAL = re.compile(r"([\d.]+)\s+Propiedades Disponibles")
RE_CIUDAD = re.compile(r"\s*,?\s*Bah[íi]a Blanca\s*$", re.I)
RE_PREFIJO = re.compile(r"^\s*(Casa|Duplex|Departamento|PH)\s+en\s+Alquiler\s*(en\s+)?", re.I)
RE_ALTURA = re.compile(r"\d{1,5}\s*$")


def zona(titulo):
    """Barrio si el aviso lo cargó; si no, la calle. Para la notificación."""
    t = RE_PREFIJO.sub("", RE_CIUDAD.sub("", (titulo or "").strip()))
    partes = [x.strip() for x in t.split(",") if x.strip()]
    if not partes:
        return "sin datos"
    if len(partes) == 1 or RE_ALTURA.search(partes[-1]):
        return partes[0]
    return partes[-1]


def _num(s):
    try:
        return int(s.replace(".", ""))
    except (ValueError, AttributeError):
        return None


def fetch(session, pagina, extra=None):
    """El server manda Content-Type: text/html pero el body es JSON."""
    data = {"operacion": "alquiler", "barrio": "false",
            "order_by": "default", "device": "desktop"}
    data.update(extra or {})
    r = session.post(ENDPOINT.format(pagina=pagina), data=data, timeout=30)
    r.raise_for_status()
    return json.loads(r.text)


def total_paginas(html):
    """El paginador trae <a data-pagina="N">; el mayor es la última página."""
    n = [int(x) for x in RE_PAGS.findall(html or "")]
    return max(n) if n else None


def parse_cards(html):
    """
    Una fila por propiedad. Cada aviso es un <div class="propiedad-box"
    data-id="..." data-coords='{"lat":..,"lng":..}'>, y la foto viene como
    background-image del <a class="propiedad-imagen">, no como <img>.
    """
    soup = BeautifulSoup(html, "html.parser")
    filas = []

    for box in soup.select("div.propiedad-box"):
        enlaces = box.find_all("a", href=RE_PROP)
        if not enlaces:
            continue
        m = RE_PROP.search(enlaces[0]["href"])
        pid = box.get("data-id") or m.group(1)

        foto = box.find("a", class_="propiedad-imagen") or enlaces[0]
        mb = RE_BG.search(foto.get("style") or "")
        imagen = None
        if mb:
            imagen = mb.group(1).split("?")[0].strip()
            if imagen.startswith("/"):
                imagen = BASE + imagen

        lat = lng = None
        if box.get("data-coords"):
            try:
                c = json.loads(box["data-coords"])
                lat, lng = c.get("lat"), c.get("lng")
            except (ValueError, TypeError):
                pass

        texto = " ".join(box.get_text(" ", strip=True).split())
        inmo = box.find("a", href=RE_INMO)
        mp, md = RE_PRECIO.search(texto), RE_DORM.search(texto)
        titulo = max((a.get_text(" ", strip=True) for a in enlaces), key=len, default="")

        filas.append({
            "id": pid,
            "url": f"{BASE}/propiedad/{pid}/{m.group(2)}",
            "titulo": titulo,
            "tipo": next((t for t in TIPOS if t.lower() in texto.lower()), None),
            "moneda": mp.group(1) if mp else None,
            "precio": _num(mp.group(2)) if mp else None,
            "dormitorios": int(md.group(1)) if md else None,
            "inmobiliaria": inmo.get_text(strip=True) if inmo else None,
            "imagen": imagen,
            "lat": lat,
            "lng": lng,
        })
    return filas


def buscar(tipos, lugar, max_precio, delay=1.0, extra=None, verbose=True):
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; alerta-alquiler-personal)",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": BASE + "/buscar",
    })

    todas, ids = {}, set()

    def sumar(cards):
        agregadas = 0
        for f in cards:
            if f["id"] in ids:
                continue
            ids.add(f["id"])
            agregadas += 1
            if tipos and (f["tipo"] or "").lower() not in {t.lower() for t in tipos}:
                continue
            if lugar and lugar.lower() not in (f["titulo"] or "").lower():
                continue
            if max_precio and f["moneda"] == "$" and (f["precio"] or 0) > max_precio:
                continue
            todas[f["id"]] = f
        return agregadas

    try:
        primera = fetch(s, 0, extra)
    except Exception as e:
        print(f"  ! no pude leer la primera página: {e}", file=sys.stderr)
        return {}

    html = primera.get("html") or ""
    paginas = total_paginas(html) or 1
    mt = RE_TOTAL.search(html)
    if verbose and mt:
        print(f"el sitio declara {mt.group(1)} publicaciones en {paginas} páginas")
    sumar(parse_cards(html))

    for pagina in range(1, paginas):
        time.sleep(delay)
        for intento in range(3):
            try:
                data = fetch(s, pagina, extra)
                break
            except Exception as e:
                print(f"  ! página {pagina}, intento {intento + 1}: {e}", file=sys.stderr)
                time.sleep(3)
        else:
            continue                       # esta página se pierde, seguimos
        sumar(parse_cards(data.get("html") or ""))

    return todas


def fmt(f):
    precio = f"{f['moneda']} {f['precio']:,}".replace(",", ".") if f["precio"] else "s/precio"
    dorm = f" · {f['dormitorios']} dorm" if f["dormitorios"] else ""
    return (f"  {f['titulo'] or '(sin título)'}\n"
            f"    {precio}{dorm} · {f['inmobiliaria'] or '?'}\n"
            f"    {f['url']}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tipo", action="append", dest="tipos", default=None)
    p.add_argument("--lugar", default="Bahía Blanca")
    p.add_argument("--max-precio", type=int)
    p.add_argument("--todo", action="store_true", help="listar todo, no solo novedades")
    p.add_argument("--ciudad", default="1", help="id de ciudad (1 = Bahía Blanca)")
    p.add_argument("--inmueble-id", action="append", dest="inmueble_ids",
                   help="id de tipo de inmueble, filtra en el server")
    p.add_argument("--sin-filtro-local", action="store_true",
                   help="confía solo en los filtros del servidor")
    p.add_argument("--resumen", metavar="ARCHIVO",
                   help="escribe las novedades en un archivo de texto "
                        "(para notificaciones); si no hay, no lo escribe")
    p.add_argument("--delay", type=float, default=1.0)
    args = p.parse_args()
    tipos = args.tipos or ["Casa"]

    extra = {}
    if args.ciudad:
        extra["ciudad"] = args.ciudad
    if args.inmueble_ids:
        extra["inmueble_id[]"] = args.inmueble_ids

    t_local = None if args.sin_filtro_local else tipos
    l_local = None if args.sin_filtro_local else args.lugar

    print(f"buscando {'/'.join(tipos).lower()}s en alquiler"
          f"{' en ' + args.lugar if args.lugar else ''}...")
    actuales = buscar(t_local, l_local, args.max_precio, args.delay, extra)
    if not actuales:
        print("no se encontró nada — revisá los filtros o avisá que cambió el sitio")
        return

    sin_foto = sum(1 for v in actuales.values() if not v.get("imagen"))
    print(f"{len(actuales)} publicaciones activas"
          + (f" ({sin_foto} sin foto)" if sin_foto else "") + "\n")

    previas, previo_ts = {}, None
    if os.path.exists(ESTADO):
        with open(ESTADO, encoding="utf-8") as f:
            _est = json.load(f)
        previas = _est.get("propiedades", {})
        previo_ts = _est.get("actualizado")

    nuevas, bajas, fuera = [], [], []
    if not previas:
        print("Primera corrida: guardé la foto inicial.")
        print("Volvé a correrlo en unos días y te aviso qué cambió.")
    else:
        nuevas = [f for i, f in actuales.items() if i not in previas]
        bajas = [(f, previas[i]["precio"]) for i, f in actuales.items()
                 if i in previas and f["precio"] and previas[i].get("precio")
                 and f["precio"] < previas[i]["precio"]]
        fuera = [v for i, v in previas.items() if i not in actuales]

        if nuevas:
            print(f"=== {len(nuevas)} NUEVA(S) ===")
            for f in nuevas:
                print(fmt(f))
            print()
        if bajas:
            print(f"=== {len(bajas)} BAJARON DE PRECIO ===")
            for f, antes in bajas:
                print(f"  antes {f['moneda']} {antes:,}".replace(",", "."))
                print(fmt(f))
            print()
        if fuera:
            print(f"=== {len(fuera)} YA NO ESTÁN ===")
            for v in fuera:
                print(f"  {v.get('titulo') or v.get('url')}")
            print()
        if not (nuevas or bajas or fuera):
            print("Sin novedades desde la última corrida.")

    if args.todo:
        print("=== LISTADO COMPLETO ===")
        for f in sorted(actuales.values(), key=lambda x: x["precio"] or 0):
            print(fmt(f))

    if args.resumen:
        def plata(f, p=None):
            p = f["precio"] if p is None else p
            return f"{f['moneda']} {p:,}".replace(",", ".") if p else "a consultar"

        titular = []
        if nuevas:
            titular.append(f"{len(nuevas)} nueva" + ("s" if len(nuevas) > 1 else ""))
        if bajas:
            titular.append(f"{len(bajas)} bajó de precio" if len(bajas) == 1
                           else f"{len(bajas)} bajaron de precio")
        if fuera:
            titular.append(f"{len(fuera)} dada de baja" if len(fuera) == 1
                           else f"{len(fuera)} dadas de baja")

        cuerpo = []
        for f in nuevas:
            d = f"{f['dormitorios']} dorm" if f["dormitorios"] else "s/dato"
            cuerpo.append(f"{plata(f)} · {d} · {zona(f['titulo'])}")
        for f, antes in bajas:
            cuerpo.append(f"Bajó a {plata(f)} (era {plata(f, antes)}) · {zona(f['titulo'])}")
        for v in fuera:
            cuerpo.append(f"Se dio de baja: {zona(v.get('titulo'))}")

        # primera línea = título de la notificación, el resto = cuerpo.
        # Si no hay nada, no se escribe el archivo y el workflow no notifica.
        if titular:
            with open(args.resumen, "w", encoding="utf-8") as f:
                f.write(" · ".join(titular) + "\n" + "\n".join(cuerpo))
        elif os.path.exists(args.resumen):
            os.remove(args.resumen)

    ahora = datetime.now().isoformat(timespec="seconds")
    hubo_baseline = bool(previas)
    for i, f in actuales.items():
        prev = previas.get(i, {})
        if prev:
            f["visto_desde"] = prev.get("visto_desde") or previo_ts or ahora
            f["nueva_en"] = prev.get("nueva_en")
        else:
            f["visto_desde"] = ahora
            # solo es novedad si apareció DESPUÉS de la foto inicial
            f["nueva_en"] = ahora if hubo_baseline else None

    with open(ESTADO, "w", encoding="utf-8") as f:
        json.dump({"actualizado": ahora, "propiedades": actuales},
                  f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
