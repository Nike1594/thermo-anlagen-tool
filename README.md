# Thermische Anlagen: Interaktive Kreisprozess-Simulation

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://thermo-anlagen-berechnungen.streamlit.app/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![CoolProp](https://img.shields.io/badge/CoolProp-6.4+-red.svg)](http://www.coolprop.org/)

Diese interaktive Web-Applikation ermöglicht die thermodynamische Auslegung und Visualisierung von thermischen Kreisprozessen. Sie dient als digitales Werkzeug zur Untersuchung von realen und idealen Betriebsbedingungen in der Energietechnik.

## Live Demo
Die Anwendung ist direkt im Browser nutzbar, ohne lokale Installation:
**[Hier geht es zur App](https://thermo-anlagen-berechnungen.streamlit.app/)**

## Über das Projekt
Dieses Tool entstand im Rahmen eines Masterprojekts im Studiengang **Gebäude- und Energietechnik** an der **HTWK Leipzig** (Betreuung: Prof. Dr.-Ing. Göpfert). Ziel war es, komplexe thermodynamische Berechnungen durch eine intuitive Benutzeroberfläche zugänglich zu machen und die Abhängigkeiten einzelner Anlagenparameter visuell erfahrbar zu machen.

## Kernfunktionen
Das Tool umfasst aktuell vier Module:

*   **Clausius-Rankine-Prozess (Dampfkraftwerk)**
    *   Vergleich von idealen (isentropen) und realen (irreversiblen) Prozessen.
    *   Integration einer optionalen Zwischenüberhitzung inkl. Parameterstudie zur Vermeidung von Tropfenschlag.
*   **Joule-Prozess (Gasturbine)**
    *   Auslegung offener Gasturbinen mit verschiedenen Arbeitsfluiden (Luft, Helium, Argon, CO2).
*   **GuD-Kombikraftwerk (Gas-und-Dampf)**
    * Prozesskopplung: Verschaltung von Gasturbine (Joule) und nachgeschaltetem Dampf-/ORC-Kreisprozess (Clausius-Rankine) über einen Abhitzedampferzeuger (AHDE).
    * Exergie-Analyse: Detaillierte Betrachtung der Entropieproduktion und Exergieverluste bei unterschiedlichen Pinch-Point-Auslegungen im interaktiven T-Q̇-Diagramm.
    * Anlagen-Sicherheit: Automatische Warnungen vor Säuretaupunkt-Unterschreitungen im Kaminabgas sowie Tropfenschlagerosion (mit zuschaltbarer Zwischenüberhitzung).
*   **Kompressionskälteanlagen & Wärmepumpen**
    *   Einstufige und zweistufige Verdichtungsprozesse.
    *   Schaltungsvarianten: Mitteldruckflasche (partiell/quenchen) und äußere Zwischenkühlung.
    *   Parameterstudien (Contour-Plots) zur Ermittlung von EER und COP in Abhängigkeit von Verdampfungs- und Kondensationstemperatur unter Berücksichtigung von Verdichterschutzgrenzen (Heißgastemperatur < 120°C).

## Verwendete Technologien
Das Backend basiert auf physikalischen Massen- und Energiebilanzen unter Verwendung präziser Stoffdaten:
*   **[Streamlit](https://streamlit.io/):** Frontend-Framework für das interaktive UI.
*   **[CoolProp](http://www.coolprop.org/):** thermodynamische Stoffdatenbibliothek (Open-Source-Alternative zu REFPROP).
*   **[Plotly](https://plotly.com/python/):** Interaktive Visualisierung der log-p-h- und T-s-Diagramme sowie der Parameterfelder.
*   **NumPy:** Vektorisierte Berechnungen für Parameterstudien.
*   **[diagrams.net](https://app.diagrams.net/):** Anlagenschaltschemata zur grafischen Veranschaulichung der Kreisprozesse

## Lokale Installation
Falls der Code lokal ausgeführt oder weiterentwickelt werden soll:

### 1. Voraussetzungen (Einmalig installieren)
Bevor es losgeht, benötigst du zwei Standard-Programme auf deinem Rechner:
* **Python:** Lade [Python hier herunter](https://www.python.org/downloads/) und starte die Installation. **WICHTIG:** Setze im allerersten Fenster ganz unten unbedingt den Haken bei **"Add python.exe to PATH"**, bevor du auf Installieren klickst!
* **Git:** Dieses Hilfsprogramm lädt den Code herunter. Lade [Git für Windows hier herunter](https://git-scm.com/download/win). Starte die Installation und klicke einfach immer auf "Next".

### 2. Eingabefenster öffnen & Zielordner wählen
* Drücke die Windows-Taste auf deiner Tastatur.
* Tippe `powershell` ein und drücke Enter. Es öffnet sich ein Textfenster. 
* Wechsle als Erstes auf deinen Desktop, damit du den Code-Ordner später leicht wiederfindest. Gib dafür diesen Befehl ein und drücke Enter:
  ```bash
  cd ~\Desktop

### 3. Programmcode herunterladen
Kopiere den folgenden Befehl, füge ihn in das PowerShell-Fenster ein und drücke Enter:
```bash
    git clone https://github.com/Nike1594/thermo-anlagen-tool.git
    cd thermo-anlagen-tool
```
### 4. Virtuelle Umgebung erstellen und aktivieren:
```bash
    # Unter Windows:
    python -m venv venv
    venv\Scripts\activate

    # Unter Linux / macOS:
    python3 -m venv venv
    source venv/bin/activate
```
### 5. Abhängigkeiten installieren:
```bash
    pip install -r requirements.txt
```
### 6. Programm starten:
```bash
    streamlit run app.py
```
## Autor
Nils Kellner

Masterstudent Gebäude- und Energietechnik, HTWK Leipzig
