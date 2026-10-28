"""
Task 7: Using a text search over overview and tagline, which 20 movies matching "noir" or
"neo-noir" (and vote_count >= 50) have the highest vote_average?
Return title, year, vote_average, and vote_count.

Solved with a MongoDB text index and a single aggregation pipeline.

Note on the search term: MongoDB's text index splits words on hyphens, so "neo-noir" is
stored as the two words "neo" and "noir". Searching for "noir" therefore matches both
"noir" and "neo-noir". Searching for "neo-noir" directly would also match every movie
containing the word "neo" on its own (e.g. the character Neo in The Matrix).
"""

from pprint import pprint

from DbConnector import DbConnector


def task7(db):
    # A collection can only have one text index; creating the same one again does nothing
    db.movies.create_index([("overview", "text"), ("tagline", "text")])

    pipeline = [
        {"$match": {"$text": {"$search": "noir"}, "vote_count": {"$gte": 50}}},
        {"$sort": {"vote_average": -1, "vote_count": -1}},
        {"$limit": 20},
        {"$project": {
            "_id": 0,
            "title": 1,
            "year": {"$year": "$release_date"},
            "vote_average": 1,
            "vote_count": 1,
        }},
    ]
    return list(db.movies.aggregate(pipeline))


def main():
    connection = DbConnector()
    try:
        result = task7(connection.db)
        print("Task 7: Top 20 'noir' / 'neo-noir' movies (vote_count >= 50) by vote_average\n")
        pprint(result, sort_dicts=False, width=120)
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()
