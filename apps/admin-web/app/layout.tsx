import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Quản lý xe giao hàng",
  description: "Hệ thống quản lý và định vị xe giao hàng",
};
export default function Layout({ children }: Readonly<{children: React.ReactNode}>) {
  return <html lang="vi"><body>{children}</body></html>;
}
