import streamlit as st
import math
import utm

# -------------------
# Helper Functions
# -------------------

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

def bearing_deg(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1)*math.sin(phi2) - math.sin(phi1)*math.cos(phi2)*math.cos(dlambda)
    brng = math.degrees(math.atan2(x, y))
    return (brng + 360) % 360

def back_bearing(brng):
    return (brng + 180) % 360

def latlon_to_utm(lat, lon):
    easting, northing, zone, letter = utm.from_latlon(lat, lon)
    return easting, northing, zone, letter

def utm_to_gr(e, n):
    return f"{int(round(e)):05d} {int(round(n)):05d}"

def intersection_point(lat1, lon1, brng1, lat2, lon2, brng2):
    # Formula from aviation intersection calculation
    brng1, brng2 = math.radians(brng1), math.radians(brng2)
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    dist12 = 2 * math.asin(math.sqrt(math.sin(dlat/2)**2 +
                        math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2))
    if dist12 == 0:
        return None, None

    brngA = math.acos((math.sin(lat2) - math.sin(lat1)*math.cos(dist12)) /
                      (math.sin(dist12)*math.cos(lat1)))
    if math.isnan(brngA):
        brngA = 0

    brngB = math.acos((math.sin(lat1) - math.sin(lat2)*math.cos(dist12)) /
                      (math.sin(dist12)*math.cos(lat2)))

    if math.sin(lon2 - lon1) > 0:
        brng12, brng21 = brngA, 2*math.pi - brngB
    else:
        brng12, brng21 = 2*math.pi - brngA, brngB

    alpha1 = (brng1 - brng12 + math.pi) % (2*math.pi) - math.pi
    alpha2 = (brng21 - brng2 + math.pi) % (2*math.pi) - math.pi

    if math.sin(alpha1) == 0 and math.sin(alpha2) == 0:
        return None, None
    if math.sin(alpha1)*math.sin(alpha2) < 0:
        return None, None

    alpha3 = math.acos(-math.cos(alpha1)*math.cos(alpha2) +
                       math.sin(alpha1)*math.sin(alpha2)*math.cos(dist12))
    dist13 = math.atan2(math.sin(dist12)*math.sin(alpha1)*math.sin(alpha2),
                        math.cos(alpha2) + math.cos(alpha1)*math.cos(alpha3))
    lat3 = math.asin(math.sin(lat1)*math.cos(dist13) +
                     math.cos(lat1)*math.sin(dist13)*math.cos(brng1))
    dlon13 = math.atan2(math.sin(brng1)*math.sin(dist13)*math.cos(lat1),
                        math.cos(dist13) - math.sin(lat1)*math.sin(lat3))
    lon3 = lon1 + dlon13
    return math.degrees(lat3), (math.degrees(lon3) + 540) % 360 - 180

# -------------------
# Streamlit UI
# -------------------

st.title("FOS Calculator (Lat/Lon Input)")

st.markdown("### Enter Coordinates (Lat, Lon) for each point:")

# Inputs
points = {}
for p in ["A", "B", "C", "D", "Target"]:
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input(f"{p} Latitude", format="%.6f")
    with col2:
        lon = st.number_input(f"{p} Longitude", format="%.6f")
    points[p] = (lat, lon)

if st.button("Calculate FOS & Corrections"):
    # Bearings for AD and BC
    brng_AD = bearing_deg(points["A"][0], points["A"][1], points["D"][0], points["D"][1])
    brng_BC = bearing_deg(points["B"][0], points["B"][1], points["C"][0], points["C"][1])

    # Intersection = FOS
    fos_lat, fos_lon = intersection_point(points["A"][0], points["A"][1], brng_AD,
                                          points["B"][0], points["B"][1], brng_BC)

    # Convert FOS to UTM GR
    fos_e, fos_n, fos_zone, fos_letter = latlon_to_utm(fos_lat, fos_lon)
    fos_gr = utm_to_gr(fos_e, fos_n)

    # Distances & bearings
    dists = {}
    for name, coords in points.items():
        dist = haversine_m(fos_lat, fos_lon, coords[0], coords[1])
        brng = bearing_deg(fos_lat, fos_lon, coords[0], coords[1])
        dists[name] = (dist, brng, back_bearing(brng))

    # Correction (FOS → Target)
    north_diff = haversine_m(fos_lat, fos_lon, points["Target"][0], fos_lon)
    north_dir = "Add" if points["Target"][0] > fos_lat else "Drop"
    east_diff = haversine_m(fos_lat, fos_lon, fos_lat, points["Target"][1])
    east_dir = "Right" if points["Target"][1] > fos_lon else "Left"

    # -------------------
    # Output
    # -------------------
    st.markdown(f"""
    <div style='padding:10px;background:#f0fff0;border-radius:6px;'>
        <b>FOS UTM 10-figure GR:</b> <span style='color:green;font-weight:bold;'>{fos_gr}</span>
        <br><b>Zone:</b> {fos_zone}{fos_letter}
    </div>
    """, unsafe_allow_html=True)

    st.write(f"**FOS Lat/Lon:** {fos_lat:.6f}, {fos_lon:.6f}")

    st.markdown("### Distances, Bearings & Back Bearings from FOS")
    for name, (dist, brng, bbrng) in dists.items():
        st.write(f"{name}: {dist:.2f} m, Bearing {brng:.2f}°, Back Bearing {bbrng:.2f}°")

    st.markdown(f"""
    <div style='padding:10px;background:#fff6f0;border-radius:6px;'>
        <b>Correction (FOS → Target):</b>
        <br>{north_dir} <b>{north_diff:.2f} m</b>
        <br>{east_dir} <b>{east_diff:.2f} m</b>
    </div>
    """, unsafe_allow_html=True)


