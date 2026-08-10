import Link from "next/link";

type LoginPageProps = {
  searchParams: Promise<{ error?: string }>;
};

const errorMessages: Record<string, string> = {
  backend_unavailable: "The local API is unavailable. Start the backend and try again.",
  invalid_credentials: "The email or password is invalid.",
  invalid_organization: "That organization is unavailable for this account.",
  missing_fields: "Complete all three fields to continue.",
  session_expired: "Your local session expired. Sign in again.",
};

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const { error } = await searchParams;
  const message = error ? errorMessages[error] : undefined;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl items-center px-6 py-12 sm:px-10">
      <div className="grid w-full overflow-hidden rounded-3xl border border-[var(--line)] bg-white shadow-[0_28px_90px_rgb(20_35_28/10%)] lg:grid-cols-[0.9fr_1.1fr]">
        <section className="bg-[var(--brand-deep)] p-8 text-white sm:p-12">
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-[#9ed5c1]">
            Local workspace
          </p>
          <h1 className="mt-8 text-4xl font-semibold tracking-[-0.04em] sm:text-5xl">
            Enter the evidence workspace.
          </h1>
          <p className="mt-6 max-w-md leading-7 text-[#d7e9e1]">
            Authentication stays local during development. Your signed session token is kept in an
            HTTP-only cookie and every request is scoped to one organization.
          </p>
          <Link className="mt-10 inline-block text-sm font-semibold text-[#f2cc7a]" href="/">
            ← Back to platform overview
          </Link>
        </section>

        <section className="p-8 sm:p-12" aria-labelledby="login-heading">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--brand)]">
            Development sign in
          </p>
          <h2 id="login-heading" className="mt-3 text-3xl font-semibold tracking-[-0.03em]">
            Continue to review projects
          </h2>
          <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
            Use the owner credentials and organization ID printed by the local bootstrap command.
          </p>

          {message ? (
            <p
              className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
              role="alert"
            >
              {message}
            </p>
          ) : null}

          <form action="/api/session" className="mt-8 space-y-5" method="post">
            <label className="block text-sm font-semibold" htmlFor="email">
              Email
              <input
                autoComplete="username"
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[#fbfdfb] px-4 py-3 font-normal outline-none transition focus:border-[var(--brand)] focus:ring-2 focus:ring-[#1d6b5020]"
                id="email"
                name="email"
                required
                type="email"
              />
            </label>
            <label className="block text-sm font-semibold" htmlFor="password">
              Password
              <input
                autoComplete="current-password"
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[#fbfdfb] px-4 py-3 font-normal outline-none transition focus:border-[var(--brand)] focus:ring-2 focus:ring-[#1d6b5020]"
                id="password"
                name="password"
                required
                type="password"
              />
            </label>
            <label className="block text-sm font-semibold" htmlFor="organization_id">
              Organization ID
              <input
                className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[#fbfdfb] px-4 py-3 font-mono text-sm font-normal outline-none transition focus:border-[var(--brand)] focus:ring-2 focus:ring-[#1d6b5020]"
                id="organization_id"
                name="organization_id"
                required
                spellCheck={false}
                type="text"
              />
            </label>
            <button
              className="w-full rounded-xl bg-[var(--brand)] px-5 py-3.5 font-semibold text-white transition hover:bg-[var(--brand-deep)]"
              type="submit"
            >
              Sign in locally
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
