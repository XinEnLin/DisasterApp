// 📦 匯入 React 與 Navigation 相關套件
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

// 📄 匯入各個頁面元件
import HomeScreen from '../screens/HomeScreen';
import MapScreen from '../screens/MapScreen';
import ReportScreen from '../screens/ReportScreen';

// 📘 定義 Stack Navigator 的頁面名稱與參數型別
// 若某頁面要傳參數，可在這裡定義（例如：Map: { lat: number; lng: number }）
export type RootStackParamList = {
  Home: undefined;   // 沒有參數
  Map: undefined;    // 沒有參數
  Report: undefined; // 沒有參數
};

// ⚙️ 建立 Stack Navigator 並附上型別
const Stack = createNativeStackNavigator<RootStackParamList>();

// 🧭 導覽主組件
export default function AppNavigator() {
  return (
    // NavigationContainer 是整個導覽系統的外層容器（必須有）
    <NavigationContainer>
      {/* Stack.Navigator 表示「堆疊式」的頁面導覽（像手機返回鍵那樣） */}
      <Stack.Navigator
        initialRouteName="Home" // App 啟動時先顯示的頁面
        screenOptions={{
          headerShown: true, // 顯示標題列
        }}
      >
        {/* 每個 Stack.Screen 對應一個頁面 */}
        <Stack.Screen
          name="Home"
          component={HomeScreen}
          options={{ title: '防災首頁' }} // 標題列文字
        />
        <Stack.Screen
          name="Map"
          component={MapScreen}
          options={{ title: '災情地圖' }}
        />
        <Stack.Screen
          name="Report"
          component={ReportScreen}
          options={{ title: '回報災情' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
