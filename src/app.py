import folium
import streamlit as st
from pymongo.errors import DuplicateKeyError
from streamlit_folium import st_folium

import geometry_operations as geo
import spatial_queries as sq
from database import get_db

st.set_page_config(page_title="Coimbatore Spatial Data Explorer", layout="wide")

PSG = "PSG College of Technology"         
CATEGORIES = ["hospital", "school", "college"]
COLORS = {"hospital": "red", "school": "green", "college": "blue"}
CITY_CENTER = (11.02, 76.99)               


# =============================================================== map helpers
def new_map(center=CITY_CENTER, zoom=12):
    return folium.Map(location=center, zoom_start=zoom)


def swap(ring):
    return [[lat, lon] for lon, lat in ring]


def draw_boundaries(m, boundaries, color="#555555", fill=False):
    for b in boundaries:
        for ring in geo.polygon_rings(b["geometry"]):
            folium.Polygon(swap(ring), color=color, weight=2, fill=fill,
                           fill_opacity=0.12, tooltip=b["name"]).add_to(m)


def draw_roads(m, roads, color="#888888", weight=3):
    for r in roads:
        folium.PolyLine(swap(r["geometry"]["coordinates"]), color=color,
                        weight=weight, tooltip=r["name"]).add_to(m)


def draw_places(m, places, color=None, radius=6):
    for p in places:
        lon, lat = sq.lonlat(p)
        c = color or COLORS.get(p["category"], "gray")
        label = f"{p['name']} ({p['category']})"
        if "distance_km" in p:
            label += f" - {p['distance_km']} km"
        folium.CircleMarker((lat, lon), radius=radius, color=c, fill=True,
                            fill_color=c, fill_opacity=0.9, tooltip=label).add_to(m)


def draw_pin(m, lon, lat, label, color="black"):
    folium.Marker((lat, lon), tooltip=label,
                  icon=folium.Icon(color=color, icon="info-sign")).add_to(m)


def show_map(m):
    st_folium(m, height=560, use_container_width=True, returned_objects=[])


def rows_for(places):
    rows = []
    for p in places:
        lon, lat = sq.lonlat(p)
        row = {"name": p["name"], "category": p["category"], "area": p.get("area", ""),
               "longitude": round(lon, 4), "latitude": round(lat, 4)}
        if "distance_km" in p:
            row["distance_km"] = p["distance_km"]
        rows.append(row)
    return rows


def show_query(text):
    with st.expander("Show the MongoDB query"):
        st.code(text.strip(), language="javascript")


# ============================================================== operations
def op_view_all(db):
    st.subheader("View all data")
    st.write("Points (places), LineStrings (roads) and Polygons (boundaries) stored in MongoDB Atlas.")
    cats = st.multiselect("Place categories to show", CATEGORIES, default=CATEGORIES)
    places = [p for p in sq.get_all(db, "places") if p["category"] in cats]
    boundaries = sq.get_all(db, "boundaries")
    roads = sq.get_all(db, "roads")

    c1, c2, c3 = st.columns(3)
    c1.metric("Points (places)", len(places))
    c2.metric("LineStrings (roads)", len(roads))
    c3.metric("Polygons (boundaries)", len(boundaries))

    m = new_map()
    draw_boundaries(m, boundaries)
    draw_roads(m, roads)
    draw_places(m, places)
    show_map(m)
    st.dataframe(rows_for(places), use_container_width=True)
    show_query('db.places.find({ category: { $in: ["hospital", "school", "college"] } })')


def op_crud(db):
    st.subheader("Basic CRUD on spatial documents")
    st.write("Create, Read, Update and Delete a Point document. "
             "Only documents you create here (source = 'user') can be deleted.")
    tab_c, tab_r, tab_u, tab_d = st.tabs(["Create", "Read", "Update", "Delete"])

    with tab_c:
        name = st.text_input("Name", "Demo Clinic (my test)", key="c_name")
        category = st.selectbox("Category", CATEGORIES, key="c_cat")
        lon = st.number_input("Longitude", value=77.0100, format="%.4f", key="c_lon")
        lat = st.number_input("Latitude", value=11.0200, format="%.4f", key="c_lat")
        if st.button("Insert place"):
            try:
                new_id = sq.insert_place(db, name, category, lon, lat)
                st.success(f"Inserted with _id = {new_id}")
            except DuplicateKeyError:
                st.error("A place with that name already exists.")

    with tab_r:
        name = st.text_input("Name to find", PSG, key="r_name")
        if st.button("Find place"):
            doc = sq.get_by_name(db, "places", name)
            if doc:
                st.json(doc)
            else:
                st.warning("No place with that name.")

    user_names = [p["name"] for p in sq.find_places(db, {"source": "user"})]

    with tab_u:
        if not user_names:
            st.info("Create a place first.")
        else:
            target = st.selectbox("Place to update", user_names, key="u_name")
            new_cat = st.selectbox("New category", CATEGORIES, key="u_cat")
            if st.button("Update category"):
                changed = sq.update_place(db, target, {"category": new_cat})
                st.success(f"Documents modified: {changed}")

    with tab_d:
        if not user_names:
            st.info("Nothing to delete yet.")
        else:
            target = st.selectbox("Place to delete", user_names, key="d_name")
            if st.button("Delete place"):
                deleted = sq.delete_place(db, target)
                st.success(f"Documents deleted: {deleted}")

    st.markdown("**Places you created (source = 'user'):**")
    mine = sq.find_places(db, {"source": "user"})
    if mine:
        st.dataframe(rows_for(mine), use_container_width=True)
    else:
        st.caption("None yet.")
    show_query("""
db.places.insertOne({ name: "Demo Clinic", category: "hospital", source: "user",
  geometry: { type: "Point", coordinates: [77.0100, 11.0200] } })
db.places.find({ name: "Demo Clinic" })
db.places.updateOne({ name: "Demo Clinic" }, { $set: { category: "school" } })
db.places.deleteOne({ name: "Demo Clinic", source: "user" })
""")


def op_point_lookup(db):
    st.subheader("Point lookup")
    st.write("Enter a longitude and latitude. MongoDB returns the nearest stored place "
             "within the search distance, and we show its normal (non-spatial) attributes.")
    c1, c2, c3 = st.columns(3)
    lon = c1.number_input("Longitude", value=77.0030, format="%.4f", key="pl_lon")
    lat = c2.number_input("Latitude", value=11.0245, format="%.4f", key="pl_lat")
    max_m = c3.slider("Search distance (m)", 50, 1000, 200, 50)

    found = sq.point_lookup(db, lon, lat, max_m)
    m = new_map((lat, lon), 15)
    draw_places(m, sq.get_all(db, "places"), color="#999999", radius=4)
    draw_pin(m, lon, lat, "Query point")
    if found:
        f_lon, f_lat = sq.lonlat(found)
        found["distance_km"] = round(geo.haversine_km(lon, lat, f_lon, f_lat), 3)
        draw_places(m, [found], color="red", radius=10)
        st.success(f"Found: {found['name']} ({found['distance_km'] * 1000:.0f} m away)")
        st.json({k: v for k, v in found.items() if k not in ("geometry", "_id")})
    else:
        st.warning(f"No stored place within {max_m} m of this point.")
    show_map(m)
    show_query("""
db.places.find({ geometry: { $nearSphere: {
  $geometry: { type: "Point", coordinates: [77.0030, 11.0245] }, $maxDistance: 200 } } }).limit(1)
""")


def op_geowithin(db):
    st.subheader("Places within a boundary ($geoWithin)")
    st.write("**Containment** means: is the point inside the polygon? "
             "Green/red/blue points are inside; grey points are outside.")
    boundaries = sq.get_all(db, "boundaries")
    choice = st.selectbox("Boundary", [b["name"] for b in boundaries])
    cats = st.multiselect("Categories", CATEGORIES, default=CATEGORIES)

    inside = sq.places_within_boundary(db, choice, cats)
    inside_names = {p["name"] for p in inside}
    everything = [p for p in sq.get_all(db, "places") if p["category"] in cats]
    outside = [p for p in everything if p["name"] not in inside_names]

    c1, c2 = st.columns(2)
    c1.metric("Inside", len(inside))
    c2.metric("Outside", len(outside))

    m = new_map()
    draw_boundaries(m, [b for b in boundaries if b["name"] == choice], color="#d9480f", fill=True)
    draw_places(m, outside, color="#999999", radius=5)
    draw_places(m, inside)
    show_map(m)
    st.dataframe(rows_for(inside), use_container_width=True)
    show_query("""
const city = db.boundaries.findOne({ name: "Coimbatore (simplified educational boundary)" })
db.places.find({ geometry: { $geoWithin: { $geometry: city.geometry } } })
""")


def op_nearsphere(db):
    st.subheader("Places near PSG Tech ($nearSphere)")
    st.write("Find places within a distance of the reference point, nearest first.")
    ref = sq.get_by_name(db, "places", PSG)
    lon, lat = sq.lonlat(ref)
    c1, c2 = st.columns(2)
    km = c1.slider("Distance (km)", 0.5, 10.0, 3.0, 0.5)
    category = c2.selectbox("Category", CATEGORIES)

    results = sq.places_near_sphere(db, lon, lat, km * 1000, category)
    st.metric(f"{category.title()}s within {km} km of {PSG}", len(results))

    m = new_map((lat, lon), 13)
    folium.Circle((lat, lon), radius=km * 1000, color="#1c7ed6", fill=True,
                  fill_opacity=0.08).add_to(m)
    draw_places(m, [p for p in sq.get_all(db, "places") if p["category"] == category],
                color="#999999", radius=5)
    draw_places(m, results, color="red", radius=8)
    draw_pin(m, lon, lat, PSG)
    show_map(m)
    st.dataframe(rows_for(results), use_container_width=True)
    show_query("""
db.places.find({ category: "hospital", geometry: { $nearSphere: {
  $geometry: { type: "Point", coordinates: [77.0028, 11.0247] },   // PSG Tech
  $maxDistance: 3000 } } })                                         // metres
""")


def op_distance(db):
    st.subheader("Distance between two locations")
    st.write("MongoDB's `$geoNear` stage measures the distance; haversine in Python is a cross-check.")
    names = sorted(p["name"] for p in sq.get_all(db, "places"))
    c1, c2 = st.columns(2)
    a_name = c1.selectbox("Location A", names, index=names.index(PSG))
    default_b = "Kovai Medical Center and Hospital"
    b_name = c2.selectbox("Location B", names, index=names.index(default_b))
    if a_name == b_name:
        st.warning("Pick two different locations.")
        return

    result = sq.distance_between(db, a_name, b_name)
    c1, c2 = st.columns(2)
    c1.metric("Distance (MongoDB $geoNear)", f"{result['mongodb_km']} km")
    c2.metric("Distance (haversine check)", f"{result['haversine_km']} km")

    a_lon, a_lat = sq.lonlat(result["a"])
    b_lon, b_lat = sq.lonlat(result["b"])
    m = new_map()
    draw_pin(m, a_lon, a_lat, a_name, "blue")
    draw_pin(m, b_lon, b_lat, b_name, "red")
    folium.PolyLine([(a_lat, a_lon), (b_lat, b_lon)], color="#d9480f", weight=3,
                    tooltip=f"{result['mongodb_km']} km").add_to(m)
    m.fit_bounds([[a_lat, a_lon], [b_lat, b_lon]], padding=(40, 40))
    show_map(m)
    show_query("""
db.places.aggregate([{ $geoNear: {
  near: <GeoJSON point of A>, distanceField: "dist_m", spherical: true,
  query: { name: "<name of B>" } } }])      // dist_m is in metres
""")


def op_count(db):
    st.subheader("Count locations in a boundary (spatial aggregation)")
    boundaries = sq.get_all(db, "boundaries")
    choice = st.selectbox("Boundary", [b["name"] for b in boundaries])
    counts = sq.count_by_category_in_boundary(db, choice)

    cols = st.columns(3)
    for col, category in zip(cols, CATEGORIES):
        col.metric(category.title() + "s", counts.get(category, 0))

    inside = sq.places_within_boundary(db, choice, CATEGORIES)
    m = new_map()
    draw_boundaries(m, [b for b in boundaries if b["name"] == choice], color="#d9480f", fill=True)
    draw_places(m, inside)
    show_map(m)
    show_query("""
db.places.aggregate([
  { $match: { geometry: { $geoWithin: { $geometry: <boundary geometry> } } } },
  { $group: { _id: "$category", count: { $sum: 1 } } },
  { $sort: { _id: 1 } }
])
""")


def op_knn(db):
    st.subheader("Nearest locations to PSG Tech (KNN)")
    st.write("K-nearest-neighbour: no radius, just the K closest places.")
    ref = sq.get_by_name(db, "places", PSG)
    lon, lat = sq.lonlat(ref)
    c1, c2 = st.columns(2)
    k = c1.slider("K (how many)", 1, 8, 3)
    category = c2.selectbox("Category", CATEGORIES)

    results = sq.nearest_k(db, lon, lat, category, k)
    m = new_map((lat, lon), 13)
    for rank, p in enumerate(results, start=1):
        p_lon, p_lat = sq.lonlat(p)
        folium.PolyLine([(lat, lon), (p_lat, p_lon)], color="#d9480f", weight=2,
                        dash_array="6").add_to(m)
        folium.Marker((p_lat, p_lon), tooltip=f"#{rank} {p['name']} - {p['distance_km']} km",
                      icon=folium.DivIcon(html=f'<div style="font-size:16px;font-weight:bold;'
                                               f'color:white;background:red;border-radius:50%;'
                                               f'width:24px;height:24px;text-align:center;">{rank}</div>')
                      ).add_to(m)
    draw_pin(m, lon, lat, PSG)
    show_map(m)
    st.dataframe(rows_for(results), use_container_width=True)
    show_query("""
db.places.find({ category: "hospital", geometry: { $nearSphere: {
  $geometry: { type: "Point", coordinates: [77.0028, 11.0247] } } } }).limit(3)
""")


def op_roads(db):
    st.subheader("Road intersection and adjacency")
    st.write("**Intersection**: the roads cross. **Adjacency**: the roads do not touch but are very close "
             "- a special case of proximity. MongoDB finds intersections; Shapely measures the gap.")
    roads = sq.get_all(db, "roads")
    c1, c2 = st.columns(2)
    selected_name = c1.selectbox("Selected road", [r["name"] for r in roads])
    adjacent_m = c2.slider("'Adjacent' if gap is at most (m)", 0, 1500, 300, 50)
    selected = next(r for r in roads if r["name"] == selected_name)

    intersecting = sq.road_names_intersecting(db, selected_name)
    related = geo.classify_roads(selected, roads, intersecting, adjacent_m)
    relation = {r["name"]: r for r in related}

    m = new_map()
    for road in roads:
        if road["name"] == selected_name:
            draw_roads(m, [road], color="red", weight=6)
        elif road["name"] in relation and relation[road["name"]]["relation"] == "intersects":
            draw_roads(m, [road], color="orange", weight=5)
        elif road["name"] in relation:
            draw_roads(m, [road], color="purple", weight=5)
        else:
            draw_roads(m, [road], color="#bbbbbb", weight=2)
    for r in related:
        for p_lon, p_lat in r["points"]:
            folium.CircleMarker((p_lat, p_lon), radius=7, color="black", fill=True,
                                tooltip=f"Crossing with {r['name']}").add_to(m)
    show_map(m)
    st.caption("Red = selected, orange = intersects, purple = adjacent, grey = unrelated.")
    st.dataframe([{"road": r["name"], "relation": r["relation"], "gap_m": r["gap_m"]}
                  for r in related] or [{"road": "(none)", "relation": "", "gap_m": ""}],
                 use_container_width=True)
    show_query("""
const road = db.roads.findOne({ name: "Avinashi Road" })
db.roads.find({ name: { $ne: "Avinashi Road" },
                geometry: { $geoIntersects: { $geometry: road.geometry } } })
""")


def op_buffer(db):
    st.subheader("Buffer around PSG Tech")
    st.write("A **buffer** is the area within a given distance of a feature. We build it as a polygon, "
             "draw it, and ask MongoDB which places fall inside it.")
    ref = sq.get_by_name(db, "places", PSG)
    lon, lat = sq.lonlat(ref)
    km = st.slider("Buffer radius (km)", 0.5, 10.0, 3.0, 0.5)

    circle = geo.circle_polygon(lon, lat, km)
    inside = sq.places_in_polygon(db, circle)
    for p in inside:
        p_lon, p_lat = sq.lonlat(p)
        p["distance_km"] = round(geo.haversine_km(lon, lat, p_lon, p_lat), 3)
    inside.sort(key=lambda p: p["distance_km"])
    inside_names = {p["name"] for p in inside}

    st.metric(f"Places inside the {km} km buffer", len(inside))
    m = new_map((lat, lon), 13)
    folium.Polygon(swap(circle["coordinates"][0]), color="#1c7ed6", fill=True,
                   fill_opacity=0.12, tooltip=f"{km} km buffer").add_to(m)
    draw_places(m, [p for p in sq.get_all(db, "places") if p["name"] not in inside_names],
                color="#999999", radius=5)
    draw_places(m, inside)
    draw_pin(m, lon, lat, PSG)
    show_map(m)
    st.dataframe(rows_for(inside), use_container_width=True)
    show_query("""
// 'buffer' is a polygon of 64 points around PSG Tech, built in Python (geometry_operations.circle_polygon)
db.places.find({ geometry: { $geoWithin: { $geometry: buffer } } })
""")


def op_union(db):
    st.subheader("Polygon union")
    st.write("**Union** merges two polygons into one. The overlapping part is not counted twice.")
    boundaries = sq.get_all(db, "boundaries")
    names = [b["name"] for b in boundaries]
    c1, c2 = st.columns(2)
    a_name = c1.selectbox("Polygon A", names, index=1)
    b_name = c2.selectbox("Polygon B", names, index=2)
    if a_name == b_name:
        st.warning("Pick two different polygons.")
        return
    a = next(b for b in boundaries if b["name"] == a_name)
    b = next(b for b in boundaries if b["name"] == b_name)

    merged = geo.union_polygons(a["geometry"], b["geometry"])
    rings = geo.polygon_rings(merged)

    m = new_map()
    draw_boundaries(m, [a], color="#1c7ed6")
    draw_boundaries(m, [b], color="#2f9e44")
    for ring in rings:
        folium.Polygon(swap(ring), color="red", weight=4, fill=True, fill_opacity=0.25,
                       tooltip="Union result").add_to(m)
    show_map(m)
    st.caption(f"Result: {merged['type']} with {sum(len(r) - 1 for r in rings)} corner points "
               "(blue and green = inputs, red = union).")
    show_query("// Union is not a MongoDB operation - it is done with Shapely:\n"
               "// unary_union([shape(a_geometry), shape(b_geometry)])")


# ================================================================== main
OPERATIONS = {
    "View all data": op_view_all,
    "CRUD (insert / find / update / delete)": op_crud,
    "Point lookup": op_point_lookup,
    "Places within a boundary ($geoWithin)": op_geowithin,
    "Places near PSG Tech ($nearSphere)": op_nearsphere,
    "Distance between locations": op_distance,
    "Count locations in a boundary": op_count,
    "Nearest hospitals (KNN)": op_knn,
    "Road intersection / adjacency": op_roads,
    "Buffer around PSG Tech": op_buffer,
    "Polygon union": op_union,
}


def main():
    st.title("Coimbatore Spatial Data Explorer")
    st.caption("MongoDB Atlas + GeoJSON + 2dsphere index. Data is a small educational sample "
               "with approximate coordinates, not official survey data.")
    try:
        db = get_db()
        db.command("ping")
    except Exception as error:
        st.error(f"Could not connect to MongoDB Atlas: {error}")
        st.stop()
    if db.places.count_documents({}) == 0:
        st.warning("The collections are empty. Run:  python src/load_data.py")
        st.stop()

    choice = st.sidebar.radio("Choose an operation", list(OPERATIONS))
    OPERATIONS[choice](db)


main()
