/** UX_UI_Design_Spec_V1.0/04_DESIGN_SYSTEM.md; presentation values only. */
export const designTokens = {
  colors: {
    primary600: "#0F6CBD", primary50: "#EFF6FF",
    neutral950: "#111827", neutral600: "#4B5563",
    neutral300: "#D1D5DB", neutral100: "#F3F4F6",
    success600: "#15803D", warning600: "#B45309",
    danger600: "#B91C1C", info600: "#0369A1", surface: "#FFFFFF",
  },
  spacing: {xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, xxxl: 40, section: 48},
  radius: {control: 8, card: 12, modal: 16},
  typography: {
    web: {pageTitle: {size: 24, lineHeight: 32}, sectionTitle: {size: 18, lineHeight: 28}, body: {size: 16, lineHeight: 24}},
    mobile: {pageTitle: {size: 22, lineHeight: 28}, cardTitle: {size: 17, lineHeight: 24}, body: {size: 16, lineHeight: 22}},
  },
  touch: {target: 44, primaryHeight: 48},
} as const;
