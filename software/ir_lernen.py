#!/usr/bin/env python3
"""ir_lernen.py - bringt fm.py die Tasten deiner IR-Fernbedienung bei.
Teaches fm.py the buttons of your IR remote.

Aufruf / usage:   sudo systemctl stop fm
                  ~/fm-env/bin/python ~/ir_lernen.py
                  sudo systemctl start fm
Fuer jede Funktion die gewuenschte Taste druecken; Enter (ohne Druck) = Funktion ueberspringen.
"""
import json
import select
import sys
import time

import evdev
from evdev import ecodes

IR_NAME = "gpio_ir_recv"
IR_DATEI = "/home/oliver/ir_tasten.json"
FUNKTIONEN = [
    ("start_stop", "Start/Stop"),
    ("weiter", "Naechster Sender"),
    ("zurueck", "Vorheriger Sender"),
    ("lauter", "Lauter"),
    ("leiser", "Leiser"),
    ("favorit1", "Favorit 1 (z. B. Taste 1)"),
    ("favorit2", "Favorit 2"),
    ("favorit3", "Favorit 3"),
    ("favorit4", "Favorit 4"),
    ("favorit5", "Favorit 5"),
    ("info", "Systeminfo (z. B. Taste 0)"),
]


def geraet():
    for pfad in evdev.list_devices():
        d = evdev.InputDevice(pfad)
        if IR_NAME in d.name:
            return d
    sys.exit("IR-Empfaenger nicht gefunden. Steht 'dtoverlay=gpio-ir,gpio_pin=23' in "
             "/boot/firmware/config.txt und wurde neu gestartet?")


def warte_auf_taste(dev):
    """Liefert den Scancode der naechsten Taste, oder None bei Enter."""
    while True:
        r, _, _ = select.select([dev.fd, sys.stdin], [], [])
        if sys.stdin in r:
            sys.stdin.readline()
            return None
        for ev in dev.read():
            if ev.type == ecodes.EV_MSC and ev.code == ecodes.MSC_SCAN:
                code = ev.value
                time.sleep(0.4)                 # Wiederholungen der gleichen Taste abwarten
                while select.select([dev.fd], [], [], 0)[0]:
                    list(dev.read())
                return code


def main():
    dev = geraet()
    print(f"Empfaenger: {dev.name}  ({dev.path})")
    try:                                        # bestehende Belegung behalten: Enter = Taste bleibt wie bisher
        belegung = json.load(open(IR_DATEI))
    except (OSError, ValueError):
        belegung = {}
    for schluessel, text in FUNKTIONEN:
        print(f"\n> Taste fuer  {text}  druecken (Enter = ueberspringen) ... ", end="", flush=True)
        code = warte_auf_taste(dev)
        if code is None:
            print("bleibt wie bisher")
            continue
        belegung = {k: v for k, v in belegung.items() if v != schluessel}   # alten Code dieser Funktion entfernen
        if f"{code:#x}" in belegung:
            print(f"0x{code:x} ist schon belegt mit {belegung[f'{code:#x}']} - ueberschrieben")
        belegung[f"{code:#x}"] = schluessel
        print(f"0x{code:x}")
    with open(IR_DATEI, "w") as f:
        json.dump(belegung, f, indent=2)
    print(f"\nGespeichert: {IR_DATEI} ({len(belegung)} Tasten). Jetzt: sudo systemctl start fm")


if __name__ == "__main__":
    main()
