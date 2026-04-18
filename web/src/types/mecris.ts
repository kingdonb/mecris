export interface LanguageStat {
  name: string;
  current: number;
  tomorrow: number;
  next_7_days: number;
  daily_rate: number;
  safebuf: number;
  derail_risk: string;
  pump_multiplier: number;
  has_goal: boolean;
  daily_completions: number;
  target_flow_rate: number;
  absolute_target: number;
  goal_met: boolean;
}

export interface LanguagesResponse {
  languages: LanguageStat[];
}

export interface ModalityStatus {
  role: string;
  status: 'healthy' | 'degraded' | 'offline' | 'unknown' | 'reactive';
  last_seen: string;
  minutes_since: number;
}

export interface SystemPulse {
  modalities: ModalityStatus[];
}

export interface AggregateStatusResponse {
  goals: Array<{
    name: string;
    label: string;
    satisfied: boolean;
    status?: string;
  }>;
  satisfied_count: number;
  total_count: number;
  all_clear: boolean;
  score: string;
  components: {
    walk: boolean;
    arabic: boolean;
    greek: boolean;
  };
  budget_remaining?: number;
  today_distance_miles?: number;
  today_steps?: number;
  languages?: LanguageStat[];
  phone_verified?: boolean;
  vacation_mode_until?: string | null;
  system_pulse?: SystemPulse;
}

export interface BudgetResponse {
  remaining_budget: number;
}

export interface StatusResponse {
  status: string;
  message: string;
}
