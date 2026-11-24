#  Glucose Overlay

Ein kompaktes Windows-Widget für Dexcom-Share-Werte: transparent, immer im Vordergrund und standardmäßig klickdurchlässig.

> [!NOTE]
> **Basiert auf [dextop von Paweł Fornagiel](https://github.com/pFornagiel/dextop).**  
> Diese Variante entwickelt das Original mit einer neuen PyQt6-Oberfläche und eigenem Crimson-Design weiter. Der ursprüngliche Copyright-Hinweis und die [MIT-Lizenz](LICENSE) bleiben erhalten.

![Crimson Glucose Overlay – Vorschau](docs/crimson-glucose-overlay-preview.png)

## Änderungen gegenüber dem Original

| Bereich | Diese Variante |
| --- | --- |
| Oberfläche | PyQt6 und QPainter statt Tk; rahmenloses Overlay mit eigener Glukose-, Trend- und Delta-Anzeige |
| Darstellung | Farbige Zustände, einstellbare Grenzwerte und automatisches Abblenden bei Inaktivität |
| Einstellungen | Überarbeiteter Dialog für Zugang, Region, Grenzwerte und Deckkraft; gespeicherte Fensterposition |
| Bedienung & Build | Tray-Menü für Verschieben, Aktualisieren und Autostart; eigenständige EXE mit PyInstaller |

Die Dexcom-Share-Anbindung erfolgt weiterhin über [pydexcom](https://github.com/gagebenne/pydexcom). Angezeigt werden mmol/L-Werte; die Share-Region ist zwischen USA und außerhalb der USA umschaltbar.

## Starten

**Voraussetzungen:** Windows 10/11, Python 3.12 und ein Dexcom-Konto mit aktivierter Share-Funktion.

```powershell
git clone https://github.com/argonaut-0/dextop.git
cd dextop
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe Dextop.py
```

Beim ersten Start die eigenen Dexcom-Zugangsdaten und die passende Region eintragen. Für europäische Konten **Outside US / Europe** wählen.

**Bedienung:** Rechtsklick auf das Tray-Symbol öffnet das Menü. Zum Verschieben **Drag and Drop aktivieren** einschalten und anschließend wieder ausschalten, damit das Widget klickdurchlässig bleibt. Einstellungen, sofortige Aktualisierung und Autostart sind ebenfalls dort erreichbar.

## EXE erstellen

Nach der Einrichtung im Projektverzeichnis ausführen:

```powershell
.\build.bat
```

Ergebnis: `dist\Dextop.exe`.

## Lokale Daten

Einstellungen und Fensterposition liegen unter `%APPDATA%\dextop\settings.ini`. Der Benutzername wird im Klartext gespeichert, das Passwort mit Fernet verschlüsselt. Der Schlüssel wird aus dem Rechnernamen abgeleitet; dies ist kein Windows-Anmeldedatenspeicher. Schriftarten werden beim ersten Bedarf nach `%APPDATA%\dextop\fonts` geladen. Das Projekt betreibt keinen eigenen Datenserver.

---

**Inoffizielles Projekt ohne Verbindung zu Dexcom, Inc.** Das Widget ersetzt keine medizinische Überwachung und ist keine alleinige Grundlage für Therapieentscheidungen.
