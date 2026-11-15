// Round trip through the planning tool (headless Chromium):
// load the example "manuell", move a card, add a printer, cable it to a switch port,
// rename a device, export the YAML.  Usage: node planer_roundtrip.js <out.yaml> [screenshot.png]
const { chromium } = require("playwright");
const path = require("path");

(async () => {
  const [out, shot] = process.argv.slice(2);
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1600, height: 1000 }, acceptDownloads: true });
  const p = await ctx.newPage();
  const errs = [];
  p.on("pageerror", e => errs.push(e.message));
  p.on("dialog", d => d.accept());
  await p.goto("file://" + path.resolve(__dirname, "../planer/planer.html"));
  await p.waitForFunction(() => document.querySelector("#status").textContent !== "bereit");
  await p.selectOption("#examples", "manuell");
  await p.waitForTimeout(300);
  const center = async sel => { const r = await p.locator(sel).first().boundingBox(); return [r.x + r.width / 2, r.y + r.height / 2]; };
  const dragTo = async (from, to) => { await p.mouse.move(...from); await p.mouse.down(); await p.mouse.move((from[0] + to[0]) / 2, (from[1] + to[1]) / 2, { steps: 5 }); await p.mouse.move(...to, { steps: 5 }); await p.mouse.up(); await p.waitForTimeout(100); };
  const k = await p.evaluate(() => view.k);

  // 1. move the PC 160 units to the left
  const pc0 = await p.evaluate(() => ({ ...devOf(lab, "pc").pos }));
  const pcAt = await center('.card[data-id="pc"]');
  await dragTo(pcAt, [pcAt[0] - 160 * k, pcAt[1]]);
  const pc1 = await p.evaluate(() => ({ ...devOf(lab, "pc").pos }));

  // 2. add a printer and put it below the laptop
  await p.click("#palette-roles button:has-text('Drucker')");
  const prId = await p.evaluate(() => sel.ids[0]);
  await p.evaluate(id => { const d = devOf(lab, id); const l = devOf(lab, "laptop").pos; d.pos.x = l.x; d.pos.y = l.y + 200; commit("Testposition"); }, prId);

  // 3. select the switch and drag from its free port p6 onto the printer
  await p.click('.card[data-id="sw"]', { position: { x: 30, y: 30 } });
  const port = await center('.handle.port[data-id="sw"][data-port="p6"]');
  const pr = await center(`.card[data-id="${prId}"]`);
  await dragTo(port, pr);
  const link = await p.evaluate(() => lab.links[lab.links.length - 1]);

  // 4. rename the laptop through the inspector
  await p.click('.card[data-id="laptop"]', { position: { x: 30, y: 30 } });
  const name = p.locator("#insp label.f", { hasText: "Funktion (Name)" }).locator("input");
  await name.fill("Notebook");
  await name.press("Tab");

  // 5. export
  const [dl] = await Promise.all([p.waitForEvent("download"), p.click("#btn-save")]);
  await dl.saveAs(out);
  if (shot) await p.screenshot({ path: shot });
  const res = await p.evaluate(() => ({ err: result.err, n: lab.devices.length }));
  console.log(JSON.stringify({ pc0, pc1, prId, link, res, errs }));
  await b.close();
})();
