"use client";

// §0: Register / Log in are decorative stubs opening the placeholder modal.
// No fields submit anywhere; no session exists.

import {
  PlaceholderModalProvider,
  usePlaceholderModal,
} from "@/components/PlaceholderAuthModal";

function AccountInner() {
  const { open } = usePlaceholderModal();
  return (
    <main className="mx-auto max-w-md px-4 py-16">
      <div className="panel p-8 space-y-5 text-center">
        <div>
          <h1 className="font-mono text-sm uppercase tracking-widest text-ink-dim">
            Account
          </h1>
          <p className="text-sm text-ink-dim mt-3 leading-relaxed">
            Accounts aren&apos;t live yet — this will connect to a subscription
            service soon. Analyses, exports and share links work without one.
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <button className="btn-primary" onClick={() => open("account")}>
            Register
          </button>
          <button className="btn-ghost" onClick={() => open("account")}>
            Log in
          </button>
        </div>
        <p className="text-[11px] text-ink-faint">
          Your analysis history is stored in this browser — see{" "}
          <a href="/history" className="text-accent-transport">
            History
          </a>
          .
        </p>
      </div>
    </main>
  );
}

export default function AccountPage() {
  return (
    <PlaceholderModalProvider>
      <AccountInner />
    </PlaceholderModalProvider>
  );
}
