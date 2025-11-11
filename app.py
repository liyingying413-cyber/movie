# TMDB Movie Explorer — Streamlit
# Features: API-key gate, search, genres/year filters, poster grid, details drawer, pagination
import os
import requests
import streamlit as st

st.set_page_config(page_title="TMDB Movie Explorer", page_icon="🎬", layout="wide")

# ---------------- TMDB endpoints ----------------
TMDB_API = "https://api.themoviedb.org/3"
IMG_FALLBACK = "https://via.placeholder.com/342x513?text=No+Poster"
DEFAULT_LANG = "en-US"

# ---------------- Sidebar: API Key Gate ----------------
st.sidebar.header("🔐 API Credentials")
hide = st.sidebar.checkbox("Hide API Key", value=True)
default_key = st.secrets.get("TMDB_V3_KEY", os.getenv("TMDB_V3_KEY", "")) if hasattr(st, "secrets") else os.getenv("TMDB_V3_KEY", "")
api_key = st.sidebar.text_input("TMDB v3 API Key", value=default_key, type="password" if hide else "default")

if api_key:
    st.session_state["TMDB_V3_KEY"] = api_key.strip()

def tmdb_get(path, params=None):
    """GET helper — v3 key via query param."""
    key = st.session_state.get("TMDB_V3_KEY", "")
    if not key:
        raise RuntimeError("Missing TMDB API key")
    params = params or {}
    params["api_key"] = key
    r = requests.get(f"{TMDB_API}{path}", params=params, timeout=20)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=86400, show_spinner=False)
def get_config():
    return tmdb_get("/configuration")

@st.cache_data(ttl=86400, show_spinner=False)
def get_genres(lang=DEFAULT_LANG):
    data = tmdb_get("/genre/movie/list", {"language": lang})
    return data.get("genres", [])

@st.cache_data(ttl=600, show_spinner=False)
def search_movies(query, page=1, lang=DEFAULT_LANG, year=None, genre_id=None):
    params = {"query": query, "page": page, "language": lang, "include_adult": False}
    if year:
        params["year"] = year
    data = tmdb_get("/search/movie", params)
    results = data.get("results", [])
    # genre 进一步过滤（search 端点不支持直接传 genre）
    if genre_id:
        results = [m for m in results if genre_id in (m.get("genre_ids") or [])]
    return results, int(data.get("total_results", 0)), int(data.get("total_pages", 1))

@st.cache_data(ttl=600, show_spinner=False)
def popular_movies(page=1, lang=DEFAULT_LANG):
    data = tmdb_get("/movie/popular", {"page": page, "language": lang})
    return data.get("results", []), int(data.get("total_results", 0)), int(data.get("total_pages", 1))

@st.cache_data(ttl=600, show_spinner=False)
def get_movie_details(movie_id, lang=DEFAULT_LANG):
    # append_to_response 一次拿到视频/图片
    return tmdb_get(f"/movie/{movie_id}", {"language": lang, "append_to_response": "videos,images"})

def img_url(poster_path, size="w342"):
    try:
        conf = get_config()
        base = (conf["images"]["secure_base_url"])
        return f"{base}{size}{poster_path}"
    except Exception:
        return IMG_FALLBACK

# ---------------- UI: Query controls ----------------
st.title("🎬 TMDB Movie Explorer")
st.caption("Enter your **TMDB v3 API Key** in the sidebar to start. Get one at https://www.themoviedb.org/ (free).")

if not st.session_state.get("TMDB_V3_KEY"):
    st.info("👉 Please enter your **TMDB v3 API Key** in the left sidebar.")
    st.stop()

# Key quick validation
try:
    _ = get_config()
except requests.HTTPError as e:
    st.error(f"TMDB error: {e.response.status_code} — {e.response.text}")
    st.stop()
except Exception as e:
    st.error(f"Failed to validate API key: {e}")
    st.stop()

st.sidebar.header("🔍 Query Settings")
q = st.sidebar.text_input("Keyword (empty → show popular)")
lang = st.sidebar.selectbox(
    "Language", ["en-US", "ko-KR", "zh-CN", "ja-JP", "fr-FR", "de-DE", "es-ES"], index=0
)
year = st.sidebar.number_input("Year (optional)", min_value=1870, max_value=2100, value=0, step=1)
genres = get_genres(lang)
genre_names = ["(Any)"] + [g["name"] for g in genres]
genre_choice = st.sidebar.selectbox("Genre", genre_names, index=0)
genre_id = None if genre_choice == "(Any)" else next(g["id"] for g in genres if g["name"] == genre_choice)

per_row = st.sidebar.select_slider("Grid columns", options=[3, 4, 5, 6], value=5)
page = st.sidebar.number_input("Page", min_value=1, value=1, step=1)
go = st.sidebar.button("Start", use_container_width=True)

# ---------------- Fetch data ----------------
if go:
    with st.spinner("Fetching movies..."):
        if q.strip():
            results, total, total_pages = search_movies(q.strip(), page=page, lang=lang, year=(year or None), genre_id=genre_id)
        else:
            # popular 忽略 year 与 genre（TMDB 不支持该端点筛选）
            results, total, total_pages = popular_movies(page=page, lang=lang)
else:
    st.warning("Click **Start** in the sidebar to run your query.")
    st.stop()

st.write(f"**{total:,}** result(s) • Page **{page} / {total_pages}**")

# ---------------- Poster grid ----------------
if not results:
    st.info("No results. Try another keyword/filters.")
    st.stop()

def movie_card(m):
    poster = m.get("poster_path")
    title = m.get("title") or m.get("name") or "Untitled"
    rel = m.get("release_date") or ""
    rate = m.get("vote_average", 0)
    mid = m.get("id")

    with st.container(border=True):
        cols = st.columns([1, 2])
        with cols[0]:
            st.image(img_url(poster) if poster else IMG_FALLBACK, use_container_width=True)
        with cols[1]:
            st.subheader(title)
            meta = " · ".join([x for x in [rel, f"⭐ {rate:.1f}"] if x])
            if meta:
                st.caption(meta)
            st.write((m.get("overview") or "")[:220] + ("..." if (m.get("overview") and len(m.get("overview")) > 220) else ""))
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔎 Details", key=f"detail_{mid}"):
                    st.session_state["detail_id"] = mid
                    st.rerun()
            with c2:
                st.link_button("↗ TMDB", f"https://www.themoviedb.org/movie/{mid}")

# Grid
rows = [results[i:i+per_row] for i in range(0, len(results), per_row)]
for row in rows:
    cols = st.columns(per_row)
    for c, item in zip(cols, row):
        with c:
            movie_card(item)

# ---------------- Details drawer ----------------
if "detail_id" in st.session_state:
    mid = st.session_state["detail_id"]
    with st.expander("Movie details", expanded=True):
        try:
            d = get_movie_details(mid, lang=lang)
        except Exception as e:
            st.error(f"Failed to load details: {e}")
            d = None

        if d:
            p = d.get("poster_path")
            cols = st.columns([1, 2])
            with cols[0]:
                st.image(img_url(p) if p else IMG_FALLBACK, use_container_width=True)
            with cols[1]:
                st.markdown(f"### {d.get('title') or 'Untitled'}")
                meta = []
                if d.get("release_date"): meta.append(d["release_date"])
                if d.get("runtime"): meta.append(f"{d['runtime']} min")
                if d.get("vote_average") is not None: meta.append(f"⭐ {d['vote_average']:.1f}")
                if d.get("genres"): meta.append(", ".join([g["name"] for g in d["genres"]]))
                if meta: st.caption(" · ".join(meta))
                if d.get("overview"): st.write(d["overview"])
                vids = (d.get("videos", {}) or {}).get("results", [])
                yt = next((v for v in vids if v.get("site")=="YouTube" and v.get("type") in ("Trailer","Teaser")), None)
                if yt:
                    st.link_button("▶ Watch trailer on YouTube", f"https://www.youtube.com/watch?v={yt['key']}")
                st.link_button("↗ Open on TMDB", f"https://www.themoviedb.org/movie/{mid}")

        if st.button("Close"):
            del st.session_state["detail_id"]
            st.rerun()
