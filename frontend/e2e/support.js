// Közös mock és képernyőkép a UI tesztekhez. Az AI végpontokat nem hívjuk.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect } from '@playwright/test';

const here = path.dirname(fileURLToPath(import.meta.url));
const shotDir = path.resolve(here, '../test-results/screenshots');
const invoicesDir = path.resolve(here, '../../invoices');

const RESULTS = {
  '01_helyes_alap.pdf': {
    status: 'ok',
    processing_time_ms: 120,
    invoice_data: {
      supplier_name: 'Minta Kereskedelmi Kft.',
      supplier_tax_id: '12345678102',
      supplier_address: '1051 Budapest, Példa utca 1.',
      buyer_name: 'Vevő Zrt.',
      buyer_tax_id: '87654321-2-41',
      invoice_number: 'SZ-2026-014',
      invoice_date: '2026-03-15T12:00:00Z',
      due_date: '2026-03-30T12:00:00Z',
      completion_date: '2026-03-15T12:00:00Z',
      net_amount: 100000,
      vat_amount: 27000,
      gross_amount: 127000,
      currency: 'HUF',
      line_items: [
        { description: 'Tanácsadás', quantity: 2, unit_price: 50000, total: 100000 },
      ],
    },
    issues: [],
    gemini_summary: 'A számla adatai összeállnak, könyvelésre átadható.',
  },
  '03_helyes_angol.pdf': {
    status: 'warning',
    processing_time_ms: 80,
    invoice_data: {
      supplier_name: 'Figyelő Bt.',
      supplier_tax_id: null,
      buyer_name: 'Vevő Zrt.',
      invoice_number: 'F-88',
      invoice_date: '2026-04-01T12:00:00Z',
      net_amount: 40000,
      vat_amount: 10000,
      gross_amount: 50000,
      currency: 'HUF',
      line_items: [],
    },
    issues: [
      {
        severity: 'warning',
        message: 'Az adószám hiányzik.',
        suggestion: 'Kérd be a szállító adószámát.',
      },
    ],
    gemini_summary: 'Hiányzó adószám miatt ellenőrizendő.',
  },
};

export function invoice(name) {
  return path.join(invoicesDir, name);
}

export async function chooseFiles(page, names) {
  await page.locator('input[type="file"]').setInputFiles(names.map(invoice));
}

export async function shot(page, name) {
  fs.mkdirSync(shotDir, { recursive: true });
  // A sticky fejléc a teljes oldalas képen középre csúszna.
  await page.addStyleTag({ content: 'header, aside { position: static !important; }' });
  await page.screenshot({
    path: path.join(shotDir, name),
    fullPage: true,
  });
}

function uploadedNames(request) {
  const contentType = request.headers()['content-type'] || '';
  const boundaryMatch = contentType.match(/boundary=(?:"([^"]+)"|([^;]+))/i);
  if (!boundaryMatch) {
    throw new Error('A feltöltés nem multipart');
  }
  const boundary = boundaryMatch[1] || boundaryMatch[2];
  const raw = request.postDataBuffer().toString('latin1');
  const names = [];
  for (const part of raw.split(`--${boundary}`)) {
    const headerEnd = part.indexOf('\r\n\r\n');
    if (headerEnd === -1) continue;
    const header = part.slice(0, headerEnd);
    const encoded = header.match(/filename\*=UTF-8''([^\r\n;]+)/i);
    const plain = header.match(/filename="([^"]*)"/);
    const name = encoded ? decodeURIComponent(encoded[1]) : plain?.[1];
    if (name) names.push(name);
  }
  if (!names.length) throw new Error('A feltöltésben nincs fájlnév');
  return names;
}

function buildResult(meta) {
  const template = RESULTS[meta?.file_name];
  if (!template) throw new Error(`Nincs mock eredmény: ${meta?.file_name}`);
  return {
    ...structuredClone(template),
    file_id: meta.file_id,
    file_name: meta.file_name,
  };
}

export async function openApp(page, options = {}) {
  const state = {
    files: [],
    deleted: null,
    releaseStatus() {},
  };
  let release = () => {};
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  state.releaseStatus = release;
  let statusHeld = false;

  await page.route(/\/api\//, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();

    if (method === 'POST' && pathname === '/api/upload') {
      if (options.failUpload) {
        await route.fulfill({
          status: 400,
          json: { detail: 'A fájl nem tölthető fel.' },
        });
        return;
      }
      const names = uploadedNames(request);
      const start = state.files.length;
      const files = names.map((fileName, index) => ({
        file_id: `file-${start + index + 1}`,
        file_name: fileName,
        status: 'uploaded',
      }));
      state.files.push(...files);
      await route.fulfill({ json: { files } });
      return;
    }

    if (method === 'POST' && pathname === '/api/upload/delete') {
      state.deleted = request.postDataJSON();
      if (options.failDelete) {
        await route.fulfill({ status: 500, json: { detail: 'nem törölhető' } });
        return;
      }
      await route.fulfill({ json: { ok: true } });
      return;
    }

    if (method === 'POST' && pathname === '/api/process') {
      const fileId = request.postDataJSON().file_ids[0];
      await route.fulfill({ json: { job_id: fileId, status: 'processing' } });
      return;
    }

    if (method === 'GET' && pathname.startsWith('/api/process/')) {
      if (options.holdFirstStatus && !statusHeld) {
        statusHeld = true;
        await gate;
      }
      const fileId = pathname.split('/').pop();
      const meta = state.files.find((file) => file.file_id === fileId);
      await route.fulfill({
        json: {
          job_id: fileId,
          status: 'done',
          progress: '1/1',
          results: [buildResult(meta)],
        },
      });
      return;
    }

    if (method === 'POST' && pathname.startsWith('/api/export/')) {
      const format = pathname.slice('/api/export/'.length);
      const ext = format === 'xlsx-accounting' ? 'xlsx' : format;
      await route.fulfill({
        status: 200,
        headers: {
          'content-type': 'application/octet-stream',
          'content-disposition': `attachment; filename=szamlak_export.${ext}`,
        },
        body: Buffer.from(`export ${format}`),
      });
      return;
    }

    const message = `Váratlan API hívás: ${method} ${pathname}`;
    await route.fulfill({ status: 500, contentType: 'text/plain', body: message });
    throw new Error(message);
  });

  await page.goto('/');
  await expect(
    page.getByRole('heading', { level: 1, name: 'Intelligens Számlafeldolgozó' }),
  ).toBeVisible();
  return state;
}
