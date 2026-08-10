import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-6">
      <p className="text-sm font-semibold uppercase tracking-widest text-[var(--brand)]">404</p>
      <h1 className="mt-3 text-4xl font-semibold">This workspace page does not exist.</h1>
      <Link className="mt-6 font-semibold text-[var(--brand)] underline" href="/">
        Return to the foundation dashboard
      </Link>
    </main>
  );
}
