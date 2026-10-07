import { Stack } from "expo-router";
import { DriverProvider } from "../driver/context";
export default function RootLayout() { return <DriverProvider><Stack><Stack.Screen name="(tabs)" options={{ headerShown: false }}/><Stack.Screen name="index" options={{ headerShown: false }}/><Stack.Screen name="stop/[id]" options={{ title: "Chi tiết điểm giao" }}/></Stack></DriverProvider>; }
