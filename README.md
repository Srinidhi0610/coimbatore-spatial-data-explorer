# Coimbatore Spatial Data Explorer using MongoDB Atlas

A small 3-day lab project for *Big Data and Modern Database Systems* that demonstrates the
concepts of the **Spatial Data** worksheet using **MongoDB Atlas**, **GeoJSON**, **PyMongo**,
**Streamlit**, **Folium** and **Shapely**.

> **Data honesty note.** The dataset is a small **educational sample**. Place names are real
> Coimbatore landmarks, but coordinates are hand-placed approximations (they may be off by a few
> hundred metres), the list is not complete, the city boundary is a rough hand-drawn outline (not the
> official limit), and one road ("Sample Link Road") is fictional. Do not present it as official data.

---

## 1. Project title
Coimbatore Spatial Data Explorer using MongoDB Atlas

## 2. Objective
Store spatial (vector) data as GeoJSON in MongoDB Atlas, index it with a `2dsphere` index, and
run the spatial operations from the lab worksheet: CRUD, point lookup, containment, proximity,
distance, aggregation, intersection/adjacency, buffer, KNN and union, with every result shown on a map.

## 3. Problem statement
Ordinary database queries cannot answer questions such as *"Which hospitals are within 3 km of PSG Tech?"*
or *"Which roads cross Avinashi Road?"*. A database with spatial support can store shapes, index them,
and answer these questions quickly. This project shows how MongoDB does that.

## 4. Technologies
| Tool | Used for |
|---|---|
| MongoDB Atlas | Cloud database with geospatial queries |
| GeoJSON | Format of the spatial data |
| Python + PyMongo | Loading data and running queries |
| Shapely | Geometry that MongoDB cannot do (union, road gap, crossing points) |
| Streamlit | The web interface |
| Folium | Interactive maps |

## 5. Dataset
Three GeoJSON files in `data/` (educational sample, see the note above):

| File | Geometry | Count | Contents |
|---|---|---|---|
| `places.geojson` | Point | 18 | 8 hospitals, 7 colleges (incl. PSG Tech, the reference point), 3 schools. One college (Ettimadai) is deliberately outside the city boundary |
| `roads.geojson` | LineString | 5 | Avinashi Road, Sathy Road, Mettupalayam Road, Trichy Road, Sample Link Road (fictional) |
| `boundaries.geojson` | Polygon | 3 | Simplified Coimbatore outline, Peelamedu Zone, Race Course Zone (the two zones overlap, used for union) |

## 6. GeoJSON explanation
GeoJSON is a JSON format for geographic shapes. A shape looks like this:

```json
{ "type": "Point", "coordinates": [77.0028, 11.0247] }
```

**Coordinates are always `[longitude, latitude]`** (x first, then y). This is the opposite of what people
usually say aloud ("lat, long") and the opposite of Folium, which wants `[lat, lon]`. The code swaps
them in one helper (`swap()` in `app.py`).

## 7. Point / LineString / Polygon
| Type | Meaning | Example here | `coordinates` looks like |
|---|---|---|---|
| **Point** | One location | A hospital | `[lon, lat]` |
| **LineString** | A path through several points | A road | `[[lon, lat], [lon, lat], ...]` |
| **Polygon** | A closed area. First and last point are identical. | A boundary | `[[[lon, lat], ..., first point again]]` |

Polygon outer rings must be **counter-clockwise** for MongoDB; the data files follow this.

## 8. MongoDB Atlas setup
1. Create a free account at <https://www.mongodb.com/cloud/atlas> and create a free **M0** cluster.
2. **Database Access** → *Add New Database User* → choose a username and password (use letters/digits
   only, to avoid URL-encoding problems).
3. **Network Access** → *Add IP Address* → *Add Current IP Address* (for a lab, "Allow access from anywhere"
   `0.0.0.0/0` also works).
4. **Database** → *Connect* → *Drivers* → copy the connection string
   (`mongodb+srv://...`) and replace `<password>` with your password.

You do **not** need to create the database or collections by hand; `load_data.py` creates them.

## 9. Database structure
Database: `coimbatore_spatial_db`

| Collection | Geometry | Example document |
|---|---|---|
| `places` | Point | `{ name: "PSG Hospitals", category: "hospital", area: "Peelamedu", geometry: { type: "Point", coordinates: [77.004, 11.0215] } }` |
| `roads` | LineString | `{ name: "Avinashi Road", category: "road", geometry: { type: "LineString", coordinates: [...] } }` |
| `boundaries` | Polygon | `{ name: "Peelamedu Zone (educational)", category: "boundary", geometry: { type: "Polygon", coordinates: [[...]] } }` |

The shape is always stored in a field called `geometry`.

## 10. The 2dsphere index
An index lets the database find data without scanning every document. A `2dsphere` index is the
spatial index MongoDB uses for GeoJSON on an Earth-like sphere. It is **required** by `$nearSphere` and
`$geoNear`, and speeds up `$geoWithin` and `$geoIntersects`.

mongosh command:
```javascript
use coimbatore_spatial_db
db.places.createIndex({ geometry: "2dsphere" })
db.roads.createIndex({ geometry: "2dsphere" })
db.boundaries.createIndex({ geometry: "2dsphere" })
```
PyMongo equivalent (in `src/load_data.py`):
```python
collection.create_index([("geometry", GEOSPHERE)])
```

## 11. Spatial operations
| # | Operation | Where | How |
|---|---|---|---|
| 1 | CRUD | `spatial_queries.py` | `insert_one`, `find`, `update_one`, `delete_one` |
| 2 | Point lookup | `point_lookup()` | `$nearSphere` + `limit(1)` |
| 3 | Containment | `places_within_boundary()` | `$geoWithin` |
| 4 | Proximity (3 km of PSG Tech) | `places_near_sphere()` | `$nearSphere` + `$maxDistance` |
| 5 | Distance | `distance_between()` | `$geoNear` aggregation (+ haversine check) |
| 6 | Spatial aggregation | `count_by_category_in_boundary()` | `$match` with `$geoWithin`, then `$group` |
| 7 | Intersection / adjacency | `road_names_intersecting()` + `geometry_operations.classify_roads()` | `$geoIntersects` + Shapely gap measurement |
| 8 | Buffer | `geometry_operations.circle_polygon()` + `places_in_polygon()` | Circle polygon + `$geoWithin` |
| 9 | KNN | `nearest_k()` | `$nearSphere` + `limit(3)` |
| 10 | Union | `geometry_operations.union_polygons()` | Shapely `unary_union` |

**Containment** = "is this point inside that polygon?". **Adjacency** = two features that do not intersect
but are very close; it is a special case of proximity (here: gap of at most 300 m, adjustable).

### The same queries in mongosh
```javascript
// 2. Point lookup (nearest place within 200 m of a coordinate)
db.places.find({ geometry: { $nearSphere: {
  $geometry: { type: "Point", coordinates: [77.0030, 11.0245] }, $maxDistance: 200 } } }).limit(1)

// 3. $geoWithin - places inside the city boundary
const city = db.boundaries.findOne({ name: "Coimbatore (simplified educational boundary)" })
db.places.find({ geometry: { $geoWithin: { $geometry: city.geometry } } })

// 4. $nearSphere - hospitals within 3 km of PSG Tech (distance in metres)
db.places.find({ category: "hospital", geometry: { $nearSphere: {
  $geometry: { type: "Point", coordinates: [77.0028, 11.0247] }, $maxDistance: 3000 } } })

// 5. Distance from PSG Tech to KMCH (dist_m is in metres)
db.places.aggregate([{ $geoNear: {
  near: { type: "Point", coordinates: [77.0028, 11.0247] },
  distanceField: "dist_m", spherical: true,
  query: { name: "Kovai Medical Center and Hospital" } } }])

// 6. Count by category inside the Peelamedu zone
const zone = db.boundaries.findOne({ name: "Peelamedu Zone (educational)" })
db.places.aggregate([
  { $match: { geometry: { $geoWithin: { $geometry: zone.geometry } } } },
  { $group: { _id: "$category", count: { $sum: 1 } } } ])

// 7. Roads that intersect Avinashi Road
const road = db.roads.findOne({ name: "Avinashi Road" })
db.roads.find({ name: { $ne: "Avinashi Road" },
                geometry: { $geoIntersects: { $geometry: road.geometry } } })

// 9. KNN - 3 nearest hospitals to PSG Tech
db.places.find({ category: "hospital", geometry: { $nearSphere: {
  $geometry: { type: "Point", coordinates: [77.0028, 11.0247] } } } }).limit(3)
```
Buffer (8) and union (10) need a polygon built in Python, so they are demonstrated in the app.

## 12. How to run the project

**Folder:**
```
coimbatore-spatial-project/
├── data/            places.geojson, roads.geojson, boundaries.geojson
├── src/             database.py, load_data.py, spatial_queries.py, geometry_operations.py, app.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

**1. Create a virtual environment and install packages** (run inside the project folder)
```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

**2. Create the `.env` file** (stores your connection string; never share it)
```bash
# Windows:      copy .env.example .env
# macOS/Linux:  cp .env.example .env
```
Open `.env` in a text editor and replace the placeholder, for example:
```
MONGODB_URI="mongodb+srv://myuser:mypassword@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority"
```

**3. Test the connection**
```bash
python src/database.py
```
Expected: `Connected to MongoDB Atlas. Database: coimbatore_spatial_db`

**4. Load the data and create the indexes**
```bash
python src/load_data.py
```

**5. Start the application**
```bash
streamlit run src/app.py
```
Your browser opens at <http://localhost:8501>. Choose an operation in the sidebar.

## 13. Expected results
Computed from the sample data (verified independently with a standard-library script; your app should match):

| Operation | Expected result |
|---|---|
| Load data | places 18, roads 5, boundaries 3 inserted |
| `$nearSphere`, hospitals within 3 km of PSG Tech | PSG Hospitals ≈ 0.38 km, G. Kuppuswamy Naidu Memorial Hospital ≈ 2.17 km, Sri Ramakrishna Hospital ≈ 2.84 km |
| KNN, 3 nearest hospitals | the same three, in the same order |
| `$geoWithin`, Coimbatore boundary | 17 of 18 places inside; *Amrita Vishwa Vidyapeetham (Ettimadai)* is outside |
| Aggregation, Peelamedu Zone | hospital 2, college 3, school 2 |
| Aggregation, Race Course Zone | hospital 5, school 1 |
| Distance, PSG Tech to Kovai Medical Center | ≈ 3.9 km (MongoDB and haversine agree within a few metres) |
| Buffer, 3 km around PSG Tech | the 3 hospitals above are inside |
| Intersection, Avinashi Road | Sathy Road, Mettupalayam Road, Sample Link Road |
| Adjacency, Sample Link Road (300 m) | Trichy Road, gap about 150 m |
| Union, Peelamedu Zone + Race Course Zone | one red polygon covering both zones |

## 14. 3-day plan
**Day 1** - Atlas cluster and user, understand GeoJSON, run `load_data.py`, check the collections in Atlas,
create/verify the `2dsphere` index in mongosh, try CRUD and point lookup.

**Day 2** - `$geoWithin`, `$nearSphere`, distance, aggregation, KNN in mongosh first, then through
`spatial_queries.py`; then the Shapely parts: intersection/adjacency, buffer, union.

**Day 3** - Run the Streamlit app, test every sidebar operation, take screenshots, finish this README,
rehearse the demo.

### Testing checklist
- [ ] `python src/database.py` prints the connected message
- [ ] `python src/load_data.py` shows 18 / 5 / 3 documents
- [ ] In Atlas, *Browse Collections* shows 3 collections, and *Indexes* shows `geometry_2dsphere` on each
- [ ] Every operation in the sidebar loads without an error
- [ ] Results match the "Expected results" table
- [ ] CRUD: insert, find, update, delete a test place; seed places cannot be deleted

### Screenshot checklist
1. Atlas *Browse Collections* showing the three collections
2. Atlas *Indexes* tab with the `2dsphere` index
3. App: View all data (points, roads, polygons)
4. App: CRUD page after inserting a place
5. App: Point lookup with a result
6. App: `$geoWithin` (inside vs outside)
7. App: `$nearSphere` 3 km result and table
8. App: Distance between two places
9. App: Count in boundary
10. App: KNN with numbered markers
11. App: Road intersection/adjacency (colours and crossing points)
12. App: 3 km buffer around PSG Tech
13. App: Polygon union
14. Terminal showing `load_data.py` output

## Professor's worksheet alignment
| Professor's Concept | Where It Is Implemented |
|---|---|
| Basic CRUD | `insert_place`, `find_places`, `update_place`, `delete_place` in `spatial_queries.py`; "CRUD" page in the app |
| Point identification | `point_lookup()`; "Point lookup" page |
| `$geoWithin` | `places_within_boundary()`; "Places within a boundary" page |
| `$nearSphere` | `places_near_sphere()`; "Places near PSG Tech" page |
| 2dsphere index | `load_data.py` (`create_index(... GEOSPHERE)`); mongosh commands in section 10 |
| Intersection | `road_names_intersecting()` (`$geoIntersects`); crossing points via Shapely in `classify_roads()`; "Road intersection / adjacency" page |
| Distance measurement | `distance_between()` (`$geoNear`) and `haversine_km()`; "Distance between locations" page |
| Spatial aggregation | `count_by_category_in_boundary()` (`$match` + `$geoWithin` + `$group`); "Count locations" page |
| Proximity | `$nearSphere` page and buffer page (`circle_polygon()` + `places_in_polygon()`) |
| Adjacency | `classify_roads()` in `geometry_operations.py` (roads closer than the chosen gap but not intersecting) |
| KNN / nearest neighbour | `nearest_k()` (`$nearSphere` + `limit(k)`); "Nearest hospitals (KNN)" page |
| Union | `union_polygons()` (Shapely `unary_union`); "Polygon union" page |

## 15. Limitations
- Small, hand-made educational sample; coordinates are approximate and the city boundary is not official.
- Adjacency uses a flat-earth metre conversion for Coimbatore's latitude (accurate enough at city scale).
- `$geoWithin`/`$geoIntersects` use curved (geodesic) edges while Shapely uses straight planar edges;
  differences are negligible at this scale but could matter for borderline cases.
- Buffer is a 64-sided approximation of a circle.
- Union is calculated in Python (MongoDB has no union operator); results are displayed, not stored.
- No authentication, no editing of roads/polygons, no large-scale performance testing.
