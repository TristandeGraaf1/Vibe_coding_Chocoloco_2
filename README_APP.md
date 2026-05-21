# Chocoloco MVP - Flask Application

Een Flask-gebaseerde applicatie voor het beheren van chocoladeproducten met een dashboard, productregistratie, favorieten en dark mode.

## Features in deze MVP

✅ **Gebruikersauthenticatie** - Registratie en inloggen
✅ **Dashboard** - Overzicht van alle geregistreerde producten
✅ **Product Management** - Producten toevoegen, bekijken en verwijderen
✅ **Favorieten** - Producten als favoriet markeren
✅ **Vervaldatum Waarschuwingen** - Meldingen voor producten die bijna verlopen
✅ **Dark Mode** - Lichte en donkere thema's
✅ **Responsive Design** - Werkt op desktop en mobiel

## Setup

### 1. Dependencies installeren
```bash
pip install -r requirements.txt
```

### 2. Database initialiseren
De database wordt automatisch aangemaakt bij de eerste run.

### 3. Applicatie starten
```bash
python run.py
```

De app is beschikbaar op: **http://localhost:5000**

## Standaard Gebruiker
Je kunt je registreren via het registratieformulier.

## Projectstructuur
```
.
├── app/
│   ├── __init__.py          # Flask app initialization
│   ├── models.py            # Database modellen
│   ├── forms.py             # Flask forms
│   ├── routes.py            # Routes/endpoints
│   ├── templates/           # HTML templates
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── auth/
│   │   └── product/
│   └── static/
│       └── style.css        # Styling met dark mode
├── config.py                # Configuratie
├── run.py                   # Entry point
└── requirements.txt         # Dependencies
```

## Odoo orderkoppeling

Zorg dat deze environment-variabelen gezet zijn zodat geslaagde checkout-orders automatisch in Odoo worden aangemaakt:

- `ODOO_URL`
- `ODOO_DB`
- `ODOO_USERNAME`
- `ODOO_PASSWORD`

De app gebruikt XML-RPC om een klant te vinden of aan te maken, een verkooporder te maken en de order te bevestigen.

### Render deployment

Op Render moet je deze variabelen handmatig invullen in je web service, of de service vanaf `render.yaml` aanmaken en daarna de env vars invullen:

- `ODOO_URL = https://edu-chocoloco2.odoo.com/`
- `ODOO_DB = edu-chocoloco2`
- `ODOO_USERNAME = tristan31tx@hotmail.com`
- `ODOO_PASSWORD = <jouw wachtwoord>`

Belangrijk: je lokale `.env` wordt op Render niet automatisch meegepakt. Zonder deze variabelen krijg je precies de fout dat de Odoo-config ontbreekt.

## Volgende Stappen (voor volle app)

- [ ] QR-code scanning
- [ ] AI Chatbot
- [ ] Product bestellingen
- [ ] Gepersonaliseerde aanbevelingen
- [ ] Product notificaties
- [ ] Workshop/event herinneringen
- [ ] Klachtenformulier
