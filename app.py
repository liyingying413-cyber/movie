# app.py  — TMDB Movie Explorer (3x4 grid, equal-height cards, v3 API)
# ---------------------------------------------------------------
import os
import math
import textwrap
from typing import Dict, Any, List, Tuple

import requests
import streamlit as st

# ---------------------------
# Streamlit version compat
# ---------------------------
def safe_rerun():
    """Use st.rerun() on new versions, fallback to experimental_rerun() on older ones."""
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()  # type: ignore[attr-defined]
        except Exception:
            pass

def set_page_query(page: int):
    """Set ?page= in URL compatibly."""
    try:
        st.query_params.update({"page": page})
    except Exception:
        try:
            st.experimental_set_query_params(page=page)  # type: ignore[attr-defined]
        except Exception:
            pass

# ---------------------------
# App config + CSS
# ---------------------------
st.set_page_config(page_title="TMDB Movie Explorer", page_icon="🎬", layout="wide")

# custom CSS: equal-height card, clamped overview, centered button-row
st.markdown("""
<style>
/* 主容器的最大宽度优化 */
.main .block-container {max-width: 1200px;}

/* 卡片外观：等高、垂直分布 */
.movie-card {
  background: var(--background-color, #fff);
  border: 1px solid rgba(0,0,0,0.06);
  border-radius: 14px;
  padding: 16px;
  height: 560px;              /* 控制等高卡片 */
  display: flex;
  flex-direction: column;
  box-shadow: 0 2px 10px rgba(0,0,0,0.03);
}

/* 海报区域：固定高度，让布局稳定 */
.poster-wrap {
  height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 10px;
  background: #f6f7f9;
}
.poster-wrap img {
  height: 100%;
  width: auto;
  object-fit: cover;
}

/* 文案区域占据剩余空间，按钮固定在底部 */
.content-wrap {
  flex: 1 1 auto;
  margin-top: 12px;
  display: flex;
  flex-direction: column;
}

/* 标题/元信息 */
.title-row {
  font-weight: 700;
  font-size: 1.05rem;
  margin-bottom: 4px;
}
.meta-row {
  color: #666;
  font-size: 0.86rem;
}

/* 多行截断的简介 */
.overview {
  margin-top: 8px;
  font-size: 0.94rem;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 6;        /* 这里控制显示行数 */
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 按钮行横向等距、居中 */
.btn-row {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-top: 12px;
}
.btn-row .stButton > button {
  width: 110px;
  border-radius: 10px;
}

/* 顶部提示行 */
.top-hint {
  color:#6b7280; font-size:0.9rem; margin-top:-6px; margin-bottom:8px;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------
# Constants & helpers
# ---------------------------
TMDB_BASE = "https://api.themoviedb.org/3"
IMG_BASE  = "https://image.tmdb.org/t/p"
IMG_FALLBACK = "https://dummyimage.com/342x513/e9eef3/93a1b0.jpg&text=No+Image"

PAGE_SIZE = 12   # 3 x 4

def img_url(path: str | None, size: str = "w342") -> str:
    if not path:
        return IMG_FALLBACK
    return f"{IMG_BASE}/{size}{path}"

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_json(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=3600, show_spinner=False)
def get_genres(api_key: str, lang: str) -> List[Dict[str, Any]]:
    data = fetch_json(f"{TMDB_BASE}/genre/movie/list", {"api_key": api_key, "language": lang})
    return data.get("genres", [])

@st.cache_data(ttl=600, show_spinner=False)
def search_movies(api_key: str, query: str, page: int, lang: str) -> Dict[str, Any]:
    return fetch_json(
        f"{TMDB_BASE}/search/movie",
        {"api_key": api_key, "query": query, "page": page, "language": lang, "include_adult": False},
    )

@st.cache_data(ttl=600, show_spinner=False)
def discover_movies(
    api_key: str,
    page: int,
    lang: str,
    region: str | None = None,
    year: int | None = None,
    genres: List[int] | None = None,
    include_adult: bool = False,
    vote_gte: float = 0.0,
    vote_lte: float = 10.0,
    runtime_min: int = 0,
    runtime_max: int = 240,
    original_lang: str | None = None,
    sort_by: str = "popularity.desc",
) -> Dict[str, Any]:
    params = {
        "api_key": api_key,
        "page": page,
        "language": lang,
        "include_adult": include_adult,
        "vote_average.gte": vote_gte,
        "vote_average.lte": vote_lte,
        "with_runtime.gte": runtime_min,
        "with_runtime.lte": runtime_max,
        "sort_by": sort_by,
    }
    if region and region != "(Any)":
        params["region"] = region
        params["watch_region"] = region
    if year:
        params["primary_release_year"] = year
    if genres:
        params["with_genres"] = ",".join(str(g) for g in genres)
    if original_lang and original_lang != "(Any)":
        params["with_original_language"] = original_lang

    return fetch_json(f"{TMDB_BASE}/discover/movie", params)

def shorten(text: str, width: int = 220) -> str:
    if not text:
        return ""
    return textwrap.shorten(text, width=width, placeholder="…")

# ---------------------------
# Session state
# ---------------------------
if "favs" not in st.session_state:
    st.session_state["favs"] = set()
if "__page__" not in st.session_state:
    # 从 URL 取初始页
    try:
        page_q = (st.query_params.get("page") if hasattr(st, "query_params") else None)  # type: ignore[attr-defined]
    except Exception:
        page_q = None
    try:
        if page_q:
            st.session_state["__page__"] = int(page_q)
        else:
            st.session_state["__page__"] = 1
    except Exception:
        st.session_state["__page__"] = 1

# ---------------------------
# Sidebar - API & filters
# ---------------------------
st.sidebar.header("🔐 API Credentials")
hide_key = st.sidebar.checkbox("Hide API Key", value=True)
api_key = st.sidebar.text_input("TMDB v3 API Key", type="password" if hide_key else "default", value=os.getenv("TMDB_V3_API_KEY",""))

st.sidebar.header("🔎 Query Settings")
keyword = st.sidebar.text_input("Keyword (empty → Discover mode)", value="")

# 语言
lang = st.sidebar.selectbox(
    "UI Language",
    options=[
        "en-US","ko-KR","zh-CN","ja-JP","fr-FR","de-DE","es-ES","it-IT","ru-RU","pt-BR"
    ],
    index=0
)

# 年份（可选）
use_year = st.sidebar.checkbox("Filter by year", value=False)
year = st.sidebar.number_input("Year", min_value=1870, max_value=2100, value=2024, step=1) if use_year else None

# 地区 / 观看可用区 / 认证
region = st.sidebar.selectbox(
    "Region (watch availability, cert, etc.)",
    options=["(Any)","US","KR","CN","JP","FR","DE","ES","IT","RU","BR","GB","CA","AU"],
    index=1
)

include_adult = st.sidebar.checkbox("Include adult", value=False)

# 评分范围
vote_gte, vote_lte = st.sidebar.slider("Vote average range", 0.0, 10.0, (0.0, 10.0))

# 时长
runtime_min, runtime_max = st.sidebar.slider("Runtime (min)", 0, 240, (0, 240))

# 原始语言
original_lang = st.sidebar.selectbox("Original language", options=["(Any)","en","ko","zh","ja","fr","de","es","it","ru","pt"], index=0)

# 排序
sort_by = st.sidebar.selectbox("Sort by (discover)", options=[
    "popularity.desc","popularity.asc",
    "primary_release_date.desc","primary_release_date.asc",
    "vote_average.desc","vote_average.asc"
], index=0)

# Genres
genres_map = {}
if api_key:
    try:
        for g in get_genres(api_key, lang):
            genres_map[g["name"]] = g["id"]
    except Exception:
        pass

sel_genre_names = st.sidebar.multiselect("Genres", options=list(genres_map.keys()))
sel_genres = [genres_map[n] for n in sel_genre_names] if sel_genre_names else None

# 布局：Grid 固定 3×4
st.sidebar.subheader("Layout")
st.sidebar.radio("Layout", options=["Grid","List"], index=0, key="__layout__", horizontal=True, help="Grid is 3×4 fixed.")
poster_w = st.sidebar.slider("Poster size", min_value=185, max_value=500, value=342, step=1)
st.sidebar.write("")  # spacer

# 页码
page = st.sidebar.number_input("Page", min_value=1, value=int(st.session_state["__page__"]), step=1)
colp1, colp2, colp3 = st.sidebar.columns([1,1,1])
with colp1:
    if st.button("⏮ First", use_container_width=True):
        st.session_state["__page__"] = 1
        set_page_query(1)
        safe_rerun()
with colp2:
    if st.button("◀ Prev", use_container_width=True, disabled=(page<=1)):
        st.session_state["__page__"] = max(1, page-1)
        set_page_query(int(st.session_state["__page__"]))
        safe_rerun()
with colp3:
    if st.button("Next ▶", use_container_width=True):
        st.session_state["__page__"] = int(page)+1
        set_page_query(int(st.session_state["__page__"]))
        safe_rerun()

if st.sidebar.button("Start / Refresh", use_container_width=True):
    st.session_state["__page__"] = int(page)
    set_page_query(int(page))
    safe_rerun()

# ---------------------------
# Header + top search
# ---------------------------
st.title("🎬 TMDB Movie Explorer")
st.markdown('<div class="top-hint">Get a free v3 API key from <a href="https://www.themoviedb.org/" target="_blank">themoviedb.org</a>. This app supports search and powerful discover filters.</div>', unsafe_allow_html=True)

# 置顶搜索框
q_col1, q_col2 = st.columns([6,1])
with q_col1:
    top_q = st.text_input("Search (press Enter to run)", value=keyword, label_visibility="collapsed")
with q_col2:
    run_btn = st.button("Search", use_container_width=True)
if run_btn and (top_q or keyword):
    keyword = top_q or keyword

if not api_key:
    st.info("Please paste your **TMDB v3 API Key** in the sidebar to start.")
    st.stop()

# ---------------------------
# Fetch movies
# ---------------------------
page = int(page)
st.session_state["__page__"] = page
set_page_query(page)

try:
    if keyword.strip():
        data = search_movies(api_key, keyword.strip(), page, lang)
    else:
        data = discover_movies(
            api_key=api_key, page=page, lang=lang, region=region,
            year=year if use_year else None, genres=sel_genres, include_adult=include_adult,
            vote_gte=vote_gte, vote_lte=vote_lte, runtime_min=runtime_min, runtime_max=runtime_max,
            original_lang=original_lang, sort_by=sort_by
        )
except requests.HTTPError as e:
    st.error(f"TMDB API error: {e}")
    st.stop()
except Exception as e:
    st.error(f"Failed: {e}")
    st.stop()

results = data.get("results", [])
total_results = int(data.get("total_results", 0))
total_pages   = int(data.get("total_pages", 1))
st.caption(f"{total_results:,} result(s) • Page **{page} / {max(1,total_pages):,}** • Showing **{PAGE_SIZE}** per page (3×4)")

# ---------------------------
# Grid render (3 × 4)
# ---------------------------
def render_card(item: Dict[str, Any], col, row_idx: int, col_idx: int):
    mid = item.get("id")
    title = (item.get("title") or item.get("name") or "Untitled").strip()
    date  = (item.get("release_date") or item.get("first_air_date") or "")[:10]
    vote  = item.get("vote_average") or 0.0
    overview = item.get("overview") or ""
    poster = img_url(item.get("poster_path"), f"w{poster_w}")

    # --- 卡片 HTML 头（控制等高 + 结构）---
    col.markdown('<div class="movie-card">', unsafe_allow_html=True)

    # Poster
    col.markdown(f'''
      <div class="poster-wrap">
        <img src="{poster}" alt="poster" />
      </div>
    ''', unsafe_allow_html=True)

    # 文案
    col.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    col.markdown(f'''
      <div class="title-row">{title}</div>
      <div class="meta-row">{date or "----"} · ⭐ {vote:.1f}</div>
    ''', unsafe_allow_html=True)
    col.markdown(f'<div class="overview">{overview}</div>', unsafe_allow_html=True)

    # --- 按钮行（横向居中/等距）---
    col.markdown('<div class="btn-row">', unsafe_allow_html=True)

    fav_key = f"fav_{mid}_{row_idx}_{col_idx}"
    det_key = f"det_{mid}_{row_idx}_{col_idx}"
    link_key = f"lnk_{mid}_{row_idx}_{col_idx}"

    is_fav = mid in st.session_state["favs"]
    fav_label = ("★ Favorite" if is_fav else "☆ Favorite")

    c1, c2, c3 = col.columns(3)
    with c1:
        if st.button(fav_label, key=fav_key, use_container_width=True):
            if is_fav:
                st.session_state["favs"].discard(mid)
            else:
                st.session_state["favs"].add(mid)
            safe_rerun()
    with c2:
        if st.button("🔎 Details", key=det_key, use_container_width=True):
            st.session_state["__detail__"] = item
            safe_rerun()
    with c3:
        # 打开 TMDB 详情
        tmdb_url = f"https://www.themoviedb.org/movie/{mid}"
        if st.button("↗ TMDB", key=link_key, use_container_width=True):
            st.session_state["__open_url__"] = tmdb_url
            st.markdown(f"[Open on TMDB]({tmdb_url})")
    col.markdown('</div>', unsafe_allow_html=True)   # /btn-row
    col.markdown('</div>', unsafe_allow_html=True)   # /content-wrap
    col.markdown('</div>', unsafe_allow_html=True)   # /movie-card

# 渲染网格
rows = math.ceil(PAGE_SIZE / 3)
cards = results[:PAGE_SIZE] if len(results) >= PAGE_SIZE else results

i = 0
for r in range(4):                # 固定 4 行
    cols = st.columns(3)
    for c in range(3):            # 固定 3 列
        if i < len(cards):
            render_card(cards[i], cols[c], r, c)
            i += 1
        else:
            # 空卡占位，保持网格完整 & 对齐
            with cols[c]:
                st.markdown('<div class="movie-card" style="opacity:0.15; background:#fafafa;"></div>', unsafe_allow_html=True)

# ---------------------------
# Detail panel (optional)
# ---------------------------
if "__detail__" in st.session_state:
    d = st.session_state["__detail__"]
    st.markdown("---")
    st.subheader(f'📝 {d.get("title") or d.get("name")}')
    dd1, dd2 = st.columns([1,2])
    with dd1:
        st.image(img_url(d.get("poster_path"), "w500"), use_container_width=True)
    with dd2:
        st.write(f"**Release**: {d.get('release_date') or '—'}")
        st.write(f"**Rating**: {d.get('vote_average') or 0:.1f} ({d.get('vote_count') or 0} votes)")
        if d.get("original_language"):
            st.write(f"**Original language**: `{d.get('original_language')}`")
        if d.get("overview"):
            st.write("**Overview**")
            st.write(d.get("overview"))
        tmdb_url = f"https://www.themoviedb.org/movie/{d.get('id')}"
        st.link_button("↗ Open on TMDB", tmdb_url)
    if st.button("Close details"):
        del st.session_state["__detail__"]
        safe_rerun()

# ---------------------------
# Footer pager
# ---------------------------
fp1, fp2, fp3 = st.columns([1,1,1])
with fp1:
    if st.button("⏮ First", use_container_width=True):
        st.session_state["__page__"] = 1
        set_page_query(1)
        safe_rerun()
with fp2:
    if st.button("◀ Prev", use_container_width=True, disabled=(page<=1)):
        st.session_state["__page__"] = max(1, page-1)
        set_page_query(int(st.session_state["__page__"]))
        safe_rerun()
with fp3:
    if st.button("Next ▶", use_container_width=True, disabled=(page>=total_pages)):
        st.session_state["__page__"] = min(total_pages, page+1)
        set_page_query(int(st.session_state["__page__"]))
        safe_rerun()
