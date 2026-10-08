/**
 * UI 截图验证流水线（手册 §8.1）
 * 用法：node scripts/ui-shots.mjs [baseUrl]
 * 输出：docs/shots/*.png（仓库根）；捕获到 console error / pageerror 时以退出码 2 结束。
 */
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const baseUrl = process.argv[2] ?? "http://localhost:5173";
const here = dirname(fileURLToPath(import.meta.url));
const shotsDir = resolve(here, "../../../docs/shots");
mkdirSync(shotsDir, { recursive: true });

const problems = [];

async function launch() {
  for (const options of [{ channel: "msedge" }, { channel: "chrome" }, {}]) {
    try {
      return await chromium.launch({ headless: true, ...options });
    } catch {
      // 尝试下一个浏览器渠道
    }
  }
  throw new Error("没有可用的 Chromium 内核浏览器（msedge / chrome / bundled）。");
}

const browser = await launch();
const page = await browser.newPage({ viewport: { width: 1512, height: 850 } });
page.on("console", (message) => {
  if (message.type() === "error") problems.push(`[console] ${message.text()}`);
});
page.on("pageerror", (error) => problems.push(`[pageerror] ${error.message}`));

async function shot(name) {
  await page.screenshot({ path: resolve(shotsDir, `${name}.png`) });
  console.log(`shot: ${name}.png`);
}

async function loginAs(username) {
  await page.fill('[data-testid="login-username"]', username);
  await page.fill('[data-testid="login-password"]', "123456");
  await page.click('[data-testid="login-submit"]');
  await page.waitForTimeout(2500);
}

await page.goto(baseUrl, { waitUntil: "load" });
await page.waitForTimeout(1500);
await shot("login");

await loginAs("community_admin");
await page.waitForTimeout(2000);
await shot("overview-top");

await page.evaluate(() => {
  const stage = document.querySelector(".workspace-stage");
  if (stage) stage.scrollTop = 1600;
});
await page.waitForTimeout(600);
await shot("overview-mid");

await page.evaluate(() => {
  const stage = document.querySelector(".workspace-stage");
  if (stage) stage.scrollTop = 999999;
});
await page.waitForTimeout(600);
await shot("overview-report");

// 切换家属账号：悬浮球 → 选 family01
await page.click(".quick-fab");
await page.waitForTimeout(400);
await page.click('.quick-pop__item:has-text("family01")');
await page.waitForTimeout(2500);
await shot("family");

await browser.close();

if (problems.length) {
  console.error("发现页面错误：\n" + problems.join("\n"));
  process.exitCode = 2;
} else {
  console.log("全部截图完成，无 console 错误。");
}
