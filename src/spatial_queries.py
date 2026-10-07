from geometry_operations import haversine_km


# ---------------------------------------------------------------- helpers
def point(lon, lat):
    return {"type": "Point", "coordinates": [lon, lat]}


def _clean(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc["_id"] = str(doc["_id"])
    return doc


def get_all(db, collection):
    return [_clean(d) for d in db[collection].find()]


def get_by_name(db, collection, name):
    return _clean(db[collection].find_one({"name": name}))


def lonlat(doc):
    lon, lat = doc["geometry"]["coordinates"]
    return lon, lat


# ----------------------------------------------------------- 1. CRUD
def insert_place(db, name, category, lon, lat, **extra):
    doc = {"name": name, "category": category, "source": "user", **extra,
           "geometry": point(lon, lat)}
    return str(db.places.insert_one(doc).inserted_id)


def find_places(db, query=None):
    return [_clean(d) for d in db.places.find(query or {})]


def update_place(db, name, new_values):
    return db.places.update_one({"name": name}, {"$set": new_values}).modified_count


def delete_place(db, name):
    return db.places.delete_one({"name": name, "source": "user"}).deleted_count


# ------------------------------------------------------ 2. POINT LOOKUP
def point_lookup(db, lon, lat, max_distance_m=200):
    query = {"geometry": {"$nearSphere": {"$geometry": point(lon, lat),
                                          "$maxDistance": max_distance_m}}}
    docs = list(db.places.find(query).limit(1))
    return _clean(docs[0]) if docs else None


# ------------------------------------------------------ 3. $geoWithin
def places_within_boundary(db, boundary_name, categories=None):
    boundary = db.boundaries.find_one({"name": boundary_name})
    query = {"geometry": {"$geoWithin": {"$geometry": boundary["geometry"]}}}
    if categories:
        query["category"] = {"$in": categories}
    return [_clean(d) for d in db.places.find(query)]


# ------------------------------------------------------ 4. $nearSphere
def places_near_sphere(db, lon, lat, max_distance_m, category=None):
    query = {"geometry": {"$nearSphere": {"$geometry": point(lon, lat),
                                          "$maxDistance": max_distance_m}}}
    if category:
        query["category"] = category
    results = []
    for doc in db.places.find(query):
        doc = _clean(doc)
        p_lon, p_lat = lonlat(doc)
        doc["distance_km"] = round(haversine_km(lon, lat, p_lon, p_lat), 3)
        results.append(doc)
    return results


# --------------------------------------------------- 5. DISTANCE ($geoNear)
def distance_between(db, name_a, name_b):
    a = get_by_name(db, "places", name_a)
    b = get_by_name(db, "places", name_b)
    pipeline = [{"$geoNear": {"near": a["geometry"], "distanceField": "dist_m",
                              "spherical": True, "query": {"name": name_b}}}]
    mongo_km = list(db.places.aggregate(pipeline))[0]["dist_m"] / 1000
    a_lon, a_lat = lonlat(a)
    b_lon, b_lat = lonlat(b)
    return {"a": a, "b": b,
            "mongodb_km": round(mongo_km, 3),
            "haversine_km": round(haversine_km(a_lon, a_lat, b_lon, b_lat), 3)}


# ------------------------------------------------- 6. SPATIAL AGGREGATION
def count_by_category_in_boundary(db, boundary_name):
    boundary = db.boundaries.find_one({"name": boundary_name})
    pipeline = [
        {"$match": {"geometry": {"$geoWithin": {"$geometry": boundary["geometry"]}}}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    return {row["_id"]: row["count"] for row in db.places.aggregate(pipeline)}


# --------------------------------------------- 7. INTERSECTION (database part)
def road_names_intersecting(db, road_name):
    road = db.roads.find_one({"name": road_name})
    query = {"geometry": {"$geoIntersects": {"$geometry": road["geometry"]}},
             "name": {"$ne": road_name}}
    return {d["name"] for d in db.roads.find(query, {"name": 1})}


# ---------------------------------------------------------- 8. BUFFER query
def places_in_polygon(db, polygon_geometry):
    query = {"geometry": {"$geoWithin": {"$geometry": polygon_geometry}}}
    return [_clean(d) for d in db.places.find(query)]


# ------------------------------------------------------------ 9. KNN
def nearest_k(db, lon, lat, category, k=3):
    query = {"category": category,
             "geometry": {"$nearSphere": {"$geometry": point(lon, lat)}}}
    results = []
    for doc in db.places.find(query).limit(k):
        doc = _clean(doc)
        p_lon, p_lat = lonlat(doc)
        doc["distance_km"] = round(haversine_km(lon, lat, p_lon, p_lat), 3)
        results.append(doc)
    return results
