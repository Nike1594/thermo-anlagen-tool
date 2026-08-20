from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import numpy as np
import CoolProp.CoolProp as CP

ZustandDict = Dict[str, float]


@lru_cache(maxsize=32)
def _saettigungslinie_fluid(fluid: str) -> Tuple[Tuple[float, ...], Tuple[float, ...]]:
    """Berechnet die Siede- und Taulinie für ein beliebiges Fluid dynamisch."""
    t_krit = CP.PropsSI("Tcrit", fluid)

    t_min_fluid = CP.PropsSI("Tmin", fluid)
    t_start = max(t_min_fluid + 0.1, 200.0) 
    
    t_kurve = np.linspace(t_start, t_krit - 0.1, 100)
    s_siedelinie = [CP.PropsSI("S", "T", t, "Q", 0, fluid) / 1000 for t in t_kurve]
    s_taulinie = [CP.PropsSI("S", "T", t, "Q", 1, fluid) / 1000 for t in t_kurve]
    T_kurve_C = [t - 273.15 for t in t_kurve]
    
    s_g = s_siedelinie + s_taulinie[::-1]
    T_g = T_kurve_C + T_kurve_C[::-1]
    return tuple(s_g), tuple(T_g)


class ClausiusRankineProzess:
    _ref_states_gesetzt = set()

    def __init__(
        self,
        p_kond: float,
        p_kessel: float,
        T_max: float,
        m_dot: float = 1.0,
        eta_s_P: float = 1.0,
        eta_s_T: float = 1.0,
        ignore_pump: bool = False,
        has_zue: bool = False,
        p_zue: Optional[float] = None,
        T_zue: Optional[float] = None,
        fluid: str = "Water"
    ) -> None:
        self.fluid = fluid
        
        if has_zue and (p_zue is None or T_zue is None):
            raise ValueError("Bei has_zue=True müssen p_zue und T_zue angegeben werden.")

        if self.fluid not in ClausiusRankineProzess._ref_states_gesetzt:
            try:
                CP.set_reference_state(self.fluid, "DEF")
            except ValueError:
                pass
            ClausiusRankineProzess._ref_states_gesetzt.add(self.fluid)

        self.p_kond = p_kond * 1e5
        self.p_kessel = p_kessel * 1e5
        self.T_max = T_max + 273.15
        self.m_dot = m_dot
        self.eta_s_P = eta_s_P
        self.eta_s_T = eta_s_T

        self.ignore_pump = ignore_pump
        self.has_zue = has_zue
        self.p_zue = (p_zue * 1e5) if p_zue else None
        self.T_zue = (T_zue + 273.15) if T_zue else None

        self.zustand: Dict[str, ZustandDict] = {}


    # Interne Hilfsfunktionen für Turbine / Pumpe / Siedepunkt

    def _turbinenstufe(
        self, h_in: float, s_in: float, p_out: float
    ) -> Tuple[ZustandDict, ZustandDict]:
        h_s = CP.PropsSI("H", "P", p_out, "S", s_in, self.fluid)
        T_s = CP.PropsSI("T", "P", p_out, "H", h_s, self.fluid)
        h_real = h_in - self.eta_s_T * (h_in - h_s)
        T_real = CP.PropsSI("T", "P", p_out, "H", h_real, self.fluid)
        s_real = CP.PropsSI("S", "P", p_out, "H", h_real, self.fluid)
        zustand_s = {"p": p_out, "T": T_s, "h": h_s, "s": s_in}
        zustand_real = {"p": p_out, "T": T_real, "h": h_real, "s": s_real}
        return zustand_s, zustand_real

    def _pumpe(
        self, zustand_ein: ZustandDict, p_out: float
    ) -> Tuple[ZustandDict, ZustandDict]:
        h_in, s_in, T_in = zustand_ein["h"], zustand_ein["s"], zustand_ein["T"]

        if self.ignore_pump:
            zustand_s = {"p": p_out, "T": T_in, "h": h_in, "s": s_in}
            return zustand_s, dict(zustand_s)

        h_s = CP.PropsSI("H", "P", p_out, "S", s_in, self.fluid)
        T_s = CP.PropsSI("T", "P", p_out, "H", h_s, self.fluid)
        h_real = h_in + (h_s - h_in) / self.eta_s_P
        T_real = CP.PropsSI("T", "P", p_out, "H", h_real, self.fluid)
        s_real = CP.PropsSI("S", "P", p_out, "H", h_real, self.fluid)
        zustand_s = {"p": p_out, "T": T_s, "h": h_s, "s": s_in}
        zustand_real = {"p": p_out, "T": T_real, "h": h_real, "s": s_real}
        return zustand_s, zustand_real

    def _siedepunkt(self, p: float) -> ZustandDict:
        h = CP.PropsSI("H", "P", p, "Q", 0, self.fluid)
        s = CP.PropsSI("S", "P", p, "Q", 0, self.fluid)
        T = CP.PropsSI("T", "P", p, "Q", 0, self.fluid)
        return {"p": p, "T": T, "h": h, "s": s}


    # Hauptberechnung

    def berechne_zustaende(self) -> None:
        try:
            h1 = CP.PropsSI("H", "P", self.p_kessel, "T", self.T_max, self.fluid)
            s1 = CP.PropsSI("S", "P", self.p_kessel, "T", self.T_max, self.fluid)
        except ValueError:
            h1 = CP.PropsSI("H", "P", self.p_kessel, "Q", 1, self.fluid)
            s1 = CP.PropsSI("S", "P", self.p_kessel, "Q", 1, self.fluid)

        self.zustand["1"] = {"p": self.p_kessel, "T": self.T_max, "h": h1, "s": s1}

        if not self.has_zue:
            self.zustand["2s"], self.zustand["2"] = self._turbinenstufe(h1, s1, self.p_kond)

            zustand_3 = self._siedepunkt(self.p_kond)
            self.zustand["3"] = zustand_3

            self.zustand["4s"], self.zustand["4"] = self._pumpe(zustand_3, self.p_kessel)

            h2 = self.zustand["2"]["h"]
            h4 = self.zustand["4"]["h"]
            self.w_t = (h1 - h2) / 1000
            self.w_p = (h4 - zustand_3["h"]) / 1000
            self.q_zu = (h1 - h4) / 1000

        else:
            self.zustand["2s"], self.zustand["2"] = self._turbinenstufe(h1, s1, self.p_zue)

            try:
                h3z = CP.PropsSI("H", "P", self.p_zue, "T", self.T_zue, self.fluid)
                s3z = CP.PropsSI("S", "P", self.p_zue, "T", self.T_zue, self.fluid)
            except ValueError:
                h3z = CP.PropsSI("H", "P", self.p_zue, "Q", 1, self.fluid)
                s3z = CP.PropsSI("S", "P", self.p_zue, "Q", 1, self.fluid)
            self.zustand["3z"] = {"p": self.p_zue, "T": self.T_zue, "h": h3z, "s": s3z}

            self.zustand["4s"], self.zustand["4"] = self._turbinenstufe(h3z, s3z, self.p_kond)

            zustand_5 = self._siedepunkt(self.p_kond)
            self.zustand["5"] = zustand_5

            self.zustand["6s"], self.zustand["6"] = self._pumpe(zustand_5, self.p_kessel)

            h2 = self.zustand["2"]["h"]
            h4 = self.zustand["4"]["h"]
            h6 = self.zustand["6"]["h"]
            self.w_t = ((h1 - h2) + (h3z - h4)) / 1000
            self.w_p = (h6 - zustand_5["h"]) / 1000
            q_kessel = (h1 - h6) / 1000
            q_zue_stufe = max((h3z - h2) / 1000, 0.0)
            self.q_zu = q_kessel + q_zue_stufe

        self.w_netto = self.w_t - self.w_p
        self.wirkungsgrad = self.w_netto / self.q_zu if self.q_zu > 0 else 0
        self.arbeitsverhaeltnis = self.w_netto / self.w_t if self.w_t > 0 else 0
        self.leistung_turbine = self.m_dot * self.w_t
        self.leistung_pumpe = self.m_dot * self.w_p
        self.pi = self.p_kessel / self.p_kond

        T_sat_kond = self.zustand["5" if self.has_zue else "3"]["T"]
        self.tau = self.T_max / T_sat_kond


    # Diagrammdaten

    def get_saettigungslinie(self) -> Tuple[List[float], List[float]]:
        """Holt die dynamische Siede-/Taulinie für das gewählte Fluid aus dem Cache."""
        s_g, T_g = _saettigungslinie_fluid(self.fluid)
        return list(s_g), list(T_g)

    def _get_boiling_curve(self, start_idx: str, p_target: float):
        h_start = self.zustand[start_idx]["h"]
        h_end = CP.PropsSI("H", "P", p_target, "Q", 0, self.fluid)
        if h_start >= h_end:
            return [], []
        h_arr = np.linspace(h_start, h_end, 20)
        s_arr = [CP.PropsSI("S", "P", p_target, "H", h, self.fluid) / 1000 for h in h_arr]
        T_arr_C = [CP.PropsSI("T", "P", p_target, "H", h, self.fluid) - 273.15 for h in h_arr]
        return s_arr, T_arr_C

    def _get_superheat_curve(self, p_target: float, T_end: float):
        h_sat = CP.PropsSI("H", "P", p_target, "Q", 1, self.fluid)
        try:
            h_end = CP.PropsSI("H", "P", p_target, "T", T_end, self.fluid)
        except ValueError:

            h_end = h_sat

        if h_sat >= h_end - 0.1:
            return [], []
            
        h_arr = np.linspace(h_sat, h_end, 20)
        s_arr = [CP.PropsSI("S", "P", p_target, "H", h, self.fluid) / 1000 for h in h_arr]
        T_arr_C = [CP.PropsSI("T", "P", p_target, "H", h, self.fluid) - 273.15 for h in h_arr]
        return s_arr, T_arr_C

    def _get_plot_daten(self, ideal: bool) -> Tuple[List[float], List[float]]:
        suffix = "s" if ideal else ""
        key2 = f"2{suffix}"
        s1, T1 = self.zustand["1"]["s"] / 1000, self.zustand["1"]["T"] - 273.15

        if not self.has_zue:
            key_end = f"4{suffix}"
            s_boil, T_boil = self._get_boiling_curve(key_end, self.p_kessel)
            s_sh, T_sh = self._get_superheat_curve(self.p_kessel, self.T_max)

            keys = ["1", key2, "3", key_end]
            s = [self.zustand[k]["s"] / 1000 for k in keys] + s_boil + s_sh + [s1]
            T = [self.zustand[k]["T"] - 273.15 for k in keys] + T_boil + T_sh + [T1]
        else:
            key_end = f"6{suffix}"
            key4 = f"4{suffix}"
            s_boil, T_boil = self._get_boiling_curve(key_end, self.p_kessel)
            s_sh, T_sh = self._get_superheat_curve(self.p_kessel, self.T_max)

            h_start_rh = self.zustand[key2]["h"]
            h_end_rh = self.zustand["3z"]["h"]
            h_arr_rh = np.linspace(h_start_rh, h_end_rh, 20)
            s_rh = [CP.PropsSI("S", "P", self.p_zue, "H", h, self.fluid) / 1000 for h in h_arr_rh]
            T_rh = [CP.PropsSI("T", "P", self.p_zue, "H", h, self.fluid) - 273.15 for h in h_arr_rh]

            keys_pre = ["1", key2]
            keys_post = [key4, "5", key_end]
            s = (
                [self.zustand[k]["s"] / 1000 for k in keys_pre]
                + s_rh
                + [self.zustand[k]["s"] / 1000 for k in keys_post]
                + s_boil
                + s_sh
                + [s1]
            )
            T = (
                [self.zustand[k]["T"] - 273.15 for k in keys_pre]
                + T_rh
                + [self.zustand[k]["T"] - 273.15 for k in keys_post]
                + T_boil
                + T_sh
                + [T1]
            )
        return s, T

    def get_plot_daten_ideal(self) -> Tuple[List[float], List[float]]:
        return self._get_plot_daten(ideal=True)

    def get_plot_daten_real(self) -> Tuple[List[float], List[float]]:
        return self._get_plot_daten(ideal=False)

    def get_eckpunkte_daten(self):
        if not self.has_zue:
            keys = ["1", "2s", "2", "3", "4s", "4"]
        else:
            keys = ["1", "2s", "2", "3z", "4s", "4", "5", "6s", "6"]

        s = [self.zustand[k]["s"] / 1000 for k in keys]
        T = [self.zustand[k]["T"] - 273.15 for k in keys]
        hover = [
            f"<b>Punkt {k}</b><br>Druck p: {self.zustand[k]['p'] / 100000:.2f} bar"
            f"<br>Temperatur T: {self.zustand[k]['T'] - 273.15:.2f} °C"
            f"<br>Enthalpie h: {self.zustand[k]['h'] / 1000:.2f} kJ/kg"
            f"<br>Entropie s: {self.zustand[k]['s'] / 1000:.4f} kJ/(kg K)"
            for k in keys
        ]
        return s, T, hover, keys

    def get_tabellen_daten(self):
        if not self.has_zue:
            keys = ["1", "2", "3", "4"]
            labels = [
                "1 (Frischdampf Kessel)",
                "2 (Austritt Turbine)",
                "3 (Kondensataustritt)",
                "4 (Austritt Pumpe)",
            ]
        else:
            keys = ["1", "2", "3z", "4", "5", "6"]
            labels = [
                "1 (Frischdampf Kessel)",
                "2 (Austritt HD-Turbine)",
                "3z (Nach Zwischenüberhitzung)",
                "4 (Austritt ND-Turbine)",
                "5 (Kondensataustritt)",
                "6 (Austritt Pumpe)",
            ]

        p = [f"{self.zustand[k]['p'] / 100000:.2f}" for k in keys]
        T = [f"{self.zustand[k]['T'] - 273.15:.2f}" for k in keys]
        h = [f"{self.zustand[k]['h'] / 1000:.2f}" for k in keys]
        s = [f"{self.zustand[k]['s'] / 1000:.4f}" for k in keys]

        return {"labels": labels, "p": p, "T": T, "h": h, "s": s}
