import os
import math
import uuid
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Tuple, List
import base64
from io import BytesIO

import folium
from folium.plugins import MarkerCluster, HeatMap
from folium import Icon

import gradio as gr
from PIL import Image, ExifTags

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "reports.db"
UPLOAD_DIR = APP_DIR / "uploads"
THUMB_DIR = UPLOAD_DIR / "thumbs"
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
THUMB_DIR.mkdir(exist_ok=True, parents=True)

# 分類顏色（Leaflet 標記可用的顏色）
CATEGORY_COLORS = {
    "土石流": "red",
    "淹水": "blue",
    "道路受阻": "orange",
    "建物損毀": "purple",
    "其他": "gray",
}
# 前端 CSS 用的十六進位顏色（徽章、邊框等）
CATEGORY_HEX = {
    "土石流": "#ef4444",
    "淹水": "#3b82f6",
    "道路受阻": "#f59e0b",
    "建物損毀": "#8b5cf6",
    "其他": "#6b7280",
}

# ---------- DB ----------
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id TEXT PRIMARY KEY,
        caption TEXT,
        category TEXT,
        severity INTEGER,
        image_path TEXT,
        thumb_path TEXT,
        lat REAL,
        lng REAL,
        taken_at TEXT,
        reported_at TEXT
    )
    """)
    con.commit()
    con.close()

# ---------- Utils ----------
def exif_taken_at(pil_img: Image.Image) -> Optional[str]:
    try:
        exif = pil_img.getexif()
        if not exif: return None
        exif_dict = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
        dt = exif_dict.get("DateTimeOriginal") or exif_dict.get("DateTime")
        if not dt: return None
        dt = dt.strip().replace("-", ":")
        parsed = datetime.strptime(dt, "%Y:%m:%d %H:%M:%S")
        return parsed.replace(tzinfo=timezone.utc).isoformat()
    except Exception:
        return None

def save_image(pil_img: Image.Image) -> Tuple[str, str]:
    rid = str(uuid.uuid4())[:8]
    img_path = UPLOAD_DIR / f"{rid}.jpg"
    pil_img.save(img_path, format="JPEG", quality=90)
    th = pil_img.copy()
    th.thumbnail((640, 640))
    th_path = THUMB_DIR / f"{rid}_thumb.jpg"
    th.save(th_path, format="JPEG", quality=85)
    return str(img_path), str(th_path)

def _img_to_b64(path: str, max_side: int = None) -> Optional[str]:
    if not path or not os.path.exists(path): return None
    try:
        if max_side:
            im = Image.open(path).convert("RGB")
            im.thumbnail((max_side, max_side))
            buf = BytesIO(); im.save(buf, format="JPEG", quality=88)
            return base64.b64encode(buf.getvalue()).decode()
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0088
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1); dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def insert_report(caption, category, severity, img_path, thumb_path, lat, lng, taken_at_iso):
    now_iso = datetime.now(timezone.utc).isoformat()
    rid = str(uuid.uuid4())
    con = sqlite3.connect(DB_PATH); cur = con.cursor()
    cur.execute("""
      INSERT INTO reports(id, caption, category, severity, image_path, thumb_path, lat, lng, taken_at, reported_at)
      VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (rid, caption, category, severity, img_path, thumb_path, lat, lng, taken_at_iso, now_iso))
    con.commit(); con.close(); return rid

def load_feed(center_lat, center_lng, radius_km, sort_key="distance") -> List[tuple]:
    con = sqlite3.connect(DB_PATH); cur = con.cursor()
    cur.execute("SELECT id, caption, category, severity, image_path, thumb_path, lat, lng, taken_at, reported_at FROM reports")
    rows = cur.fetchall(); con.close()
    items = []
    for r in rows:
        rid, caption, category, severity, image_path, thumb_path, lat, lng, taken_at, reported_at = r
        dist = haversine(center_lat, center_lng, lat, lng) if None not in (center_lat, center_lng, lat, lng) else None
        if radius_km <= 0 or dist is None or dist <= radius_km:
            items.append((rid, caption, category, severity, image_path, thumb_path, lat, lng, taken_at, reported_at, dist))
    if sort_key == "distance":
        items.sort(key=lambda x: float("inf") if x[10] is None else x[10])
    elif sort_key == "time_newest":
        items.sort(key=lambda x: x[9] or "", reverse=True)
    elif sort_key == "time_taken_newest":
        items.sort(key=lambda x: x[8] or "", reverse=True)
    return items

# ---------- Map HTML ----------
def generate_map_html():
    con = sqlite3.connect(DB_PATH); cur = con.cursor()
    cur.execute("SELECT id, caption, category, severity, image_path, thumb_path, lat, lng, taken_at, reported_at FROM reports")
    rows = cur.fetchall(); con.close()

    fmap = folium.Map(location=[23.7, 121.0], zoom_start=7, tiles=None, control_scale=True, zoom_control=True, height="100%", width="100%")
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", control=False).add_to(fmap)

    marker_layer = folium.FeatureGroup(name="災情叢集", show=True)
    cluster = MarkerCluster().add_to(marker_layer)

    heat_data = []
    all_points = []

    for rid, caption, category, severity, image_path, thumb_path, lat, lng, taken_at, reported_at in rows:
        if lat is None or lng is None: continue
        w = float(severity or 1); heat_data.append([lat, lng, w])

        thumb_b64 = _img_to_b64(thumb_path, max_side=480) or _img_to_b64(image_path, max_side=480)
        large_b64 = _img_to_b64(image_path, max_side=1600) or thumb_b64

        color_name = CATEGORY_COLORS.get(category or "其他", "gray")
        color_hex = CATEGORY_HEX.get(category or "其他", "#6b7280")

        payload = {
            "id": rid, "category": category, "severity": severity,
            "caption": caption or "", "lat": lat, "lng": lng,
            "taken_at": taken_at or "", "reported_at": reported_at or "",
            "img_large": f"data:image/jpeg;base64,{large_b64}" if large_b64 else "",
            "img_thumb": f"data:image/jpeg;base64,{thumb_b64}" if thumb_b64 else "",
            "cat_hex": color_hex
        }
        all_points.append(payload)

        payload_json = json.dumps(payload, ensure_ascii=False)
        badge_html = f'<span style="display:inline-flex;align-items:center;gap:6px;font-weight:800"><i style="display:inline-block;width:10px;height:10px;border-radius:9999px;background:{color_hex}"></i>{category or "未分類"}・嚴重度 {severity}</span>'
        preview_html = f"""
        <div style="min-width:220px;max-width:260px;font-family:system-ui,-apple-system,Segoe UI,Roboto,Noto Sans,Arial">
          <div style="margin-bottom:6px">{badge_html}</div>
          <div style="font-size:12px;color:#555;margin-bottom:6px">{(caption or "").strip()}</div>
          {f'<img src="{payload["img_thumb"]}" style="width:100%;border-radius:8px;margin:6px 0;box-shadow:0 2px 8px rgba(0,0,0,.12)">' if payload["img_thumb"] else ""}
          <button style="width:100%;padding:8px 10px;border:none;border-radius:8px;background:#2563eb;color:#fff;font-weight:700;cursor:pointer"
            onclick='(function(btn){{window.openPanel(JSON.parse(btn.dataset.payload));}})(this)'
            data-payload='{payload_json}'
          >查看詳情</button>
        </div>
        """
        folium.Marker(
            [lat, lng],
            popup=preview_html,
            tooltip=f'{category or "未分類"}｜嚴重度{severity}',
            icon=Icon(color=color_name, icon="info-sign"),
        ).add_to(cluster)

    marker_layer.add_to(fmap)

    if heat_data:
        heat_layer = folium.FeatureGroup(name="熱度圖（依嚴重度加權）", show=False)
        HeatMap(
            heat_data, min_opacity=0.25, radius=22, blur=18, max_zoom=12,
            gradient={0.0:"#d4f4ff", 0.35:"#7ad3ff", 0.55:"#2ea3ff", 0.75:"#ff8a5c", 1.0:"#ff2d2d"}
        ).add_to(heat_layer)
        heat_layer.add_to(fmap)

    folium.LayerControl(collapsed=False, position="topright").add_to(fmap)

    panel_html = r"""
    <style>
      .rg-sidepanel { font-size: 15.5px; }
      .rg-sp-title  { font-size: 20px; }
      .rg-sp-meta   { font-size: 14.5px; }
      .rg-sp-caption{ font-size: 15.5px; }
      .rg-sp-time   { font-size: 13.5px; }

      .rg-sidepanel {
        position: absolute; left: 0; top: 0; height: 100%;
        width: min(560px, 48vw); background: #fff;
        transform: translateX(-105%); transition: transform .28s ease;
        z-index: 1000; box-shadow: 0 0 20px rgba(0,0,0,.15);
        display: flex; flex-direction: column;
      }
      .rg-sidepanel.open { transform: translateX(0); }

      .rg-sp-header { padding: 16px 18px; border-bottom: 1px solid #eee;
        display: flex; align-items: center; justify-content: space-between; }
      .rg-sp-close { border:none; background:#f3f4f6; border-radius:12px;
        padding:10px 12px; cursor:pointer; font-weight:800; }
      .rg-sp-body { padding: 14px 18px; overflow: auto; line-height: 1.6; }
      .rg-sp-meta{ display:grid; grid-template-columns: 1fr 1fr; gap:12px;
        margin:12px 0 14px; color:#374151; }
      .rg-sp-meta div{ background:#f9fafb; border:1px solid #eef2f7;
        border-radius:12px; padding:10px 12px; }
      .rg-sp-img{ width:100%; border-radius:16px;
        box-shadow:0 4px 18px rgba(0,0,0,.15); margin-bottom:12px; }
      .rg-sp-caption{ color:#111827; margin-bottom:8px; }
      .rg-sp-time{ color:#6b7280 }

      .rg-cat-badge{
        display:inline-flex; align-items:center; gap:8px; font-weight:800; margin-bottom:8px;
        background:#fff; border:1px solid #e5e7eb; border-radius:9999px; padding:4px 10px;
      }
      .rg-cat-dot{ width:10px; height:10px; border-radius:9999px; display:inline-block; }

      /* tabs */
      .rg-tabs{ margin-top:14px; }
      .rg-tab-buttons{ display:flex; gap:8px; border-bottom:1px solid #eee; }
      .rg-tab-btn{ padding:8px 12px; border:none; background:#f3f4f6; border-radius:10px 10px 0 0; cursor:pointer; font-weight:700; }
      .rg-tab-btn.active{ background:#fff; border:1px solid #e5e7eb; border-bottom:1px solid #fff; }
      .rg-tab-panel{ display:none; padding:12px 2px; }
      .rg-tab-panel.active{ display:block; }

      /* nearby gallery grid */
      .rg-nearby-grid{
        display:grid; grid-template-columns: repeat(3, 1fr); gap:10px;
      }
      .rg-nearby-card{
        border:2px solid #eef2f7; border-radius:12px; overflow:hidden; background:#fff; cursor:pointer;
      }
      .rg-nearby-card img{ width:100%; display:block; aspect-ratio:1/1; object-fit:cover; }
      .rg-nearby-meta{ font-size:12px; padding:6px 8px; color:#374151; }

      /* comments */
      .rg-comments-controls{ display:flex; align-items:center; gap:8px; margin-bottom:8px; }
      .rg-comments{ display:flex; flex-direction:column; gap:10px; }
      .rg-comment{ border:1px solid #eef2f7; border-radius:10px; padding:8px 10px; }
      .rg-comment small{ color:#6b7280; display:block; margin-bottom:2px; }
      .rg-cmt-actions{ display:flex; align-items:center; gap:10px; margin-top:6px; }
      .rg-like-btn{ border:none; background:#f3f4f6; border-radius:8px; padding:6px 10px; cursor:pointer; }
      .rg-like-btn[disabled]{ opacity:.6; cursor:not-allowed; }
      .rg-cmt-form{ display:grid; grid-template-columns: 1fr; gap:8px; margin-top:8px; }
      .rg-cmt-form input, .rg-cmt-form textarea{
        border:1px solid #e5e7eb; border-radius:8px; padding:8px 10px; font:inherit;
      }
      .rg-cmt-form button{
        border:none; background:#2563eb; color:#fff; border-radius:10px; padding:10px 12px; font-weight:800; cursor:pointer;
      }
      .rg-cmt-sort{ border:1px solid #e5e7eb; border-radius:8px; padding:6px 10px; font:inherit; }
    </style>

    <div id="rg-sidepanel" class="rg-sidepanel" aria-hidden="true">
      <div class="rg-sp-header">
        <div class="rg-sp-title">災情詳細資訊</div>
        <button class="rg-sp-close" onclick="window.closePanel()">收回 / 關閉</button>
      </div>
      <div class="rg-sp-body">
        <div id="rg-cat" class="rg-cat-badge" style="display:none">
          <i id="rg-cat-dot" class="rg-cat-dot"></i>
          <span id="rg-cat-text"></span>
        </div>
        <img id="rg-sp-img" class="rg-sp-img" alt="災情照片">
        <div id="rg-sp-caption" class="rg-sp-caption"></div>
        <div class="rg-sp-meta">
          <div><b>類別</b><br><span id="rg-sp-category"></span></div>
          <div><b>嚴重度</b><br><span id="rg-sp-severity"></span></div>
          <div><b>緯度</b><br><span id="rg-sp-lat"></span></div>
          <div><b>經度</b><br><span id="rg-sp-lng"></span></div>
        </div>
        <div class="rg-sp-time"><b>拍攝時間</b>：<span id="rg-sp-taken"></span></div>
        <div class="rg-sp-time"><b>上報時間</b>：<span id="rg-sp-reported"></span></div>

        <!-- Tabs -->
        <div class="rg-tabs">
          <div class="rg-tab-buttons">
            <button id="rg-tab-nearby-btn" class="rg-tab-btn active" onclick="window._rgSwitchTab('nearby')">附近災情</button>
            <button id="rg-tab-cmt-btn" class="rg-tab-btn" onclick="window._rgSwitchTab('comments')">留言區</button>
          </div>
          <div id="rg-tab-nearby" class="rg-tab-panel active">
            <div id="rg-nearby-grid" class="rg-nearby-grid"></div>
          </div>
          <div id="rg-tab-comments" class="rg-tab-panel">
            <div class="rg-comments-controls">
              <label for="rg-cmt-sort">排序：</label>
              <select id="rg-cmt-sort" class="rg-cmt-sort">
                <option value="time_desc">最新優先</option>
                <option value="likes_desc">讚數優先</option>
              </select>
            </div>
            <div id="rg-comments" class="rg-comments"></div>
            <div class="rg-cmt-form">
              <input id="rg-cmt-name" placeholder="暱稱（可留空）">
              <textarea id="rg-cmt-text" rows="3" placeholder="寫下你的留言..."></textarea>
              <button onclick="window._rgSubmitComment()">送出留言</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <script>
      (function(){
        const HOME_VIEW = {lat:23.7, lng:121.0, zoom:7};
        const NEARBY_LIMIT = 12;
        const NEARBY_RADIUS_KM = 25;

        const $=(s)=>document.querySelector(s);
        const panel=$('#rg-sidepanel');
        const elImg=$('#rg-sp-img'), elCaption=$('#rg-sp-caption');
        const elCat=$('#rg-sp-category'), elSev=$('#rg-sp-severity');
        const elLat=$('#rg-sp-lat'), elLng=$('#rg-sp-lng');
        const elTaken=$('#rg-sp-taken'), elReported=$('#rg-sp-reported');
        const nearbyGrid = $('#rg-nearby-grid');

        const catWrap = $('#rg-cat'), catDot = $('#rg-cat-dot'), catText = $('#rg-cat-text');

        const cmtList = $('#rg-comments');
        const cmtName = $('#rg-cmt-name');
        const cmtText = $('#rg-cmt-text');
        const cmtSortSel = $('#rg-cmt-sort');

        window.RG_DATA = window.RG_DATA || [];
        window.RG_CAT_HEX = window.RG_CAT_HEX || {};

        let currentId = null;
        let currentPoint = null;

        // Tabs
        window._rgSwitchTab = function(which){
          const nbBtn = $('#rg-tab-nearby-btn'), cBtn = $('#rg-tab-cmt-btn');
          const nb = $('#rg-tab-nearby'), cmt = $('#rg-tab-comments');
          if(which==='nearby'){
            nbBtn.classList.add('active'); cBtn.classList.remove('active');
            nb.classList.add('active'); cmt.classList.remove('active');
          }else{
            cBtn.classList.add('active'); nbBtn.classList.remove('active');
            cmt.classList.add('active'); nb.classList.remove('active');
          }
        };

        // 開關抽屜
        window.openPanel=function(p){
          currentId = p.id;
          currentPoint = p;

          if(p.img_large){elImg.src=p.img_large;elImg.style.display='block';}
          else if(p.img_thumb){elImg.src=p.img_thumb;elImg.style.display='block';}
          else{elImg.removeAttribute('src');elImg.style.display='none';}

          elCaption.textContent=p.caption||"";
          elCat.textContent=p.category||"未分類";
          elSev.textContent=p.severity||"";
          elLat.textContent=(typeof p.lat==="number")?p.lat.toFixed(6):"";
          elLng.textContent=(typeof p.lng==="number")?p.lng.toFixed(6):"";
          elTaken.textContent=p.taken_at||"—";
          elReported.textContent=p.reported_at||"—";

          // 類別徽章套色
          const hex = p.cat_hex || (window.RG_CAT_HEX[p.category]||"#6b7280");
          catDot.style.background = hex;
          catText.textContent = (p.category||"未分類") + "・嚴重度 " + (p.severity||"");
          catWrap.style.display = "inline-flex";

          renderNearby();
          // 讀取先前記住的排序
          const memoSort = localStorage.getItem(sortKey());
          if(memoSort){ cmtSortSel.value = memoSort; }
          renderComments();

          panel.classList.add('open');
        };
        window.closePanel=function(){panel.classList.remove('open');};

        // 計算距離
        function haversine(lat1,lng1,lat2,lng2){
          const R=6371.0088;
          const toRad=(d)=>d*Math.PI/180;
          const dphi=toRad(lat2-lat1), dl=toRad(lng2-lng1);
          const a=Math.sin(dphi/2)**2 + Math.cos(toRad(lat1))*Math.cos(toRad(lat2))*Math.sin(dl/2)**2;
          return R*2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a));
        }

        // 附近災情
        function renderNearby(){
          nearbyGrid.innerHTML = "";
          if(!currentPoint){ return; }
          const base = currentPoint;
          const withDist = window.RG_DATA
            .filter(x=>x.id!==base.id && typeof x.lat==="number" && typeof x.lng==="number")
            .map(x=>({ ...x, _dist: haversine(base.lat, base.lng, x.lat, x.lng) }));

          let inRadius = withDist.filter(x=>x._dist<=NEARBY_RADIUS_KM).sort((a,b)=>a._dist-b._dist);
          let picked = inRadius.slice(0, NEARBY_LIMIT);
          if(picked.length < NEARBY_LIMIT){
            const others = withDist.filter(x=>!inRadius.includes(x)).sort((a,b)=>a._dist-b._dist);
            picked = picked.concat(others.slice(0, NEARBY_LIMIT-picked.length));
          }

          picked.forEach(x=>{
            const card = document.createElement('div');
            card.className='rg-nearby-card';
            // 邊框套該類別顏色
            const hx = x.cat_hex || window.RG_CAT_HEX[x.category] || "#e5e7eb";
            card.style.borderColor = hx;
            card.title = (x.category||'') + ' · ' + (x.caption||'');
            card.onclick = ()=>{ openById(x.id, true); };

            const img = document.createElement('img');
            img.src = x.img_thumb || x.img_large || '';
            card.appendChild(img);

            const meta = document.createElement('div');
            meta.className='rg-nearby-meta';
            meta.textContent = `${(x.category||'')}${x._dist!=null?` · ${x._dist.toFixed(1)} km`:''}`;
            card.appendChild(meta);

            nearbyGrid.appendChild(card);
          });
        }

        // 依 ID 開啟（可飛過去）
        window.openById = function(id, fly){
          const p = window.RG_DATA.find(d=>d.id===id);
          if(!p) return;
          if(fly){
            const m = getLeafletMap();
            if(m){ m.flyTo([p.lat, p.lng], Math.max(m.getZoom(), 14), {animate:true, duration:0.8}); }
          }
          window.openPanel(p);
        };

        // ====== 留言（localStorage） + 按讚 + 排序 ======
        function commentsKey(){ return 'rg-comments-'+(currentId||''); }
        function likedKey(){ return 'rg-liked-'+(currentId||''); }
        function sortKey(){ return 'rg-cmt-sort-'+(currentId||''); }

        function getComments(){
          return JSON.parse(localStorage.getItem(commentsKey())||'[]');
        }
        function saveComments(arr){
          localStorage.setItem(commentsKey(), JSON.stringify(arr));
        }
        function getLikedMap(){
          return JSON.parse(localStorage.getItem(likedKey())||'{}');
        }
        function saveLikedMap(obj){
          localStorage.setItem(likedKey(), JSON.stringify(obj));
        }

        function renderComments(){
          cmtList.innerHTML='';
          let arr = getComments();
          // 排序
          const mode = cmtSortSel.value || 'time_desc';
          if(mode==='time_desc'){
            arr.sort((a,b)=> (b.ts||0)-(a.ts||0));
          }else{
            // 讚數優先 -> 由多到少，同讚數再以最新優先
            arr.sort((a,b)=> (b.likes||0)-(a.likes||0) || (b.ts||0)-(a.ts||0));
          }

          if(!arr.length){
            const empty = document.createElement('div');
            empty.textContent = '目前尚無留言，成為第一個留言的人吧！';
            empty.style.color = '#6b7280';
            cmtList.appendChild(empty);
            return;
          }

          const likedMap = getLikedMap();

          arr.forEach(c=>{
            // 兼容舊資料
            if(typeof c.likes!=='number') c.likes = 0;
            if(typeof c.id!=='number') c.id = c.ts || Date.now();

            const item = document.createElement('div');
            item.className='rg-comment';

            const meta = document.createElement('small');
            meta.textContent = `${c.name||'匿名'} · ${new Date(c.ts).toLocaleString()}`;
            const body = document.createElement('div');
            body.textContent = c.text;

            const actions = document.createElement('div');
            actions.className = 'rg-cmt-actions';

            const likeBtn = document.createElement('button');
            likeBtn.className = 'rg-like-btn';
            likeBtn.textContent = `👍 ${c.likes||0}`;
            likeBtn.dataset.cid = String(c.id);

            // 如果已按過讚則 disable
            if(likedMap[String(c.id)]){
              likeBtn.setAttribute('disabled','disabled');
            }

            likeBtn.addEventListener('click', ()=>{
              const cid = likeBtn.dataset.cid;
              const list = getComments();
              const idx = list.findIndex(x=>String(x.id)===cid);
              if(idx>=0){
                list[idx].likes = (list[idx].likes||0)+1;
                saveComments(list);
                const lm = getLikedMap(); lm[cid]=true; saveLikedMap(lm);
                likeBtn.textContent = `👍 ${list[idx].likes}`;
                likeBtn.setAttribute('disabled','disabled');
                // 若目前是「讚數優先」，重新渲染以反映排序改變
                if(cmtSortSel.value==='likes_desc'){ renderComments(); }
              }
            });

            actions.appendChild(likeBtn);

            item.appendChild(meta);
            item.appendChild(body);
            item.appendChild(actions);
            cmtList.appendChild(item);
          });
        }

        cmtSortSel.addEventListener('change', ()=>{
          localStorage.setItem(sortKey(), cmtSortSel.value);
          renderComments();
        });

        window._rgSubmitComment = function(){
          if(!currentId) return;
          const text = (cmtText.value||'').trim();
          const name = (cmtName.value||'').trim();
          if(!text){ alert('請輸入留言內容'); return; }
          const arr = getComments();
          const now = Date.now();
          arr.unshift({ id: now, name, text, ts: now, likes: 0 });
          saveComments(arr);
          cmtText.value='';
          renderComments();
        };

        // Leaflet Map & Home 控制
        function getLeafletMap(){
          for (const k in window){
            try{
              const v = window[k];
              if(v && v instanceof L.Map) return v;
            }catch(e){}
          }
          return null;
        }
        function addHomeControl(){
          const map = getLeafletMap();
          if(!map) return;
          if(map._rgHomeAdded) return;
          const Home = L.Control.extend({
            options:{position:'topright'},
            onAdd:function(){
              const c = L.DomUtil.create('div','leaflet-bar');
              const a = L.DomUtil.create('a','',c);
              a.innerHTML = '🏠';
              a.href = '#';
              a.title='回到台灣預設視角';
              a.style.fontSize='18px'; a.style.lineHeight='26px'; a.style.textAlign='center';
              L.DomEvent.on(a,'click', (e)=>{ L.DomEvent.stop(e); map.setView([HOME_VIEW.lat, HOME_VIEW.lng], HOME_VIEW.zoom); });
              return c;
            }
          });
          map.addControl(new Home());
          map._rgHomeAdded = true;
        }

        // 把縮放控制與比例尺移到右上
        function moveZoom(){
          const zoom=document.querySelector('.leaflet-control-zoom');
          const right=document.querySelector('.leaflet-top.leaflet-right');
          if(zoom && right && zoom.parentNode!==right){
            right.appendChild(zoom);
            zoom.style.margin='14px 14px 0 0';
          }
        }
        function moveScale(){
          const scale = document.querySelector('.leaflet-control-scale');
          const rightTop = document.querySelector('.leaflet-top.leaflet-right');
          if(scale && rightTop && scale.parentNode!==rightTop){
            rightTop.appendChild(scale);
            scale.style.margin='6px 14px 0 0';
          }
        }

        const id=setInterval(()=>{
          moveZoom();
          moveScale();
          addHomeControl();
          if(document.querySelector('.leaflet-control-zoom') && document.querySelector('.leaflet-control-scale')){
            clearInterval(id);
          }
        },150);

      })();
    </script>
    """

    # 將 all_points 與 類別色碼 注入到前端
    points_script = f"<script>window.RG_DATA = {json.dumps(all_points, ensure_ascii=False)}; window.RG_CAT_HEX = {json.dumps(CATEGORY_HEX, ensure_ascii=False)};</script>"

    fmap.get_root().html.add_child(folium.Element(panel_html))
    fmap.get_root().html.add_child(folium.Element(points_script))

    return fmap._repr_html_()

# ---------- Browser geolocation ----------
def js_get_location():
    return r"""
async () => {
  if (!navigator.geolocation) { alert("此瀏覽器不支援定位。"); return [null, null]; }
  try {
    const pos = await new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 8000 });
    });
    return [pos.coords.latitude, pos.coords.longitude];
  } catch (e) {
    alert("無法取得定位，請改用手動輸入。");
    return [null, null];
  }
}
"""

# ---------- Gradio UI ----------
def build_ui():

    FULLSCREEN_CSS = """
    /* 讓整體高度可用 */
    html, body, .gradio-container { height: 100%; }
    /* Map Tab 內的 HTML 元件容器 */
    #map_container {
      height: calc(100vh - 96px); /* 視窗高 - 上方標題與Tab的高度，可視覺微調 */
      padding: 0 !important;
      overflow: hidden;
    }
    /* Folium 會輸出一個外層包著 map 的 div，這裡把子元素也撐滿 */
    #map_container > * { height: 100%; }
    /* Folium 內部 map 本身設定為 100% 高度時，父層也必須是固定位高，這裡強化一下 */
    #map_container .folium-map { height: 100% !important; }
    /* 讓地圖頁不要因為父級的 margin/padding 造成額外空隙 */
    .gr-block { margin: 0; }
    """

    with gr.Blocks(css=FULLSCREEN_CSS) as demo:
        gr.Markdown("## 攏災影｜災情回報 Prototype（Python + Gradio）")

        with gr.Tab("地圖檢視"):
            map_html = gr.HTML(label=None, value=generate_map_html(), elem_id="map_container")
            gr.Button("重新載入地圖").click(lambda: generate_map_html(), None, map_html)

        with gr.Tab("附近災情串流"):
            with gr.Row():
                center_lat = gr.Number(label="中心緯度", value=23.5)
                center_lng = gr.Number(label="中心經度", value=121.0)
            with gr.Row():
                radius_km = gr.Slider(0, 50, value=10, step=1, label="半徑 (km) — 0 表示全部")
                sort_key = gr.Dropdown(choices=["distance","time_newest","time_taken_newest"], value="distance", label="排序")
            use_my_loc = gr.Button("以目前位置作為中心")
            gallery = gr.Gallery(label="災情照片（按距離先後）", show_label=True, columns=4, height=400)
            table = gr.Dataframe(headers=["距離(km)","類別","嚴重","描述","拍攝時間","上報時間","緯度","經度","ID"],
                                 datatype=["number","str","number","str","str","str","number","number","str"], interactive=False)
            refresh = gr.Button("重新整理")

            def refresh_feed(clat, clng, r_km, sortk):
                items = load_feed(clat, clng, r_km, sortk)
                gal, rows = [], []
                for (rid, caption, category, severity, image_path, thumb_path, lat, lng, taken_at, reported_at, dist) in items:
                    cap = f"{category} | {caption or ''}" + (f" | {dist:.2f} km" if dist is not None else "")
                    gal.append((thumb_path if os.path.exists(thumb_path) else image_path, cap))
                    rows.append([round(dist,2) if dist is not None else None, category, severity, caption or "", taken_at or "", reported_at or "", lat, lng, rid])
                return gal, rows

            refresh.click(refresh_feed, [center_lat, center_lng, radius_km, sort_key], [gallery, table])
            use_my_loc.click(fn=None, inputs=None, outputs=[center_lat, center_lng], js=js_get_location())

        with gr.Tab("上報"):
            with gr.Row():
                source_mode = gr.Radio(choices=["上傳照片", "鏡頭拍照"], value="上傳照片", label="來源")
            image_upload = gr.Image(label="選擇或拖曳照片", type="numpy", sources=["upload"], height=300)
            image_cam = gr.Image(label="拍照", type="numpy", sources=["webcam"], height=300, visible=False)

            def toggle_source(choice):
                return gr.update(visible=(choice=="上傳照片")), gr.update(visible=(choice=="鏡頭拍照"))
            source_mode.change(toggle_source, [source_mode], [image_upload, image_cam])

            with gr.Accordion("資訊", open=True):
                caption = gr.Textbox(label="描述（可選）", placeholder="例如：路面坍方，無法通行")
                category = gr.Dropdown(label="類別", choices=["土石流","淹水","道路受阻","建物損毀","其他"], value="其他")
                severity = gr.Slider(1,5,step=1, value=2, label="嚴重程度（1~5）")

                time_mode = gr.Radio(choices=["使用目前時間", "手動輸入"], value="使用目前時間", label="拍攝時間")
                taken_time_text = gr.Textbox(label="拍攝時間（ISO 8601）", placeholder="例如：2025-10-08T08:30:00Z", visible=False)
                time_mode.change(lambda tm: gr.update(visible=(tm=="手動輸入")), [time_mode], [taken_time_text])

                lat_mode = gr.Radio(choices=["手動輸入", "使用目前位置"], value="手動輸入", label="地點")
                with gr.Row():
                    manual_lat = gr.Textbox(label="緯度", placeholder="23.5")
                    manual_lng = gr.Textbox(label="經度", placeholder="121.0")
                current_lat = gr.Number(label="目前緯度（自動）", interactive=False, visible=False)
                current_lng = gr.Number(label="目前經度（自動）", interactive=False, visible=False)
                gr.Button("取得目前位置").click(fn=None, inputs=None, outputs=[current_lat, current_lng], js=js_get_location())
                lat_mode.change(lambda m: [gr.update(visible=(m=="手動輸入")), gr.update(visible=(m=="手動輸入"))],
                                [lat_mode], [manual_lat, manual_lng])

            submit = gr.Button("送出上報", variant="primary")
            status = gr.Markdown("")

            def on_submit(img_up, img_cam, src_mode, caption_v, cat_v, sev_v, tm_v, time_text, lm_v, man_lat, man_lng, cur_lat, cur_lng,
                          clat, clng, r_km, sortk):
                img = img_up if src_mode=="上傳照片" else img_cam
                if img is None: return "⚠️ 請先提供照片。", gr.update(), gr.update()
                pil_img = Image.fromarray(img)
                exif_time = exif_taken_at(pil_img)
                taken_at_iso = exif_time or (datetime.now(timezone.utc).isoformat() if tm_v=="使用目前時間" else (time_text or datetime.now(timezone.utc).isoformat()))
                if lm_v == "使用目前位置":
                    if cur_lat is None or cur_lng is None:
                        return "⚠️ 請先按「取得目前位置」或切換為手動輸入。", gr.update(), gr.update()
                    lat, lng = float(cur_lat), float(cur_lng)
                else:
                    try:
                        lat, lng = float(man_lat), float(man_lng)
                    except Exception:
                        return "⚠️ 請輸入有效的緯度/經度（小數）。", gr.update(), gr.update()
                img_path, thumb_path = save_image(pil_img)
                insert_report(caption_v or "", cat_v or "其他", int(sev_v or 1), img_path, thumb_path, lat, lng, taken_at_iso)

                items = load_feed(clat, clng, r_km, sortk)
                gal, rows = [], []
                for (rid, cap, category, severity, image_path, thumb_path, lt, lg, taken_at, reported_at, dist) in items:
                    title = f"{category} | {cap or ''}" + (f" | {dist:.2f} km" if dist is not None else "")
                    gal.append((thumb_path if os.path.exists(thumb_path) else image_path, title))
                    rows.append([round(dist,2) if dist is not None else None, category, severity, cap or "", taken_at or "", reported_at or "", lt, lg, rid])
                return "✅ 上傳成功！", gal, rows

            submit.click(on_submit,
                [image_upload, image_cam, source_mode, caption, category, severity, time_mode, taken_time_text,
                 lat_mode, manual_lat, manual_lng, current_lat, current_lng, center_lat, center_lng, radius_km, sort_key],
                [status, gallery, table]
            )
    return demo

if __name__ == "__main__":
    init_db()
    demo = build_ui()
    demo.launch()
