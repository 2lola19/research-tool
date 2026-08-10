import { NextResponse } from "next/server";

export async function POST(request: Request): Promise<NextResponse> {
  const response = NextResponse.redirect(new URL("/login", request.url), { status: 303 });
  response.cookies.delete("review_access_token");
  response.cookies.delete("review_organization_id");
  return response;
}
