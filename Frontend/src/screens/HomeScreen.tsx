import React from 'react';
import { View, Text, Button } from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { RootStackParamList } from '../navigation/AppNavigator';

// 定義此頁面能用的 navigation props 型別
type Props = NativeStackScreenProps<RootStackParamList, 'Home'>;

export default function HomeScreen({ navigation }: Props) {
  return (
    <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
      <Text>🏠 防災首頁</Text>

      {/* 點擊按鈕導向「地圖頁」 */}
      <Button title="查看災情地圖" onPress={() => navigation.navigate('Map')} />

      {/* 點擊按鈕導向「回報頁」 */}
      <Button title="回報災情" onPress={() => navigation.navigate('Report')} />
    </View>
  );
}
