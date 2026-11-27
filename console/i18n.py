"""console i18n: lightweight dict catalog (no gettext tooling).

Web UI only — kubusd/headless stays English (SPEC §C). Default language is
English; the user's choice is a cookie (`lf_lang`) toggled from the header
button next to the dark/light toggle. Keys ARE the English strings, so a
missing key falls back to the key itself — English by construction.
Code/comments stay English (repo convention); only UI strings are translated.
"""

LANGS = ("en", "nl")
DEFAULT_LANG = "en"
COOKIE = "lf_lang"

# key (English string) -> {"nl": ...}. English needs no entry: it IS the key.
# Placeholders use str.format(): e.g. "Pattern {title} published (counter {c})."
CATALOG = {
    # ---- nav / chrome (base.html) ----
    "Patterns": {"nl": "Patronen"},
    "New pattern": {"nl": "Nieuw patroon"},
    "Admin": {"nl": "Beheer"},
    "Log out": {"nl": "Uitloggen"},
    # ---- login ----
    "Log in": {"nl": "Inloggen"},
    "Username": {"nl": "Gebruikersnaam"},
    "Password": {"nl": "Wachtwoord"},
    "Accounts are created by the makerspace admin.":
        {"nl": "Accounts worden aangemaakt door de beheerder van de makerspace."},
    # ---- change password ----
    "Change password": {"nl": "Wachtwoord wijzigen"},
    "You must set a new password on first login.":
        {"nl": "Bij de eerste login moet je een nieuw wachtwoord instellen."},
    "New password": {"nl": "Nieuw wachtwoord"},
    "Repeat new password": {"nl": "Herhaal het nieuwe wachtwoord"},
    # ---- patterns page ----
    "+ New pattern": {"nl": "+ Nieuw patroon"},
    "Title": {"nl": "Titel"},
    "Steps": {"nl": "Stappen"},
    "Creator": {"nl": "Maker"},
    "Created": {"nl": "Aangemaakt"},
    "Status": {"nl": "Status"},
    "active": {"nl": "actief"},
    "Activate": {"nl": "Activeren"},
    "No patterns yet — create one.": {"nl": "Nog geen patronen — maak er een aan."},
    "Revoke all (default show)": {"nl": "Alles intrekken (standaardshow)"},
    # ---- admin page ----
    "Users": {"nl": "Gebruikers"},
    "Banned": {"nl": "Geblokkeerd"},
    "Actions": {"nl": "Acties"},
    "yes": {"nl": "ja"},
    "no": {"nl": "nee"},
    "Unban": {"nl": "Deblokkeer"},
    "Ban": {"nl": "Blokkeer"},
    "Create user": {"nl": "Gebruiker aanmaken"},
    "Password (>= 8 chars)": {"nl": "Wachtwoord (min. 8 tekens)"},
    "Sign control (admin only, V18)": {"nl": "Bordbediening (alleen beheer, V18)"},
    "Sign on": {"nl": "Bord aan"},
    "Sign off": {"nl": "Bord uit"},
    "Schedule": {"nl": "Schema"},
    "Start (HH:MM)": {"nl": "Begin (UU:MM)"},
    "Stop (HH:MM)": {"nl": "Einde (UU:MM)"},
    "Schedule enabled": {"nl": "Schema ingeschakeld"},
    "Publish schedule": {"nl": "Schema publiceren"},
    "Audit log": {"nl": "Auditlog"},
    "Time": {"nl": "Tijd"},
    "Actor": {"nl": "Actor"},
    "Action": {"nl": "Actie"},
    "Detail": {"nl": "Detail"},
    # ---- flash messages ----
    "Account suspended.": {"nl": "Account is geschorst."},
    "Invalid credentials.": {"nl": "Ongeldige inloggegevens."},
    "Password must be at least 8 characters.":
        {"nl": "Wachtwoord moet minstens 8 tekens zijn."},
    "Passwords do not match.": {"nl": "Wachtwoorden komen niet overeen."},
    "Password updated.": {"nl": "Wachtwoord bijgewerkt."},
    "Rate limit reached — try again in a minute.":
        {"nl": "Te veel verzoeken — probeer het over een minuut opnieuw."},
    "Invalid steps JSON.": {"nl": "Ongeldige stappen-JSON."},
    "Invalid pattern: {e}": {"nl": "Ongeldig patroon: {e}"},
    "MQTT publish failed: {e}": {"nl": "MQTT-publicatie mislukt: {e}"},
    "Pattern {title} published (counter {counter}).":
        {"nl": "Patroon {title} gepubliceerd (teller {counter})."},
    "Pattern {title} activated.": {"nl": "Patroon {title} geactiveerd."},
    "All patterns revoked (default show).":
        {"nl": "Alle patronen ingetrokken (standaardshow)."},
    "Username + password (>= 8 chars) required.":
        {"nl": "Gebruikersnaam + wachtwoord (min. 8 tekens) vereist."},
    "User already exists.": {"nl": "Gebruiker bestaat al."},
    "User {username} created.": {"nl": "Gebruiker {username} aangemaakt."},
    "User {username} banned.": {"nl": "Gebruiker {username} geblokkeerd."},
    "User {username} unbanned.": {"nl": "Gebruiker {username} gedeblokkeerd."},
    "Sign manually on (override, expires in 1 h).":
        {"nl": "Bord handmatig aan (override, verloopt na 1 uur)."},
    "Sign manually off (override, expires in 1 h).":
        {"nl": "Bord handmatig uit (override, verloopt na 1 uur)."},
    "Invalid schedule: {e}": {"nl": "Ongeldig schema: {e}"},
    "Schedule published.": {"nl": "Schema gepubliceerd."},
    # ---- new pattern page ----
    "A pattern is a sequence of steps. Each step runs for its duration, and "
    "each cube can use its own primitive. Cubes you don't set keep their "
    "previous step's look (first step = off). Publishing activates it on the "
    "cubes immediately.":
        {"nl": "Een patroon is een reeks stappen. Elke stap draait voor zijn "
               "duur en elke kubus kan zijn eigen primitieve gebruiken. Kubussen "
               "die je niet instelt behouden de look van de vorige stap (eerste "
               "stap = uit). Publiceren activeert het meteen op de kubussen."},
    "e.g. Sinterklaas 2026": {"nl": "bijv. Sinterklaas 2026"},
    "What it looks like, when to use it":
        {"nl": "Hoe het eruitziet, wanneer je het gebruikt"},
    "Description": {"nl": "Omschrijving"},
    "+ Add step": {"nl": "+ Stap toevoegen"},
    "Publish": {"nl": "Publiceren"},
    "LED sign board (SPEC §C)": {"nl": "LED-bord (SPEC §C)"},
    "sign": {"nl": "bord"},
    "anvil — always on": {"nl": "aambeeld — altijd aan"},
    "hammer raised": {"nl": "hamer omhoog"},
    "hammer mid-swing": {"nl": "hamer midslingering"},
    "hammer impact": {"nl": "hamer impact"},
    "sparks": {"nl": "vonken"},
    "cube 1": {"nl": "kubus 1"},
    "cube 2": {"nl": "kubus 2"},
    "cube 3": {"nl": "kubus 3"},
    # JS-side editor strings (see js_strings)
    "(keep)": {"nl": "(behoud)"},
    "primitives available": {"nl": "primitieven beschikbaar"},
    # ---- primitive reference table ----
    "Primitive reference": {"nl": "Primitieven-overzicht"},
    "What each primitive does, and which controls apply.":
        {"nl": "Wat elke primitieve doet en welke instellingen gelden."},
    "primitive": {"nl": "primitief"},
    "what it does": {"nl": "wat het doet"},
    "color": {"nl": "kleur"},
    "brightness": {"nl": "helderheid"},
    "speed": {"nl": "snelheid"},
    "offset": {"nl": "verschuiving"},
    "built-in": {"nl": "ingebouwd"},
    "random": {"nl": "willekeurig"},
    "A single fixed color, stays on.":
        {"nl": "Eén vaste kleur, blijft aan."},
    "Continuously cycles through all hues (the classic rainbow).":
        {"nl": "Draait continu door alle kleuren (de klassieke regenboog)."},
    "Breathing effect: steps through colors, each gently pulsing in intensity.":
        {"nl": "Ademend effect: loopt door de kleuren, elke kleur pulseert "
               "zachtjes in intensiteit."},
    "Smoothly fades from one color to the next and back.":
        {"nl": "Vloeit soepel van de ene kleur naar de volgende en terug."},
    "Flashing chase effect (blinks on a single cube; sweeps in a sequence).":
        {"nl": "Flitsend chase-effect (knippert op één kubus; veegt in een reeks)."},
    "Warm festive glow that gently breathes (reddish-gold).":
        {"nl": "Warm feestelijke gloed die zacht ademt (roodgoud)."},
    "Jumps to a new random color at a steady rate.":
        {"nl": "Springt in vast tempo naar een willekeurige nieuwe kleur."},
    "Flickering orange-red like a real flame.":
        {"nl": "Flikkert oranje-rood als een echte vlam."},
    "Mostly dark, with brief flashes in random colors (twinkle).":
        {"nl": "Meestal donker, met korte flitsen in willekeurige kleuren (fonkelt)."},
    "Slow, smooth sweep through the color wheel.":
        {"nl": "Langzame, vloeiende sweep door het kleurenwiel."},
    "Smooth oscillation between two colors (red ↔ blue by default).":
        {"nl": "Gladde oscillatie tussen twee kleuren (standaard rood ↔ blauw)."},
    "Hard on/off strobe of your chosen color (capped below 3 Hz).":
        {"nl": "Harde aan/uit-flitsing van je gekozen kleur (max. 3 Hz)."},
    "Alternating red ↔ blue, like an emergency light.":
        {"nl": "Wisselt rood ↔ blauw, als een zwaailicht."},
    "Knight-Rider style scanning light (blinks on one cube; with per-cube "
    "offsets it sweeps across the stack).":
        {"nl": "Scannerlicht à la Knight Rider (knippert op één kubus; met "
               "per-kubus-verschuivingen veegt het over de stack)."},
    "Turns the cube off (black).": {"nl": "Zet de kubus uit (zwart)."},
    "• color: your chosen color (single-color primitives).\n"
    "  • brightness 0–1, speed 1 = normal, 2 = twice as fast, 0.5 = half speed.\n"
    "  • offset: phase shift as a fraction of one animation cycle — 0 = in sync; "
    "0.5 = half a cycle out of phase; stagger cubes (0 / 0.33 / 0.66) to make "
    "knight/chase/rainbow sweep across the stack.\n"
    "  • built-in = the primitive uses its own fixed palette.":
        {"nl": "• kleur: je gekozen kleur (één-kleur-primitieven).\n"
               "  • helderheid 0–1, snelheid 1 = normaal, 2 = twee keer zo snel, "
               "0.5 = halve snelheid.\n"
               "  • verschuiving: faseverschuiving als fractie van één "
               "animatiecyclus — 0 = synchroon; 0.5 = halve cyclus verschoven; "
               "kubussen staggeren (0 / 0.33 / 0.66) laat knight/chase/rainbow "
               "over de stack vegen.\n"
               "  • ingebouwd = de primitieve gebruikt zijn eigen vaste palet."},
}


def current_lang() -> str:
    """The user's language: cookie `lf_lang` if valid, else English."""
    from flask import request

    lang = request.cookies.get(COOKIE, DEFAULT_LANG)
    return lang if lang in LANGS else DEFAULT_LANG


def t(key: str, **params) -> str:
    """Translate `key` (an English string) into the current language.

    Unknown keys fall back to the key itself (English), so a missed string
    degrades gracefully instead of rendering an error.
    """
    entry = CATALOG.get(key)
    s = (entry.get(current_lang()) if entry else None) or key
    if params:
        s = s.format(**params)
    return s


# Strings the JS editor needs (template literals in new_pattern.html).
JS_KEYS = (
    "(keep)",
    "Step {n}",
    "duration (s)",
    "cube",
    "primitive",
    "color",
    "brightness",
    "speed",
    "offset",
    "primitives available",
    "cube 1",
    "cube 2",
    "cube 3",
    "color (single-color primitive)",
    "color picker only for single-color primitives (static, strobe, chase, knight)",
    "brightness: 0 = off, 1 = full",
    "speed: 0.1 = slow, 3 = fast",
    "offset: phase shift as a fraction of one animation cycle (0 = in sync; "
    "0.5 = half a cycle out of phase; stagger cubes e.g. 0 / 0.33 / 0.66 for a sweep)",
)


def js_strings() -> dict:
    """{key -> translation} for injecting into the page's JS as `const T`."""
    return {k: t(k) for k in JS_KEYS}
