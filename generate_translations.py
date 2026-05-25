#!/usr/bin/env python
# Quick translation generator script

import os
import json
from datetime import datetime

# Translation dictionary with key strings
TRANSLATIONS = {
    'nl': {
        'Chocoloco': 'Chocoloco',
        'Dashboard': 'Dashboard',
        'Producten': 'Producten',
        'Shop': 'Shop',
        'Instellingen': 'Instellingen',
        'Uitloggen': 'Uitloggen',
        'Accountgegevens': 'Accountgegevens',
        'Gebruikersnaam': 'Gebruikersnaam',
        'E-mailadres': 'E-mailadres',
        'Lid sinds': 'Lid sinds',
        'Voorkeuren': 'Voorkeuren',
        'Taal': 'Taal',
        'Nederlands': 'Nederlands',
        'Deutsch': 'Deutsch',
        'English': 'English',
        'Français': 'Français',
        'Thema': 'Thema',
        'Licht': 'Licht',
        'Donker': 'Donker',
    },
    'de': {
        'Chocoloco': 'Chocoloco',
        'Dashboard': 'Dashboard',
        'Producten': 'Produkte',
        'Shop': 'Shop',
        'Instellingen': 'Einstellungen',
        'Uitloggen': 'Abmelden',
        'Accountgegevens': 'Kontodaten',
        'Gebruikersnaam': 'Benutzername',
        'E-mailadres': 'E-Mail-Adresse',
        'Lid sinds': 'Mitglied seit',
        'Voorkeuren': 'Präferenzen',
        'Taal': 'Sprache',
        'Nederlands': 'Niederländisch',
        'Deutsch': 'Deutsch',
        'English': 'Englisch',
        'Français': 'Französisch',
        'Thema': 'Design',
        'Licht': 'Hell',
        'Donker': 'Dunkel',
    },
    'en': {
        'Chocoloco': 'Chocoloco',
        'Dashboard': 'Dashboard',
        'Producten': 'Products',
        'Shop': 'Shop',
        'Instellingen': 'Settings',
        'Uitloggen': 'Logout',
        'Accountgegevens': 'Account Information',
        'Gebruikersnaam': 'Username',
        'E-mailadres': 'Email Address',
        'Lid sinds': 'Member Since',
        'Voorkeuren': 'Preferences',
        'Taal': 'Language',
        'Nederlands': 'Dutch',
        'Deutsch': 'German',
        'English': 'English',
        'Français': 'French',
        'Thema': 'Theme',
        'Licht': 'Light',
        'Donker': 'Dark',
    },
    'fr': {
        'Chocoloco': 'Chocoloco',
        'Dashboard': 'Tableau de bord',
        'Producten': 'Produits',
        'Shop': 'Boutique',
        'Instellingen': 'Paramètres',
        'Uitloggen': 'Déconnexion',
        'Accountgegevens': 'Informations du compte',
        'Gebruikersnaam': 'Nom d\'utilisateur',
        'E-mailadres': 'Adresse e-mail',
        'Lid sinds': 'Membre depuis',
        'Voorkeuren': 'Préférences',
        'Taal': 'Langue',
        'Nederlands': 'Néerlandais',
        'Deutsch': 'Allemand',
        'English': 'Anglais',
        'Français': 'Français',
        'Thema': 'Thème',
        'Licht': 'Clair',
        'Donker': 'Sombre',
    }
}

print("✓ Translation dictionary loaded with basic strings")
print(f"  Supported languages: {', '.join(TRANSLATIONS.keys())}")
print(f"  Strings per language: {len(TRANSLATIONS['nl'])}")
