import Link from "next/link";

const navLinks = [
  { href: "/#features", label: "Features" },
  { href: "/#pricing", label: "Pricing" },
  { href: "/#how-it-works", label: "How it works" },
  { href: "/about", label: "About" },
  { href: "/support", label: "Support" },
];

export function PublicHeader() {
  return (
    <header className="sticky top-0 z-30 border-b bg-[#f5f4f0]/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-4">
        <Link href="/" className="flex shrink-0 items-center gap-3" aria-label="BeoOS home">
          <span className="grid size-10 place-items-center rounded-2xl bg-[#ed633f] font-black text-white">
            B
          </span>
          <span>
            <span className="block text-lg font-black tracking-tight">BeoOS</span>
            <span className="block text-xs text-[#6f746f]">Business automation OS</span>
          </span>
        </Link>
        <nav className="hidden min-w-0 flex-1 items-center justify-center gap-6 text-sm font-semibold text-[#59605a] md:flex">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-label={`Go to ${link.label}`}
              className="whitespace-nowrap hover:text-[#ed633f]"
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="flex shrink-0 items-center gap-2">
          <Link
            href="/sign-in"
            className="rounded-full px-4 py-2 text-sm font-bold text-[#101827] hover:bg-white"
          >
            Sign in
          </Link>
          <Link
            href="/sign-up"
            className="rounded-full bg-[#101827] px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-[#1c2638]"
          >
            Get started
          </Link>
        </div>
      </div>
    </header>
  );
}

export function PublicFooter() {
  return (
    <footer className="border-t bg-white">
      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-10 md:grid-cols-[1.4fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-2xl bg-[#ed633f] font-black text-white">
              B
            </span>
            <div>
              <p className="font-black">BeoOS</p>
              <p className="text-sm text-[#6f746f]">AI communication and sales automation.</p>
            </div>
          </div>
          <p className="mt-4 max-w-md text-sm leading-6 text-[#6f746f]">
            BeoOS helps brick-and-mortar service businesses manage leads, customer messages,
            quotations, approvals, pricing, and follow-up workflows from one secure dashboard.
          </p>
          <p className="mt-3 text-sm font-semibold text-[#59605a]">
            Support:{" "}
            <a className="text-[#ed633f]" href="mailto:support@beoos.com.ng">
              support@beoos.com.ng
            </a>
          </p>
        </div>
        <div>
          <p className="font-bold">Product</p>
          <div className="mt-3 grid gap-2 text-sm text-[#6f746f]">
            <Link href="/#features">Features</Link>
            <Link href="/#pricing">Pricing</Link>
            <Link href="/#how-it-works">How it works</Link>
            <Link href="/sign-up">Create account</Link>
          </div>
        </div>
        <div>
          <p className="font-bold">Company</p>
          <div className="mt-3 grid gap-2 text-sm text-[#6f746f]">
            <Link href="/about">About</Link>
            <Link href="/support">Support</Link>
            <Link href="/privacy">Privacy Policy</Link>
            <Link href="/terms">Terms of Service</Link>
            <Link href="/data-deletion">Data Deletion</Link>
            <Link href="/cookies">Cookie Policy</Link>
          </div>
        </div>
      </div>
      <div className="border-t px-5 py-4 text-center text-xs text-[#6f746f]">
        © {new Date().getFullYear()} BeoOS. Built for business communication automation.
      </div>
    </footer>
  );
}

export function PublicPageShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen">
      <PublicHeader />
      {children}
      <PublicFooter />
    </main>
  );
}
