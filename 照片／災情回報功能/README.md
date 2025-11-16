# 攏災影｜災情回報系統 Disaster Report System (Gradio + Folium)

一個結合 **Gradio + Folium** 製作的互動式災情回報原型系統。  
使用者可即時上報災情照片與資訊，於地圖上顯示叢集標記與熱度圖，並查看附近災情、留言與按讚互動。  
本系統適合學術專題、校園展示、或防災應用原型開發。

---

## 🗺️ 系統特色 | Key Features

### 🌐 地圖互動 Map Interaction
- **右上角控制**：縮放鍵、比例尺、🏠 Home 按鈕（回台灣預設視角）  
- **Marker 叢集與熱度圖**：依災情嚴重度加權可切換顯示  
- **分類顏色**：不同災害類型以顏色區分  
  | 類別 | 地圖顏色 | 說明 |
  |------|-----------|------|
  | 土石流 | 🔴 Red | Landslide |
  | 淹水 | 🔵 Blue | Flood |
  | 道路受阻 | 🟠 Orange | Road Block |
  | 建物損毀 | 🟣 Purple | Building Damage |
  | 其他 | ⚫ Gray | Other / Unknown |

---

### 🧭 抽屜資訊 Drawer Panel
- 點擊 Marker → 開啟左側抽屜顯示詳細資訊  
- 上方類別徽章具對應顏色點  
- 內含兩個分頁（Tabs）：
  1. **附近災情 Nearby Reports**  
     - 以距離排序，顯示 12 張縮圖  
     - 點縮圖 → 飛到該點 + 開啟詳細資訊  
  2. **留言區 Comments Section**  
     - 支援留言與按讚 👍  
     - 可選擇排序方式：**最新優先 / 讚數優先**  
     - 所有留言存在本機瀏覽器 `localStorage`  

---

### 📸 災情上報 Disaster Report
- 支援「照片上傳」與「鏡頭拍照」
- 自動讀取 EXIF 拍攝時間（若無則使用目前時間）
- 可選擇「目前位置」或「手動輸入座標」
- 送出後自動更新地圖與災情串流

---

### 🧩 架構示意 | System Architecture

```text
┌─────────────────────────────────┐
│          使用者介面              │
│  Gradio Tabs: 地圖 / 串流 / 上報 │
└────────────┬────────────────────┘
             │
             ▼
┌────────────────────────────┐
│       Python 後端層         │
│ - Folium 生成互動地圖       │
│ - Gradio 控制介面與事件邏輯  │
│ - SQLite 儲存災情資料       │
│ - Pillow 處理圖片與 EXIF    │
└────────────┬───────────────┘
             │
             ▼
┌──────────────────────────────┐
│         前端互動層 (JS)       │
│ - Leaflet 控制地圖互動        │
│ - Drawer 抽屜與 Tabs 控制     │
│ - LocalStorage 留言與按讚系統 │
└──────────────────────────────┘
```

---

## 🗂️ 專案結構 Project Structure

```
project/
├─ app.py                 # 主程式
├─ requirements.txt
├─ README.md
├─ reports.db             # SQLite 資料庫（自動生成）
└─ uploads/
   ├─ <id>.jpg            # 原始災情照片
   └─ thumbs/
      └─ <id>_thumb.jpg   # 縮圖
```

---

## ⚙️ 安裝與執行 Installation

### 1️⃣ 建立虛擬環境
```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# 或 macOS/Linux:
# source .venv/bin/activate
```

### 2️⃣ 安裝依賴套件
```bash
pip install -r requirements.txt
```

### 3️⃣ 啟動服務
```bash
python app.py
```

瀏覽器開啟 [http://127.0.0.1:7860](http://127.0.0.1:7860) 即可使用。  
若想公開連線，改成：
```python
demo.launch(share=True)
```

---

## 📦 Requirements

```text
folium>=0.15.1
gradio>=4.36.0
Pillow>=10.0.0
numpy>=1.24.0
```

---

## 🧠 資料庫結構 Database Schema

表格：`reports`

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | TEXT | 主鍵 UUID |
| caption | TEXT | 描述 |
| category | TEXT | 類別 |
| severity | INT | 嚴重度 1–5 |
| image_path | TEXT | 原圖路徑 |
| thumb_path | TEXT | 縮圖路徑 |
| lat | REAL | 緯度 |
| lng | REAL | 經度 |
| taken_at | TEXT | 拍攝時間 ISO8601 |
| reported_at | TEXT | 上報時間 ISO8601 |

留言資料目前僅存在瀏覽器 `localStorage` 中，依照災情 ID 分開儲存：
```json
rg-comments-<report_id> : [{ "id":123, "name":"訪客", "text":"注意安全！", "ts":1730840000, "likes":3 }]
rg-liked-<report_id>    : {"123": true}
```

---

## 💡 常見問題 FAQ

| 問題 | 解決方式 |
|------|-----------|
| 地圖仍出現滾動條 | 調整 CSS `calc(100vh - 96px)` 數值 |
| 定位取不到 | 檢查瀏覽器權限或使用手動輸入 |
| 照片未顯示 | 檢查 `uploads/` 資料夾權限與磁碟空間 |
| Port 被占用 | 改成 `demo.launch(server_port=7861)` |
| 要清空資料 | 刪除 `reports.db` 與 `uploads/` |

---

## 🔧 可自訂參數 Configurations

| 名稱 | 位置 | 預設值 | 說明 |
|------|------|--------|------|
| HOME_VIEW | JS | `{lat:23.7, lng:121.0, zoom:7}` | Home 按鈕視角 |
| NEARBY_LIMIT | JS | `12` | 附近災情顯示數量 |
| NEARBY_RADIUS_KM | JS | `25` | 優先範圍（公里） |
| CATEGORY_COLORS / HEX | Python | 紅、藍、橘、紫、灰 | 類別顏色配置 |

---

## 🚀 未來可延伸方向 Future Extensions

- ✅ **留言資料庫化**：以 API / SQLite 儲存留言，加入防刷機制。  
- ✅ **帳號系統與角色權限**：分「管理員 / 一般用戶」。  
- ✅ **上傳審核與地圖過濾**：允許管理員核可災情顯示。  
- ✅ **外部資料圖層整合**：可疊加雨量、土石流潛勢區圖層。  
- ✅ **行動裝置優化與離線模式**。  

---

## 🧾 授權 License

此專案僅用於學術與展示用途，可自由修改、延伸與再利用。  
若用於正式公開或商業用途，請確認使用之地圖圖磚與外部資料來源的授權條款。
