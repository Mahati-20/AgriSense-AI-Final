export function authenticatedDisplayName(name: string | null | undefined): string {
  return name?.trim() || 'Farmer';
}
