import type { ReactNode } from "react";

import ReviewWorkspaceShell from "@/components/review-workspace-shell";

export default async function ReviewLayout({
  children,
  params,
}: Readonly<{ children: ReactNode; params: Promise<{ reviewId: string }> }>) {
  const { reviewId } = await params;
  return <ReviewWorkspaceShell reviewId={reviewId}>{children}</ReviewWorkspaceShell>;
}
