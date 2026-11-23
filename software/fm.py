#!/usr/bin/env python3
"""fm.py (V7) - steuert das Si4713-UKW-Modul, das 1,3"-OLED, die IR-Fernbedienung und den Neustart-Taster.
FM webradio for the B&O 9300 - controls the Si4713 FM transmitter, a 1.3" OLED, an IR remote and a reboot button."""
import json
import os
import socket
import struct
import threading
import subprocess
import time
import board, busio, digitalio
import adafruit_si4713
import builtins
import diagnose                      # Diagnose-Seite http://webradio.local:8080


def print(*args, **kw):              # alles Ausgegebene auch auf der Diagnose-Seite zeigen
    builtins.print(*args, **kw)
    diagnose.protokoll(" ".join(str(a) for a in args))

# ===== Einstellungen / Settings =====
FREQUENZ_KHZ = 102300        # 102300 = 102,3 MHz
ANTENNE_DATEI = "/home/oliver/.aether_antenne"   # fest eingestellte Antennen-C in pF (0 = automatisch), per Diagnose-Seite gespeichert
LEISTUNG     = 88            # 88 (minimum) .. 115 (maximum); V7f: nur noch 1 Daempfer -> Minimum reicht, am wenigsten HF im Gehaeuse


def antenne_pf():
    """Antennen-Kapazitaet: 0 = automatische Abstimmung (Chip-Standard), sonst fester Wert 0,25..47,75 pF."""
    try:
        v = float(open(ANTENNE_DATEI).read().strip())
        return v if v == 0 or 0.25 <= v <= 47.75 else 0
    except (OSError, ValueError):
        return 0


ANTENNE_PF = antenne_pf()


def leistung_setzen(fm, p):
    """Sendeleistung (0 = Traeger aus) mit der eingestellten Antennen-C setzen.
    Bei Kabeleinspeisung (75 Ohm) findet die Automatik oft keinen sinnvollen Wert - deshalb einstellbar."""
    fm.set_tx_power_capacitance(p, ANTENNE_PF if p else 0)
ADRESSE      = 0x63          # Si4713: 0x63 oder/or 0x11
SENDERNAME   = "WEBRADIO"    # RDS, max. 8 Zeichen/characters
METADATEN    = "/var/local/www/currentsong.txt"   # moOde: Metadata file = ON
OLED_ADRESSE = 0x3C          # SH1106: 0x3C oder/or 0x3D, None = ohne Display/no display
OLED_BUS     = 3             # V7: eigener I2C-Bus (GPIO 22 = SDA Pin 15, GPIO 27 = SCL Pin 13), entlastet den Si4713-Bus
WECHSEL_S    = 4             # Sekunden zwischen Sender- und Titelanzeige / station <-> title
# Taster zwischen GPIO und GND (interner Pull-up); None = nicht vorhanden / not fitted
T_STARTSTOP  = None          # V5: 17 (Pin 11)  Start/Stop
T_WEITER     = None          # V5: 27 (Pin 13)  naechster Favorit
T_LAUTER     = None          # V5: 22 (Pin 15)  Lautstaerke +
T_LEISER     = None          # V5: 23 (Pin 16)  Lautstaerke -
T_NEUSTART   = None          # V6: Taster haengt an J2 (Power-Anschluss des Pi 5), nicht an einem GPIO
# IR-Fernbedienung: Empfaenger-Signal an GPIO 23 (Pin 16), Overlay dtoverlay=gpio-ir,gpio_pin=23
IR_DATEI     = "/home/oliver/ir_tasten.json"   # erstellt von ir_lernen.py
IR_NAME      = "gpio_ir_recv"                   # Name des Linux-Eingabegeraets
POWER_NAME   = "pwr_button"                     # Taster an J2 (Pi 5): kurz = Start/Stop (lang = Linux faehrt herunter)
POWER_KURZ_S = 1.5                              # kuerzer gedrueckt = Start/Stop
LANG_S       = 3             # Neustart-Taste so lange halten / hold time for reboot
LAUT_SCHRITT = 2             # Lautstaerke-Schritt Fernbedienung in % / volume step
FAVORITEN    = []            # max. 5 Sender-URLs/Dateien; leer = erste 5 der moOde-Favoriten
STILLE_DB    = -50           # leiser als das = Stille / below this level = silence (dBFS)
STILLE_S     = 50            # nach so vielen Sekunden Stille Sender aus (BAKOM: max. 60 s)
HAENGT_S     = 15            # Stream spielt, aber so lange Stille / unerwartet gestoppt -> neu starten
NEUSTART_NACH_STOP = True    # auch neu starten, wenn moOde ohne Stop-Taste stoppt (Stream-Abbruch)
# Pegelanzeige (wie Kassettendeck) / level meter
CLIP_DB      = -8            # ab hier meldet der Si4713 Uebersteuerung (Test 30.10.) = "0" auf der Skala
METER_S      = 0.15          # so oft den Pegel messen (s); bei I2C 50 kHz auf 0.25 erhoehen
# Automatische Aussteuerung (regelt die moOde-Lautstaerke) / automatic level control
AUTO_PEGEL   = True          # False = aus
AUTO_MIN, AUTO_MAX = 30, 75  # Grenzen in %
AUTO_ZU_LEISE = -10          # Spitzen 20 s lang unter -10 dB (relativ zu CLIP) -> +5 %
AUTO_STILLE   = -35          # darunter gilt es als Pause/Stille -> nichts aendern
AUTO_RUNTER, AUTO_RAUF = 5, 2   # Schritte in %: bei CLIP schnell runter, beim Anheben in kleinen Schritten
# Selbstueberwachung / self-monitoring (Plug and Play)
OFFLINE_WLAN_NEU_S = 120     # so lange ohne Internet -> WLAN aus/ein
OFFLINE_REBOOT_S   = 600     # so lange ohne Internet -> Pi neu starten
TEMP_WARN          = 80      # °C -> Warnung auf dem Display
MPD_SCHONFRIST_S   = 120     # so lange nach dem Start wird moOde/mpd noch nicht geprueft
MPD_FEHLER_MAX     = 6       # so oft hintereinander keine Antwort von moOde/mpd -> mpd neu starten
# ====================================

UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
                         "ß": "ss", "é": "e", "è": "e", "à": "a", "ç": "c"})


def ascii_text(text):
    """Fuer RDS: nur ASCII / RDS needs plain ASCII."""
    return text.translate(UMLAUTE).encode("ascii", "replace").decode("ascii")


def mpd_meta():
    """Fallback ohne moOde-Metadatei: Sender/Titel/Status direkt von mpd (Port 6600)."""
    try:
        with socket.create_connection(("127.0.0.1", 6600), timeout=2) as c:
            f = c.makefile("rwb")
            if not f.readline().startswith(b"OK MPD"):
                return {}
            werte = {}
            for befehl in (b"currentsong\n", b"status\n"):
                f.write(befehl); f.flush()
                for z in iter(f.readline, b""):
                    z = z.decode("utf-8", "replace").rstrip("\n")
                    if z == "OK" or z.startswith("ACK"):
                        break
                    k, _, v = z.partition(": ")
                    werte[k.lower()] = v.strip()
    except OSError:
        return {}
    if not werte.get("file"):
        return {}
    titel = werte.get("title", "")
    sender = werte.get("name") or werte.get("album") or werte.get("artist") or "Internetradio"
    if not werte.get("name") and ": " in titel:          # z. B. "Swiss Pop: Interpret - Titel"
        sender, titel = titel.split(": ", 1)
    return {"album": sender, "title": titel, "state": werte.get("state", "play")}


def lies_meta():
    """Liest Sender und Titel aus moOde / reads station and title from moOde."""
    werte = {}
    try:
        with open(METADATEN, encoding="utf-8") as f:
            for zeile in f:
                if "=" in zeile:
                    k, v = zeile.rstrip("\n").split("=", 1)
                    werte[k] = v.strip()
    except OSError:
        pass
    if not werte:                       # Metadaten-Datei leer/aus: direkt bei mpd nachfragen
        werte = mpd_meta()
    if not werte:
        return None, "", False          # moOde laedt noch / still loading
    sender = werte.get("album") or werte.get("artist") or "Internetradio"
    titel = werte.get("title") or ""
    spielt = werte.get("state", "play") == "play"
    return sender, titel, spielt


def mpc(*args):
    r = subprocess.run(["mpc", *args], capture_output=True, text=True)
    return r.stdout


# ---------- Display ----------
class Anzeige:
    """1,3"-OLED 128x64 (SH1106) ueber I2C; laeuft ohne Display einfach weiter."""
    def __init__(self, adresse):
        self.dev = None
        self.letzte = None
        if adresse is None:
            return
        try:
            from luma.core.interface.serial import i2c
            from luma.oled.device import sh1106
            from PIL import ImageFont
            self.dev = sh1106(i2c(port=OLED_BUS, address=adresse), width=128, height=64)
            pfad = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            try:
                self.gross = ImageFont.truetype(pfad.replace(".ttf", "-Bold.ttf"), 14)
                self.klein = ImageFont.truetype(pfad, 10)
                self.mini = ImageFont.truetype(pfad.replace(".ttf", "-Bold.ttf"), 7)
            except OSError:
                self.gross = self.klein = self.mini = ImageFont.load_default()
            self.start("Radio startet")
        except Exception as e:      # Display fehlt oder falsche Adresse
            print(f"OLED nicht gefunden ({e}) - weiter ohne Display")
            self.dev = None

    def start(self, text, gesamt=None):
        """Startbild mit Countdown (gleiches Bild wie die Startanzeige beim Booten)."""
        if not self.dev:
            return
        from luma.core.render import canvas
        import boot_anzeige
        if not hasattr(self, "start_fonts"):
            self.start_fonts = boot_anzeige.schriften()
        self.letzte = None
        try:
            with canvas(self.dev) as d:
                boot_anzeige.zeichne_start(d, self.start_fonts, text, gesamt=gesamt)
        except OSError:
            pass

    @staticmethod
    def _kuerzen(draw, text, font, breite=126):
        while text and draw.textlength(text, font=font) > breite:
            text = text[:-1]
        return text

    def _zeilen(self, draw, text, font, n, breite=126):
        """Bricht Text auf n Zeilen um / wraps text onto n lines."""
        woerter, zeilen, z = text.split(), [], ""
        for w in woerter:
            t = (z + " " + w).strip()
            if draw.textlength(t, font=font) <= breite:
                z = t
            else:
                if z:
                    zeilen.append(z)
                z = w
        if z:
            zeilen.append(z)
        zeilen = zeilen[:n]
        return [self._kuerzen(draw, x, font) for x in zeilen]

    def zeigen(self, oben, mitte, unten, vu=None, wlan=None, temp=None):
        """oben = Sender (fett), mitte = Titel, unten = Statuszeile, vu = (pegel_rel, spitze_rel, clip) oder None,
        wlan = 0..4 Balken, "LAN" oder None (oben rechts)."""
        if not self.dev or (oben, mitte, unten, vu, wlan, temp) == self.letzte:
            return
        from luma.core.render import canvas
        try:
            with canvas(self.dev) as d:
                rechts = 0 if wlan is None else 18
                d.text((0, -2), self._kuerzen(d, oben, self.gross, 126 - rechts), font=self.gross, fill="white")
                if wlan == "LAN":
                    d.text((112, 0), "LAN", font=self.mini, fill="white")
                elif wlan is not None:
                    for i in range(4):                   # WLAN-Balken
                        h = 3 + i * 2; x = 112 + i * 4
                        if i < wlan:
                            d.rectangle((x, 10 - h, x + 2, 10), fill="white")
                        else:
                            d.rectangle((x, 10 - h, x + 2, 10), outline="white")
                    if wlan == 0:
                        d.line((110, 0, 127, 11), fill="white")
                for i, z in enumerate(self._zeilen(d, mitte, self.klein, 2)):
                    d.text((0, 15 + i * 11), z, font=self.klein, fill="white")
                if vu is None:
                    d.line((0, 50, 127, 50), fill="white")
                else:
                    self._meter(d, *vu)
                breite = 126
                if temp is not None:                     # Pi-Temperatur rechts in der Statuszeile
                    tt = f"{temp:.0f}\u00b0C"
                    tw = d.textlength(tt, font=self.klein)
                    d.text((127 - tw, 53), tt, font=self.klein, fill="white")
                    breite = int(124 - tw)
                d.text((0, 53), self._kuerzen(d, unten, self.klein, breite), font=self.klein, fill="white")
            self.letzte = (oben, mitte, unten, vu, wlan, temp)
        except OSError:
            self.letzte = None

    def infoseite(self, w, temp, volt):
        """Systemseite: 6 Zeilen klein."""
        if not self.dev:
            return
        from luma.core.render import canvas
        t = int(w["up"]); tage, rest = divmod(t, 86400)
        zeilen = [f"CPU {w['cpu']:3.0f} %   RAM {w['ram']:3.0f} %",
                  f"Temp {temp or 0:.0f}\u00b0C" + (f"  Luefter {w['luefter']}" if w["luefter"] is not None else ""),
                  f"Netzteil {volt:.2f} V".replace(".", ",") if volt else "Netzteil -",
                  f"WLAN {w['dbm']:.0f} dBm" if w["dbm"] is not None else "LAN",
                  f"IP {w['ip']}",
                  f"Laeuft {tage} d {rest // 3600:02d}:{rest % 3600 // 60:02d}"]
        try:
            with canvas(self.dev) as d:
                for i, z in enumerate(zeilen):
                    d.text((0, i * 10.6 - 1), z, font=self.klein, fill="white")
            self.letzte = None
        except OSError:
            pass

    # Skala relativ zu CLIP_DB: -20 ... +3 dB, 1 Segment = 1 dB; ab 0 "roter Bereich" (hohe Segmente)
    M_MIN, M_MAX, M_X0, M_Y = -20, 3, 2, 47

    def _meter(self, d, rel, spitze, clip):
        n = self.M_MAX - self.M_MIN
        sw = (127 - 24 - self.M_X0) // n                     # Segmentbreite (inkl. 1 px Luecke)
        for i in range(n):
            db = self.M_MIN + i + 1
            x = self.M_X0 + i * sw
            rot = db > 0
            h = 7 if rot else 4
            an = rel >= db or (spitze >= db > spitze - 1)    # Balken oder Spitzenwert-Segment
            if an:
                d.rectangle((x, self.M_Y - h, x + sw - 2, self.M_Y), fill="white")
            elif rot:
                d.rectangle((x, self.M_Y - h, x + sw - 2, self.M_Y), outline="white")
            else:
                d.point((x + (sw - 2) // 2, self.M_Y), fill="white")
        for db, txt in ((-15, "15"), (-10, "10"), (-5, "5"), (0, "0")):  # Skala unter dem Balken
            x = self.M_X0 + (db - self.M_MIN) * sw - 1
            d.line((x, self.M_Y + 1, x, self.M_Y + 2), fill="white")
        xc = 127 - 21                                         # CLIP-Lampe
        if clip:
            d.rectangle((xc, self.M_Y - 8, 127, self.M_Y), fill="white")
            d.text((xc + 2, self.M_Y - 9), "CLIP", font=self.mini, fill="black")
        else:
            d.rectangle((xc, self.M_Y - 8, 127, self.M_Y), outline="white")
            d.text((xc + 2, self.M_Y - 9), "CLIP", font=self.mini, fill="white")


def sd_notify(nachricht):
    """Meldung an systemd (Type=notify + WatchdogSec): READY=1 beim Start, WATCHDOG=1 regelmaessig."""
    adr = os.environ.get("NOTIFY_SOCKET")
    if not adr:
        return
    if adr.startswith("@"):
        adr = "\0" + adr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s_:
            s_.sendto(nachricht.encode(), adr)
    except OSError:
        pass


def sudo(*cmd):
    """Befehl mit Root-Rechten (in /etc/sudoers.d/aether freigegeben, siehe install.sh)."""
    subprocess.run(["sudo", "-n", *cmd], capture_output=True, timeout=30)


class Systeminfo:
    """CPU, RAM, Temperatur, Luefter, Spannung, WLAN, IP, Laufzeit - fuer die Infoseite (Taste 0)."""
    def __init__(self):
        self.cpu_alt = self._cpu()
    @staticmethod
    def _cpu():
        w = [int(x) for x in open("/proc/stat").readline().split()[1:]]
        return sum(w), w[3] + w[4]
    def werte(self):
        g, l = self._cpu(); g0, l0 = self.cpu_alt; self.cpu_alt = (g, l)
        cpu = 100 * (1 - (l - l0) / max(1, g - g0))
        mem = {z.split(":")[0]: int(z.split()[1]) for z in open("/proc/meminfo") if z.split(":")[0] in ("MemTotal", "MemAvailable")}
        ram = 100 * (1 - mem["MemAvailable"] / mem["MemTotal"])
        luefter = None
        try:
            import glob
            for p in glob.glob("/sys/devices/platform/cooling_fan/hwmon/*/fan1_input"):
                luefter = int(open(p).read())
        except (OSError, ValueError):
            pass
        dbm = None
        try:
            for z in open("/proc/net/wireless").read().splitlines()[2:]:
                if z.split()[0].startswith("wlan"):
                    dbm = float(z.split()[3].rstrip("."))
        except (OSError, ValueError, IndexError):
            pass
        try:
            s_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s_.connect(("1.1.1.1", 53)); ip = s_.getsockname()[0]; s_.close()
        except OSError:
            ip = "-"
        up = float(open("/proc/uptime").read().split()[0])
        return dict(cpu=cpu, ram=ram, luefter=luefter, dbm=dbm, ip=ip, up=up)


def start_pruefung():
    """Beim Start: Netzteil-Faehigkeit (Pi 5 meldet den ausgehandelten Strom) und gehaeufte Neustarts erkennen."""
    hinweise = []
    try:   # USB-PD-Ergebnis in mA (5000 = offizielles 27-W-Netzteil, 3000 = normales USB-C, darunter zu schwach)
        ma = int.from_bytes(open("/proc/device-tree/chosen/power/max_current", "rb").read()[:4], "big")
        print(f"Netzteil meldet {ma} mA", flush=True)
        if ma < 3000:
            hinweise.append(f"Netzteil nur {ma / 1000:.1f} A".replace(".", ","))
    except (OSError, ValueError):
        pass
    try:   # Neustart-Zaehler: 3 Starts in 10 min deuten auf ein schwaches Netzteil (Pi bricht beim Hochfahren ab)
        boot = open("/proc/sys/kernel/random/boot_id").read().strip()
        pfad = os.path.expanduser("~/.aether_starts.json")
        starts = json.load(open(pfad)) if os.path.exists(pfad) else []
        if not starts or starts[-1][0] != boot:
            starts = (starts + [[boot, time.time()]])[-5:]
            json.dump(starts, open(pfad, "w"))
        juengste = [t for _, t in starts if time.time() - t < 600]
        if len(juengste) >= 3:
            hinweise.append(f"{len(juengste)} Neustarts in 10 min")
    except (OSError, ValueError):
        pass
    return hinweise


class Waechter:
    """Selbstueberwachung: WLAN-Pegel, Internet, moOde/mpd, Temperatur, Unterspannung.
    Zeigt Fehler auf dem Display und repariert stufenweise (WLAN neu -> mpd neu -> Pi neu starten)."""
    def __init__(self, oled):
        self.oled, self.wlan, self.fehler, self.temp = oled, None, None, None
        self.naechst, self.naechst_netz, self.offline_seit, self.wlan_neu = 0.0, 0.0, None, False
        self.mpd_fehler, self.mpd_neu_um = 0, None
        self.start = time.monotonic()            # Schonfrist nach dem Start: moOde/mpd braucht Zeit
        self.kein_reboot = False
        self.mpd_gesehen = False                 # erst ueberwachen, wenn moOde mpd einmal gestartet hat

    @staticmethod
    def wlan_balken():
        try:
            for z in open("/proc/net/wireless").read().splitlines()[2:]:
                teile = z.split()
                if teile and teile[0].startswith("wlan"):
                    dbm = float(teile[3].rstrip("."))
                    return 4 if dbm > -55 else 3 if dbm > -65 else 2 if dbm > -72 else 1 if dbm > -80 else 0
        except (OSError, ValueError, IndexError):
            pass
        try:
            if open("/sys/class/net/eth0/carrier").read().strip() == "1":
                return "LAN"
        except OSError:
            pass
        return 0

    @staticmethod
    def internet():
        for ziel in (("1.1.1.1", 53), ("8.8.8.8", 53)):
            try:
                socket.create_connection(ziel, timeout=3).close()
                return True
            except OSError:
                continue
        return False

    @staticmethod
    def temperatur():
        try:
            return int(open("/sys/class/thermal/thermal_zone0/temp").read()) / 1000
        except (OSError, ValueError):
            return 0

    @staticmethod
    def unterspannung():
        try:
            r = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=5)
            return bool(int(r.stdout.strip().split("=")[1], 16) & 0x1)
        except Exception:
            return False

    @staticmethod
    def spannung():
        """Pi 5: Eingangsspannung am USB-C in Volt (vcgencmd pmic_read_adc EXT5V_V), sonst None."""
        try:
            r = subprocess.run(["vcgencmd", "pmic_read_adc", "EXT5V_V"], capture_output=True, text=True, timeout=5)
            return float(r.stdout.strip().split("=")[1].rstrip("V"))
        except Exception:
            return None

    def neustart(self, grund):
        if self.kein_reboot:
            return
        try:   # Schutz vor Neustart-Schleife: schon 2 Starts in 30 min -> nicht nochmals neu starten, nur melden
            starts = json.load(open(os.path.expanduser("~/.aether_starts.json")))
            if len([t for _, t in starts if time.time() - t < 1800]) >= 2:
                print(f"KEIN Neustart ({grund}) - schon mehrere Neustarts, bitte pruefen", flush=True)
                self.kein_reboot = True
                return
        except (OSError, ValueError):
            pass
        print(f"NEUSTART: {grund}", flush=True)
        for i in range(10, 0, -1):
            self.oled.zeigen("Neustart", grund, f"in {i} s", None, self.wlan)
            time.sleep(1)
        sudo("/usr/sbin/reboot")

    def pruefen(self, jetzt):
        """Alle 5 s aufrufen. Liefert Fehlertext fuer die Statuszeile (oder None)."""
        if jetzt < self.naechst:
            return self.fehler
        self.naechst = jetzt + 5
        self.wlan = self.wlan_balken()
        meldungen = []
        # Internet (alle 30 s)
        if jetzt >= self.naechst_netz:
            self.naechst_netz = jetzt + 30
            if self.internet():
                if self.offline_seit:
                    print("Internet wieder da", flush=True)
                self.offline_seit, self.wlan_neu = None, False
            elif self.offline_seit is None:
                self.offline_seit = jetzt
        if self.offline_seit:
            weg = jetzt - self.offline_seit
            meldungen.append(f"Kein Internet {int(weg // 60)}:{int(weg % 60):02d}")
            if weg > OFFLINE_WLAN_NEU_S and not self.wlan_neu:
                print("Kein Internet - WLAN wird neu verbunden", flush=True)
                self.oled.zeigen("WLAN", "wird neu verbunden", "bitte warten", None, self.wlan)
                sudo("/usr/bin/nmcli", "radio", "wifi", "off"); time.sleep(3); sudo("/usr/bin/nmcli", "radio", "wifi", "on")
                self.wlan_neu = True
            if weg > OFFLINE_REBOOT_S:
                self.neustart("kein Internet")
        # moOde / mpd (direkt am Port 6600 fragen; erst 2 min nach dem Start)
        ok = True
        if jetzt - self.start > MPD_SCHONFRIST_S:
            try:
                with socket.create_connection(("127.0.0.1", 6600), timeout=5) as c:
                    ok = c.recv(64).startswith(b"OK MPD")
            except OSError:
                ok = False
        if ok:
            self.mpd_gesehen = True
        if not self.mpd_gesehen:                 # moOde startet mpd erst spaet (bis ca. 3-5 min nach dem Booten)
            ok = True
            if jetzt - self.start > 600:
                meldungen.append("moOde startet nicht")
        self.mpd_fehler = 0 if ok else self.mpd_fehler + 1
        if self.mpd_fehler >= MPD_FEHLER_MAX:            # nur melden - moOde startet mpd selbst neu (kein Eingriff mehr)
            meldungen.append("moOde antwortet nicht")
        # Temperatur, Netzteil
        t = self.temperatur()
        self.temp = t or None
        if t >= TEMP_WARN:
            meldungen.append(f"Pi heiss {t:.0f} C")
        u = self.spannung()
        if self.unterspannung() or (u is not None and u < 4.75):
            meldungen.append("Netzteil schwach" + (f" {u:.2f} V".replace(".", ",") if u else ""))
        elif u is not None and jetzt >= getattr(self, "naechst_u_log", 0):
            print(f"Eingangsspannung {u:.2f} V, Temperatur {t:.0f} C", flush=True); self.naechst_u_log = jetzt + 600
        neu = meldungen[0] if meldungen else None
        if neu != self.fehler:
            print(f"Status: {neu or 'alles OK'}", flush=True)
        self.fehler = neu
        return neu


class AutoPegel:
    """Senkt bei CLIP sofort um LAUT_SCHRITT (hoechstens alle 3 s), hebt langsam an,
    wenn die Spitzen 20 s lang deutlich unter der Grenze liegen und Musik laeuft."""
    def __init__(self):
        self.letzte, self.fenster_bis, self.max_rel = 0.0, time.monotonic() + 20, -99.0

    def neu(self, rel, clip, jetzt, spielt):
        if not AUTO_PEGEL or not spielt:
            self.fenster_bis, self.max_rel = jetzt + 20, -99.0
            return None
        self.max_rel = max(self.max_rel, rel)
        if clip and jetzt - self.letzte > 3:
            v = lautstaerke()
            if v is not None and v > AUTO_MIN:
                mpc("volume", str(max(AUTO_MIN, v - AUTO_RUNTER)))
                self.letzte, self.fenster_bis, self.max_rel = jetzt, jetzt + 20, -99.0
                return f"Auto: leiser {max(AUTO_MIN, v - AUTO_RUNTER)}%"
        if jetzt > self.fenster_bis:
            meldung = None
            if AUTO_STILLE < self.max_rel < AUTO_ZU_LEISE:
                v = lautstaerke()
                if v is not None and v < AUTO_MAX:
                    mpc("volume", str(min(AUTO_MAX, v + AUTO_RAUF)))
                    self.letzte, meldung = jetzt, f"Auto: lauter {min(AUTO_MAX, v + AUTO_RAUF)}%"
            self.fenster_bis, self.max_rel = jetzt + 20, -99.0
            return meldung
        return None


class Pegelmesser:
    """Ballistik wie am Kassettendeck: schnell hoch, langsam runter; Spitzenwert 1,5 s halten; CLIP 2 s halten."""
    def __init__(self):
        self.anz, self.spitze, self.spitze_bis, self.clip_bis, self.t = -99.0, -99.0, 0.0, 0.0, time.monotonic()

    def neu(self, pegel, ueber, jetzt):
        rel = pegel - CLIP_DB
        dt, self.t = jetzt - self.t, jetzt
        self.anz = rel if rel > self.anz else max(rel, self.anz - 20 * dt)       # 20 dB/s Abfall
        if rel >= self.spitze or jetzt > self.spitze_bis:
            self.spitze, self.spitze_bis = rel, jetzt + 1.5
        if ueber or rel > 0:
            self.clip_bis = jetzt + 2.0

    def werte(self, jetzt):
        return (round(self.anz), round(self.spitze), jetzt < self.clip_bis)


# ---------- Favoriten / favourites ----------
def favoriten():
    """Bis zu 5 Sender: FAVORITEN aus den Einstellungen, sonst moOde-Playlist 'Favorites'."""
    if FAVORITEN:
        return FAVORITEN[:5]
    if "Favorites" in mpc("lsplaylists").splitlines():
        return [z for z in mpc("playlist", "-f", "%file%", "Favorites").splitlines() if z][:5]
    return []


def anzeigename(eintrag):
    name = eintrag.rsplit("/", 1)[-1]
    return name[:-4] if name.endswith(".pls") else name


def lautstaerke():
    """Liest die moOde-Lautstaerke in % (None, wenn nicht regelbar)."""
    for zeile in mpc("status").splitlines():
        if zeile.startswith("volume:"):
            wert = zeile.split(":", 1)[1].split("%")[0].strip()
            return int(wert) if wert.lstrip("-").isdigit() and int(wert) >= 0 else None
    return None


# ---------- 5 Taster / 5 buttons ----------
class Tasten:
    """Start/Stop, naechster Favorit, Lautstaerke +/-, Neustart (3 s halten)."""
    def __init__(self, anzeige):
        self.anzeige = anzeige
        self.hinweis, self.hinweis_bis = None, 0.0
        self.tasten = []
        try:
            from gpiozero import Button
        except ImportError:
            print("gpiozero fehlt - weiter ohne Taster")
            return

        def taste(gpio, aktion, **kw):
            if gpio is None:
                return
            t = Button(gpio, pull_up=True, bounce_time=0.05, **kw)
            if aktion:
                t.when_pressed = aktion
            self.tasten.append(t)
            return t

        try:
            taste(T_STARTSTOP, self.start_stop)
            taste(T_WEITER, self.weiter)
            taste(T_LAUTER, lambda: self.laut(+LAUT_SCHRITT))
            taste(T_LEISER, lambda: self.laut(-LAUT_SCHRITT))
            n = taste(T_NEUSTART, None, hold_time=LANG_S)
        except Exception as e:              # z. B. lgpio fehlt: Radio laeuft trotzdem weiter
            print(f"Taster nicht verfuegbar ({e}) - weiter ohne Taster")
            self.tasten = []
            return
        if n:
            n.when_pressed = lambda: self.melden("Halten = Neustart", LANG_S)
            n.when_held = self.neustart
        for t in self.tasten:               # Lautstaerke-Tasten wiederholen beim Halten
            if t.pin.number in (T_LAUTER, T_LEISER):
                t.hold_time, t.hold_repeat = 0.5, True
                t.when_held = t.when_pressed

    def melden(self, text, sekunden=2.5):
        self.hinweis, self.hinweis_bis = text, time.monotonic() + sekunden

    def start_stop(self):
        _, _, spielt = lies_meta()
        print(f"Taste Start/Stop: {'Stop' if spielt else 'Start'}", flush=True)
        if spielt:
            ZUSTAND["nutzer_stop"] = True
            mpc("stop")
            self.melden("Stop")
        else:
            ZUSTAND["nutzer_stop"] = False
            mpc("play")
            self.melden("Start")

    def weiter(self, schritt=1):
        liste = favoriten()
        if not liste:
            self.melden("Keine Favoriten")
            return
        aktuell = mpc("-f", "%file%", "current").strip()
        i = (liste.index(aktuell) + schritt) % len(liste) if aktuell in liste else 0
        mpc("clear")
        mpc("add", liste[i])
        mpc("play")
        ZUSTAND["nutzer_stop"] = False
        self.melden(f"{i + 1}/{len(liste)} {anzeigename(liste[i])}")

    def zurueck(self):
        self.weiter(-1)

    def favorit(self, nr):
        """Direktwahl Favorit 1-5 (Zifferntasten der Fernbedienung)."""
        liste = favoriten()
        if nr > len(liste):
            self.melden(f"Kein Favorit {nr}")
            return
        mpc("clear")
        mpc("add", liste[nr - 1])
        mpc("play")
        ZUSTAND["nutzer_stop"] = False
        self.melden(f"{nr}/{len(liste)} {anzeigename(liste[nr - 1])}")

    def laut(self, schritt):
        mpc("volume", f"{schritt:+d}")
        v = lautstaerke()
        self.melden(f"Lautstaerke {v} %" if v is not None else "Lautst. fest (moOde)")

    def neustart(self):
        self.anzeige.zeigen("Neustart ...", "bitte warten", "")
        subprocess.run(["sudo", "reboot"])


# ---------- IR-Fernbedienung / IR remote ----------
AKTIONEN = ["start_stop", "weiter", "zurueck", "lauter", "leiser",
            "favorit1", "favorit2", "favorit3", "favorit4", "favorit5", "info"]
INFO = {"bis": 0.0}          # Taste 0: Systemseite fuer 10 s (nochmal druecken = zurueck)


def ir_geraet():
    """Sucht den IR-Empfaenger unter den Linux-Eingabegeraeten."""
    import evdev
    for pfad in evdev.list_devices():
        d = evdev.InputDevice(pfad)
        if IR_NAME in d.name:
            return d
    return None


class Fernbedienung:
    """Liest Scancodes vom IR-Empfaenger (Kernel-Treiber gpio-ir) und loest Aktionen aus."""
    def __init__(self, tasten):
        self.tasten = tasten
        self.belegung = {}
        try:
            with open(IR_DATEI) as f:
                self.belegung = {int(k, 16): v for k, v in json.load(f).items()}
        except (OSError, ValueError):
            print(f"Keine IR-Belegung ({IR_DATEI}) - zuerst ir_lernen.py ausfuehren")
            return
        try:
            self.dev = ir_geraet()
        except Exception as e:
            print(f"evdev fehlt ({e}) - weiter ohne Fernbedienung")
            return
        if not self.dev:
            print("IR-Empfaenger nicht gefunden (dtoverlay=gpio-ir?) - weiter ohne Fernbedienung")
            return
        print(f"Fernbedienung bereit: {len(self.belegung)} Tasten")
        threading.Thread(target=self._lauf, daemon=True).start()

    def _lauf(self):
        from evdev import ecodes
        letzte, zeit = None, 0.0
        while True:
            try:
                for ev in self.dev.read_loop():
                    if ev.type != ecodes.EV_MSC or ev.code != ecodes.MSC_SCAN:
                        continue
                    jetzt = time.monotonic()
                    aktion = self.belegung.get(ev.value)
                    if not aktion:
                        diagnose.ZAEHLER["ir_unbekannt"] += 1
                        if jetzt - getattr(self, "unbekannt_log", -99) > 60:   # hoechstens 1x pro Minute melden
                            self.unbekannt_log = jetzt
                            print(f"IR: unbekannter Code {ev.value:#x} (bisher {diagnose.ZAEHLER['ir_unbekannt']})", flush=True)
                        letzte, zeit = ev.value, jetzt
                        continue
                    wiederholt = ev.value == letzte and jetzt - zeit < 0.25
                    letzte, zeit = ev.value, jetzt
                    if wiederholt and aktion not in ("lauter", "leiser"):
                        continue                    # nur Lautstaerke wiederholt beim Halten
                    diagnose.ZAEHLER["ir_tasten"] += 1
                    print(f"IR: {ev.value:#x} -> {aktion}", flush=True)
                    self.ausfuehren(aktion)
            except OSError as e:
                print(f"IR-Fehler ({e}) - neuer Versuch in 5 s")
                time.sleep(5)
                self.dev = ir_geraet() or self.dev

    def ausfuehren(self, aktion):
        t = self.tasten
        if aktion == "info":
            INFO["bis"] = 0.0 if time.monotonic() < INFO["bis"] else time.monotonic() + 10
            return
        if aktion == "start_stop":
            t.start_stop()
        elif aktion == "weiter":
            t.weiter()
        elif aktion == "zurueck":
            t.zurueck()
        elif aktion == "lauter":
            t.laut(+LAUT_SCHRITT)
        elif aktion == "leiser":
            t.laut(-LAUT_SCHRITT)
        elif aktion.startswith("favorit"):
            t.favorit(int(aktion[-1]))


# ---------- Taster an J2 (Power-Anschluss Pi 5) ----------
class PowerTaster:
    """Kurz druecken = Radio Start/Stop. Langes Druecken (5 s) erledigt systemd-logind (Ausschalten),
    bei ausgeschaltetem Pi schaltet der Taster ihn ein (macht der Pi 5 selbst)."""
    def __init__(self, tasten):
        self.tasten = tasten
        try:
            import evdev
            self.dev = next((evdev.InputDevice(p) for p in evdev.list_devices()
                             if POWER_NAME in evdev.InputDevice(p).name), None)
        except Exception as e:
            print(f"Power-Taster nicht verfuegbar ({e})")
            return
        if not self.dev:
            print("Power-Taster (pwr_button) nicht gefunden")
            return
        print("Power-Taster bereit: kurz = Start/Stop, 5 s = Ausschalten")
        threading.Thread(target=self._lauf, daemon=True).start()

    def _lauf(self):
        from evdev import ecodes
        gedrueckt = None
        while True:
            try:
                for ev in self.dev.read_loop():
                    if ev.type != ecodes.EV_KEY or ev.code != ecodes.KEY_POWER:
                        continue
                    if ev.value == 1:
                        gedrueckt = time.monotonic()
                        diagnose.ZAEHLER["taster"] += 1
                    elif ev.value == 0 and gedrueckt is not None:
                        print(f"Taster: {time.monotonic() - gedrueckt:.2f} s gedrueckt", flush=True)
                        if time.monotonic() - gedrueckt < POWER_KURZ_S:
                            self.tasten.start_stop()
                        gedrueckt = None
            except OSError as e:
                print(f"Power-Taster-Fehler ({e}) - neuer Versuch in 5 s")
                time.sleep(5)


# ---------- Stream-Waechter / stream watchdog ----------
ZUSTAND = {"nutzer_stop": False}   # True, wenn mit der Stop-Taste angehalten


class StreamWaechter:
    """Startet den Radiostream neu, wenn er haengt (spielt, aber Stille) oder unerwartet stoppt."""
    def __init__(self):
        mpc("repeat", "on")                     # Stream-Ende -> gleicher Sender startet neu
        mpc("single", "off")
        self.stille_seit = None
        self.stop_seit = None
        self.spielte = True              # so wird auch "beim Start schon pausiert/gestoppt" erkannt
        self.letzter_neustart = -999.0

    def _neustart(self, grund, jetzt):
        print(f"Stream {grund} - starte neu")
        mpc("stop")
        time.sleep(1)
        mpc("play")
        self.letzter_neustart, self.stille_seit, self.stop_seit = jetzt, None, None

    def pruefen(self, pegel, spielt, jetzt):
        if spielt:
            ZUSTAND["nutzer_stop"] = False
            self.stop_seit = None
            if pegel > STILLE_DB:
                self.stille_seit = None
            elif self.stille_seit is None:
                self.stille_seit = jetzt
            elif jetzt - self.stille_seit >= HAENGT_S and jetzt - self.letzter_neustart >= 60:
                self._neustart(f"haengt ({HAENGT_S} s Stille)", jetzt)
        else:
            self.stille_seit = None
            if self.spielte and not ZUSTAND["nutzer_stop"] and NEUSTART_NACH_STOP:
                self.stop_seit = jetzt              # gerade eben unerwartet gestoppt
            if (self.stop_seit is not None and not ZUSTAND["nutzer_stop"]
                    and jetzt - self.stop_seit >= HAENGT_S and jetzt - self.letzter_neustart >= 60):
                self._neustart("unerwartet gestoppt", jetzt)
        self.spielte = spielt


# ---------- Stille-Abschaltung / silence switch-off ----------
class Stillschaltung:
    """Schaltet den Traeger nach STILLE_S Sekunden ohne Ton ab und bei Ton/Play sofort wieder ein.
    Switches the carrier off after STILLE_S seconds of silence, back on as soon as audio returns."""
    def __init__(self, fm):
        self.fm, self.an, self.letzter_ton = fm, True, time.monotonic()
        self.spielte = False

    def pruefen(self, pegel, spielt):
        jetzt = time.monotonic()
        if pegel > STILLE_DB:
            self.letzter_ton = jetzt
        play_gedrueckt = spielt and not self.spielte   # Pause -> Play
        self.spielte = spielt
        if not self.an and (pegel > STILLE_DB or play_gedrueckt):
            leistung_setzen(self.fm, LEISTUNG)          # wieder einschalten
            self.an, self.letzter_ton = True, jetzt
            print("Ton da - Sender EIN")
        elif self.an and jetzt - self.letzter_ton >= STILLE_S:
            leistung_setzen(self.fm, 0)                 # 0 = Traeger aus / carrier off
            self.an = False
            print(f"{STILLE_S} s Stille - Sender AUS")
        return self.an


# ---------- Sender-Chip robust ansteuern / robust chip handling ----------
class Sender:
    """Kapselt den Si4713: Neu-Initialisierung bei I2C-Fehlern, Waechter fuer Frequenz/Leistung."""
    def __init__(self):
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.reset = digitalio.DigitalInOut(board.D5)
        self.fm = None
        self.leistung = LEISTUNG
        self.rds = b"Internetradio"

    def starten(self):
        self.fm = adafruit_si4713.SI4713(self.i2c, address=ADRESSE, reset=self.reset, timeout_s=0.5)
        self.fm.tx_frequency_khz = FREQUENZ_KHZ
        leistung_setzen(self.fm, self.leistung)
        self.fm.configure_rds(0xB0B0, station=SENDERNAME.encode()[:8], rds_buffer=self.rds)
        print("Chip meldet:", self.fm.tx_frequency_khz, "kHz, Leistung", self.fm.tx_power,
              ", Antennen-C", self.fm.tx_antenna_capacitance, "pF")

    def asq(self):
        """Pegel und Uebersteuerung mit EINER Abfrage / level + overmodulation in one read."""
        self.fm._asq_status()
        status, pegel = self.fm._BUFFER[1], struct.unpack("b", bytes([self.fm._BUFFER[4]]))[0]
        return pegel, bool(status & 0x04)

    def pruefen(self, soll_an):
        """Waechter: stimmt Frequenz/Leistung noch? (z. B. nach Spannungseinbruch)"""
        f, p = self.fm.tx_frequency_khz, self.fm.tx_power
        soll_p = self.leistung if soll_an else 0
        if f != FREQUENZ_KHZ or p != soll_p:
            print(f"Waechter: Chip meldet {f} kHz / {p} - stelle neu ein")
            self.fm.tx_frequency_khz = FREQUENZ_KHZ
            leistung_setzen(self.fm, soll_p)
            self.fm.rds_buffer = self.rds
            return
        if soll_an:                                 # Antennenabstimmung pruefen (normal ca. 5-40 pF)
            c = self.fm.tx_antenna_capacitance
            if c != getattr(self, "letzte_c", None) and abs(c - getattr(self, "letzte_c", c)) >= 3:
                print(f"Waechter: Antennen-C jetzt {c} pF (vorher {self.letzte_c} pF)")
            if ANTENNE_PF == 0 and (c < 2 or c >= 47):
                print(f"Waechter: Antennen-C {c} pF unplausibel - stimme neu ab")
                leistung_setzen(self.fm, soll_p)      # loest neue automatische Abstimmung aus
                c = self.fm.tx_antenna_capacitance
                print(f"Waechter: nach Neuabstimmung {c} pF")
            self.letzte_c = c


try:
    FM_START_UPTIME = float(open("/proc/uptime").read().split()[0])
except (OSError, ValueError):
    FM_START_UPTIME = 0.0


def bootzeit_merken():
    """Wie lange hat es diesmal ab Einschalten gedauert? Gleitender Mittelwert in ~/.aether_bootzeit."""
    pfad = "/home/oliver/.aether_bootzeit"
    try:
        t = float(open("/proc/uptime").read().split()[0])
        if t > 900 or FM_START_UPTIME > 120:            # fm.py wurde spaeter (von Hand) gestartet - nicht mitzaehlen
            return
        try:
            t = 0.5 * float(open(pfad).read()) + 0.5 * t
        except (OSError, ValueError):
            pass
        open(pfad, "w").write(f"{t:.0f}\n")
        print(f"Startdauer gemerkt: {t:.0f} s", flush=True)
    except OSError:
        pass


def main():
    try:                                    # Startanzeige (aether-boot.service) beenden, dann selbst zeichnen
        open("/dev/shm/aether_fm", "w").close()
        time.sleep(0.4)
    except OSError:
        pass
    oled = Anzeige(OLED_ADRESSE)
    bed = Tasten(oled)               # Referenz halten, sonst raeumt gpiozero auf
    fb = Fernbedienung(bed)          # IR-Fernbedienung (laeuft im Hintergrund)
    diagnose.starten(fb)             # http://webradio.local:8080
    pt = PowerTaster(bed)            # Taster an J2: kurz = Start/Stop
    freq = f"FM {FREQUENZ_KHZ / 1000:.1f}"
    oled.start("Sender startet")
    tx, versuch, bereit = Sender(), 0, False
    while not bereit:                # FM-Modul fehlt/antwortet nicht: warten statt abstuerzen (sonst Neustart-Schleife)
        try:
            tx.starten(); bereit = True
        except Exception as e:
            versuch += 1
            print(f"FM-Modul nicht gefunden ({e}) - Versuch {versuch}, neuer Versuch in 10 s", flush=True)
            oled.zeigen("FM-Modul fehlt", f"I2C 0x{ADRESSE:02X} Kabel pruefen", f"Versuch {versuch}")
            if versuch == 1:
                sd_notify("READY=1")
            sd_notify("WATCHDOG=1")
            time.sleep(10)

    stille = Stillschaltung(tx.fm)
    strom = StreamWaechter()
    letzter_titel, naechste_messung, naechster_waechter, naechstes_log = None, 0.0, 30.0, 0.0
    naechste_meta, meta = 0.0, (None, "", False)
    pegel, ueber, sendet, fehler = -99, False, True, 0
    vu, naechster_pegel, ueber_2s = Pegelmesser(), 0.0, False
    auto = AutoPegel()
    waechter = Waechter(oled)
    sysinfo, naechste_info = Systeminfo(), 0.0
    for h in start_pruefung():                          # Netzteil-Hinweise 8 s gross anzeigen
        print("Hinweis:", h, flush=True)
        oled.zeigen("Netzteil pruefen", h, "27-W-Netzteil Pi 5", None, None)
        time.sleep(8)
    sd_notify("READY=1")
    naechster_hund = 0.0
    naechste_phase, start_text, bootzeit_gemerkt = 0.0, "moOde l\u00e4dt", False
    leer_seit, auto_gestartet = None, False
    while True:
        jetzt = time.monotonic()
        if jetzt >= naechster_hund:                     # systemd-Watchdog fuettern (haengt fm.py, startet systemd neu)
            sd_notify("WATCHDOG=1"); naechster_hund = jetzt + 10
        problem = waechter.pruefen(jetzt)
        if jetzt >= naechste_meta:                      # moOde-Datei 1x pro Sekunde lesen
            meta, naechste_meta = lies_meta(), jetzt + 1
        sender, titel, spielt = meta
        try:
            if jetzt >= naechster_pegel:                # Pegel fuer die Anzeige (alle METER_S)
                pegel, u = tx.asq()
                vu.neu(pegel, u, jetzt)
                ueber_2s = ueber_2s or u
                m = auto.neu(pegel - CLIP_DB, u or pegel > CLIP_DB, jetzt, sendet and spielt)
                if m:
                    print(m, flush=True)
                    bed.melden(m)
                naechster_pegel = jetzt + METER_S
            if jetzt >= naechste_messung:               # Logik alle 2 s
                ueber, ueber_2s = ueber_2s, False
                sendet = stille.pruefen(pegel, spielt)
                if sender is not None:
                    strom.pruefen(pegel, spielt, jetzt)
                naechste_messung = jetzt + 2
                if ueber or jetzt >= naechstes_log:     # Log nur alle 60 s oder bei Warnung (schont SD-Karte)
                    print(f"Pegel: {pegel:4d} dB" + ("  <-- UEBERSTEUERT, leiser stellen!" if ueber else ""))
                    naechstes_log = jetzt + 60
            if "antenne" in diagnose.WUNSCH:            # Antennen-C testen / speichern (Diagnose-Seite)
                pf, speichern = diagnose.WUNSCH.pop("antenne")
                globals()["ANTENNE_PF"] = pf
                if speichern:
                    try:
                        open(ANTENNE_DATEI, "w").write(f"{pf}\n")
                    except OSError:
                        pass
                if sendet:
                    leistung_setzen(tx.fm, tx.leistung)
                print(f"Antennen-C jetzt {'automatisch' if pf == 0 else str(pf) + ' pF'}"
                      f"{' (gespeichert)' if speichern else ''} - Chip meldet {tx.fm.tx_antenna_capacitance} pF", flush=True)
            if "leistung" in diagnose.WUNSCH:           # von der Diagnose-Seite (Test)
                tx.leistung = diagnose.WUNSCH.pop("leistung")
                globals()["LEISTUNG"] = tx.leistung     # auch fuer das Wiedereinschalten nach Stille
                if sendet:
                    leistung_setzen(tx.fm, tx.leistung)
                print(f"Leistung jetzt {tx.leistung} dBuV (Chip: {tx.fm.tx_power}, Antennen-C {tx.fm.tx_antenna_capacitance} pF)", flush=True)
            if jetzt >= naechster_waechter:             # alle 30 s Frequenz/Leistung kontrollieren
                tx.pruefen(sendet)
                naechster_waechter = jetzt + 30
            if sender is not None:
                rds = titel or sender
                if rds != letzter_titel:
                    tx.rds = ascii_text(rds).encode("ascii")[:64]
                    tx.fm.rds_buffer = tx.rds
                    letzter_titel = rds
            fehler = 0
        except (OSError, RuntimeError) as e:            # I2C-Stoerung
            fehler += 1
            diagnose.ZAEHLER["i2c_fehler"] += 1
            if fehler <= 2:                             # einzelne Aussetzer: einfach nochmals lesen, Sender laeuft weiter
                print(f"I2C-Aussetzer ({e}) - {fehler}. Mal, lese erneut", flush=True)
                time.sleep(0.3)
                continue
            print(f"I2C-Fehler ({e}) - Versuch {fehler}: Chip wird neu gestartet")
            oled.zeigen("Sender-Stoerung", "wird neu gestartet", f"Versuch {fehler - 2}")
            if fehler >= 7:
                raise                                   # systemd startet das ganze Script neu
            time.sleep(2)
            try:
                tx.starten()
                stille.fm = tx.fm
                letzter_titel = None
            except Exception as e2:
                print("Neustart fehlgeschlagen:", e2)
            continue

        if sender is None:                              # moOde noch nicht bereit: Countdown wie beim Booten
            if jetzt >= naechste_phase:
                import boot_anzeige
                start_text, naechste_phase = problem or boot_anzeige.phase(), jetzt + 1.0
            oled.start(start_text)
            if start_text == "Radio startet":           # mpd laeuft, aber kein Sender geladen
                leer_seit = leer_seit or jetzt
                if not auto_gestartet and jetzt - leer_seit > 20:
                    auto_gestartet = True               # Plug & Play: selbst einen Sender starten
                    if mpc("playlist").strip():
                        print("Autostart: Wiedergabe starten", flush=True); mpc("play")
                    elif favoriten():
                        print("Autostart: Favorit 1 laden", flush=True); bed.favorit(1)
                    else:
                        print("Autostart: keine Sender gefunden - in moOde einen Sender waehlen", flush=True)
                        start_text = "Sender in moOde waehlen"
            time.sleep(0.2)
            continue
        if not bootzeit_gemerkt:                        # Startdauer lernen (fuer den Countdown beim naechsten Mal)
            bootzeit_gemerkt = True
            bootzeit_merken()
        if problem:
            status = problem
        elif not sendet:
            status = f"{freq} Stille"
        elif not spielt:
            status = f"{freq}  Pause"
        elif ueber:
            status = f"{freq}  leiser stellen!"
        else:
            status = f"{freq} {pegel}dB"
        if jetzt < INFO["bis"]:                          # Systemseite (Taste 0)
            if jetzt >= naechste_info:
                oled.infoseite(sysinfo.werte(), waechter.temp, waechter.spannung()); naechste_info = jetzt + 1
            time.sleep(0.1)
            continue
        oben = bed.hinweis if bed.hinweis and jetzt < bed.hinweis_bis else sender
        diagnose.STATUS.update(sender=sender, titel=titel, status=status, pegel_db=pegel, sendet=sendet, spielt=spielt,
                               antenne_pf=getattr(tx, "letzte_c", None), temp=waechter.temp, wlan=waechter.wlan,
                               leistung=tx.leistung, problem=problem)
        oled.zeigen(oben, titel, status, vu.werte(jetzt) if (sendet and spielt) else None, waechter.wlan, waechter.temp)
        time.sleep(0.1)

if __name__ == "__main__":
    main()
