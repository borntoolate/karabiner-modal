// Does a mouse-made selection on a READ-ONLY web page get extended by Shift+Arrow?
// This is the behaviour the "mark" emulation depends on outside of text fields.
const { chromium } = require('playwright');

const HTML = `<!doctype html><meta charset="utf-8">
<body style="font:16px/1.6 monospace; padding:20px">
<p id="ro">alpha bravo charlie delta echo foxtrot golf hotel india juliet</p>
<textarea id="ta" rows="3" cols="40">alpha bravo charlie delta echo foxtrot</textarea>
</body>`;

const sel = (page) => page.evaluate(() => (window.getSelection() || '').toString());

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setContent(HTML);

  // ---- Case 1: read-only paragraph, selection made with the mouse ----
  const box = await page.locator('#ro').boundingBox();
  await page.mouse.move(box.x + 4, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + 60, box.y + box.height / 2, { steps: 10 });
  await page.mouse.up();
  const before = await sel(page);

  await page.keyboard.press('Shift+ArrowRight');
  await page.keyboard.press('Shift+ArrowRight');
  await page.keyboard.press('Shift+ArrowRight');
  const after = await sel(page);

  console.log('== read-only <p>, mouse selection ==');
  console.log('  before        :', JSON.stringify(before));
  console.log('  after 3x S-Rt :', JSON.stringify(after));
  console.log('  EXTENDED      :', after.length > before.length && after.startsWith(before));

  // Does a bare arrow collapse it? (this is why "mark mode" is needed)
  await page.keyboard.press('ArrowRight');
  console.log('  after bare Rt :', JSON.stringify(await sel(page)));

  // ---- Case 2: same thing with no prior selection (caret browsing off) ----
  await page.evaluate(() => window.getSelection().removeAllRanges());
  await page.keyboard.press('Shift+ArrowRight');
  console.log('  no-prior-sel  :', JSON.stringify(await sel(page)), '(expect empty: no caret)');

  // ---- Case 3: textarea, mouse selection then Shift+Arrow ----
  const tb = await page.locator('#ta').boundingBox();
  await page.mouse.move(tb.x + 8, tb.y + 12);
  await page.mouse.down();
  await page.mouse.move(tb.x + 70, tb.y + 12, { steps: 10 });
  await page.mouse.up();
  const taBefore = await page.$eval('#ta', (e) => e.value.slice(e.selectionStart, e.selectionEnd));
  await page.keyboard.press('Shift+ArrowRight');
  await page.keyboard.press('Shift+ArrowRight');
  const taAfter = await page.$eval('#ta', (e) => e.value.slice(e.selectionStart, e.selectionEnd));
  console.log('== <textarea>, mouse selection ==');
  console.log('  before        :', JSON.stringify(taBefore));
  console.log('  after 2x S-Rt :', JSON.stringify(taAfter));
  console.log('  EXTENDED      :', taAfter.length > taBefore.length);

  await browser.close();
})();
