#!/usr/bin/env python3
"""Generate basic translation files for Chocoloco app"""

import os
from pathlib import Path

TRANSLATIONS = {
    'Chocoloco': {'de': 'Chocoloco', 'en': 'Chocoloco', 'fr': 'Chocoloco'},
    'Dashboard': {'de': 'Dashboard', 'en': 'Dashboard', 'fr': 'Tableau de bord'},
    'Producten': {'de': 'Produkte', 'en': 'Products', 'fr': 'Produits'},
    'Shop': {'de': 'Shop', 'en': 'Shop', 'fr': 'Boutique'},
    'Instellingen': {'de': 'Einstellungen', 'en': 'Settings', 'fr': 'Paramètres'},
    'Uitloggen': {'de': 'Abmelden', 'en': 'Logout', 'fr': 'Déconnexion'},
    'Accountgegevens': {'de': 'Kontodaten', 'en': 'Account Information', 'fr': 'Informations du compte'},
    'Gebruikersnaam': {'de': 'Benutzername', 'en': 'Username', 'fr': 'Nom d\'utilisateur'},
    'E-mailadres': {'de': 'E-Mail-Adresse', 'en': 'Email Address', 'fr': 'Adresse e-mail'},
    'Lid sinds': {'de': 'Mitglied seit', 'en': 'Member Since', 'fr': 'Membre depuis'},
    'Voorkeuren': {'de': 'Präferenzen', 'en': 'Preferences', 'fr': 'Préférences'},
    'Taal': {'de': 'Sprache', 'en': 'Language', 'fr': 'Langue'},
    'Nederlands': {'de': 'Niederländisch', 'en': 'Dutch', 'fr': 'Néerlandais'},
    'Deutsch': {'de': 'Deutsch', 'en': 'German', 'fr': 'Allemand'},
    'English': {'de': 'Englisch', 'en': 'English', 'fr': 'Anglais'},
    'Français': {'de': 'Französisch', 'en': 'French', 'fr': 'Français'},
    'Thema': {'de': 'Design', 'en': 'Theme', 'fr': 'Thème'},
    'Licht': {'de': 'Hell', 'en': 'Light', 'fr': 'Clair'},
    'Donker': {'de': 'Dunkel', 'en': 'Dark', 'fr': 'Sombre'},
}

PO_HEADER = '''# Chocoloco Translations
# Copyright (C) 2024
msgid ""
msgstr ""
"Project-Id-Version: Chocoloco 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Language: {lang}\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"

'''

base_dir = Path('/c/Users/trist/Copilot/Vibe_coding_Chocoloco_2/app/translations')

for lang in ['nl', 'de', 'en', 'fr']:
    po_path = base_dir / lang / 'LC_MESSAGES' / 'messages.po'
    mo_path = base_dir / lang / 'LC_MESSAGES' / 'messages.mo'

    content = PO_HEADER.format(lang=lang)

    for nl_text, translations in TRANSLATIONS.items():
        translated = translations.get(lang, nl_text)
        content += f'msgid "{nl_text}"\nmsgstr "{translated}"\n\n'

    po_path.write_text(content, encoding='utf-8')
    print(f"✓ Created {po_path}")

print("\n✓ All PO files created successfully")
print("✓ Now compile them with: pybabel compile -d app/translations")
