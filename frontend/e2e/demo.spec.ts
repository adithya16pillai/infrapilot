import { expect, test } from "@playwright/test";

/**
 * This single test IS the demo rehearsal (PRD Section 10).
 * Run it before walking to the stage:
 *
 *   npx playwright test
 *
 * It walks the exact path of the 3-minute script: load the city, launch the
 * ransomware scenario, watch the agent reason, see the score fall, approve a
 * mitigation, see the score climb.
 */

const API = "http://127.0.0.1:8000";

test.beforeEach(async ({ request }) => {
  await request.post(`${API}/api/reset`);
});

test.afterAll(async ({ request }) => {
  await request.post(`${API}/api/reset`);
});

test("demo happy path: load -> simulate -> approve -> score recovers", async ({
  page,
}) => {
  await page.goto("/");

  // 1. The city loads with all twelve assets and a baseline score.
  await expect(page.getByTestId("node-control_centre")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('[data-testid^="node-"]')).toHaveCount(12);

  const score = page.getByTestId("resilience-score");
  await expect(score).toHaveText("84");

  // Baseline posture: the seed city carries known degradations, not a perfect 100.
  await expect(page.getByTestId("node-telecom_hub")).toHaveAttribute(
    "data-status",
    "degraded",
  );

  // 2. Launch the demo scenario.
  await page.getByTestId("preset-ransomware_control_centre").click();

  // 3. The agent's reasoning streams in, one readable row at a time.
  await expect(page.getByText("Calculating cascading impact")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("Generating mitigation plan")).toBeVisible({
    timeout: 20_000,
  });

  // 4. The cascade lands: red spreads and the score falls.
  await expect(page.getByTestId("node-control_centre")).toHaveAttribute(
    "data-status",
    "failed",
    { timeout: 20_000 },
  );
  await expect(page.getByTestId("node-substation_a")).toHaveAttribute(
    "data-status",
    "failed",
  );
  await expect(page.getByTestId("node-hospital")).toHaveAttribute(
    "data-status",
    "degraded",
  );
  await expect(score).toHaveText("43", { timeout: 10_000 });

  // 5. Mitigations appear with computed gains.
  const cards = page.getByTestId("recommendation-card");
  await expect(cards.first()).toBeVisible({ timeout: 15_000 });
  const gainText = await cards.first().locator("text=/^\\+\\d+$/").first().textContent();
  const claimedGain = Number(gainText?.replace("+", ""));
  expect(claimedGain).toBeGreaterThan(0);

  // 6. Human approval — and the advertised gain is the real delta.
  await cards.first().getByTestId("approve-button").click();
  await expect(score).toHaveText(String(43 + claimedGain), { timeout: 15_000 });

  // 7. The safety guarantee is on screen the whole time.
  await expect(
    page.getByText(/never applies changes to live systems/i),
  ).toBeVisible();
});

test("agent picks analyses per question (F4 autonomy proof)", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("node-control_centre")).toBeVisible({ timeout: 15_000 });

  // A structural question must NOT run a cascade.
  await page.getByTestId("preset-spof_analysis").click();
  await expect(page.getByText("Mapping structural dependencies")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("Calculating cascading impact")).toHaveCount(0);

  // Score is untouched: nothing failed, this is graph shape not an incident.
  await expect(page.getByTestId("resilience-score")).toHaveText("84");
});

test("unknown asset returns a friendly answer, not a crash", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("node-control_centre")).toBeVisible({ timeout: 15_000 });

  await page.getByTestId("query-input").fill("Simulate an attack on the Atlantis Sea Gate");
  await page.getByTestId("query-input").press("Enter");

  await expect(page.getByText(/could not match that query/i)).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByTestId("resilience-score")).toHaveText("84");
});

test("node detail sheet shows inventory and supply chain findings", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("node-control_centre").click();

  await expect(page.getByRole("heading", { name: "Control Centre" })).toBeVisible();
  await expect(page.getByText(/Windows Server 2016/)).toBeVisible();

  // The package appears twice by design: once in the inventory, once as a
  // supply chain finding with its behavioural description.
  await expect(page.getByText("node-ipc@10.1.1")).toHaveCount(2);
  await expect(page.getByText(/protestware payload/i)).toBeVisible();
  await expect(page.getByText(/operational impact/i)).toBeVisible();
});
