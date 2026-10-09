import { NextRequest, NextResponse } from "next/server";
import { createHash } from "node:crypto";
import { sameOrigin } from "../origin";

const api = process.env.API_URL || "http://127.0.0.1:8000";
const routes =
  /^(auth\/(login|logout|me)|tracking-links(?:\/[0-9a-f-]+\/revoke)?|users(?:\/[0-9a-f-]+)?|vehicles(?:\/[0-9a-f-]+(?:\/(live|history|odometer))?)?|drivers(?:\/[0-9a-f-]+)?|gps\/devices|routing\/config|deliveries(?:\/[0-9a-f-]+(?:\/(status|reschedule|arrival-correction))?)?|trips(?:\/(config|[0-9a-f-]+(?:\/(optimize|optimization|approve))?))?)$/;
type Tokens = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
};
const refreshing = new Map<string, Promise<Tokens | undefined>>();
function renew(token: string): Promise<Tokens | undefined> {
  const key = createHash("sha256").update(token).digest("hex");
  const existing = refreshing.get(key);
  if (existing) return existing;
  const result = fetch(`${api}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: token }),
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  })
    .then(async (response) =>
      response.ok ? ((await response.json()) as Tokens) : undefined,
    )
    .finally(() => {
      setTimeout(() => refreshing.delete(key), 2000);
    });
  refreshing.set(key, result);
  return result;
}

async function handle(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const route = (await context.params).path.join("/");
  if (!routes.test(route))
    return NextResponse.json({ detail: "Không tìm thấy API" }, { status: 404 });
  if (
    request.method !== "GET" &&
    !sameOrigin(
      request.headers.get("origin"),
      request.nextUrl.protocol,
      request.headers.get("host"),
    )
  ) {
    return NextResponse.json(
      { detail: "Nguồn yêu cầu không hợp lệ" },
      { status: 403 },
    );
  }
  if (Number(request.headers.get("content-length") || 0) > 16384) {
    return NextResponse.json({ detail: "Yêu cầu quá lớn" }, { status: 413 });
  }
  let refresh = request.cookies.get("fleet_refresh")?.value;
  let access = request.cookies.get("fleet_access")?.value;
  let rotated: Tokens | undefined;
  const raw = request.method === "GET" ? undefined : await request.text();
  if (raw && raw.length > 16384)
    return NextResponse.json({ detail: "Yêu cầu quá lớn" }, { status: 413 });
  try {
    const invoke = (body?: string) =>
      fetch(`${api}/api/v1/${route}${request.nextUrl.search}`, {
        method: request.method,
        headers: {
          "Content-Type": "application/json",
          ...(access ? { Authorization: `Bearer ${access}` } : {}),
        },
        body,
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      });
    let upstream = await invoke(
      route === "auth/logout"
        ? JSON.stringify({ refresh_token: refresh || "" })
        : raw,
    );
    if (upstream.status === 401 && refresh && route !== "auth/login") {
      rotated = await renew(refresh);
      if (rotated) {
        access = rotated?.access_token;
        refresh = rotated.refresh_token;
        upstream = await invoke(
          route === "auth/logout"
            ? JSON.stringify({ refresh_token: refresh })
            : raw,
        );
      }
    }
    let value = upstream.status === 204 ? null : await upstream.json();
    if (route === "auth/login" && upstream.ok) {
      rotated = value;
      value = { user: value.user };
    }
    const response =
      upstream.status === 204
        ? new NextResponse(null, { status: 204 })
        : NextResponse.json(value, { status: upstream.status });
    response.headers.set("Cache-Control", "no-store");
    const options = {
      httpOnly: true,
      sameSite: "strict" as const,
      path: "/",
      secure: request.nextUrl.protocol === "https:",
    };
    if (rotated) {
      response.cookies.set("fleet_access", rotated.access_token, {
        ...options,
        maxAge: rotated.expires_in,
      });
      response.cookies.set("fleet_refresh", rotated.refresh_token, {
        ...options,
        maxAge: 604800,
      });
    }
    if (route === "auth/logout" || upstream.status === 401) {
      response.cookies.set("fleet_access", "", { ...options, maxAge: 0 });
      response.cookies.set("fleet_refresh", "", { ...options, maxAge: 0 });
    }
    return response;
  } catch {
    const response = NextResponse.json(
      { detail: "Không thể kết nối hệ thống. Vui lòng thử lại." },
      { status: 503 },
    );
    response.headers.set("Cache-Control", "no-store");
    if (route === "auth/logout") {
      for (const name of ["fleet_access", "fleet_refresh"])
        response.cookies.set(name, "", {
          httpOnly: true,
          sameSite: "strict",
          path: "/",
          maxAge: 0,
          secure: request.nextUrl.protocol === "https:",
        });
    }
    return response;
  }
}

export {
  handle as GET,
  handle as POST,
  handle as PUT,
  handle as PATCH,
  handle as DELETE,
};
