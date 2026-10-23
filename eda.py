import os
import pandas as pd
from tabulate import tabulate
import matplotlib.pyplot as plt
import ast
from collections import Counter
import numpy as np
from itertools import combinations

DATA = "data/"
OUT = "eda_results/"          # figurer og tabeller til rapporten
os.makedirs(OUT, exist_ok=True)

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 50)


def load_all():
    movies = pd.read_csv(DATA + "movies_metadata.csv", low_memory=False)
    credits = pd.read_csv(DATA + "credits.csv")
    keywords = pd.read_csv(DATA + "keywords.csv")
    links = pd.read_csv(DATA + "links.csv")
    # Mindre datatyper for å spare minne på 26 mill. rader
    ratings = pd.read_csv(
        DATA + "ratings.csv",
        dtype={"userId": "int32", "movieId": "int32",
               "rating": "float32", "timestamp": "int64"},
    )
    return {"movies_metadata": movies, "credits": credits,
            "keywords": keywords, "links": links, "ratings": ratings}



def short(value, n=50):
    """Kort ned lange verdier så tabellen holder seg lesbar."""
    s = str(value)
    return s if len(s) <= n else s[:n - 3] + "..."


def step1_overview(dfs):
    print("\n########## STEG 1: OVERSIKT ##########\n")

    # Samletabell for alle filer
    summary = [
        [name, f"{df.shape[0]:,}", df.shape[1],
         f"{df.memory_usage(deep=True).sum() / 1024**2:,.1f}"]
        for name, df in dfs.items()
    ]
    print(tabulate(summary,
                   headers=["Fil", "Rader", "Kolonner", "MB i minnet"],
                   tablefmt="github", disable_numparse=True))

    # Én tabell per fil: kolonne, datatype og eksempelverdi
    for name, df in dfs.items():
        print(f"\n\n=== {name} ===\n")
        rows = [[col, str(df[col].dtype), short(df[col].iloc[0])]
                for col in df.columns]
        print(tabulate(rows,
                       headers=["Kolonne", "Datatype", "Eksempel (rad 0)"],
                       tablefmt="github",disable_numparse=True))


def step2_keys(dfs):
    print("\n########## STEG 2: NØKLER OG RELASJONER ##########\n")
    movies, credits, keywords = dfs["movies_metadata"], dfs["credits"], dfs["keywords"]
    links, ratings = dfs["links"], dfs["ratings"]

    movie_ids = set(pd.to_numeric(movies["id"], errors="coerce").dropna().astype(int))
    credit_ids = set(credits["id"])
    keyword_ids = set(keywords["id"])
    link_tmdb = set(links["tmdbId"].dropna().astype(int))
    link_ml = set(links["movieId"])
    rating_ml = set(ratings["movieId"].unique())

    pairs = [
        ("movies.id", movie_ids, "credits.id", credit_ids),
        ("movies.id", movie_ids, "keywords.id", keyword_ids),
        ("movies.id", movie_ids, "links.tmdbId", link_tmdb),
        ("links.movieId", link_ml, "ratings.movieId", rating_ml),
    ]
    rows = [[a, b, f"{len(A & B):,}", f"{len(A - B):,}", f"{len(B - A):,}"]
            for a, A, b, B in pairs]
    print("Overlapp mellom unike nøkler:")
    print(tabulate(rows, headers=["Nøkkel A", "Nøkkel B", "I begge",
                                  "Kun i A", "Kun i B"], tablefmt="github"))

    # Er nøklene unike i hver fil?
    print("\nDupliserte nøkler per fil:")
    dup_rows = [
        ["movies.id", movies["id"].duplicated().sum()],
        ["credits.id", credits["id"].duplicated().sum()],
        ["keywords.id", keywords["id"].duplicated().sum()],
        ["links.movieId", links["movieId"].duplicated().sum()],
        ["links.tmdbId (ekskl. NaN)", links["tmdbId"].dropna().duplicated().sum()],
    ]
    print(tabulate(dup_rows, headers=["Nøkkel", "Duplikater"], tablefmt="github"))

    # Kryssjekk: peker links på samme film som movies, målt med IMDb-id?
    m = movies[["id", "imdb_id"]].copy()
    m["id"] = pd.to_numeric(m["id"], errors="coerce")
    m["imdb_num"] = pd.to_numeric(m["imdb_id"].str.replace("tt", "", regex=False),
                                  errors="coerce")
    j = links.dropna(subset=["tmdbId"]).merge(m, left_on="tmdbId", right_on="id")
    mismatch = (j["imdbId"] != j["imdb_num"]).sum()
    print(f"\nIMDb-kryssjekk: {len(j):,} koblede rader, {mismatch:,} med ulik IMDb-id")

def step3_quality(dfs):
    print("\n########## STEG 3: DATAKVALITET ##########\n")
    movies, credits, keywords, links = (dfs["movies_metadata"], dfs["credits"],
                                        dfs["keywords"], dfs["links"])

    # 3a. Ødelagte rader – og raden rett før, for å se hva som har skjedd
    bad_mask = pd.to_numeric(movies["id"], errors="coerce").isna()
    print(f"3a. Ødelagte rader i movies_metadata: {bad_mask.sum()}\n")

    cols = ["adult", "belongs_to_collection", "budget", "id", "title"]
    rows = []
    for i in movies.index[bad_mask]:
        for idx, part in [(i - 1, "1. halvdel"), (i, "2. halvdel")]:
            rows.append([idx, part] + [short(movies.at[idx, c], 22) for c in cols])
    print(tabulate(rows, headers=["Rad", "Del"] + cols,
                   tablefmt="github", disable_numparse=True))

    # 3b. Duplikater: helt like rader eller ulike?
    movies_ok = movies[~bad_mask]
    rows = []
    for name, df in [("movies", movies_ok), ("credits", credits), ("keywords", keywords)]:
        extra = df["id"].duplicated().sum()
        exact = df.duplicated().sum()
        rows.append([name, extra, exact, extra - exact])
    print("3b. Duplikater:")
    print(tabulate(rows, headers=["Fil", "Ekstra rader med samme id",
                                  "Helt like", "Ulike"], tablefmt="github"))

    # Hvilke kolonner skiller de ulike duplikatene?
    for name, df in [("movies", movies_ok), ("credits", credits)]:
        dups = df[df["id"].duplicated(keep=False)]
        diff_cols = {}
        for _, g in dups.groupby("id"):
            if len(g.drop_duplicates()) > 1:
                for c in g.columns:
                    if g[c].astype(str).nunique() > 1:
                        diff_cols[c] = diff_cols.get(c, 0) + 1
        print(f"\nKolonner som skiller de ulike duplikatene i {name}: {diff_cols}")

    # 3c. TMDB-id-er som forekommer flere ganger i links
    dl = links[links["tmdbId"].notna() & links["tmdbId"].duplicated(keep=False)]
    print(f"\n3c. Rader i links med duplisert tmdbId: {len(dl)} (eksempler):")
    print(tabulate(dl.sort_values("tmdbId").head(8), headers="keys",
                   tablefmt="github", showindex=False))
    n_ratings = dfs["ratings"]["movieId"].isin(dl["movieId"]).sum()
    print(f"Ratinger som gjelder disse MovieLens-id-ene: {n_ratings:,}")

    # 3d. IMDb-avvik mellom links og movies – eksempler
    m = movies_ok[["id", "imdb_id", "title"]].copy()
    m["id"] = m["id"].astype(int)
    m["imdb_num"] = pd.to_numeric(m["imdb_id"].str.replace("tt", "", regex=False),
                                  errors="coerce")
    j = links.dropna(subset=["tmdbId"]).merge(m, left_on="tmdbId", right_on="id")
    mism = j[j["imdbId"] != j["imdb_num"]]
    print(f"\n3d. IMDb-avvik: {len(mism)} (eksempler):")
    print(tabulate(mism[["movieId", "tmdbId", "imdbId", "imdb_num", "title"]].head(10),
                   headers="keys", tablefmt="github", showindex=False))

    
def step4_missing(dfs):
    print("\n########## STEG 4: MANGLENDE VERDIER ##########\n")
    movies = dfs["movies_metadata"]
    movies = movies[pd.to_numeric(movies["id"], errors="coerce").notna()].copy()
    for c in ["budget", "popularity"]:
        movies[c] = pd.to_numeric(movies[c], errors="coerce")
    n = len(movies)

    # Skjulte manglende verdier for tallkolonner
    hidden_num = {
        "budget": movies["budget"] == 0,
        "revenue": movies["revenue"] == 0,
        "runtime": movies["runtime"] == 0,
        "vote_average": movies["vote_count"] == 0,   # snitt av 0 stemmer gir ingen mening
    }

    rows = []
    for c in movies.columns:
        nan = movies[c].isna()
        if c in hidden_num:
            hidden = hidden_num[c] & ~nan
        elif pd.api.types.is_string_dtype(movies[c]) or movies[c].dtype == object:
            s = movies[c].astype(str).str.strip()
            hidden = s.isin(["", "[]", "{}"]) & ~nan
        else:
            hidden = pd.Series(False, index=movies.index)
        total = nan | hidden
        rows.append([c, nan.sum(), hidden.sum(), total.sum(), 100 * total.mean()])

    tab = pd.DataFrame(rows, columns=["Kolonne", "NaN", "Skjult", "Totalt", "%"])
    tab = tab.sort_values("%", ascending=False)
    print(f"movies_metadata ({n:,} filmer):")
    print(tabulate(tab, headers="keys", tablefmt="github",
                   showindex=False, floatfmt=".1f"))
    tab.to_csv(OUT + "missing_values.csv", index=False)   # brukes til figur senere

    # Plassholdertekster i overview og tagline
    for c in ["overview", "tagline"]:
        vc = movies[c].value_counts().head(5)
        rows = [[repr(short(v, 45)), cnt] for v, cnt in vc.items()]
        print(f"\nVanligste verdier i {c}:")
        print(tabulate(rows, headers=["Verdi", "Antall"], tablefmt="github"))

    # Tomme lister i credits og keywords
    print("\nTomme lister i credits/keywords:")
    rows = [["credits.cast", (dfs["credits"]["cast"] == "[]").sum()],
            ["credits.crew", (dfs["credits"]["crew"] == "[]").sum()],
            ["keywords.keywords", (dfs["keywords"]["keywords"] == "[]").sum()]]
    print(tabulate(rows, headers=["Felt", "Tomme lister"], tablefmt="github"))

    # Figur til rapporten
    t = tab[tab["%"] >= 0.1].sort_values("%")
    nan_pct, hid_pct = 100 * t["NaN"] / n, 100 * t["Skjult"] / n
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.barh(t["Kolonne"], nan_pct, height=0.6, color="#2a78d6",
            label="Missing (NaN)", edgecolor="white", linewidth=1.5)
    ax.barh(t["Kolonne"], hid_pct, left=nan_pct, height=0.6, color="#eb6834",
            label="Hidden missing (0, empty list, empty text)",
            edgecolor="white", linewidth=1.5)
    for y, pct in enumerate(t["%"]):
        ax.text(pct + 1, y, f"{pct:.1f} %", va="center", fontsize=9, color="#52514e")
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of films (%)")
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color="#e5e4df"); ax.set_axisbelow(True)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    plt.tight_layout()
    plt.savefig(OUT + "missing_values.png", dpi=200)
    plt.close()

def step5_numeric(dfs):
    print("\n########## STEG 5: NUMERISKE FELTER ##########\n")
    m = dfs["movies_metadata"]
    m = m[pd.to_numeric(m["id"], errors="coerce").notna()].copy()
    for c in ["budget", "popularity"]:
        m[c] = pd.to_numeric(m[c], errors="coerce")

    # 0 regnes som manglende (fra steg 4)
    for c in ["budget", "revenue", "runtime"]:
        m.loc[m[c] == 0, c] = None
    m.loc[m["vote_count"] == 0, "vote_average"] = None

    cols = ["budget", "revenue", "runtime", "vote_average", "vote_count", "popularity"]
    desc = m[cols].describe(percentiles=[.01, .25, .5, .75, .99]).T
    print(tabulate(desc, headers="keys", tablefmt="github", floatfmt=",.1f"))

    # Mistenkelig små eller store verdier
    checks = [
        ("budget < 1,000 USD",   m["budget"] < 1000),
        ("revenue < 1,000 USD",  m["revenue"] < 1000),
        ("runtime < 10 min",     m["runtime"] < 10),
        ("runtime > 300 min",    m["runtime"] > 300),
        ("vote_average = 10",    m["vote_average"] == 10),
        ("vote_count < 10",      m["vote_count"] < 10),
    ]
    print("\nMistenkelige verdier:")
    print(tabulate([[name, mask.sum()] for name, mask in checks],
                   headers=["Sjekk", "Antall filmer"], tablefmt="github"))

    show = ["title", "release_date", "budget", "revenue", "runtime", "vote_count"]
    print("\nEksempler – budget < 1,000:")
    print(tabulate(m.loc[m["budget"] < 1000, show].head(8), headers="keys",
                   tablefmt="github", showindex=False, floatfmt=",.0f"))
    print("\nEksempler – runtime > 300:")
    print(tabulate(m.loc[m["runtime"] > 300, show].sort_values("runtime",
                   ascending=False).head(8), headers="keys", tablefmt="github",
                   showindex=False, floatfmt=",.0f"))


def step6_dates(dfs):
    print("\n########## STEG 6: UTGIVELSESDATOER ##########\n")
    m = dfs["movies_metadata"]
    m = m[pd.to_numeric(m["id"], errors="coerce").notna()].copy()

    raw = m["release_date"]
    parsed = pd.to_datetime(raw, format="%Y-%m-%d", errors="coerce")
    invalid = raw.notna() & parsed.isna()

    print(f"Gyldige datoer: {parsed.notna().sum():,}")
    print(f"Manglende datoer (NaN): {raw.isna().sum():,}")
    print(f"Datoer som ikke kunne tolkes: {invalid.sum():,}")
    if invalid.any():
        print(raw[invalid].head(10).to_string())

    print(f"\nTidligste: {parsed.min().date()}   Seneste: {parsed.max().date()}")

    # Datoer etter at datasettet ble laget (juli 2017) – fremtidige filmer?
    future = parsed > "2017-08-01"
    print(f"\nFilmer med dato etter august 2017: {future.sum()}")
    print(tabulate(m.loc[future, ["title", "release_date", "status", "vote_count"]],
                   headers="keys", tablefmt="github", showindex=False))

    # Status-feltet
    print("\nFordeling av status:")
    print(tabulate(m["status"].value_counts(dropna=False).reset_index().values,
                   headers=["Status", "Antall"], tablefmt="github"))

    # Filmer per tiår
    decade = (parsed.dt.year // 10 * 10).astype("Int64")
    per_dec = decade.value_counts().sort_index()
    print("\nFilmer per tiår:")
    print(tabulate([[f"{d}s", n] for d, n in per_dec.items()],
                   headers=["Tiår", "Antall"], tablefmt="github"))
    per_dec.to_csv(OUT + "films_per_decade.csv")


def parse_literal(x):
    """Tolker Python-literal-tekst til liste/dict. None hvis tom, 'ERROR' hvis ugyldig."""
    if pd.isna(x):
        return None
    try:
        return ast.literal_eval(x)
    except (ValueError, SyntaxError):
        return "ERROR"


def names(lst, key="name"):
    return [d[key] for d in lst] if isinstance(lst, list) else []


def step7_nested(dfs):
    print("\n########## STEG 7: NØSTEDE FELTER ##########\n")
    m = dfs["movies_metadata"]
    m = m[pd.to_numeric(m["id"], errors="coerce").notna()].copy()

    fields = ["genres", "production_companies", "production_countries",
              "spoken_languages", "belongs_to_collection"]
    p = {f: m[f].apply(parse_literal) for f in fields}

    # 7a. Lot alt seg tolke, og hvilken type ble det?
    rows = []
    for f in fields:
        errors = p[f].apply(lambda v: isinstance(v, str)).sum()
        types = p[f].dropna().apply(lambda v: type(v).__name__).value_counts().to_dict()
        rows.append([f, errors, types])
    print("7a. Parsing:")
    print(tabulate(rows, headers=["Felt", "Feil", "Typer"], tablefmt="github"))

    # 7b. Hvilke nøkler finnes i elementene?
    print("\n7b. Nøkler i elementene:")
    for f in fields[:4]:
        keys = Counter(k for lst in p[f] if isinstance(lst, list) for d in lst for k in d)
        print(f"  {f}: {dict(keys)}")

    # 7c. Genres
    g = p["genres"].apply(names)
    cnt = Counter(x for lst in g for x in lst)
    print(f"\n7c. Genres: {len(cnt)} ulike")
    print(tabulate(cnt.most_common(), headers=["Genre", "Filmer"], tablefmt="github"))
    print("\nAntall genres per film:")
    print(tabulate(g.apply(len).value_counts().sort_index().reset_index().values,
                   headers=["Genres", "Filmer"], tablefmt="github"))
    primary = g.apply(lambda lst: lst[0] if lst else None).value_counts().head(10)
    print("\nVanligste primary genre (første element):")
    print(tabulate(primary.reset_index().values, headers=["Genre", "Filmer"],
                   tablefmt="github"))

    # 7d. Språk og land
    print(f"\n7d. original_language: {m['original_language'].nunique()} ulike")
    print(tabulate(m["original_language"].value_counts().head(10).reset_index().values,
                   headers=["Språk", "Filmer"], tablefmt="github"))
    countries = Counter(x for lst in p["production_countries"]
                        for x in names(lst, "iso_3166_1"))
    print(f"\nproduction_countries: {len(countries)} ulike")
    print(tabulate(countries.most_common(10), headers=["Land", "Filmer"], tablefmt="github"))

    # 7e. Produksjonsselskaper
    comp = Counter(x for lst in p["production_companies"] for x in names(lst))
    print(f"\n7e. production_companies: {len(comp)} ulike")
    print(tabulate(comp.most_common(10), headers=["Selskap", "Filmer"], tablefmt="github"))

    # 7f. Collections
    coll = p["belongs_to_collection"]
    coll_id = coll.apply(lambda d: d.get("id") if isinstance(d, dict) else None)
    coll_name = coll.apply(lambda d: d.get("name") if isinstance(d, dict) else None)
    sizes = coll_id.value_counts()
    print(f"\n7f. Collections: {coll_id.nunique()} ulike id-er, {coll_name.nunique()} ulike navn")
    print(f"Collections med ≥ 3 filmer: {(sizes >= 3).sum()}")
    top = coll_name.value_counts().head(10)
    print(tabulate(top.reset_index().values, headers=["Collection", "Filmer"],
                   tablefmt="github"))

    # 7g. Forsmak på oppgave 9
    us = p["production_countries"].apply(lambda lst: "US" in names(lst, "iso_3166_1"))
    non_en = m["original_language"].notna() & (m["original_language"] != "en")
    print(f"\n7g. Ikke-engelske filmer med US som produksjonsland: {(us & non_en).sum()}")


def step8_credits(dfs):
    print("\n########## STEG 8: CAST OG CREW ##########\n")
    c = dfs["credits"].drop_duplicates()                       # helt like rader fjernet
    cast = c["cast"].apply(parse_literal)
    crew = c["crew"].apply(parse_literal)

    # 8a. Nøkler og størrelse
    print("8a. Nøkler i cast:", dict(Counter(k for l in cast for d in l for k in d)))
    print("    Nøkler i crew:", dict(Counter(k for l in crew for d in l for k in d)))
    sizes = pd.DataFrame({"cast": cast.apply(len), "crew": crew.apply(len)})
    print("\nStørrelse per film:")
    print(tabulate(sizes.describe(percentiles=[.5, .9, .99]).T, headers="keys",
                   tablefmt="github", floatfmt=".1f"))

    # 8b. Kjønn i cast (0 = ukjent, 1 = kvinne, 2 = mann)
    g = Counter(d.get("gender") for l in cast for d in l)
    print("\n8b. Kjønn i cast:", dict(g))
    top5 = Counter(d.get("gender") for l in cast
                   for d in sorted(l, key=lambda d: d["order"])[:5])
    print("    Kjønn blant topp 5 i hver film:", dict(top5))

    # 8c. Er 'order' sammenhengende fra 0?
    starts_at_0 = cast.apply(lambda l: not l or min(d["order"] for d in l) == 0).mean()
    print(f"\n8c. Andel filmer der order starter på 0: {100 * starts_at_0:.1f} %")

    # 8d. Samme skuespiller flere ganger i samme film (flere roller)
    dup_actor = cast.apply(lambda l: len(l) - len({d["id"] for d in l}))
    print(f"8d. Filmer der samme skuespiller står flere ganger: {(dup_actor > 0).sum()}")

    # 8e. Regissører
    dirs = crew.apply(lambda l: [d for d in l if d.get("job") == "Director"])
    n_dir = dirs.apply(len).value_counts().sort_index()
    print("\n8e. Antall regissører per film:")
    print(tabulate(n_dir.reset_index().values, headers=["Regissører", "Filmer"],
                   tablefmt="github"))
    jobs = Counter(d.get("job") for l in crew for d in l)
    print("\nVanligste jobber i crew:")
    print(tabulate(jobs.most_common(8), headers=["Job", "Antall"], tablefmt="github"))

    # 8f. Navn som deles av flere personer (ulike id-er)
    actors = pd.DataFrame([(d["id"], d["name"]) for l in cast for d in l],
                          columns=["id", "name"]).drop_duplicates()
    shared = actors.groupby("name")["id"].nunique()
    print(f"\n8f. Ulike skuespillere (id): {actors['id'].nunique():,}")
    print(f"    Navn som brukes av mer enn én skuespiller: {(shared > 1).sum():,}")
    print(tabulate(shared[shared > 1].sort_values(ascending=False).head(5).reset_index().values,
                   headers=["Navn", "Ulike id-er"], tablefmt="github"))

    c = dfs["credits"].drop_duplicates()              # fjerner de 37 helt like
    dups = c[c["id"].duplicated(keep=False)]           # de 7 ulike, med begge radene

    rows = []
    for mid, g in dups.groupby("id"):
        for _, r in g.iterrows():
            crew = parse_literal(r["crew"])
            directors = sorted(d["name"] for d in crew if d.get("job") == "Director")
            rows.append([mid, len(crew), ", ".join(directors)])
    show_rows = tabulate(rows, headers=["id", "Crew-lengde", "Regissører"], tablefmt="github")
    print(show_rows)

def check_revenue(dfs):
    m = dfs["movies_metadata"]
    m = m[pd.to_numeric(m["id"], errors="coerce").notna()].copy()
    m["id"] = m["id"].astype(int)
    m = m.drop_duplicates("id")

    c = dfs["credits"].drop_duplicates("id").copy()
    c["directors"] = c["crew"].apply(
        lambda s: [d["name"] for d in parse_literal(s) if d.get("job") == "Director"])
    mc = m.merge(c[["id", "directors"]], on="id").explode("directors")

    known = mc[mc["revenue"] > 0]
    n_films = known.groupby("directors")["id"].nunique()
    eligible = set(n_films[n_films >= 5].index)

    small = known[(known["revenue"] < 1000) & known["directors"].isin(eligible)]
    print(f"Regissører med ≥ 5 filmer med kjent revenue: {len(eligible)}")
    print(f"Små revenue-verdier hos disse: {small['id'].nunique()} filmer, "
        f"{small['directors'].nunique()} regissører")


def check_links(dfs):
    movies = dfs["movies_metadata"]
    movies = movies[pd.to_numeric(movies["id"], errors="coerce").notna()].copy()
    movies["id"] = movies["id"].astype(int)
    movies = movies.drop_duplicates("id")
    movies["imdb_num"] = pd.to_numeric(movies["imdb_id"].str.replace("tt", "", regex=False),
                                    errors="coerce")

    links = dfs["links"].dropna(subset=["tmdbId"]).copy()
    links["tmdbId"] = links["tmdbId"].astype(int)
    j = links.merge(movies[["id", "imdb_num"]], left_on="tmdbId", right_on="id", how="left")
    j["status"] = np.select(
        [j["id"].isna(), j["imdb_num"].isna(), j["imdbId"] == j["imdb_num"]],
        ["ikke i metadata", "mangler imdb_id i metadata", "match"], default="avvik")

    # Kan avvikene reddes ved å koble via IMDb-id?
    imdb_to_tmdb = (movies.dropna(subset=["imdb_num"]).drop_duplicates("imdb_num")
                    .set_index("imdb_num")["id"])
    j["tmdb_via_imdb"] = j["imdbId"].map(imdb_to_tmdb)

    # Antall ratinger per MovieLens-film
    rc = dfs["ratings"]["movieId"].value_counts()
    j["ratinger"] = j["movieId"].map(rc).fillna(0).astype(int)

    summary = j.groupby("status").agg(linker=("movieId", "size"), ratinger=("ratinger", "sum"))
    print(tabulate(summary, headers="keys", tablefmt="github"))

    avvik = j[j["status"] == "avvik"]
    redd = avvik["tmdb_via_imdb"].notna()
    print(f"\nAvvik som kan reddes via IMDb: {redd.sum()} linker, "
        f"{avvik.loc[redd, 'ratinger'].sum():,} ratinger")

    dup = j[j["tmdbId"].duplicated(keep=False)]
    print("\nDupliserte tmdbId-er fordelt på status:")
    print(tabulate(dup["status"].value_counts().reset_index().values,
                headers=["Status", "Linker"], tablefmt="github"))


def step8_dup_actors(dfs):
    print("\n########## SAMME SKUESPILLER FLERE GANGER ##########\n")
    m = dfs["movies_metadata"]
    m = m[pd.to_numeric(m["id"], errors="coerce").notna()].copy()
    m["id"] = m["id"].astype(int)
    titles = m.drop_duplicates("id").set_index("id")["title"]

    c = dfs["credits"].drop_duplicates("id").copy()
    c["cast_p"] = c["cast"].apply(parse_literal)

    # Én rad per skuespiller-oppføring som forekommer mer enn én gang i samme film
    rows = []
    for _, r in c.iterrows():
        cast = r["cast_p"]
        counts = Counter(d["id"] for d in cast)
        for d in cast:
            if counts[d["id"]] > 1:
                rows.append({"film_id": r["id"], "actor_id": d["id"], "name": d["name"],
                             "character": d["character"], "order": d["order"],
                             "cast_id": d["cast_id"], "credit_id": d["credit_id"]})
    dup = pd.DataFrame(rows)
    print(f"Filmer: {dup['film_id'].nunique()}, skuespillere: "
          f"{dup.groupby(['film_id', 'actor_id']).ngroups}, oppføringer: {len(dup)}")

    # Ulike karakterer (flere roller) eller samme karakter (duplikat)?
    g = dup.groupby(["film_id", "actor_id"])
    kind = g["character"].nunique().map(lambda n: "ulike karakterer" if n > 1
                                        else "samme karakter")
    print("\nType:")
    print(tabulate(kind.value_counts().reset_index().values,
                   headers=["Type", "Skuespiller-film-par"], tablefmt="github"))
    print("\nAntall oppføringer per skuespiller i samme film:")
    print(tabulate(g.size().value_counts().sort_index().reset_index().values,
                   headers=["Oppføringer", "Par"], tablefmt="github"))

    # Eksempler av hver type
    dup["title"] = dup["film_id"].map(titles)
    dup["type"] = [kind[(f, a)] for f, a in zip(dup["film_id"], dup["actor_id"])]
    cols = ["title", "name", "character", "order", "cast_id", "credit_id"]
    for t in ["ulike karakterer", "samme karakter"]:
        ex = dup[dup["type"] == t]
        first_pairs = ex[["film_id", "actor_id"]].drop_duplicates().head(4)
        ex = ex.merge(first_pairs, on=["film_id", "actor_id"])
        print(f"\nEksempler – {t}:")
        print(tabulate(ex[cols].map(lambda v: short(v, 30)), headers="keys",
                       tablefmt="github", showindex=False))

def step9_pairs(dfs):
    print("\n########## OPPGAVE 2: SKUESPILLERPAR ##########\n")
    c = dfs["credits"].drop_duplicates("id").copy()

    # Én oppføring per skuespiller per film, sortert på laveste order
    def actors_by_order(s):
        best = {}
        for d in parse_literal(s):
            if d["id"] not in best or d["order"] < best[d["id"]]:
                best[d["id"]] = d["order"]
        return [a for a, _ in sorted(best.items(), key=lambda x: x[1])]

    casts = c["cast"].apply(actors_by_order)

    rows = []
    for top_n in [5, 10, 20, None]:                         # None = hele casten
        pairs = Counter()
        for actors in casts:
            sel = actors if top_n is None else actors[:top_n]
            pairs.update(combinations(sorted(sel), 2))
        n3 = sum(1 for v in pairs.values() if v >= 3)
        top = pairs.most_common(1)[0][1] if pairs else 0
        rows.append(["alle" if top_n is None else top_n, f"{sum(pairs.values()):,}",
                     f"{len(pairs):,}", f"{n3:,}", top])
        if top_n is None:
            all_pairs = pairs

    print(tabulate(rows, headers=["Topp N", "Par totalt", "Unike par",
                                  "Par med ≥ 3 filmer", "Flest filmer sammen"],
                   tablefmt="github"))

    # Hvor stor andel av ≥3-parene i hele casten involverer minst én birolle?
    big = sorted(casts.apply(len).nlargest(5).tolist(), reverse=True)
    print(f"\nStørste casts: {big}")

def main():
    dfs = load_all()
    # step1_overview(dfs)
    # step2_keys(dfs)
    # step3_quality(dfs)
    # step4_missing(dfs)
    # step5_numeric(dfs)
    # step6_dates(dfs)
    # step7_nested(dfs)
    # step8_credits(dfs)
    # check_revenue(dfs)
    # check_links(dfs)
    # step8_dup_actors(dfs)
    step9_pairs(dfs)

if __name__ == "__main__":
    main()