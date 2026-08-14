import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import CoolProp.CoolProp as CP
from backend_rankine import ClausiusRankineProzess 
from frontend_kaelte_svg import generate_svg
from backend_kaelte import KaelteKreisprozess

# ==========================================
# 0. SEITENKONFIGURATION & CSS
# ==========================================
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

# ==========================================
# 1. SESSION STATE & HILFSFUNKTIONEN
# ==========================================
initial_values = {
    "p_verd": 100.0,
    "t_frisch": 450.0,
    "p_kond": 0.5,
    "eta_p": 1.0,  
    "eta_t": 1.0,
    "j_T1": 21.0,
    "j_p1": 1.03,
    "j_T3": 1010.0,
    "j_pi": 6.9,
    "j_m_dot": 1.12
}

for key, val in initial_values.items():
    if f"{key}_slider" not in st.session_state:
        st.session_state[f"{key}_slider"] = val
    if f"{key}_input" not in st.session_state:
        st.session_state[f"{key}_input"] = val

def sync_values(changed_key, target_key):
    st.session_state[target_key] = st.session_state[changed_key]

def create_synced_input(label, key, min_val, max_val, step, format="%.2f"):
    st.sidebar.markdown(f"**{label}**")
    col1, col2 = st.sidebar.columns([3, 2])
    with col1:
        st.slider(
            label, min_value=min_val, max_value=max_val, step=step,
            key=f"{key}_slider", 
            on_change=sync_values, args=(f"{key}_slider", f"{key}_input"), 
            label_visibility="collapsed"
        )
    with col2:
        st.number_input(
            label, min_value=min_val, max_value=max_val, step=step, format=format,
            key=f"{key}_input", 
            on_change=sync_values, args=(f"{key}_input", f"{key}_slider"), 
            label_visibility="collapsed"
        )
    st.sidebar.write("")

# ==========================================
# NAVIGATION (SIDEBAR)
# ==========================================
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

# ==========================================
# 2. CLAUSIUS-RANKINE-PROZESS
# ==========================================
if prozess_auswahl == "Clausius-Rankine-Prozess":
    st.title("Clausius-Rankine-Prozess (Dampfkraftwerk)")
    st.write("Vergleich: Idealer (reversibler) vs. Realer (irreversibler) Kreisprozess.")
    
    st.sidebar.header("Anlagenkonfiguration")
    ignore_pump = st.sidebar.checkbox("Vernachlässigung der Pumpenarbeit", value=False, help="Setzt die Enthalpieänderung der Pumpe auf 0")
    has_zue = st.sidebar.checkbox("Zwischenüberhitzung (ZÜ)", value=False)
    
    st.sidebar.divider()
    
    st.sidebar.header("Zustandsgrößen")
    create_synced_input("Kondensatordruck $p_{kond}$ (bar)", "cr_p1", 0.02, 1.0, 0.01)
    create_synced_input("Kesseldruck $p_{kessel}$ (bar)", "cr_p2", 10.0, 300.0, 5.0)
    create_synced_input("Frischdampftemp. $T_{max}$ (°C)", "cr_T3", 200.0, 600.0, 10.0)
    
    p_kond = st.session_state.cr_p1_input
    p_verd = st.session_state.cr_p2_input
    T_max = st.session_state.cr_T3_input
    
    if has_zue:
        st.sidebar.markdown("**Zwischenüberhitzung**")
        p_zue = st.sidebar.slider("Zwischendruck $p_{ZÜ}$ (bar)", min_value=float(p_kond)+0.1, max_value=float(p_verd)-1.0, value=float(p_verd)/2, step=1.0)
        T_zue = st.sidebar.slider("Zwischentemperatur $T_{ZÜ}$ (°C)", min_value=200.0, max_value=float(T_max), value=float(T_max), step=10.0)
    else:
        p_zue, T_zue = None, None
        
    st.sidebar.divider()
    create_synced_input(r"Massenstrom $\dot{m}$ (kg/s)", "cr_m_dot", 1.0, 100.0, 1.0)
    
    st.sidebar.divider()
    st.sidebar.header("Reale Verluste")
    eta_s_P = st.sidebar.slider(r"Isentroper Wirkungsgrad Pumpe $\eta_{s,P}$ (%)", 50.0, 100.0, 80.0, 1.0) / 100
    eta_s_T = st.sidebar.slider(r"Isentroper Wirkungsgrad Turbine $\eta_{s,T}$ (%)", 50.0, 100.0, 85.0, 1.0) / 100
    
    m_dot = st.session_state.cr_m_dot_input
    
    try:
        cr_prozess = ClausiusRankineProzess(
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
        
        st.subheader("Reale Ergebnisse für Wasser/Dampf")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(r"Wirkungsgrad $\eta_{th}$", f"{eta_th_real * 100:.2f} %")
        col2.metric(r"Spez. Arbeit $w_{net}$", f"{w_net_real:.2f} kJ/kg")
        col3.metric(r"Spez. Zu-Wärme $q_{zu}$", f"{cr_prozess.q_zu:.2f} kJ/kg")
        col4.metric(r"Druckverh. $\pi$", f"{pi:.1f}")
        
        col5, col6, col7, _ = st.columns([1, 1, 1, 1])
        col5.metric(r"Temp.-Verh. $\tau$", f"{tau:.2f}")
        col6.metric(r"Turbine(n) $P_T$", f"{P_tT_real:.0f} kW")
        col7.metric(r"Pumpe $P_P$", f"{-P_tP_real:.0f} kW")
        
        fig = make_subplots(
            rows=2, cols=1, 
            shared_xaxes=False, vertical_spacing=0.1,
            specs=[[{"type": "scatter"}], [{"type": "table"}]], row_heights=[0.75, 0.25]
        )
        
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
        
        # --- PARAMETERSTUDIE ---
        if has_zue:
            st.divider()
            st.subheader("Parameterstudie: Einfluss der Zwischenüberhitzung")
            st.write("Untersuche den thermischen Wirkungsgrad $\eta_{th}$ in Abhängigkeit von Zwischendruck und Zwischentemperatur. Graue/Leere Bereiche markieren technisch unzulässige Betriebspunkte. Ausschlusskriterien: 1. Tropfenschlag ($x < 0,88$ am ND-Austritt) und 2. Fehlende Erwärmung ($T_{ZÜ} \le T_{HD,aus}$).")
            
            if st.button("Parameterfeld berechnen (Contour-Plot erstellen)"):
                with st.spinner("Berechne Wirkungsgradfeld inklusive Turbinenschutz..."):
                    # 1. Auflösung massiv erhöhen (z. B. 80 statt 25 Punkte) für flüssiges Hovern
                    # und Startdruck leicht anheben (z.B. auf 1.0 bar oder p_kond*2), 
                    # um das extreme Randphänomen nahe 0 bar zu dämpfen.
                    p_zue_arr = np.linspace(max(1.0, p_kond*2), p_verd*0.9, 80) 
                    T_zue_arr = np.linspace(200.0, T_max, 80)
                    eta_grid = np.zeros((len(T_zue_arr), len(p_zue_arr)))
                    
                    for i, T_z in enumerate(T_zue_arr):
                        for j, p_z in enumerate(p_zue_arr):
                            temp_prozess = ClausiusRankineProzess(
                                p_kond=p_kond, p_kessel=p_verd, T_max=T_max, m_dot=m_dot, 
                                eta_s_P=eta_s_P, eta_s_T=eta_s_T, ignore_pump=ignore_pump, 
                                has_zue=True, p_zue=p_z, T_zue=T_z
                            )
                            try:
                                temp_prozess.berechne_zustaende()
                                
                                # --- NEUER FILTER 1: Findet wirklich eine Überhitzung statt? ---
                                h2 = temp_prozess.zustand['2']['h']
                                # p_z aus der Schleife ist in bar, CoolProp braucht Pascal
                                T2_C = CP.PropsSI('T', 'P', p_z * 100000, 'H', h2, temp_prozess.fluid) - 273.15
                                
                                # Wenn die ZÜ-Temperatur kleiner/gleich der HD-Austrittstemperatur ist -> ignorieren
                                if T_z <= T2_C:
                                    eta_grid[i, j] = None
                                    continue # Überspringt den Rest und geht direkt zum nächsten Punkt
                                
                                # --- BESTEHENDER FILTER 2: Turbinenschutz (Tropfenschlag) ---
                                h4 = temp_prozess.zustand['4']['h']
                                p_kond_pa = temp_prozess.p_kond # Ist bereits in Pascal
                                hf = CP.PropsSI('H', 'P', p_kond_pa, 'Q', 0, temp_prozess.fluid)
                                hg = CP.PropsSI('H', 'P', p_kond_pa, 'Q', 1, temp_prozess.fluid)
                                x4 = (h4 - hf) / (hg - hf)
                                
                                if x4 < 0.88:
                                    eta_grid[i, j] = None 
                                else:
                                    eta_grid[i, j] = temp_prozess.wirkungsgrad * 100
                            except:
                                eta_grid[i, j] = None
                                
                    fig_contour = go.Figure(data=go.Contour(
                        z=eta_grid, x=p_zue_arr, y=T_zue_arr,
                        colorscale="Viridis",
                        colorbar=dict(title="η<sub>th</sub> (%)"), # <-- Hier das HTML-Tag eingefügt
                        connectgaps=False, 
                        hovertemplate="p_ZÜ: %{x:.1f} bar<br>T_ZÜ: %{y:.1f} °C<br>η<sub>th</sub>: %{z:.2f} %<extra></extra>" # <-- Hier auch direkt für das Hover-Feld angepasst
                    ))
                    # 2. HTML-Tags <sub> für tiefgestellte Buchstaben nutzen
                    fig_contour.update_layout(
                        xaxis_title="Zwischendruck p<sub>ZÜ</sub> (bar)",
                        yaxis_title="Zwischentemperatur T<sub>ZÜ</sub> (°C)",
                        height=550, margin=dict(l=40, r=40, t=40, b=40)
                    )
                    st.plotly_chart(fig_contour, use_container_width=True, theme="streamlit")
        
    except Exception as e:
        st.error(f"Fehler bei der Berechnung des Clausius-Rankine-Prozesses: {e}")
        st.info("Bitte überprüfe die Eingabeparameter.")

# ==========================================
# 3. JOULE-PROZESS
# ==========================================
elif prozess_auswahl == "Joule-Prozess (Gasturbine)":
    st.title("Joule-Prozess (Offene Gasturbine)")
    st.write("Vergleich: Idealer (reversibler) vs. Realer (irreversibler) Kreisprozess.")
    
    st.sidebar.header("Anlagenkonfiguration")
    fluid_name = st.sidebar.selectbox("Arbeitsfluid", ["Luft (zweiatomig)", "Helium (einatomig)", "Argon (einatomig)", "R744 (CO2)"])
    
    st.sidebar.header("Zustandsgrößen")
    create_synced_input("Ansaugtemperatur $T_1$ (°C)", "j_T1", -20.0, 50.0, 1.0)
    create_synced_input("Ansaugdruck $p_1$ (bar)", "j_p1", 0.8, 1.2, 0.01)
    create_synced_input("Max. Prozesstemp. $T_3$ (°C)", "j_T3", 500.0, 1500.0, 10.0)
    
    T1_c = st.session_state.j_T1_input
    T3_c = st.session_state.j_T3_input
    T1 = T1_c + 273.15
    T3 = T3_c + 273.15
    
    var_cp_mode = False
    if fluid_name == "Luft (zweiatomig)":
        var_cp_mode = st.sidebar.checkbox(r"Temp.-abhängige Stoffwerte ($\kappa_m$) nutzen", value=False)
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
    eta_s_V = st.sidebar.slider(r"Isentroper Wirkungsgrad Verdichter $\eta_{s,V}$ (%)", 50.0, 100.0, 85.0, 1.0) / 100
    eta_s_T = st.sidebar.slider(r"Isentroper Wirkungsgrad Turbine $\eta_{s,T}$ (%)", 50.0, 100.0, 88.0, 1.0) / 100
    
    st.sidebar.divider()
    
    opt_mode = st.sidebar.toggle("Optimierungs-Modus (max. Arbeit)")
    if opt_mode:
        tau = T3 / T1
        pi = tau ** (kappa / (2 * (kappa - 1)))
        st.sidebar.success(f"Optimiertes Druckverhältnis $\pi$: **{pi:.2f}**")
    else:
        create_synced_input(r"Druckverhältnis $\pi$", "j_pi", 2.0, 30.0, 0.1)
        pi = st.session_state.j_pi_input
        
    create_synced_input(r"Massenstrom $\dot{m}$ (kg/s)", "j_m_dot", 0.1, 5.0, 0.01)
    
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
        col1.metric(r"Wirkungsgrad $\eta_{th}$", f"{eta_th_real * 100:.2f} %")
        col2.metric(r"Spez. Arbeit $w_{net}$", f"{w_net_real:.2f} kJ/kg")
        col3.metric(r"Arbeitsverh. $\omega$", f"{omega_real:.2f}")
        col4.metric(r"Turbine $P_T$", f"{P_tT_real:.0f} kW")
        col5.metric(r"Verdichter $P_V$", f"{P_tV_real:.0f} kW")
    
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

# ==========================================
# 4. KÄLTEANLAGE
# ==========================================
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
    
    import CoolProp.CoolProp as CP
    all_fluids = sorted(CP.FluidsList())
    default_index = all_fluids.index("R134a") if "R134a" in all_fluids else 0
    fluid = st.sidebar.selectbox("Kältemittel", all_fluids, index=default_index)
    
    kaelte_init = {
        "k_t0": -10.0, "k_tc": 40.0, "k_tm": 10.0,
        "k_p0": 2.0, "k_pc": 10.0, "k_pm": 5.0,
        "k_tzk": 25.0,
        "k_eta": 80.0, "k_eta_nd": 80.0, "k_eta_hd": 80.0
    }
    for k, v in kaelte_init.items():
        if f"{k}_slider" not in st.session_state:
            st.session_state[f"{k}_slider"] = v
            st.session_state[f"{k}_input"] = v

    st.sidebar.markdown("---")
    
    st.sidebar.markdown("**Verdampfung (Niederdruck)**")
    eingabe_modus_0 = st.sidebar.radio("Modus Verdampfung", ["Temperatur (°C)", "Druck (bar)"], horizontal=True, label_visibility="collapsed")
    if eingabe_modus_0 == "Temperatur (°C)":
        create_synced_input("Verdampfungstemp. $T_0$ (°C)", "k_t0", -80.0, 50.0, 1.0, format="%.1f")
    else:
        create_synced_input("Verdampfungsdruck $p_0$ (bar)", "k_p0", 0.1, 80.0, 0.1, format="%.2f")

    st.sidebar.markdown("**Kondensation (Hochdruck)**")
    eingabe_modus_c = st.sidebar.radio("Modus Kondensation", ["Temperatur (°C)", "Druck (bar)"], horizontal=True, label_visibility="collapsed")
    if eingabe_modus_c == "Temperatur (°C)":
        create_synced_input("Kondensationstemp. $T_c$ (°C)", "k_tc", -20.0, 90.0, 1.0, format="%.1f")
    else:
        create_synced_input("Kondensationsdruck $p_c$ (bar)", "k_pc", 0.5, 150.0, 0.5, format="%.2f")

    opt_pm = False
    if is_2stage:
        st.sidebar.markdown("**Zwischenstufe (Mitteldruck)**")
        opt_pm = st.sidebar.checkbox("Optimalen Mitteldruck berechnen", value=False, help="Berechnet automatisch $p_m$ = √($p_0$ · $p_c$)")
        
        if not opt_pm:
            eingabe_modus_m = st.sidebar.radio("Modus Zwischenstufe", ["Temperatur (°C)", "Druck (bar)"], horizontal=True, label_visibility="collapsed")
            if eingabe_modus_m == "Temperatur (°C)":
                create_synced_input("Zwischentemp. $T_m$ (°C)", "k_tm", -40.0, 60.0, 1.0, format="%.1f")
            else:
                create_synced_input("Zwischendruck $p_m$ (bar)", "k_pm", 0.2, 100.0, 0.5, format="%.2f")
        
        if has_zk:
            st.sidebar.markdown("**Äußere Zwischenkühlung (ZK)**")
            create_synced_input("Temp. nach ZK $T_{2zk}$ (°C)", "k_tzk", -30.0, 80.0, 1.0, format="%.1f")
            T_zk_input = st.session_state.k_tzk_input
        else:
            T_zk_input = None
    
    st.sidebar.markdown("---")
    
    st.sidebar.markdown("**Überhitzung (Sauggas)**")
    has_sh = st.sidebar.checkbox("Überhitzung aktiv", value=True)
    if has_sh:
        sh_mode = st.sidebar.radio("Art der Überhitzung", ["um (ΔT)", "auf (T)"], horizontal=True, label_visibility="collapsed")
        if sh_mode == "um (ΔT)":
            dT_sh_input = st.sidebar.number_input(r"$\Delta T_{sh}$ (K)", value=5.0, min_value=0.0, step=1.0)
            T_sh_input = None
        else:
            T_sh_input = st.sidebar.number_input("Sauggastemperatur $T_1$ (°C)", value=-5.0, step=1.0)
            dT_sh_input = None

    st.sidebar.markdown("**Unterkühlung (Kondensat)**")
    has_sc = st.sidebar.checkbox("Unterkühlung aktiv", value=True)
    if has_sc:
        sc_mode = st.sidebar.radio("Art der Unterkühlung", ["um (ΔT)", "auf (T)"], horizontal=True, label_visibility="collapsed")
        t_sub_label = "Flüssigkeitstemp. $T_5$ (°C)" if is_2stage else "Flüssigkeitstemp. $T_3$ (°C)"
        
        if sc_mode == "um (ΔT)":
            dT_sc_input = st.sidebar.number_input(r"$\Delta T_{sc}$ (K)", value=2.0, min_value=0.0, step=1.0)
            T_sc_input = None
        else:
            T_sc_input = st.sidebar.number_input(t_sub_label, value=38.0, step=1.0)
            dT_sc_input = None

    st.sidebar.divider()
    
    st.sidebar.header("3. Reale Verluste")
    if is_2stage:
        create_synced_input(r"Wirkungsgrad ND-Verdichter $\eta_{is,ND}$ (%)", "k_eta_nd", 30.0, 100.0, 1.0, format="%.0f")
        create_synced_input(r"Wirkungsgrad HD-Verdichter $\eta_{is,HD}$ (%)", "k_eta_hd", 30.0, 100.0, 1.0, format="%.0f")
        eta_is_nd = st.session_state.k_eta_nd_input / 100.0
        eta_is_hd = st.session_state.k_eta_hd_input / 100.0
    else:
        create_synced_input(r"Isentroper Verdichter-Wirkungsgrad $\eta_{is}$ (%)", "k_eta", 30.0, 100.0, 1.0, format="%.0f")
        eta_is_nd = st.session_state.k_eta_input / 100.0
        eta_is_hd = eta_is_nd 
    
    col_img, col_diag = st.columns([1, 1.5])
    
    with col_img:
        st.subheader("Anlagenschema")
        svg_code, svg_height = generate_svg(is_2stage, has_mdf, has_zk, mdf_mode_key)
        components.html(
            f'<div style="display:flex; justify-content:center; background:#111; padding:20px; border-radius:8px;">{svg_code}</div>', 
            height=svg_height+60, 
            scrolling=False
        )

    with col_diag:
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
                    st.info(f"💡 **Optimaler Mitteldruck aktiv:** $p_m$ = {p_m_bar:.2f} bar (entspricht $T_m$ = {T_m_C:.1f} °C)")
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
                        st.warning(f"⚠️ Die eingestellte Sauggastemperatur ({T_sh_input} °C) liegt unter der Verdampfungstemperatur $T_0$ ({T_0_C:.1f} °C). Überhitzung wird auf 0 K gesetzt.")
                        dT_sh = 0.0

            dT_sc = 0.0
            if has_sc:
                if sc_mode == "um (ΔT)":
                    dT_sc = dT_sc_input
                else:
                    dT_sc = T_c_C - T_sc_input
                    if dT_sc < 0:
                        st.warning(f"⚠️ Die eingestellte Flüssigkeitstemperatur liegt über der Kondensationstemperatur $T_c$ ({T_c_C:.1f} °C). Unterkühlung wird auf 0 K gesetzt.")
                        dT_sc = 0.0

            kaelte_prozess = KaelteKreisprozess(fluid=fluid, T_0_C=T_0_C, T_c_C=T_c_C, T_m_C=T_m_C, dT_sh=dT_sh, dT_sc=dT_sc, eta_is_nd=eta_is_nd, eta_is_hd=eta_is_hd)
            
            if is_2stage:
                if has_zk and T_zk_input is not None:
                    T_sat_m = CP.PropsSI('T', 'P', kaelte_prozess.p_m, 'Q', 1, fluid) - 273.15
                    if T_zk_input < T_sat_m:
                        st.warning(f"⚠️ Die eingestellte ZK-Temperatur ({T_zk_input} °C) liegt unter der Sättigungstemperatur ({T_sat_m:.2f} °C) bei Mitteldruck. Das Gas würde kondensieren. Die Temperatur wird auf den Taupunkt begrenzt.")
                
                kaelte_prozess.berechne_zweistufig(has_mdf=has_mdf, mdf_mode=mdf_mode_key, has_zk=has_zk, T_2zk_C=T_zk_input)
            else:
                kaelte_prozess.berechne_einstufig()
            
            st.subheader("Leistungskennzahlen")
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Leistungszahl (EER)", f"{kaelte_prozess.cop:.2f}")
            kpi2.metric(r"Spez. Kälteleistung $q_0$", f"{kaelte_prozess.q_0:.2f} kJ/kg")
            kpi3.metric(r"Spez. Verdichterarbeit $w_c$", f"{kaelte_prozess.w_c:.2f} kJ/kg")
            
            if is_2stage and has_zk:
                st.info(f"Die äußere Zwischenkühlung führt **$q_{{zk}}$ = {kaelte_prozess.q_zk:.2f} kJ/kg** Wärme ab.")

            if is_2stage and has_mdf:
                st.subheader("Massenstromverhältnisse")
                st.caption("Bezogen auf 1 kg/s im Hochdruckkreislauf")
                
                if mdf_mode_key == "partiell":
                    # Partiell: Zeige alle drei Massenströme (HD, ND, Bypass)
                    m1, m2, m3 = st.columns(3)
                    m1.metric(r"$\mu_{HD}$ (Hochdruck)", f"{kaelte_prozess.m_hd:.3f} kg/kg")
                    m2.metric(r"$\mu_{ND}$ (Niederdruck)", f"{kaelte_prozess.m_nd:.3f} kg/kg")
                    m3.metric(r"$\mu_{Bypass}$ (Flashgas)", f"{kaelte_prozess.m_bypass:.3f} kg/kg")
                else:
                    # Quenchen: Zeige nur HD und ND an
                    m1, m2 = st.columns(2)
                    m1.metric(r"$\mu_{HD}$ (Hochdruck)", f"{kaelte_prozess.m_hd:.3f} kg/kg")
                    m2.metric(r"$\mu_{ND}$ (Niederdruck)", f"{kaelte_prozess.m_nd:.3f} kg/kg")
            
            h_g, s_g, T_g, p_g = kaelte_prozess.get_saettigungslinie()
            h_id, s_id, T_id, p_id = kaelte_prozess.get_plot_linien_ideal()
            h_re, s_re, T_re, p_re = kaelte_prozess.get_plot_linien_real()
            h_pts, s_pts, T_pts, p_pts, hover_pts, pt_keys = kaelte_prozess.get_eckpunkte_daten()
            
            marker_colors = ['#888888' if 's' in k else '#0068C9' for k in pt_keys]
            
            st.subheader("Thermodynamik")
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
                    height=500, hovermode="closest", margin=dict(l=40, r=40, t=40, b=40),
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
                    height=500, hovermode="closest", margin=dict(l=40, r=40, t=40, b=40),
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

# ==========================================
    # --- PARAMETERSTUDIE: KÄLTEKREIS / WÄRMEPUMPE ---
    # ==========================================
    st.divider()
    bautyp_text = "zweistufigen" if is_2stage else "einstufigen"
    st.subheader(f"Parameterstudie: COP (Wärmepumpe) vs. EER (Kältemaschine)")
    st.write(f"Einfluss der Temperaturniveaus auf die Effizienz im **{bautyp_text}** Betrieb. Der graue Bereich markiert die absolute technische Grenze durch Ölzersetzung im Verdichter (Heißgastemperatur $> 120 °C$).")
    
    if st.button("Parameterfelder berechnen (Contour-Plots)"):
        with st.spinner(f"Berechne Leistungsfelder ({bautyp_text}) inklusive Verdichterschutz..."):
            T_verd_arr = np.linspace(-75.0, 20.0, 60) 
            T_kond_arr = np.linspace(25.0, 75.0, 60)  
            
            cop_heiz_grid = np.zeros((len(T_kond_arr), len(T_verd_arr)))
            eer_kalt_grid = np.zeros((len(T_kond_arr), len(T_verd_arr)))
            
            for i, T_k in enumerate(T_kond_arr):
                for j, T_v in enumerate(T_verd_arr):
                    
                    if T_v >= T_k:
                        cop_heiz_grid[i, j] = None
                        eer_kalt_grid[i, j] = None
                        continue
                    
                    try:
                        # Für 2-stufig: Optimalen Mitteldruck für jeden Gitterpunkt dynamisch berechnen
                        if is_2stage:
                            p_0_temp = CP.PropsSI('P', 'T', T_v + 273.15, 'Q', 1, fluid)
                            p_c_temp = CP.PropsSI('P', 'T', T_k + 273.15, 'Q', 0, fluid)
                            p_m_opt = np.sqrt(p_0_temp * p_c_temp)
                            T_m_opt_C = CP.PropsSI('T', 'P', p_m_opt, 'Q', 1, fluid) - 273.15
                        else:
                            T_m_opt_C = None

                        # Konstante Werte für Überhitzung (5K) und Unterkühlung (2K)
                        temp_prozess = KaelteKreisprozess(
                            fluid=fluid, 
                            T_0_C=T_v, 
                            T_c_C=T_k, 
                            T_m_C=T_m_opt_C,     # Dynamischer Mitteldruck (nur relevant falls 2-stufig)
                            dT_sh=5.0,           
                            dT_sc=2.0,           
                            eta_is_nd=eta_is_nd, 
                            eta_is_hd=eta_is_hd  # Nutzt globalen Wert aus UI
                        )
                    
                        # Berechnung je nach UI-Auswahl
                        if is_2stage:
                            temp_prozess.berechne_zweistufig(
                                has_mdf=has_mdf, 
                                mdf_mode=mdf_mode_key, 
                                has_zk=has_zk, 
                                T_2zk_C=T_zk_input
                            )
                            # Verdichterschutz: Bei 2-stufig müssen BEIDE Verdichter geprüft werden
                            T_heissgas_ND_C = temp_prozess.zustand['2']['T'] - 273.15
                            T_heissgas_HD_C = temp_prozess.zustand['4']['T'] - 273.15
                            T_heissgas_max = max(T_heissgas_ND_C, T_heissgas_HD_C)
                        else:
                            temp_prozess.berechne_einstufig()
                            T_heissgas_max = temp_prozess.zustand['2']['T'] - 273.15
                        
                        # Filter anwenden
                        if T_heissgas_max > 120.0:
                            cop_heiz_grid[i, j] = None 
                            eer_kalt_grid[i, j] = None
                        else:
                            # Backend liefert Kälte-COP (EER). Heiz-COP ist EER + 1
                            eer_kalt_grid[i, j] = temp_prozess.cop
                            cop_heiz_grid[i, j] = temp_prozess.cop + 1.0 
                    except:
                        # Falls CoolProp bei extremen Kombinationen nicht konvergiert
                        cop_heiz_grid[i, j] = None
                        eer_kalt_grid[i, j] = None
                        
            # --- Plot 1: Wärmepumpe (Heizen) ---
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

            # --- Plot 2: Kältemaschine (Kühlen) ---
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

            # --- Darstellung in zwei Spalten nebeneinander ---
            col_heiz, col_kalt = st.columns(2)
            with col_heiz:
                st.plotly_chart(fig_heiz, use_container_width=True, theme="streamlit")
            with col_kalt:
                st.plotly_chart(fig_kalt, use_container_width=True, theme="streamlit")