import { Card } from "@/components/ui/card";

function SkeletonBlock({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-[#ebe8df] ${className}`} />;
}

export function InboxLoadingSkeleton() {
  return (
    <div className="mx-auto max-w-[1480px] px-4 py-5 sm:px-5 md:px-8 md:py-8">
      <header className="flex items-start justify-between gap-4">
        <div className="w-full max-w-lg">
          <SkeletonBlock className="h-3 w-32" />
          <SkeletonBlock className="mt-3 h-8 w-72" />
          <SkeletonBlock className="mt-3 h-4 w-56" />
        </div>
        <SkeletonBlock className="size-10 rounded-xl" />
      </header>

      <Card className="mt-6 p-4">
        <SkeletonBlock className="h-3 w-36" />
        <SkeletonBlock className="mt-3 h-5 w-64" />
        <SkeletonBlock className="mt-2 h-4 w-80 max-w-full" />
      </Card>

      <section className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, index) => (
          <Card key={index} className="flex items-center gap-4 p-4">
            <SkeletonBlock className="size-10 rounded-xl" />
            <div className="flex-1">
              <SkeletonBlock className="h-7 w-12" />
              <SkeletonBlock className="mt-2 h-3 w-24" />
            </div>
          </Card>
        ))}
      </section>

      <Card className="mt-6 overflow-hidden">
        <div className="flex flex-col gap-4 border-b px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <SkeletonBlock className="h-5 w-32" />
            <SkeletonBlock className="mt-2 h-3 w-64" />
          </div>
          <SkeletonBlock className="h-10 w-full sm:w-64" />
        </div>
        <div className="divide-y">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="grid grid-cols-[32px_1fr_auto] gap-3 px-5 py-4 md:grid-cols-[32px_180px_1fr_150px_100px] md:items-center">
              <SkeletonBlock className="mt-1 size-2 rounded-full md:mt-0" />
              <div className="hidden md:block">
                <SkeletonBlock className="h-4 w-32" />
                <SkeletonBlock className="mt-2 h-3 w-40" />
              </div>
              <div>
                <SkeletonBlock className="h-4 w-56 max-w-full" />
                <SkeletonBlock className="mt-2 h-3 w-32 md:hidden" />
              </div>
              <SkeletonBlock className="hidden h-6 w-20 md:block" />
              <SkeletonBlock className="h-4 w-16" />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

export function ThreadLoadingSkeleton() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 md:px-8">
      <SkeletonBlock className="h-4 w-28" />
      <header className="mt-5">
        <div className="flex gap-2">
          <SkeletonBlock className="h-6 w-20" />
          <SkeletonBlock className="h-6 w-28" />
        </div>
        <SkeletonBlock className="mt-4 h-9 w-3/4" />
        <SkeletonBlock className="mt-3 h-4 w-64" />
      </header>
      <div className="mt-7 grid gap-5 lg:grid-cols-[1fr_360px]">
        <section className="space-y-4">
          {Array.from({ length: 2 }).map((_, index) => (
            <Card key={index} className="overflow-hidden">
              <div className="border-b bg-[#fbfaf7] px-5 py-4">
                <SkeletonBlock className="h-4 w-44" />
                <SkeletonBlock className="mt-2 h-3 w-60" />
              </div>
              <div className="space-y-3 p-5">
                <SkeletonBlock className="h-4 w-full" />
                <SkeletonBlock className="h-4 w-11/12" />
                <SkeletonBlock className="h-4 w-8/12" />
              </div>
            </Card>
          ))}
        </section>
        <aside className="space-y-4">
          <Card className="space-y-3 p-5">
            <SkeletonBlock className="h-5 w-28" />
            <SkeletonBlock className="h-4 w-full" />
            <SkeletonBlock className="h-4 w-10/12" />
          </Card>
          <Card className="space-y-3 p-5">
            <SkeletonBlock className="h-5 w-24" />
            <SkeletonBlock className="h-4 w-full" />
            <SkeletonBlock className="h-4 w-9/12" />
          </Card>
        </aside>
      </div>
    </div>
  );
}
