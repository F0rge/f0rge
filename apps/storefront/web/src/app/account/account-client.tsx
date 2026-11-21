"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useClerk, useUser } from "@clerk/nextjs";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@f0rge/ui";
import { TextInput } from "@f0rge/ui/forms";
import { useRouter } from "next/navigation";
import { useStorefrontAnalytics } from "@/components/analytics/analytics-provider";
import { OrderHistory } from "./order-history";
import { logoutCustomer } from "@/lib/customer-logout";

type Address = {
  id: string;
  first_name?: string | null;
  last_name?: string | null;
  address_1?: string | null;
  address_2?: string | null;
  city?: string | null;
  province?: string | null;
  postal_code?: string | null;
  phone?: string | null;
};
type AddressDraft = Omit<Address, "id">;
const blankAddress: AddressDraft = { first_name: "", last_name: "", address_1: "", address_2: "", city: "", province: "Gauteng", postal_code: "", phone: "" };

interface AccountClientProps {
  customer: { email: string; first_name: string; last_name: string };
}

export function AccountClient({ customer }: AccountClientProps) {
  const { signOut } = useClerk();
  const { user, isLoaded } = useUser();
  const router = useRouter();
  const { resetIdentity, identify } = useStorefrontAnalytics();
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [draft, setDraft] = useState<AddressDraft>(blankAddress);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadAddresses = useCallback(async () => {
    const response = await fetch("/api/account/addresses", { cache: "no-store" });
    const payload = await response.json() as { addresses?: Address[]; message?: string };
    if (!response.ok) throw new Error(payload.message || "Saved addresses are unavailable");
    setAddresses(payload.addresses || []);
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const response = await fetch("/api/account/session", { method: "POST", cache: "no-store" });
        const payload = await response.json() as { customer?: { id?: string }; message?: string };
        if (!response.ok) throw new Error(payload.message || "Your account could not be opened");
        if (payload.customer?.id) setCustomerId(payload.customer.id);
        await loadAddresses();
      } catch (reason) { setError(reason instanceof Error ? reason.message : "Your account could not be opened"); }
    })();
  }, [loadAddresses]);

  useEffect(() => {
    if (!customerId || !isLoaded) return;
    const createdAt = user?.createdAt ? new Date(user.createdAt).getTime() : 0;
    identify(customerId, { created: createdAt > 0 && Date.now() - createdAt < 10 * 60 * 1000 });
  }, [customerId, identify, isLoaded, user]);

  async function saveAddress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const response = await fetch(editingId ? `/api/account/addresses/${encodeURIComponent(editingId)}` : "/api/account/addresses", {
        method: "POST", headers: { "content-type": "application/json" }, cache: "no-store", body: JSON.stringify(draft),
      });
      const payload = await response.json() as { message?: string };
      if (!response.ok) throw new Error(payload.message || "Address could not be saved");
      setDraft(blankAddress); setEditingId(null); await loadAddresses();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Address could not be saved"); }
    finally { setBusy(false); }
  }

  async function removeAddress(id: string) {
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/account/addresses/${encodeURIComponent(id)}`, { method: "DELETE", cache: "no-store" });
      if (!response.ok) throw new Error("Address could not be removed");
      await loadAddresses();
    } catch { setError("Address could not be removed"); }
    finally { setBusy(false); }
  }

  async function logout() {
    setBusy(true); setError("");
    try {
      await logoutCustomer({ resetIdentity, signOut, refresh: () => router.refresh() });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not end your customer session"); setBusy(false); }
  }

  function edit(address: Address) {
    const fields = {
      first_name: address.first_name, last_name: address.last_name, address_1: address.address_1,
      address_2: address.address_2, city: address.city, province: address.province,
      postal_code: address.postal_code, phone: address.phone,
    };
    setDraft({ ...blankAddress, ...fields }); setEditingId(address.id); setError("");
  }

  // Mantine's unlayered button reset makes buttons inherit their font, so the action rows carry it.
  return <>
    <div className="mt-6 grid gap-6 lg:grid-cols-2 lg:items-start">
      <Card>
        <CardHeader>
          <CardDescription>Signed in</CardDescription>
          <CardTitle><h2 className="text-xl">{customer.first_name || customer.email}</h2></CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-muted-foreground">
          <p>{customer.email}</p>
          <p>Your bag remains attached to this account while you are signed in. Signing out clears this browser’s bag access.</p>
          <div className="text-sm font-medium text-foreground"><Button type="button" variant="outline" className="h-11 px-4" disabled={busy} onClick={() => void logout()}>Sign out</Button></div>
        </CardContent>
      </Card>
      <Card className="lg:row-span-2">
        <CardHeader><CardTitle><h2 className="text-xl">{editingId ? "Edit saved address" : "Save a delivery address"}</h2></CardTitle></CardHeader>
        <CardContent>
          {/* 16px inputs on phones so iOS does not zoom (Mantine reads --input-fz). */}
          <form className="grid gap-4 max-md:[--input-fz:1rem]" onSubmit={(event) => void saveAddress(event)}>
            <div className="grid gap-4 sm:grid-cols-2"><TextInput label="First name" required maxLength={100} autoComplete="given-name" value={draft.first_name || ""} onChange={(event) => setDraft({ ...draft, first_name: event.target.value })} /><TextInput label="Last name" required maxLength={100} autoComplete="family-name" value={draft.last_name || ""} onChange={(event) => setDraft({ ...draft, last_name: event.target.value })} /></div>
            <TextInput label="Street address" required maxLength={250} autoComplete="address-line1" value={draft.address_1 || ""} onChange={(event) => setDraft({ ...draft, address_1: event.target.value })} />
            <TextInput label="Suburb" maxLength={150} autoComplete="address-line2" value={draft.address_2 || ""} onChange={(event) => setDraft({ ...draft, address_2: event.target.value })} />
            <div className="grid gap-4 sm:grid-cols-2"><TextInput label="City" required maxLength={100} autoComplete="address-level2" value={draft.city || ""} onChange={(event) => setDraft({ ...draft, city: event.target.value })} /><TextInput label="Province" required maxLength={100} autoComplete="address-level1" value={draft.province || ""} onChange={(event) => setDraft({ ...draft, province: event.target.value })} /></div>
            <div className="grid gap-4 sm:grid-cols-2"><TextInput label="Postal code" required inputMode="numeric" pattern="[0-9]{4}" autoComplete="postal-code" value={draft.postal_code || ""} onChange={(event) => setDraft({ ...draft, postal_code: event.target.value })} /><TextInput label="Phone" maxLength={40} autoComplete="tel" value={draft.phone || ""} onChange={(event) => setDraft({ ...draft, phone: event.target.value })} /></div>
            <div className="flex flex-wrap gap-2 text-sm font-medium"><Button type="submit" className="h-11 px-4" disabled={busy}>{busy ? "Saving…" : editingId ? "Update address" : "Save address"}</Button>{editingId && <Button type="button" variant="outline" className="h-11 px-4" disabled={busy} onClick={() => { setDraft(blankAddress); setEditingId(null); }}>Cancel</Button>}</div>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle><h2 className="text-xl">Saved addresses</h2></CardTitle></CardHeader>
        <CardContent>
          {addresses.length === 0 ? <p className="text-muted-foreground">No saved addresses yet.</p> : <ul className="divide-y">{addresses.map((address) => <li className="space-y-1 py-4 first:pt-0" key={address.id}>
            <p className="font-medium">{address.first_name} {address.last_name}</p><p className="text-muted-foreground">{address.address_1}{address.address_2 ? `, ${address.address_2}` : ""}</p><p className="text-muted-foreground">{address.city}, {address.province} {address.postal_code}</p>
            <div className="flex flex-wrap gap-2 pt-2 text-sm font-medium"><Button type="button" variant="outline" className="h-11 px-4" disabled={busy} onClick={() => edit(address)}>Edit</Button><Button type="button" variant="outline" className="h-11 px-4" disabled={busy} onClick={() => void removeAddress(address.id)}>Remove</Button></div>
          </li>)}</ul>}
        </CardContent>
      </Card>
    </div>
    <OrderHistory />
    {error && <p role="alert" className="mt-6 rounded-lg border border-destructive p-4 text-sm text-destructive">{error}</p>}
  </>;
}
