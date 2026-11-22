#!/usr/bin/env python3
"""AETHER 102.3 - Startanzeige mit Countdown.
Laeuft sehr frueh beim Booten (aether-boot.service), bis fm.py das Display uebernimmt.
Die Restzeit wird aus den letzten Starts gelernt (~/.aether_bootzeit)."""
import os
import socket
import time

OLED_BUS, OLED_ADRESSE = 3, 0x3C
UEBERGABE = "/dev/shm/aether_fm"                 # legt fm.py an, sobald es das Display uebernimmt
BOOTZEIT = "/home/oliver/.aether_bootzeit"       # Sekunden ab Einschalten bis das Radio spielt (gelernt)
STANDARD_S = 200                                 # Schaetzung, solange noch nichts gelernt ist
TITEL = "ÆTHER 102.3"


def uptime():
    try:
        return float(open("/proc/uptime").read().split()[0])
    except (OSError, ValueError):
        return 0.0


def geschaetzt():
    try:
        return max(30.0, float(open(BOOTZEIT).read().strip()))
    except (OSError, ValueError):
        return float(STANDARD_S)


def netz_da():
    try:
        return any(z.split()[1] == "00000000" for z in open("/proc/net/route").read().splitlines()[1:])
    except (OSError, IndexError):
        return False


def mpd_da():
    try:
        with socket.create_connection(("127.0.0.1", 6600), timeout=0.3) as c:
            return c.recv(16).startswith(b"OK MPD")
    except OSError:
        return False


def phase():
    if not netz_da():
        return "WLAN verbindet"
    if not mpd_da():
        return "moOde lädt"
    return "Radio startet"


def schriften():
    from PIL import ImageFont
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans"
    try:
        return (ImageFont.truetype(p + "-Bold.ttf", 14), ImageFont.truetype(p + ".ttf", 10),
                ImageFont.truetype(p + "-Bold.ttf", 22))
    except OSError:
        f = ImageFont.load_default()
        return f, f, f


def zeichne_start(d, fonts, text, t=None, gesamt=None):
    """Startbild: Titel, Phase, grosser Countdown, Fortschrittsbalken. Auch von fm.py genutzt."""
    gross, klein, riesig = fonts
    t = uptime() if t is None else t
    gesamt = geschaetzt() if gesamt is None else gesamt
    rest = gesamt - t
    d.text((0, -2), TITEL, font=gross, fill="white")
    d.text((0, 15), text, font=klein, fill="white")
    if rest > 0:
        z = f"{int(rest // 60)}:{int(rest % 60):02d}"
    else:                                         # laenger als sonst: kein negativer Countdown, nur Punkte
        z = "gleich" + "." * (int(t * 2) % 4)
    w = d.textlength(z, font=riesig)
    d.text(((128 - w) / 2, 26), z, font=riesig, fill="white")
    anteil = min(1.0, t / gesamt)
    d.rectangle((0, 56, 127, 63), outline="white")
    if rest > 0:
        d.rectangle((2, 58, 2 + int(123 * anteil), 61), fill="white")
    else:                                         # Lauflicht, solange es laenger dauert
        x = int(t * 40) % 110
        d.rectangle((2 + x, 58, 2 + x + 13, 61), fill="white")


def main():
    for _ in range(100):                          # auf den I2C-Bus 3 warten (Overlay wird frueh geladen)
        if os.path.exists(f"/dev/i2c-{OLED_BUS}"):
            break
        time.sleep(0.2)
    try:
        os.remove(UEBERGABE)                      # Rest vom letzten Lauf (liegt im RAM, eigentlich leer)
    except OSError:
        pass
    from luma.core.interface.serial import i2c
    from luma.core.render import canvas
    from luma.oled.device import sh1106
    dev = sh1106(i2c(port=OLED_BUS, address=OLED_ADRESSE), width=128, height=64)
    dev.persist = True                            # Bild beim Beenden nicht loeschen (fm.py zeichnet nahtlos weiter)
    fonts = schriften()
    text, naechste_phase = "System startet", 0.0
    while not os.path.exists(UEBERGABE):
        jetzt = time.monotonic()
        if jetzt >= naechste_phase:
            text, naechste_phase = phase(), jetzt + 1.0
        with canvas(dev) as d:
            zeichne_start(d, fonts, text)
        time.sleep(0.2)


if __name__ == "__main__":
    main()
