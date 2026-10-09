"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export function DataUnavailable({
  title = "This page could not load",
  message = "We could not retrieve the business data. Try again. If this continues, check the API deployment and your business access.",
}: {
  title?: string;
  message?: string;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return (
    <Card className="border-amber-200 bg-amber-50 p-5" role="alert">
      <h2 className="font-bold">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-[#5f655f]">{message}</p>
      <Button
        className="mt-4"
        variant="outline"
        disabled={pending}
        onClick={() => startTransition(() => router.refresh())}
      >
        {pending ? "Retrying…" : "Try again"}
      </Button>
    </Card>
  );
}
