"use client";

// Brief §0: registration/auth/payments are PURE UI placeholders. This modal
// is decorative — no form, no session, no backing logic of any kind.

import { createContext, useContext, useState } from "react";

type ModalKind = "account" | "upgrade" | null;

const ModalCtx = createContext<{ open: (k: Exclude<ModalKind, null>) => void }>({
  open: () => {},
});

export function usePlaceholderModal() {
  return useContext(ModalCtx);
}

export function PlaceholderModalProvider({ children }: { children: React.ReactNode }) {
  const [kind, setKind] = useState<ModalKind>(null);
  return (
    <ModalCtx.Provider value={{ open: setKind }}>
      {children}
      {kind && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
          onClick={() => setKind(null)}
        >
          <div
            className="panel max-w-md w-[92%] p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="font-mono text-xs uppercase tracking-widest text-accent-poi mb-3">
              {kind === "account" ? "Accounts" : "Plans & billing"}
            </div>
            <h2 className="text-lg font-semibold mb-2">
              {kind === "account" ? "Accounts aren't live yet" : "Paid plans aren't live yet"}
            </h2>
            <p className="text-sm text-ink-dim leading-relaxed">
              {kind === "account"
                ? "Registration and login will connect to a subscription service soon. Everything you see today is free to use without an account."
                : "Pricing tiers shown here are a preview. Checkout will be wired to a payment provider soon — for now, the full analysis toolkit is free."}
            </p>
            <button className="btn-primary mt-5 w-full" onClick={() => setKind(null)}>
              Got it
            </button>
          </div>
        </div>
      )}
    </ModalCtx.Provider>
  );
}

export function AuthButtons() {
  const { open } = usePlaceholderModal();
  return (
    <div className="flex items-center gap-2">
      <button className="btn-ghost" onClick={() => open("account")}>
        Log in
      </button>
      <button className="btn-primary !py-1.5" onClick={() => open("account")}>
        Register
      </button>
    </div>
  );
}

export function UpgradeButton({ label = "Upgrade" }: { label?: string }) {
  const { open } = usePlaceholderModal();
  return (
    <button className="btn-primary" onClick={() => open("upgrade")}>
      {label}
    </button>
  );
}
