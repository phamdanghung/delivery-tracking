export const statusLabels: Record<string, string> = {
  CREATED: "Mới tạo",
  PLANNED: "Đã lên kế hoạch",
  ASSIGNED: "Đã phân",
  EN_ROUTE: "Đang đi giao",
  ARRIVED: "Đã đến",
  DELIVERING: "Đang bàn giao",
  DELIVERED: "Giao thành công",
  FAILED: "Giao thất bại",
  RESCHEDULED: "Hẹn giao lại",
  CANCELLED: "Đã hủy",
  DRAFT: "Chuyến nháp",
  ACTIVE: "Đang chạy",
};
export const commitmentLabels: Record<string, string> = {
  FIXED_TIME: "Giờ cố định",
  TIME_WINDOW: "Khung giờ",
  BEFORE_DEADLINE: "Trước một mốc",
};
export function zaloSuggestions(raw: string): Record<string, string> {
  const result: Record<string, string> = {};
  const names: Record<string, string> = {
    khách: "recipient_name",
    "khách hàng": "recipient_name",
    "người nhận": "recipient_name",
    sđt: "recipient_phone",
    "điện thoại": "recipient_phone",
    "địa chỉ": "address_text",
    "ghi chú": "notes",
  };
  for (const line of raw.split(/\r?\n/)) {
    const separator = line.indexOf(":");
    if (separator < 0) continue;
    const name =
      names[line.slice(0, separator).trim().toLocaleLowerCase("vi-VN")];
    const value = line.slice(separator + 1).trim();
    if (name && value) result[name] = value;
  }
  return result;
}
export function day(): string {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Bangkok" }).format(
    new Date(),
  );
}
export const localInput = (iso?: string | null) =>
  iso ? iso.slice(0, 19) : "";
export function datetimePayload(value: string): string | null {
  // Business timestamps are entered in company timezone, independently of browser timezone.
  return value ? `${value}:00+07:00` : null;
}
export function showTime(value?: string | null): string {
  return value
    ? new Date(value).toLocaleString("vi-VN", { timeZone: "Asia/Bangkok" })
    : "—";
}
