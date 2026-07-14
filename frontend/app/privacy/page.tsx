import { LegalPage } from "@/components/public/legal-page";

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy Policy"
      description="This policy explains how BeoOS handles business communication data, connected channel data, and account information."
      sections={[
        {
          heading: "Information we process",
          body: [
            "BeoOS processes account details, business profile information, channel connection metadata, customer messages, form submissions, CRM leads, quotations, pricing data, and AI policy settings that users add to the platform.",
            "When a user connects third-party services such as email or WhatsApp, BeoOS processes only the data needed to provide inbox, lead, quotation, routing, and automation features for the connected business.",
          ],
        },
        {
          heading: "How information is used",
          body: [
            "We use data to authenticate users, display business dashboards, synchronize messages, classify customer requests, prepare draft replies, create leads, support quotations, and improve operational reliability.",
            "AI-generated outputs are used to assist business owners. Users remain responsible for reviewing policy-sensitive messages, quotes, commitments, and customer replies before use.",
          ],
        },
        {
          heading: "Third-party providers",
          body: [
            "BeoOS may use infrastructure and service providers including authentication, database, hosting, email, storage, AI, and messaging providers to operate the product.",
            "Connected platforms such as Meta, WhatsApp, Google, Zoho, and other services may apply their own terms and privacy policies when a user authorizes access.",
          ],
        },
        {
          heading: "Data retention and deletion",
          body: [
            "Business data is retained while the account or business workspace is active, unless a user requests deletion or disconnects a channel.",
            "Users can request deletion of account or business data by following the Data Deletion page instructions or contacting support.",
          ],
        },
      ]}
    />
  );
}
