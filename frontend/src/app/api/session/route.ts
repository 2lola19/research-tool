import { NextResponse } from "next/server";

const accessTokenCookie = "review_access_token";
const organizationCookie = "review_organization_id";

function loginRedirect(request: Request, error: string): NextResponse {
  const url = new URL("/login", request.url);
  url.searchParams.set("error", error);
  return NextResponse.redirect(url, { status: 303 });
}

export async function POST(request: Request): Promise<NextResponse> {
  const form = await request.formData();
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  const organizationId = String(form.get("organization_id") ?? "").trim();
  if (!email || !password || !organizationId) {
    return loginRedirect(request, "missing_fields");
  }

  const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  try {
    const tokenResponse = await fetch(`${apiBaseUrl}/api/v1/auth/token`, {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!tokenResponse.ok) {
      return loginRedirect(request, "invalid_credentials");
    }
    const tokenPayload = (await tokenResponse.json()) as { access_token: string };
    const actorResponse = await fetch(`${apiBaseUrl}/api/v1/auth/me`, {
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${tokenPayload.access_token}`,
        "X-Organization-ID": organizationId,
      },
    });
    if (!actorResponse.ok) {
      return loginRedirect(request, "invalid_organization");
    }

    const response = NextResponse.redirect(new URL("/reviews", request.url), { status: 303 });
    const secure = process.env.NODE_ENV === "production";
    response.cookies.set(accessTokenCookie, tokenPayload.access_token, {
      httpOnly: true,
      maxAge: 3600,
      path: "/",
      sameSite: "lax",
      secure,
    });
    response.cookies.set(organizationCookie, organizationId, {
      httpOnly: true,
      maxAge: 3600,
      path: "/",
      sameSite: "lax",
      secure,
    });
    return response;
  } catch {
    return loginRedirect(request, "backend_unavailable");
  }
}
