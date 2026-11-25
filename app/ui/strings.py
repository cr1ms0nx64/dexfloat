from app.services.polling import ErrorKind

ERROR_MESSAGES = {
    ErrorKind.AUTH: "Zugangsdaten abgelehnt. Bitte Benutzername, Passwort und Region prüfen. Automatische Anmeldung gestoppt.",
    ErrorKind.NETWORK: "Keine Verbindung zu Dexcom. Ein neuer Versuch erfolgt automatisch.",
    ErrorKind.SESSION: "Dexcom-Sitzung abgelaufen. Die Verbindung wird erneut hergestellt.",
    ErrorKind.NO_DATA: "Keine aktuellen Sensordaten verfügbar.",
    ErrorKind.UNKNOWN: "Die Dexcom-Antwort konnte nicht verarbeitet werden. Ein neuer Versuch erfolgt automatisch.",
}
