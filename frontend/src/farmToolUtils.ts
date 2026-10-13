export const agriculturalUnits = {
  kg: { tonnes: 0.001 }, tonnes: { kg: 1000 },
  acres: { hectares: 0.40468564224 }, hectares: { acres: 2.47105381467 },
  'm²': { acres: 0.000247105381, hectares: 0.0001 },
  litres: { millilitres: 1000 }, 'price/kg': { 'price/quintal': 100 }, 'price/quintal': { 'price/kg': 0.01 },
} as const;

export function convertAgriculturalUnit(value: number, from: string, to: string): number | null {
  if (!Number.isFinite(value) || value < 0) return null;
  const multiplier = (agriculturalUnits as Record<string, Record<string, number>>)[from]?.[to];
  return multiplier === undefined ? null : value * multiplier;
}

export function escapeCsvCell(value: unknown): string {
  const text = String(value ?? '');
  const safeText = /^\s*[=+@-]/.test(text) ? `'${text}` : text;
  return `"${safeText.replaceAll('"', '""')}"`;
}

export function currentDateKey(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

export function isValidDateKey(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split('-').map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return parsed.getUTCFullYear() === year
    && parsed.getUTCMonth() === month - 1
    && parsed.getUTCDate() === day;
}

export function monthCalendarDays(monthKey: string): string[] {
  const [year, month] = monthKey.split('-').map(Number);
  if (!year || !month || month > 12) return [];
  const firstWeekday = new Date(year, month - 1, 1).getDay();
  const daysInMonth = new Date(year, month, 0).getDate();
  const count = Math.ceil((firstWeekday + daysInMonth) / 7) * 7;
  return Array.from({ length: count }, (_, index) => {
    const day = index - firstWeekday + 1;
    const value = new Date(year, month - 1, day);
    return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
  });
}
