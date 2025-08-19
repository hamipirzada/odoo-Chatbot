#!/bin/bash
cd /home/mudasir/Desktop/odoo-17-ent
pkill -f "odoo-bin"
sleep 3
python3.10 odoo-bin -c .odoorc_kpak -d kpak_july_25 -u ai_analytics &
echo "Odoo restarted with ai_analytics module update"