"""
Task 2: List actor pairs that have co-starred in >= 3 movies together, their number of
co-appearances, and their average movie vote_average. Sort by number of co-appearances.

MongoDB fetches the cast and vote_average of each movie. Python builds the actor pairs,
since creating all pairs within a list is much simpler in Python than in a pipeline.
"""

from collections import Counter
from itertools import combinations
from pprint import pprint
from pathlib import Path

from DbConnector import DbConnector


def task2(db):
    # Fetch only what we need: movies with at least two actors
    movies = list(db.movies.find(
        {"cast.1": {"$exists": True}},
        {"cast.id": 1, "cast.name": 1, "vote_average": 1},
    ))

    # Only actors who appear in at least 3 movies can be part of a pair with >= 3 movies.
    # Filtering them first keeps the number of pairs small.
    movies_per_actor = Counter()
    names = {}
    for m in movies:
        for actor in m["cast"]:
            movies_per_actor[actor["id"]] += 1
            names[actor["id"]] = actor["name"]

    pair_count = Counter()
    pair_votes = {}
    for m in movies:
        actors = sorted({a["id"] for a in m["cast"] if movies_per_actor[a["id"]] >= 3})
        for pair in combinations(actors, 2):
            pair_count[pair] += 1
            if m.get("vote_average") is not None:
                pair_votes.setdefault(pair, []).append(m["vote_average"])

    result = []
    for (a, b), count in pair_count.items():
        if count >= 3:
            votes = pair_votes.get((a, b), [])
            result.append({
                "actor_1": names[a],
                "actor_2": names[b],
                "co_appearances": count,
                "avg_vote_average": round(sum(votes) / len(votes), 2) if votes else None,
            })

    result.sort(key=lambda r: r["co_appearances"], reverse=True)
    return result


def main():
    connection = DbConnector()
    try:
        result = task2(connection.db)

        print(f"Task 2: {len(result):,} actor pairs have co-starred in >= 3 movies.")
        print("Top 20 by number of co-appearances:\n")
        pprint(result[:20], sort_dicts=False)

        # Save all pairs in a results folder next to this script
        output_dir = Path(__file__).resolve().parent / "results"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "task2_results.txt"

        with output_file.open("w", encoding="utf-8") as file:
            pprint(result, stream=file, sort_dicts=False)

        print(f"\nAll {len(result):,} pairs saved to: {output_file}")

    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()
