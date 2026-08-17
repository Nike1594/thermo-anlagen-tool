import CoolProp.CoolProp as CP
import numpy as np


class KaelteKreisprozess:
    _reference_state_fluids = set()

    def __init__(self, fluid, T_0_C, T_c_C, T_m_C=None, dT_sh=0.0, dT_sc=0.0, eta_is_nd=1.0, eta_is_hd=1.0):
        self.fluid = fluid

        if fluid not in KaelteKreisprozess._reference_state_fluids:
            CP.set_reference_state(fluid, 'IIR')
            KaelteKreisprozess._reference_state_fluids.add(fluid)

        self._AS = CP.AbstractState("HEOS", fluid)

        self.T_0 = T_0_C + 273.15
        self.T_c = T_c_C + 273.15
        self.T_m = (T_m_C + 273.15) if T_m_C is not None else None

        self.dT_sh = dT_sh
        self.dT_sc = dT_sc
        self.eta_is_nd = eta_is_nd
        self.eta_is_hd = eta_is_hd

        self.zustand = {}
        self._mapping_cache = None

        self._AS.update(CP.QT_INPUTS, 1, self.T_0)
        self.p_0 = self._AS.p()

        self._AS.update(CP.QT_INPUTS, 0, self.T_c)
        self.p_c = self._AS.p()

        if self.T_m is not None:
            self._AS.update(CP.QT_INPUTS, 1, self.T_m)
            self.p_m = self._AS.p()

    def _safe_quality(self):
        try:
            return self._AS.Q()
        except Exception:
            return -1.0

    def berechne_einstufig(self):
        AS = self._AS

        # Punkt 1: Verdampferaustritt
        T1 = self.T_0 + self.dT_sh
        if self.dT_sh == 0:
            AS.update(CP.PQ_INPUTS, self.p_0, 1)
        else:
            AS.update(CP.PT_INPUTS, self.p_0, T1)
        h1, s1 = AS.hmass(), AS.smass()
        self.zustand['1'] = {'p': self.p_0, 'T': T1, 'h': h1, 's': s1}

        # Punkt 2s: isentrope Verdichtung
        AS.update(CP.PSmass_INPUTS, self.p_c, s1)
        h2s, T2s = AS.hmass(), AS.T()
        self.zustand['2s'] = {'p': self.p_c, 'T': T2s, 'h': h2s, 's': s1}

        # Punkt 2: reale Verdichtung
        h2 = h1 + (h2s - h1) / self.eta_is_nd
        AS.update(CP.HmassP_INPUTS, h2, self.p_c)
        T2, s2 = AS.T(), AS.smass()
        self.zustand['2'] = {'p': self.p_c, 'T': T2, 'h': h2, 's': s2}

        # Punkt 3: Kondensataustritt
        T3 = self.T_c - self.dT_sc
        if self.dT_sc == 0:
            AS.update(CP.PQ_INPUTS, self.p_c, 0)
        else:
            AS.update(CP.PT_INPUTS, self.p_c, T3)
        h3, s3 = AS.hmass(), AS.smass()
        self.zustand['3'] = {'p': self.p_c, 'T': T3, 'h': h3, 's': s3}

        # Punkt 4: nach Drossel (isenthalp)
        h4 = h3
        AS.update(CP.HmassP_INPUTS, h4, self.p_0)
        T4, s4 = AS.T(), AS.smass()
        x4 = self._safe_quality()
        self.zustand['4'] = {'p': self.p_0, 'T': T4, 'h': h4, 's': s4, 'x': x4}

        self.q_0 = (h1 - h4) / 1000
        self.w_c = (h2 - h1) / 1000
        self.cop = self.q_0 / self.w_c if self.w_c > 0 else 0

        for k in self.zustand:
            self.zustand[k]['mu'] = 1.0

    def berechne_zweistufig(self, has_mdf=True, mdf_mode="partiell", has_zk=False, T_2zk_C=None):
        AS = self._AS

        # HD-Seite (Kondensator & 1. Drossel)
        T5 = self.T_c - self.dT_sc
        if self.dT_sc == 0:
            AS.update(CP.PQ_INPUTS, self.p_c, 0)
        else:
            AS.update(CP.PT_INPUTS, self.p_c, T5)
        h5, s5 = AS.hmass(), AS.smass()
        self.zustand['5'] = {'p': self.p_c, 'T': T5, 'h': h5, 's': s5}

        h6 = h5
        T6 = self.T_m
        AS.update(CP.HmassP_INPUTS, h6, self.p_m)
        s6 = AS.smass()
        x6 = self._safe_quality()
        self.zustand['6'] = {'p': self.p_m, 'T': T6, 'h': h6, 's': s6, 'x': x6}

        if has_mdf:
            AS.update(CP.PQ_INPUTS, self.p_m, 1)
            h7, s7 = AS.hmass(), AS.smass()
            self.zustand['7'] = {'p': self.p_m, 'T': T6, 'h': h7, 's': s7, 'x': 1.0}

            AS.update(CP.PQ_INPUTS, self.p_m, 0)
            h8, s8 = AS.hmass(), AS.smass()
            self.zustand['8'] = {'p': self.p_m, 'T': T6, 'h': h8, 's': s8, 'x': 0.0}

            h9_eingang = h8
        else:
            h9_eingang = h6

        # ND-Seite (Verdampfer & ND-Verdichter)
        T9 = self.T_0
        AS.update(CP.HmassP_INPUTS, h9_eingang, self.p_0)
        s9 = AS.smass()
        x9 = self._safe_quality()
        self.zustand['9'] = {'p': self.p_0, 'T': T9, 'h': h9_eingang, 's': s9, 'x': x9}

        T1 = self.T_0 + self.dT_sh
        if self.dT_sh == 0:
            AS.update(CP.PQ_INPUTS, self.p_0, 1)
        else:
            AS.update(CP.PT_INPUTS, self.p_0, T1)
        h1, s1 = AS.hmass(), AS.smass()
        self.zustand['1'] = {'p': self.p_0, 'T': T1, 'h': h1, 's': s1}

        AS.update(CP.PSmass_INPUTS, self.p_m, s1)
        h2s, T2s = AS.hmass(), AS.T()

        h2 = h1 + (h2s - h1) / self.eta_is_nd
        AS.update(CP.HmassP_INPUTS, h2, self.p_m)
        T2, s2 = AS.T(), AS.smass()
        self.zustand['2'] = {'p': self.p_m, 'T': T2, 'h': h2, 's': s2}
        self.zustand['2s'] = {'p': self.p_m, 'T': T2s, 'h': h2s, 's': s1}

        # Zwischenkühlung(ZK)
        if has_zk:
            AS.update(CP.PQ_INPUTS, self.p_m, 1)
            T_sat_m = AS.T()
            if T_2zk_C is not None:
                T2zk = T_2zk_C + 273.15
                T2zk = min(T2zk, T2)
                if T2zk <= T_sat_m + 0.05:
                    AS.update(CP.PQ_INPUTS, self.p_m, 1)
                    h2zk, s2zk = AS.hmass(), AS.smass()
                    T2zk = T_sat_m
                else:
                    AS.update(CP.PT_INPUTS, self.p_m, T2zk)
                    h2zk, s2zk = AS.hmass(), AS.smass()
            else:
                AS.update(CP.PQ_INPUTS, self.p_m, 1)
                h2zk, s2zk = AS.hmass(), AS.smass()
                T2zk = T_sat_m

            self.zustand['2zk'] = {'p': self.p_m, 'T': T2zk, 'h': h2zk, 's': s2zk}
            h_vor_mischung = h2zk
        else:
            h_vor_mischung = h2

        # Massenstrombilanz
        self.m_hd = 1.0

        if has_mdf:
            if mdf_mode == "partiell":
                self.m_bypass = x6
                self.m_nd = self.m_hd - self.m_bypass
            else:
                denom = h_vor_mischung - h8
                if abs(denom) < 1e-6:
                    raise ValueError(
                        "Massenstromberechnung im Quench-Modus nicht möglich: die "
                        "Enthalpiedifferenz zwischen Sauggas und Sattflüssigkeit an der "
                        "Mitteldruckflasche ist (nahezu) null."
                    )
                self.m_nd = self.m_hd * (h7 - h6) / denom
                self.m_bypass = self.m_hd - self.m_nd
        else:
            self.m_nd = self.m_hd
            self.m_bypass = 0.0

        # Mischpunkt (vor HD-Verdichter)
        if has_mdf:
            if mdf_mode == "partiell":
                h3 = (self.m_nd * h_vor_mischung + self.m_bypass * self.zustand['7']['h']) / self.m_hd
            else:
                h3 = self.zustand['7']['h']
        else:
            h3 = h_vor_mischung

        AS.update(CP.HmassP_INPUTS, h3, self.p_m)
        T3, s3 = AS.T(), AS.smass()
        self.zustand['3'] = {'p': self.p_m, 'T': T3, 'h': h3, 's': s3}

        # HD-Verdichter
        AS.update(CP.PSmass_INPUTS, self.p_c, s3)
        h4s, T4s = AS.hmass(), AS.T()

        h4 = h3 + (h4s - h3) / self.eta_is_hd
        AS.update(CP.HmassP_INPUTS, h4, self.p_c)
        T4, s4 = AS.T(), AS.smass()
        self.zustand['4'] = {'p': self.p_c, 'T': T4, 'h': h4, 's': s4}
        self.zustand['4s'] = {'p': self.p_c, 'T': T4s, 'h': h4s, 's': s3}

        # Leistungskennzahlen
        self.q_0 = self.m_nd * (h1 - h9_eingang) / 1000
        self.w_nd = self.m_nd * (h2 - h1) / 1000
        self.w_hd = self.m_hd * (h4 - h3) / 1000
        self.w_c = self.w_nd + self.w_hd
        self.cop = self.q_0 / self.w_c if self.w_c > 0 else 0

        if has_zk:
            self.q_zk = self.m_nd * (h2 - h_vor_mischung) / 1000

        # Massenströme für die einzelnen Zustandspunkte
        for k in self.zustand:
            if k in ['3', '4', '4s', '5', '6']:
                self.zustand[k]['mu'] = self.m_hd
            elif k == '7':
                if mdf_mode == "partiell":
                    self.zustand[k]['mu'] = self.m_bypass
                else:
                    self.zustand[k]['mu'] = self.m_hd  
            else:
                self.zustand[k]['mu'] = self.m_nd

    def get_saettigungslinie(self):
        """Vektorisiert: 5 PropsSI-Aufrufe mit Array-Input statt 400 Einzelaufrufen."""
        t_krit = CP.PropsSI('Tcrit', self.fluid)
        t_min = max(CP.PropsSI('Tmin', self.fluid), 273.15 - 80)
        t_kurve = np.linspace(t_min + 1, t_krit - 0.5, 100)

        h_siedelinie = np.array(CP.PropsSI('H', 'T', t_kurve, 'Q', 0, self.fluid)) / 1000
        h_taulinie = np.array(CP.PropsSI('H', 'T', t_kurve, 'Q', 1, self.fluid)) / 1000
        s_siedelinie = np.array(CP.PropsSI('S', 'T', t_kurve, 'Q', 0, self.fluid)) / 1000
        s_taulinie = np.array(CP.PropsSI('S', 'T', t_kurve, 'Q', 1, self.fluid)) / 1000
        p_kurve = np.array(CP.PropsSI('P', 'T', t_kurve, 'Q', 0, self.fluid)) / 100000

        h_g = np.concatenate([h_siedelinie, h_taulinie[::-1]]).tolist()
        s_g = np.concatenate([s_siedelinie, s_taulinie[::-1]]).tolist()
        T_g = np.concatenate([t_kurve - 273.15, t_kurve[::-1] - 273.15]).tolist()
        p_g = np.concatenate([p_kurve, p_kurve[::-1]]).tolist()

        return h_g, s_g, T_g, p_g

    def _get_point_mapping(self):
        if self._mapping_cache is None:
            self._mapping_cache = self._compute_point_mapping()
        return self._mapping_cache

    def _compute_point_mapping(self):
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

            is_partiell = self.zustand['7']['mu'] < 0.999
            if is_partiell:
                display_keys.append('3')
                labels.append(f'{pt} (Mischpunkt HD-Saug)')
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
                # np.nan zwingt Plotly garantiert dazu, die Linie hier abzusetzen!
                h.append(np.nan)
                s.append(np.nan)
                T.append(np.nan)
                p.append(np.nan)
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
