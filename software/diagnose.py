"""AETHER 102.3 - Diagnose-Seite im Heimnetz: http://webradio.local:8080
Zeigt Status und Log von fm.py und kann Tasten der Fernbedienung ausloesen (zum Testen ohne Terminal).
Nur lesen + Radio-Bedienung; keine Systembefehle."""
import collections
import html
import json
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PORT = 8080
LOG = collections.deque(maxlen=2000)            # letzte Ausgaben von fm.py (print wird hierher kopiert)
ZAEHLER = collections.Counter()                 # z. B. i2c_aussetzer, i2c_neustart, taster, ir
STATUS = {}                                     # wird von fm.py laufend aktualisiert
WUNSCH = {}                                     # Auftraege an die Hauptschleife (I2C nur dort)
AKTIONEN = ["start_stop", "weiter", "zurueck", "lauter", "leiser",
            "favorit1", "favorit2", "favorit3", "favorit4", "favorit5", "info"]


def protokoll(text):
    LOG.append(f"{time.strftime('%H:%M:%S')} {text}")


def _cmd(*args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception as e:
        return f"({e})"


TEST = {"laeuft": False, "bericht": []}


def _snap(lbl):
    z = zustand()
    m = z["mpc"].splitlines()
    zeile = (f"{time.strftime('%H:%M:%S')} {lbl:<12} | {z.get('status')} | sendet={z.get('sendet')} spielt={z.get('spielt')} "
             f"pegel={z.get('pegel_db')} C={z.get('antenne_pf')} | {m[1] if len(m) > 1 else '-'} | "
             f"{(m[2].split('   ')[0] if len(m) > 2 else '')} | zaehler={dict(ZAEHLER)}")
    TEST["bericht"].append(zeile)


def selbsttest(fb, dauer_s=300):
    """Alle Funktionen der Reihe nach ausloesen, danach dauer_s Sekunden Dauertest (I2C, Pegel, Antenne)."""
    if TEST["laeuft"]:
        return
    TEST.update(laeuft=True, bericht=[], start=time.strftime("%H:%M:%S"))
    protokoll("SELBSTTEST gestartet")
    try:
        _snap("start")
        for name, warte in [("start_stop", 6), ("start_stop", 12), ("lauter", 3), ("lauter", 3), ("leiser", 3),
                            ("leiser", 3), ("weiter", 12), ("zurueck", 12), ("favorit2", 12), ("favorit1", 12),
                            ("info", 3), ("info", 3)]:
            fb.ausfuehren(name)
            time.sleep(warte)
            _snap(name)
        ende = time.monotonic() + dauer_s
        while time.monotonic() < ende:
            time.sleep(15)
            _snap("dauertest")
    except Exception as e:
        TEST["bericht"].append(f"FEHLER im Test: {e!r}")
    TEST["laeuft"] = False
    protokoll("SELBSTTEST fertig")


def zustand():
    z = dict(STATUS)
    z["zaehler"] = dict(ZAEHLER)
    z["uptime_s"] = float(open("/proc/uptime").read().split()[0])
    z["throttled"] = _cmd("vcgencmd", "get_throttled")
    z["mpc"] = _cmd("mpc", "status")
    return z


SEITE = """<!doctype html><html lang=de><meta charset=utf-8><meta name=viewport content="width=device-width">
<title>AETHER Diagnose</title><style>
body{{font:14px -apple-system,system-ui,sans-serif;margin:16px;background:#111;color:#eee}}
h1{{font-size:18px}} pre{{background:#000;padding:8px;white-space:pre-wrap;font:12px ui-monospace,monospace}}
button{{margin:2px;padding:6px 10px;background:#333;color:#eee;border:1px solid #555;border-radius:4px}}
td{{padding:2px 8px;vertical-align:top}}</style>
<h1>&AElig;THER 102.3 &ndash; Diagnose</h1>
<p>{knoepfe}</p>
<table>{zeilen}</table>
<h2>Log (neueste unten)</h2><pre id=log>{log}</pre>
<script>
document.querySelectorAll('button').forEach(b=>b.onclick=()=>fetch('/aktion?name='+b.dataset.a,{{method:'POST'}}).then(()=>setTimeout(()=>location.reload(),1500)));
window.scrollTo(0,document.body.scrollHeight);
</script></html>"""


class Handler(BaseHTTPRequestHandler):
    fb = None

    def log_message(self, *a):
        pass

    def _senden(self, code, typ, text):
        b = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/status.json":
            return self._senden(200, "application/json", json.dumps(zustand(), indent=1, default=str))
        if u.path == "/log":
            n = int(q.get("n", ["300"])[0])
            return self._senden(200, "text/plain; charset=utf-8", "\n".join(list(LOG)[-n:]))
        if u.path == "/selbsttest":
            if q.get("start") and self.fb is not None and not TEST["laeuft"]:
                dauer = int(q.get("dauer", ["300"])[0])
                threading.Thread(target=selbsttest, args=(self.fb, dauer), daemon=True).start()
                time.sleep(0.5)
            text = (f"Selbsttest: {'LAEUFT' if TEST['laeuft'] else 'fertig/bereit'} (Start {TEST.get('start', '-')})\n"
                    + "\n".join(TEST["bericht"]) + "\n\n--- Log ---\n" + "\n".join(list(LOG)[-120:]))
            return self._senden(200, "text/plain; charset=utf-8", text)
        if u.path == "/antenne":                        # Antennen-C: pf=0 (automatisch) oder 0.25..47.75; speichern=1 dauerhaft
            try:
                pf = round(float(q.get("pf", [""])[0]) * 4) / 4
            except ValueError:
                pf = -1
            if pf == 0 or 0.25 <= pf <= 47.75:
                WUNSCH["antenne"] = (pf, bool(q.get("speichern")))
                protokoll(f"Diagnose-Seite: Antennen-C -> {pf}")
                return self._senden(200, "text/plain", f"Antennen-C wird auf {pf} pF gesetzt (0 = automatisch)")
            return self._senden(400, "text/plain", "pf 0 oder 0.25..47.75")
        if u.path == "/leistung":                       # Sendeleistung testweise aendern (88..115), bis zum Neustart
            try:
                w = int(q.get("wert", [""])[0])
            except ValueError:
                w = 0
            if 88 <= w <= 115:
                WUNSCH["leistung"] = w
                protokoll(f"Diagnose-Seite: Leistung -> {w}")
                return self._senden(200, "text/plain", f"Leistung wird auf {w} gesetzt")
            return self._senden(400, "text/plain", "wert 88..115")
        if u.path == "/aktion" and q.get("name", [""])[0] in AKTIONEN and self.fb is not None:
            name = q["name"][0]
            protokoll(f"Diagnose-Seite: Aktion {name}")
            threading.Thread(target=self.fb.ausfuehren, args=(name,), daemon=True).start()
            return self._senden(200, "text/plain", "ok " + name)
        if u.path == "/":
            z = zustand()
            zeilen = "".join(f"<tr><td>{html.escape(str(k))}</td><td><pre>{html.escape(str(v))}</pre></td></tr>"
                             for k, v in z.items())
            knoepfe = "".join(f"<button data-a={a}>{a}</button>" for a in AKTIONEN)
            log = html.escape("\n".join(list(LOG)[-150:]))
            return self._senden(200, "text/html; charset=utf-8", SEITE.format(knoepfe=knoepfe, zeilen=zeilen, log=log))
        self._senden(404, "text/plain", "nicht gefunden")

    def do_POST(self):
        u = urlparse(self.path)
        name = parse_qs(u.query).get("name", [""])[0]
        if u.path == "/aktion" and name in AKTIONEN and self.fb is not None:
            protokoll(f"Diagnose-Seite: Aktion {name}")
            threading.Thread(target=self.fb.ausfuehren, args=(name,), daemon=True).start()
            return self._senden(200, "text/plain", "ok")
        self._senden(400, "text/plain", "unbekannte Aktion")


def starten(fb):
    Handler.fb = fb
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    except OSError as e:
        protokoll(f"Diagnose-Seite nicht gestartet ({e})")
        return
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    protokoll(f"Diagnose-Seite: http://webradio.local:{PORT}")
