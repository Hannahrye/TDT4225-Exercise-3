import ast
from datetime import datetime

import pandas as pd
from tabulate import tabulate

from collections import OrderedDict
from DbConnector import DbConnector

import sys

DATA = "data/"
PLACEHOLDERS = {"", "-", "No overview found.", "No Overview"}


# ---------------------------------------------------------------- hjelpere
def parse_literal(x):
    """Tekst med Python-literal -> liste/dict. None hvis tom."""
    if pd.isna(x):
        return None
    return ast.literal_eval(x)


def clean(v):
    """NaN -> None, slik at MongoDB får null i stedet for NaN."""
    return None if pd.isna(v) else v


def to_int(v):
    return None if pd.isna(v) else int(v)


def clean_text(v):
    """Tom tekst og plassholdere -> None."""
    if pd.isna(v) or str(v).strip() in PLACEHOLDERS:
        return None
    return str(v).strip()


def amount(v):
    """Budget/revenue: 0, NaN og verdier under 1 000 USD -> None."""
    if pd.isna(v) or v < 1000:
        return None
    return int(v)


def to_bool(v):
    return {"True": True, "False": False, True: True, False: False}.get(v)


def to_date(v):
    d = pd.to_datetime(v, format="%Y-%m-%d", errors="coerce")
    return None if pd.isna(d) else d.to_pydatetime()


# ---------------------------------------------------------------- del 1
def load_movies():
    m = pd.read_csv(DATA + "movies_metadata.csv", low_memory=False)
    n_raw = len(m)

    # Beslutning 4: fjern de 3 ødelagte radene og den halve filmen over hver av dem
    bad = pd.to_numeric(m["id"], errors="coerce").isna()
    m = m.drop(m.index[bad].union(m.index[bad] - 1))
    n_malformed = n_raw - len(m)

    # Beslutning 1: behold første forekomst av hver id
    m["id"] = m["id"].astype(int)
    n_before = len(m)
    m = m.drop_duplicates("id", keep="first")
    n_dups = n_before - len(m)

    # Tall som skal være tall
    for c in ["budget", "revenue", "runtime", "vote_average", "vote_count", "popularity"]:
        m[c] = pd.to_numeric(m[c], errors="coerce")

    print(tabulate([["Rader i CSV", n_raw],
                    ["Fjernet: ødelagte rader", n_malformed],
                    ["Fjernet: dupliserte id-er", n_dups],
                    ["Filmer igjen", len(m)]],
                   headers=["", "Antall"], tablefmt="github"))
    return m


def movie_doc(r):
    """Én rad fra movies_metadata -> ett MongoDB-dokument (uten cast/crew/keywords)."""
    vote_count = to_int(r["vote_count"])
    return {
        "_id": int(r["id"]),
        "imdb_id": clean(r["imdb_id"]),
        "title": clean(r["title"]),
        "original_title": clean(r["original_title"]),
        "original_language": clean(r["original_language"]),
        "overview": clean_text(r["overview"]),                 # beslutning 7
        "tagline": clean_text(r["tagline"]),
        "status": clean(r["status"]),
        "adult": to_bool(r["adult"]),
        "video": to_bool(r["video"]),
        "release_date": to_date(r["release_date"]),
        "runtime": None if pd.isna(r["runtime"]) or r["runtime"] == 0 else float(r["runtime"]),
        "budget": amount(r["budget"]),                         # beslutning 3
        "revenue": amount(r["revenue"]),
        "vote_count": vote_count,
        "vote_average": None if not vote_count else clean(r["vote_average"]),  # beslutning 6
        "popularity": clean(r["popularity"]),
        "homepage": clean(r["homepage"]),
        "poster_path": clean(r["poster_path"]),
        "genres": parse_literal(r["genres"]) or [],            # [{"id", "name"}], rekkefølge bevart
        "production_companies": parse_literal(r["production_companies"]) or [],
        "production_countries": parse_literal(r["production_countries"]) or [],
        "spoken_languages": parse_literal(r["spoken_languages"]) or [],
        "belongs_to_collection": parse_literal(r["belongs_to_collection"]),  # dict eller None
    }


def merge_people(entries, person_keys, role_keys):
    """Beslutning 11: én oppføring per person (id), alle roller i en liste."""
    people = OrderedDict()
    for e in entries:
        p = people.setdefault(e["id"], {**{k: e.get(k) for k in person_keys}, "roles": []})
        p["roles"].append({k: e.get(k) for k in role_keys})
    return list(people.values())


def load_credits():
    c = pd.read_csv(DATA + "credits.csv")
    c = c.drop_duplicates("id", keep="first")                   # beslutning 2
    credits, n_cast_raw = {}, 0
    for _, r in c.iterrows():
        cast_raw = parse_literal(r["cast"]) or []
        crew_raw = parse_literal(r["crew"]) or []
        n_cast_raw += len(cast_raw)

        cast = merge_people(cast_raw, ["id", "name", "gender", "profile_path"],
                            ["character", "cast_id", "credit_id", "order"])
        for p in cast:                                          # laveste order per skuespiller
            p["order"] = min(role["order"] for role in p["roles"])
        cast.sort(key=lambda p: p["order"])

        directors = merge_people([d for d in crew_raw if d.get("job") == "Director"],
                                 ["id", "name", "gender", "profile_path"],
                                 ["credit_id", "job", "department"])
        credits[int(r["id"])] = (cast, directors)
    print(f"\nCredits: {len(credits):,} filmer, {n_cast_raw:,} cast-oppføringer før sammenslåing")
    return credits


def load_keywords():
    k = pd.read_csv(DATA + "keywords.csv").drop_duplicates("id", keep="first")
    return {int(r["id"]): parse_literal(r["keywords"]) or [] for _, r in k.iterrows()}


def insert_movies(db, docs, batch_size=5000):
    db.movies.drop()                                  # gjør skriptet trygt å kjøre flere ganger
    for i in range(0, len(docs), batch_size):
        db.movies.insert_many(docs[i:i + batch_size])
    print(f"\nSatt inn i movies: {db.movies.count_documents({}):,} dokumenter")

def build_link_map(m):
    """MovieLens movieId -> TMDB-id, etter beslutning 5."""
    links = pd.read_csv(DATA + "links.csv")
    n_raw = len(links)
    links = links.dropna(subset=["tmdbId"])
    links["tmdbId"] = links["tmdbId"].astype(int)
    n_no_tmdb = n_raw - len(links)

    imdb = (m.set_index("id")["imdb_id"].str.replace("tt", "", regex=False)
            .pipe(pd.to_numeric, errors="coerce"))
    links["imdb_meta"] = links["tmdbId"].map(imdb)
    in_meta = links["tmdbId"].isin(m["id"])
    mismatch = in_meta & links["imdb_meta"].notna() & (links["imdb_meta"] != links["imdbId"])
    keep = in_meta & ~mismatch

    print(tabulate([["Linker i CSV", n_raw],
                    ["Fjernet: uten tmdbId", n_no_tmdb],
                    ["Fjernet: ikke i metadata", (~in_meta).sum()],
                    ["Fjernet: feil IMDb-id", mismatch.sum()],
                    ["Linker som brukes", keep.sum()]],
                   headers=["", "Antall"], tablefmt="github"))
    return dict(zip(links.loc[keep, "movieId"], links.loc[keep, "tmdbId"]))


def insert_ratings(db, link_map, chunk_size=500_000):
    db.ratings.drop()
    n_read = n_inserted = 0
    reader = pd.read_csv(DATA + "ratings.csv", chunksize=chunk_size,
                         dtype={"userId": "int32", "movieId": "int32",
                                "rating": "float32", "timestamp": "int64"})
    for i, chunk in enumerate(reader, start=1):
        n_read += len(chunk)
        chunk["movieId"] = chunk["movieId"].map(link_map)
        chunk = chunk.dropna(subset=["movieId"])               # beslutning 8
        docs = [{"userId": int(u), "movieId": int(mv), "rating": float(r),
                 "timestamp": t.to_pydatetime()}
                for u, mv, r, t in zip(chunk["userId"], chunk["movieId"], chunk["rating"],
                                       pd.to_datetime(chunk["timestamp"], unit="s"))]
        if docs:
            db.ratings.insert_many(docs, ordered=False)
        n_inserted += len(docs)
        print(f"  Bit {i}: lest {n_read:,}, satt inn {n_inserted:,}", end="\r")

    print(f"\n\nRatinger lest: {n_read:,}")
    print(f"Ikke koblet (fjernet): {n_read - n_inserted:,}")
    print(f"Satt inn i ratings: {db.ratings.count_documents({}):,} dokumenter")
    
def main():
    only_ratings = "ratings" in sys.argv
    m = load_movies()
    connection = DbConnector()
    try:
        db = connection.db
        if not only_ratings:
            credits = load_credits()
            keywords = load_keywords()
            docs = []
            for _, r in m.iterrows():
                d = movie_doc(r)
                d["cast"], d["directors"] = credits.get(d["_id"], ([], []))
                d["keywords"] = keywords.get(d["_id"], [])
                docs.append(d)
            insert_movies(db, docs)

        link_map = build_link_map(m)
        insert_ratings(db, link_map)
        print("Stikkprøve:", db.ratings.find_one({}, {"_id": 0}))
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()