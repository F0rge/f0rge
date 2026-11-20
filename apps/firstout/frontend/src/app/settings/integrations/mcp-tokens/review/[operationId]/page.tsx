import Link from "next/link";

import { AdminPageHeader } from "@/components/administration";

export default function RetiredMcpReviewPage() {
  return (
    <AdminPageHeader
      title="Transfer approval link retired"
      description="Connected assistants now apply transfer changes using your Firstout permissions. Check the transfer’s current status before asking your assistant to run an action."
    >
      <Link className="cds--link" href="/transfers">Open transfers</Link>
    </AdminPageHeader>
  );
}
