

# 攏災影防災app

> 一款以 **React Native CLI + TypeScript** 開發的防災應用程式前端專案，  
> 結合 IoT 資料與即時災害資訊，協助使用者在災害發生時快速反應、查詢與避難。

---

## 📱 專案簡介

本專案為 **防災應用系統的前端 App**，以 React Native CLI 建立，  
並計畫與後端 **Python Flask** 伺服器串接。  
使用者可透過 App 進行：

- 🌧️ 即時災情查詢與視覺化呈現  
- 🗺️ 災害地圖與避難地點導航  
- 🧭 緊急通報與家庭群組定位  
- 📊 感測裝置（IoT）資料顯示（溫度、濕度、CO₂、PM2.5等）  

---

## 🏗️ 技術架構

| 分層 | 技術 |
|:--|:--|
| **前端 App** | React Native CLI (TypeScript) |
| **頁面導航** | React Navigation |
| **狀態管理** | React Hooks / Context API |
| **開發工具** | Android Studio + Metro Bundler |
| **後端（規劃中）** | Flask REST API (Python) |
| **資料庫（規劃中）** | MongoDB / PostgreSQL |

---

## 📦 專案結構

```

Frontend/
├─ android/                # Android 原生專案設定
├─ ios/                    # iOS 原生專案設定（可選）
├─ src/                    # App 主程式碼
│   ├─ screens/            # 畫面組件
│   ├─ components/         # 可重用 UI 元件
│   ├─ navigation/         # 導航設定
│   └─ assets/             # 圖示、圖片資源
├─ App.tsx                 # 入口檔案
├─ package.json            # 專案依賴與指令
└─ tsconfig.json           # TypeScript 設定

````

---

## 🚀 開發環境設定

### 1️⃣ 安裝依賴
```bash
npm install
````

### 2️⃣ 啟動 Metro Bundler

```bash
npx react-native start
```

### 3️⃣ 執行 Android 模擬器

```bash
npx react-native run-android
```

> ⚠️ 若遇到建置錯誤，可先執行：
>
> ```bash
> cd android
> gradlew clean
> cd ..
> ```

---

## 🧩 主要依賴

| 套件                               | 功能說明        |
| :------------------------------- | :---------- |
| `react-native`                   | 核心框架        |
| `react-navigation`               | 頁面導航        |
| `@react-navigation/native-stack` | Stack 式導覽架構 |
| `react-native-safe-area-context` | 安全顯示區域控制    |
| `typescript`                     | 型別安全開發      |
| `eslint`                         | 程式風格檢查      |

---

## ⚙️ 開發注意事項

* 建議 Node.js 版本： **v18+**
* Android SDK： **API 33 (Android 13)** 以上
* JDK： **Java 17**
* 已啟用 Windows 長路徑支援（LongPathsEnabled）
* 若遇 CMake 錯誤，可調整 `android/gradle.properties` 中的暫存路徑

---

## 🧠 專案目標

此應用將整合：

* IoT 感測資料（Raspberry Pi Pico W / ESP32）
* 災情分析模型（AI/ML 預測）
* 行動端即時通知與家庭群組協作機制

最終期望打造一個能在災害現場「即時反應 + 團隊協作」的智慧防災平台。

---

## 👥 開發團隊

| 成員  | 角色                      |
| :-- | :---------------------- |


---

## 📄 授權條款

本專案採用 [MIT License](./LICENSE)。

---

## ⭐ 未來功能規劃

* [ ] IoT 感測器資料上傳整合
* [ ] 災害預測 AI 模型接入 (Flask API)
* [ ] 災情地圖與避難所顯示
* [ ] 離線模式 + 資料快取
* [ ] 推播通知與家庭群組定位
