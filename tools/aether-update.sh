#!/bin/zsh
# Mac helper: copies the newest AETHER_software_update*.zip from ~/Downloads to the Pi,
# installs it and reboots. Set PI to your user@host.
PI=${PI:-$USER@webradio.local}
cd ~/Downloads || exit 1
f=$(ls -t AETHER_software_update*.zip 2>/dev/null | head -1)
[ -z "$f" ] && { echo "No AETHER_software_update.zip in Downloads"; exit 1; }
echo "Installing: $f"
scp "$f" "$PI":AETHER_software_update.zip && \
ssh "$PI" 'sudo systemctl stop fm; unzip -o AETHER_software_update.zip -d aether && cd aether && bash install.sh && sudo systemctl enable fm && sudo reboot'
