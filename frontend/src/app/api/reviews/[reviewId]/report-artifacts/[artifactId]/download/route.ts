import { cookies } from "next/headers";
import { NextResponse } from "next/server";

type Context = { params: Promise<{ reviewId: string; artifactId: string }> };

export async function GET(_request: Request, context: Context) {
  const [{ reviewId, artifactId }, cookieStore] = await Promise.all([context.params, cookies()]);
  const token = cookieStore.get("review_access_token")?.value;
  const organizationId = cookieStore.get("review_organization_id")?.value;
  if (!token || !organizationId) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  const response = await fetch(`${process.env.API_BASE_URL ?? "http://localhost:8000"}/api/v1/reporting/artifacts/${artifactId}/download?review_id=${reviewId}`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${token}`, "X-Organization-ID": organizationId },
  });
  return new NextResponse(response.body, { status: response.status, headers: response.headers });
}

