# app.py — TMDB Movie Explorer (3x4 grid, equal-height cards, neat button row)

import os
import math
import requests
import streamlit as st
from functools import lru_cache

# ----------------------------
# Page / Session
# ----------------------------
st.set_page_config(
    page_title="TMDB Movie Explorer",
    page_icon="🎬",
    layout="wide",
)

if "favorites" not in st.session_state:
    st.session_state["favorites"] = set()

# ----------------------------
# Global
# ----------------------------
TMDB_API_BASE = "https://api.themoviedb.org/3"
DEFAULT_LANG = "en-US"

# ----------------------------
# CSS: reset container (fix ghost cards) + card styles
# ----------------------------
st.markdown(
    """
<style>
/* ----------- RESET STREAMLIT LAYOUT CONTAINERS ----------- */
div[data-testid="stVerticalBlock"] > div,
div[data-testid="stHorizontalBlock"] > div,
div[data-testid="stColumn"] > div {
  background: transparent !important;
  box-shadow: none !important;
  border: none !important;
  padding: 0 !important;
  border-radius: 0 !important;
  min-height: auto !important;
}

/* ----------- CARD STYLES (equal height; poster/overview/buttons distributed) ----------- */
.movie-card {
  background: #ffffff;
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 14px;
  box-shadow: 0 2px 20px rgba(0,0,0,0.04);
  padding: 14px;
  height: 520px;                     /* 统一卡片高度 */
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 顶部：海报 + 文字 */
.movie-card .topcols {
  display: grid;
  grid-template-columns: 110px 1fr;  /* 左海报固定宽，右侧自适应 */
  gap: 12px;
  align-items: start;
}

.movie-card .poster-img {
  width: 100%;
  height: 165px;                     /* 固定海报高度 */
  border-radius: 10px;
  object-fit: cover;
  background: #f4f4f4;
  border: 1px solid rgba(0,0,0,0.06);
}

.movie-card .title {
  font-weight: 700;
  font-size: 18px;
  margin-bottom: 4px;
}

.movie-card .meta {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}

/* 中部简介：固定高度，溢出省略 */
.movie-card .overview-wrap {
  flex: 1 1 auto;                    /* 填充中间空间 */
  min-height: 110px;
  max-height: 110px;                 /* 保证等高 */
  overflow: hidden;
  position: relative;
}

.movie-card .overview {
  font-size: 13px;
  line-height: 1.5;
  color: #333;
  display: -webkit-box;
  -webkit-line-clamp: 6;             /* 约 6 行 */
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 底部按钮栏：横向等宽、居中 */
.movie-card .btnbar {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr; /* 三等分 */
  gap: 10px;
  margin-top: 10px;
}

.movie-card .btnbar .stButton>button,
.movie-card .btnbar .stLinkButton>a {
  width: 100%;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: 10px;
}

/* Favorite 实心/空心效果由文案控制：★/☆ */

/* 右上角收藏小星标（可选） */
/*
.movie-card .favpin {
  position: absolute;
  top: 10px; right: 10px;
  font-size: 18px;
  color: #f3b400;
}
*/
</style>
""",
    unsafe_allow_html=True,
)

# ----------------------------
# Utilities
# ----------------------------
def _get_api_key():
    # 优先取 sidebar 文本，其次环境变量
    key = st.session_state.get("tmdb_key") or os.environ.get("TMDB_V3_KEY", "")
    return (key or "").strip()

def tmdb_get(path: str, params: dict = None):
    """GET wrapper with API key"""
    key = _get_api_key()
    if not key:
        st.warning("Please enter your **TMDB v3 API Key** in the sidebar.")
        return {}
    params = dict(params or {})
    params["api_key"] = key
    try:
        r = requests.get(f"{TMDB_API_BASE}{path}", params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"TMDB request failed: {e}")
        return {}

@st.cache_data(show_spinner=False, ttl=3600)
def get_genres(lang: str = DEFAULT_LANG):
    js = tmdb_get("/genre/movie/list", {"language": lang})
    return js.get("genres", []) if js else []

@st.cache_data(show_spinner=False, ttl=3600)
def get_languages():
    js = tmdb_get("/configuration/languages")
    if not js:
        return []
    # 返回[{"iso_639_1":"en","english_name":"English"}...]
    return js

def pick_image(m: dict, size: str = "w342") -> str:
    pf = m.get("poster_path") or ""
    if not pf:
        return ""
    return f"https://image.tmdb.org/t/p/{size}{pf}"

def tmdb_url(m: dict) -> str:
    mid = m.get("id")
    return f"https://www.themoviedb.org/movie/{mid}" if mid else "#"

def clamp(text: str, n=600) -> str:
    if not text:
        return ""
    text = text.strip()
    return text[:n] + ("..." if len(text) > n else "")

def fav_key(mid: int) -> str:
    return f"fav_{mid}"

def favorite_label(mid: int) -> str:
    return ("★ Unfavorite" if mid in st.session_state["favorites"] else "☆ Favorite")

# ----------------------------
# Discover Search
# ----------------------------
def discover_movies(
    page: int,
    per_page: int,
    *,
    language: str,
    query: str,
    with_genres: list[int],
    year: int | None,
    region: str | None,
    include_adult: bool,
    vote_gte: float,
    vote_lte: float,
    runtime_min: int,
    runtime_max: int,
    orig_lang: str | None,
    sort_by: str,
):
    # TMDB 每页最多 20，这里取 20 再前端裁 12
    params = {
        "language": language,
        "sort_by": sort_by,
        "include_adult": str(include_adult).lower(),
        "include_video": "false",
        "page": page,
        "vote_average.gte": vote_gte,
        "vote_average.lte": vote_lte,
        "with_runtime.gte": runtime_min,
        "with_runtime.lte": runtime_max,
    }
    if region and region != "(Any)":
        params["region"] = region
        params["watch_region"] = region
    if orig_lang and orig_lang != "(Any)":
        params["with_original_language"] = orig_lang
    if with_genres:
        params["with_genres"] = ",".join(map(str, with_genres))
    if year:
        params["primary_release_year"] = year

    # 有关键词就用 /search/movie；否则 /discover/movie
    if query:
        params_search = {
            "language": language,
            "query": query,
            "include_adult": str(include_adult).lower(),
            "page": page,
        }
        js = tmdb_get("/search/movie", params_search)
    else:
        js = tmdb_get("/discover/movie", params)

    results = (js or {}).get("results", [])
    total_results = (js or {}).get("total_results", 0)
    total_pages = (js or {}).get("total_pages", 1)

    # 统一只给 12 个
    return results[:per_page], total_results, total_pages

# ----------------------------
# Render one card
# ----------------------------
def movie_card_horizontal(m: dict, poster_size: str = "w342"):
    """
    在“卡片盒”内用 Streamlit 组件渲染：
    - 顶部：海报 + 标题 + meta
    - 中部：简介（固定高，省略号）
    - 底部：按钮栏（3等分、横向居中）
    """
    mid = int(m.get("id"))
    title = m.get("title") or m.get("name") or "Untitled"
    date = (m.get("release_date") or "")[:10]
    vote = m.get("vote_average") or 0
    overview = clamp(m.get("overview") or "", 600)
    poster = pick_image(m, poster_size)
    details_key = f"details_{mid}"

    # 卡片壳（控制整体等高）
    st.markdown('<div class="movie-card">', unsafe_allow_html=True)

    # 顶部两列
    c1, c2 = st.columns([110, 1], gap="small")
    with c1:
        if poster:
            st.image(poster, use_container_width=True, output_format="JPEG")
        else:
            st.image(
                "https://placehold.co/300x450?text=No+Image",
                use_container_width=True,
            )
    with c2:
        st.markdown(f'<div class="title">{title}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="meta">{date or "—"} &nbsp;·&nbsp; ⭐ {vote:.1f}</div>',
            unsafe_allow_html=True,
        )

    # 简介区域（固定高，溢出省略）
    st.markdown('<div class="overview-wrap">', unsafe_allow_html=True)
    st.markdown(f'<div class="overview">{overview}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # 按钮栏（3 等分）
    st.markdown('<div class="btnbar">', unsafe_allow_html=True)
    bcol1, bcol2, bcol3 = st.columns(3)

    with bcol1:
        fav_label = favorite_label(mid)
        if st.button(fav_label, key=fav_key(mid)):

            # toggle favorite
            if mid in st.session_state["favorites"]:
                st.session_state["favorites"].remove(mid)
            else:
                st.session_state["favorites"].add(mid)
            st.experimental_rerun()

    with bcol2:
        # 详情弹层
        if st.button("🔎 Details", key=f"btn_det_{mid}"):
            with st.expander(f"Details — {title}", expanded=True):
                st.write(
                    {
                        "id": mid,
                        "title": title,
                        "original_title": m.get("original_title"),
                        "original_language": m.get("original_language"),
                        "overview": m.get("overview"),
                        "release_date": m.get("release_date"),
                        "vote_average": m.get("vote_average"),
                        "vote_count": m.get("vote_count"),
                        "popularity": m.get("popularity"),
                    }
                )

    with bcol3:
        st.link_button("↗ TMDB", tmdb_url(m))

    st.markdown("</div>", unsafe_allow_html=True)  # end btnbar
    st.markdown("</div>", unsafe_allow_html=True)  # end movie-card


# ----------------------------
# Sidebar — API & Filters
# ----------------------------
st.sidebar.header("🔐 API Credentials")
hide = st.sidebar.checkbox("Hide API Key", value=True)
tmdb_key_input = st.sidebar.text_input(
    "TMDB v3 API Key",
    value=st.session_state.get("tmdb_key", ""),
    type=("password" if hide else "default"),
)
st.session_state["tmdb_key"] = tmdb_key_input

st.sidebar.header("🔎 Query Settings")
query = st.sidebar.text_input("Keyword (empty → Discover mode)", value="")
lang_ui = st.sidebar.selectbox(
    "UI Language",
    options=["en-US", "ko-KR", "zh-CN", "ja-JP", "fr-FR", "de-DE", "es-ES"],
    index=0,
)

# 动态类型列表
genres_map = {g["name"]: g["id"] for g in get_genres(lang_ui) or []}
sel_genres = st.sidebar.multiselect(
    "Genres",
    options=list(genres_map.keys()),
    default=[],
)
with_genres = [genres_map[n] for n in sel_genres] if sel_genres else []

# 其他 discover 过滤
year_filter = st.sidebar.checkbox("Filter by year", value=False)
year = st.sidebar.number_input("Year", min_value=1870, max_value=2100, value=2024, step=1) if year_filter else None

region = st.sidebar.selectbox(
    "Region (watch availability, certification, etc.)",
    options=["(Any)", "US", "GB", "KR", "JP", "FR", "DE", "ES", "CN", "TW", "HK"],
    index=1,
)

include_adult = st.sidebar.checkbox("Include adult", value=False)

vote_gte, vote_lte = st.sidebar.slider("Vote average range", 0.0, 10.0, (0.0, 10.0), 0.1)
runtime_min, runtime_max = st.sidebar.slider("Runtime (min)", 0, 240, (0, 240), 5)

orig_lang_options = ["(Any)"] + [x.get("iso_639_1") for x in (get_languages() or []) if x.get("iso_639_1")]
orig_lang = st.sidebar.selectbox("Original language", options=orig_lang_options, index=orig_lang_options.index("(Any)"))

sort_by = st.sidebar.selectbox(
    "Sort by (discover)",
    options=[
        "popularity.desc",
        "popularity.asc",
        "primary_release_date.desc",
        "primary_release_date.asc",
        "vote_average.desc",
        "vote_average.asc",
    ],
    index=0,
)

# 卡片网格/分页
st.sidebar.subheader("Layout")
poster_w = st.sidebar.slider("Poster size", 185, 500, 342, 1)   # 映射为 w185~w500
per_page = 12   # 3x4 固定
page = st.sidebar.number_input("Page", min_value=1, value=1, step=1)
if st.sidebar.button("Start / Refresh", use_container_width=True):
    st.experimental_rerun()

# ----------------------------
# Header
# ----------------------------
st.markdown("### 🎬 TMDB Movie Explorer")
st.caption("Get a free **v3 API key** at https://www.themoviedb.org/ (free). This app supports search and powerful discover filters.")

# ----------------------------
# Perform search / discover
# ----------------------------
items, total_results, total_pages = discover_movies(
    page=page,
    per_page=per_page,
    language=lang_ui,
    query=query,
    with_genres=with_genres,
    year=year,
    region=region,
    include_adult=include_adult,
    vote_gte=vote_gte,
    vote_lte=vote_lte,
    runtime_min=runtime_min,
    runtime_max=runtime_max,
    orig_lang=orig_lang,
    sort_by=sort_by,
)

# Summary bar
st.markdown(
    f"**{total_results:,}** result(s) • Page **{page} / {max(1,total_pages):,}** • Showing **{per_page}** per page (3x4)"
)

# Search bar (仅展示，不改变逻辑)
_ = st.text_input("", value=query, placeholder="Search again here...", label_visibility="collapsed", disabled=True)

# ----------------------------
# Grid render (3 columns x 4 rows)
# ----------------------------
cols = st.columns(3, gap="large")
poster_size_token = f"w{poster_w}"

for i, m in enumerate(items[:per_page]):
    with cols[i % 3]:
        movie_card_horizontal(m, poster_size=poster_size_token)

# ----------------------------
# Pager controls
# ----------------------------
pc1, pc2, pc3 = st.columns(3)
with pc1:
    if st.button("⏮ First", disabled=(page <= 1)):
        st.experimental_set_query_params(page=1)
        st.session_state["__page__"] = 1
        st.experimental_rerun()
with pc2:
    if st.button("◀ Prev", disabled=(page <= 1)):
        st.experimental_set_query_params(page=page-1)
        st.session_state["__page__"] = page-1
        st.experimental_rerun()
with pc3:
    if st.button("Next ▶", disabled=(page >= total_pages)):
        st.experimental_set_query_params(page=page+1)
        st.session_state["__page__"] = page+1
        st.experimental_rerun()
