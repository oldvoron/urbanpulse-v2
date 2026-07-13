"use client";

// Brief §0: registration/auth/payments are PURE UI placeholders — no auth
// logic, no session. The one real thing here is the paid-plans email
// waitlist (Addendum 2 §10), which only writes an email to users.email.

import { createContext, useContext, useState } from "react";
import { API_URL } from "@/lib/api";

function WaitlistForm() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");

  const submit = async () => {
    if (!email.trim()) return;
    setState("busy");
    try {
      const res = await fetch(`${API_URL}/api/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      setState(res.ok ? "done" : "error");
    } catch {
      setState("error");
    }
  };

  if (state === "done")
    return (
      <p className="text-xs text-accent-nature font-mono text-center border-t border-edge pt-4">
        ✓ You&apos;re on the list — we&apos;ll email you when plans launch.
      </p>
    );
  return (
    <div className="border-t border-edge pt-4 space-y-2">
      <p className="text-xs text-ink-faint">
        Want to know when paid plans launch?
      </p>
      <div className="flex gap-2">
        <input
          className="input-dark !py-1.5 text-xs"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        <button
          className="btn-ghost !text-xs shrink-0"
          onClick={submit}
          disabled={state === "busy" || !email.trim()}
        >
          {state === "busy" ? "…" : "Notify me"}
        </button>
      </div>
      {state === "error" && (
        <p className="text-[10px] text-accent-risk font-mono">
          Something went wrong — check the address and try again.
        </p>
      )}
    </div>
  );
}

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
            <div className="mt-4">
              <WaitlistForm />
            </div>
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
