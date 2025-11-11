# app.py — TMDB Movie Explorer (Grid 3x4, equal-height cards)
# -----------------------------------------------------------
# 需要：pip install streamlit requests
# 在侧边栏输入 TMDB v3 API key（themoviedb.org 个人设置页里叫“API 키 / API key (v3 auth)”）

import math
import requests
import streamlit as st

st.set_page_config(page_title="TMDB Movie Explorer", page_icon="🎬", layout="wide")

# ==========================
# --------- CSS ------------
# ==========================
CARD_CSS = """
<style>
/* ---- 页面主区域留白更紧凑 ---- */
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }

/* 让列容器本身也走 flex，避免“上半空白、下半内容” */
[data-testid="stColumn"] > div {
  display: flex;
  flex-direction: column;
}

/* --- 卡片：等高、分区、阴影 --- */
.movie-card {
  background: #ffffff;
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 14px;
  padding: 16px;
  height: 100%;                  /* 关键：占满列容器高度 */
  min-height: 520px;             /* 别太矮，视觉更稳 */
  display: flex;
  flex-direction: column;
  box-shadow: 0 2px 20px rgba(0,0,0,0.04);
}

/* 海报固定高度区域，防空白抖动 */
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

/* 标题/元信息/简介 */
.content-wrap { margin-top: 12px; }
.title-row {
  font-weight: 800;
  font-size: 1.05rem;
  margin-bottom: 4px;
}
.meta-row {
  color: #666;
  font-size: .86rem;
}

/* 多行截断，保持卡片等高 */
.overview {
  margin-top: 8px;
  font-size: .94rem;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 6;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 占位弹性块，用来把底部按钮“压到底” */
.flex-spacer { flex: 1 1 auto; }

/* 按钮横排、居中、等距 */
.btn-row {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-top: 12px;
}
.btn-row .stButton > button, .btn-row .stLinkButton > a {
  width: 100px;
  height: 36px;
  border-radius: 10px;
  font-weight: 600;
}

/* 列间距、卡片之间留白 */
.card-pad { padding: .2rem; }

/* 列表模式下的简洁卡片 */
.list-card {
  display: grid;
  grid-template-columns: 120px 1fr 260px;
  gap: 16px;
  align-items: center;
  background: #fff;
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.04);
}
.list-poster {
  width: 100%;
  height: 160px;
  border-radius: 8px;
  object-fit: cover;
  background: #f6f7f9;
}

/* 顶部面包屑/统计 */
.topbar { color:#666; font-size: .92rem; margin:.2rem 0 1rem; }
</style>
"""
st.markdown(CARD_CSS, unsafe_allow_html=True)

# ==========================
# ------- 常量/工具 ---------
# ==========================
TMDB_API = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p/"

def api_get(path, params, api_key):
    """基础 GET 封装（自动加 key/报错消息）"""
    params = dict(params or {})
    params["api_key"] = api_key
    try:
        r = requests.get(f"{TMDB_API}{path}", params=params, timeout=25)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        st.error(f"TMDB 请求失败：{e}")
    except Exception as e:
        st.error(f"网络异常：{e}")
    return {}

@st.cache_data(show_spinner=False, ttl=3600)
def get_genres(lang, api_key):
    j = api_get("/genre/movie/list", {"language": lang}, api_key)
    data = j.get("genres", []) if isinstance(j, dict) else []
    return {g["id"]: g["name"] for g in data}

def poster_url(path: str|None, width: int):
    if not path:
        return ""  # 无海报
    # 选用接近的 TMDB 预设宽度档位
    # 官方有：w185, w342, w500, w780, 原图 original
    size = "w342"
    if width <= 200: size = "w185"
    elif width <= 420: size = "w342"
    elif width <= 650: size = "w500"
    elif width <= 900: size = "w780"
    else: size = "original"
    return f"{TMDB_IMG}{size}{path}"

# ==========================
# -------- 侧边栏 ----------
# ==========================
st.sidebar.header("🔐 API Credentials")
hide = st.sidebar.checkbox("Hide API Key", value=True)
api_key = st.sidebar.text_input("TMDB v3 API Key", type="password" if hide else "default").strip()

st.sidebar.header("🔎 Query Settings")
keyword = st.sidebar.text_input("Keyword (empty → Discover mode)", value="")
lang = st.sidebar.selectbox(
    "UI Language", ["en-US", "ko-KR", "ja-JP", "zh-CN", "zh-TW", "fr-FR", "de-DE", "es-ES"],
    index=0,
)

col_a, col_b = st.sidebar.columns(2)
with col_a:
    region = st.selectbox("Region (watch availability, cert, etc.)", ["(Any)", "US", "KR", "JP", "GB", "DE", "FR", "ES"], index=1)
with col_b:
    sort_by = st.selectbox("Sort by (discover)", [
        "popularity.desc","popularity.asc",
        "vote_average.desc","vote_average.asc",
        "primary_release_date.desc","primary_release_date.asc",
    ], index=0)

include_adult = st.sidebar.checkbox("Include adult", value=False)
st.sidebar.caption("Vote average range")
va_min, va_max = 0.0, 10.0
st.sidebar.slider("", min_value=0.0, max_value=10.0, value=(0.0, 10.0), step=0.1, key="vote_rng")
st.sidebar.caption("Runtime (min)")
st.sidebar.slider("", 0, 240, (0, 240), key="rt_rng")

orig_lang = st.sidebar.selectbox("Original language", ["(Any)","en","ko","ja","zh","fr","de","es","it","ru","pt"], index=0)

genres_map = get_genres(lang, api_key) if api_key else {}
sel_genre = st.sidebar.multiselect("Genres", options=list(genres_map.values()), default=[])

st.sidebar.header("🧩 Layout")
layout_mode = st.sidebar.radio("Layout", ["Grid", "List"], index=0, horizontal=True)
poster_w = st.sidebar.slider("Poster size", 185, 500, 342, step=1)
page = st.sidebar.number_input("Page", min_value=1, value=1, step=1)
R, C = (4, 3)   # 4 行 × 3 列
PER_PAGE = R * C

with st.sidebar:
    c1, c2, c3 = st.columns([1,1,1])
    if c1.button("⏮ First", use_container_width=True):
        st.session_state["jump_page"] = 1
    if c2.button("◀ Prev", use_container_width=True):
        st.session_state["jump_page"] = max(1, page-1)
    if c3.button("Next ▶", use_container_width=True):
        st.session_state["jump_page"] = page+1
    if "jump_page" in st.session_state:
        page = st.session_state.pop("jump_page")

if not api_key:
    st.info("请在左侧输入 TMDB v3 API Key 后再开始～")
    st.stop()

# ==========================
# -------- 数据获取 ---------
# ==========================
def ids_by_genre_names(names):
    inv = {v:k for k,v in genres_map.items()}
    return [inv[n] for n in names if n in inv]

def search_movies():
    if keyword.strip():
        # 关键字搜索
        j = api_get("/search/movie", {
            "query": keyword, "language": lang, "include_adult": str(include_adult).lower(),
            "page": page
        }, api_key)
        results = j.get("results", []) if isinstance(j, dict) else []
        total = j.get("total_results", 0)
        total_pages = j.get("total_pages", 1)
        return results, total, total_pages

    # Discover
    params = {
        "language": lang,
        "include_adult": str(include_adult).lower(),
        "sort_by": sort_by,
        "page": page,
        "vote_average.gte": st.session_state.vote_rng[0],
        "vote_average.lte": st.session_state.vote_rng[1],
        "with_runtime.gte": st.session_state.rt_rng[0],
        "with_runtime.lte": st.session_state.rt_rng[1],
    }
    if region and region != "(Any)":
        params["region"] = region
        params["watch_region"] = region
    if orig_lang != "(Any)":
        params["with_original_language"] = orig_lang
    g_ids = ids_by_genre_names(sel_genre)
    if g_ids:
        params["with_genres"] = ",".join(map(str, g_ids))

    j = api_get("/discover/movie", params, api_key)
    results = j.get("results", []) if isinstance(j, dict) else []
    total = j.get("total_results", 0)
    total_pages = j.get("total_pages", 1)
    return results, total, total_pages

movies, total_items, total_pages = search_movies()

st.markdown(
    f'<div class="topbar">'
    f'{total_items:,.0f} result(s) • Page <b>{page}</b> / {total_pages:,} '
    f'• Showing <b>{min(PER_PAGE, len(movies))}</b> per page ({C}×{R})'
    f'</div>', unsafe_allow_html=True
)

# ==========================
# ------- 卡片组件 ----------
# ==========================
def render_movie_grid_item(m):
    """网格卡片（等高）"""
    title = m.get("title") or m.get("name") or "Untitled"
    date = (m.get("release_date") or "")[:10]
    vote = m.get("vote_average") or 0
    overview = m.get("overview") or ""
    poster = poster_url(m.get("poster_path"), poster_w)
    tmdb_url = f'https://www.themoviedb.org/movie/{m.get("id")}'

    # 卡片外框
    st.markdown('<div class="movie-card">', unsafe_allow_html=True)

    # 海报
    if poster:
        st.markdown(f'<div class="poster-wrap"><img src="{poster}" alt="poster"></div>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<div class="poster-wrap"><div style="opacity:.5">No Image</div></div>',
                    unsafe_allow_html=True)

    # 文本区
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.markdown(f'<div class="title-row">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="meta-row">{date} · ⭐ {vote:.1f}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="overview">{overview}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 弹性占位，保证下面按钮“压底”
    st.markdown('<div class="flex-spacer"></div>', unsafe_allow_html=True)

    # 按钮横排
    st.markdown('<div class="btn-row">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1,1], vertical_alignment="center")
    with c1:
        st.button("⭐ Favorite", key=f"fav_{m['id']}", use_container_width=True)
    with c2:
        with st.expander("🔍 Details", expanded=False):
            st.write(f"**Title**: {title}")
            st.write(f"**Release**: {date}")
            st.write(f"**Rating**: {vote:.1f}")
            g_ids = m.get("genre_ids") or []
            if genres_map:
                st.write("**Genres**:", ", ".join(genres_map.get(g,"") for g in g_ids if g in genres_map))
            st.write("**Overview**:", overview or "(no overview)")
    with c3:
        st.link_button("↗ TMDB", tmdb_url, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)  # end .movie-card


def render_movie_list_item(m):
    """列表卡片（简洁行）"""
    title = m.get("title") or m.get("name") or "Untitled"
    date = (m.get("release_date") or "")[:10]
    vote = m.get("vote_average") or 0
    overview = m.get("overview") or ""
    poster = poster_url(m.get("poster_path"), 200)
    tmdb_url = f'https://www.themoviedb.org/movie/{m.get("id")}'

    with st.container():
        st.markdown('<div class="list-card">', unsafe_allow_html=True)
        # 左：海报
        if poster:
            st.markdown(f'<img class="list-poster" src="{poster}" alt="poster">', unsafe_allow_html=True)
        else:
            st.markdown('<div class="list-poster" />', unsafe_allow_html=True)
        # 中：文本
        st.markdown(
            f"""<div>
                <div class="title-row">{title}</div>
                <div class="meta-row">{date} · ⭐ {vote:.1f}</div>
                <div style="margin-top:8px">{overview}</div>
            </div>""", unsafe_allow_html=True
        )
        # 右：按钮
        b1, b2, b3 = st.columns(3)
        with b1: st.button("⭐ Favorite", key=f"fav_list_{m['id']}", use_container_width=True)
        with b2:
            with st.expander("🔍 Details", expanded=False):
                st.write(f"**Title**: {title}")
                st.write(f"**Release**: {date}")
                st.write(f"**Rating**: {vote:.1f}")
                g_ids = m.get("genre_ids") or []
                if genres_map:
                    st.write("**Genres**:", ", ".join(genres_map.get(g,"") for g in g_ids if g in genres_map))
                st.write("**Overview**:", overview or "(no overview)")
        with b3: st.link_button("↗ TMDB", tmdb_url, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ==========================
# --------- 渲染 -----------
# ==========================
if not movies:
    st.warning("没有结果。可以换个关键词 / 语言 / 地区 / 筛选试试。")
else:
    if layout_mode == "Grid":
        # 3×4 网格
        idx = 0
        for _ in range(R):
            cols = st.columns(C, gap="large")
            for c in cols:
                if idx >= len(movies):  # 不足 12 个时补位
                    with c:
                        st.markdown('<div class="movie-card" style="opacity:.0"></div>', unsafe_allow_html=True)
                    continue
                with c.container():
                    st.markdown('<div class="card-pad">', unsafe_allow_html=True)
                    render_movie_grid_item(movies[idx])
                    st.markdown('</div>', unsafe_allow_html=True)
                    idx += 1
    else:
        # 列表模式
        for m in movies:
            render_movie_list_item(m)

# 页脚链接
st.caption("Data source: TMDB Open API. This product uses the TMDB API but is not endorsed or certified by TMDB.")
