import type { Metadata } from "next";
import type { CSSProperties } from "react";
import { designTokens as tokens } from "@fleet/shared";
import "./globals.css";
export const metadata: Metadata = {
  title: "Quản lý xe giao hàng",
  description: "Hệ thống quản lý và định vị xe giao hàng",
};
export default function Layout({ children }: Readonly<{children: React.ReactNode}>) {
  const theme = {
    "--color-text": tokens.colors.neutral950,
    "--color-muted": tokens.colors.neutral600,
    "--color-border": tokens.colors.neutral300,
    "--color-background": tokens.colors.neutral100,
    "--color-surface": tokens.colors.surface,
    "--color-primary": tokens.colors.primary600,
    "--color-primary-soft": tokens.colors.primary50,
    "--radius-card": `${tokens.radius.card}px`,
    "--space-card": `${tokens.spacing.xl}px`,
    "--space-section": `${tokens.spacing.xxl}px`,
    "--font-page": `${tokens.typography.web.pageTitle.size}px`,
    "--line-page": `${tokens.typography.web.pageTitle.lineHeight}px`,
    "--font-section": `${tokens.typography.web.sectionTitle.size}px`,
    "--line-section": `${tokens.typography.web.sectionTitle.lineHeight}px`,
    "--font-body": `${tokens.typography.web.body.size}px`,
    "--line-body": `${tokens.typography.web.body.lineHeight}px`,
  } as CSSProperties;
  return <html lang="vi"><body style={theme}>{children}</body></html>;
}
