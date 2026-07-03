import { Card } from "@/components/ui/card";

function Block({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-[#ebe8e1] ${className}`} />;
}

export default function DashboardLoading() {
  return (
    <div className="mx-auto max-w-[1480px] px-4 py-5 sm:px-5 md:px-8 md:py-8">
      <div className="flex items-start justify-between gap-4">
        <div className="w-full max-w-md">
          <Block className="h-3 w-32" />
          <Block className="mt-3 h-8 w-72 max-w-full" />
          <Block className="mt-3 h-4 w-56 max-w-full" />
        </div>
        <Block className="size-10 shrink-0" />
      </div>

      <section className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, index) => (
          <Card key={index} className="flex items-center gap-4 p-4">
            <Block className="size-10 shrink-0" />
            <div className="flex-1">
              <Block className="h-6 w-12" />
              <Block className="mt-2 h-3 w-24" />
            </div>
          </Card>
        ))}
      </section>

      <Card className="mt-6 overflow-hidden">
        <div className="flex flex-col gap-4 border-b px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <Block className="h-5 w-36" />
            <Block className="mt-2 h-3 w-52" />
          </div>
          <Block className="h-10 w-full sm:w-64" />
        </div>
        <div className="divide-y">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="grid grid-cols-[32px_1fr_auto] gap-3 px-5 py-4 md:grid-cols-[32px_180px_1fr_150px_100px] md:items-center">
              <Block className="mt-1 size-2 rounded-full md:mt-0" />
              <div className="hidden md:block">
                <Block className="h-4 w-32" />
                <Block className="mt-2 h-3 w-40" />
              </div>
              <div>
                <Block className="h-4 w-full max-w-md" />
                <Block className="mt-2 h-3 w-40 md:hidden" />
              </div>
              <Block className="hidden h-6 w-24 md:block" />
              <Block className="h-4 w-14" />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
