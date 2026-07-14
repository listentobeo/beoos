import { LegalPage } from "@/components/public/legal-page";

export default function CookiesPage() {
  return (
    <LegalPage
      title="Cookie Policy"
      description="This page explains how BeoOS may use cookies and similar technologies."
      sections={[
        {
          heading: "Essential cookies",
          body: [
            "BeoOS uses essential cookies and browser storage to support authentication, security, session management, and product functionality.",
            "These technologies help keep users signed in, protect accounts, and operate dashboard features.",
          ],
        },
        {
          heading: "Third-party services",
          body: [
            "Authentication and connected-service providers may use their own cookies or browser storage during login, authorization, and account connection flows.",
            "Examples include sign-in providers, Meta login, Google login, and other integration authorization pages.",
          ],
        },
        {
          heading: "User controls",
          body: [
            "Users can control cookies through their browser settings. Blocking essential cookies may prevent sign-in or connected features from working correctly.",
          ],
        },
      ]}
    />
  );
}
