import math
import re

WHITE = "#ffffff"
GREEN = "#3fae4a"
BLUE = "#3f7fd6"
RED = "#d64b3f" 
PURPLE = "#9a4fd6" 

def line(x1, y1, x2, y2, color=WHITE, width=3):
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>'

def polyline(points, color=WHITE, width=3):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>'

def text(x, y, s, size=15, anchor="middle", color=WHITE, weight="normal"):

    s_formatted = re.sub(r'_([a-zA-Z0-9]+)', r'<tspan baseline-shift="sub" font-size="0.75em">\1</tspan>', s)
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-family="Arial, sans-serif" font-weight="{weight}">{s_formatted}</text>'

def flow_label(p1, p2, s, color=WHITE, dy=-10):
    mx = (p1[0] + p2[0]) / 2
    my = (p1[1] + p2[1]) / 2
    return text(mx, my + dy, s, 13, "middle", color)

def side_label(x_line, y, s, side="left", color=WHITE, tick=5, offset=22):
    if side == "left":
        x_text = x_line - offset
        x_tick = x_line - tick
        anchor = "end"
    else:
        x_text = x_line + offset
        x_tick = x_line + tick
        anchor = "start"
    svg = line(x_line, y, x_tick, y, color, 1.5)
    svg += text(x_text, y + 4, s, 12, anchor, color)
    return svg

def path_label(points, s, color=WHITE, dy=-10):
    best = None
    best_len = -1
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        l = math.hypot(b[0] - a[0], b[1] - a[1])
        if l > best_len:
            best_len = l
            best = (a, b)
    return flow_label(best[0], best[1], s, color, dy)

def state_marker(x, y, num):
    """Zeichnet einen Zustandspunkt punktgenau auf die Linie."""
    svg = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="{WHITE}" stroke="#111" stroke-width="1.5"/>'
    svg += f'<text x="{x:.1f}" y="{y+4.5:.1f}" font-size="13" fill="#111" text-anchor="middle" font-family="Arial, sans-serif" font-weight="bold">{num}</text>'
    return svg

def mass_flow_marker(x, y, label, direction="down", color=WHITE):
    """Zeichnet einen Pfeil mit Beschriftung für den Massenstrom (μ)"""
    svg = ""
    if direction == "down":
        svg += line(x, y-12, x, y+12, color, 1.5)
        svg += polyline([(x-4, y+6), (x, y+12), (x+4, y+6)], color, 1.5)
        svg += text(x + 10, y + 4, label, 15, "start", color, weight="bold")
    elif direction == "up":
        svg += line(x, y-12, x, y+12, color, 1.5)
        svg += polyline([(x-4, y-6), (x, y-12), (x+4, y-6)], color, 1.5)
        svg += text(x + 10, y + 4, label, 15, "start", color, weight="bold")
    elif direction == "right":
        svg += line(x-12, y, x+12, y, color, 1.5)
        svg += polyline([(x+6, y-4), (x+12, y), (x+6, y+4)], color, 1.5)
        svg += text(x, y - 10, label, 15, "middle", color, weight="bold")
    elif direction == "left":
        svg += line(x-12, y, x+12, y, color, 1.5)
        svg += polyline([(x-6, y-4), (x-12, y), (x-6, y+4)], color, 1.5)
        svg += text(x, y - 10, label, 15, "middle", color, weight="bold")
    return svg

def heat_exchanger(cx, cy, name, fill):
    w, h = 170, 110
    x, y = cx - w / 2, cy - h / 2
    svg = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" fill="{fill}" stroke="{WHITE}" stroke-width="2" rx="6"/>'
    r = 32
    fcy = cy - 6
    svg += f'<circle cx="{cx:.1f}" cy="{fcy:.1f}" r="{r}" fill="none" stroke="{WHITE}" stroke-width="2"/>'
    for ang in (90, 210, 330):
        a = math.radians(ang)
        x2 = cx + r * 0.85 * math.cos(a)
        y2 = fcy + r * 0.85 * math.sin(a)
        cxr = cx + r * 0.35 * math.cos(a + 1.0)
        cyr = fcy + r * 0.35 * math.sin(a + 1.0)
        svg += f'<path d="M {cx:.1f} {fcy:.1f} Q {cxr:.1f} {cyr:.1f} {x2:.1f} {y2:.1f}" stroke="{WHITE}" stroke-width="2.2" fill="none"/>'
    for i in range(5):
        fx = x + 18 + i * (w - 36) / 4
        svg += line(fx, y + h, fx, y + h + 12, WHITE, 2)
    svg += text(cx, y + h + 32, name, 16, weight="bold")
    return svg

def compressor(cx, cy, name, r=48):
    svg = f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="#2b2b2b" stroke="{WHITE}" stroke-width="2.2"/>'
    tx, ty = cx, cy - r + 10
    bx1, by1 = cx - r + 14, cy + r - 12
    bx2, by2 = cx + r - 14, cy + r - 12
    svg += f'<path d="M {tx:.1f} {ty:.1f} L {bx1:.1f} {by1:.1f}" stroke="{WHITE}" stroke-width="2.2" fill="none"/>'
    svg += f'<path d="M {tx:.1f} {ty:.1f} L {bx2:.1f} {by2:.1f}" stroke="{WHITE}" stroke-width="2.2" fill="none"/>'
    svg += line(cx, cy - r + 10, cx, cy + r - 10, WHITE, 2.2)
    svg += text(cx, cy + r + 24, name, 16, weight="bold")
    return svg

def expansion_valve(cx, cy, name="E"):
    s = 20
    p1 = f"{cx-s},{cy-s} {cx},{cy} {cx-s},{cy+s}"
    p2 = f"{cx+s},{cy-s} {cx},{cy} {cx+s},{cy+s}"
    svg = f'<polygon points="{p1}" fill="none" stroke="{WHITE}" stroke-width="2.2"/>'
    svg += f'<polygon points="{p2}" fill="none" stroke="{WHITE}" stroke-width="2.2"/>'
    bulb_x = cx + s + 34
    svg += f'<circle cx="{bulb_x:.1f}" cy="{cy:.1f}" r="15" fill="none" stroke="{WHITE}" stroke-width="2.2"/>'
    svg += line(cx + s, cy, bulb_x - 15, cy, WHITE, 2)
    svg += text(bulb_x + 26, cy + 5, name, 16, "start", weight="bold")
    return svg

def reservoir(cx, cy, name="MDF"):
    w, h = 56, 92
    x, y = cx - w / 2, cy - h / 2
    svg = f'<rect x="{x:.1f}" y="{y+14:.1f}" width="{w}" height="{h-28}" fill="#2b2b2b" stroke="{WHITE}" stroke-width="2.2"/>'
    svg += f'<ellipse cx="{cx:.1f}" cy="{y+14:.1f}" rx="{w/2:.1f}" ry="14" fill="#2b2b2b" stroke="{WHITE}" stroke-width="2.2"/>'
    svg += f'<path d="M {x:.1f} {y+h-14:.1f} A {w/2:.1f} 14 0 0 0 {x+w:.1f} {y+h-14:.1f}" fill="none" stroke="{WHITE}" stroke-width="2.2"/>'
    svg += text(cx, y + h + 26, name, 15, weight="bold")
    return svg

def zk_box(cx, cy, name="Äußerer ZK"):
    w, h = 130, 60
    x, y = cx - w / 2, cy - h / 2
    svg = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" fill="#233022" stroke="{WHITE}" stroke-width="2.2" rx="6"/>'
    n = 6
    pts = []
    for i in range(n + 1):
        px = x + 10 + i * (w - 20) / n
        py = y + h / 2 + (16 if i % 2 == 0 else -16)
        pts.append((px, py))
    svg += polyline(pts, WHITE, 2)
    svg += text(cx, y + h + 24, name, 15, weight="bold")
    return svg

def generate_svg(is_2stage, has_mdf, has_zk, mdf_mode="partiell"):
    CANVAS_W = 1080
    left_x = 250
    right_x = 750 if (is_2stage and (has_mdf or has_zk)) else 650
    top_y = 100

    LANE_LIQUID  = left_x
    LANE_MDF_OUT = right_x - 240  
    LANE_MDF_IN  = right_x - 160  
    LANE_SUCTION = right_x - 100
    LANE_COMP    = right_x

    left_mid = ["D1"]
    if has_mdf:
        left_mid.append("MDF")
        left_mid.append("D2")

    right_mid = []
    if is_2stage:
        right_mid.append("VD_ND")
        if has_zk:
            right_mid.append("ZK")
        right_mid.append("VD_HD")
    else:
        right_mid.append("VD")

    row_gap = 195
    n_rows = max(len(left_mid), len(right_mid)) + 1
    bottom_y = top_y + row_gap * n_rows

    pos = {"K": (left_x, top_y), "V": (left_x, bottom_y)}

    n_l = len(left_mid)
    for i, node in enumerate(left_mid):
        frac = (i + 1) / (n_l + 1)
        pos[node] = (left_x, top_y + frac * (bottom_y - top_y))

    n_r = len(right_mid)
    if n_r == 1:
        pos[right_mid[0]] = (right_x, (top_y + bottom_y) / 2)
    else:
        for i, node in enumerate(right_mid):
            y = bottom_y + i * (top_y - bottom_y) / (n_r - 1)
            pos[node] = (right_x, y)

    R = 48  
    elements = []

    left_chain = ["K"] + left_mid + ["V"]
    for i in range(len(left_chain) - 1):
        a, b = left_chain[i], left_chain[i + 1]
        pa, pb = pos[a], pos[b]
        color = BLUE if b == "V" else GREEN
        elements.append(line(pa[0], pa[1], pb[0], pb[1], color, 3.5))
        lbl = None
        if a == "K" and b == "D1": lbl = "p_c  Flüssigkeit"
        elif a == "MDF" and b == "D2": lbl = "Flüssigkeit"
        elif b == "V": lbl = "Nassdampf  p_0"
        
        if lbl:
            mid_y = (pa[1] + pb[1]) / 2 + 15 
            elements.append(side_label(left_x, mid_y, lbl, "left", color))

        if is_2stage and has_mdf:
            marker_y = pb[1] - 45 
            if a == "K" and b == "D1":
                elements.append(mass_flow_marker(left_x + 35, marker_y, "μ_HD", "down", WHITE))
            elif a == "D2" and b == "V":
                elements.append(mass_flow_marker(left_x + 35, marker_y, "μ_ND", "down", WHITE))

    def mdf_ports():
        mcx, mcy = pos["MDF"]
        return {"gas_in": (mcx + 28, mcy + 20), "gas_out": (mcx + 28, mcy - 20)}

    first_right = right_mid[0]
    v_pos = pos["V"]
    target_pos = pos[first_right]
    rim_y_in = target_pos[1] + R + 15

    pts = [v_pos, (LANE_SUCTION, v_pos[1]), (LANE_SUCTION, rim_y_in), (target_pos[0], rim_y_in), (target_pos[0], target_pos[1] + R)]
    elements.append(polyline(pts, BLUE, 3.5))
    elements.append(side_label(LANE_SUCTION, (v_pos[1] + rim_y_in)/2, "Sauggas  p_0", "right", BLUE))

    if is_2stage and len(right_mid) >= 2:
        for i in range(len(right_mid) - 1):
            a, b = right_mid[i], right_mid[i + 1]
            pa, pb = pos[a], pos[b]

            if a == "VD_ND" and b == "ZK":
                elements.append(line(pa[0], pa[1]-R, pb[0], pb[1]+30, PURPLE, 3.5))
                elements.append(mass_flow_marker(pa[0], (pa[1]-R + pb[1]+30)/2, "μ_ND", "up", WHITE))

            elif a in ("VD_ND", "ZK") and b == "VD_HD" and has_mdf:
                ports = mdf_ports()
                rim_a = (pa[0], pa[1]-R) if a == "VD_ND" else (pa[0], pa[1]-30)
                rim_b = (pb[0], pb[1]+R)
                
                if mdf_mode == "vollstaendig":
                    pts1 = [rim_a, (rim_a[0], rim_a[1]-15), (LANE_MDF_IN, rim_a[1]-15), (LANE_MDF_IN, ports["gas_in"][1]), ports["gas_in"]]
                    elements.append(polyline(pts1, PURPLE, 3.5))
                    
                    mdf_in_x = (rim_a[0] + LANE_MDF_IN) / 2
                    mdf_in_y = rim_a[1] - 15
                    elements.append(mass_flow_marker(mdf_in_x, mdf_in_y, "μ_ND", "left", WHITE))
                    
                    pts2 = [ports["gas_out"], (LANE_MDF_OUT, ports["gas_out"][1]), (LANE_MDF_OUT, rim_b[1]+15), (rim_b[0], rim_b[1]+15), rim_b]
                    elements.append(polyline(pts2, PURPLE, 3.5))
                    elements.append(side_label(LANE_MDF_OUT, (ports["gas_out"][1] + rim_b[1])/2, "Sattdampf p_m", "left", PURPLE))
                    
                    mdf_out_x = (LANE_MDF_OUT + rim_b[0]) / 2
                    mdf_out_y = rim_b[1] + 15
                    elements.append(mass_flow_marker(mdf_out_x, mdf_out_y, "μ_HD", "right", WHITE))
                    
                else:
                    merge_y = (rim_a[1] + rim_b[1]) / 2
                    
                    elements.append(line(rim_a[0], rim_a[1], rim_a[0], merge_y, PURPLE, 3.5))
                    if not has_zk:
                        elements.append(mass_flow_marker(rim_a[0], (rim_a[1] + merge_y)/2 + 10, "μ_ND", "up", WHITE))
                    
                    elements.append(line(rim_a[0], merge_y, rim_b[0], rim_b[1], PURPLE, 3.5))
                    elements.append(mass_flow_marker(rim_b[0], (merge_y + rim_b[1])/2 - 10, "μ_HD", "up", WHITE))
                    
                    branch_pts = [ports["gas_out"], (LANE_MDF_OUT, ports["gas_out"][1]), (LANE_MDF_OUT, merge_y), (rim_a[0], merge_y)]
                    elements.append(polyline(branch_pts, PURPLE, 3.5))
                    elements.append(side_label(LANE_MDF_OUT, (ports["gas_out"][1] + merge_y)/2, "p_m", "left", PURPLE))
                    
                    bypass_x = (LANE_MDF_OUT + rim_a[0]) / 2
                    elements.append(mass_flow_marker(bypass_x, merge_y, "μ_Bypass", "right", WHITE))

            elif a in ("VD_ND", "ZK") and b == "VD_HD" and not has_mdf:
                rim_a = (pa[0], pa[1]-R) if a == "VD_ND" else (pa[0], pa[1]-30)
                rim_b = (pb[0], pb[1]+R)
                elements.append(line(rim_a[0], rim_a[1], rim_b[0], rim_b[1], PURPLE, 3.5))
                elements.append(side_label(right_x, (rim_a[1] + rim_b[1])/2, "p_m", "right", PURPLE))

    last_right = right_mid[-1]
    k_pos = pos["K"]
    last_pos = pos[last_right]
    north_pole = (last_pos[0], last_pos[1] - R)
    pts = [north_pole, (last_pos[0], k_pos[1]), k_pos]
    elements.append(polyline(pts, RED, 3.5))
    elements.append(path_label(pts, "Heißgas  p_c", RED))

    elements.append(heat_exchanger(*pos["K"], "Kondensator", "#4a2323"))
    elements.append(heat_exchanger(*pos["V"], "Verdampfer", "#23304a"))

    for node in left_mid:
        cx, cy = pos[node]
        if node == "MDF":
            elements.append(reservoir(cx, cy))
        else:
            label_txt = "Drossel 1" if node == "D1" else "Drossel 2"
            elements.append(expansion_valve(cx, cy, label_txt))

    for node in right_mid:
        cx, cy = pos[node]
        if node == "ZK":
            elements.append(zk_box(cx, cy))
        else:
            label_txt = {"VD": "Verdichter", "VD_ND": "Verdichter ND", "VD_HD": "Verdichter HD"}[node]
            elements.append(compressor(cx, cy, label_txt))

    state_svgs = []
    point_num = 1

    state_svgs.append(state_marker(LANE_SUCTION, pos["VD_ND" if is_2stage else "VD"][1] + R + 25, str(point_num)))
    point_num += 1

    if is_2stage:
        if not has_mdf and not has_zk:
            state_svgs.append(state_marker(LANE_COMP, (pos["VD_ND"][1] + pos["VD_HD"][1])/2, str(point_num)))
        else:
            state_svgs.append(state_marker(LANE_COMP, pos["VD_ND"][1] - R - 20, str(point_num)))
        point_num += 1

        if has_zk:
            state_svgs.append(state_marker(LANE_COMP, pos["ZK"][1] - 45, str(point_num)))
            point_num += 1

        if has_mdf:
            if mdf_mode == "vollstaendig":
                state_svgs.append(state_marker(LANE_MDF_OUT, pos["VD_HD"][1] + R + 35, str(point_num)))
            else:
                merge_y = (pos["VD_ND"][1] - R + pos["VD_HD"][1] + R) / 2
                state_svgs.append(state_marker(LANE_MDF_OUT, (pos["MDF"][1] - 20 + merge_y) / 2, str(point_num)))
            point_num += 1

        state_svgs.append(state_marker(right_x - 120, pos["K"][1], str(point_num)))
        point_num += 1
    else:
        state_svgs.append(state_marker(right_x - 120, pos["K"][1], str(point_num)))
        point_num += 1

    state_svgs.append(state_marker(left_x, pos["K"][1] + 50, str(point_num)))
    point_num += 1

    if has_mdf:
        state_svgs.append(state_marker(left_x, pos["MDF"][1] - 45, str(point_num)))
        point_num += 1
        state_svgs.append(state_marker(left_x, pos["D2"][1] - 45, str(point_num)))
        point_num += 1
        state_svgs.append(state_marker(left_x, pos["V"][1] - 45, str(point_num)))
        point_num += 1
    else:
        state_svgs.append(state_marker(left_x, pos["V"][1] - 45, str(point_num)))
        point_num += 1

    elements.extend(state_svgs)

    total_h = bottom_y + 130
    svg = (
        f'<svg viewBox="0 0 {CANVAS_W} {total_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:transparent; width:100%; height:auto;">'
        + "".join(elements)
        + "</svg>"
    )
    return svg, int(total_h)
