import { StatusBar } from 'expo-status-bar';
import { StyleSheet, Text, View } from 'react-native';

export default function App() {
  return (
    <View style={styles.container}>
      <Text style={styles.label}>ỨNG DỤNG TÀI XẾ</Text>
      <Text style={styles.title}>Giao hàng</Text>
      <Text style={styles.description}>Ứng dụng đang được chuẩn bị. Chuyến giao và chức năng cập nhật kết quả sẽ được bổ sung theo từng giai đoạn.</Text>
      <StatusBar style="auto" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f3f6fa',
    padding: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  label: { color: '#436489', fontSize: 12, fontWeight: '700', letterSpacing: 2 },
  title: { color: '#172b4d', fontSize: 36, fontWeight: '700', marginVertical: 20 },
  description: { color: '#52647c', fontSize: 17, lineHeight: 28, textAlign: 'center' },
});
