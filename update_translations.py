#!/usr/bin/env python3
"""
Comprehensive translations for Chocoloco app
"""
import os
from pathlib import Path

TRANSLATIONS = {
    # Navigation & Common
    'Chocoloco': {'de': 'Chocoloco', 'en': 'Chocoloco', 'fr': 'Chocoloco'},
    'Dashboard': {'de': 'Dashboard', 'en': 'Dashboard', 'fr': 'Tableau de bord'},
    'Producten': {'de': 'Produkte', 'en': 'Products', 'fr': 'Produits'},
    'Shop': {'de': 'Shop', 'en': 'Shop', 'fr': 'Boutique'},
    'Meldingen': {'de': 'Benachrichtigungen', 'en': 'Notifications', 'fr': 'Notifications'},
    'Instellingen': {'de': 'Einstellungen', 'en': 'Settings', 'fr': 'Paramètres'},
    'Uitloggen': {'de': 'Abmelden', 'en': 'Logout', 'fr': 'Déconnexion'},

    # Account Settings
    'Accountgegevens': {'de': 'Kontodaten', 'en': 'Account Information', 'fr': 'Informations du compte'},
    'Gebruikersnaam': {'de': 'Benutzername', 'en': 'Username', 'fr': 'Nom d\'utilisateur'},
    'E-mailadres': {'de': 'E-Mail-Adresse', 'en': 'Email Address', 'fr': 'Adresse e-mail'},
    'Lid sinds': {'de': 'Mitglied seit', 'en': 'Member Since', 'fr': 'Membre depuis'},

    # Preferences
    'Voorkeuren': {'de': 'Präferenzen', 'en': 'Preferences', 'fr': 'Préférences'},
    'Taal': {'de': 'Sprache', 'en': 'Language', 'fr': 'Langue'},
    'Nederlands': {'de': 'Niederländisch', 'en': 'Dutch', 'fr': 'Néerlandais'},
    'Deutsch': {'de': 'Deutsch', 'en': 'German', 'fr': 'Allemand'},
    'English': {'de': 'Englisch', 'en': 'English', 'fr': 'Anglais'},
    'Francais': {'de': 'Französisch', 'en': 'French', 'fr': 'Français'},
    'Thema': {'de': 'Design', 'en': 'Theme', 'fr': 'Thème'},
    'Licht': {'de': 'Hell', 'en': 'Light', 'fr': 'Clair'},
    'Donker': {'de': 'Dunkel', 'en': 'Dark', 'fr': 'Sombre'},

    # Accessibility
    'Toegankelijkheid': {'de': 'Barrierefreiheit', 'en': 'Accessibility', 'fr': 'Accessibilité'},
    'Schermlezer inschakelen': {'de': 'Bildschirmleser aktivieren', 'en': 'Enable Screen Reader', 'fr': 'Activer le lecteur d\'écran'},
    'Lettergrootte': {'de': 'Schriftgröße', 'en': 'Font Size', 'fr': 'Taille de police'},
    'Normaal': {'de': 'Normal', 'en': 'Normal', 'fr': 'Normal'},
    'Klein': {'de': 'Klein', 'en': 'Small', 'fr': 'Petit'},
    'Groot': {'de': 'Groß', 'en': 'Large', 'fr': 'Grand'},
    'Extra groot': {'de': 'Extra groß', 'en': 'Extra Large', 'fr': 'Extra grand'},
    'Contrast': {'de': 'Kontrast', 'en': 'Contrast', 'fr': 'Contraste'},
    'Hoog contrast': {'de': 'Hoher Kontrast', 'en': 'High Contrast', 'fr': 'Contraste élevé'},
    'Sepia': {'de': 'Sepia', 'en': 'Sepia', 'fr': 'Sépia'},
    'Focus modus (vermindert afleiding)': {'de': 'Fokusmodus (reduziert Ablenkung)', 'en': 'Focus Mode (reduces distraction)', 'fr': 'Mode focus (réduit les distractions)'},

    # Dashboard
    'Welkom': {'de': 'Willkommen', 'en': 'Welcome', 'fr': 'Bienvenue'},
    'Beheer en ontdek je favoriete chocoladeproducten': {'de': 'Verwalte und entdecke deine Lieblings-Schokoladenprodukte', 'en': 'Manage and discover your favorite chocolate products', 'fr': 'Gérez et découvrez vos produits de chocolat préférés'},
    'Favorieten': {'de': 'Favoriten', 'en': 'Favorites', 'fr': 'Favoris'},
    'Je Producten': {'de': 'Deine Produkte', 'en': 'Your Products', 'fr': 'Vos produits'},
    'Alles weergeven': {'de': 'Alles anzeigen', 'en': 'Show All', 'fr': 'Afficher tout'},
    'Sleep kaarten om je dashboard aan te passen': {'de': 'Ziehe Karten, um dein Dashboard anzupassen', 'en': 'Drag cards to customize your dashboard', 'fr': 'Glissez les cartes pour personnaliser votre tableau de bord'},
    'Opslaan': {'de': 'Speichern', 'en': 'Save', 'fr': 'Enregistrer'},
    'Herstellen': {'de': 'Wiederherstellen', 'en': 'Reset', 'fr': 'Réinitialiser'},
    'Klaar': {'de': 'Fertig', 'en': 'Done', 'fr': 'Terminer'},
    'Registreer en bekijk je producten': {'de': 'Registriere und verwalte deine Produkte', 'en': 'Register and view your products', 'fr': 'Enregistrez et affichez vos produits'},
    'Ontdekken': {'de': 'Entdecken', 'en': 'Discover', 'fr': 'Découvrir'},
    'Verken nieuwe chocolades': {'de': 'Entdecke neue Schokoladen', 'en': 'Explore new chocolates', 'fr': 'Explorez de nouveaux chocolats'},
    'Klantenservice': {'de': 'Kundenservice', 'en': 'Customer Service', 'fr': 'Service client'},
    'Hulp en ondersteuning': {'de': 'Hilfe und Unterstützung', 'en': 'Help and Support', 'fr': 'Aide et assistance'},
    'Bestel nieuwe producten': {'de': 'Bestelle neue Produkte', 'en': 'Order new products', 'fr': 'Commandez de nouveaux produits'},
    'Community': {'de': 'Gemeinschaft', 'en': 'Community', 'fr': 'Communauté'},
    'Verbind met andere fans': {'de': 'Verbinde dich mit anderen Fans', 'en': 'Connect with other fans', 'fr': 'Connectez-vous avec d\'autres fans'},
    'Chocorewards': {'de': 'Chocorewards', 'en': 'Chocorewards', 'fr': 'Chocorewards'},
    'Verzamel punten en beloningen': {'de': 'Sammle Punkte und Belohnungen', 'en': 'Collect points and rewards', 'fr': 'Collectez des points et des récompenses'},
    'Winkels': {'de': 'Geschäfte', 'en': 'Stores', 'fr': 'Magasins'},
    'Vind de dichtstbijzijnde winkel': {'de': 'Finde den nächsten Laden', 'en': 'Find the nearest store', 'fr': 'Trouvez le magasin le plus proche'},
    'Ontdek Chocoloco': {'de': 'Entdecke Chocoloco', 'en': 'Discover Chocoloco', 'fr': 'Découvrez Chocoloco'},
    'Kijk hoe je onze chocoladeproducten het beste kunt gebruiken': {'de': 'Sieh, wie du unsere Schokoladenprodukte am besten verwendest', 'en': 'See how to best use our chocolate products', 'fr': 'Découvrez comment utiliser au mieux nos produits au chocolat'},
    'Laatste Nieuws': {'de': 'Letzte Nachrichten', 'en': 'Latest News', 'fr': 'Actualités'},
    'Er is momenteel geen nieuws beschikbaar.': {'de': 'Es sind derzeit keine Nachrichten verfügbar.', 'en': 'No news available at the moment.', 'fr': 'Aucune actualité disponible pour le moment.'},
    'Toegevoegd': {'de': 'Hinzugefügt', 'en': 'Added', 'fr': 'Ajouté'},
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

base_dir = Path('app/translations')

for lang in ['nl', 'de', 'en', 'fr']:
    po_path = base_dir / lang / 'LC_MESSAGES' / 'messages.po'

    content = PO_HEADER.format(lang=lang)

    for nl_text, translations in TRANSLATIONS.items():
        translated = translations.get(lang, nl_text)
        content += f'msgid "{nl_text}"\nmsgstr "{translated}"\n\n'

    po_path.write_text(content, encoding='utf-8')
    print(f"Updated {po_path}")

print("\nAll PO files updated. Compiling...")
os.system('pybabel compile -d app/translations')
print("Done!")
