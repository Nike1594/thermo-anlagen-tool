import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import CoolProp.CoolProp as CP
import re
from backend_rankine import ClausiusRankineProzess 
from backend_kaelte import KaelteKreisprozess

st.set_page_config(page_title="Thermische Anlagen", layout="wide")

st.markdown("""
<style>
[data-testid="stMetricLabel"] div {
    font-size: 1.15rem !important;
    font-weight: 600 !important;
}
[data-testid="stMetricValue"] {
    font-size: 2.5rem !important; 
    font-weight: 700 !important;
}
</style>
""", unsafe_allow_html=True)


def apply_theme_to_svg(svg_str, *args, **kwargs):
    if "<svg" in svg_str:
        svg_str = svg_str[svg_str.index("<svg"):]
        
    svg_str = re.sub(r'<rect[^>]*width="100%"[^>]*height="100%"[^>]*>', '', svg_str, flags=re.IGNORECASE)
        
    svg_str = re.sub(r'stroke="(?!none|transparent|var)[^"]+"', 'stroke="var(--text-color)"', svg_str, flags=re.IGNORECASE)

    svg_str = re.sub(r'color:\s*(?!none|transparent|var)[^;"]+;?', 'color: var(--text-color);', svg_str, flags=re.IGNORECASE)
    svg_str = re.sub(r'(<text[^>]*?)fill="(?!none|transparent|var)[^"]+"', r'\1fill="var(--text-color)"', svg_str, flags=re.IGNORECASE)
    svg_str = re.sub(r'(<font[^>]*?)color="(?!none|transparent|var)[^"]+"', r'\1color="var(--text-color)"', svg_str, flags=re.IGNORECASE)
    
    color_pattern = r'(#[0-9a-fA-F]{3,8}|rgb\([^)]+\)|rgba\([^)]+\)|white|black)'
    svg_str = re.sub(r'fill="' + color_pattern + r'"', 'fill="var(--background-color)"', svg_str, flags=re.IGNORECASE)

    svg_str = re.sub(r'background-color:\s*[^;"]+;?', 'background-color: transparent;', svg_str, flags=re.IGNORECASE)
    svg_str = svg_str.replace('color-scheme: light dark;', '')
    
    return svg_str

theme_type = "auto"

def ensure_default(key, value):
    """Initialisiert Slider/Number-Input-Paar im Session State, falls noch nicht vorhanden."""
    if f"{key}_slider" not in st.session_state:
        st.session_state[f"{key}_slider"] = value
        st.session_state[f"{key}_input"] = value


initial_values = {
    # Clausius-Rankine-Prozess
    "cr_p1": 0.05,       # Kondensatordruck (bar)
    "cr_p2": 100.0,      # Kesseldruck (bar)
    "cr_T3": 450.0,      # Frischdampftemperatur (°C)
    "cr_m_dot": 10.0,    # Massenstrom (kg/s)
    "cr_eta_s_P": 80.0,  # Isentroper Wirkungsgrad Pumpe (%)
    "cr_eta_s_T": 85.0,  # Isentroper Wirkungsgrad Turbine (%)
    # Joule-Prozess
    "j_T1": 21.0,
    "j_p1": 1.03,
    "j_T3": 1010.0,
    "j_pi": 6.9,
    "j_m_dot": 1.12,
}

for key, val in initial_values.items():
    ensure_default(key, val)

def sync_values(changed_key, target_key):
    st.session_state[target_key] = st.session_state[changed_key]

def create_synced_input(label, key, min_val, max_val, step, format="%.2f", help_text=None):
    st.sidebar.markdown(f"**{label}**")
    col1, col2 = st.sidebar.columns([3, 2])
    with col1:
        st.slider(
            label, min_value=min_val, max_value=max_val, step=step,
            key=f"{key}_slider", 
            on_change=sync_values, args=(f"{key}_slider", f"{key}_input"), 
            label_visibility="collapsed",
            help=help_text
        )
    with col2:
        st.number_input(
            label, min_value=min_val, max_value=max_val, step=step, format=format,
            key=f"{key}_input", 
            on_change=sync_values, args=(f"{key}_input", f"{key}_slider"), 
            label_visibility="collapsed",
            help=help_text
        )
    st.sidebar.write("")

@st.cache_data
def get_filtered_fluids():
    fluid_mapping = {}
    for f in CP.FluidsList():
        if re.match(r'^R\d+', f):
            fluid_mapping[f] = f
        elif f.lower() == "carbondioxide":
            fluid_mapping["CO2 (R744)"] = f
        elif f.lower() in ["propane", "n-propane"]:
            fluid_mapping["Propan (R290)"] = f
        elif f.lower() == "ammonia":
            fluid_mapping["Ammoniak (R717)"] = f
            
    return dict(sorted(fluid_mapping.items()))

@st.cache_data
def get_orc_fluids():
    """Definiert typische Fluide für Dampfkraftwerke und ORC-Prozesse."""
    orc_fluids = {
        "Wasser (Standard)": "Water",
        "Ammoniak": "Ammonia",
        "Propan (R290)": "Propane",
        "n-Butan": "n-Butane",
        "Isobutan (R600a)": "IsoButane",
        "n-Pentan": "n-Pentane",
        "Isopentan": "Isopentane",
        "Ethanol": "Ethanol",
        "Toluol": "Toluene",
        "R134a": "R134a",
        "R245fa": "R245fa",
        "R1234yf": "R1234yf"
    }
    all_cp_fluids = CP.FluidsList()
    return {k: v for k, v in orc_fluids.items() if v in all_cp_fluids}

@st.cache_data(show_spinner=False)
def berechne_zue_feld(fluid, p_kond, p_verd, T_max, m_dot, eta_s_P, eta_s_T, ignore_pump):
    p_zue_arr = np.linspace(max(1.0, p_kond * 2), p_verd * 0.9, 80)
    T_zue_arr = np.linspace(200.0, T_max, 80)
    eta_grid = np.zeros((len(T_zue_arr), len(p_zue_arr)))
    n_failed = 0

    for i, T_z in enumerate(T_zue_arr):
        for j, p_z in enumerate(p_zue_arr):
            temp_prozess = ClausiusRankineProzess(
                fluid=fluid,
                p_kond=p_kond, p_kessel=p_verd, T_max=T_max, m_dot=m_dot,
                eta_s_P=eta_s_P, eta_s_T=eta_s_T, ignore_pump=ignore_pump,
                has_zue=True, p_zue=p_z, T_zue=T_z
            )
            try:
                temp_prozess.berechne_zustaende()
                h2 = temp_prozess.zustand['2']['h']
                T2_C = CP.PropsSI('T', 'P', p_z * 100000, 'H', h2, temp_prozess.fluid) - 273.15

                if T_z <= T2_C:
                    eta_grid[i, j] = None
                    continue

                h4 = temp_prozess.zustand['4']['h']
                p_kond_pa = temp_prozess.p_kond
                hf = CP.PropsSI('H', 'P', p_kond_pa, 'Q', 0, temp_prozess.fluid)
                hg = CP.PropsSI('H', 'P', p_kond_pa, 'Q', 1, temp_prozess.fluid)
                x4 = (h4 - hf) / (hg - hf)

                if x4 < 0.88:
                    eta_grid[i, j] = None
                else:
                    eta_grid[i, j] = temp_prozess.wirkungsgrad * 100
            except Exception:
                eta_grid[i, j] = None
                n_failed += 1

    return eta_grid, p_zue_arr, T_zue_arr, n_failed

@st.cache_data(show_spinner=False)
def berechne_effizienzfelder(fluid, is_2stage, has_mdf, mdf_mode_key, has_zk, T_zk_input, eta_is_nd, eta_is_hd,
                             has_sh, sh_mode, dT_sh_input, T_sh_input,
                             has_sc, sc_mode, dT_sc_input, T_sc_input):
    T_verd_arr = np.linspace(-75.0, 20.0, 60)
    T_kond_arr = np.linspace(25.0, 75.0, 60)

    cop_heiz_grid = np.zeros((len(T_kond_arr), len(T_verd_arr)))
    eer_kalt_grid = np.zeros((len(T_kond_arr), len(T_verd_arr)))
    n_failed = 0

    for i, T_k in enumerate(T_kond_arr):
        for j, T_v in enumerate(T_verd_arr):

            if T_v >= T_k:
                cop_heiz_grid[i, j] = None
                eer_kalt_grid[i, j] = None
                continue

            dT_sh_local = 0.0
            if has_sh:
                if sh_mode == "um (ΔT)":
                    dT_sh_local = dT_sh_input
                else:
                    dT_sh_local = T_sh_input - T_v
                    if dT_sh_local < 0: dT_sh_local = 0.0

            dT_sc_local = 0.0
            if has_sc:
                if sc_mode == "um (ΔT)":
                    dT_sc_local = dT_sc_input
                else:
                    dT_sc_local = T_k - T_sc_input
                    if dT_sc_local < 0: dT_sc_local = 0.0

            try:
                if is_2stage:
                    p_0_temp = CP.PropsSI('P', 'T', T_v + 273.15, 'Q', 1, fluid)
                    p_c_temp = CP.PropsSI('P', 'T', T_k + 273.15, 'Q', 0, fluid)
                    p_m_opt = np.sqrt(p_0_temp * p_c_temp)
                    T_m_opt_C = CP.PropsSI('T', 'P', p_m_opt, 'Q', 1, fluid) - 273.15
                else:
                    T_m_opt_C = None

                temp_prozess = KaelteKreisprozess(
                    fluid=fluid, T_0_C=T_v, T_c_C=T_k, T_m_C=T_m_opt_C,
                    dT_sh=dT_sh_local, dT_sc=dT_sc_local,
                    eta_is_nd=eta_is_nd, eta_is_hd=eta_is_hd
                )

                if is_2stage:
                    temp_prozess.berechne_zweistufig(
                        has_mdf=has_mdf, mdf_mode=mdf_mode_key,
                        has_zk=has_zk, T_2zk_C=T_zk_input
                    )
                    T_heissgas_ND_C = temp_prozess.zustand['2']['T'] - 273.15
                    T_heissgas_HD_C = temp_prozess.zustand['4']['T'] - 273.15
                    T_heissgas_max = max(T_heissgas_ND_C, T_heissgas_HD_C)
                else:
                    temp_prozess.berechne_einstufig()
                    T_heissgas_max = temp_prozess.zustand['2']['T'] - 273.15

                if T_heissgas_max > 120.0:
                    cop_heiz_grid[i, j] = None
                    eer_kalt_grid[i, j] = None
                else:
                    eer_kalt_grid[i, j] = temp_prozess.cop
                    cop_heiz_grid[i, j] = temp_prozess.cop + 1.0
            except Exception:
                cop_heiz_grid[i, j] = None
                eer_kalt_grid[i, j] = None
                n_failed += 1

    return cop_heiz_grid, eer_kalt_grid, T_verd_arr, T_kond_arr, n_failed

# Sidebar

st.sidebar.title("Thermische Anlagen")
prozess_auswahl = st.sidebar.radio(
    "Wähle den Kreisprozess:", 
    [
        "Clausius-Rankine-Prozess", 
        "Joule-Prozess (Gasturbine)", 
        "Kälteanlage (Kompressionskältemaschine)"
    ]
)

st.sidebar.divider()

def get_orc_bounds(fluid_display):
    if "Wasser" in fluid_display:
        return {"p1": (0.01, 2.0, 0.05), "p2": (2.0, 300.0, 100.0), "T3": (100.0, 650.0, 450.0)}
    elif "Ammoniak" in fluid_display or "Propan" in fluid_display or "CO2" in fluid_display:
        return {"p1": (1.0, 50.0, 10.0), "p2": (10.0, 150.0, 50.0), "T3": (50.0, 300.0, 150.0)}
    elif "Butan" in fluid_display or "Pentan" in fluid_display or "R1" in fluid_display or "R2" in fluid_display:
        return {"p1": (0.1, 25.0, 2.0), "p2": (2.0, 80.0, 20.0), "T3": (40.0, 250.0, 120.0)}
    else:
        return {"p1": (0.02, 10.0, 0.5), "p2": (2.0, 100.0, 20.0), "T3": (80.0, 400.0, 250.0)}

# 2. Clausius-Rankine-Prozess
if prozess_auswahl == "Clausius-Rankine-Prozess":
    st.title("Clausius-Rankine-Prozess (bzw. ORC)")
    st.write("Vergleich: Idealer (reversibler) vs. Realer (irreversibler) Kreisprozess.")
    
    st.sidebar.header("Anlagenkonfiguration")
    
    orc_mapping = get_orc_fluids()
    
    if "last_cr_fluid" not in st.session_state:
        st.session_state["last_cr_fluid"] = list(orc_mapping.keys())[0]

    selected_orc_display = st.sidebar.selectbox(
        "Arbeitsfluid", 
        list(orc_mapping.keys()), 
        index=list(orc_mapping.keys()).index(st.session_state["last_cr_fluid"]),
        help="Wähle das Arbeitsmedium. ORC-Fluide (Kältemittel, Kohlenwasserstoffe) eignen sich zur Nutzung von Niedertemperatur-Abwärme."
    )
    cr_fluid = orc_mapping[selected_orc_display]
    
    bounds = get_orc_bounds(selected_orc_display)

    if selected_orc_display != st.session_state["last_cr_fluid"]:
        st.session_state["last_cr_fluid"] = selected_orc_display
        st.session_state["cr_p1_slider"] = bounds["p1"][2]
        st.session_state["cr_p1_input"] = bounds["p1"][2]
        st.session_state["cr_p2_slider"] = bounds["p2"][2]
        st.session_state["cr_p2_input"] = bounds["p2"][2]
        st.session_state["cr_T3_slider"] = bounds["T3"][2]
        st.session_state["cr_T3_input"] = bounds["T3"][2]
        st.rerun() 

    st.sidebar.divider()
    
    ignore_pump = st.sidebar.checkbox(
        "Vernachlässigung der Pumpenarbeit", value=False, 
        help="Setzt die Enthalpieänderung der Pumpe auf 0. Oft in theoretischen Aufgaben verwendet, da die Pumpenarbeit von Flüssigkeiten im Vergleich zur Turbinenarbeit sehr gering ist."
    )
    has_zue = st.sidebar.checkbox(
        "Zwischenüberhitzung (ZÜ)", value=False,
        help="Führt das Gas nach teilweiser Entspannung zurück in den Kessel. Steigert den Wirkungsgrad und verschiebt den Turbinenaustritt ins Trockene (vermeidet Tropfenschlag)."
    )
    
    st.sidebar.divider()
    
    st.sidebar.header("Zustandsgrößen")
    create_synced_input(
        "Kondensatordruck $p_{kond}$ (bar)", "cr_p1", bounds["p1"][0], bounds["p1"][1], bounds["p1"][0]*2,
        help_text="**Kondensatordruck**\n\nBestimmt das untere Temperaturniveau des Prozesses. Ein niedrigerer Druck senkt die Kondensationstemperatur und steigert den Carnot-Wirkungsgrad. Limitiert durch die Temperatur der realen Wärmesenke (z. B. Flusswasser/Umgebungsluft)."
    )
    create_synced_input(
        "Kesseldruck $p_{kessel}$ (bar)", "cr_p2", bounds["p2"][0], bounds["p2"][1], 1.0,
        help_text="**Kesseldruck / Verdampfungsdruck**\n\nBestimmt das obere Druckniveau. Eine Erhöhung steigert meist den Wirkungsgrad, führt bei nicht angepasster Frischdampftemperatur jedoch zu höherer Nässe am Turbinenaustritt."
    )
    create_synced_input(
        "Frischdampftemp. $T_{max}$ (°C)", "cr_T3", bounds["T3"][0], bounds["T3"][1], 5.0,
        help_text="**Frischdampftemperatur**\n\nTemperatur am Eintritt der Turbine. Höhere Temperaturen steigern das spez. Enthalpiegefälle und den Wirkungsgrad. Limitiert durch die Materialfestigkeit der Leitungen und Turbinenschaufeln."
    )
    
    p_kond = st.session_state.cr_p1_input
    p_verd_manuell = st.session_state.cr_p2_input
    T_max = st.session_state.cr_T3_input

    opt_p_kessel = st.sidebar.checkbox(
        "Optimalen Kesseldruck berechnen (Sattdampf)", 
        value=False, 
        help="Setzt den Kesseldruck exakt auf den Sättigungsdruck bei der eingestellten Temperatur $T_{max}$. Optimal für ORC-Prozesse mit 'trockenen' Fluiden wie Isopentan, da hier keine Überhitzung nötig ist."
    )
    
    if opt_p_kessel:
        try:
            p_opt_pa = CP.PropsSI('P', 'T', T_max + 273.15, 'Q', 1, cr_fluid)
            p_verd = p_opt_pa / 100000
            st.sidebar.success(f"Automatischer Kesseldruck: **{p_verd:.2f} bar**")
        except ValueError:
            st.sidebar.warning(f"{T_max} °C ist überkritisch für {selected_orc_display}. Manueller Druck erforderlich.")
            p_verd = p_verd_manuell
    else:
        p_verd = p_verd_manuell
    
    if has_zue:
        st.sidebar.markdown("**Zwischenüberhitzung**")
        
        p_zue_min = float(p_kond) + 0.1
        p_zue_max = float(p_verd) - 1.0
        p_zue_default = float(p_verd) / 2.0
        
        ensure_default("cr_p_zue", p_zue_default)
        
        if st.session_state["cr_p_zue_slider"] > p_zue_max:
            st.session_state["cr_p_zue_slider"] = p_zue_max
            st.session_state["cr_p_zue_input"] = p_zue_max
        elif st.session_state["cr_p_zue_slider"] < p_zue_min:
            st.session_state["cr_p_zue_slider"] = p_zue_min
            st.session_state["cr_p_zue_input"] = p_zue_min
            
        create_synced_input(
            "Zwischendruck $p_{ZÜ}$ (bar)", "cr_p_zue", p_zue_min, p_zue_max, 1.0,
            help_text="**Zwischendruck**\n\nDas Druckniveau, bei dem der Dampf aus der HD-Turbine entnommen und zur erneuten Erhitzung in den Kessel geführt wird."
        )
        p_zue = st.session_state.cr_p_zue_input

        T_max_float = float(T_max)
        
        if T_max_float <= bounds["T3"][0]:
            st.sidebar.info(f"T_max ist am Minimum. Die Zwischentemperatur wird automatisch auf {bounds['T3'][0]} °C fixiert.")
            T_zue = bounds["T3"][0]
        else:
            ensure_default("cr_T_zue", T_max_float)
                
            if st.session_state["cr_T_zue_slider"] > T_max_float:
                st.session_state["cr_T_zue_slider"] = T_max_float
                st.session_state["cr_T_zue_input"] = T_max_float
            elif st.session_state["cr_T_zue_slider"] < bounds["T3"][0]:
                st.session_state["cr_T_zue_slider"] = bounds["T3"][0]
                st.session_state["cr_T_zue_input"] = bounds["T3"][0]
                
            create_synced_input(
                "Zwischentemperatur $T_{ZÜ}$ (°C)", "cr_T_zue", bounds["T3"][0], T_max_float, 5.0,
                help_text="**Zwischentemperatur**\n\nZieltemperatur nach der Zwischenüberhitzung. Meist identisch zur Frischdampftemperatur."
            )
            T_zue = st.session_state.cr_T_zue_input
    else:
        p_zue, T_zue = None, None
        
    st.sidebar.divider()
    create_synced_input(
        r"Massenstrom $\dot{m}$ (kg/s)", "cr_m_dot", 1.0, 100.0, 1.0,
        help_text="**Massenstrom**\n\nSkalierungsfaktor der Anlage. Hat keinen Einfluss auf spezifische Größen (wie Wirkungsgrad), bestimmt aber die absoluten kW-Leistungen."
    )
    
    st.sidebar.divider()
    st.sidebar.header("Reale Verluste")
    create_synced_input(
        r"Isentroper Wirkungsgrad Pumpe $\eta_{s,P}$ (%)", "cr_eta_s_P", 50.0, 100.0, 1.0, format="%.0f",
        help_text="**Isentroper Wirkungsgrad (Pumpe)**\n\nBerücksichtigt Strömungs- und Reibungsverluste in der Pumpe. Je niedriger, desto mehr Arbeit muss aufgewendet werden, um den Druck zu erreichen."
    )
    create_synced_input(
        r"Isentroper Wirkungsgrad Turbine $\eta_{s,T}$ (%)", "cr_eta_s_T", 50.0, 100.0, 1.0, format="%.0f",
        help_text="**Isentroper Wirkungsgrad (Turbine)**\n\nBeschreibt, wie viel der ideal verfügbaren Energie in reale mechanische Arbeit umgesetzt wird. Der Rest wird dissipiert und erwärmt das Fluid (Rechtsverschiebung im T-s-Diagramm)."
    )

    eta_s_P = st.session_state.cr_eta_s_P_input / 100.0
    eta_s_T = st.session_state.cr_eta_s_T_input / 100.0
    m_dot = st.session_state.cr_m_dot_input
    
    if p_kond >= p_verd:
        st.error("**Thermodynamischer Widerspruch:** Der Kondensatordruck ($p_{kond}$) darf nicht höher oder gleich dem Kesseldruck ($p_{kessel}$) sein.")
        st.info("Bitte korrigiere die Druckniveaus in der Seitenleiste. Die Kreispumpe kann nicht von einem hohen auf einen niedrigen Druck fördern.")
    else:
        try:
            cr_prozess = ClausiusRankineProzess(
                fluid=cr_fluid, 
                p_kond=p_kond, p_kessel=p_verd, T_max=T_max, m_dot=m_dot, 
                eta_s_P=eta_s_P, eta_s_T=eta_s_T, 
                ignore_pump=ignore_pump, has_zue=has_zue, p_zue=p_zue, T_zue=T_zue
            )
            cr_prozess.berechne_zustaende()
            
            eta_th_real = cr_prozess.wirkungsgrad
            w_net_real = cr_prozess.w_netto
            omega_real = cr_prozess.arbeitsverhaeltnis
            P_tT_real = cr_prozess.leistung_turbine
            P_tP_real = cr_prozess.leistung_pumpe
            pi = cr_prozess.pi
            tau = cr_prozess.tau
            
            st.subheader(f"Reale Ergebnisse für {selected_orc_display}")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric(
                r"Wirkungsgrad $\eta_{th}$", f"{eta_th_real * 100:.2f} %",
                help="**Thermischer Wirkungsgrad**\n\n$\\eta_{th} = \\frac{w_{net}}{q_{zu}}$\n\nGibt an, welcher Anteil der zugeführten Wärme in nutzbare mechanische Arbeit umgewandelt wird."
            )
            col2.metric(
                r"Spez. Arbeit $w_{net}$", f"{w_net_real:.2f} kJ/kg",
                help="**Spezifische Nettoarbeit**\n\n$w_{net} = |w_T| - |w_P| = (h_1 - h_2) - (h_4 - h_3)$\n\nDie pro kg Arbeitsfluid an der Welle effektiv nutzbare mechanische Energie."
            )
            col3.metric(
                r"Spez. Zu-Wärme $q_{zu}$", f"{cr_prozess.q_zu:.2f} kJ/kg",
                help="**Spezifische Wärmezufuhr**\n\n$q_{zu} = h_1 - h_4$\n\nDie im Kessel bzw. Verdampfer pro kg Fluid zugeführte thermische Energie."
            )
            col4.metric(
                r"Druckverh. $\pi$", f"{pi:.1f}",
                help="**Druckverhältnis**\n\n$\\pi = \\frac{p_{kessel}}{p_{kond}}$\n\nMaß für die Druckspreizung der Anlage."
            )
            
            col5, col6, col7, _ = st.columns([1, 1, 1, 1])
            col5.metric(
                r"Temp.-Verh. $\tau$", f"{tau:.2f}",
                help="**Temperaturverhältnis**\n\n$\\tau = \\frac{T_{max}}{T_{kond}}$ (in Kelvin)\n\nJe höher $\\tau$, desto größer ist theoretisch der Carnot-Wirkungsgrad."
            )
            col6.metric(
                r"Turbine(n) $P_T$", f"{P_tT_real:.0f} kW",
                help="**Brutto-Turbinenleistung**\n\n$P_T = \\dot{m} \\cdot |w_T|$\n\nDie gesamte erzeugte mechanische Leistung."
            )
            col7.metric(
                r"Pumpe $P_P$", f"{-P_tP_real:.0f} kW",
                help="**Pumpenleistung (Eigenbedarf)**\n\n$P_P = \\dot{m} \\cdot |w_P|$\n\nLeistungsbedarf zur Förderung des Fluids auf Kesseldruck."
            )
            
            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=False, vertical_spacing=0.1,
                specs=[[{"type": "scatter"}], [{"type": "table"}]], row_heights=[0.75, 0.25]
            )

            # SVG Schema
            if not has_zue:
                try:
                    T1 = cr_prozess.zustand['1']['T'] - 273.15
                    p1 = cr_prozess.zustand['1']['p'] / 100000
                    h1 = cr_prozess.zustand['1']['h'] / 1000
                    T2 = cr_prozess.zustand['2']['T'] - 273.15
                    p2 = cr_prozess.zustand['2']['p'] / 100000
                    h2 = cr_prozess.zustand['2']['h'] / 1000
                    T3 = cr_prozess.zustand['3']['T'] - 273.15
                    p3 = cr_prozess.zustand['3']['p'] / 100000
                    h3 = cr_prozess.zustand['3']['h'] / 1000
                    T4 = cr_prozess.zustand['4']['T'] - 273.15
                    p4 = cr_prozess.zustand['4']['p'] / 100000
                    h4 = cr_prozess.zustand['4']['h'] / 1000

                    with open("CRP.svg", "r", encoding="utf-8") as file:
                        svg_code = file.read()

                    svg_code = svg_code.replace("{T1}", f"{T1:.1f}")
                    svg_code = svg_code.replace("{p1}", f"{p1:.2f}")
                    svg_code = svg_code.replace("{h1}", f"{h1:.1f}")
                    svg_code = svg_code.replace("{T2}", f"{T2:.1f}")
                    svg_code = svg_code.replace("{p2}", f"{p2:.2f}")
                    svg_code = svg_code.replace("{h2}", f"{h2:.1f}")
                    svg_code = svg_code.replace("{T3}", f"{T3:.1f}")
                    svg_code = svg_code.replace("{p3}", f"{p3:.2f}")
                    svg_code = svg_code.replace("{h3}", f"{h3:.1f}")
                    svg_code = svg_code.replace("{T4}", f"{T4:.1f}")
                    svg_code = svg_code.replace("{p4}", f"{p4:.2f}")
                    svg_code = svg_code.replace("{h4}", f"{h4:.1f}")
                    
                    svg_code = apply_theme_to_svg(svg_code)

                    st.subheader("Anlagenschema")
                    st.markdown(
                        f'<div style="display:flex; justify-content:center; width: 100%;">{svg_code}</div>',
                        unsafe_allow_html=True
                    )
                    
                except FileNotFoundError:
                    st.warning("Das Bild 'CRP.svg' fehlt noch im Ordner.")
            
            s_g, T_g = cr_prozess.get_saettigungslinie() 
            fig.add_trace(go.Scatter(x=s_g, y=T_g, mode='lines', line=dict(color='#333333', width=2), name='Nassdampfgebiet'), row=1, col=1)
            
            s_ideal, T_ideal = cr_prozess.get_plot_daten_ideal()
            fig.add_trace(go.Scatter(x=s_ideal, y=T_ideal, mode='lines', line=dict(color='#888888', width=2, dash='dash'), name='Ideal (Isentrop)'), row=1, col=1)
            
            s_real, T_real = cr_prozess.get_plot_daten_real()
            fig.add_trace(go.Scatter(x=s_real, y=T_real, mode='lines', line=dict(color='#FF4B4B', width=3), name='Real (Irreversibel)'), row=1, col=1)
            
            s_eck, t_eck, hover_texte, pt_keys = cr_prozess.get_eckpunkte_daten()
            marker_colors = ['#888888' if 's' in k else '#FF4B4B' for k in pt_keys]
            formatted_keys = [k.replace('s', '<sub>s</sub>').replace('z', '<sub>z</sub>') for k in pt_keys]
            
            fig.add_trace(go.Scatter(
                x=s_eck, y=t_eck, mode='markers+text',
                marker=dict(size=10, color='white', line=dict(width=2, color=marker_colors)),
                text=formatted_keys, 
                textposition="top right",
                hoverinfo="text", hovertext=hover_texte, showlegend=False
            ), row=1, col=1)
            
            daten_tabelle = cr_prozess.get_tabellen_daten()
            fig.add_trace(go.Table(
                header=dict(
                    values=["<b>Punkt</b>", "<b>Druck <i>p</i> (bar)</b>", "<b>Temp. <i>T</i> (°C)</b>", "<b>Enthalpie <i>h</i> (kJ/kg)</b>", "<b>Entropie <i>s</i> (kJ/(kg K))</b>"],
                    font=dict(size=14, color='white'), align="left", fill_color='#FF4B4B', line=dict(color='#E0E0E0', width=1)
                ),
                cells=dict(
                    values=[
                        daten_tabelle['labels'],
                        daten_tabelle['p'], daten_tabelle['T'], daten_tabelle['h'], daten_tabelle['s']
                    ],
                    align="left", font=dict(size=13, color='#333333'), fill_color='#F8F9FA', line=dict(color='#E0E0E0', width=1)
                )
            ), row=2, col=1)
            
            fig.update_layout(
                xaxis_title="Spezifische Entropie <i>s</i> in kJ/(kg K)",
                yaxis_title="Temperatur <i>T</i> in °C",
                height=850, hovermode="closest", margin=dict(l=40, r=40, t=40, b=40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig, use_container_width=True, theme="streamlit")
            
            # Parameterstudie
            if has_zue:
                st.divider()
                st.subheader("Parameterstudie: Einfluss der Zwischenüberhitzung")
                st.write("Untersuche den thermischen Wirkungsgrad $\eta_{th}$ in Abhängigkeit von Zwischendruck und Zwischentemperatur. Graue/Leere Bereiche markieren technisch unzulässige Betriebspunkte. Ausschlusskriterien: 1. Tropfenschlag ($x < 0,88$ am ND-Austritt) und 2. Fehlende Erwärmung ($T_{ZÜ} \le T_{HD,aus}$).")
                
                if st.button("Parameterfeld berechnen (Contour-Plot erstellen)"):
                    with st.spinner("Berechne Wirkungsgradfeld inklusive Turbinenschutz..."):
                        eta_grid, p_zue_arr, T_zue_arr, n_failed = berechne_zue_feld(
                            cr_fluid, p_kond, p_verd, T_max, m_dot, eta_s_P, eta_s_T, ignore_pump
                        )

                        if n_failed:
                            st.caption(f"Hinweis: {n_failed} von {eta_grid.size} Gitterpunkten sind nicht konvergiert und wurden ausgeblendet.")

                        fig_contour = go.Figure(data=go.Contour(
                            z=eta_grid, x=p_zue_arr, y=T_zue_arr,
                            colorscale="Viridis",
                            colorbar=dict(title="η<sub>th</sub> (%)"),
                            connectgaps=False, 
                            hovertemplate="p_ZÜ: %{x:.1f} bar<br>T_ZÜ: %{y:.1f} °C<br>η<sub>th</sub>: %{z:.2f} %<extra></extra>"
                        ))
                        fig_contour.update_layout(
                            xaxis_title="Zwischendruck p<sub>ZÜ</sub> (bar)",
                            yaxis_title="Zwischentemperatur T<sub>ZÜ</sub> (bar)",
                            height=550, margin=dict(l=40, r=40, t=40, b=40)
                        )
                        st.plotly_chart(fig_contour, use_container_width=True, theme="streamlit")
            
        except Exception as e:
            st.error("Thermodynamischer Fehler: Die gewählten Parameter liegen außerhalb des Nassdampf- oder Gasgebiets dieses Fluids.")
            st.info(
                f"**Tipp für ORC-Prozesse:** \n"
                f"Die Frischdampftemperatur ($T_{{max}}$) muss bei dem gewählten Kesseldruck hoch genug sein, damit das Fluid vollständig verdampft. "
                f"Wenn du z. B. den Kesseldruck stark erhöhst, musst du oft auch $T_{{max}}$ anheben."
            )
            with st.expander("Technisches Fehlerdetail (CoolProp)"):
                st.code(e)

# 3. JOULE-PROZESS
elif prozess_auswahl == "Joule-Prozess (Gasturbine)":
    st.title("Joule-Prozess (Offene Gasturbine)")
    st.write("Vergleich: Idealer (reversibler) vs. Realer (irreversibler) Kreisprozess.")
    
    st.sidebar.header("Anlagenkonfiguration")
    fluid_name = st.sidebar.selectbox(
        "Arbeitsfluid", ["Luft (zweiatomig)", "Helium (einatomig)", "Argon (einatomig)", "R744 (CO2)"],
        help="Wähle das Arbeitsgas. Unterschiedliche Gase haben spezifische Wärmekapazitäten ($c_p$) und Isentropenexponenten ($\\kappa$), die den Prozess stark beeinflussen."
    )
    
    st.sidebar.header("Zustandsgrößen")
    create_synced_input(
        "Ansaugtemperatur $T_1$ (°C)", "j_T1", -20.0, 50.0, 1.0,
        help_text="**Ansaugtemperatur**\n\nTemperatur der angesaugten Luft/des Fluids. Je kälter, desto dichter das Gas und desto geringer die spezifische Verdichterarbeit."
    )
    create_synced_input(
        "Ansaugdruck $p_1$ (bar)", "j_p1", 0.8, 1.2, 0.01,
        help_text="**Ansaugdruck**\n\nDruck am Verdichtereintritt, entspricht bei offenen Gasturbinen in der Regel dem Umgebungsdruck."
    )
    create_synced_input(
        "Max. Prozesstemp. $T_3$ (°C)", "j_T3", 500.0, 1500.0, 10.0,
        help_text="**Turbineneintrittstemperatur**\n\nHöchste Temperatur im Prozess nach der Brennkammer. Ein höherer Wert steigert massiv den Wirkungsgrad, ist aber stark durch die Materialfestigkeit der Turbinenschaufeln begrenzt."
    )
    
    T1_c = st.session_state.j_T1_input
    T3_c = st.session_state.j_T3_input
    T1 = T1_c + 273.15
    T3 = T3_c + 273.15
    
    var_cp_mode = False
    if fluid_name == "Luft (zweiatomig)":
        var_cp_mode = st.sidebar.checkbox(
            r"Temp.-abhängige Stoffwerte ($\kappa_m$) nutzen", value=False,
            help="Realere Berechnung für Luft. Berücksichtigt, dass die Wärmekapazität ($c_p$) bei hohen Temperaturen durch Anregung molekularer Schwingungen steigt."
        )
        if var_cp_mode:
            R_i = 287.1
            T_table = np.array([200.0, 250.0, 263.15, 300.0, 500.0, 800.0, 1000.0, 1173.15, 1500.0])
            cp_table = np.array([1002.0, 1003.0, 1003.5, 1005.0, 1030.0, 1099.0, 1142.0, 1170.6, 1211.0])
            
            cp_T1 = np.interp(T1, T_table, cp_table)
            cp_T3 = np.interp(T3, T_table, cp_table)
            
            cp = (cp_T1 + cp_T3) / 2
            kappa = cp / (cp - R_i)
            
            st.sidebar.caption(f"Mittleres $c_p$: **{cp/1000:.4f} kJ/(kg K)**")
            st.sidebar.caption(f"Mittleres $\kappa_m$: **{kappa:.5f}**")
        else:
            R_i, kappa = 287.05, 1.4
            cp = (kappa / (kappa - 1)) * R_i
            
    elif fluid_name == "Helium (einatomig)":
        R_i, kappa = 2077.1, 1.667
        cp = (kappa / (kappa - 1)) * R_i
    elif fluid_name == "R744 (CO2)":
        R_i, kappa = 188.9, 1.289
        cp = (kappa / (kappa - 1)) * R_i
    else: 
        R_i, kappa = 208.1, 1.667
        cp = (kappa / (kappa - 1)) * R_i
        
    st.sidebar.divider()
    
    st.sidebar.header("Reale Verluste")
    eta_s_V = st.sidebar.slider(
        r"Isentroper Wirkungsgrad Verdichter $\eta_{s,V}$ (%)", 50.0, 100.0, 85.0, 1.0,
        help="**Isentroper Wirkungsgrad (Verdichter)**\n\nEin Teil der Verdichterarbeit geht durch Reibung in Wärme über. Ein Wert < 100% bedeutet, dass die Verdichterendtemperatur höher ausfällt als im idealen (isentropen) Fall."
    ) / 100
    eta_s_T = st.sidebar.slider(
        r"Isentroper Wirkungsgrad Turbine $\eta_{s,T}$ (%)", 50.0, 100.0, 88.0, 1.0,
        help="**Isentroper Wirkungsgrad (Turbine)**\n\nNur ein Teil des Enthalpiegefälles kann genutzt werden. Der Rest bleibt als Abwärme im Gas, wodurch die Austrittstemperatur (Punkt 4) heißer ist als ideal berechnet."
    ) / 100
    
    st.sidebar.divider()
    
    opt_mode = st.sidebar.toggle(
        "Optimierungs-Modus (max. Arbeit)",
        help="Berechnet exakt das Druckverhältnis $\\pi$, bei dem die spez. Nettoarbeit maximal wird. Theoretisches Optimum für Leistung, nicht zwingend für Wirkungsgrad."
    )
    if opt_mode:
        tau = T3 / T1
        pi = tau ** (kappa / (2 * (kappa - 1)))
        st.sidebar.success(f"Optimiertes Druckverhältnis $\pi$: **{pi:.2f}**")
    else:
        create_synced_input(
            r"Druckverhältnis $\pi$", "j_pi", 2.0, 30.0, 0.1,
            help_text="**Druckverhältnis**\n\n$\\pi = \\frac{p_2}{p_1}$\n\nVerhältnis von Verdichtungsenddruck zu Ansaugdruck."
        )
        pi = st.session_state.j_pi_input
        
    create_synced_input(
        r"Massenstrom $\dot{m}$ (kg/s)", "j_m_dot", 0.1, 5.0, 0.01,
        help_text="**Massenstrom**\n\nSkalierungsfaktor der Anlage. Hat keinen Einfluss auf den Wirkungsgrad, bestimmt aber die absoluten kW-Leistungen."
    )
    
    p1_bar = st.session_state.j_p1_input
    m_dot = st.session_state.j_m_dot_input
    p1 = p1_bar * 100000 
    
    p2 = p1 * pi
    p3 = p2
    p4 = p1
    
    T2s = T1 * (pi ** ((kappa - 1) / kappa))
    T4s = T3 / (pi ** ((kappa - 1) / kappa))
    
    w_tV_ideal = cp * (T2s - T1) / 1000  
    w_tT_ideal = cp * (T3 - T4s) / 1000  
    
    w_tV_real = w_tV_ideal / eta_s_V
    w_tT_real = w_tT_ideal * eta_s_T
    
    T2 = T1 + (w_tV_real * 1000 / cp)
    T4 = T3 - (w_tT_real * 1000 / cp)
    
    w_net_real = w_tT_real - w_tV_real
    q_zu_real = cp * (T3 - T2) / 1000
    
    eta_th_real = w_net_real / q_zu_real if q_zu_real > 0 else 0
    omega_real = w_net_real / w_tT_real if w_tT_real > 0 else 0
    
    P_tV_real = m_dot * w_tV_real
    P_tT_real = m_dot * w_tT_real 
    
    def calc_s(T, p):
        return (cp * np.log(T / T1) - R_i * np.log(p / p1)) / 1000
        
    s1 = calc_s(T1, p1)
    s2s = calc_s(T2s, p2)
    s2 = calc_s(T2, p2)
    s3 = calc_s(T3, p3)
    s4s = calc_s(T4s, p4)
    s4 = calc_s(T4, p4)
    
    T_2s3 = np.linspace(T2s, T3, 50)
    s_2s3 = [calc_s(T, p2) for T in T_2s3]
    
    T_23 = np.linspace(T2, T3, 50)
    s_23 = [calc_s(T, p2) for T in T_23]
    
    T_4s1 = np.linspace(T4s, T1, 50)
    s_4s1 = [calc_s(T, p1) for T in T_4s1]
    
    T_41 = np.linspace(T4, T1, 50)
    s_41 = [calc_s(T, p1) for T in T_41]
    
    fluid_title = "Luft (variabel)" if var_cp_mode else fluid_name.split()[0]
    st.subheader(f"Reale Ergebnisse für {fluid_title}")
    
    if w_net_real < 0:
        st.error("Achtung: Der Verdichter verbraucht mehr Leistung als die Turbine liefert. Die Anlage ist nicht lauffähig!")
    else:
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric(
            r"Wirkungsgrad $\eta_{th}$", f"{eta_th_real * 100:.2f} %",
            help="**Thermischer Wirkungsgrad**\n\n$\\eta_{th} = \\frac{w_{net}}{q_{zu}}$\n\nAnteil der in der Brennkammer zugeführten Wärme, der in nutzbare mechanische Energie (Welle) umgewandelt wird."
        )
        col2.metric(
            r"Spez. Arbeit $w_{net}$", f"{w_net_real:.2f} kJ/kg",
            help="**Spezifische Nettoarbeit**\n\n$w_{net} = |w_T| - |w_V|$\n\nDie Energieausbeute pro kg Gas. Bei Gasturbinen merklich geringer als beim Dampfkraftwerk, da der Gas-Verdichter extrem viel Leistung schluckt."
        )
        col3.metric(
            r"Arbeitsverh. $\omega$", f"{omega_real:.2f}",
            help="**Arbeitsverhältnis**\n\n$\\omega = \\frac{w_{net}}{w_T}$\n\nGibt an, welcher Bruchteil der Turbinenleistung nach Abzug des Eigenbedarfs (Verdichter) noch als effektive Nutzleistung für den Generator übrig bleibt."
        )
        col4.metric(
            r"Turbine $P_T$", f"{P_tT_real:.0f} kW",
            help="**Brutto-Turbinenleistung**\n\nDie gesamte von der Turbine erzeugte Leistung (Expansion aus dem Heißgas)."
        )
        col5.metric(
            r"Verdichter $P_V$", f"{P_tV_real:.0f} kW",
            help="**Verdichterleistung (Eigenbedarf)**\n\nDer Leistungsbedarf des Luft-Kompressors. Wird in der Praxis direkt über dieselbe Welle von der Turbine angetrieben."
        )

    # Schema Joule-Prozess
    try:
        with open("Joule-Prozess.svg", "r", encoding="utf-8") as file:
            svg_code = file.read()

        svg_code = svg_code.replace("{T1}", f"{T1-273.15:.1f}")
        svg_code = svg_code.replace("{p1}", f"{p1/100000:.2f}")

        svg_code = svg_code.replace("{T2}", f"{T2-273.15:.1f}")
        svg_code = svg_code.replace("{p2}", f"{p2/100000:.2f}")

        svg_code = svg_code.replace("{T3}", f"{T3-273.15:.1f}")
        svg_code = svg_code.replace("{p3}", f"{p3/100000:.2f}")

        svg_code = svg_code.replace("{T4}", f"{T4-273.15:.1f}")
        svg_code = svg_code.replace("{p4}", f"{p4/100000:.2f}")

        svg_code = apply_theme_to_svg(svg_code)

        st.subheader("Anlagenschema")
        st.markdown(
            f'<div style="display:flex; justify-content:center; width: 100%;">{svg_code}</div>',
            unsafe_allow_html=True
        )
        
    except FileNotFoundError:
        st.warning("Das Bild 'Joule-Prozess.svg' fehlt noch im Ordner.")

    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=False, vertical_spacing=0.1,
        specs=[[{"type": "scatter"}], [{"type": "table"}]], row_heights=[0.75, 0.25]
    )
    
    fig.add_trace(go.Scatter(x=[s1, s2s], y=[T1-273.15, T2s-273.15], mode='lines', line=dict(color='#888888', width=2, dash='dash'), name='Ideal (Isentrop)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=s_2s3, y=T_2s3-273.15, mode='lines', line=dict(color='#888888', width=2, dash='dash'), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=[s3, s4s], y=[T3-273.15, T4s-273.15], mode='lines', line=dict(color='#888888', width=2, dash='dash'), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=s_4s1, y=T_4s1-273.15, mode='lines', line=dict(color='#888888', width=2, dash='dash'), showlegend=False), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=[s1, s2], y=[T1-273.15, T2-273.15], mode='lines', line=dict(color='#0068C9', width=3), name='Real (Irreversibel)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=s_23, y=T_23-273.15, mode='lines', line=dict(color='#0068C9', width=3), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=[s3, s4], y=[T3-273.15, T4-273.15], mode='lines', line=dict(color='#0068C9', width=3), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=s_41, y=T_41-273.15, mode='lines', line=dict(color='#0068C9', width=3), showlegend=False), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=[s1, s2s, s2, s3, s4s, s4], y=[T1-273.15, T2s-273.15, T2-273.15, T3-273.15, T4s-273.15, T4-273.15],
        mode='markers+text',
        marker=dict(size=10, color='white', line=dict(width=2, color=['#0068C9', '#888888', '#0068C9', '#0068C9', '#888888', '#0068C9'])),
        text=["1", "2<sub>s</sub>", "2", "3", "4<sub>s</sub>", "4"], 
        textposition=["bottom right", "top left", "bottom right", "top center", "bottom left", "bottom right"],
        showlegend=False
    ), row=1, col=1)
    
    fig.add_trace(go.Table(
        header=dict(
            values=["<b>Punkt</b>", "<b>Druck <i>p</i> (bar)</b>", "<b>Temp. <i>T</i> (°C)</b>", "<b>Entropie <i>s</i> (kJ/(kg K))</b>"],
            font=dict(size=14, color='white'), align="left", fill_color='#0068C9', line=dict(color='#E0E0E0', width=1)
        ),
        cells=dict(
            values=[
                ["1 (Ansaugung)", "2<sub>s</sub> (Ideal Verdichtet)", "2 (Real Verdichtet)", "3 (Turbineneintritt)", "4<sub>s</sub> (Ideal Entspannt)", "4 (Real Entspannt)"],
                [f"{p1/100000:.2f}", f"{p2/100000:.2f}", f"{p2/100000:.2f}", f"{p3/100000:.2f}", f"{p4/100000:.2f}", f"{p4/100000:.2f}"],
                [f"{T1-273.15:.2f}", f"{T2s-273.15:.2f}", f"{T2-273.15:.2f}", f"{T3-273.15:.2f}", f"{T4s-273.15:.2f}", f"{T4-273.15:.2f}"],
                [f"{s1:.4f}", f"{s2s:.4f}", f"{s2:.4f}", f"{s3:.4f}", f"{s4s:.4f}", f"{s4:.4f}"]
            ],
            align="left", font=dict(size=13, color='#333333'), fill_color='#F8F9FA', line=dict(color='#E0E0E0', width=1)
        )
    ), row=2, col=1)
    
    fig.update_layout(
        xaxis_title="Spezifische Entropie <i>s</i> in kJ/(kg K)",
        yaxis_title="Temperatur <i>T</i> in °C",
        height=850, hovermode="closest", margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")


# 4. KÄLTEANLAGEN
elif prozess_auswahl == "Kälteanlage (Kompressionskältemaschine)":
    st.title("Kompressionskälteanlage")
    st.write("Thermodynamische Auslegung und Analyse von Kältekreisläufen.")
    
    st.sidebar.header("1. Anlagenaufbau")
    is_2stage = st.sidebar.toggle("Zweistufige Verdichtung", value=False)
    
    has_mdf = st.sidebar.checkbox("Mitteldruckflasche (MDF)", value=is_2stage, disabled=not is_2stage)
    if has_mdf:
        mdf_auswahl = st.sidebar.radio("Verschaltung MDF", ["Partiell (Flashgas-Bypass)", "Vollständig (Quenchen)"], label_visibility="collapsed")
        mdf_mode_key = "partiell" if "Partiell" in mdf_auswahl else "vollstaendig"
    else:
        mdf_mode_key = "partiell"
        
    has_zk = st.sidebar.checkbox("Äußere Zwischenkühlung (ZK)", disabled=not is_2stage)
    
    if not is_2stage:
        has_mdf = False
        has_zk = False
        T_zk_input = None

    st.sidebar.divider()
    
    st.sidebar.header("2. Prozessparameter")
    
    fluid_mapping = get_filtered_fluids()
    display_names = list(fluid_mapping.keys())
    
    default_index = display_names.index("R134a") if "R134a" in display_names else 0
    selected_display = st.sidebar.selectbox("Kältemittel", display_names, index=default_index)
    
    fluid = fluid_mapping[selected_display] 
    
    kaelte_init = {
        "k_t0": -10.0, "k_tc": 40.0, "k_tm": 10.0,
        "k_p0": 2.0, "k_pc": 10.0, "k_pm": 5.0,
        "k_tzk": 25.0,
        "k_eta": 80.0, "k_eta_nd": 80.0, "k_eta_hd": 80.0
    }
    for k, v in kaelte_init.items():
        ensure_default(k, v)

    st.sidebar.markdown("---")
    
    st.sidebar.markdown("**Verdampfung (Niederdruck)**")
    eingabe_modus_0 = st.sidebar.radio("Modus Verdampfung", ["Temperatur (°C)", "Druck (bar)"], horizontal=True, label_visibility="collapsed")
    help_v = "**Verdampfungsniveau**\n\nDie Zieltemperatur bzw. der Zieldruck für die Nutzkälte (z.B. Kühlraum). Je tiefer $T_0$, desto mehr spezifische Verdichterarbeit wird benötigt und desto geringer wird die Energieeffizienz (EER)."
    if eingabe_modus_0 == "Temperatur (°C)":
        create_synced_input("Verdampfungstemp. $T_0$ (°C)", "k_t0", -80.0, 50.0, 1.0, format="%.1f", help_text=help_v)
    else:
        create_synced_input("Verdampfungsdruck $p_0$ (bar)", "k_p0", 0.1, 80.0, 0.1, format="%.2f", help_text=help_v)

    st.sidebar.markdown("**Kondensation (Hochdruck)**")
    eingabe_modus_c = st.sidebar.radio("Modus Kondensation", ["Temperatur (°C)", "Druck (bar)"], horizontal=True, label_visibility="collapsed")
    help_c = "**Kondensationsniveau**\n\nTemperatur/Druck der Wärmeabfuhr an die Umgebung. Muss etwas höher als die Umgebungstemperatur sein, damit Wärme abfließen kann. Eine hohe Kondensationstemperatur verschlechtert den EER."
    if eingabe_modus_c == "Temperatur (°C)":
        create_synced_input("Kondensationstemp. $T_c$ (°C)", "k_tc", -20.0, 90.0, 1.0, format="%.1f", help_text=help_c)
    else:
        create_synced_input("Kondensationsdruck $p_c$ (bar)", "k_pc", 0.5, 150.0, 0.5, format="%.2f", help_text=help_c)

    opt_pm = False
    if is_2stage:
        st.sidebar.markdown("**Zwischenstufe (Mitteldruck)**")
        opt_pm = st.sidebar.checkbox(
            "Optimalen Mitteldruck berechnen", value=False, 
            help="Berechnet automatisch $p_m = \sqrt{p_0 \\cdot p_c}$. Das geometrische Mittel sorgt bei vielen Anlagen thermodynamisch für den maximalen COP/EER."
        )
        
        if not opt_pm:
            eingabe_modus_m = st.sidebar.radio("Modus Zwischenstufe", ["Temperatur (°C)", "Druck (bar)"], horizontal=True, label_visibility="collapsed")
            help_m = "**Mittel- / Zwischendruck**\n\nDas Druckniveau, auf dem das Gas aus dem ND-Verdichter gekühlt oder das Flashgas abgetrennt wird."
            if eingabe_modus_m == "Temperatur (°C)":
                create_synced_input("Zwischentemp. $T_m$ (°C)", "k_tm", -40.0, 60.0, 1.0, format="%.1f", help_text=help_m)
            else:
                create_synced_input("Zwischendruck $p_m$ (bar)", "k_pm", 0.2, 100.0, 0.5, format="%.2f", help_text=help_m)
        
        if has_zk:
            st.sidebar.markdown("**Äußere Zwischenkühlung (ZK)**")
            create_synced_input(
                "Temp. nach ZK $T_{2zk}$ (°C)", "k_tzk", -30.0, 80.0, 1.0, format="%.1f",
                help_text="**Temperatur nach Zwischenkühlung**\n\nTemperatur, auf die das Heißgas nach dem Niederdruckverdichter durch einen äußeren Kühler (z. B. Kühlwasser) vor dem HD-Verdichter heruntergekühlt wird."
            )
            T_zk_input = st.session_state.k_tzk_input
        else:
            T_zk_input = None
    
    st.sidebar.markdown("---")
    
    st.sidebar.markdown("**Überhitzung (Sauggas)**")
    has_sh = st.sidebar.checkbox("Überhitzung aktiv", value=True)
    if has_sh:
        sh_mode = st.sidebar.radio("Art der Überhitzung", ["um (ΔT)", "auf (T)"], horizontal=True, label_visibility="collapsed")
        help_sh = "**Sauggas-Überhitzung**\n\nErwärmung des Kältemittels nach dem Verdampfer. Sorgt dafür, dass restliche Tröpfchen verdampfen und schützt den Verdichter vor gefährlichem Flüssigkeitsschlag."
        if sh_mode == "um (ΔT)":
            dT_sh_input = st.sidebar.number_input(r"$\Delta T_{sh}$ (K)", value=5.0, min_value=0.0, step=1.0, help=help_sh)
            T_sh_input = None
        else:
            T_sh_input = st.sidebar.number_input("Sauggastemperatur $T_1$ (°C)", value=-5.0, step=1.0, help=help_sh)
            dT_sh_input = None

    st.sidebar.markdown("**Unterkühlung (Kondensat)**")
    has_sc = st.sidebar.checkbox("Unterkühlung aktiv", value=True)
    if has_sc:
        sc_mode = st.sidebar.radio("Art der Unterkühlung", ["um (ΔT)", "auf (T)"], horizontal=True, label_visibility="collapsed")
        t_sub_label = "Flüssigkeitstemp. $T_5$ (°C)" if is_2stage else "Flüssigkeitstemp. $T_3$ (°C)"
        help_sc = "**Kondensat-Unterkühlung**\n\nWeitere Abkühlung der flüssigen Phase nach der Kondensation. Erhöht die nutzbare spezifische Kälteleistung, da nach dem Ex-Ventil weniger Flashgas entsteht."
        if sc_mode == "um (ΔT)":
            dT_sc_input = st.sidebar.number_input(r"$\Delta T_{sc}$ (K)", value=2.0, min_value=0.0, step=1.0, help=help_sc)
            T_sc_input = None
        else:
            T_sc_input = st.sidebar.number_input(t_sub_label, value=38.0, step=1.0, help=help_sc)
            dT_sc_input = None

    st.sidebar.divider()
    
    st.sidebar.header("3. Reale Verluste")
    help_eta = "**Isentroper Verdichter-Wirkungsgrad**\n\nBerücksichtigt Reibungs- und Strömungsverluste bei der Kompression. Führt zu einem höheren Leistungsbedarf und einer Erwärmung des Gases (höhere Heißgastemperatur)."
    if is_2stage:
        create_synced_input(r"Wirkungsgrad ND-Verdichter $\eta_{is,ND}$ (%)", "k_eta_nd", 30.0, 100.0, 1.0, format="%.0f", help_text=help_eta)
        create_synced_input(r"Wirkungsgrad HD-Verdichter $\eta_{is,HD}$ (%)", "k_eta_hd", 30.0, 100.0, 1.0, format="%.0f", help_text=help_eta)
        eta_is_nd = st.session_state.k_eta_nd_input / 100.0
        eta_is_hd = st.session_state.k_eta_hd_input / 100.0
    else:
        create_synced_input(r"Isentroper Verdichter-Wirkungsgrad $\eta_{is}$ (%)", "k_eta", 30.0, 100.0, 1.0, format="%.0f", help_text=help_eta)
        eta_is_nd = st.session_state.k_eta_input / 100.0
        eta_is_hd = eta_is_nd 
    
    try:
        if eingabe_modus_0 == "Druck (bar)":
            p_0_bar = st.session_state.k_p0_input
            T_0_C = CP.PropsSI('T', 'P', p_0_bar * 100000, 'Q', 1, fluid) - 273.15
        else:
            T_0_C = st.session_state.k_t0_input
            p_0_bar = CP.PropsSI('P', 'T', T_0_C + 273.15, 'Q', 1, fluid) / 100000

        if eingabe_modus_c == "Druck (bar)":
            p_c_bar = st.session_state.k_pc_input
            T_c_C = CP.PropsSI('T', 'P', p_c_bar * 100000, 'Q', 0, fluid) - 273.15
        else:
            T_c_C = st.session_state.k_tc_input
            p_c_bar = CP.PropsSI('P', 'T', T_c_C + 273.15, 'Q', 0, fluid) / 100000

        if is_2stage:
            if opt_pm:
                p_m_bar = np.sqrt(p_0_bar * p_c_bar)
                T_m_C = CP.PropsSI('T', 'P', p_m_bar * 100000, 'Q', 1, fluid) - 273.15
            else:
                if eingabe_modus_m == "Druck (bar)":
                    p_m_bar = st.session_state.k_pm_input
                    T_m_C = CP.PropsSI('T', 'P', p_m_bar * 100000, 'Q', 1, fluid) - 273.15
                else:
                    T_m_C = st.session_state.k_tm_input
        else:
            T_m_C = None

        dT_sh = 0.0
        if has_sh:
            if sh_mode == "um (ΔT)":
                dT_sh = dT_sh_input
            else:
                dT_sh = T_sh_input - T_0_C
                if dT_sh < 0:
                    st.warning(f"Die eingestellte Sauggastemperatur ({T_sh_input} °C) liegt unter der Verdampfungstemperatur $T_0$ ({T_0_C:.1f} °C). Überhitzung wird auf 0 K gesetzt.")
                    dT_sh = 0.0

        dT_sc = 0.0
        if has_sc:
            if sc_mode == "um (ΔT)":
                dT_sc = dT_sc_input
            else:
                dT_sc = T_c_C - T_sc_input
                if dT_sc < 0:
                    st.warning(f"Die eingestellte Flüssigkeitstemperatur liegt über der Kondensationstemperatur $T_c$ ({T_c_C:.1f} °C). Unterkühlung wird auf 0 K gesetzt.")
                    dT_sc = 0.0

        kaelte_prozess = KaelteKreisprozess(fluid=fluid, T_0_C=T_0_C, T_c_C=T_c_C, T_m_C=T_m_C, dT_sh=dT_sh, dT_sc=dT_sc, eta_is_nd=eta_is_nd, eta_is_hd=eta_is_hd)
        
        if is_2stage:
            if has_zk and T_zk_input is not None:
                T_sat_m = CP.PropsSI('T', 'P', kaelte_prozess.p_m, 'Q', 1, fluid) - 273.15
                if T_zk_input < T_sat_m:
                    st.warning(f"Die eingestellte ZK-Temperatur ({T_zk_input} °C) liegt unter der Sättigungstemperatur ({T_sat_m:.2f} °C) bei Mitteldruck. Das Gas würde kondensieren. Die Temperatur wird auf den Taupunkt begrenzt.")
            
            kaelte_prozess.berechne_zweistufig(has_mdf=has_mdf, mdf_mode=mdf_mode_key, has_zk=has_zk, T_2zk_C=T_zk_input)
        else:
            kaelte_prozess.berechne_einstufig()

        
        if is_2stage and opt_pm:
            st.info(f"**Optimaler Mitteldruck aktiv:** $p_m$ = {p_m_bar:.2f} bar (entspricht $T_m$ = {T_m_C:.1f} °C)")

        st.subheader("Leistungskennzahlen")
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric(
            "Leistungszahl (EER)", f"{kaelte_prozess.cop:.2f}",
            help="**Energy Efficiency Ratio (EER)**\n\n$EER = \\frac{q_0}{w_c}$\n\nGibt an, wie viele Einheiten Nutzkälte pro eingesetzter Einheit elektrischer Verdichterarbeit erzeugt werden. Entspricht dem COP für Kälte."
        )
        kpi2.metric(
            r"Spez. Kälteleistung $q_0$", f"{kaelte_prozess.q_0:.2f} kJ/kg",
            help="**Spezifische Kälteleistung**\n\n$q_0 = h_{austritt} - h_{eintritt}$\n\nDie vom Kältemittel im Verdampfer pro kg Masse aufgenommene thermische Energie."
        )
        kpi3.metric(
            r"Spez. Verdichterarbeit $w_c$", f"{kaelte_prozess.w_c:.2f} kJ/kg",
            help="**Spezifische Verdichterarbeit**\n\n$w_c = h_{heißgas} - h_{sauggas}$\n\nDie an der Welle in das Fluid eingebrachte Kompressionsarbeit. Bei zweistufigen Anlagen die Summe aus ND- und HD-Stufe."
        )
        
        if is_2stage and has_zk:
            st.info(f"Die äußere Zwischenkühlung führt **$q_{{zk}}$ = {kaelte_prozess.q_zk:.2f} kJ/kg** Wärme ab.")

        if is_2stage and has_mdf:
            st.subheader("Massenstromverhältnisse")
            st.caption("Bezogen auf 1 kg/s im Hochdruckkreislauf")
            
            help_mhd = "**Hochdruck-Massenanteil**\n\nDefiniert als 1,0. Normierter Basis-Massenstrom durch Kondensator und HD-Verdichter."
            help_mnd = "**Niederdruck-Massenanteil**\n\nAnteil des Massenstroms, der effektiv durch den Verdampfer und ND-Verdichter fließt. Bei aktiver Flasche stets < 1."
            help_mbypass = "**Bypass- / Flashgas-Anteil**\n\nDer Dampfanteil $x$, der bei der ersten Entspannung entsteht und direkt (als Gas) abgeführt wird, um den Verdampfer zu entlasten."

            if mdf_mode_key == "partiell":
                m1, m2, m3 = st.columns(3)
                m1.metric(r"$\mu_{HD}$ (Hochdruck)", f"{kaelte_prozess.m_hd:.3f} kg/kg", help=help_mhd)
                m2.metric(r"$\mu_{ND}$ (Niederdruck)", f"{kaelte_prozess.m_nd:.3f} kg/kg", help=help_mnd)
                m3.metric(r"$\mu_{Bypass}$ (Flashgas)", f"{kaelte_prozess.m_bypass:.3f} kg/kg", help=help_mbypass)
            else:
                m1, m2 = st.columns(2)
                m1.metric(r"$\mu_{HD}$ (Hochdruck)", f"{kaelte_prozess.m_hd:.3f} kg/kg", help=help_mhd)
                m2.metric(r"$\mu_{ND}$ (Niederdruck)", f"{kaelte_prozess.m_nd:.3f} kg/kg", help=help_mnd)

        st.subheader("Anlagenschema (Interaktiv)")
        
        if not is_2stage:
            try:

                with open("Kaelte_1_stufig.svg", "r", encoding="utf-8") as file:
                    svg_code = file.read()
                for i in range(1, 5):
                    idx = str(i)
                    if idx in kaelte_prozess.zustand:
                        T = kaelte_prozess.zustand[idx]['T'] - 273.15
                        p = kaelte_prozess.zustand[idx]['p'] / 100000
                        h = kaelte_prozess.zustand[idx]['h'] / 1000
                        
                        svg_code = svg_code.replace(f"{{T{i}}}", f"{T:.1f}")
                        svg_code = svg_code.replace(f"{{p{i}}}", f"{p:.2f}")
                        svg_code = svg_code.replace(f"{{h{i}}}", f"{h:.1f}")
                
                svg_code = apply_theme_to_svg(svg_code)
                st.markdown(f'<div style="display:flex; justify-content:center; width: 100%;">{svg_code}</div>', unsafe_allow_html=True)
            except FileNotFoundError:
                st.warning("Das Bild 'Kaelte_1_stufig.svg' fehlt noch im Ordner.")
                
        elif not has_mdf and not has_zk:
            try:
                with open("Kaelte_2_stufig_basis.svg", "r", encoding="utf-8") as file:
                    svg_code = file.read()

                mapping = {1: '1', 2: '2', 3: '4', 4: '5', 5: '9'}
                
                for svg_idx, backend_idx in mapping.items():
                    if backend_idx in kaelte_prozess.zustand:
                        T = kaelte_prozess.zustand[backend_idx]['T'] - 273.15
                        p = kaelte_prozess.zustand[backend_idx]['p'] / 100000
                        h = kaelte_prozess.zustand[backend_idx]['h'] / 1000
                        
                        svg_code = svg_code.replace(f"{{T{svg_idx}}}", f"{T:.1f}")
                        svg_code = svg_code.replace(f"{{p{svg_idx}}}", f"{p:.2f}")
                        svg_code = svg_code.replace(f"{{h{svg_idx}}}", f"{h:.1f}")
                
                svg_code = apply_theme_to_svg(svg_code)
                st.markdown(f'<div style="display:flex; justify-content:center; width: 100%;">{svg_code}</div>', unsafe_allow_html=True)
            except FileNotFoundError:
                st.warning("Das Bild 'Kaelte_2_stufig_basis.svg' fehlt noch im Ordner.")
                
        elif has_mdf and mdf_mode_key == "partiell" and not has_zk:
            try:
                with open("Kaelte_2_stufig_mdf_partiell.svg", "r", encoding="utf-8") as file:
                    svg_code = file.read()

                mapping = {
                    1: '1',
                    2: '2',
                    3: '7',
                    4: '3',
                    5: '4',
                    6: '5',
                    7: '6',
                    8: '8',
                    9: '9'
                }
                
                for svg_idx, backend_idx in mapping.items():
                    if backend_idx in kaelte_prozess.zustand:
                        T = kaelte_prozess.zustand[backend_idx]['T'] - 273.15
                        p = kaelte_prozess.zustand[backend_idx]['p'] / 100000
                        h = kaelte_prozess.zustand[backend_idx]['h'] / 1000
                        
                        svg_code = svg_code.replace(f"{{T{svg_idx}}}", f"{T:.1f}")
                        svg_code = svg_code.replace(f"{{p{svg_idx}}}", f"{p:.2f}")
                        svg_code = svg_code.replace(f"{{h{svg_idx}}}", f"{h:.1f}")
                
                svg_code = apply_theme_to_svg(svg_code)
                st.markdown(f'<div style="display:flex; justify-content:center; width: 100%;">{svg_code}</div>', unsafe_allow_html=True)
            except FileNotFoundError:
                st.warning("Das Bild 'Kaelte_2_stufig_mdf_partiell.svg' fehlt noch im Ordner.")
                
        elif has_mdf and mdf_mode_key == "partiell" and has_zk:
            try:
                with open("Kaelte_2_stufig_mdf_partiell_zk.svg", "r", encoding="utf-8") as file:
                    svg_code = file.read()

                mapping = {
                    1: '1',
                    2: '2',
                    3: '10',
                    4: '7',
                    5: '3',
                    6: '4',
                    7: '5',
                    8: '6',
                    9: '8',
                    10: '9'
                }
                
                for svg_idx, backend_idx in mapping.items():
                    if backend_idx in kaelte_prozess.zustand:
                        T = kaelte_prozess.zustand[backend_idx]['T'] - 273.15
                        p = kaelte_prozess.zustand[backend_idx]['p'] / 100000
                        h = kaelte_prozess.zustand[backend_idx]['h'] / 1000
                        
                        svg_code = svg_code.replace(f"{{T{svg_idx}}}", f"{T:.1f}")
                        svg_code = svg_code.replace(f"{{p{svg_idx}}}", f"{p:.2f}")
                        svg_code = svg_code.replace(f"{{h{svg_idx}}}", f"{h:.1f}")
                
                svg_code = apply_theme_to_svg(svg_code)
                st.markdown(f'<div style="display:flex; justify-content:center; width: 100%;">{svg_code}</div>', unsafe_allow_html=True)
            except FileNotFoundError:
                st.warning("Das Bild 'Kaelte_2_stufig_mdf_partiell_zk.svg' fehlt noch im Ordner.")

        elif has_mdf and mdf_mode_key == "vollstaendig" and not has_zk:
            try:

                with open("Kaelte_2_stufig_mdf_vollstaendig.svg", "r", encoding="utf-8") as file:
                    svg_code = file.read()

                mapping = {
                    1: '1',
                    2: '2',
                    3: '3',
                    4: '4',
                    5: '5',
                    6: '6',
                    7: '8',
                    8: '9'
                }
                
                for svg_idx, backend_idx in mapping.items():
                    if backend_idx in kaelte_prozess.zustand:
                        T = kaelte_prozess.zustand[backend_idx]['T'] - 273.15
                        p = kaelte_prozess.zustand[backend_idx]['p'] / 100000
                        h = kaelte_prozess.zustand[backend_idx]['h'] / 1000
                        
                        svg_code = svg_code.replace(f"{{T{svg_idx}}}", f"{T:.1f}")
                        svg_code = svg_code.replace(f"{{p{svg_idx}}}", f"{p:.2f}")
                        svg_code = svg_code.replace(f"{{h{svg_idx}}}", f"{h:.1f}")
                
                svg_code = apply_theme_to_svg(svg_code)
                st.markdown(f'<div style="display:flex; justify-content:center; width: 100%;">{svg_code}</div>', unsafe_allow_html=True)
            except FileNotFoundError:
                st.warning("Das Bild 'Kaelte_2_stufig_mdf_vollstaendig.svg' fehlt noch im Ordner.")
        elif not has_mdf and has_zk:
            try:
                with open("Kaelte_2_stufig_zk.svg", "r", encoding="utf-8") as file:
                    svg_code = file.read()

                mapping = {
                    1: '1',
                    2: '2',
                    3: '3',
                    4: '4',
                    5: '5',
                    6: '9'
                }
                
                for svg_idx, backend_idx in mapping.items():
                    if backend_idx in kaelte_prozess.zustand:
                        T = kaelte_prozess.zustand[backend_idx]['T'] - 273.15
                        p = kaelte_prozess.zustand[backend_idx]['p'] / 100000
                        h = kaelte_prozess.zustand[backend_idx]['h'] / 1000
                        
                        svg_code = svg_code.replace(f"{{T{svg_idx}}}", f"{T:.1f}")
                        svg_code = svg_code.replace(f"{{p{svg_idx}}}", f"{p:.2f}")
                        svg_code = svg_code.replace(f"{{h{svg_idx}}}", f"{h:.1f}")
                
                svg_code = apply_theme_to_svg(svg_code)
                st.markdown(f'<div style="display:flex; justify-content:center; width: 100%;">{svg_code}</div>', unsafe_allow_html=True)
            except FileNotFoundError:
                st.warning("Das Bild 'Kaelte_2_stufig_zk.svg' fehlt noch im Ordner.")
        elif has_mdf and mdf_mode_key == "vollstaendig" and has_zk:
            try:
                with open("Kaelte_2_stufig_mdf_vollstaendig_zk.svg", "r", encoding="utf-8") as file:
                    svg_code = file.read()

                mapping = {
                    1: '1',
                    2: '2',
                    3: '2zk',
                    4: '3',
                    5: '4',
                    6: '5',
                    7: '6',
                    8: '8',
                    9: '9'
                }
                
                for svg_idx, backend_idx in mapping.items():
                    if backend_idx in kaelte_prozess.zustand:
                        T = kaelte_prozess.zustand[backend_idx]['T'] - 273.15
                        p = kaelte_prozess.zustand[backend_idx]['p'] / 100000
                        h = kaelte_prozess.zustand[backend_idx]['h'] / 1000
                        
                        svg_code = svg_code.replace(f"{{T{svg_idx}}}", f"{T:.1f}")
                        svg_code = svg_code.replace(f"{{p{svg_idx}}}", f"{p:.2f}")
                        svg_code = svg_code.replace(f"{{h{svg_idx}}}", f"{h:.1f}")
                
                svg_code = apply_theme_to_svg(svg_code)
                st.markdown(f'<div style="display:flex; justify-content:center; width: 100%;">{svg_code}</div>', unsafe_allow_html=True)
            except FileNotFoundError:
                st.warning("Das Bild 'Kaelte_2_stufig_mdf_vollstaendig_zk.svg' fehlt noch im Ordner.")

        st.subheader("Thermodynamik")
        
        h_g, s_g, T_g, p_g = kaelte_prozess.get_saettigungslinie()
        h_id, s_id, T_id, p_id = kaelte_prozess.get_plot_linien_ideal()
        h_re, s_re, T_re, p_re = kaelte_prozess.get_plot_linien_real()
        h_pts, s_pts, T_pts, p_pts, hover_pts, pt_keys = kaelte_prozess.get_eckpunkte_daten()
        
        marker_colors = ['#888888' if 's' in k else '#0068C9' for k in pt_keys]
        
        tab_ph, tab_ts, tab_tab = st.tabs(["log-p-h Diagramm", "T-s Diagramm", "Zustandspunkte"])
        
        with tab_ph:
            fig_ph = go.Figure()
            fig_ph.add_trace(go.Scatter(x=h_g, y=p_g, mode='lines', line=dict(color='#333333', width=2), name='Nassdampfgebiet'))
            fig_ph.add_trace(go.Scatter(x=h_id, y=p_id, mode='lines', line=dict(color='#888888', width=2, dash='dash'), name='Ideal (Isentrop)'))
            fig_ph.add_trace(go.Scatter(x=h_re, y=p_re, mode='lines', line=dict(color='#0068C9', width=3), name='Real (Irreversibel)'))
            fig_ph.add_trace(go.Scatter(
                x=h_pts, y=p_pts, mode='markers+text',
                marker=dict(size=10, color='white', line=dict(width=2, color=marker_colors)),
                text=pt_keys, 
                textposition="top right", hoverinfo="text", hovertext=hover_pts, showlegend=False
            ))
            
            fig_ph.update_layout(
                xaxis_title="Spezifische Enthalpie <i>h</i> in kJ/kg",
                yaxis_title="Druck <i>p</i> in bar",
                yaxis_type="log",
                height=600, hovermode="closest", margin=dict(l=40, r=40, t=40, b=40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_ph, use_container_width=True, theme="streamlit")
            
        with tab_ts:
            fig_ts = go.Figure()
            fig_ts.add_trace(go.Scatter(x=s_g, y=T_g, mode='lines', line=dict(color='#333333', width=2), name='Nassdampfgebiet'))
            fig_ts.add_trace(go.Scatter(x=s_id, y=T_id, mode='lines', line=dict(color='#888888', width=2, dash='dash'), name='Ideal (Isentrop)'))
            fig_ts.add_trace(go.Scatter(x=s_re, y=T_re, mode='lines', line=dict(color='#0068C9', width=3), name='Real (Irreversibel)'))
            fig_ts.add_trace(go.Scatter(
                x=s_pts, y=T_pts, mode='markers+text',
                marker=dict(size=10, color='white', line=dict(width=2, color=marker_colors)),
                text=pt_keys, 
                textposition="top right", hoverinfo="text", hovertext=hover_pts, showlegend=False
            ))
            
            fig_ts.update_layout(
                xaxis_title="Spezifische Entropie <i>s</i> in kJ/(kg K)",
                yaxis_title="Temperatur <i>T</i> in °C",
                height=600, hovermode="closest", margin=dict(l=40, r=40, t=40, b=40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_ts, use_container_width=True, theme="streamlit")
            
        with tab_tab:
            daten_tabelle = kaelte_prozess.get_tabellen_daten()
            
            headers = ["<b>Punkt</b>", "<b>Druck <i>p</i> (bar)</b>", "<b>Temp. <i>T</i> (°C)</b>", "<b>Enthalpie <i>h</i> (kJ/kg)</b>", "<b>Entropie <i>s</i> (kJ/(kg K))</b>"]
            cells_values = [
                daten_tabelle['labels'], 
                daten_tabelle['p'], daten_tabelle['T'], daten_tabelle['h'], daten_tabelle['s']
            ]
            
            if 'mu' in daten_tabelle:
                headers.append("<b>Massenanteil <i>μ</i></b>")
                cells_values.append(daten_tabelle['mu'])
            
            fig_tab = go.Figure(data=[go.Table(
                header=dict(
                    values=headers,
                    font=dict(size=14, color='white'), align="left", fill_color='#0068C9', line=dict(color='#E0E0E0', width=1)
                ),
                cells=dict(
                    values=cells_values,
                    align="left", font=dict(size=13, color='#333333'), fill_color='#F8F9FA', line=dict(color='#E0E0E0', width=1)
                )
            )])

            fig_tab.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=400)
            st.plotly_chart(fig_tab, use_container_width=True, theme="streamlit")
            
    except Exception as e:
        st.error(f"Berechnungsfehler: {e}")
        st.info("Tipp: Wenn du über den Druck steuerst, stelle sicher, dass dieser innerhalb der Sättigungsgrenzen (zwischen Tripel- und kritischem Punkt) des gewählten Kältemittels liegt.")

    # Parameterstudie Kälteanlagen/WP
    st.divider()
    bautyp_text = "zweistufigen" if is_2stage else "einstufigen"
    st.subheader(f"Parameterstudie: COP (Wärmepumpe) vs. EER (Kältemaschine)")
    st.write(f"Einfluss der Temperaturniveaus auf die Effizienz im **{bautyp_text}** Betrieb. Der graue Bereich markiert die absolute technische Grenze durch Ölzersetzung im Verdichter (Heißgastemperatur $> 120 °C$).")
    
    if st.button("Parameterfelder berechnen (Contour-Plots)"):
        with st.spinner(f"Berechne Leistungsfelder ({bautyp_text}) inklusive Verdichterschutz..."):
            
            safe_sh_mode = sh_mode if has_sh else None
            safe_dT_sh_input = dT_sh_input if (has_sh and sh_mode == "um (ΔT)") else 0.0
            safe_T_sh_input = T_sh_input if (has_sh and sh_mode == "auf (T)") else 0.0

            safe_sc_mode = sc_mode if has_sc else None
            safe_dT_sc_input = dT_sc_input if (has_sc and sc_mode == "um (ΔT)") else 0.0
            safe_T_sc_input = T_sc_input if (has_sc and sc_mode == "auf (T)") else 0.0

            cop_heiz_grid, eer_kalt_grid, T_verd_arr, T_kond_arr, n_failed = berechne_effizienzfelder(
                fluid, is_2stage, has_mdf, mdf_mode_key, has_zk, T_zk_input, eta_is_nd, eta_is_hd,
                has_sh, safe_sh_mode, safe_dT_sh_input, safe_T_sh_input,
                has_sc, safe_sc_mode, safe_dT_sc_input, safe_T_sc_input
            )

            if n_failed:
                st.caption(f"Hinweis: {n_failed} von {cop_heiz_grid.size} Gitterpunkten sind nicht konvergiert und wurden ausgeblendet.")

            # Plot 1: Wärmepumpe
            fig_heiz = go.Figure(data=go.Contour(
                z=cop_heiz_grid, x=T_verd_arr, y=T_kond_arr,
                colorscale="Inferno", 
                colorbar=dict(title="COP<sub>Heiz</sub>"),
                connectgaps=False, 
                zmin=0,   
                zmax=10,  
                contours=dict(start=0, end=10, size=0.5),
                hovertemplate="T<sub>0</sub>: %{x:.1f} °C<br>T<sub>c</sub>: %{y:.1f} °C<br>COP<sub>Heiz</sub>: %{z:.2f}<extra></extra>"
            ))
            fig_heiz.update_layout(
                title=f"Wärmepumpe ({bautyp_text})",
                xaxis_title="Verdampfungstemperatur T<sub>0</sub> (°C)",
                yaxis_title="Kondensationstemperatur T<sub>c</sub> (°C)",
                height=500, margin=dict(l=40, r=40, t=60, b=40)
            )

            # Plot 2: Kältemaschine
            fig_kalt = go.Figure(data=go.Contour(
                z=eer_kalt_grid, x=T_verd_arr, y=T_kond_arr,
                colorscale="Viridis", 
                colorbar=dict(title="EER"),
                connectgaps=False, 
                zmin=0,   
                zmax=10,  
                contours=dict(start=0, end=10, size=0.5),
                hovertemplate="T<sub>0</sub>: %{x:.1f} °C<br>T<sub>c</sub>: %{y:.1f} °C<br>EER: %{z:.2f}<extra></extra>"
            ))
            fig_kalt.update_layout(
                title=f"Kältemaschine ({bautyp_text})",
                xaxis_title="Verdampfungstemperatur T<sub>0</sub> (°C)",
                yaxis_title="Kondensationstemperatur T<sub>c</sub> (°C)",
                height=500, margin=dict(l=40, r=40, t=60, b=40)
            )

            col_heiz, col_kalt = st.columns(2)
            with col_heiz:
                st.plotly_chart(fig_heiz, use_container_width=True, theme="streamlit")
            with col_kalt:
                st.plotly_chart(fig_kalt, use_container_width=True, theme="streamlit")
