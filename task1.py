"""
Task 1: Considering only crew with job = Director, which 10 directors with >= 5 movies
have the highest median revenue? Also report each director's movie count and mean vote_average.

"""

from pprint import pprint
from statistics import median

from DbConnector import DbConnector


def task1(db):
    pipeline = [
        {"$match": {"directors.0": {"$exists": True}}},
        {"$unwind": "$directors"},
        {"$group": {
            "_id": "$directors.id",
            "director": {"$first": "$directors.name"},
            "movie_count": {"$sum": 1},
            "revenues": {"$push": "$revenue"},
            "mean_vote_average": {"$avg": "$vote_average"},
        }},
        {"$match": {"movie_count": {"$gte": 5}}},
    ]

    directors = []

    for d in db.movies.aggregate(pipeline):
        # Unknown revenue is excluded from the median.
        known_revenues = [
            value for value in d.pop("revenues")
            if value is not None
        ]

        # A director without known revenue cannot be ranked.
        if not known_revenues:
            continue

        d["movies_with_known_revenue"] = len(known_revenues)
        d["median_revenue"] = median(known_revenues)

        average = d["mean_vote_average"]
        d["mean_vote_average"] = (
            round(average, 2) if average is not None else None
        )

        directors.append(d)

    # Use person ID to make ordering consistent when medians are equal.
    directors.sort(
        key=lambda d: (-d["median_revenue"], d["_id"])
    )

    result = directors[:10]
    for d in result:
        del d["_id"]

    return result


def main():
    connection = DbConnector()
    try:
        result = task1(connection.db)
        print(
            "Task 1: Top 10 directors (>= 5 movies total) "
            "by median known revenue\n"
        )
        pprint(result, sort_dicts=False)
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()