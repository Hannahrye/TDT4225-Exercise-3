"""
Task 3: List the top 10 actors (with >= 10 credited movies) that have the widest genre
breadth. Report the actor, the number of distinct genres they've appeared in, and up to
5 example genres.

Solved with a single MongoDB aggregation pipeline.
"""

from pprint import pprint

from DbConnector import DbConnector


def task3(db):
    pipeline = [
        # One document per (movie, actor, genre)
        {"$project": {"cast.id": 1, "cast.name": 1, "genres.name": 1}},
        {"$unwind": "$cast"},
        # Keep movies without genres, so they still count as credited movies
        {"$unwind": {"path": "$genres", "preserveNullAndEmptyArrays": True}},
        # Per actor: the set of distinct movies and the set of distinct genres
        {"$group": {
            "_id": "$cast.id",
            "actor": {"$first": "$cast.name"},
            "movies": {"$addToSet": "$_id"},
            "genres": {"$addToSet": "$genres.name"},
        }},
        {"$addFields": {
            "movie_count": {"$size": "$movies"},
            "genre_count": {"$size": "$genres"},
        }},
        {"$match": {"movie_count": {"$gte": 10}}},
        # Widest genre breadth first; more movies breaks ties
        {"$sort": {"genre_count": -1, "movie_count": -1}},
        {"$limit": 10},
        {"$project": {
            "_id": 0,
            "actor": 1,
            "movie_count": 1,
            "genre_count": 1,
            "example_genres": {"$slice": ["$genres", 5]},
        }},
    ]
    return list(db.movies.aggregate(pipeline, allowDiskUse=True))


def main():
    connection = DbConnector()
    try:
        result = task3(connection.db)
        print("Task 3: Top 10 actors (>= 10 movies) by number of distinct genres\n")
        pprint(result, sort_dicts=False)
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()
