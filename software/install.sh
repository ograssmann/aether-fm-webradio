#!/bin/bash
# Installation auf dem Raspberry Pi (moOde) / installation on the Pi.  V7
# Aufruf/usage: im Ordner software:  bash install.sh
set -e
CFG=/boot/firmware/config.txt
sudo raspi-config nonint do_i2c 0
# I2C langsamer = stoerfester gegen HF / slower I2C = more robust against RF
I2C_HZ=50000    # V7e: 50 kHz = robuster gegen HF vom Sender; bei I2C-Fehlern im Log hier 50000 eintragen und install.sh erneut ausfuehren
if grep -q "i2c_arm_baudrate" $CFG; then sudo sed -i "s/i2c_arm_baudrate=[0-9]*/i2c_arm_baudrate=$I2C_HZ/" $CFG
else echo "dtparam=i2c_arm_baudrate=$I2C_HZ" | sudo tee -a $CFG; fi
# Active Cooler am FAN-Anschluss: temperaturgesteuert (PWM), Kurve hier anpassbar (Temperatur in m°C, Drehzahl 0-255)
if ! grep -q "fan_temp0" $CFG; then
  printf "dtparam=fan_temp0=50000,fan_temp0_hyst=5000,fan_temp0_speed=60\ndtparam=fan_temp1=60000,fan_temp1_hyst=5000,fan_temp1_speed=120\ndtparam=fan_temp2=67500,fan_temp2_hyst=5000,fan_temp2_speed=180\ndtparam=fan_temp3=75000,fan_temp3_hyst=5000,fan_temp3_speed=255\n" | sudo tee -a $CFG
fi
# V7: OLED auf eigenem I2C-Bus 3 (SDA GPIO 22 = Pin 15, SCL GPIO 27 = Pin 13) - keine Y-Kabel noetig
grep -q "i2c-gpio,bus=3" $CFG || echo "dtoverlay=i2c-gpio,bus=3,i2c_gpio_sda=22,i2c_gpio_scl=27,i2c_gpio_delay_us=2" | sudo tee -a $CFG
# V7: 3,3 V fuer den IR-Empfaenger aus GPIO 24 (Pin 18, ab dem Start auf HIGH) - beide 3,3-V-Pins sind belegt
grep -q "^gpio=24=op,dh" $CFG || echo "gpio=24=op,dh" | sudo tee -a $CFG
# IR-Empfaenger an GPIO 23 (Pin 16) / IR receiver on GPIO 23
grep -q "dtoverlay=gpio-ir" $CFG || echo "dtoverlay=gpio-ir,gpio_pin=23" | sudo tee -a $CFG
# Taster an J2 (Power-Anschluss Pi 5): kurz = Start/Stop (macht fm.py), 5 s halten = ausschalten; aus -> kurz = einschalten
sudo mkdir -p /etc/systemd/logind.conf.d
printf "[Login]\nHandlePowerKey=ignore\nHandlePowerKeyLongPress=poweroff\n" | sudo tee /etc/systemd/logind.conf.d/taster.conf
sudo apt update
sudo apt install -y i2c-tools python3-venv python3-dev build-essential python3-lgpio \
                    fonts-dejavu-core ir-keytable python3-evdev
sudo usermod -aG input,gpio,i2c "$USER"
[ -d ~/fm-env ] || python3 -m venv --system-site-packages ~/fm-env
~/fm-env/bin/pip install --upgrade pip
~/fm-env/bin/pip install adafruit-blinka adafruit-circuitpython-si4713 luma.oled smbus2 gpiozero evdev
cp fm.py ir_lernen.py boot_anzeige.py diagnose.py ~/
[ -f ~/ir_tasten.json ] || cp ir_tasten.json ~/   # Standard-Codes der 17-Tasten-Fernbedienung (NEC)
sed "s/User=oliver/User=$USER/; s#/home/oliver#$HOME#g" fm.service | sudo tee /etc/systemd/system/fm.service > /dev/null
sed -i "s#/home/oliver#$HOME#g" ~/fm.py ~/ir_lernen.py ~/boot_anzeige.py
# V7e: Startanzeige mit Countdown, laeuft ganz frueh beim Booten
sed "s#/home/oliver#$HOME#g" aether-boot.service | sudo tee /etc/systemd/system/aether-boot.service > /dev/null
# V7: Selbstueberwachung - fm.py darf ohne Passwort WLAN, mpd und den Pi neu starten
printf "%s ALL=(root) NOPASSWD: /usr/sbin/reboot, /usr/bin/nmcli, /usr/bin/systemctl restart mpd\n" "$USER" | sudo tee /etc/sudoers.d/aether > /dev/null
sudo chmod 440 /etc/sudoers.d/aether && sudo visudo -cf /etc/sudoers.d/aether
# V7: Hardware-Watchdog - haengt das ganze System, startet der Pi nach 15 s von selbst neu
sudo mkdir -p /etc/systemd/system.conf.d
printf "[Manager]\nRuntimeWatchdogSec=15\nRebootWatchdogSec=2min\n" | sudo tee /etc/systemd/system.conf.d/watchdog.conf > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable fm aether-boot
echo
echo "Fertig. Jetzt:  sudo reboot"
echo "Nach dem Neustart Fernbedienung anlernen:"
echo "  sudo systemctl stop fm; ~/fm-env/bin/python ~/ir_lernen.py; sudo systemctl start fm"
