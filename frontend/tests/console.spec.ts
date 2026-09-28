import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const password = "browser-fixture-password-2026";
async function login(page: Page, email = "admin@example.com") {
  await page.goto("/login");
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Your workspaces" }),
  ).toBeVisible();
}
async function workspace(page: Page, name: string) {
  await page.getByRole("button", { name: "New workspace" }).click();
  await page.getByLabel("Workspace name").fill(name);
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}
async function knowledge(page: Page) {
  await page
    .getByRole("link", { name: "Knowledge bases", exact: true })
    .click();
  await page.getByRole("button", { name: "New knowledge base" }).click();
  await page.getByLabel("Knowledge base name").fill("Employee handbook");
  await page
    .getByRole("button", { name: "Create knowledge base", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Employee handbook", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Choose document").setInputFiles({
    name: "travel-policy.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "The daily meal allowance is 75 dollars. Receipts are required for expenses over 25 dollars.",
    ),
  });
  await page
    .getByRole("button", { name: "Upload document", exact: true })
    .click();
  await expect(page.getByText("ready", { exact: true })).toBeVisible();
}
test("ingestion, grounded query, source inspection and saved trace", async ({
  page,
}) => {
  await login(page);
  await workspace(page, "Meridian research");
  await knowledge(page);
  await page.getByRole("button", { name: "Inspect chunks" }).click();
  await expect(
    page
      .getByText("The daily meal allowance is 75 dollars.", { exact: false })
      .last(),
  ).toBeVisible();
  await page.getByRole("link", { name: "Playground", exact: true }).click();
  await page
    .getByLabel("Question", { exact: true })
    .fill("What is the daily meal allowance?");
  await page.getByRole("button", { name: "Ask question" }).click();
  await expect(page.getByTestId("answer")).toContainText("75 dollars");
  await page.getByRole("button", { name: "View citation 1" }).click();
  await expect(
    page.getByRole("heading", { name: "Source evidence" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Download source" }),
  ).toHaveAttribute("href", /\/api\/documents\/.+\/download/);
  await expect(
    page.getByText("Unknown", { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/playground.png",
    fullPage: true,
  });
  await expect(
    new AxeBuilder({ page }).analyze().then((r) => r.violations),
  ).resolves.toEqual([]);
  await page.reload();
  await page
    .getByRole("button", { name: "What is the daily meal allowance?" })
    .click();
  await expect(page.getByTestId("answer")).toContainText("75 dollars");
  await page
    .getByLabel("Question", { exact: true })
    .fill("What is the moon policy?");
  await page.getByRole("button", { name: "Ask question" }).click();
  await expect(page.getByTestId("answer")).toContainText("No evidence");
});
test("mobile workspace navigation remains accessible", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await workspace(page, "Mobile research");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("link", { name: "Knowledge bases", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Knowledge bases", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Compare runs", exact: true }),
  ).not.toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await expect(
    new AxeBuilder({ page }).analyze().then((r) => r.violations),
  ).resolves.toEqual([]);
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
});

test("versioned cases, immutable semantic runs and honest comparison coverage", async ({
  page,
}) => {
  await login(page);
  await workspace(page, "Evaluation research");
  await knowledge(page);
  await page.getByRole("link", { name: "Evaluations", exact: true }).click();
  await page.getByRole("button", { name: "New dataset", exact: true }).click();
  await page.getByLabel("Dataset name").fill("Travel reference cases");
  await page
    .getByRole("button", { name: "Create dataset", exact: true })
    .click();
  await page.getByRole("button", { name: "Add case", exact: true }).click();
  await page
    .getByLabel("Question 1", { exact: true })
    .fill("What is the daily meal allowance?");
  await page
    .getByLabel("Reference answer", { exact: true })
    .fill("The daily meal allowance is 75 dollars.");
  await page.getByLabel("Expected outcome").selectOption("answer");
  await page.getByLabel("Tags", { exact: true }).fill("travel, policy");
  await page.getByRole("button", { name: "Add case", exact: true }).click();
  await page
    .getByLabel("Question 2", { exact: true })
    .fill("What is the moon policy?");
  await page.getByLabel("Expected outcome").nth(1).selectOption("abstain");
  await page.getByRole("button", { name: "Save dataset", exact: true }).click();
  await expect(page.getByText("REFERENCE DATASET · VERSION 2")).toBeVisible();
  const datasetId = page.url().split("/").pop()!;
  await page
    .getByLabel("Notes", { exact: true })
    .first()
    .fill("Local unsaved note");
  const me = await (await page.request.get("/api/auth/me")).json();
  const remote = await page.request.patch(`/api/datasets/${datasetId}`, {
    headers: { Origin: "http://127.0.0.1:3110", "X-CSRF-Token": me.csrf_token },
    data: { name: "Travel reference cases", version: 2 },
  });
  expect(remote.status()).toBe(200);
  await page.getByRole("button", { name: "Save dataset", exact: true }).click();
  await expect(page.locator(".notice[role=alert]")).toContainText(
    "Dataset changed",
  );
  await expect(page.getByLabel("Notes", { exact: true }).first()).toHaveValue(
    "Local unsaved note",
  );
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Reload latest" }).click();
  await expect(page.getByText("REFERENCE DATASET · VERSION 3")).toBeVisible();
  await expect(page.getByLabel("Notes", { exact: true }).first()).toHaveValue(
    "",
  );
  const runIds: string[] = [];
  for (const name of ["Baseline top 5", "Candidate top 3"]) {
    await page.getByRole("link", { name: "Evaluations", exact: true }).click();
    await page
      .getByRole("button", { name: "New evaluation", exact: true })
      .click();
    await page.getByLabel("Run name").fill(name);
    await page
      .getByLabel("Retrieved chunks (top K)")
      .fill(name.startsWith("Candidate") ? "3" : "5");
    await page
      .getByRole("button", { name: "Start evaluation", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("completed", { exact: true }).first(),
    ).toBeVisible();
    await expect(page.getByText("2 of 2 cases recorded")).toBeVisible();
    runIds.push(page.url().split("/").pop()!);
  }
  await page
    .getByRole("button", {
      name: "What is the daily meal allowance?",
      exact: true,
    })
    .click();
  await expect(page.getByTestId("answer")).toContainText("75 dollars");
  await page.screenshot({
    path: "test-results/evaluation.png",
    fullPage: true,
  });
  await expect(
    new AxeBuilder({ page }).analyze().then((r) => r.violations),
  ).resolves.toEqual([]);
  await page.getByRole("link", { name: "Compare runs", exact: true }).click();
  await page.getByLabel("Baseline run ID").fill(runIds[0]);
  await page.getByLabel("Candidate run ID").fill(runIds[1]);
  await page.getByLabel("Latency / cost tolerance (relative)").fill("10");
  await page.getByRole("button", { name: "Compare experiments" }).click();
  await expect(
    page.getByRole("heading", { name: "Comparison inconclusive" }),
  ).toBeVisible();
  await expect(
    page.getByText("Missing or reduced coverage: cost coverage"),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/comparison.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Document pipeline", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/dashboard.png",
    fullPage: false,
  });
});

test("viewer membership prevents writes and session expiry closes protected views", async ({
  page,
  browser,
}) => {
  await login(page);
  await workspace(page, "Scoped research");
  const workspaceUrl = page.url();
  await page.getByRole("link", { name: "Members", exact: true }).click();
  await page.getByLabel("Member email").fill("viewer@example.com");
  await page.getByRole("button", { name: "Save membership" }).click();
  await expect(page.getByText("Membership saved.")).toBeVisible();
  const context = await browser.newContext();
  const viewer = await context.newPage();
  await login(viewer, "viewer@example.com");
  await viewer.goto(workspaceUrl + "/knowledge");
  await expect(
    viewer.getByRole("heading", { name: "Knowledge bases", exact: true }),
  ).toBeVisible();
  await expect(
    viewer.getByRole("button", { name: "New knowledge base" }),
  ).toHaveCount(0);
  const me = await (await viewer.request.get("/api/auth/me")).json();
  const denied = await viewer.request.post(
    `/api/workspaces/${workspaceUrl.split("/").pop()}/knowledge-bases`,
    {
      headers: {
        Origin: "http://127.0.0.1:3110",
        "X-CSRF-Token": me.csrf_token,
      },
      data: { name: "Forbidden" },
    },
  );
  expect(denied.status()).toBe(403);
  await viewer.request.post("/api/auth/logout", {
    headers: { Origin: "http://127.0.0.1:3110", "X-CSRF-Token": me.csrf_token },
  });
  await viewer.getByRole("link", { name: "Playground", exact: true }).click();
  await expect(viewer).toHaveURL(/\/login$/);
  await context.close();
});

test("agent tool records and provider failures are visible", async ({
  page,
}) => {
  await login(page);
  await workspace(page, "Agent research");
  await knowledge(page);
  await page.getByRole("link", { name: "Playground", exact: true }).click();
  await page
    .getByLabel("Question", { exact: true })
    .fill("Calculate the allowance for three days");
  await page.getByText("Query settings", { exact: true }).click();
  await page.getByLabel("Enable agent tools", { exact: false }).check();
  await page.getByRole("button", { name: "Ask question" }).click();
  await expect(page.getByTestId("answer")).toContainText("75 dollars");
  await page.getByText("1. calculator", { exact: true }).click();
  await expect(page.getByText('"result": 225', { exact: false })).toBeVisible();
  await page.getByLabel("Question", { exact: true }).fill("Provider failure");
  await page.getByRole("button", { name: "Ask question" }).click();
  await expect(page.getByTestId("answer")).toContainText("provider_http_503");
  await expect(page.getByText("Partial usage", { exact: true })).toBeVisible();
});

test("successful save adopts its returned version and self-demotion refreshes permissions", async ({
  page,
}) => {
  await login(page);
  await workspace(page, "Edit consistency");
  await page.getByRole("link", { name: "Evaluations", exact: true }).click();
  await page.getByRole("button", { name: "New dataset", exact: true }).click();
  await page.getByLabel("Dataset name").fill("Consistency cases");
  await page
    .getByRole("button", { name: "Create dataset", exact: true })
    .click();
  await page.getByRole("button", { name: "Add case", exact: true }).click();
  await page.getByLabel("Question 1", { exact: true }).fill("Initial question");
  const datasetId = page.url().split("/").pop()!;
  let readAfterSave = 0;
  await page.route(`**/api/datasets/${datasetId}`, async (route) => {
    readAfterSave++;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ error: { message: "Controlled read failure" } }),
    });
  });
  await page.getByRole("button", { name: "Save dataset", exact: true }).click();
  await expect(page.getByText("REFERENCE DATASET · VERSION 2")).toBeVisible();
  await expect(page.getByLabel("Question 1", { exact: true })).toHaveValue(
    "Initial question",
  );
  expect(readAfterSave).toBe(0);
  await page
    .getByLabel("Question 1", { exact: true })
    .fill("Retained local edit");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Reload latest" }).click();
  await expect(page.locator(".notice[role=alert]")).toContainText(
    "Controlled read failure",
  );
  await expect(page.getByLabel("Question 1", { exact: true })).toHaveValue(
    "Retained local edit",
  );
  await page.unroute(`**/api/datasets/${datasetId}`);
  await page.getByRole("link", { name: "Members", exact: true }).click();
  await page.getByLabel("Member email").fill("other@example.com");
  await page.getByLabel("Workspace role").selectOption("owner");
  await page.getByRole("button", { name: "Save membership" }).click();
  await expect(page.getByText("Membership saved.")).toBeVisible();
  await page.getByLabel("Member email").fill("admin@example.com");
  await page.getByLabel("Workspace role").selectOption("viewer");
  await page.getByRole("button", { name: "Save membership" }).click();
  await expect(
    page.getByRole("button", { name: "Save membership" }),
  ).toHaveCount(0);
  await page
    .getByRole("link", { name: "Knowledge bases", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "New knowledge base" }),
  ).toHaveCount(0);
});

test("account provisioning and login forms are accessible", async ({
  page,
  browser,
}) => {
  await page.goto("/login");
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeEnabled();
  await expect(
    new AxeBuilder({ page }).analyze().then((r) => r.violations),
  ).resolves.toEqual([]);
  await login(page);
  await page
    .getByRole("link", { name: "Account administration", exact: true })
    .click();
  await page.getByRole("button", { name: "New account", exact: true }).click();
  await page.getByLabel("Full name").fill("Morgan Ellis");
  await page
    .getByLabel("Email address", { exact: true })
    .fill("morgan@example.com");
  await page.getByLabel("Initial password").fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByText("Account created.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("morgan@example.com", { exact: true }),
  ).toBeVisible();
  await expect(
    new AxeBuilder({ page }).analyze().then((r) => r.violations),
  ).resolves.toEqual([]);
  const context = await browser.newContext();
  const member = await context.newPage();
  await login(member, "morgan@example.com");
  await expect(
    member.getByRole("link", { name: "Account administration", exact: true }),
  ).toHaveCount(0);
  await member.goto("/team");
  await expect(member.locator(".notice[role=alert]")).toContainText(
    "requires an administrator",
  );
  await context.close();
});
