"use client";

import {
  BarChart3,
  BellRing,
  Bot,
  ClipboardList,
  FileText,
  MessagesSquare,
  Tags,
  UsersRound,
} from "lucide-react";
import {
  FloatingIconsHero,
  type FloatingIconsHeroProps,
} from "@/components/ui/floating-icons-hero-section";

const IconWhatsApp = (props: React.SVGProps<SVGSVGElement>) => (
  <svg {...props} viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle cx="12" cy="12" r="10" fill="#25D366" />
    <path
      fill="#fff"
      d="M16.9 14.5c-.2-.1-1.4-.7-1.6-.8-.2-.1-.4-.1-.6.1-.2.3-.7.8-.8.9-.1.2-.3.2-.5.1a6.4 6.4 0 0 1-1.9-1.2 7 7 0 0 1-1.3-1.7c-.1-.2 0-.4.1-.5l.4-.5c.1-.2.2-.3.3-.5.1-.2 0-.4 0-.5l-.7-1.6c-.2-.5-.4-.4-.6-.4h-.5c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.3 0 1.4 1 2.7 1.1 2.9.1.2 2 3.1 4.9 4.3 2.4 1 2.9.8 3.4.8.5-.1 1.4-.6 1.6-1.1.2-.6.2-1 .1-1.1-.1-.2-.3-.3-.6-.4Z"
    />
  </svg>
);

const IconGmail = (props: React.SVGProps<SVGSVGElement>) => (
  <svg {...props} viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M3 7.2A2.2 2.2 0 0 1 5.2 5h13.6A2.2 2.2 0 0 1 21 7.2v9.6a2.2 2.2 0 0 1-2.2 2.2H5.2A2.2 2.2 0 0 1 3 16.8V7.2Z" fill="#fff" />
    <path d="M5 7l7 5.2L19 7v10H5V7Z" fill="#EA4335" />
    <path d="M5 7l7 5.2L19 7" stroke="#fff" strokeWidth="2.4" strokeLinejoin="round" />
    <path d="M5 7v10" stroke="#34A853" strokeWidth="2.4" />
    <path d="M19 7v10" stroke="#4285F4" strokeWidth="2.4" />
    <path d="M5 7l7 5.2" stroke="#FBBC05" strokeWidth="2.4" />
  </svg>
);

const IconZoho = (props: React.SVGProps<SVGSVGElement>) => (
  <svg {...props} viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <rect x="2" y="6" width="5" height="8" rx="1.2" fill="#E42527" transform="rotate(-10 2 6)" />
    <rect x="7" y="4" width="5" height="8" rx="1.2" fill="#0E7A3B" transform="rotate(10 7 4)" />
    <rect x="12" y="6" width="5" height="8" rx="1.2" fill="#1473E6" transform="rotate(-8 12 6)" />
    <rect x="17" y="5" width="5" height="8" rx="1.2" fill="#FDBA12" transform="rotate(7 17 5)" />
    <text x="12" y="19.2" textAnchor="middle" fontSize="4.2" fontWeight="900" fill="#101827">ZOHO</text>
  </svg>
);

const iconClass = "text-[#101827]";

const icons: FloatingIconsHeroProps["icons"] = [
  { id: 1, icon: IconWhatsApp, className: "top-[14%] left-[7%]", label: "WhatsApp" },
  { id: 2, icon: IconGmail, className: "top-[18%] right-[8%]", label: "Gmail" },
  { id: 3, icon: IconZoho, className: "bottom-[15%] left-[9%]", label: "Zoho Mail" },
  { id: 4, icon: (props) => <FileText {...props} className={`${props.className ?? ""} ${iconClass}`} />, className: "bottom-[11%] right-[9%]", label: "Quotations" },
  { id: 5, icon: (props) => <UsersRound {...props} className={`${props.className ?? ""} text-blue-700`} />, className: "top-[8%] left-[28%]", label: "CRM" },
  { id: 6, icon: (props) => <Tags {...props} className={`${props.className ?? ""} text-[#ed633f]`} />, className: "top-[8%] right-[29%]", label: "Price catalogue" },
  { id: 7, icon: (props) => <ClipboardList {...props} className={`${props.className ?? ""} text-violet-700`} />, className: "bottom-[8%] left-[27%]", label: "Approvals" },
  { id: 8, icon: (props) => <BellRing {...props} className={`${props.className ?? ""} text-amber-700`} />, className: "top-[44%] left-[11%]", label: "Notifications" },
  { id: 9, icon: (props) => <BarChart3 {...props} className={`${props.className ?? ""} text-emerald-700`} />, className: "top-[74%] right-[24%]", label: "Analytics" },
  { id: 10, icon: (props) => <Bot {...props} className={`${props.className ?? ""} text-[#ed633f]`} />, className: "top-[31%] right-[18%]", label: "AI assistant" },
  { id: 11, icon: (props) => <MessagesSquare {...props} className={`${props.className ?? ""} text-slate-800`} />, className: "top-[57%] right-[6%]", label: "Unified inbox" },
  { id: 12, icon: (props) => <FileText {...props} className={`${props.className ?? ""} text-green-700`} />, className: "top-[61%] left-[29%]", label: "Website forms" },
];

export function BeoOSFloatingHero() {
  return (
    <FloatingIconsHero
      eyebrow="AI-powered business communication OS"
      title="Run sales, messages, leads, and quotes from one calm dashboard."
      subtitle="BeoOS connects WhatsApp, Gmail, Zoho Mail, website forms, CRM, pricing, quotations, approvals, and alerts so service businesses stop losing customers between tabs."
      ctaText="Create BeoOS account"
      ctaHref="/sign-up"
      secondaryCtaText="Sign in"
      secondaryCtaHref="/sign-in"
      icons={icons}
    />
  );
}
