import { test, expect } from '@playwright/test';
import { chooseFiles, openApp, shot } from './support.js';

function amount(value) {
  const pattern = String(value).replace(/\B(?=(\d{3})+(?!\d))/g, '[\\s\\u00a0\\u202f]');
  return new RegExp(pattern);
}

test('üres oldalon a feldolgozás le van tiltva', async ({ page }) => {
  await openApp(page);

  await expect(page.getByText('Húzd ide a számlákat, vagy kattints a kiválasztáshoz')).toBeVisible();
  await expect(page.getByText(/maximum 20 MB/)).toBeVisible();
  await expect(page.getByRole('button', { name: /Feldolgozás indítása/ })).toBeDisabled();
  await expect(page.getByRole('heading', { name: 'Feldolgozási eredmények' })).toHaveCount(0);
  await expect(page.getByText(/GCP AI Demo/)).toBeVisible();

  await shot(page, '01-ures-kepernyo.png');
});

test('feltöltés, egy fájl kivétele és az összes törlése', async ({ page }) => {
  const state = await openApp(page);

  await chooseFiles(page, ['01_helyes_alap.pdf', '03_helyes_angol.pdf']);

  await expect(page.getByText('2 fájl feltöltve')).toBeVisible();
  await expect(page.getByRole('row', { name: /01_helyes_alap\.pdf/ })).toContainText('Feltöltve');
  await expect(page.getByRole('row', { name: /03_helyes_angol\.pdf/ })).toContainText('Feltöltve');
  await expect(page.getByRole('button', { name: /Feldolgozás indítása/ })).toBeEnabled();
  await shot(page, '02-feltoltes.png');

  await page.getByRole('row', { name: /01_helyes_alap\.pdf/ }).getByTitle('Fájl eltávolítása').click();
  await expect(page.getByText('01_helyes_alap.pdf')).toHaveCount(0);
  await expect(page.getByText('1 fájl feltöltve')).toBeVisible();
  expect(state.deleted).toBeNull();

  await page.getByRole('button', { name: /Összes törlése/ }).click();
  await expect(page.getByText('fájl feltöltve')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Feldolgozás indítása/ })).toBeDisabled();
  expect(state.deleted.file_ids).toEqual(['file-2']);
});

test('a szöveges fájl nem kerül fel', async ({ page }) => {
  await openApp(page);
  const uploadRequest = page.waitForRequest(
    (request) => request.method() === 'POST' && new URL(request.url()).pathname === '/api/upload',
    { timeout: 1500 },
  );

  await page.locator('input[type="file"]').setInputFiles({
    name: 'jegyzet.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('nem számla'),
  });

  await expect(uploadRequest).rejects.toThrow();
  await expect(page.getByText('fájl feltöltve')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Feldolgozás indítása/ })).toBeDisabled();
});

test('a feltöltési hiba megjelenik, a lista üres marad', async ({ page }) => {
  await openApp(page, { failUpload: true });

  await chooseFiles(page, ['01_helyes_alap.pdf']);

  await expect(page.getByText(/Feltöltési hiba/)).toBeVisible();
  await expect(page.getByText('fájl feltöltve')).toHaveCount(0);
});

test('ha a törlés elhasal, a fájl a listában marad', async ({ page }) => {
  await openApp(page, { failDelete: true });
  await chooseFiles(page, ['01_helyes_alap.pdf']);
  await expect(page.getByText('1 fájl feltöltve')).toBeVisible();

  await page.getByRole('button', { name: /Összes törlése/ }).click();

  await expect(page.getByText(/Törlési hiba/)).toBeVisible();
  await expect(page.getByText('1 fájl feltöltve')).toBeVisible();
  await expect(page.getByRole('button', { name: /Feldolgozás indítása/ })).toBeEnabled();
});

test('a mockolt eredmény táblázata, szűrője, részlete és exportja', async ({ page }) => {
  const state = await openApp(page, { holdFirstStatus: true });
  await chooseFiles(page, ['01_helyes_alap.pdf', '03_helyes_angol.pdf']);
  await expect(page.getByText('2 fájl feltöltve')).toBeVisible();

  try {
    await page.getByRole('button', { name: /Feldolgozás indítása/ }).click();
    await expect(page.getByText('Feldolgozás: 0/2')).toBeVisible();
    await expect(page.getByText('Az első számla feldolgozása folyamatban...')).toBeVisible();
    await shot(page, '03-feldolgozas.png');
  } finally {
    state.releaseStatus();
  }

  const okRow = page.getByRole('row', { name: /Minta Kereskedelmi Kft/ });
  const warningRow = page.getByRole('row', { name: /Figyelő Bt/ });
  await expect(okRow).toBeVisible();
  await expect(warningRow).toBeVisible();
  await expect(page.getByText(/Összesen:\s*2\s*számla/)).toBeVisible();
  await expect(page.getByText(/Bruttó összeg:/)).toContainText(amount(177000));
  await expect(page.getByText(/Figyelmeztetés:\s*1/)).toBeVisible();
  await expect(okRow).toContainText('Rendben');
  await expect(okRow).toContainText(amount(127000));
  await expect(warningRow).toContainText(amount(50000));
  await shot(page, '04-eredmenyek.png');

  await page.getByRole('button', { name: 'Rendben', exact: true }).click();
  await expect(warningRow).toHaveCount(0);
  await expect(page.getByRole('cell', { name: 'Minta Kereskedelmi Kft.' })).toBeVisible();

  await page.getByRole('button', { name: 'Figyelmeztetés', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'Minta Kereskedelmi Kft.' })).toHaveCount(0);
  await expect(page.getByRole('cell', { name: 'Figyelő Bt.' })).toBeVisible();

  await page.getByRole('button', { name: 'Hiba', exact: true }).click();
  await expect(page.getByText('Nincs megjeleníthető eredmény.')).toBeVisible();

  await page.getByRole('button', { name: 'Összes', exact: true }).click();
  await page.getByRole('cell', { name: 'Minta Kereskedelmi Kft.' }).click();
  await expect(page.getByText('12345678-1-02')).toBeVisible();
  await expect(page.getByText('SZ-2026-014')).toBeVisible();
  await expect(page.getByText('Tanácsadás')).toBeVisible();
  await expect(page.getByText('2026-03-15').first()).toBeVisible();

  await page.getByRole('cell', { name: 'Figyelő Bt.' }).click();
  await expect(page.getByText('Az adószám hiányzik.')).toBeVisible();
  await expect(page.getByText('Kérd be a szállító adószámát.')).toBeVisible();
  await expect(page.getByText('Tanácsadás')).toHaveCount(0);
  await shot(page, '05-reszletek.png');

  await expect(page.getByRole('button', { name: /Feldolgozás indítása/ })).toBeEnabled();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: /PDF/ }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('szamlak_export.pdf');
});

test('a feltöltött számla megnyílik a betekintőben', async ({ page }) => {
  await openApp(page);
  await chooseFiles(page, ['07_hibas_kezzel_irt.jpg']);
  await expect(page.getByRole('button', { name: 'Megtekintés' })).toBeVisible();

  await page.getByRole('button', { name: 'Megtekintés' }).click();
  const dialog = page.getByRole('dialog', { name: '07_hibas_kezzel_irt.jpg' });
  const image = dialog.locator('img');
  await expect(image).toBeVisible();
  await image.evaluate((img) => img.decode());
  await shot(page, '06-betekinto.png');

  await dialog.getByRole('button', { name: 'Bezárás' }).click();
  await expect(dialog).toHaveCount(0);
});

test('az API panel a böngésző és a backend hívást mutatja', async ({ page }) => {
  await openApp(page);

  await page.getByRole('button', { name: /API hívások/ }).click();
  await expect(page.getByRole('complementary', { name: 'API hívások' })).toBeVisible();
  await expect(page.getByText(/Még nincs rögzített hívás/)).toBeVisible();

  await chooseFiles(page, ['01_helyes_alap.pdf']);
  await expect(page.getByText('1 fájl feltöltve')).toBeVisible();
  await expect(page.getByRole('button', { name: /API hívások/ })).toContainText('2');
  await expect(page.getByText('POST /api/upload')).toHaveCount(2);

  await page.getByRole('button', { name: 'JSON lenyitása' }).first().click();
  await expect(page.getByText('Kérés', { exact: true })).toBeVisible();
  await shot(page, '07-api-hivasok.png');

  for (const label of [/^DOCAI/, /AI model/]) {
    await page.getByRole('tab', { name: label }).click();
    await expect(page.getByText('POST /api/upload')).toHaveCount(0);
    await expect(page.getByText(/Még nincs rögzített hívás/)).toBeVisible();
  }

  await page.getByRole('tab', { name: /^BE/ }).click();
  await expect(page.getByText('POST /api/upload')).toBeVisible();
  await expect(page.getByText('200')).toBeVisible();
});
