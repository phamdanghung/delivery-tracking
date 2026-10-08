import { Tabs } from "expo-router";
export default function TabLayout() { return <Tabs screenOptions={{ headerShown: false }}><Tabs.Screen name="today" options={{ title: "Hôm nay" }}/><Tabs.Screen name="expenses" options={{ title: "Chi phí" }}/><Tabs.Screen name="account" options={{ title: "Tài khoản" }}/></Tabs>; }
