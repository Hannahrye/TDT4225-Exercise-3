"""
Task 10: For each user, what is their ratings count, population variance of ratings, and
number of distinct genres rated? List the top 10 most genre-diverse users, and separately
the top 10 highest-variance users (only users with >= 20 ratings).

The ratings collection has ~26 million documents, so this is solved in one pass:
1. The genres of every movie are loaded from MongoDB into a dictionary (fast lookups).
2. All ratings are read from MongoDB once. For each user, Python keeps the number of
   ratings, the sum and sum of squares of the ratings (for the variance), and the set of
   genres seen.
Population variance = mean of squares - square of mean.
The >= 20 ratings limit is applied to both lists.
"""

from pprint import pprint

from DbConnector import DbConnector


def task10(db):
    # 1. movieId -> set of genre names
    movie_genres = {
        m["_id"]: {g["name"] for g in m.get("genres", [])}
        for m in db.movies.find({}, {"genres.name": 1})
    }

    # 2. One pass over all ratings: userId -> [count, sum, sum of squares, genres]
    users = {}
    cursor = db.ratings.find({}, {"_id": 0, "userId": 1, "movieId": 1, "rating": 1},
                             batch_size=50_000)
    for i, r in enumerate(cursor, start=1):
        u = users.get(r["userId"])
        if u is None:
            u = users[r["userId"]] = [0, 0.0, 0.0, set()]
        u[0] += 1
        u[1] += r["rating"]
        u[2] += r["rating"] ** 2
        u[3] |= movie_genres.get(r["movieId"], set())
        if i % 2_000_000 == 0:
            print(f"  ...read {i:,} ratings")

    # 3. Final statistics per user (only users with >= 20 ratings)
    result = []
    for user_id, (count, total, total_sq, genres) in users.items():
        if count >= 20:
            mean = total / count
            result.append({
                "userId": user_id,
                "ratings_count": count,
                "variance": round(total_sq / count - mean ** 2, 3),
                "distinct_genres": len(genres),
            })

    print(f"\nUsers in total: {len(users):,}   Users with >= 20 ratings: {len(result):,}")

    # More ratings breaks ties in both lists
    most_diverse = sorted(result, key=lambda r: (r["distinct_genres"], r["ratings_count"]),
                          reverse=True)[:10]
    highest_variance = sorted(result, key=lambda r: (r["variance"], r["ratings_count"]),
                              reverse=True)[:10]
    return most_diverse, highest_variance


def main():
    connection = DbConnector()
    try:
        most_diverse, highest_variance = task10(connection.db)
        print("\nTask 10a: Top 10 most genre-diverse users (>= 20 ratings)\n")
        pprint(most_diverse, sort_dicts=False, width=120)
        print("\nTask 10b: Top 10 highest-variance users (>= 20 ratings)\n")
        pprint(highest_variance, sort_dicts=False, width=120)
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()
