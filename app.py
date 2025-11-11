# app.py
import os
import math
import requests
import streamlit as st

# -------------------- Page & Basic --------------------
st.set_page_config(page_title="TMDB Movie Explorer", page_icon="🎬", layout="wide")

# ---------- Style Injection ----------
st.markdown("""
<style>
/* 背景 */
.main { background-color: #fafafa; }

/* 卡片容器美化 */
div[data-testid="stVerticalBlock"] > div.stContainer {
  border-radius: 16px !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.07);
  background: #fff !important;
  transition: transform .15s ease, box-shadow .15s ease;
  display: block; /* 外层容器 */
}
div[data-testid="stVerticalBlock"] > div.stContainer:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 14px rgba(0,0,0,0.12);
}

/* 内层真正的卡片框架：等高关键 */
.card-fixed{
  display:flex;
  flex-direction:column;
  min-height: 420px;  /* 卡片最小高度，可按喜好微调 */
}

/* 顶部内容块占据剩余高度（按钮压底部） */
.card-top{ flex: 1 1 auto; }

/* 概要 7 行省略 */
.overview-7{
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 7;
  overflow: hidden;
  line-height: 1.2;
  min-height: calc(1.2em * 7);
}

/* 标题 2 行省略，大小与 subheader 接近 */
.title-2{
  font-size: 1.15rem;
  font-weight: 700;
  margin: 0 0 .25rem 0;
  color:#222;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

/* meta（日期/评分） */
.meta{ color:#666; font-size:.9rem; margin-bottom:.35rem; }

/* 海报固定高度，裁切 */
.poster-img{
  width:100%;
  height:220px;
  object-fit:cover;
  border-radius:12px;
  display:block;
}

/* 按钮横排：等宽、居中、贴底 */
.btnbar-wrap{ margin-top:auto; padding-top:.35rem; }
.btnbar{ display:flex; justify-content:center; gap:.5rem; }
.btnbar .stButton>button{
  width:8rem;
  font-size:.85rem !important;
  border-radius:10px !important;
  background:#f1f1f1 !important;
  color:#333 !important;
  border:none !important;
  padding:.38rem .6rem !important;
  transition:background-color .15s ease, transform .1s ease;
}
.btnbar .stButton>button:hover{ background:#dcecff !important; transform:translateY(-1px); }
.btnbar .stButton>button:active{ background:#c0deff !important; }

/* 次级按钮（分页） */
button[kind="secondary"]{
  border-radius:10px !important;
  border:1px solid #ddd !important;
  background:#f9f9f9 !important;
}
button[kind="secondary"]:hover{ background:#eef7ff !important; }
</style>
""", unsafe_allow_html=True)

# -------------------- Constants --------------------
DEFAULT_LANG = "en-US"
IMG_FALLBACK = "https://via.placeholder.com/342x513?text=No+Image"
TMDB_IMG_BASE = "https://image.tmdb.org/t/p/"   # https://developer.themoviedb.org/reference/configuration-details

UI_COLS = 3
UI_ROWS = 4
UI_PAGE_SIZE = UI_COLS * UI_ROWS      # 12
TMDB_PAGE_SIZE = 20                   # 固定每页 20

# -------------------- Helpers --------------------
def img_url(p, size="w342"):
    if not p: return IMG_FALLBACK
    return f"{TMDB_IMG_BASE}{size}{p}"

def _get_api_key():
    # 优先 secrets（如果你在 Cloud 的 secrets 中配置了 TMDB_KEY）
    return st.secrets.get("TMDB_KEY") or st.session_state.get("TMDB_KEY", "")

def _headers():
    return {"Accept": "application/json"}

def _base_params(lang=None, region=None):
    key = _get_api_key()
    p = {"api_key": key}
    if lang: p["language"] = lang
    if region: p["region"] = region
    return p

# -------------------- TMDB API --------------------
@st.cache_data(ttl=3600, show_spinner=False)
def get_genres(api_key: str, lang=None):
    lang = lang or DEFAULT_LANG
    url = "https://api.themoviedb.org/3/genre/movie/list"
    r = requests.get(url, headers=_headers(), params={"api_key": api_key, "language": lang}, timeout=20)
    r.raise_for_status()
    return r.json().get("genres", [])

@st.cache_data(ttl=24*3600, show_spinner=False)
def get_movie_details(api_key: str, movie_id: int, lang=None):
    lang = lang or DEFAULT_LANG
    url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    params = {
        "api_key": api_key,
        "language": lang,
        "append_to_response": "videos,credits,release_dates"
    }
    r = requests.get(url, headers=_headers(), params=params, timeout=20)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=6*3600, show_spinner=False)
def get_watch_providers(api_key: str, movie_id: int):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers"
    r = requests.get(url, headers=_headers(), params={"api_key": api_key}, timeout=20)
    r.raise_for_status()
    return r.json().get("results", {})

@st.cache_data(ttl=1800, show_spinner=False)
def search_movies(api_key: str, query: str, page=1, lang=None):
    lang = lang or DEFAULT_LANG
    url = "https://api.themoviedb.org/3/search/movie"
    params = {
        "api_key": api_key, "language": lang, "query": query,
        "page": page, "include_adult": False
    }
    r = requests.get(url, headers=_headers(), params=params, timeout=20)
    r.raise_for_status()
    j = r.json()
    return j.get("results", []), int(j.get("total_results", 0)), int(j.get("total_pages", 1))

@st.cache_data(ttl=900, show_spinner=False)
def discover_movies(
    api_key: str, page=1, lang=None, *,
    with_genres=None, year=None, region=None, sort_by="popularity.desc",
    include_adult=False, vote_gte=0.0, vote_lte=10.0, runtime_gte=0, runtime_lte=400, original_lang=None
):
    lang = lang or DEFAULT_LANG
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": api_key,
        "language": lang,
        "page": page,
        "include_adult": bool(include_adult),
        "vote_average.gte": vote_gte,
        "vote_average.lte": vote_lte,
        "with_runtime.gte": runtime_gte,
        "with_runtime.lte": runtime_lte,
        "sort_by": sort_by
    }
    if with_genres: params["with_genres"] = ",".join(map(str, with_genres))
    if year: params["primary_release_year"] = year
    if region: params["region"] = region
    if original_lang: params["with_original_language"] = original_lang

    r = requests.get(url, headers=_headers(), params=params, timeout=20)
    r.raise_for_status()
    j = r.json()
    return j.get("results", []), int(j.get("total_results", 0)), int(j.get("total_pages", 1))

# ---------- Pagination window (UI 12/页 -> TMDB 20/页) ----------
def fetch_window_by_ui_page(api_key: str, ui_page: int, *, lang, keyword, discover_kwargs):
    start_global = (ui_page - 1) * UI_PAGE_SIZE
    api_page = start_global // TMDB_PAGE_SIZE + 1
    offset = start_global % TMDB_PAGE_SIZE

    if keyword:
        page1, total, _ = search_movies(api_key, keyword, page=api_page, lang=lang)
    else:
        page1, total, _ = discover_movies(api_key, page=api_page, lang=lang, **discover_kwargs)

    need = UI_PAGE_SIZE
    buf = page1[offset: offset + need]
    need -= len(buf)

    if need > 0:
        if keyword:
            page2, _, _ = search_movies(api_key, keyword, page=api_page + 1, lang=lang)
        else:
            page2, _, _ = discover_movies(api_key, page=api_page + 1, lang=lang, **discover_kwargs)
        take2 = min(need, len(page2))
        buf += page2[:take2]

    total_ui_pages = max(1, math.ceil(total / UI_PAGE_SIZE))
    return buf, total, total_ui_pages

# -------------------- UI: Sidebar --------------------
st.sidebar.header("🔐 API Credentials")
hide = st.sidebar.checkbox("Hide API Key", value=True)
api_key_input = st.sidebar.text_input("TMDB v3 API Key", value=os.getenv("TMDB_KEY", ""), type="password" if hide else "default")
if api_key_input:
    st.session_state["TMDB_KEY"] = api_key_input

api_key = _get_api_key()

st.sidebar.header("🔎 Query Settings")

lang = st.sidebar.selectbox(
    "UI Language",
    ["en-US","ko-KR","zh-CN","ja-JP","fr-FR","de-DE","es-ES","it-IT","ru-RU"],
    index=0
)

q = st.sidebar.text_input("Keyword (empty → Discover mode)", value="")

# genres
genres = []
try:
    if api_key:
        genres = get_genres(api_key, lang=lang)
except Exception:
    genres = []

genre_map = {g["name"]: g["id"] for g in genres}
with_genres_names = st.sidebar.multiselect("Genres (effective when keyword is empty)", list(genre_map.keys()), default=[])
with_genres = [genre_map[n] for n in with_genres_names]

# discover filters
filter_by_year = st.sidebar.checkbox("Filter by year", value=False)
year = st.sidebar.number_input("Year", min_value=1870, max_value=2100, value=2024, step=1, disabled=not filter_by_year)
region = st.sidebar.selectbox("Region (watch availability, cert, etc.)", ["", "US","KR","CN","JP","GB","FR","DE","IT","ES","RU"], index=1)
include_adult = st.sidebar.checkbox("Include adult", value=False)
vote_gte, vote_lte = st.sidebar.slider("Vote average range", 0.0, 10.0, (0.0, 10.0), step=0.1)
rt_gte, rt_lte   = st.sidebar.slider("Runtime (min)", 0, 240, (0, 240), step=5)
orig_lang = st.sidebar.selectbox("Original language", ["","en","ko","zh","ja","fr","de","es","it","ru"], index=0)
sort_by = st.sidebar.selectbox("Sort by (discover)", ["popularity.desc","vote_average.desc","primary_release_date.desc","revenue.desc"], index=0)

layout = st.sidebar.radio("Layout", ["Grid","List"], index=0, horizontal=True)
poster_size = st.sidebar.select_slider("Poster size", options=["w185","w342","w500"], value="w342")

page = st.sidebar.number_input("Page", min_value=1, value=int(st.query_params.get("page",[1])[0]), step=1)
go = st.sidebar.button("Start / Refresh", use_container_width=True)

# init session states
st.session_state.setdefault("favorites", set())

# -------------------- Header --------------------
st.title("🎬 TMDB Movie Explorer")
st.caption("Get a free v3 API key from https://www.themoviedb.org/ · This app supports search and powerful discover filters.")

tab_results, tab_fav = st.tabs(["📀 Explore", "⭐ Favorites"])

if not api_key:
    with tab_results:
        st.warning("Please enter your **TMDB v3 API Key** in the left sidebar.")
    st.stop()

# -------------------- Card Renderer --------------------
def _fav_toggle(mid: int):
    favs = st.session_state["favorites"]
    if mid in favs: favs.remove(mid)
    else: favs.add(mid)

def movie_card_horizontal(m, poster_size="w342"):
    """横排卡片：等高 + 简介/标题省略 + 底部按钮对齐"""
    # ---- 数据兜底 ----
    poster = m.get("poster_path")
    title  = m.get("title") or m.get("name") or "Untitled"
    rel    = m.get("release_date") or ""
    try:
        rate = float(m.get("vote_average", 0) or 0.0)
    except Exception:
        rate = 0.0
    mid    = int(m.get("id", 0) or 0)
    overview = (m.get("overview") or "").strip()
    poster_size = str(poster_size or "w342")

    # 图片 URL（字符串兜底，避免 st.image 类型报错）
    poster_url = img_url(poster.strip(), poster_size) if isinstance(poster, str) and poster.strip() else IMG_FALLBACK

    with st.container(border=True):
        # 用一个真正的等高容器包住整张卡片
        st.markdown('<div class="card-fixed">', unsafe_allow_html=True)

        # ===== 顶部内容（会自动占满高度） =====
        st.markdown('<div class="card-top">', unsafe_allow_html=True)
        top = st.columns([1, 2])
        with top[0]:
            st.markdown(
                f'<img src="{poster_url}" alt="poster" class="poster-img">', unsafe_allow_html=True
            )
        with top[1]:
            # 标题 2 行省略
            st.markdown(f'<div class="title-2">{title}</div>', unsafe_allow_html=True)
            meta = " · ".join([x for x in [rel, f"⭐ {rate:.1f}"] if x])
            if meta:
                st.markdown(f'<div class="meta">{meta}</div>', unsafe_allow_html=True)
            if overview:
                st.markdown(f'<div class="overview-7">{overview}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)  # end card-top

        # ===== 底部按钮：等宽、居中、贴底 =====
        st.markdown('<div class="btnbar-wrap"><div class="btnbar">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)

        # Favorite：去掉表情/图标，用纯文本，避免被拆成两段
        fav_label = "Unfavorite" if mid in st.session_state["favorites"] else "Favorite"
        with c1:
            if st.button(fav_label, key=f"fav_{mid}", use_container_width=True):
                _fav_toggle(mid); st.rerun()

        # Details
        with c2:
            if st.button("Details", key=f"detail_{mid}", use_container_width=True):
                st.session_state["detail_id"] = mid; st.rerun()

        # TMDB 链接
        with c3:
            st.link_button("TMDB", f"https://www.themoviedb.org/movie/{mid}", use_container_width=True)

        st.markdown('</div></div>', unsafe_allow_html=True)  # end btnbar

        st.markdown('</div>', unsafe_allow_html=True)  # end card-fixed


# -------------------- Results --------------------
with tab_results:
    if not go:
        st.info("Set filters and click **Start / Refresh**.")
        st.stop()

    discover_kwargs = dict(
        with_genres=with_genres,
        year=int(year) if filter_by_year else None,
        region=region or None,
        sort_by=sort_by,
        include_adult=include_adult,
        vote_gte=float(vote_gte),
        vote_lte=float(vote_lte),
        runtime_gte=int(rt_gte),
        runtime_lte=int(rt_lte),
        original_lang=(orig_lang or None),
    )

    try:
        window, total, total_ui_pages = fetch_window_by_ui_page(
            api_key, page, lang=lang, keyword=q.strip() or None, discover_kwargs=discover_kwargs
        )
    except requests.HTTPError as e:
        st.error(f"TMDB error: {e}")
        st.stop()
    except Exception as e:
        st.error(f"Failed: {e}")
        st.stop()

    st.write(f"**{total:,}** result(s) • Page **{page} / {total_ui_pages}** • Showing **{len(window)}** per page (3×4)")

    if not window:
        st.info("No results. Try another keyword/filters.")
        st.stop()

    rows = [window[i:i+UI_COLS] for i in range(0, len(window), UI_COLS)]
    for row in rows:
        cols = st.columns(UI_COLS)
        for c, item in zip(cols, row):
            with c:
                movie_card_horizontal(item, poster_size=poster_size)

    st.divider()
    c1,c2,c3,c4 = st.columns(4)
    with c1:
        if st.button("⏮ First", disabled=(page<=1)):
            st.query_params["page"]="1"; st.rerun()
    with c2:
        if st.button("◀ Prev", disabled=(page<=1)):
            st.query_params["page"]=str(page-1); st.rerun()
    with c3:
        if st.button("Next ▶", disabled=(page>=total_ui_pages)):
            st.query_params["page"]=str(min(total_ui_pages, page+1)); st.rerun()
    with c4:
        if st.button("Last ⏭", disabled=(page>=total_ui_pages)):
            st.query_params["page"]=str(total_ui_pages); st.rerun()

# -------------------- Favorites --------------------
with tab_fav:
    fav_ids = list(st.session_state["favorites"])
    st.write(f"⭐ You have **{len(fav_ids)}** favorite(s).")
    if not fav_ids:
        st.info("No favorites yet. Click ☆ in results to add.")
    else:
        for mid in fav_ids:
            try:
                d = get_movie_details(api_key, mid, lang=DEFAULT_LANG)
            except Exception:
                continue
            title = d.get("title") or "Untitled"
            p = d.get("poster_path")
            rate = d.get("vote_average") or 0
            cols = st.columns([1,4,1])
            with cols[0]:
                st.image(img_url(p, size="w185") if p else IMG_FALLBACK, use_container_width=True)
            with cols[1]:
                st.markdown(f"**{title}**  ·  ⭐ {rate:.1f}")
                st.caption((d.get("overview","") or "")[:200] + "…")
                st.link_button("Open on TMDB ↗", f"https://www.themoviedb.org/movie/{mid}")
            with cols[2]:
                if st.button("Remove", key=f"rm_{mid}"):
                    st.session_state["favorites"].remove(mid); st.rerun()

# -------------------- Details Expander --------------------
if "detail_id" in st.session_state:
    mid = st.session_state["detail_id"]
    with st.expander("Movie details", expanded=True):
        try:
            d = get_movie_details(api_key, mid, lang=lang)
        except Exception as e:
            st.error(f"Failed to load details: {e}")
            d = None

        if d:
            p = d.get("poster_path")
            cols = st.columns([1, 2])
            with cols[0]:
                st.image(img_url(p, size="w500") if p else IMG_FALLBACK, use_container_width=True)
            with cols[1]:
                st.markdown(f"### {d.get('title') or 'Untitled'}")
                meta = []
                if d.get("release_date"): meta.append(d["release_date"])
                if d.get("runtime"): meta.append(f"{d['runtime']} min")
                if d.get("vote_average") is not None: meta.append(f"⭐ {d['vote_average']:.1f}")
                if d.get("genres"): meta.append(", ".join([g["name"] for g in d["genres"]]))
                if meta: st.caption(" · ".join(meta))
                if d.get("overview"): st.write(d["overview"])

                cast = ((d.get("credits") or {}).get("cast") or [])[:6]
                if cast:
                    st.markdown("**Top Cast**")
                    cast_line = " · ".join([f"{c.get('name','?')} ({c.get('character','')})" for c in cast])
                    st.write(cast_line)

                if region:
                    rels = (d.get("release_dates") or {}).get("results") or []
                    cert = None
                    for block in rels:
                        if block.get("iso_3166_1")==region:
                            for rel in block.get("release_dates", []):
                                c = rel.get("certification")
                                if c:
                                    cert = c; break
                            if cert: break
                    if cert:
                        st.caption(f"Certification in {region}: **{cert}**")

                vids = (d.get("videos", {}) or {}).get("results", [])
                yt = next((v for v in vids if v.get("site")=="YouTube" and v.get("type") in ("Trailer","Teaser")), None)
                if yt:
                    st.link_button("▶ Watch trailer on YouTube", f"https://www.youtube.com/watch?v={yt['key']}")

                provs = get_watch_providers(api_key, mid)
                if region and region in provs:
                    st.markdown("**Where to watch**")
                    p_block = provs[region]
                    names = []
                    for sect in ("flatrate","rent","buy","ads","free"):
                        arr = p_block.get(sect) or []
                        if arr:
                            names.append(f"{sect}: " + ", ".join(sorted({p['provider_name'] for p in arr})))
                    if names:
                        st.write(" · ".join(names))
                st.link_button("↗ Open on TMDB", f"https://www.themoviedb.org/movie/{mid}")

        if st.button("Close"):
            del st.session_state["detail_id"]
            st.rerun()
