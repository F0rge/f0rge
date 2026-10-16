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
      <h1 className="cds--type-productive-heading-04">Trading history</h1>
      <Tabs>
        <TabList aria-label="History">
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
