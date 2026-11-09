#!/usr/bin/env python3
"""Comprueba que los enlaces de la documentación siguen respondiendo.

Uso: python3 tests/check_links.py [archivos .md ...]
Por defecto revisa skills/bulonator/references/*.md. Requiere conexión a internet,
por eso no forma parte de las pruebas unitarias (se ejecuta a mano o de forma programada en CI).

Resultado por enlace:
  OK         2xx o 3xx
  BLOQUEADO  403/405/429/5xx o error TLS: el sitio rechaza clientes automáticos; revísalo a mano
  ROTO       404/410 o el dominio no resuelve
"""
from __future__ import annotations

import re
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
LINK = re.compile(r"<(https?://[^>\s]+)>|\]\((https?://[^)\s]+)\)")
# El propio repositorio y sus paquetes de PyPI no se pueden comprobar antes de publicarlos
SKIP = ("github.com/bbotella/bulonator", "pypi.org/project/bulonator", "ejemplo.", "example.")


def check(url: str) -> tuple[str, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return "OK", str(r.status), url
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return "ROTO", str(e.code), url
        return "BLOQUEADO", str(e.code), url
    except (urllib.error.URLError, ssl.SSLError, TimeoutError, OSError) as e:
        reason = str(getattr(e, "reason", e))
        if "Name or service not known" in reason or "nodename nor servname" in reason or "getaddrinfo" in reason:
            return "ROTO", "DNS", url
        return "BLOQUEADO", reason[:60], url


def main(argv: list[str]) -> int:
    files = [Path(a) for a in argv] or sorted((ROOT / "skills" / "bulonator" / "references").glob("*.md"))
    found = (a or b for f in files for a, b in LINK.findall(f.read_text(encoding="utf-8")))
    urls = sorted({u.rstrip(".,") for u in found if not any(s in u for s in SKIP)})
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(check, urls))
    broken = 0
    for status, code, url in sorted(results):
        if status != "OK":
            print(f"{status:10} {code:>6}  {url}")
        broken += status == "ROTO"
    print(f"\n{len(urls)} enlaces: {sum(r[0] == 'OK' for r in results)} OK, "
          f"{sum(r[0] == 'BLOQUEADO' for r in results)} bloqueados, {broken} rotos")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
