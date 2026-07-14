import { PublicPageShell } from "@/components/public/site-shell";

export function LegalPage({
  title,
  description,
  sections,
}: {
  title: string;
  description: string;
  sections: Array<{ heading: string; body: string[] }>;
}) {
  return (
    <PublicPageShell>
      <section className="mx-auto max-w-3xl px-5 py-16">
        <p className="text-sm font-black uppercase tracking-[0.25em] text-[#ed633f]">
          BeoOS
        </p>
        <h1 className="mt-3 text-5xl font-black tracking-[-0.045em] text-[#101827]">
          {title}
        </h1>
        <p className="mt-5 text-lg leading-8 text-[#59605a]">{description}</p>
        <p className="mt-3 text-sm text-[#6f746f]">Last updated: July 14, 2026</p>

        <div className="mt-10 grid gap-6">
          {sections.map((section) => (
            <section key={section.heading} className="rounded-3xl border bg-white p-6">
              <h2 className="text-xl font-black">{section.heading}</h2>
              <div className="mt-3 grid gap-3 text-sm leading-7 text-[#59605a]">
                {section.body.map((paragraph) => (
                  <p key={paragraph}>{paragraph}</p>
                ))}
              </div>
            </section>
          ))}
        </div>
      </section>
    </PublicPageShell>
  );
}
