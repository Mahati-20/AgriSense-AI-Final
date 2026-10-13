export type DashboardDecision = {
  recommendation: string;
  confidence: number;
  reasons: string[];
  score: number;
  profit_now?: number | null;
  profit_future?: number | null;
  status?: string;
  missing_inputs?: string[];
  score_breakdown?: Record<string, Record<string, number>>;
  data_date?: string | null;
};

export type Farmer = {
  id: number;
  name: string;
  location: string;
  preferred_language: string;
  farm_size: number;
  primary_crop: string;
  data_source?: string;
};

export type Crop = {
  id: number;
  name: string;
  variety: string;
  planting_date: string;
  expected_harvest_date: string;
  current_stage: string;
  quantity: number;
  data_source?: string;
};

export type Market = {
  crop: string;
  market: string | null;
  district?: string | null;
  state?: string;
  variety?: string | null;
  grade?: string | null;
  price: number | null;
  unit: string | null;
  source_price?: number | string | null;
  min_price?: number | string | null;
  max_price?: number | string | null;
  price_compatible?: boolean;
  date: string | null;
  demand_level: number | null;
  trend: number | null;
  data_source?: string;
  price_label?: string;
  original_unit?: string;
  original_price?: number;
  source_price_unit?: string | null;
};

export type MandiRecord = {
  id?: string | number;
  state?: string | null;
  district?: string | null;
  market?: string | null;
  commodity?: string | null;
  variety?: string | null;
  grade?: string | null;
  arrival_date?: string | null;
  min_price?: number | string | null;
  max_price?: number | string | null;
  modal_price?: number | string | null;
  fetched_at?: string | null;
  source_price_unit?: string | null;
  converted_price_unit?: string | null;
  converted_min_price?: number | null;
  converted_max_price?: number | null;
  converted_modal_price?: number | null;
  price_compatible?: boolean;
};

export type MandiPricesResponse = {
  success: boolean;
  data: MandiRecord[];
  meta: Record<string, unknown>;
  data_source: string;
  retrieved_at: string;
  source_fetched_at?: string | null;
  cached: boolean;
  cache_age_seconds: number;
  freshness: 'current' | 'stale' | 'unknown';
  stale: boolean | null;
  latest_arrival_date?: string | null;
  age_days?: number | null;
  freshness_message: string;
  unit_status: string;
};

export type MandiOptions = {
  states: string[];
  commodities: string[];
  selected_state: string;
  data_source: string;
};

export type Weather = {
  location: string;
  date: string;
  temperature: number | null;
  temperature_min?: number | null;
  rainfall_mm?: number | null;
  current_temperature?: number | null;
  rainfall_probability: number | null;
  humidity: number | null;
  current_humidity?: number | null;
  wind_kmh?: number | null;
  weather_condition: string;
  data_source?: string;
  data_status?: string;
  observation_time?: string | null;
  forecast_time?: string;
};

export type StorageItem = {
  id: number;
  name: string;
  location: string;
  distance: number;
  capacity: number;
  available_capacity: number;
  storage_type: string;
  price_per_day: number;
  rating: number;
  data_source?: string;
  directions_url?: string | null;
};

export type CalendarTask = {
  id: number;
  title: string;
  crop: string;
  date: string;
  priority: string;
  completed: boolean;
  data_source?: string;
};

export type NotificationItem = {
  id: number;
  title: string;
  message: string;
  severity: string;
  timestamp: string;
  read: boolean;
  data_source?: string;
};

export type NewsItem = {
  id: number | string;
  headline?: string | null;
  date?: string | null;
  summary?: string | null;
  data_source?: string;
  source?: string | null;
  url?: string | null;
  image?: string | null;
};

export type DecisionPayload = {
  crop_readiness_score?: number | null;
  current_price?: number | null;
  price_trend?: number | null;
  demand_level?: number | null;
  rainfall_risk?: number | null;
  storage_cost?: number | null;
  storage_availability?: number | null;
  quantity?: number | null;
  transport_cost?: number | null;
  production_cost?: number | null;
  other_expenses?: number | null;
  expected_future_price?: number | null;
  storage_duration_days?: number | null;
  input_sources?: Record<string, string>;
  crop: string;
  location: string;
};

export type ProfitData = {
  crop: string;
  quantity: number;
  current_price: number;
  expected_selling_price: number;
  revenue: number;
  expenses: number;
  net_profit: number;
  profit_per_kg: number;
  profit_percentage: number;
  sell_now_profit: number;
  store_profit: number;
  storage_total: number;
};

export type DashboardData = {
  farmer: Farmer;
  crop: Crop;
  farmer_summary?: { crop_count: number; open_task_count: number; data_source: string } | null;
  weather: Weather[];
  market: Market[];
  notifications: NotificationItem[];
  tasks: CalendarTask[];
  decision: DashboardDecision;
  decision_data_source?: string;
  market_error?: string | null;
};
