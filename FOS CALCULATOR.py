# fos_streamlit.py
import streamlit as st
import math
import mgrs

R_EARTH = 6371000.0  # mean Earth radius in meters



def deg2rad(d): return d * math.pi / 180.0
def rad2deg(r): return r * 180.0 / math.pi

def haversine_m(lat1, lon1, lat2, lon2):
    # returns great-circle distance in meters
    phi1, phi2 = deg2rad(lat1), deg2rad(lat2)
    dl = deg2rad(lon2 - lon1)
    dphi = phi2 - phi1
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2 * R_EARTH * math.asin(math.sqrt(a))

def bearing_deg(lat1, lon1, lat2, lon2):
    # initial bearing from point1 -> point2 in degrees (0..360)
    phi1, phi2 = deg2rad(lat1), deg2rad(lat2)
    dl = deg2rad(lon2 - lon1)
    x = math.sin(dl) * math.cos(phi2)
    y = math.cos(phi1)*math.sin(phi2) - math.sin(phi1)*math.cos(phi2)*math.cos(dl)
    bearing = math.atan2(x, y)
    return (rad2deg(bearing) + 360) % 360

def angle_between_bearings(b1, b2):
    # smallest angle between two bearings in degrees (0..180)
    diff = (b2 - b1 + 360) % 360
    return diff if diff <= 180 else 360 - diff

def destination_point(lat1, lon1, bearing_deg_val, distance_m):
    # returns lat2, lon2 after moving distance_m from lat1,lon1 at bearing (degrees)
    phi1 = deg2rad(lat1)
    lambda1 = deg2rad(lon1)
    theta = deg2rad(bearing_deg_val)
    delta = distance_m / R_EARTH

    phi2 = math.asin(math.sin(phi1)*math.cos(delta) + math.cos(phi1)*math.sin(delta)*math.cos(theta))
    lambda2 = lambda1 + math.atan2(math.sin(theta)*math.sin(delta)*math.cos(phi1),
                                   math.cos(delta) - math.sin(phi1)*math.sin(phi2))
    return rad2deg(phi2), (rad2deg(lambda2) + 540) % 360 - 180  # normalize lon to [-180,180]


def compute_fos_and_corrections(A, B, C, D, FT):
    # A,B,C,D,FT are each (lat, lon)
    AB = haversine_m(A[0], A[1], B[0], B[1])
    if AB == 0:
        return {"error": "A and B are the same point (AB=0)."}

    # Bearings
    bearing_AB = bearing_deg(A[0], A[1], B[0], B[1])
    bearing_AD = bearing_deg(A[0], A[1], D[0], D[1])  # D between A and FOS
    bearing_BA = bearing_deg(B[0], B[1], A[0], A[1])
    bearing_BC = bearing_deg(B[0], B[1], C[0], C[1])  # C between B and FOS

    # Angles
    angle_A = angle_between_bearings(bearing_AB, bearing_AD)
    angle_B = angle_between_bearings(bearing_BA, bearing_BC)
    angle_FOS = 180.0 - angle_A - angle_B

    if angle_FOS <= 0 or angle_A <= 0 or angle_B <= 0:
        return {"error": f"Invalid geometry: A={angle_A:.6f}°, B={angle_B:.6f}°, FOS={angle_FOS:.6f}°"}

    # Law of Sines to get AFOS
    alpha = deg2rad(angle_A)
    beta = deg2rad(angle_B)
    gamma = deg2rad(angle_FOS)
    sin_gamma = math.sin(gamma)
    if abs(sin_gamma) < 1e-12:
        return {"error": "Degenerate triangle (sin(gamma) ~ 0)."}

    AFOS = AB * math.sin(beta) / sin_gamma

    # Compute FOS coordinates
    fos_lat, fos_lon = destination_point(A[0], A[1], bearing_AD, AFOS)

    # Corrections
    north_diff_m = haversine_m(fos_lat, fos_lon, FT[0], fos_lon)
    east_diff_m  = haversine_m(fos_lat, fos_lon, fos_lat, FT[1])
    ns_dir = "Up" if FT[0] > fos_lat else "Down"
    ew_dir = "Right" if FT[1] > fos_lon else "Left"

    # MGRS conversion
    m = mgrs.MGRS()
    fos_mgrs = m.toMGRS(fos_lat, fos_lon, MGRSPrecision=5)     # 10-figure
    target_mgrs = m.toMGRS(FT[0], FT[1], MGRSPrecision=5)      # 10-figure

    return {
        "FOS_lat": fos_lat,
        "FOS_lon": fos_lon,
        "AFOS_m": AFOS,
        "angle_A_deg": angle_A,
        "angle_B_deg": angle_B,
        "angle_FOS_deg": angle_FOS,
        "north_correction_m": north_diff_m,
        "north_direction": ns_dir,
        "east_correction_m": east_diff_m,
        "east_direction": ew_dir,
        "bearing_AB": bearing_AB,
        "bearing_AD": bearing_AD,
        "bearing_BA": bearing_BA,
        "bearing_BC": bearing_BC,
        "FOS_mgrs": fos_mgrs,
        "Target_mgrs": target_mgrs
    }


st.title("AGNIBAAN FOS & Correction Calculator")

st.markdown("Enter coordinates in decimal degrees (lat lon). Example: `28.6139 77.2090`")

col1, col2 = st.columns(2)
with col1:
    A_txt = st.text_input("A (lat lon)", "28.6139 77.2090")
    B_txt = st.text_input("B (lat lon)", "28.7041 77.1025")
    FT_txt = st.text_input("Final Target (lat lon)", "28.6500 77.2100")
    run = st.button("Calculate")
with col2:
    D_txt = st.text_input("D (lat lon) — between A and FOS", "28.5355 77.3910")
    C_txt = st.text_input("C (lat lon) — between B and FOS", "28.6692 77.4538")

if run:
    try:
        A = tuple(map(float, A_txt.strip().split()))
        B = tuple(map(float, B_txt.strip().split()))
        C = tuple(map(float, C_txt.strip().split()))
        D = tuple(map(float, D_txt.strip().split()))
        FT = tuple(map(float, FT_txt.strip().split()))
    except Exception as e:
        st.error("Invalid input format. Use: `lat lon` (two numbers separated by space).")
        st.stop()

    res = compute_fos_and_corrections(A, B, C, D, FT)
    if "error" in res:
        st.error(res["error"])
    else:
        st.subheader("Results")
        st.write(f"**FOS (lat, lon):** {res['FOS_lat']:.6f}, {res['FOS_lon']:.6f}")
        st.write(f"**AFOS distance from A:** {res['AFOS_m']:.2f} m")
        st.write(f"**Angle A:** {res['angle_A_deg']:.3f}°")
        st.write(f"**Angle B:** {res['angle_B_deg']:.3f}°")
        st.write(f"**Angle at FOS:** {res['angle_FOS_deg']:.3f}°")
        st.write(f"**Bearings used (deg):** A→B={res['bearing_AB']:.3f}, A→D={res['bearing_AD']:.3f}, B→A={res['bearing_BA']:.3f}, B→C={res['bearing_BC']:.3f}")
        st.write(f"**FOS MGRS (10-figure):** {res['FOS_mgrs']}")
        st.write(f"**Target MGRS (10-figure):** {res['Target_mgrs']}")
        st.markdown(
    f"<span style='background-color:yellow; color:black;'>"
    f"Correction: {res['north_direction']} {res['north_correction_m']:.2f} m, "
    f"{res['east_direction']} {res['east_correction_m']:.2f} m"
    f"</span>",
    unsafe_allow_html=True
)
        # optional: show small help
        st.info("If results show 'Invalid geometry', check that C is on the line B→FOS and D is on the line A→FOS and that points are not collinear.")
