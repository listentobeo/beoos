import { LegalPage } from "@/components/public/legal-page";

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms of Service"
      description="These terms describe the basic rules for using BeoOS as a business automation platform."
      sections={[
        {
          heading: "Service purpose",
          body: [
            "BeoOS provides business communication, inbox, CRM, quotation, pricing, AI drafting, and workflow automation tools for service businesses.",
            "The platform is intended for legitimate business use. Users must only connect accounts, phone numbers, inboxes, and business assets they own or are authorized to manage.",
          ],
        },
        {
          heading: "User responsibility",
          body: [
            "Users are responsible for the accuracy of business policies, pricing, inventory, customer replies, and quotations configured inside BeoOS.",
            "AI outputs are assistive drafts and recommendations. Users should review important messages, prices, legal commitments, and customer-facing promises before sending or publishing them.",
          ],
        },
        {
          heading: "Connected services",
          body: [
            "When users connect third-party services, they authorize BeoOS to access and process data needed to deliver the requested feature.",
            "Users must comply with the policies of connected services, including Meta, WhatsApp, Google, Zoho, and other communication platforms.",
          ],
        },
        {
          heading: "Availability and changes",
          body: [
            "We aim to keep BeoOS reliable and secure, but access may be interrupted for maintenance, provider outages, network issues, or platform changes.",
            "Features may change as the product improves, especially integrations that depend on third-party APIs and approval requirements.",
          ],
        },
      ]}
    />
  );
}
