import { NextResponse } from "next/server";

const headers = {
  "Cache-Control": "no-store",
  "Referrer-Policy": "no-referrer",
  "X-Robots-Tag": "noindex, nofollow",
  "X-Content-Type-Options": "nosniff",
};
export async function GET(
  _: Request,
  context: { params: Promise<{ token: string }> },
) {
  const { token } = await context.params;
  if (!/^[A-Za-z0-9_-]{43}$/.test(token))
    return NextResponse.json(
      { detail: "Liên kết không còn hiệu lực" },
      { status: 410, headers },
    );
  try {
    const response = await fetch(
      `${process.env.API_URL || "http://127.0.0.1:8000"}/api/v1/public/tracking/${token}`,
      {
        cache: "no-store",
        signal: AbortSignal.timeout(12000),
        redirect: "error",
      },
    );
    // This anonymous proxy never forwards internal cookies, Authorization or client IP headers.
    if (!response.ok)
      return NextResponse.json(
        {
          detail:
            response.status === 410
              ? "Liên kết không còn hiệu lực"
              : "Chưa thể tải dữ liệu",
        },
        {
          status: [410, 429, 503].includes(response.status)
            ? response.status
            : 503,
          headers,
        },
      );
    return NextResponse.json(await response.json(), { headers });
  } catch {
    return NextResponse.json(
      { detail: "Chưa thể tải dữ liệu" },
      { status: 503, headers },
    );
  }
}
