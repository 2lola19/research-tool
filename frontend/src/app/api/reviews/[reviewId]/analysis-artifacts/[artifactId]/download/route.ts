import { cookies } from "next/headers";

type DownloadRouteContext = {
  params: Promise<{ reviewId: string; artifactId: string }>;
};

export async function GET(_: Request, { params }: DownloadRouteContext) {
  const [{ reviewId, artifactId }, cookieStore] = await Promise.all([params, cookies()]);
  const accessToken = cookieStore.get("review_access_token")?.value;
  const organizationId = cookieStore.get("review_organization_id")?.value;
  if (!accessToken || !organizationId) {
    return Response.json({ error: "authentication_required" }, { status: 401 });
  }
  let response: Response;
  try {
    response = await fetch(
      `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api/v1/analysis/artifacts/${artifactId}/download?review_id=${encodeURIComponent(reviewId)}`,
      {
        cache: "no-store",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "X-Organization-ID": organizationId,
        },
      },
    );
  } catch {
    return Response.json({ error: "service_unavailable" }, { status: 503 });
  }
  if (!response.ok) {
    return Response.json({ error: "download_failed" }, { status: response.status });
  }
  return new Response(response.body, {
    status: 200,
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "image/svg+xml",
      "Content-Disposition": response.headers.get("content-disposition") ?? "attachment",
      "X-Content-SHA256": response.headers.get("x-content-sha256") ?? "",
      "Cache-Control": "private, no-store",
    },
  });
}
