export async function GET() {
  return Response.json(
    { status: "healthy", service: "review-platform-frontend" },
    {
      headers: {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
      },
    },
  );
}
