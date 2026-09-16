import { expect, test } from "@playwright/test";

test("home renders the Stockroom hero", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Company software, built for humans." })).toBeVisible();
  await expect(page.getByRole("link", { name: "Create a company workspace" })).toBeVisible();
});

test("signup submit stays disabled until the form is valid", async ({ page }) => {
  await page.goto("/signup");
  const submit = page.getByRole("button", { name: /Create / });
  await expect(submit).toBeDisabled();

  await page.getByLabel(/Legal company name/).fill("Acme (Pty) Ltd");
  await page.getByLabel(/Your full name/).fill("Ada Owner");
  await page.getByLabel(/Work email/).fill("ada@acme.example");
  await page.getByLabel(/^Password/).fill("correct horse battery staple");
  await page.getByRole("checkbox").nth(0).check();
  await page.getByRole("checkbox").nth(1).check();
  await expect(page.getByRole("button", { name: /Create Acme/ })).toBeEnabled();
});

test("reserved slug vellano is rejected before submit", async ({ page }) => {
  await page.goto("/signup");
  const slug = page.getByLabel(/Workspace address/);
  await slug.fill("vellano");
  await expect(page.getByText("That address is reserved. Try another.")).toBeVisible();
  await expect(page.getByRole("button", { name: /Create your company/i })).toBeDisabled();
});
