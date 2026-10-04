import { StatusBar } from 'expo-status-bar';
import { StyleSheet, Text, View } from 'react-native';
import { designTokens as tokens } from '@fleet/shared';

export default function App() {
  return (
    <View style={styles.container}>
      <Text style={styles.label}>ỨNG DỤNG TÀI XẾ</Text>
      <Text style={styles.title} accessibilityRole="header">Giao hàng</Text>
      <Text style={styles.description}>Ứng dụng đang được chuẩn bị. Chuyến giao và chức năng cập nhật kết quả sẽ được bổ sung theo từng giai đoạn.</Text>
      <StatusBar style="auto" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: tokens.colors.neutral100,
    padding: tokens.spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  label: { color: tokens.colors.neutral600, fontSize: 14, lineHeight: 20, fontWeight: '600' },
  title: { color: tokens.colors.neutral950, fontSize: tokens.typography.mobile.pageTitle.size,
    lineHeight: tokens.typography.mobile.pageTitle.lineHeight, fontWeight: '600', marginVertical: tokens.spacing.xl },
  description: { color: tokens.colors.neutral600, fontSize: tokens.typography.mobile.body.size,
    lineHeight: tokens.typography.mobile.body.lineHeight, textAlign: 'center' },
});
