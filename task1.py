"""
Task 1: Considering only crew with job = Director, which 10 directors with >= 5 movies
have the highest median revenue? Also report each director's movie count and mean vote_average.

Choice: only movies with known revenue are used. revenue is stored as null when it is
unknown (0 or < 1000 USD in the CSV), so a director's median and movie count are based on
the movies where revenue is actually known. Otherwise a director with 5 movies but only one
known revenue would get a "median" based on a single movie.
"""

from pprint import pprint
from statistics import median

from DbConnector import DbConnector


def task1(db):
    pipeline = [
        # Only movies with known revenue and at least one director
        {"$match": {"revenue": {"$ne": None}, "directors.0": {"$exists": True}}},
        # One document per (movie, director), so co-directed movies count for each director
        {"$unwind": "$directors"},
        # Group on director id, since different people can share a name
        {"$group": {
            "_id": "$directors.id",
            "director": {"$first": "$directors.name"},
            "movie_count": {"$sum": 1},
            "revenues": {"$push": "$revenue"},
            "mean_vote_average": {"$avg": "$vote_average"},  # $avg ignores null
        }},
        {"$match": {"movie_count": {"$gte": 5}}},
    ]
    directors = list(db.movies.aggregate(pipeline))

    # Exact median computed in Python (MongoDB's $median is approximate)
    for d in directors:
        d["median_revenue"] = median(d.pop("revenues"))
        d["mean_vote_average"] = round(d["mean_vote_average"], 2)
        del d["_id"]

    directors.sort(key=lambda d: d["median_revenue"], reverse=True)
    return directors[:10]


def main():
    connection = DbConnector()
    try:
        result = task1(connection.db)
        print("Task 1: Top 10 directors (>= 5 movies with known revenue) by median revenue\n")
        pprint(result, sort_dicts=False)
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()
