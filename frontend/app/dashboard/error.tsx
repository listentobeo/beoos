"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Dashboard data could not load", error);
  }, [error]);
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-5 md:px-8">
      <Card className="p-6" role="alert">
        <h1 className="text-xl font-bold">This page could not load</h1>
        <p className="mt-2 text-sm leading-6 text-[#747973]">
          We could not retrieve the business data. Try again. If this continues, check the
          API deployment and your business access.
        </p>
        <Button className="mt-4" onClick={reset}>Try again</Button>
      </Card>
    </div>
  );
}
