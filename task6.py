"""
Task 6: For each movie's top-billed 5 cast (by order), what is the proportion of female
cast? Aggregate by decade and list decades sorted by average female proportion (desc),
including movie counts used. Unknown gender may be ignored.

Solved with a single MongoDB aggregation pipeline. The cast list is stored sorted by
order (done in insert_data.py), so the first 5 elements are the top-billed cast.
Gender: 0 = unknown, 1 = female, 2 = male.
"""

from pprint import pprint

from DbConnector import DbConnector


def task6(db):
    year = {"$year": "$release_date"}
    pipeline = [
        {"$match": {"release_date": {"$ne": None}, "cast.0": {"$exists": True}}},
        # Top 5 billed cast, keeping only those with known gender
        {"$project": {
            "decade": {"$subtract": [year, {"$mod": [year, 10]}]},
            "known": {"$filter": {
                "input": {"$slice": ["$cast", 5]},
                "cond": {"$in": ["$$this.gender", [1, 2]]},
            }},
        }},
        {"$project": {
            "decade": 1,
            "known_count": {"$size": "$known"},
            "female_count": {"$size": {"$filter": {
                "input": "$known", "cond": {"$eq": ["$$this.gender", 1]}}}},
        }},
        # Movies where none of the top 5 have known gender cannot be used
        {"$match": {"known_count": {"$gt": 0}}},
        {"$project": {
            "decade": 1,
            "female_proportion": {"$divide": ["$female_count", "$known_count"]},
        }},
        {"$group": {
            "_id": "$decade",
            "avg_female_proportion": {"$avg": "$female_proportion"},
            "movie_count": {"$sum": 1},
        }},
        {"$sort": {"avg_female_proportion": -1}},
    ]

    return [{
        "decade": f"{int(d['_id'])}s",
        "avg_female_proportion": round(d["avg_female_proportion"], 3),
        "movie_count": d["movie_count"],
    } for d in db.movies.aggregate(pipeline)]


def main():
    connection = DbConnector()
    try:
        result = task6(connection.db)
        print("Task 6: Average female proportion among top-5 billed cast, by decade\n")
        pprint(result, sort_dicts=False, width=120)
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()
