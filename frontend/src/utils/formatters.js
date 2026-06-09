// Formázó segédfüggvények – összeg, dátum és adószám megjelenítéshez

/**
 * Pénzösszeg formázása ezres elválasztóval.
 * Null értéknél üres stringet ad vissza.
 *
 * @param {number|null} value – a formázandó összeg
 * @param {number} decimals – tizedesjegyek száma (alapértelmezett: 0)
 * @returns {string}
 */
export function formatAmount(value, decimals = 0) {
  if (value === null || value === undefined) return '';
  return new Intl.NumberFormat('hu-HU', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/**
 * Dátum formázása ÉÉÉÉ-HH-NN formátumba.
 * ISO string és Date objektum egyaránt elfogadott.
 *
 * @param {string|Date|null} value – a formázandó dátum
 * @returns {string}
 */
export function formatDate(value) {
  if (!value) return '';
  try {
    const date = typeof value === 'string' ? new Date(value) : value;
    if (isNaN(date.getTime())) return String(value);
    return date.toISOString().split('T')[0]; // ÉÉÉÉ-HH-NN
  } catch {
    return String(value);
  }
}

/**
 * Magyar adószám formázása (XXXXXXXX-Y-ZZ) formátumba.
 * Ha a szám már tartalmaz kötőjelet, változtatás nélkül adja vissza.
 *
 * @param {string|null} taxId – a formázandó adószám
 * @returns {string}
 */
export function formatTaxId(taxId) {
  if (!taxId) return '';
  // Ha már formázott, visszaadjuk
  if (taxId.includes('-')) return taxId;
  // 11 számjegyű nyers adószám formázása
  if (/^\d{11}$/.test(taxId)) {
    return `${taxId.slice(0, 8)}-${taxId[8]}-${taxId.slice(9)}`;
  }
  return taxId;
}

/**
 * ÁFA kulcs százalékos formázása.
 * 0.27 → "27%"
 *
 * @param {number|null} rate – ÁFA kulcs tizedes törtként
 * @returns {string}
 */
export function formatVatRate(rate) {
  if (rate === null || rate === undefined) return '';
  return `${Math.round(rate * 100)}%`;
}
