"""
Task 9: Among movies where original_language != "en" but at least one production company or
country is United States, which are the top 10 original languages by count?
For each language, report the count and one example title.

Solved with a single MongoDB aggregation pipeline.

Note: production companies in this dataset only have a name and an id, no country. A movie
is therefore counted as American if one of its production countries is the US (ISO code
"US"), or if a production company has "United States" in its name.
"""

from pprint import pprint

from DbConnector import DbConnector


def task9(db):
    pipeline = [
        {"$match": {
            "original_language": {"$nin": ["en", None]},
            "$or": [
                {"production_countries.iso_3166_1": "US"},
                {"production_companies.name": {"$regex": "United States", "$options": "i"}},
            ],
        }},
        {"$group": {
            "_id": "$original_language",
            "count": {"$sum": 1},
            "example_title": {"$first": "$title"},
        }},
        {"$sort": {"count": -1}},
        {"$limit": 10},
        {"$project": {"_id": 0, "original_language": "$_id", "count": 1, "example_title": 1}},
    ]
    return list(db.movies.aggregate(pipeline))


def main():
    connection = DbConnector()
    try:
        result = task9(connection.db)
        print("Task 9: Top 10 non-English original languages among US-produced movies\n")
        pprint(result, sort_dicts=False, width=120)
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()
