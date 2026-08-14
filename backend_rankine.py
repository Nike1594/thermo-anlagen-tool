import CoolProp.CoolProp as CP
import numpy as np

class ClausiusRankineProzess:
    def __init__(self, p_kond, p_kessel, T_max, m_dot=1.0, eta_s_P=1.0, eta_s_T=1.0, ignore_pump=False, has_zue=False, p_zue=None, T_zue=None):
        self.fluid = 'Water'
        CP.set_reference_state(self.fluid, 'DEF')
        self.p_kond = p_kond * 100000
        self.p_kessel = p_kessel * 100000
        self.T_max = T_max + 273.15
        self.m_dot = m_dot
        self.eta_s_P = eta_s_P
        self.eta_s_T = eta_s_T
        
        self.ignore_pump = ignore_pump
        self.has_zue = has_zue
        self.p_zue = (p_zue * 100000) if p_zue else None
        self.T_zue = (T_zue + 273.15) if T_zue else None
        
        self.zustand = {}

    def berechne_zustaende(self):
        h1 = CP.PropsSI('H', 'P', self.p_kessel, 'T', self.T_max, self.fluid)
        s1 = CP.PropsSI('S', 'P', self.p_kessel, 'T', self.T_max, self.fluid)
        self.zustand['1'] = {'p': self.p_kessel, 'T': self.T_max, 'h': h1, 's': s1}
        
        if not self.has_zue:
            h2s = CP.PropsSI('H', 'P', self.p_kond, 'S', s1, self.fluid)
            h2 = h1 - self.eta_s_T * (h1 - h2s)
            T2s = CP.PropsSI('T', 'P', self.p_kond, 'H', h2s, self.fluid)
            T2 = CP.PropsSI('T', 'P', self.p_kond, 'H', h2, self.fluid)
            s2 = CP.PropsSI('S', 'P', self.p_kond, 'H', h2, self.fluid)
            self.zustand['2s'] = {'p': self.p_kond, 'T': T2s, 'h': h2s, 's': s1}
            self.zustand['2'] = {'p': self.p_kond, 'T': T2, 'h': h2, 's': s2}

            h3 = CP.PropsSI('H', 'P', self.p_kond, 'Q', 0, self.fluid)
            s3 = CP.PropsSI('S', 'P', self.p_kond, 'Q', 0, self.fluid)
            T3 = CP.PropsSI('T', 'P', self.p_kond, 'Q', 0, self.fluid)
            self.zustand['3'] = {'p': self.p_kond, 'T': T3, 'h': h3, 's': s3}

            if self.ignore_pump:
                h4 = h3; h4s = h3; s4 = s3; T4 = T3; T4s = T3
            else:
                h4s = CP.PropsSI('H', 'P', self.p_kessel, 'S', s3, self.fluid)
                h4 = h3 + (h4s - h3) / self.eta_s_P
                s4 = CP.PropsSI('S', 'P', self.p_kessel, 'H', h4, self.fluid)
                T4s = CP.PropsSI('T', 'P', self.p_kessel, 'H', h4s, self.fluid)
                T4 = CP.PropsSI('T', 'P', self.p_kessel, 'H', h4, self.fluid)
                
            self.zustand['4s'] = {'p': self.p_kessel, 'T': T4s, 'h': h4s, 's': s3}
            self.zustand['4'] = {'p': self.p_kessel, 'T': T4, 'h': h4, 's': s4}
            
            self.w_t = (h1 - h2) / 1000
            self.w_p = (h4 - h3) / 1000
            self.q_zu = (h1 - h4) / 1000
            
        else:
    
            h2s = CP.PropsSI('H', 'P', self.p_zue, 'S', s1, self.fluid)
            h2 = h1 - self.eta_s_T * (h1 - h2s)
            T2s = CP.PropsSI('T', 'P', self.p_zue, 'H', h2s, self.fluid)
            T2 = CP.PropsSI('T', 'P', self.p_zue, 'H', h2, self.fluid)
            s2 = CP.PropsSI('S', 'P', self.p_zue, 'H', h2, self.fluid)
            self.zustand['2s'] = {'p': self.p_zue, 'T': T2s, 'h': h2s, 's': s1}
            self.zustand['2'] = {'p': self.p_zue, 'T': T2, 'h': h2, 's': s2}
            
            h3z = CP.PropsSI('H', 'P', self.p_zue, 'T', self.T_zue, self.fluid)
            s3z = CP.PropsSI('S', 'P', self.p_zue, 'T', self.T_zue, self.fluid)
            self.zustand['3z'] = {'p': self.p_zue, 'T': self.T_zue, 'h': h3z, 's': s3z}
            
            h4s = CP.PropsSI('H', 'P', self.p_kond, 'S', s3z, self.fluid)
            h4 = h3z - self.eta_s_T * (h3z - h4s)
            T4s = CP.PropsSI('T', 'P', self.p_kond, 'H', h4s, self.fluid)
            T4 = CP.PropsSI('T', 'P', self.p_kond, 'H', h4, self.fluid)
            s4 = CP.PropsSI('S', 'P', self.p_kond, 'H', h4, self.fluid)
            self.zustand['4s'] = {'p': self.p_kond, 'T': T4s, 'h': h4s, 's': s3z}
            self.zustand['4'] = {'p': self.p_kond, 'T': T4, 'h': h4, 's': s4}

            h5 = CP.PropsSI('H', 'P', self.p_kond, 'Q', 0, self.fluid)
            s5 = CP.PropsSI('S', 'P', self.p_kond, 'Q', 0, self.fluid)
            T5 = CP.PropsSI('T', 'P', self.p_kond, 'Q', 0, self.fluid)
            self.zustand['5'] = {'p': self.p_kond, 'T': T5, 'h': h5, 's': s5}

            if self.ignore_pump:
                h6 = h5; h6s = h5; s6 = s5; T6 = T5; T6s = T5
            else:
                h6s = CP.PropsSI('H', 'P', self.p_kessel, 'S', s5, self.fluid)
                h6 = h5 + (h6s - h5) / self.eta_s_P
                s6 = CP.PropsSI('S', 'P', self.p_kessel, 'H', h6, self.fluid)
                T6s = CP.PropsSI('T', 'P', self.p_kessel, 'H', h6s, self.fluid)
                T6 = CP.PropsSI('T', 'P', self.p_kessel, 'H', h6, self.fluid)
                
            self.zustand['6s'] = {'p': self.p_kessel, 'T': T6s, 'h': h6s, 's': s5}
            self.zustand['6'] = {'p': self.p_kessel, 'T': T6, 'h': h6, 's': s6}
            
            self.w_t = ((h1 - h2) + (h3z - h4)) / 1000
            self.w_p = (h6 - h5) / 1000
            q_kessel = (h1 - h6) / 1000
            q_zue_stufe = (h3z - h2) / 1000

            if q_zue_stufe < 0:
                q_zue_stufe = 0 
            self.q_zu = q_kessel + q_zue_stufe

        self.w_netto = self.w_t - self.w_p
        self.wirkungsgrad = self.w_netto / self.q_zu if self.q_zu > 0 else 0
        self.arbeitsverhaeltnis = self.w_netto / self.w_t if self.w_t > 0 else 0
        self.leistung_turbine = self.m_dot * self.w_t
        self.leistung_pumpe = self.m_dot * self.w_p
        self.pi = self.p_kessel / self.p_kond
        self.tau = self.T_max / CP.PropsSI('T', 'P', self.p_kond, 'Q', 0, self.fluid)

    def get_saettigungslinie(self):
        t_krit = CP.PropsSI('Tcrit', self.fluid)
        t_kurve = np.linspace(273.15 + 0.1, t_krit - 0.1, 100)
        s_siedelinie = [CP.PropsSI('S', 'T', t, 'Q', 0, self.fluid) / 1000 for t in t_kurve]
        s_taulinie = [CP.PropsSI('S', 'T', t, 'Q', 1, self.fluid) / 1000 for t in t_kurve]
        T_kurve_C = [t - 273.15 for t in t_kurve]
        s_g = s_siedelinie + s_taulinie[::-1]
        T_g = T_kurve_C + T_kurve_C[::-1]
        return s_g, T_g

    def _get_boiling_curve(self, start_idx, p_target):
        h_start = self.zustand[start_idx]['h']
        h_end = CP.PropsSI('H', 'P', p_target, 'Q', 0, self.fluid)
        if h_start >= h_end: return [], []
        h_arr = np.linspace(h_start, h_end, 20)
        s_arr = [CP.PropsSI('S', 'P', p_target, 'H', h, self.fluid) / 1000 for h in h_arr]
        T_arr_C = [CP.PropsSI('T', 'P', p_target, 'H', h, self.fluid) - 273.15 for h in h_arr]
        return s_arr, T_arr_C
        
    def _get_superheat_curve(self, p_target, T_end):
        h_sat = CP.PropsSI('H', 'P', p_target, 'Q', 1, self.fluid)
        h_end = CP.PropsSI('H', 'P', p_target, 'T', T_end, self.fluid)
        h_arr = np.linspace(h_sat, h_end, 20)
        s_arr = [CP.PropsSI('S', 'P', p_target, 'H', h, self.fluid) / 1000 for h in h_arr]
        T_arr_C = [CP.PropsSI('T', 'P', p_target, 'H', h, self.fluid) - 273.15 for h in h_arr]
        return s_arr, T_arr_C

    def get_plot_daten_ideal(self):
        if not self.has_zue:
            s_boil, T_boil = self._get_boiling_curve('4s', self.p_kessel)
            s_sh, T_sh = self._get_superheat_curve(self.p_kessel, self.T_max)
            s = [self.zustand['1']['s']/1000, self.zustand['2s']['s']/1000, self.zustand['3']['s']/1000, self.zustand['4s']['s']/1000] + s_boil + s_sh + [self.zustand['1']['s']/1000]
            T = [self.zustand['1']['T']-273.15, self.zustand['2s']['T']-273.15, self.zustand['3']['T']-273.15, self.zustand['4s']['T']-273.15] + T_boil + T_sh + [self.zustand['1']['T']-273.15]
        else:
            s_boil, T_boil = self._get_boiling_curve('6s', self.p_kessel)
            s_sh, T_sh = self._get_superheat_curve(self.p_kessel, self.T_max)
            
            h_start_rh = self.zustand['2s']['h']
            h_end_rh = self.zustand['3z']['h']
            h_arr_rh = np.linspace(h_start_rh, h_end_rh, 20)
            s_rh = [CP.PropsSI('S', 'P', self.p_zue, 'H', h, self.fluid) / 1000 for h in h_arr_rh]
            T_rh = [CP.PropsSI('T', 'P', self.p_zue, 'H', h, self.fluid) - 273.15 for h in h_arr_rh]
            
            s = [self.zustand['1']['s']/1000, self.zustand['2s']['s']/1000] + s_rh + [self.zustand['4s']['s']/1000, self.zustand['5']['s']/1000, self.zustand['6s']['s']/1000] + s_boil + s_sh + [self.zustand['1']['s']/1000]
            T = [self.zustand['1']['T']-273.15, self.zustand['2s']['T']-273.15] + T_rh + [self.zustand['4s']['T']-273.15, self.zustand['5']['T']-273.15, self.zustand['6s']['T']-273.15] + T_boil + T_sh + [self.zustand['1']['T']-273.15]
        return s, T

    def get_plot_daten_real(self):
        if not self.has_zue:
            s_boil, T_boil = self._get_boiling_curve('4', self.p_kessel)
            s_sh, T_sh = self._get_superheat_curve(self.p_kessel, self.T_max)
            s = [self.zustand['1']['s']/1000, self.zustand['2']['s']/1000, self.zustand['3']['s']/1000, self.zustand['4']['s']/1000] + s_boil + s_sh + [self.zustand['1']['s']/1000]
            T = [self.zustand['1']['T']-273.15, self.zustand['2']['T']-273.15, self.zustand['3']['T']-273.15, self.zustand['4']['T']-273.15] + T_boil + T_sh + [self.zustand['1']['T']-273.15]
        else:
            s_boil, T_boil = self._get_boiling_curve('6', self.p_kessel)
            s_sh, T_sh = self._get_superheat_curve(self.p_kessel, self.T_max)
            
            h_start_rh = self.zustand['2']['h']
            h_end_rh = self.zustand['3z']['h']
            h_arr_rh = np.linspace(h_start_rh, h_end_rh, 20)
            s_rh = [CP.PropsSI('S', 'P', self.p_zue, 'H', h, self.fluid) / 1000 for h in h_arr_rh]
            T_rh = [CP.PropsSI('T', 'P', self.p_zue, 'H', h, self.fluid) - 273.15 for h in h_arr_rh]
            
            s = [self.zustand['1']['s']/1000, self.zustand['2']['s']/1000] + s_rh + [self.zustand['4']['s']/1000, self.zustand['5']['s']/1000, self.zustand['6']['s']/1000] + s_boil + s_sh + [self.zustand['1']['s']/1000]
            T = [self.zustand['1']['T']-273.15, self.zustand['2']['T']-273.15] + T_rh + [self.zustand['4']['T']-273.15, self.zustand['5']['T']-273.15, self.zustand['6']['T']-273.15] + T_boil + T_sh + [self.zustand['1']['T']-273.15]
        return s, T

    def get_eckpunkte_daten(self):
        if not self.has_zue:
            keys = ['1', '2s', '2', '3', '4s', '4']
        else:
            keys = ['1', '2s', '2', '3z', '4s', '4', '5', '6s', '6']
            
        s = [self.zustand[k]['s']/1000 for k in keys]
        T = [self.zustand[k]['T']-273.15 for k in keys]
        hover = [
            f"<b>Punkt {k}</b><br>Druck p: {self.zustand[k]['p']/100000:.2f} bar<br>Temperatur T: {self.zustand[k]['T']-273.15:.2f} °C<br>Enthalpie h: {self.zustand[k]['h']/1000:.2f} kJ/kg<br>Entropie s: {self.zustand[k]['s']/1000:.4f} kJ/(kg K)"
            for k in keys
        ]
        return s, T, hover, keys

    def get_tabellen_daten(self):

        if not self.has_zue:
            keys = ['1', '2', '3', '4']
            labels = [
                "1 (Frischdampf Kessel)", 
                "2 (Austritt Turbine)", 
                "3 (Kondensataustritt)", 
                "4 (Austritt Pumpe)"
            ]
        else:
            keys = ['1', '2', '3z', '4', '5', '6']
            labels = [
                "1 (Frischdampf Kessel)", 
                "2 (Austritt HD-Turbine)", 
                "3z (Nach Zwischenüberhitzung)", 
                "4 (Austritt ND-Turbine)", 
                "5 (Kondensataustritt)", 
                "6 (Austritt Pumpe)"
            ]
            
        p = [f"{self.zustand[k]['p']/100000:.2f}" for k in keys]
        T = [f"{self.zustand[k]['T']-273.15:.2f}" for k in keys]
        h = [f"{self.zustand[k]['h']/1000:.2f}" for k in keys]
        s = [f"{self.zustand[k]['s']/1000:.4f}" for k in keys]
        
        return {'labels': labels, 'p': p, 'T': T, 'h': h, 's': s}
