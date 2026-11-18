# IGS Linden: WebUntis → Apple Kalender

**Vorkonfiguriert:** `igs-hannover-linden.webuntis.com`, Schule `igs-hannover-linden`, Schüler-/Stundenplan-ID `8279`.

Dieses Projekt fragt den **öffentlich freigegebenen Schüler-Stundenplan** ab und erzeugt daraus alle 6 Stunden einen **abonnierten Apple-Kalender** unter HTTPS. Zeitraum: 7 Tage zurück, 63 Tage voraus. Es verwendet zunächst die öffentliche REST-Schnittstelle von WebUntis und danach versuchsweise die ältere öffentliche Wochenschnittstelle.

## Aktueller Stand / wichtig

Der Code und die Kalendererzeugung sind mit **Testdaten** geprüft. Ein Echtabruf von der IGS Linden war in der Erstellungsumgebung nicht möglich. Es ist daher **noch nicht nachgewiesen**, dass die Schule die Schüler-ID 8279 auf der anonymen Datenschnittstelle freigibt. Solange das nicht funktioniert, veröffentlicht das Programm **keinen leeren oder falschen Kalender**. Bei Fehlern zeigt der GitHub-Actions-Log, warum es nicht geht.

⚠️ **Datenschutz:** Wer die ICS-URL kennt, kann den veröffentlichten Stundenplan lesen. GitHub Pages ist auch dann nicht automatisch privat, wenn der Quellcode privat ist. Veröffentliche einen personenbezogenen Plan nur, wenn dies für dich und die Betroffenen in Ordnung ist. Wähle sonst einen eigenen, zugriffsgeschützten Hostingdienst oder nutze ausschließlich eine lokale ICS-Datei (ohne Synchronisierung).

## Schnellstart auf GitHub (für automatisches Abo)

1. Bei [github.com](https://github.com/) anmelden. Ein neues Repository anlegen, z. B. `untis-kalender`. Beachte den Datenschutzhinweis oben.
2. Die **Inhalte dieses entpackten Ordners** in das Repository hochladen, einschließlich der versteckten `.github/workflows/stundenplan.yml` und des Ordners `tests`. Falls die GitHub-Weboberfläche Ordner nicht mitsendet, die Dateien unter den exakten Pfaden einzeln anlegen.
3. Unter **Settings → Pages → Build and deployment** als Quelle **GitHub Actions** einstellen.
4. Unter **Actions → Untis-Stundenplan aktualisieren → Run workflow** einmal starten.
5. Prüfen, ob alle Schritte grün durchlaufen. Der Log muss die Anzahl der abgerufenen Stunden melden. Wenn der Aufruf scheitert, nicht mit einer leeren Datei weiterarbeiten: Die Freigabe ist dann nicht bestätigt.
6. Bei erfolgreicher Veröffentlichung lautet die Abo-Adresse typischerweise:

   `https://DEIN-GITHUB-NAME.github.io/untis-kalender/stundenplan.ics`

   Den echten Pfad findest du unter **Settings → Pages**. In der Apple-App Kalender unter **Kalender → Hinzufügen → Kalenderabonnement hinzufügen** einfügen; als Account **iCloud** auswählen.

**Änderungen:** Der GitHub-Workflow läuft viermal täglich; das Apple-iCloud-Abo holt die Änderungen nach eigenem Zeitplan. Somit ist eine Übernahme von Vertretungen nicht garantiert sofort. In den Kalendern werden abgesagte Stunden als „Entfällt: …“ sichtbar, aber nicht als belegte Zeit geführt. Änderungen des Stundenplans können eine neue Apple-Aktualisierung benötigen.

## Lokal auf dem Mac testen

Python 3.10 oder neuer mit Zeitzonendaten installieren (auf GitHub Actions vorhanden). Im entpackten Ordner im Terminal:

```bash
python3 -m unittest discover -s tests -v
python3 untis_ical.py
```

Bei Erfolg liegt die Datei unter `public/stundenplan.ics` und kann einmalig in Kalender importiert werden. Ein Import ist **kein** automatisches Abonnement.

## Technische Konfiguration (optional)

Im Skript sind die Umgebungsvariablen `UNTIS_SERVER`, `UNTIS_SCHOOL`, `UNTIS_STUDENT_ID`, `UNTIS_DAYS_PAST`, `UNTIS_DAYS_FUTURE` und `UNTIS_OUTPUT` vorgesehen. Alle Netzwerkanfragen erfolgen via HTTPS; Anmeldepasswörter werden nicht benötigt oder gespeichert. Bei WebUntis-Änderungen kann eine Anpassung notwendig sein. Die automatische Durchführung von GitHub Actions kann bei Inaktivität deaktiviert werden.

## Quellen

- [Untis: Öffentliche Stundenpläne](https://help.untis.at/hc/en-150/articles/18077455725340-Public-Timetables)
- [API-Referenz zum anonymen View-Endpunkt (Community)](https://github.com/UntisPlus/webuntis-apis/blob/main/docs/07-rest-view.md)
- [Python-Client mit öffentlich dokumentiertem Antwortformat (Apache-2.0)](https://github.com/mklemmingen/webuntis-public)

Dies ist ein unabhängiges Hilfsprogramm und kein offizielles Untis-Produkt.
