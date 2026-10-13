import type { CalendarTask, DashboardData, DecisionPayload, Market, MandiOptions, MandiPricesResponse, NewsItem, NotificationItem, ProfitData, StorageItem, Weather } from '../types';

// Match the backend's loopback IPv4 address. `localhost` can resolve to ::1
// while Uvicorn is bound only to 127.0.0.1 on some Windows setups.
const API_URL = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '');

async function fetchJson<T>(path: string, options?: RequestInit, onRequestStarted?: () => void): Promise<T> {
  if (!API_URL) throw new Error('The production API URL is missing. Set VITE_API_URL to the deployed backend origin and rebuild the frontend.');
  const token = sessionStorage.getItem('agrisense_session');
  const request = fetch(`${API_URL}${path}`, {
    ...options,
    headers: { ...(options?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(options?.headers || {}) },
  });
  onRequestStarted?.();
  let response: Response;
  try {
    response = await request;
  } catch (reason) {
    if (reason instanceof Error && reason.name === 'AbortError') throw reason;
    if (reason instanceof TypeError) throw new Error('Could not reach the AgriSense backend. Check that the backend is running, then retry.');
    throw reason;
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export type AuthResult = { access_token: string; expires_at: string; user: { id: number; name: string; email: string; email_verified: boolean; created_at: string } };
export const signup = (name: string, email: string, password: string) => fetchJson<AuthResult>('/api/auth/signup', { method: 'POST', body: JSON.stringify({ name, email, password }) });
export const login = (email: string, password: string) => fetchJson<AuthResult>('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
export const logout = () => fetchJson<{ status: string }>('/api/auth/logout', { method: 'POST' });
export const getAuthUser = () => fetchJson<AuthResult['user']>('/api/auth/me');
export const updateAuthProfile = (name: string) => fetchJson<AuthResult['user']>('/api/auth/profile', { method: 'PUT', body: JSON.stringify({ name }) });

export const getDashboard = () => fetchJson<DashboardData>('/api/dashboard');
export const getMarkets = () => fetchJson<Market[]>('/api/markets');
export const getMarketOptions = (state: string) => fetchJson<MandiOptions>(`/api/markets/options?${new URLSearchParams({ state })}`);
export const getMarketPrices = (state: string, commodity: string, refresh = false) => fetchJson<MandiPricesResponse>(`/api/markets/prices?${new URLSearchParams({ state, commodity, ...(refresh ? { refresh: 'true' } : {}) })}`);
export const getMarketTrend = (state = 'Karnataka', commodity = 'Tomato') => fetchJson<any>(`/api/markets/trend?${new URLSearchParams({ state, commodity })}`);
export const getWeather = () => fetchJson<Weather[]>('/api/weather');
export const getWeatherRisk = () => fetchJson<any>('/api/weather/risk');
export const getStorage = () => fetchJson<StorageItem[]>('/api/storage');
export const getStorageDetails = (id: number) => fetchJson<StorageItem>(`/api/storage/${id}`);

function plantImagesForm(files: File[], organ: string): FormData {
  const form = new FormData();
  files.forEach((file) => { form.append('images', file); form.append('organs', organ); });
  return form;
}

export async function analyzeCrop(files: File[], crop = '', organ = 'leaf', signal?: AbortSignal, onRequestStarted?: () => void): Promise<any> {
  const form = plantImagesForm(files, organ);
  form.append('crop', crop);
  return fetchJson('/api/crop/analyze', { method: 'POST', body: form, signal }, onRequestStarted);
}

export async function screenCropDisease(files: File[], organ = 'leaf', signal?: AbortSignal, onRequestStarted?: () => void): Promise<any> {
  const form = plantImagesForm(files, organ);
  return fetchJson('/api/crop/disease-screening', { method: 'POST', body: form, signal }, onRequestStarted);
}

export const calculateProfit = (payload: unknown) => fetchJson<ProfitData>('/api/profit/calculate', { method: 'POST', body: JSON.stringify(payload) });
export const getDecision = (payload: DecisionPayload) => fetchJson<any>('/api/decision/analyze', { method: 'POST', body: JSON.stringify(payload) });
export const askAssistant = (payload: { message: string; crop: string; location: string; language: string }) => fetchJson<any>('/api/assistant', { method: 'POST', body: JSON.stringify(payload) });
export const getAssistantStatus = () => fetchJson<{ available: boolean; status: string; label: string; data_source: string }>('/api/assistant/status');
export const getCalendar = () => fetchJson<CalendarTask[]>('/api/calendar');
export type NewsSearchFilters = { lang?: string; country?: string; sortBy?: 'publishedAt' | 'relevance' };
export const getNews = (q: string, filters: NewsSearchFilters = {}) => {
  const params = new URLSearchParams({ q, lang: filters.lang || 'en', sortBy: filters.sortBy || 'publishedAt' });
  if (filters.country) params.set('country', filters.country);
  return fetchJson<NewsItem[]>(`/api/news?${params.toString()}`);
};
export const getNotifications = () => fetchJson<NotificationItem[]>('/api/notifications');
export const markNotificationRead = (id: number) => fetchJson(`/api/notifications/${id}/read`, { method: 'PUT' });
export const addTask = (task: Omit<CalendarTask, 'id'>) => fetchJson<CalendarTask>('/api/calendar/tasks', { method: 'POST', body: JSON.stringify(task) });
export const updateTask = (task: CalendarTask) => fetchJson(`/api/calendar/tasks/${task.id}`, { method: 'PUT', body: JSON.stringify(task) });
export const deleteTask = (id: number) => fetchJson(`/api/calendar/tasks/${id}`, { method: 'DELETE' });
export type FarmToolKind = 'planner-crops' | 'planner-tasks' | 'crop-journal' | 'harvest' | 'profit';
export type FarmToolRecord = Record<string, any> & { id: number; kind: FarmToolKind; data_status: string };
export const getFarmToolRecords = (kind: FarmToolKind) => fetchJson<FarmToolRecord[]>(`/api/farm-tools/${kind}`);
export const createFarmToolRecord = (kind: FarmToolKind, data: Record<string, unknown>) => fetchJson<FarmToolRecord>(`/api/farm-tools/${kind}`, { method: 'POST', body: JSON.stringify({ data }) });
export const updateFarmToolRecord = (kind: FarmToolKind, id: number, data: Record<string, unknown>) => fetchJson<FarmToolRecord>(`/api/farm-tools/${kind}/${id}`, { method: 'PUT', body: JSON.stringify({ data }) });
export const deleteFarmToolRecord = (kind: FarmToolKind, id: number) => fetchJson<{ status: string }>(`/api/farm-tools/${kind}/${id}`, { method: 'DELETE' });
export type FarmToolReport = { farmer: AuthResult['user']; crop_profiles: FarmToolRecord[]; tasks: FarmToolRecord[]; inspections: FarmToolRecord[]; harvests: FarmToolRecord[]; profit_calculations: FarmToolRecord[]; data_quality: string[]; generated_at: string };
export const getFarmToolReport = () => fetchJson<FarmToolReport>('/api/farm-tools/report');
