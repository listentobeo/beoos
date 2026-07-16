import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-2xl border bg-white shadow-[0_1px_2px_rgba(16,24,39,0.03)]", className)} {...props} />;
}
