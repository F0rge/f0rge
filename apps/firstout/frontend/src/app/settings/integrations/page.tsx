import { Stack } from "@carbon/react";
import { AdminDirectoryLinks, AdminPageHeader } from "@/components/administration";
import { ADMIN_DESTINATIONS } from "@/lib/admin-navigation";

export default function IntegrationsPage() {
  const { label, description } = ADMIN_DESTINATIONS.integrations;
  return (
    <Stack gap={6}>
      <AdminPageHeader title={label} description={description} />
      <AdminDirectoryLinks items={["mcp"]} />
    </Stack>
  );
}
