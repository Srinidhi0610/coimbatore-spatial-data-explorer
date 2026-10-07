from math import asin, atan2, cos, degrees, pi, radians, sin, sqrt

from shapely.geometry import LineString, mapping, shape
from shapely.ops import unary_union

EARTH_RADIUS_KM = 6371.0088


# ---------------------------------------------------------------- distance
def haversine_km(lon1, lat1, lon2, lat2):
    
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


# ------------------------------------------------------------------ buffer
def circle_polygon(lon, lat, radius_km, points=64):
    """
    Build a GeoJSON Polygon that approximates a circle of radius_km around a point.

    Why: a BUFFER is "everything within X km of something". We draw it as a polygon
    so it can be shown on the map and also used in a $geoWithin query.
    Worksheet concept: BUFFER / PROXIMITY.
    """
    lat1, lon1 = radians(lat), radians(lon)
    angular_distance = radius_km / EARTH_RADIUS_KM
    ring = []
    for i in range(points):
        bearing = 2 * pi * i / points
        lat2 = asin(sin(lat1) * cos(angular_distance)
                    + cos(lat1) * sin(angular_distance) * cos(bearing))
        lon2 = lon1 + atan2(sin(bearing) * sin(angular_distance) * cos(lat1),
                            cos(angular_distance) - sin(lat1) * sin(lat2))
        ring.append([degrees(lon2), degrees(lat2)])
    ring.reverse()           # bearings go clockwise; GeoJSON outer rings must be counter-clockwise
    ring.append(ring[0])     # a polygon ring must end where it starts
    return {"type": "Polygon", "coordinates": [ring]}


# ------------------------------------------------- intersection / adjacency
def _to_meters(line):
    """
    Convert a Shapely LineString from lon/lat degrees to rough x/y metres.

    Why: Shapely measures distance in the units of the coordinates (degrees), which
    is not useful. Around Coimbatore, 1 degree latitude ~ 110.6 km and
    1 degree longitude ~ 111.3 km * cos(latitude). That is accurate enough here.
    """
    lon_scale = 111320 * cos(radians(11.0))
    lat_scale = 110574
    return LineString([(x * lon_scale, y * lat_scale) for x, y in line.coords])


def _points_of(geometry):
    """Return the crossing point(s) of an intersection result as [[lon, lat], ...]."""
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Point":
        return [[geometry.x, geometry.y]]
    if hasattr(geometry, "geoms"):                    # MultiPoint / GeometryCollection
        points = []
        for part in geometry.geoms:
            points.extend(_points_of(part))
        return points
    return [[geometry.centroid.x, geometry.centroid.y]]   # roads share a stretch of line


def classify_roads(selected_road, other_roads, intersecting_names, adjacent_m=300):
    """
    For the selected road, label every other road as 'intersects' or 'adjacent'.

    intersecting_names : names MongoDB's $geoIntersects already found (database side).
    We then use Shapely to (a) find the exact crossing point and (b) measure the gap
    for roads that do NOT intersect, and call them 'adjacent' if the gap is small.

    Worksheet concepts: INTERSECTION and ADJACENCY (adjacency = very close proximity).
    """
    selected_shape = shape(selected_road["geometry"])
    selected_m = _to_meters(selected_shape)
    results = []
    for road in other_roads:
        if road["name"] == selected_road["name"]:
            continue
        other_shape = shape(road["geometry"])
        if road["name"] in intersecting_names:
            crossing = _points_of(selected_shape.intersection(other_shape))
            results.append({"name": road["name"], "relation": "intersects",
                            "gap_m": 0, "points": crossing})
        else:
            gap = selected_m.distance(_to_meters(other_shape))
            if gap <= adjacent_m:
                results.append({"name": road["name"], "relation": "adjacent",
                                "gap_m": round(gap), "points": []})
    return results


# ------------------------------------------------------------------- union
def union_polygons(geometry_a, geometry_b):
    """
    Merge two GeoJSON polygons into one GeoJSON geometry.

    Why: UNION combines two regions into a single region (the overlap is not counted twice).
    Worksheet concept: UNION.
    """
    merged = unary_union([shape(geometry_a), shape(geometry_b)])
    return mapping(merged)


def polygon_rings(geometry):
    """Return the outer ring(s) of a Polygon or MultiPolygon as lists of [lon, lat]."""
    if geometry["type"] == "Polygon":
        return [[list(p) for p in geometry["coordinates"][0]]]
    return [[list(p) for p in poly[0]] for poly in geometry["coordinates"]]
