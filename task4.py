"""
Task 4: For film collections (belongs_to_collection.name not null) with >= 3 movies, which
10 collections have the largest total revenue? For each, report movie count, total revenue,
median vote_average, and the earliest -> latest release date.

MongoDB groups the movies per collection. Python computes the exact median and formats
the dates, the same way as in Task 1.
"""

from pprint import pprint
from statistics import median

from DbConnector import DbConnector


def task4(db):
    pipeline = [
        {"$match": {"belongs_to_collection.name": {"$ne": None}}},
        {"$group": {
            "_id": "$belongs_to_collection.id",
            "collection": {"$first": "$belongs_to_collection.name"},
            "movie_count": {"$sum": 1},
            "total_revenue": {"$sum": "$revenue"},      # unknown revenue (null) is skipped
            "votes": {"$push": "$vote_average"},
            "earliest": {"$min": "$release_date"},
            "latest": {"$max": "$release_date"},
        }},
        {"$match": {"movie_count": {"$gte": 3}}},
        {"$sort": {"total_revenue": -1}},
        {"$limit": 10},
    ]

    result = []
    for c in db.movies.aggregate(pipeline):
        votes = [v for v in c["votes"] if v is not None]
        result.append({
            "collection": c["collection"],
            "movie_count": c["movie_count"],
            "total_revenue": c["total_revenue"],
            "median_vote_average": median(votes) if votes else None,
            "release_dates": f"{c['earliest']:%Y-%m-%d} -> {c['latest']:%Y-%m-%d}",
        })
    return result


def main():
    connection = DbConnector()
    try:
        result = task4(connection.db)
        print("Task 4: Top 10 collections (>= 3 movies) by total revenue\n")
        pprint(result, sort_dicts=False)
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()
