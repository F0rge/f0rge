"use client";

import { Stack, Tab, TabList, TabPanel, TabPanels, Tabs } from "@carbon/react";

import {
  PurchaseHistoryTable,
  SalesHistoryTable,
  SupplierPricesTable,
} from "@/components/records/history-tables";

export default function HistoryPage() {
  return (
    <Stack gap={6}>
      <h1 className="cds--type-productive-heading-04">Archive</h1>
      <p className="cds--type-body-01">The old Cin7 records: past sales, purchases and supplier prices.</p>
      <Tabs>
        <TabList aria-label="Archive">
          <Tab>Sales</Tab>
          <Tab>Purchases</Tab>
          <Tab>Supplier prices</Tab>
        </TabList>
        <TabPanels>
          <TabPanel>
            <SalesHistoryTable />
          </TabPanel>
          <TabPanel>
            <PurchaseHistoryTable />
          </TabPanel>
          <TabPanel>
            <SupplierPricesTable />
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Stack>
  );
}
