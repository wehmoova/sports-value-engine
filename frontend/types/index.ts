export type Recommendation = {
  id: string;
  event_id: string;
  sport: string;
  sport_name: string;
  competition: string;
  event: string;
  home_name: string;
  away_name: string;
  start_time: string;
  market: string;
  selection: string;
  bookmaker: string | null;
  best_odds: number;
  average_odds: number;
  median_odds: number;
  opening_odds: number | null;
  model_probability: number;
  market_probability: number;
  fair_odds: number;
  edge: number;
  expected_value: number;
  confidence_score: number;
  data_quality_score: number;
  status: "VALUE" | "NO_BET" | "WATCHLIST";
  reason_code: string;
  desired_entry_odds: number | null;
  odds_timestamp: string;
  is_demo: boolean;
  model_version: string | null;
  feature_version: string | null;
  probability_low: number | null;
  probability_high: number | null;
  model_components: Record<string, number>;
  positive_factors: string[];
  risks: string[];
};

export type EventSummary = {
  id: string;
  sport: string;
  sport_name: string;
  competition: string;
  name: string;
  home_name: string;
  away_name: string;
  start_time: string;
  status: string;
  surface: string | null;
  round: string | null;
  is_demo: boolean;
  recommendation: null | {
    status: string;
    best_odds: number;
    edge: number;
    confidence_score: number;
  };
};

export type Combination = {
  id: string;
  category: string;
  legs: Recommendation[];
  combined_odds: number;
  combined_probability: number;
  combined_ev: number;
  confidence_score: number;
  correlation_warning: string | null;
  independence_assumed: boolean;
  is_demo: boolean;
};

export type Dashboard = {
  provider_configured: boolean;
  generated_at: string;
  is_demo: boolean;
  last_refresh: string | null;
  metrics: {
    events_analysed: number;
    football_events: number;
    tennis_events: number;
    value_opportunities: number;
    strong_picks: number;
    average_edge: number;
    average_ev: number;
  };
  top_picks: Recommendation[];
  football_opportunities: Recommendation[];
  tennis_opportunities: Recommendation[];
  combinations: Combination[];
  no_bets: Recommendation[];
  analysis_run: null | {
    id: string;
    status: string;
    events_processed: number;
    log_summary: string | null;
  };
};

export type EventDetail = {
  data_sources: { event: string; fetched_at: string | null };
  statistics_sources: Array<{ provider: string; fetched_at: string | null; side: string; sample_size: number }>;
  id: string;
  sport: string;
  competition: string;
  name: string;
  home_name: string;
  away_name: string;
  start_time: string;
  status: string;
  surface: string | null;
  round: string | null;
  best_of: number | null;
  is_demo: boolean;
  source_timestamp: string;
  recommendations: Recommendation[];
  odds: Array<{
    provider: string;
    validation_status: string;
    freshness_status: string;
    bookmaker: string;
    market: string;
    selection: string;
    decimal_odds: number;
    point: number | null;
    observed_at: string;
    is_outlier: boolean;
  }>;
};
