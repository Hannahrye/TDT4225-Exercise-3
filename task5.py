"""
Task 5: By decade (e.g., 1970s, 1980s, ...) and primary genre (first element in genres),
what is the median runtime and movie count? List results sorted by decade then median
runtime (desc).

MongoDB groups the movies per (decade, primary genre). Python computes the exact median
and sorts the result.
"""

from pathlib import Path
from pprint import pprint
from statistics import median

from DbConnector import DbConnector


def task5(db):
    year = {"$year": "$release_date"}
    pipeline = [
        # Need a release date (for the decade) and at least one genre (for the primary genre)
        {"$match": {"release_date": {"$ne": None}, "genres.0": {"$exists": True}}},
        {"$group": {
            "_id": {
                "decade": {"$subtract": [year, {"$mod": [year, 10]}]},   # 1987 -> 1980
                "genre": {"$arrayElemAt": ["$genres.name", 0]},
            },
            "movie_count": {"$sum": 1},
            "runtimes": {"$push": "$runtime"},
        }},
    ]

    result = []
    for g in db.movies.aggregate(pipeline):
        runtimes = [r for r in g["runtimes"] if r is not None]   # unknown runtime is null
        result.append({
            "decade": f"{int(g['_id']['decade'])}s",
            "primary_genre": g["_id"]["genre"],
            "movie_count": g["movie_count"],
            "median_runtime": median(runtimes) if runtimes else None,
        })

    # Decade ascending, then median runtime descending (groups without runtime last)
    result.sort(key=lambda r: (r["decade"], -(r["median_runtime"] or 0)))
    return result


def main():
    connection = DbConnector()
    try:
        result = task5(connection.db)
        print(f"Task 5: Median runtime and movie count for {len(result)} "
              "(decade, primary genre) groups")

        # Show an excerpt in the terminal: the 2010s, the largest decade
        print("\nExcerpt: the 2010s\n")
        pprint([r for r in result if r["decade"] == "2010s"], sort_dicts=False, width=120)

        # Save the full list in the results folder, like in Task 2
        output_dir = Path(__file__).resolve().parent / "results"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "task5_results.txt"
        with output_file.open("w", encoding="utf-8") as file:
            pprint(result, stream=file, sort_dicts=False, width=120)
        print(f"\nAll {len(result)} groups saved to: {output_file}")
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()
