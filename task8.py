"""
Task 8: Which 20 director-actor pairs with >= 3 collaborations (same movie) have the highest
mean vote_average, considering only movies with vote_count >= 100?
Include the pair's films count and mean revenue.

Solved with a single MongoDB aggregation pipeline.
Directors who act in their own movies are not paired with themselves.
"""

from pprint import pprint

from DbConnector import DbConnector


def task8(db):
    pipeline = [
        {"$match": {"vote_count": {"$gte": 100}}},
        {"$project": {"directors.id": 1, "directors.name": 1, "cast.id": 1, "cast.name": 1,
                      "vote_average": 1, "revenue": 1}},
        # One document per (movie, director, actor)
        {"$unwind": "$directors"},
        {"$unwind": "$cast"},
        # Skip directors acting in their own movies (a person is not a pair with themselves)
        {"$match": {"$expr": {"$ne": ["$directors.id", "$cast.id"]}}},
        {"$group": {
            "_id": {"director": "$directors.id", "actor": "$cast.id"},
            "director": {"$first": "$directors.name"},
            "actor": {"$first": "$cast.name"},
            "films_count": {"$sum": 1},
            "mean_vote_average": {"$avg": "$vote_average"},
            "mean_revenue": {"$avg": "$revenue"},          # unknown revenue (null) is skipped
        }},
        {"$match": {"films_count": {"$gte": 3}}},
        # Highest mean vote_average first; more films breaks ties
        {"$sort": {"mean_vote_average": -1, "films_count": -1}},
        {"$limit": 20},
        {"$project": {
            "_id": 0,
            "director": 1,
            "actor": 1,
            "films_count": 1,
            "mean_vote_average": {"$round": ["$mean_vote_average", 2]},
            "mean_revenue": {"$round": ["$mean_revenue", 0]},
        }},
    ]
    return list(db.movies.aggregate(pipeline, allowDiskUse=True))


def main():
    connection = DbConnector()
    try:
        result = task8(connection.db)
        print("Task 8: Top 20 director-actor pairs (>= 3 films, vote_count >= 100) "
              "by mean vote_average\n")
        pprint(result, sort_dicts=False, width=120)
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()
