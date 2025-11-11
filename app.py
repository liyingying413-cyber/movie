# TMDB Movie Explorer — Pro (Discover + Favorites + Providers)
# Author: you :)
# Dependencies: streamlit>=1.34, requests>=2.31

import os
import math
import requests
import streamlit as st

st.set_page_config(page_title="TMDB Movie Explorer", page_icon="🎬", layout="wide")

TMDB_API = "https://api.themoviedb.org/3"
IMG_FALLBACK = "https://via.placeholder.com/342x513?text=No+Poster"
DEFAULT_LANG = "en-US"

# ---------------- API Gate ----------------
st.sidebar.header("🔐 API Credentials")
hide = st.sidebar.checkbox("Hide API Key", value=True)
default_key = st.secrets.get("TMDB_V3_KEY", os.getenv("TMDB_V3_KEY", "")) if hasattr(st, "secrets") else os.getenv("TMDB_V3_KEY", "")
api_key = st.sidebar.text_input("TMDB v3 API Key", value=default_key, type="password" if hide else "default")
if api_key:
    st.session_state["TMDB_V3_KEY"] = api_key.strip()

def tmdb_get(path: str, params: dict | None = None):
    key = st.session_state.get("TMDB_V3_KEY", "")
    if not key:
        raise RuntimeError("Missing TMDB API key")
    params = params or {}
    params["api_key"] = key
    r = requests.get(f"{TMDB_API}{path}", params=params, timeout=20)
    r.raise_for_status()
    return r.json()

# ---------------- Cached lookups ----------------
@st.cache_data(ttl=86400, show_spinner=False)
def get_config():
    return tmdb_get("/configuration")

@st.cache_data(ttl=86400, show_spinner=False)
def get_genres(lang=DEFAULT_LANG):
    return tmdb_get("/genre/movie/list", {"language": lang}).get("genres", [])

@st.cache_data(ttl=86400, show_spinner=False)
def get_regions():
    # watch provider regions
    data = tmdb_get("/watch/providers/regions")
    # 取常见地区优先顺序
    priority = ["US", "KR", "JP", "GB", "FR", "DE", "ES", "IT", "AU", "CA", "IN", "CN"]
    results = data.get("results", [])
    results.sort(key=lambda x: (0 if x.get("iso_3166_1") in priority else 1, x.get("english_name","")))
    return results

@st.cache_data(ttl=600, show_spinner=False)
def search_movies(query, page=1, lang=DEFAULT_LANG):
    params = {"query": query, "page": page, "language": lang, "include_adult": False}
    data = tmdb_get("/search/movie", params)
    return data.get("results", []), int(data.get("total_results", 0)), int(data.get("total_pages", 1))

@st.cache_data(ttl=600, show_spinner=False)
def discover_movies(page=1, lang=DEFAULT_LANG, with_genres=None, year=None,
                    region=None, sort_by="popularity.desc", include_adult=False,
                    vote_gte=0.0, vote_lte=10.0, runtime_gte=0, runtime_lte=400,
                    original_lang=None):
    params = {
        "language": lang,
        "page": page,
        "sort_by": sort_by,
        "include_adult": bool(include_adult),
        "vote_average.gte": vote_gte,
        "vote_average.lte": vote_lte,
        "with_runtime.gte": runtime_gte,
        "with_runtime.lte": runtime_lte,
    }
    if with_genres:
        params["with_genres"] = ",".join(map(str, with_genres))
    if year:
        params["primary_release_year"] = int(year)
    if region:
        params["region"] = region
    if original_lang:
        params["with_original_language"] = original_lang

    data = tmdb_get("/discover/movie", params)
    return data.get("results", []), int(data.get("total_results", 0)), int(data.get("total_pages", 1))

@st.cache_data(ttl=600, show_spinner=False)
def get_movie_details(movie_id, lang=DEFAULT_LANG):
    # 一次拿齐：视频、图片、演职员、上映信息
    return tmdb_get(f"/movie/{movie_id}", {
        "language": lang,
        "append_to_response": "videos,images,credits,release_dates"
    })

@st.cache_data(ttl=600, show_spinner=False)
def get_watch_providers(movie_id):
    # 返回各国可观看渠道
    return tmdb_get(f"/movie/{movie_id}/watch/providers").get("results", {})

def img_url(poster_path, size="w342"):
    try:
        conf = get_config()
        base = conf["images"]["secure_base_url"]
        return f"{base}{size}{poster_path}"
    except Exception:
        return IMG_FALLBACK

# ---------------- UI: Title & Key Check ----------------
st.title("🎬 TMDB Movie Explorer — Pro")
st.caption("Get a free v3 API key from https://www.themoviedb.org/ • This app supports **search** and powerful **discover** filters.")

if not st.session_state.get("TMDB_V3_KEY"):
    st.info("👉 Please enter your **TMDB v3 API Key** in the left sidebar.")
    st.stop()

# quick validation
try:
    _ = get_config()
except requests.HTTPError as e:
    st.error(f"TMDB error: {e.response.status_code} — {e.response.text}")
    st.stop()
except Exception as e:
    st.error(f"Failed to validate API key: {e}")
    st.stop()

# ---------------- Tabs (Results / Favorites) ----------------
tab_results, tab_fav = st.tabs(["🔎 Explore", "⭐ Favorites"])

# ---------------- Sidebar: Controls ----------------
st.sidebar.header("🔍 Query Settings")

q = st.sidebar.text_input("Keyword (empty → Discover mode)")
lang = st.sidebar.selectbox("UI Language",
                            ["en-US","ko-KR","zh-CN","ja-JP","fr-FR","de-DE","es-ES","it-IT","pt-BR"],
                            index=0)

# Discover Controls（仅在 q 为空时起作用）
st.sidebar.markdown("**Discover filters** (effective when keyword is empty)")
genres = get_genres(lang)
genre_map = {g["name"]: g["id"] for g in genres}
genre_choices = st.sidebar.multiselect("Genres", list(genre_map.keys()))
with_genres = [genre_map[name] for name in genre_choices] if genre_choices else None

use_year = st.sidebar.checkbox("Filter by year", value=False)
year = st.sidebar.number_input("Year", min_value=1870, max_value=2100, value=2020, step=1) if use_year else None

regions = get_regions()
region_disp = [f"{r.get('iso_3166_1')} — {r.get('english_name')}" for r in regions]
region_idx = st.sidebar.selectbox("Region (watch availability, certification, etc.)",
                                  ["(Any)"] + region_disp, index=0)
region_code = None if region_idx == "(Any)" else regions[region_disp.index(region_idx)].get("iso_3166_1")

include_adult = st.sidebar.checkbox("Include adult", value=False)

# 分数 & 时长范围
vote_gte, vote_lte = st.sidebar.slider("Vote average range", 0.0, 10.0, (0.0, 10.0), step=0.1)
rt_gte, rt_lte = st.sidebar.slider("Runtime (min)", 0, 400, (0, 240), step=10)

# 原始语言（注意与 UI 语言不同，这是影片原始发行语言）
orig_lang = st.sidebar.selectbox("Original language",
                                 ["(Any)","en","ko","zh","ja","fr","de","es","it","pt","hi","ru"],
                                 index=0)
orig_lang = None if orig_lang == "(Any)" else orig_lang

# 排序（仅 discover）
sort_by = st.sidebar.selectbox(
    "Sort by (discover)",
    ["popularity.desc","popularity.asc","vote_average.desc","vote_average.asc",
     "primary_release_date.desc","primary_release_date.asc","revenue.desc","revenue.asc"],
    index=0
)

# 布局 & 海报清晰度
layout = st.sidebar.radio("Layout", ["Grid","List"], index=0, horizontal=True)
poster_size = st.sidebar.select_slider("Poster size", options=["w185","w342","w500"], value="w342")

# 分页
per_row = 5 if layout=="Grid" else 1
page = st.sidebar.number_input("Page", min_value=1, value=1, step=1)
go = st.sidebar.button("Start / Refresh", use_container_width=True)

# 初始化收藏
if "favorites" not in st.session_state:
    st.session_state["favorites"] = set()

# ---------------- Fetch & Show ----------------
import math

UI_COLS = 3             # 每行 3 张
UI_ROWS = 4             # 4 行
UI_PAGE_SIZE = UI_COLS * UI_ROWS   # 12 条/页
TMDB_PAGE_SIZE = 20     # TMDB 固定 20 条/页

def _fetch_window_by_ui_page(
    ui_page: int,
    *,
    lang: str,
    keyword: str | None,
    discover_kwargs: dict
):
    """
    将“UI 页” -> 映射到 TMDB 的 20/页数据，拼接两页以保证 UI 显示 12 条。
    返回 (slice_results, total_count, total_ui_pages)
    """
    start_global = (ui_page - 1) * UI_PAGE_SIZE
    api_page = start_global // TMDB_PAGE_SIZE + 1
    offset = start_global % TMDB_PAGE_SIZE

    # 拉第一页
    if keyword:
        page1, total1, total_pages1 = search_movies(keyword, page=api_page, lang=lang)
    else:
        page1, total1, total_pages1 = discover_movies(page=api_page, lang=lang, **discover_kwargs)

    total = total1  # TMDB 两次返回的 total 一致
    total_ui_pages = max(1, math.ceil(total / UI_PAGE_SIZE))

    # 可能需要跨页
    need = UI_PAGE_SIZE
    buf = page1[offset: offset + need]
    need -= len(buf)

    if need > 0:
        # 拉第二页补齐
        if keyword:
            page2, _, _ = search_movies(keyword, page=api_page + 1, lang=lang)
        else:
            page2, _, _ = discover_movies(page=api_page + 1, lang=lang, **discover_kwargs)
        take2 = min(need, len(page2))
        buf += page2[:take2]

    return buf, total, total_ui_pages


def _fav_toggle(mid: int):
    favs = st.session_state["favorites"]
    if mid in favs:
        favs.remove(mid)
    else:
        favs.add(mid)


def movie_card_horizontal(m, poster_size="w342"):
    """卡片：横向内容，底部三按钮横排"""
    poster = m.get("poster_path")
    title = m.get("title") or m.get("name") or "Untitled"
    rel = m.get("release_date") or ""
    rate = m.get("vote_average", 0)
    mid = m.get("id")
    overview = (m.get("overview") or "").strip()

    with st.container(border=True):
        # 头部：封面 + 文案
        top = st.columns([1, 2])
        with top[0]:
            st.image(img_url(poster, size=poster_size) if poster else IMG_FALLBACK,
                     use_container_width=True)
        with top[1]:
            st.subheader(title)
            meta = " · ".join([x for x in [rel, f"⭐ {rate:.1f}"] if x])
            if meta:
                st.caption(meta)
            if overview:
                st.write(overview[:260] + ("..." if len(overview) > 260 else ""))

        # 底部：按钮横排
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button(("⭐ Unfavorite" if mid in st.session_state["favorites"] else "☆ Favorite"),
                         key=f"fav_{mid}"):
                _fav_toggle(mid); st.rerun()
        with b2:
            if st.button("🔎 Details", key=f"detail_{mid}"):
                st.session_state["detail_id"] = mid; st.rerun()
        with b3:
            st.link_button("↗ TMDB", f"https://www.themoviedb.org/movie/{mid}")


# ---------- 结果页 ----------
with tab_results:
    if not go:
        st.warning("Click **Start / Refresh** in the sidebar to run your query.")
        st.stop()

    # 构造 discover 参数（keyword 为空时生效）
    discover_kwargs = dict(
        with_genres=with_genres,
        year=year,
        region=region_code,
        sort_by=sort_by,
        include_adult=include_adult,
        vote_gte=vote_gte,
        vote_lte=vote_lte,
        runtime_gte=rt_gte,
        runtime_lte=rt_lte,
        original_lang=orig_lang,
    )

    with st.spinner("Fetching movies..."):
        window, total, total_ui_pages = _fetch_window_by_ui_page(
            ui_page=page,
            lang=lang,
            keyword=q.strip() if q.strip() else None,
            discover_kwargs=discover_kwargs
        )

    st.write(f"**{total:,}** result(s) • Page **{page} / {total_ui_pages}** • "
             f"Showing **{len(window)}** per page (3×4)")

    if not window:
        st.info("No results. Try another keyword/filters.")
        st.stop()

    # 渲染 3 列×4 行（最多 12 个）
    rows = [window[i:i+UI_COLS] for i in range(0, len(window), UI_COLS)]
    for row in rows:
        cols = st.columns(UI_COLS)
        for c, item in zip(cols, row):
            with c:
                movie_card_horizontal(item, poster_size=poster_size)

    # UI 分页（基于 12/页）
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("⏮ First", disabled=(page <= 1)):
            st.session_state["_goto_page"] = 1; st.rerun()
    with c2:
        if st.button("◀ Prev", disabled=(page <= 1)):
            st.session_state["_goto_page"] = page - 1; st.rerun()
    with c3:
        if st.button("Next ▶", disabled=(page >= total_ui_pages)):
            st.session_state["_goto_page"] = min(total_ui_pages, page + 1); st.rerun()
    with c4:
        if st.button("Last ⏭", disabled=(page >= total_ui_pages)):
            st.session_state["_goto_page"] = total_ui_pages; st.rerun()

    if "_goto_page" in st.session_state:
        st.experimental_set_query_params(page=str(st.session_state["_goto_page"]))
        del st.session_state["_goto_page"]

# ---------- 收藏页（保持不变） ----------
with tab_fav:
    fav_ids = list(st.session_state["favorites"])
    st.write(f"⭐ You have **{len(fav_ids)}** favorite(s).")
    if not fav_ids:
        st.info("No favorites yet. Click ☆ in results to add.")
    else:
        for mid in fav_ids:
            try:
                d = get_movie_details(mid, lang=DEFAULT_LANG)
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
                st.caption(d.get("overview","")[:200] + "…")
                st.link_button("Open on TMDB ↗", f"https://www.themoviedb.org/movie/{mid}")
            with cols[2]:
                if st.button("Remove", key=f"rm_{mid}"):
                    st.session_state["favorites"].remove(mid); st.rerun()

# ---------- 详情抽屉（保持不变） ----------
if "detail_id" in st.session_state:
    mid = st.session_state["detail_id"]
    with st.expander("Movie details", expanded=True):
        try:
            d = get_movie_details(mid, lang=DEFAULT_LANG)
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

                if region_code:
                    rels = (d.get("release_dates") or {}).get("results") or []
                    cert = None
                    for block in rels:
                        if block.get("iso_3166_1")==region_code:
                            for rel in block.get("release_dates", []):
                                c = rel.get("certification")
                                if c:
                                    cert = c; break
                            if cert: break
                    if cert:
                        st.caption(f"Certification in {region_code}: **{cert}**")

                vids = (d.get("videos", {}) or {}).get("results", [])
                yt = next((v for v in vids if v.get("site")=="YouTube" and v.get("type") in ("Trailer","Teaser")), None)
                if yt:
                    st.link_button("▶ Watch trailer on YouTube", f"https://www.youtube.com/watch?v={yt['key']}")

                provs = get_watch_providers(mid)
                if region_code and region_code in provs:
                    st.markdown("**Where to watch**")
                    p_block = provs[region_code]
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

# ---------------- Favorites Tab ----------------
with tab_fav:
    fav_ids = list(st.session_state["favorites"])
    st.write(f"⭐ You have **{len(fav_ids)}** favorite(s).")
    if not fav_ids:
        st.info("No favorites yet. Click ☆ in results to add.")
    else:
        # 简单展示收藏：逐个拿详情（缓存命中快）
        for mid in fav_ids:
            try:
                d = get_movie_details(mid, lang=DEFAULT_LANG)
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
                st.caption(d.get("overview","")[:200] + "…")
                st.link_button("Open on TMDB ↗", f"https://www.themoviedb.org/movie/{mid}")
            with cols[2]:
                if st.button("Remove", key=f"rm_{mid}"):
                    st.session_state["favorites"].remove(mid); st.rerun()

# ---------------- Details Drawer ----------------
if "detail_id" in st.session_state:
    mid = st.session_state["detail_id"]
    with st.expander("Movie details", expanded=True):
        try:
            d = get_movie_details(mid, lang=DEFAULT_LANG)
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

                # Top cast
                cast = ((d.get("credits") or {}).get("cast") or [])[:6]
                if cast:
                    st.markdown("**Top Cast**")
                    cast_line = " · ".join([f"{c.get('name','?')} ({c.get('character','')})" for c in cast])
                    st.write(cast_line)

                # Certification by region
                if region_code:
                    rels = (d.get("release_dates") or {}).get("results") or []
                    cert = None
                    for block in rels:
                        if block.get("iso_3166_1")==region_code:
                            for rel in block.get("release_dates", []):
                                c = rel.get("certification")
                                if c:
                                    cert = c; break
                            if cert: break
                    if cert:
                        st.caption(f"Certification in {region_code}: **{cert}**")

                # Trailer
                vids = (d.get("videos", {}) or {}).get("results", [])
                yt = next((v for v in vids if v.get("site")=="YouTube" and v.get("type") in ("Trailer","Teaser")), None)
                if yt:
                    st.link_button("▶ Watch trailer on YouTube", f"https://www.youtube.com/watch?v={yt['key']}")

                # Watch providers
                provs = get_watch_providers(mid)
                if region_code and region_code in provs:
                    st.markdown("**Where to watch**")
                    p_block = provs[region_code]
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
