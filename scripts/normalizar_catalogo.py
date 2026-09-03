#!/usr/bin/env python3
import csv, io, os, re, sys, unicodedata, urllib.request
from datetime import datetime, timezone
from pathlib import Path
URL = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("LOGISTA_URL")
ROOT = Path(__file__).resolve().parents[1]
def norm(s):
    s=str(s or "").strip().lower()
    s=unicodedata.normalize("NFKD",s)
    return "".join(c for c in s if not unicodedata.combining(c))
def decode(data):
    for e in ("utf-8-sig","utf-8","cp1252","latin-1"):
        try: return data.decode(e)
        except UnicodeDecodeError: pass
    return data.decode("latin-1",errors="replace")
def dialect(text):
    try: return csv.Sniffer().sniff(text[:10000],delimiters=";,|\t,")
    except csv.Error:
        counts={d:text[:10000].count(d) for d in (";",",","\t","|")}
        d=max(counts,key=counts.get)
        return type("D",(),{"delimiter":d})()
def col(headers, names):
    nh={norm(h):h for h in headers}
    for n in names:
        if norm(n) in nh: return nh[norm(n)]
    for h in headers:
        if any(norm(n) in norm(h) for n in names): return h
    return None
def price(v):
    s=str(v or "").strip().replace("€","").replace(" ","")
    if "," in s and "." in s:
        s=s.replace(".","").replace(",",".") if s.rfind(",")>s.rfind(".") else s.replace(",","")
    elif "," in s: s=s.replace(",",".")
    elif ":" in s: s=s.replace(":","." )
    try: return f"{float(s):.2f}"
    except ValueError: return None
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 (PRECIOSTABACO/1.0)"})
with urllib.request.urlopen(req,timeout=60) as r: text=decode(r.read())
reader=csv.DictReader(io.StringIO(text),dialect=dialect(text))
headers=reader.fieldnames or []
code=col(headers,["codigo","código","codigo sap","referencia"])
desc=col(headers,["descripcion","descripción","nombre"])
pcol=col(headers,["precio (eur)","precio eur","precio","pvp"])
ucol=col(headers,["lote min","lote minimo","lote mínimo"])
mcol=col(headers,["um"])
if not code or not pcol: raise SystemExit(f"Columnas no reconocidas: {headers}")
if not ucol: print(f"[AVISO] No se encontró columna de unidades. Cabeceras disponibles: {headers}")
if not mcol: print(f"[AVISO] No se encontró columna UM. Cabeceras disponibles: {headers}")
rows=[]
for r in reader:
    c=str(r.get(code,"") or "").strip()
    p=price(r.get(pcol,""))
    d=str(r.get(desc,"") or "").strip() if desc else ""
    u=str(r.get(ucol,"") or "").strip() if ucol else ""
    m=str(r.get(mcol,"") or "").strip() if mcol else ""
    if c and p is not None: rows.append((c,d,p,u,m))
rows.sort()

# --- Archivo principal (formato actual: codigo;descripcion;precio) ---
out=io.StringIO(newline="")
w=csv.writer(out,delimiter=";",lineterminator="\n")
w.writerow(["codigo","descripcion","precio"])
w.writerows((c,d,p) for c,d,p,u,m in rows)
content=out.getvalue()

# --- Archivo con unidades y UM: CODIGO,DESCRIPCION,UNIDADES,UM,PRECIO (separador ; , precio con coma decimal) ---
out2=io.StringIO(newline="")
w2=csv.writer(out2,delimiter=";",lineterminator="\n")
w2.writerow(["codigo","descripcion","unidades","um","precio"])
w2.writerows((c,d,u,m,p.replace(".",",")) for c,d,p,u,m in rows)
content2=out2.getvalue()

# Detección de cambios: se basa en el archivo con unidades (es superset de la info)
latest=0
for p in ROOT.glob("PRECIOSTABACO_UNIDADES*.csv"):
    m=re.fullmatch(r"PRECIOSTABACO_UNIDADES(\d+)\.csv",p.name)
    if m: latest=max(latest,int(m.group(1)))
old=ROOT/f"PRECIOSTABACO_UNIDADES{latest}.csv" if latest else None
if old and old.read_text(encoding="utf-8")==content2:
    print("Sin cambios.")
    raise SystemExit(0)

v=latest+1
(ROOT/f"PRECIOSTABACO{v}.csv").write_text(content,encoding="utf-8",newline="")
(ROOT/f"PRECIOSTABACO_UNIDADES{v}.csv").write_text(content2,encoding="utf-8",newline="")
(ROOT/"ultimo.txt").write_text(str(v)+"\n",encoding="utf-8")
(ROOT/"fecha_actualizacion.txt").write_text(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")+"\n",encoding="utf-8")
print(f"PRECIOSTABACO{v}.csv y PRECIOSTABACO_UNIDADES{v}.csv: {len(rows)} productos")
