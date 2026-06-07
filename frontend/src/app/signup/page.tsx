import Link from "next/link";
import { SignupForm } from "@/components/auth/SignupForm";

export default function SignupPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <Link
          href="/"
          className="mb-8 block font-display text-2xl font-bold italic text-foreground"
        >
          CallLens
        </Link>

        <h1 className="mb-1 font-display text-2xl font-bold text-foreground">
          Set up your workspace
        </h1>
        <p className="mb-8 text-sm text-muted-foreground">
          Create your CallLens account. Only one account per installation.
        </p>

        <SignupForm />
      </div>
    </div>
  );
}
