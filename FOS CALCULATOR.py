# fos_utm_10fig_streamlit.py
import streamlit as st
import math
import utm

st.set_page_config(page_title="ATACS", layout="centered")

# ---------- small math / geo helpers ----------
def deg2rad(d): return d * math.pi / 180.0
def rad2deg(r): return r * 180.0 / math.pi

def planar_bearing_deg(e1, n1, e2, n2):
    """Planar bearing from point1 -> point2 using UTM meters.
       Bearing is degrees clockwise from North (0..360)."""
    de = e2 - e1
    dn = n2 - n1
    if de == 0 and dn == 0:
        return 0.0
    theta = math.atan2(de, dn)  # note order: atan2(E diff, N diff)
    return (rad2deg(theta) + 360.0) % 360.0

def planar_distance_m(e1, n1, e2, n2):
    return math.hypot(e2 - e1, n2 - n1)

def intersection_of_two_rays(Ae, An, bearA_deg, Be, Bn, bearB_deg):
    """
    Intersection of two rays in plane:
    Ray1: (Ae,An) + t*(sin(b1), cos(b1))  t>=0
    Ray2: (Be,Bn) + u*(sin(b2), cos(b2))  u>=0
    Returns (E,N) if intersect (including negative t/u means lines extended).
    Raises ValueError if parallel (no intersection).
    """
    b1 = math.radians(bearA_deg)
    b2 = math.radians(bearB_deg)
    s1, c1 = math.sin(b1), math.cos(b1)
    s2, c2 = math.sin(b2), math.cos(b2)
    # Solve:
    # Ae + t*s1 = Be + u*s2
    # An + t*c1 = Bn + u*c2
    # -> t*s1 - u*s2 = Be - Ae
    #    t*c1 - u*c2 = Bn - An
    D = s1 * (-c2) - (-s2) * c1  # determinant of [[s1, -s2],[c1, -c2]]
    # simpler determinant:
    det = s1 * (-c2) - (-s2) * c1
    # compute properly:
    det = s1 * (-c2) - (-s2) * c1
    # Equivalent simpler calculation:
    det = s1 * (-c2) - (-s2) * c1
    # But easier: build 2x2 matrix and solve directly:
    a11, a12 = s1, -s2
    a21, a22 = c1, -c2
    det = a11 * a22 - a12 * a21
    if abs(det) < 1e-12:
        raise ValueError("Bearing lines are parallel or nearly parallel — no intersection.")
    rhs1 = Be - Ae
    rhs2 = Bn - An
    t = (rhs1 * a22 - rhs2 * a12) / det
    # u = (a11*rhs2 - a21*rhs1) / det  # not needed
    Ix = Ae + t * s1
    Iy = An + t * c1
    return Ix, Iy

def utm10_to_full(e5, n5, e_prefix, n_prefix):
    """Convert 5-digit easting and northing to full UTM meters using prefix.
       e_prefix and n_prefix should be integers in meters (e.g. 430000, 3100000)."""
    return int(e_prefix) + int(e5), int(n_prefix) + int(n5)

def format_10fig_from_full(easting, northing):
    e5 = str(int(round(easting)) % 100000).zfill(5)
    n5 = str(int(round(northing)) % 100000).zfill(5)
    return f"{e5} {n5}"

# ---------- Streamlit UI ----------
st.title("AGNIBAAN TARGET ACQUISITION & CORRECTION SYS")

st.markdown("""
**Instructions**
- Enter the UTM **Zone** and **Hemisphere**.
- For each point enter the **5-digit Easting** and **5-digit Northing** (these are the last 5 digits).
- Provide the **UTM Easting prefix** and **UTM Northing prefix** (meters) once — these are the leading digits to build full UTM meters.
  Example: if full Easting is 431234 then prefix=430000 and 5-digit=1234 (entered as 01234).  
  Typical prefixes (India) might be `400000` for Easting and `3000000` for Northing — adjust to your area.
""")

colz1, colz2 = st.columns(2)
with colz1:
    zone_number = st.number_input("UTM Zone number", min_value=1, max_value=60, value=43, step=1)
with colz2:
    hemisphere = st.selectbox("Hemisphere", ("N", "S"), index=0)
northern = True if hemisphere == "N" else False

st.markdown("### Enter 5-digit Easting and 5-digit Northing for each point (UTM 10-figure)")
prefix_cols = st.columns(2)
e_prefix = prefix_cols[0].number_input("UTM Easting prefix (meters)", value=430000, step=100)
n_prefix = prefix_cols[1].number_input("UTM Northing prefix (meters)", value=3100000, step=100)

points = ["A", "B", "C", "D", "Target"]
inputs_5 = {}
for p in points:
    c0, c1, c2 = st.columns([1,2,2])
    c0.write(f"**{p}**")
    e5 = c1.text_input(f"Easting 5-digit ({p})", value="31000", key=f"e5_{p}")
    n5 = c2.text_input(f"Northing 5-digit ({p})", value="10000", key=f"n5_{p}")
    # sanitize: strip spaces, ensure exactly 5 digits (pad with zeros if needed)
    e5s = e5.strip().replace(" ", "").zfill(5)[-5:]
    n5s = n5.strip().replace(" ", "").zfill(5)[-5:]
    inputs_5[p] = (e5s, n5s)

st.markdown("")
if st.button("Calculate FOS & Corrections"):
    try:
        # build full UTM meter coords
        full = {}
        for p in points:
            e5, n5 = inputs_5[p]
            fe, fn = utm10_to_full(e5, n5, e_prefix, n_prefix)
            full[p] = {"e": fe, "n": fn}
        # Compute planar bearings for A->D and B->C using UTM meters
        Ae, An = full["A"]["e"], full["A"]["n"]
        De, Dn = full["D"]["e"], full["D"]["n"]
        Be, Bn = full["B"]["e"], full["B"]["n"]
        Ce, Cn = full["C"]["e"], full["C"]["n"]

        bear_AD = planar_bearing_deg(Ae, An, De, Dn)
        bear_BC = planar_bearing_deg(Be, Bn, Ce, Cn)

        # Find intersection of rays A->(bearing_AD) and B->(bearing_BC)
        try:
            fos_e, fos_n = intersection_of_two_rays(Ae, An, bear_AD, Be, Bn, bear_BC)
        except ValueError as ex:
            st.error(f"Could not compute FOS intersection: {ex}")
            st.stop()

        # Convert FOS UTM -> lat/lon
        try:
            fos_lat, fos_lon = utm.to_latlon(fos_e, fos_n, int(zone_number), northern=northern)
        except Exception as ex:
            st.error(f"Failed converting FOS UTM -> lat/lon: {ex}")
            st.stop()

        # Distances and bearings from FOS to points (use planar UTM distances & bearings)
        report = {}
        for p in points:
            pe, pn = full[p]["e"], full[p]["n"]
            dist = planar_distance_m(fos_e, fos_n, pe, pn)
            bear = planar_bearing_deg(fos_e, fos_n, pe, pn)
            back = (bear + 180.0) % 360.0
            report[p] = {"dist_m": dist, "bearing_deg": bear, "back_bearing_deg": back}

        # Corrections FOS -> Target in UTM meters (signed)
        target_e = full["Target"]["e"]
        target_n = full["Target"]["n"]
        east_diff = target_e - fos_e   # + -> Target east of FOS (Right)
        north_diff = target_n - fos_n  # + -> Target north of FOS (Add)

        vert_word = "Add" if north_diff >= 0 else "Drop"
        horiz_word = "Right" if east_diff >= 0 else "Left"

        # Prepare outputs
        st.subheader("Results")

        # FOS lat/lon
        st.write(f"**FOS (lat, lon):** {fos_lat:.6f}, {fos_lon:.6f}")

        # FOS UTM full & 10-figure
        st.write(f"**FOS UTM (meters):** Zone {zone_number}{hemisphere}  E={int(round(fos_e))}  N={int(round(fos_n))}")
        fos_10 = format_10fig_from_full(fos_e, fos_n)
        fos_box = f"<div style='padding:8px;background:#f0fff0;border-radius:6px;'><b>FOS UTM 10-figure (5E 5N):</b> <span style='color:green;font-weight:700'>{fos_10}</span></div>"
        st.markdown(fos_box, unsafe_allow_html=True)

        # show triangle bearings used
        st.markdown(f"**Bearing A→D:** {bear_AD:.3f}°, **Bearing B→C:** {bear_BC:.3f}°")

        st.markdown("### Distances, Bearings & Back-bearings from FOS")
        for p in points:
            v = report[p]
            st.write(f"{p}: Distance = {v['dist_m']:.2f} m, Bearing = {v['bearing_deg']:.2f}°, Back-bearing = {v['back_bearing_deg']:.2f}°")

        # AFOS: distance from A along ray to FOS (signed t from param)
        # compute t for ray A: solve (fos_e - Ae) = t*sin(b1) => t = (fos_e - Ae)/sin(b1)  (if sin not zero)
        b1 = math.radians(bear_AD)
        s1 = math.sin(b1)
        if abs(s1) > 1e-12:
            tA = (fos_e - Ae) / s1
        else:
            # use north component
            c1 = math.cos(b1)
            tA = (fos_n - An) / c1 if abs(c1) > 1e-12 else 0.0
        AFOS_m = abs(tA)

        st.write(f"**AFOS (distance from A along A→FOS):** {AFOS_m:.2f} m")
        st.write(f"**Triangle angles (deg):** Angle A = {abs((planar_bearing_deg(Ae,An,Be,Bn) - planar_bearing_deg(Ae,An,De,Dn))%360):.3f}°, "
                 f"Angle B = {abs((planar_bearing_deg(Be,Bn,Ae,An) - planar_bearing_deg(Be,Bn,Ce,Cn))%360):.3f}°")

        # Highlight correction block
        corr_box = (f"<div style='padding:10px;background:#fff6f0;border-radius:6px;'>"
                    f"<b>Correction (FOS → Target):</b> "
                    f"<span style='font-weight:700;color:#b30000;'>{vert_word} {abs(north_diff):.2f} m</span>, "
                    f"<span style='font-weight:700;color:#b30000;'>{horiz_word} {abs(east_diff):.2f} m</span>"
                    f"</div>")
        st.markdown(corr_box, unsafe_allow_html=True)

        st.write(f"**Target UTM (input reconstructed):** E={int(target_e)} N={int(target_n)}")

        # warn if zone/hemisphere mismatch concerns (we used user's zone for lat/lon)
        # Note: if the full UTM easting/northing actually belong to a different zone, user should adjust prefix
        st.info("If the computed FOS appears far away or bearings look wrong, check your easting/northing prefixes and UTM zone/hemisphere.")

    except Exception as exc:
        st.error(f"Computation error: {exc}")

