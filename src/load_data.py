import json

from pymongo import GEOSPHERE

from database import ROOT, get_db

FILES = {
    "places": "places.geojson",        # Point
    "roads": "roads.geojson",          # LineString
    "boundaries": "boundaries.geojson" # Polygon
}


def read_geojson(filename):
    with open(ROOT / "data" / filename, encoding="utf-8") as f:
        return json.load(f)["features"]


def feature_to_document(feature):
    document = dict(feature["properties"])
    document["geometry"] = feature["geometry"]
    return document


def main():
    db = get_db()
    db.command("ping")
    print("Connected to MongoDB Atlas.\n")

    for collection_name, filename in FILES.items():
        documents = [feature_to_document(f) for f in read_geojson(filename)]
        collection = db[collection_name]

        collection.delete_many({})                 # start clean
        collection.insert_many(documents)          # insert all features

        collection.create_index([("geometry", GEOSPHERE)])
        collection.create_index("name", unique=True)

        print(f"{collection_name:<11} inserted {len(documents):>2} documents  (2dsphere index on 'geometry')")

    print("\nDone. Indexes on places:", list(db.places.index_information().keys()))


if __name__ == "__main__":
    main()
