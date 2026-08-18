# Thermische Anlagen: Interaktive Kreisprozess-Simulation

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://thermo-anlagen-berechnungen.streamlit.app/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![CoolProp](https://img.shields.io/badge/CoolProp-6.4+-red.svg)](http://www.coolprop.org/)

Diese interaktive Web-Applikation ermöglicht die thermodynamische Auslegung, Simulation und Visualisierung von thermischen Kreisprozessen. Sie dient als digitales Werkzeug zur Untersuchung von realen und idealen Betriebsbedingungen in der Energietechnik.

## Live Demo
Die Anwendung ist direkt im Browser nutzbar, ohne lokale Installation:
**[Hier geht es zur App](https://thermo-anlagen-berechnungen.streamlit.app/)**

## Über das Projekt
Dieses Tool entstand im Rahmen eines Masterprojekts im Studiengang **Gebäude- und Energietechnik** an der **HTWK Leipzig** (Betreuung: Prof. Dr.-Ing. Göpfert). Ziel war es, komplexe thermodynamische Berechnungen durch eine intuitive Benutzeroberfläche zugänglich zu machen und die Abhängigkeiten einzelner Anlagenparameter visuell erfahrbar zu machen.

## Kernfunktionen
Das Tool umfasst aktuell drei Simulationsmodule:

*   **Clausius-Rankine-Prozess (Dampfkraftwerk)**
    *   Vergleich von idealen (isentropen) und realen (irreversiblen) Prozessen.
    *   Integration einer optionalen Zwischenüberhitzung inkl. Parameterstudie zur Vermeidung von Tropfenschlag.
*   **Joule-Prozess (Gasturbine)**
    *   Auslegung offener Gasturbinen mit verschiedenen Arbeitsfluiden (Luft, Helium, Argon, CO2).
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

1. Repository klonen:
   ```bash
   git clone https://github.com/Nike1594/thermo-anlagen-tool.git
   cd thermo-anlagen-tool
2. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
4. App starten:
   ```bash
   streamlit run app.py

## Autor
Nils Kellner

Masterstudent Gebäude- und Energietechnik, HTWK Leipzig
