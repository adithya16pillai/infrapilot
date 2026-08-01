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
  await page.goto("/city");

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
  await page.goto("/city");
  await expect(page.getByTestId("node-control_centre")).toBeVisible({ timeout: 15_000 });

  // A structural question must NOT run a cascade. Asked free-text: there is
  // deliberately no preset chip for it, so this also exercises the query box.
  await page.getByTestId("query-input").fill("What is our biggest single point of failure?");
  await page.getByTestId("query-input").press("Enter");
  await expect(page.getByText("Mapping structural dependencies")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("Calculating cascading impact")).toHaveCount(0);

  // Score is untouched: nothing failed, this is graph shape not an incident.
  await expect(page.getByTestId("resilience-score")).toHaveText("84");
});

test("unknown asset returns a friendly answer, not a crash", async ({ page }) => {
  await page.goto("/city");
  await expect(page.getByTestId("node-control_centre")).toBeVisible({ timeout: 15_000 });

  await page.getByTestId("query-input").fill("Simulate an attack on the Atlantis Sea Gate");
  await page.getByTestId("query-input").press("Enter");

  await expect(page.getByText(/could not match that query/i)).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByTestId("resilience-score")).toHaveText("84");
});

test("node detail sheet shows inventory and supply chain findings", async ({ page }) => {
  await page.goto("/city");
  await page.getByTestId("node-control_centre").click();

  await expect(page.getByRole("heading", { name: "Control Centre" })).toBeVisible();
  await expect(page.getByText(/Windows Server 2016/)).toBeVisible();

  // The package appears twice by design: once in the inventory, once as a
  // supply chain finding with its behavioural description.
  await expect(page.getByText("node-ipc@10.1.1")).toHaveCount(2);
  await expect(page.getByText(/protestware payload/i)).toBeVisible();
  await expect(page.getByText(/operational impact/i)).toBeVisible();
});

test("kill chain names the mechanism at each hop", async ({ page }) => {
  await page.goto("/city");
  await page.getByTestId("preset-ransomware_control_centre").click();

  await expect(page.getByRole("heading", { name: "Attack path" })).toBeVisible({
    timeout: 25_000,
  });
  const path = page.getByRole("heading", { name: "Attack path" }).locator("..");
  await expect(path.getByText("compromised")).toBeVisible();
  await expect(path.getByText(/control link/)).toBeVisible();
  await expect(path.getByText(/power feed/)).toBeVisible();
  await expect(path.getByText(/weight/).first()).toBeVisible();
});

test("dashboard is the landing page and links into the city", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Resilience posture" }),
  ).toBeVisible();
  await expect(page.getByTestId("resilience-score")).toHaveText("84", {
    timeout: 15_000,
  });

  // Sidebar sections are all present.
  const nav = page.locator("nav").first();
  for (const label of ["Assets", "Approvals", "Risks", "Simulations", "More"]) {
    await expect(nav.getByText(label, { exact: true })).toBeVisible();
  }
  await expect(nav.getByText("Profile")).toBeVisible();
  await expect(nav.getByText("Sign out")).toBeVisible();

  // Score Trend is gone.
  await expect(page.getByText(/score trend/i)).toHaveCount(0);

  await page.getByTestId("city-view-button").click();
  await expect(page).toHaveURL(/\/city$/);
  await expect(page.getByTestId("node-control_centre")).toBeVisible({
    timeout: 15_000,
  });
});

test("a past simulation replays on the graph from the dashboard", async ({
  page,
}) => {
  // Produce one run to click on.
  await page.goto("/city");
  await page.getByTestId("preset-ransomware_control_centre").click();
  await expect(page.getByTestId("resilience-score")).toHaveText("43", {
    timeout: 25_000,
  });

  await page.goto("/simulations");
  const row = page.getByTestId("simulation-row").first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.click();

  // The graph comes back in exactly the state that run produced.
  await expect(page).toHaveURL(/simulation=sim_/);
  await expect(page.getByTestId("node-control_centre")).toHaveAttribute(
    "data-status",
    "failed",
    { timeout: 20_000 },
  );
  await expect(page.getByTestId("resilience-score")).toHaveText("43");
  await expect(page.getByRole("heading", { name: "Attack path" })).toBeVisible();
});

test("risks page explains OSSPrey and ranks by operational impact", async ({
  page,
}) => {
  await page.goto("/risks");

  await expect(page.getByRole("heading", { name: /how ossprey reads this/i })).toBeVisible();
  await expect(page.getByText(/rather than by matching known/i)).toBeVisible();
  await expect(page.getByText(/impact = severity_weight/i)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /same severity, different consequence/i }),
  ).toBeVisible();

  // Findings are ordered by operational impact, and each row deep-links.
  const rows = page.getByTestId("risk-row");
  await expect(rows.first()).toBeVisible();
  await rows.first().click();
  await expect(page).toHaveURL(/\/city\?asset=/);
});

test("pending approvals are reviewable from their own page", async ({ page }) => {
  await page.goto("/city");
  await page.getByTestId("preset-ransomware_control_centre").click();
  await expect(page.getByTestId("recommendation-card").first()).toBeVisible({
    timeout: 25_000,
  });

  await page.goto("/approvals");
  const card = page.getByTestId("recommendation-card").first();
  await expect(card).toBeVisible({ timeout: 15_000 });
  await expect(card.getByText(/pts \/ £10k/)).toBeVisible();

  await card.getByTestId("approve-button").click();
  await expect(page.getByText(/Applied\. Resilience under that scenario/i)).toBeVisible({
    timeout: 15_000,
  });
});

test("dashboard sections navigate as a whole, rows still win", async ({ page }) => {
  await page.goto("/city");
  await page.getByTestId("preset-ransomware_control_centre").click();
  await expect(page.getByTestId("resilience-score")).toHaveText("43", {
    timeout: 25_000,
  });

  await page.goto("/");
  // The separate "view all"/"Inspect" affordances are gone.
  for (const gone of ["Inspect", "All assets", "All findings", "Review all", "Full history"]) {
    await expect(page.getByText(gone, { exact: true })).toHaveCount(0);
  }

  // Clicking a section navigates.
  await page.getByText("Operational status").click();
  await expect(page).toHaveURL(/\/assets$/);

  // A row inside a clickable section beats the section behind it.
  await page.goto("/");
  await page.getByText(/^impact /).first().click();
  await expect(page).toHaveURL(/\/city\?asset=/);
});
