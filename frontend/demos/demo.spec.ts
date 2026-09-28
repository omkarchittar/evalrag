import { test, expect } from "@playwright/test";
import { createHash } from "node:crypto";

test("record the evidence-to-evaluation journey", async ({
  browser,
}, testInfo) => {
  const context = await browser.newContext({
    viewport: { width: 1280, height: 850 },
    recordVideo: {
      dir: testInfo.outputPath("recording"),
      size: { width: 1280, height: 850 },
    },
  });
  const page = await context.newPage();
  const video = page.video()!;
  const pause = () => page.waitForTimeout(1400); // Presentation pacing, never a readiness check.
  try {
    await page.goto("http://127.0.0.1:3110/login");
    await page
      .getByLabel("Email address", { exact: true })
      .fill("admin@example.com");
    await page
      .getByLabel("Password", { exact: true })
      .fill("browser-fixture-password-2026");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Your workspaces" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "New workspace" }).click();
    await page.getByLabel("Workspace name").fill("Meridian research lab");
    await page
      .getByRole("button", { name: "Create workspace", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Meridian research lab" }),
    ).toBeVisible();
    await page
      .getByRole("link", { name: "Knowledge bases", exact: true })
      .click();
    await page.getByRole("button", { name: "New knowledge base" }).click();
    await page.getByLabel("Knowledge base name").fill("Employee handbook");
    await page
      .getByLabel("Description", { exact: true })
      .fill("Travel policy · original fictional evidence");
    await page
      .getByRole("button", { name: "Create knowledge base", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Employee handbook", exact: true }),
    ).toBeVisible();
    const source =
      "The daily meal allowance is 75 dollars. Receipts are required for expenses over 25 dollars.";
    await page.getByLabel("Choose document").setInputFiles({
      name: "travel-policy.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(source),
    });
    await page
      .getByRole("button", { name: "Upload document", exact: true })
      .click();
    await expect(page.getByText("ready", { exact: true })).toBeVisible();
    await pause();
    await page.getByRole("link", { name: "Playground", exact: true }).click();
    await page
      .getByLabel("Question", { exact: true })
      .pressSequentially("What is the daily meal allowance?", { delay: 35 });
    await page.getByRole("button", { name: "Ask question" }).click();
    await expect(page.getByTestId("answer")).toContainText("75 dollars");
    await page.getByTestId("answer").scrollIntoViewIfNeeded();
    await pause();
    await page.getByRole("button", { name: "View citation 1" }).click();
    await page
      .getByRole("heading", { name: "Source evidence" })
      .scrollIntoViewIfNeeded();
    await pause();
    await page.getByRole("link", { name: "Evaluations", exact: true }).click();
    await page
      .getByRole("button", { name: "New dataset", exact: true })
      .click();
    await page.getByLabel("Dataset name").fill("Travel policy reference");
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
    await page
      .getByPlaceholder("One SHA-256 document checksum per line")
      .fill(createHash("sha256").update(source).digest("hex"));
    await page
      .getByRole("button", { name: "Save dataset", exact: true })
      .click();
    await expect(page.getByText("REFERENCE DATASET · VERSION 2")).toBeVisible();
    await page.getByRole("link", { name: "Evaluations", exact: true }).click();
    await page
      .getByRole("button", { name: "New evaluation", exact: true })
      .click();
    await page.getByLabel("Run name").fill("Grounded baseline · top 5");
    await page
      .getByRole("button", { name: "Start evaluation", exact: true })
      .click();
    await expect(
      page.getByText("completed", { exact: true }).first(),
    ).toBeVisible();
    await page
      .getByRole("heading", { name: "Quality & coverage" })
      .scrollIntoViewIfNeeded();
    await pause();
    await page
      .getByRole("button", {
        name: "What is the daily meal allowance?",
        exact: true,
      })
      .click();
    await page
      .getByRole("heading", { name: "Case inspection" })
      .scrollIntoViewIfNeeded();
    await pause();
    await page.getByRole("link", { name: "Overview", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Document pipeline" }),
    ).toBeVisible();
    await pause();
  } finally {
    await context.close();
  }
  await video.saveAs(testInfo.outputPath("demo.webm"));
});
