import { LegalPage } from "@/components/public/legal-page";

export default function DataDeletionPage() {
  return (
    <LegalPage
      title="Data Deletion Instructions"
      description="Users can request deletion of BeoOS account, business, and connected-channel data."
      sections={[
        {
          heading: "How to request deletion",
          body: [
            "Send an email to admin@beoarts.com using the email address connected to your BeoOS account. Include your name, business name, and the data you want deleted.",
            "You may request deletion of a full BeoOS account, a specific business workspace, connected mailbox data, WhatsApp connection data, CRM leads, quotes, pricing catalogue data, or AI policy settings.",
          ],
        },
        {
          heading: "What happens next",
          body: [
            "We will verify the request, confirm ownership or authorization, and process eligible deletion requests as soon as reasonably possible.",
            "Some records may be retained where required for security, fraud prevention, legal compliance, dispute resolution, or backup recovery windows.",
          ],
        },
        {
          heading: "Disconnecting integrations",
          body: [
            "Users can also disconnect third-party services from their provider accounts, such as Meta, Google, or Zoho. Disconnecting at the provider may stop future sync but does not automatically delete historical data already stored in BeoOS.",
          ],
        },
      ]}
    />
  );
}
