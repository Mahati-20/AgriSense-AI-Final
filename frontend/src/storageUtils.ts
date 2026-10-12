import type { StorageItem } from './types.ts';

export type StorageSort = 'distance' | 'price' | 'rating';
export type StorageListState = 'loading' | 'error' | 'empty' | 'results';

export function storageListState(loading: boolean, error: string, resultCount: number): StorageListState {
  if (loading) return 'loading';
  if (error) return 'error';
  return resultCount > 0 ? 'results' : 'empty';
}

export function filterAndSortStorage(
  items: StorageItem[],
  locationQuery: string,
  selectedType: string,
  sortBy: StorageSort,
): StorageItem[] {
  const query = locationQuery.trim().toLowerCase();
  return items
    .filter((item) => (selectedType === 'All' || item.storage_type === selectedType)
      && (!query || (item.location || '').toLowerCase().includes(query)))
    .slice()
    .sort((a, b) => {
      if (sortBy === 'distance') return a.distance - b.distance;
      if (sortBy === 'price') return a.price_per_day - b.price_per_day;
      return b.rating - a.rating;
    });
}
