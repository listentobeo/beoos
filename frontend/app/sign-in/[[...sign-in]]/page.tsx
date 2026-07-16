import { SignIn } from "@clerk/nextjs";

export const metadata = {
  robots: { index: false, follow: false },
};

export default function SignInPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-[#101827] p-6">
      <SignIn
        path="/sign-in"
        routing="path"
        signUpUrl="/sign-up"
        fallbackRedirectUrl="/dashboard/inbox"
      />
    </main>
  );
}
