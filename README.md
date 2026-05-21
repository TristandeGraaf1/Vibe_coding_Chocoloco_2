# Vibe_coding_Chocoloco_2
Goede versie
# versie


## Run lokaal

Deze applicatie start met `run.py`. Gebruik niet `app.py` (bestaat niet).

PowerShell (aanbevolen):

```powershell
# activeer virtuele omgeving (in projectroot)
.venv\Scripts\Activate.ps1

# installeer requirements (eerste keer)
pip install -r requirements.txt

# start de app
python run.py

# test Odoo-verbinding
python scripts/test_odoo_connection.py
```

Windows CMD:

```cmd
.venv\Scripts\activate.bat
pip install -r requirements.txt
python run.py
python scripts\test_odoo_connection.py
```

Veelvoorkomende fout: `can't open file ... app.py` betekent dat je per ongeluk `python app.py` gebruikt — gebruik `python run.py`.

