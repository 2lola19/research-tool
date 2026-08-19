import type { ReactNode } from "react";
import Link from "next/link";

const navigation = [
  { key: "overview", label: "Overview", suffix: "" },
  { key: "screening", label: "Screening", suffix: "/screening" },
  { key: "search", label: "Search", suffix: "/search" },
  { key: "reports", label: "Reports", suffix: "/reports" },
  { key: "reporting", label: "Reproducibility", suffix: "/reporting" },
  { key: "quality", label: "Quality", suffix: "/risk-of-bias" },
  { key: "analysis", label: "Analysis", suffix: "/analysis" },
  { key: "ai", label: "Governed AI", suffix: "/ai" },
];

export default function ReviewWorkspaceShell({
  reviewId,
  children,
}: Readonly<{ reviewId: string; children: ReactNode }>) {
  return (
    <div className="min-h-screen">
      <a
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-3 focus:font-semibold focus:text-[var(--brand-deep)] focus:shadow-lg"
        href="#review-content"
      >
        Skip to review content
      </a>
      <header className="border-b border-[var(--line)] bg-white/90 backdrop-blur">
        <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center gap-4 px-6 py-4 sm:px-10 lg:px-14">
          <Link className="mr-auto text-sm font-semibold text-[var(--brand)] hover:underline" href="/reviews">
            &larr; Review projects
          </Link>
          <nav aria-label="Review workspace" className="order-3 w-full overflow-x-auto lg:order-2 lg:w-auto">
            <ul className="flex min-w-max gap-2 text-sm font-semibold text-[var(--muted)]">
              {navigation.map((item) => (
                <li key={item.key}>
                  <Link
                    className="inline-block rounded-full px-3 py-2 hover:bg-[#e7f1ec] hover:text-[var(--brand-deep)]"
                    href={`/reviews/${reviewId}${item.suffix}`}
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <form action="/api/session/logout" className="order-2 lg:order-3" method="post">
            <button
              className="rounded-full border border-[var(--line)] bg-white px-4 py-2 text-sm font-semibold hover:border-[var(--brand)]"
              type="submit"
            >
              Sign out
            </button>
          </form>
        </div>
      </header>
      <div id="review-content">{children}</div>
    </div>
  );
}
