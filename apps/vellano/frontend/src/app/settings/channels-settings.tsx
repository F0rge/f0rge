"use client";

import {
  Button,
  InlineNotification,
  Select,
  SelectItem,
  Stack,
  TextInput,
  Tile,
  Toggle,
} from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  canManageChannels,
  connectShopify,
  createChannelApiKey,
  drainChannelOutbox,
  getChannelConfig,
  isActiveLocation,
  listChannelApiKeys,
  listChannelListings,
  listChannelOutbox,
  listLocations,
  listSkus,
  revokeChannelApiKey,
  updateChannelSettings,
  upsertChannelListing,
  type ChannelApiKey,
  type ChannelApiKeyCreated,
  type ChannelAtpMode,
  type ChannelConfig,
  type ChannelListing,
  type ChannelLocationMap,
  type ChannelOutboxItem,
  type Location,
  type Sku,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const ATP_MODES: { value: ChannelAtpMode; label: string }[] = [
  { value: "warehouse_only", label: "Warehouse only" },
  { value: "pooled", label: "Pooled" },
  { value: "mapped", label: "Mapped per Shopify location" },
];

export function ChannelsSettings() {
  const { user } = useAuth();
  const canManage = canManageChannels(user);
  const [config, setConfig] = useState<ChannelConfig | null>(null);
  const [locations, setLocations] = useState<Location[]>([]);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [listings, setListings] = useState<ChannelListing[]>([]);
  const [keys, setKeys] = useState<ChannelApiKey[]>([]);
  const [outbox, setOutbox] = useState<ChannelOutboxItem[]>([]);
  const [atpMode, setAtpMode] = useState<ChannelAtpMode>("warehouse_only");
  const [atpLocationId, setAtpLocationId] = useState("");
  const [maps, setMaps] = useState<ChannelLocationMap[]>([]);
  const [shopDomain, setShopDomain] = useState("");
  const [adminToken, setAdminToken] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [shopifyEnabled, setShopifyEnabled] = useState(true);
  const [keyName, setKeyName] = useState("Ingest");
  const [createdToken, setCreatedToken] = useState<ChannelApiKeyCreated | null>(null);
  const [listingSkuId, setListingSkuId] = useState("");
  const [listingInventoryItemId, setListingInventoryItemId] = useState("");
  const [listingVariantId, setListingVariantId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextConfig, locationData, skuData, listingData] = await Promise.all([
        getChannelConfig(),
        listLocations(),
        listSkus(),
        listChannelListings(),
      ]);
      setConfig(nextConfig);
      setAtpMode(nextConfig.atp_mode);
      setAtpLocationId(nextConfig.atp_location_id ?? "");
      setMaps(nextConfig.maps);
      const shopify = nextConfig.channels.find((row) => row.slug === "shopify");
      setShopDomain(shopify?.shopify_shop_domain ?? "");
      setShopifyEnabled(shopify?.enabled ?? false);
      setLocations(locationData.filter(isActiveLocation));
      setSkus(skuData);
      setListings(listingData);
      if (canManage) {
        const [keyData, outboxData] = await Promise.all([
          listChannelApiKeys(),
          listChannelOutbox(),
        ]);
        setKeys(keyData);
        setOutbox(outboxData);
      }
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to load channel settings");
    } finally {
      setLoading(false);
    }
  }, [canManage]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleSaveAtp() {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await updateChannelSettings({
        atp_mode: atpMode,
        atp_location_id: atpLocationId || null,
        maps: maps.map((row) => ({
          location_id: row.location_id,
          shopify_location_gid: row.shopify_location_gid,
          include_in_atp: row.include_in_atp,
        })),
      });
      setConfig(updated);
      setMaps(updated.maps);
      setNotice("Channel ATP settings saved.");
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to save ATP settings");
    } finally {
      setSaving(false);
    }
  }

  async function handleConnectShopify() {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await connectShopify({
        shop_domain: shopDomain,
        admin_token: adminToken.trim() || undefined,
        webhook_secret: webhookSecret.trim() || undefined,
        enabled: shopifyEnabled,
      });
      setAdminToken("");
      setWebhookSecret("");
      setNotice("Shopify connection saved. Token fields are write-only.");
      await load();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to save Shopify connection");
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateKey() {
    setSaving(true);
    setError(null);
    try {
      const created = await createChannelApiKey(keyName.trim() || "Ingest");
      setCreatedToken(created);
      setNotice("Copy the API key now. It will not be shown again.");
      await load();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to create API key");
    } finally {
      setSaving(false);
    }
  }

  async function handleListing() {
    if (!listingSkuId) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await upsertChannelListing({
        sku_id: listingSkuId,
        external_inventory_item_id: listingInventoryItemId.trim() || undefined,
        external_variant_id: listingVariantId.trim() || undefined,
      });
      setNotice("Listing saved.");
      await load();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to save listing");
    } finally {
      setSaving(false);
    }
  }

  const coverage =
    config && config.sku_count > 0
      ? Math.round((config.listing_count / config.sku_count) * 100)
      : 0;
  const shopify = config?.channels.find((row) => row.slug === "shopify");

  return (
    <Tile>
      <Stack gap={5}>
        <div>
          <h2 className="cds--type-productive-heading-03">Channels</h2>
          <p className="cds--type-body-01 vellano-muted-text">
            Vellano is the inventory source of truth. Shopify inventory is a cache of available to
            promise. Connect a Partner dev store first — not the live DasKasas shop.
          </p>
        </div>
        {loading ? <p className="cds--type-body-01">Loading channels…</p> : null}
        {error ? (
          <InlineNotification kind="error" title="Channels" subtitle={error} hideCloseButton />
        ) : null}
        {notice ? (
          <InlineNotification kind="info" title="Channels" subtitle={notice} hideCloseButton />
        ) : null}
        {config ? (
          <>
            <p className="cds--type-body-01">
              Listing coverage {coverage}% ({config.listing_count} of {config.sku_count} SKUs).
              Outbox failures: {config.outbox_failed}.
            </p>
            <Select
              id="channel-atp-mode"
              labelText="ATP mode"
              value={atpMode}
              disabled={!canManage || saving}
              onChange={(event) => setAtpMode(event.target.value as ChannelAtpMode)}
            >
              {ATP_MODES.map((mode) => (
                <SelectItem key={mode.value} value={mode.value} text={mode.label} />
              ))}
            </Select>
            <Select
              id="channel-atp-location"
              labelText="Warehouse ATP location"
              value={atpLocationId}
              disabled={!canManage || saving}
              onChange={(event) => setAtpLocationId(event.target.value)}
            >
              <SelectItem value="" text="Default warehouse" />
              {locations
                .filter((location) => location.type === "warehouse")
                .map((location) => (
                  <SelectItem key={location.id} value={location.id} text={location.name} />
                ))}
            </Select>
            <Stack gap={3}>
              <p className="cds--label">Location maps</p>
              {maps.map((row, index) => (
                <div key={row.id} className="vellano-pick-priority-row">
                  <span>
                    {row.location_name} ({row.location_type})
                  </span>
                  <Toggle
                    id={`map-atp-${row.id}`}
                    labelText="Include in ATP"
                    hideLabel
                    toggled={row.include_in_atp}
                    disabled={!canManage || saving}
                    onToggle={(checked) =>
                      setMaps((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, include_in_atp: checked } : item,
                        ),
                      )
                    }
                  />
                  <TextInput
                    id={`map-gid-${row.id}`}
                    labelText="Shopify location GID"
                    hideLabel
                    value={row.shopify_location_gid ?? ""}
                    disabled={!canManage || saving}
                    onChange={(event) =>
                      setMaps((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index
                            ? { ...item, shopify_location_gid: event.target.value || null }
                            : item,
                        ),
                      )
                    }
                  />
                </div>
              ))}
            </Stack>
            {canManage ? (
              <Button kind="secondary" disabled={saving} onClick={() => void handleSaveAtp()}>
                Save ATP settings
              </Button>
            ) : (
              <InlineNotification
                kind="info"
                title="Read only"
                subtitle="Only the owner can change channel settings or rotate tokens."
                hideCloseButton
              />
            )}
            <TextInput
              id="shopify-domain"
              labelText="Shopify shop domain"
              helperText={
                shopify?.has_shopify_token ? "Admin token is set." : "No admin token stored."
              }
              value={shopDomain}
              disabled={!canManage || saving}
              onChange={(event) => setShopDomain(event.target.value)}
            />
            <TextInput
              id="shopify-token"
              labelText="Admin API token"
              type="password"
              value={adminToken}
              disabled={!canManage || saving}
              onChange={(event) => setAdminToken(event.target.value)}
            />
            <TextInput
              id="shopify-webhook-secret"
              labelText="Webhook secret"
              type="password"
              helperText={
                shopify?.has_webhook_secret ? "Webhook secret is set." : "No webhook secret stored."
              }
              value={webhookSecret}
              disabled={!canManage || saving}
              onChange={(event) => setWebhookSecret(event.target.value)}
            />
            <Toggle
              id="shopify-enabled"
              labelText="Shopify channel enabled"
              toggled={shopifyEnabled}
              disabled={!canManage || saving}
              onToggle={setShopifyEnabled}
            />
            {canManage ? (
              <Button kind="secondary" disabled={saving} onClick={() => void handleConnectShopify()}>
                Save Shopify connection
              </Button>
            ) : null}
            <Select
              id="listing-sku"
              labelText="Map SKU to Shopify inventory item"
              value={listingSkuId}
              disabled={!canManage || saving}
              onChange={(event) => setListingSkuId(event.target.value)}
            >
              <SelectItem value="" text="Select SKU" />
              {skus.map((sku) => (
                <SelectItem key={sku.id} value={sku.id} text={`${sku.our_ref} — ${sku.name}`} />
              ))}
            </Select>
            <TextInput
              id="listing-inventory-item"
              labelText="Shopify inventory_item_id"
              value={listingInventoryItemId}
              disabled={!canManage || saving}
              onChange={(event) => setListingInventoryItemId(event.target.value)}
            />
            <TextInput
              id="listing-variant"
              labelText="Shopify variant id (optional)"
              value={listingVariantId}
              disabled={!canManage || saving}
              onChange={(event) => setListingVariantId(event.target.value)}
            />
            {canManage ? (
              <Button kind="tertiary" disabled={saving || !listingSkuId} onClick={() => void handleListing()}>
                Save listing
              </Button>
            ) : null}
            <p className="cds--type-body-01">{listings.length} listings stored.</p>
            {canManage ? (
              <>
                <TextInput
                  id="channel-key-name"
                  labelText="API key name"
                  value={keyName}
                  disabled={saving}
                  onChange={(event) => setKeyName(event.target.value)}
                />
                <Button kind="tertiary" disabled={saving} onClick={() => void handleCreateKey()}>
                  Create ingest API key
                </Button>
                {createdToken ? (
                  <InlineNotification
                    kind="warning"
                    title="New API key"
                    subtitle={createdToken.token}
                    hideCloseButton
                  />
                ) : null}
                {keys.map((key) => (
                  <div key={key.id} className="vellano-pick-priority-row">
                    <span>
                      {key.name} ({key.key_prefix}…)
                      {key.revoked_at ? " — revoked" : ""}
                    </span>
                    {key.revoked_at ? null : (
                      <Button
                        kind="ghost"
                        size="sm"
                        disabled={saving}
                        onClick={() => void revokeChannelApiKey(key.id).then(() => load())}
                      >
                        Revoke
                      </Button>
                    )}
                  </div>
                ))}
                <Button
                  kind="ghost"
                  disabled={saving}
                  onClick={() => void drainChannelOutbox().then((result) => {
                    setNotice(`Drained ${result.processed} outbox jobs.`);
                    return load();
                  })}
                >
                  Drain outbox
                </Button>
                {outbox
                  .filter((row) => row.status === "failed")
                  .map((row) => (
                    <p key={row.id} className="cds--type-body-01">
                      Failed {row.kind}: {row.last_error}
                    </p>
                  ))}
              </>
            ) : null}
          </>
        ) : null}
      </Stack>
    </Tile>
  );
}
