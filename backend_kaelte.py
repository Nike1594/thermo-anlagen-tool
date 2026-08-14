import CoolProp.CoolProp as CP
import numpy as np

class KaelteKreisprozess:
    """
    Berechnet die Zustandsgrößen für Kompressionskälteanlagen.
    Aktuell implementiert: Einstufig & Zweistufig (dynamisch mit MDF partiell/vollständig und ZK)
    """
    def __init__(self, fluid, T_0_C, T_c_C, T_m_C=None, dT_sh=0.0, dT_sc=0.0, eta_is_nd=1.0, eta_is_hd=1.0):
        self.fluid = fluid
        CP.set_reference_state(self.fluid, 'IIR') 
        
        self.T_0 = T_0_C + 273.15
        self.T_c = T_c_C + 273.15
        self.T_m = (T_m_C + 273.15) if T_m_C else None
        
        self.dT_sh = dT_sh
        self.dT_sc = dT_sc
        self.eta_is_nd = eta_is_nd
        self.eta_is_hd = eta_is_hd
        
        self.zustand = {}
        
        self.p_0 = CP.PropsSI('P', 'T', self.T_0, 'Q', 1, self.fluid)
        self.p_c = CP.PropsSI('P', 'T', self.T_c, 'Q', 0, self.fluid)
        if self.T_m:
            self.p_m = CP.PropsSI('P', 'T', self.T_m, 'Q', 1, self.fluid)
            
    def berechne_einstufig(self):
        fluid = self.fluid
        
        T1 = self.T_0 + self.dT_sh
        if self.dT_sh == 0:
            h1 = CP.PropsSI('H', 'P', self.p_0, 'Q', 1, fluid)
            s1 = CP.PropsSI('S', 'P', self.p_0, 'Q', 1, fluid)
        else:
            h1 = CP.PropsSI('H', 'P', self.p_0, 'T', T1, fluid)
            s1 = CP.PropsSI('S', 'P', self.p_0, 'T', T1, fluid)
            
        self.zustand['1'] = {'p': self.p_0, 'T': T1, 'h': h1, 's': s1}
        
        h2s = CP.PropsSI('H', 'P', self.p_c, 'S', s1, fluid)
        T2s = CP.PropsSI('T', 'P', self.p_c, 'H', h2s, fluid)
        self.zustand['2s'] = {'p': self.p_c, 'T': T2s, 'h': h2s, 's': s1}
        
        h2 = h1 + (h2s - h1) / self.eta_is_nd
        T2 = CP.PropsSI('T', 'P', self.p_c, 'H', h2, fluid)
        s2 = CP.PropsSI('S', 'P', self.p_c, 'H', h2, fluid)
        self.zustand['2'] = {'p': self.p_c, 'T': T2, 'h': h2, 's': s2}
        
        T3 = self.T_c - self.dT_sc
        if self.dT_sc == 0:
            h3 = CP.PropsSI('H', 'P', self.p_c, 'Q', 0, fluid)
            s3 = CP.PropsSI('S', 'P', self.p_c, 'Q', 0, fluid)
        else:
            h3 = CP.PropsSI('H', 'P', self.p_c, 'T', T3, fluid)
            s3 = CP.PropsSI('S', 'P', self.p_c, 'T', T3, fluid)
            
        self.zustand['3'] = {'p': self.p_c, 'T': T3, 'h': h3, 's': s3}
        
        h4 = h3
        T4 = CP.PropsSI('T', 'P', self.p_0, 'H', h4, fluid)
        s4 = CP.PropsSI('S', 'P', self.p_0, 'H', h4, fluid)
        x4 = CP.PropsSI('Q', 'P', self.p_0, 'H', h4, fluid)
        self.zustand['4'] = {'p': self.p_0, 'T': T4, 'h': h4, 's': s4, 'x': x4}
        
        self.q_0 = (h1 - h4) / 1000 
        self.w_c = (h2 - h1) / 1000 
        self.cop = self.q_0 / self.w_c if self.w_c > 0 else 0
        
        for k in self.zustand:
            self.zustand[k]['mu'] = 1.0

    def berechne_zweistufig(self, has_mdf=True, mdf_mode="partiell", has_zk=False, T_2zk_C=None):
        fluid = self.fluid

        # --- HD-Seite (Kondensator & 1. Drossel) ---
        T5 = self.T_c - self.dT_sc
        if self.dT_sc == 0:
            h5 = CP.PropsSI('H', 'P', self.p_c, 'Q', 0, fluid)
            s5 = CP.PropsSI('S', 'P', self.p_c, 'Q', 0, fluid)
        else:
            h5 = CP.PropsSI('H', 'P', self.p_c, 'T', T5, fluid)
            s5 = CP.PropsSI('S', 'P', self.p_c, 'T', T5, fluid)
        self.zustand['5'] = {'p': self.p_c, 'T': T5, 'h': h5, 's': s5}

        h6 = h5
        T6 = self.T_m
        s6 = CP.PropsSI('S', 'P', self.p_m, 'H', h6, fluid)
        x6 = CP.PropsSI('Q', 'P', self.p_m, 'H', h6, fluid)
        self.zustand['6'] = {'p': self.p_m, 'T': T6, 'h': h6, 's': s6, 'x': x6}

        if has_mdf:
            h7 = CP.PropsSI('H', 'P', self.p_m, 'Q', 1, fluid)
            s7 = CP.PropsSI('S', 'P', self.p_m, 'Q', 1, fluid)
            self.zustand['7'] = {'p': self.p_m, 'T': T6, 'h': h7, 's': s7, 'x': 1.0}

            h8 = CP.PropsSI('H', 'P', self.p_m, 'Q', 0, fluid)
            s8 = CP.PropsSI('S', 'P', self.p_m, 'Q', 0, fluid)
            self.zustand['8'] = {'p': self.p_m, 'T': T6, 'h': h8, 's': s8, 'x': 0.0}
            
            h9_eingang = h8
        else:
            h9_eingang = h6

        # --- ND-Seite (Verdampfer & ND-Verdichter) ---
        T9 = self.T_0
        s9 = CP.PropsSI('S', 'P', self.p_0, 'H', h9_eingang, fluid)
        x9 = CP.PropsSI('Q', 'P', self.p_0, 'H', h9_eingang, fluid)
        self.zustand['9'] = {'p': self.p_0, 'T': T9, 'h': h9_eingang, 's': s9, 'x': x9}

        T1 = self.T_0 + self.dT_sh
        if self.dT_sh == 0:
            h1 = CP.PropsSI('H', 'P', self.p_0, 'Q', 1, fluid)
            s1 = CP.PropsSI('S', 'P', self.p_0, 'Q', 1, fluid)
        else:
            h1 = CP.PropsSI('H', 'P', self.p_0, 'T', T1, fluid)
            s1 = CP.PropsSI('S', 'P', self.p_0, 'T', T1, fluid)
        self.zustand['1'] = {'p': self.p_0, 'T': T1, 'h': h1, 's': s1}

        h2s = CP.PropsSI('H', 'P', self.p_m, 'S', s1, fluid)
        h2 = h1 + (h2s - h1) / self.eta_is_nd
        T2 = CP.PropsSI('T', 'P', self.p_m, 'H', h2, fluid)
        s2 = CP.PropsSI('S', 'P', self.p_m, 'H', h2, fluid)
        self.zustand['2'] = {'p': self.p_m, 'T': T2, 'h': h2, 's': s2}
        self.zustand['2s'] = {'p': self.p_m, 'T': CP.PropsSI('T', 'P', self.p_m, 'H', h2s, fluid), 'h': h2s, 's': s1}

        # --- ZWISCHENKÜHLUNG (ZK) ---
        if has_zk:
            T_sat_m = CP.PropsSI('T', 'P', self.p_m, 'Q', 1, fluid)
            if T_2zk_C is not None:
                T2zk = T_2zk_C + 273.15
                T2zk = min(T2zk, T2)
                if T2zk <= T_sat_m + 0.05:
                    h2zk = CP.PropsSI('H', 'P', self.p_m, 'Q', 1, fluid)
                    s2zk = CP.PropsSI('S', 'P', self.p_m, 'Q', 1, fluid)
                    T2zk = T_sat_m
                else:
                    h2zk = CP.PropsSI('H', 'P', self.p_m, 'T', T2zk, fluid)
                    s2zk = CP.PropsSI('S', 'P', self.p_m, 'T', T2zk, fluid)
            else:
                h2zk = CP.PropsSI('H', 'P', self.p_m, 'Q', 1, fluid)
                s2zk = CP.PropsSI('S', 'P', self.p_m, 'Q', 1, fluid)
                T2zk = T_sat_m
                
            self.zustand['2zk'] = {'p': self.p_m, 'T': T2zk, 'h': h2zk, 's': s2zk}
            h_vor_mischung = h2zk
        else:
            h_vor_mischung = h2

        # --- Massenstrombilanzen berechnen ---
        self.m_hd = 1.0  

        if has_mdf:
            if mdf_mode == "partiell":
                self.m_bypass = x6
                self.m_nd = self.m_hd - self.m_bypass
            else:
                self.m_nd = self.m_hd * (h7 - h6) / (h_vor_mischung - h8)
                self.m_bypass = self.m_hd - self.m_nd 
        else:
            self.m_nd = self.m_hd
            self.m_bypass = 0.0

        # --- Mischpunkt (Vor HD-Verdichter) ---
        if has_mdf:
            if mdf_mode == "partiell":
                h3 = (self.m_nd * h_vor_mischung + self.m_bypass * self.zustand['7']['h']) / self.m_hd
            else:
                h3 = self.zustand['7']['h'] 
        else:
            h3 = h_vor_mischung
            
        T3 = CP.PropsSI('T', 'P', self.p_m, 'H', h3, fluid)
        s3 = CP.PropsSI('S', 'P', self.p_m, 'H', h3, fluid)
        self.zustand['3'] = {'p': self.p_m, 'T': T3, 'h': h3, 's': s3}

        # --- HD-Verdichter ---
        h4s = CP.PropsSI('H', 'P', self.p_c, 'S', s3, fluid)
        h4 = h3 + (h4s - h3) / self.eta_is_hd
        T4 = CP.PropsSI('T', 'P', self.p_c, 'H', h4, fluid)
        s4 = CP.PropsSI('S', 'P', self.p_c, 'H', h4, fluid)
        self.zustand['4'] = {'p': self.p_c, 'T': T4, 'h': h4, 's': s4}
        self.zustand['4s'] = {'p': self.p_c, 'T': CP.PropsSI('T', 'P', self.p_c, 'H', h4s, fluid), 'h': h4s, 's': s3}

        # --- Leistungskennzahlen ---
        self.q_0 = self.m_nd * (h1 - h9_eingang) / 1000 
        self.w_nd = self.m_nd * (h2 - h1) / 1000
        self.w_hd = self.m_hd * (h4 - h3) / 1000
        self.w_c = self.w_nd + self.w_hd
        self.cop = self.q_0 / self.w_c if self.w_c > 0 else 0
        
        if has_zk:
            self.q_zk = self.m_nd * (h2 - h_vor_mischung) / 1000
            
        # Zuweisung der Massenströme für die einzelnen Zustandspunkte
        for k in self.zustand:
            if k in ['3', '4', '4s', '5', '6']:
                self.zustand[k]['mu'] = self.m_hd
            elif k == '7':
                if mdf_mode == "partiell":
                    self.zustand[k]['mu'] = self.m_bypass
                else:
                    self.zustand[k]['mu'] = self.m_hd  # Beim Quenchen geht alles durch Punkt 7
            else: # 8, 9, 1, 2, 2s, 2zk
                self.zustand[k]['mu'] = self.m_nd

    def get_saettigungslinie(self):
        t_krit = CP.PropsSI('Tcrit', self.fluid)
        t_min = max(CP.PropsSI('Tmin', self.fluid), 273.15 - 80) 
        t_kurve = np.linspace(t_min + 1, t_krit - 0.5, 100)
        
        h_siedelinie = [CP.PropsSI('H', 'T', t, 'Q', 0, self.fluid) / 1000 for t in t_kurve]
        h_taulinie = [CP.PropsSI('H', 'T', t, 'Q', 1, self.fluid) / 1000 for t in t_kurve]
        
        s_siedelinie = [CP.PropsSI('S', 'T', t, 'Q', 0, self.fluid) / 1000 for t in t_kurve]
        s_taulinie = [CP.PropsSI('S', 'T', t, 'Q', 1, self.fluid) / 1000 for t in t_kurve]
        
        p_kurve = [CP.PropsSI('P', 'T', t, 'Q', 0, self.fluid) / 100000 for t in t_kurve]
        
        h_g = h_siedelinie + h_taulinie[::-1]
        s_g = s_siedelinie + s_taulinie[::-1]
        T_g = [t - 273.15 for t in t_kurve] + [t - 273.15 for t in t_kurve[::-1]]
        p_g = p_kurve + p_kurve[::-1]
        
        return h_g, s_g, T_g, p_g

    def _get_point_mapping(self):
        has_2stage = '5' in self.zustand
        has_mdf = '7' in self.zustand
        has_zk = '2zk' in self.zustand
        
        display_keys, labels, short_labels, plot_real, plot_ideal = [], [], [], [], []
        
        if not has_2stage:
            display_keys = ['1', '2s', '2', '3', '4']
            labels = ['1 (Sauggas)', '2<sub>s</sub> (Ideal verdichtet)', '2 (Real verdichtet)', '3 (Kondensataustritt)', '4 (Nach Drossel)']
            short_labels = ['1', '2<sub>s</sub>', '2', '3', '4']
            plot_real = ['1', '2', '3', '4', '1']
            plot_ideal = ['1', '2s', '3', '4', '1']
            
        elif has_2stage and not has_mdf:
            pt = 1
            display_keys.extend(['1', '2s', '2'])
            labels.extend([f'{pt} (ND-Sauggas)', f'{pt+1}<sub>s</sub> (ND ideal)', f'{pt+1} (ND real)'])
            short_labels.extend([f'{pt}', f'{pt+1}<sub>s</sub>', f'{pt+1}'])
            pt += 2
            
            plot_real = ['1', '2']
            plot_ideal = ['1', '2s']
            
            if has_zk:
                display_keys.append('2zk')
                labels.append(f'{pt}<sub>zk</sub> (Nach ZK)')
                short_labels.append(f'{pt}<sub>zk</sub>')
                plot_real.append('2zk')
                plot_ideal.append('2zk')
                pt += 1
            
            display_keys.extend(['4s', '4', '5', '9'])
            labels.extend([f'{pt}<sub>s</sub> (HD ideal)', f'{pt} (HD real)', f'{pt+1} (Kond.austritt)', f'{pt+2} (Nach Drossel)'])
            short_labels.extend([f'{pt}<sub>s</sub>', f'{pt}', f'{pt+1}', f'{pt+2}'])
            
            plot_real.extend(['3', '4', '5', '9', '1'])
            plot_ideal.extend(['3', '4s', '5', '9', '1'])
            
        elif has_2stage and has_mdf:
            pt = 1
            display_keys.extend(['1', '2s', '2'])
            labels.extend([f'{pt} (ND-Sauggas)', f'{pt+1}<sub>s</sub> (ND ideal)', f'{pt+1} (ND real)'])
            short_labels.extend([f'{pt}', f'{pt+1}<sub>s</sub>', f'{pt+1}'])
            pt += 2
            
            plot_real = ['1', '2']
            plot_ideal = ['1', '2s']
            
            if has_zk:
                display_keys.append('2zk')
                labels.append(f'{pt}<sub>zk</sub> (Nach ZK)')
                short_labels.append(f'{pt}<sub>zk</sub>')
                plot_real.append('2zk')
                plot_ideal.append('2zk')
                pt += 1
                
            display_keys.append('7')
            labels.append(f'{pt} (MDF Gas)')
            short_labels.append(f'{pt}')
            pt += 1
            
            display_keys.extend(['4s', '4'])
            labels.extend([f'{pt}<sub>s</sub> (HD ideal)', f'{pt} (HD real)'])
            short_labels.extend([f'{pt}<sub>s</sub>', f'{pt}'])
            pt += 1
            
            display_keys.extend(['5', '6', '8', '9'])
            labels.extend([
                f'{pt} (Kond.austritt)', 
                f'{pt+1} (Nach 1. Drossel)', 
                f'{pt+2} (MDF Flüssig)', 
                f'{pt+3} (Nach 2. Drossel)'
            ])
            short_labels.extend([f'{pt}', f'{pt+1}', f'{pt+2}', f'{pt+3}'])
            
            plot_real.extend(['3', '4', '5', '6', None, '8', '9', '1', None, '8', '7', '3', None])
            plot_ideal.extend(['3', '4s', '5', '6', None, '8', '9', '1', None, '8', '7', '3', None])
            
        return display_keys, labels, short_labels, plot_real, plot_ideal

    def get_plot_linien_ideal(self):
        _, _, _, _, plot_ideal = self._get_point_mapping()
        return self._extract_arrays(plot_ideal)

    def get_plot_linien_real(self):
        _, _, _, plot_real, _ = self._get_point_mapping()
        return self._extract_arrays(plot_real)

    def _extract_arrays(self, keys):
        h, s, T, p = [], [], [], []
        for k in keys:
            if k is None:
                h.append(None); s.append(None); T.append(None); p.append(None)
            else:
                h.append(self.zustand[k]['h']/1000)
                s.append(self.zustand[k]['s']/1000)
                T.append(self.zustand[k]['T']-273.15)
                p.append(self.zustand[k]['p']/100000)
        return h, s, T, p

    def get_eckpunkte_daten(self):
        display_keys, labels, short_labels, _, _ = self._get_point_mapping()
        h, s, T, p = self._extract_arrays(display_keys)
        
        hover_texte = []
        for label, k in zip(labels, display_keys):
            daten = self.zustand[k]
            text = (f"<b>Punkt {label}</b><br>"
                    f"Druck <i>p</i>: {daten['p']/100000:.2f} bar<br>"
                    f"Temperatur <i>T</i>: {daten['T']-273.15:.2f} °C<br>"
                    f"Enthalpie <i>h</i>: {daten['h']/1000:.2f} kJ/kg<br>"
                    f"Entropie <i>s</i>: {daten['s']/1000:.4f} kJ/(kg K)<br>")
            if 'x' in daten and daten['x'] >= 0 and daten['x'] <= 1:
                text += f"Dampfgehalt <i>x</i>: {daten['x']:.3f}<br>"
            if 'mu' in daten and '7' in self.zustand:
                text += f"Massenanteil <i>μ</i>: {daten['mu']:.3f}"
                
            hover_texte.append(text)
            
        return h, s, T, p, hover_texte, short_labels

    def get_tabellen_daten(self):
        display_keys, labels, _, _, _ = self._get_point_mapping()
        p_vals = [f"{self.zustand[k]['p']/100000:.2f}" for k in display_keys]
        T_vals = [f"{self.zustand[k]['T']-273.15:.2f}" for k in display_keys]
        h_vals = [f"{self.zustand[k]['h']/1000:.2f}" for k in display_keys]
        s_vals = [f"{self.zustand[k]['s']/1000:.4f}" for k in display_keys]
        
        if '7' in self.zustand:
            mu_vals = [f"{self.zustand[k].get('mu', 1.0):.3f}" for k in display_keys]
            return {'labels': labels, 'p': p_vals, 'T': T_vals, 'h': h_vals, 's': s_vals, 'mu': mu_vals}
            
        return {'labels': labels, 'p': p_vals, 'T': T_vals, 'h': h_vals, 's': s_vals}