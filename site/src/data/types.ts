/* Shapes of data/processed + core.json, mirroring what scripts/build_site_data.py
   emits. Kept hand-written rather than generated so the compiler enforces the
   honesty rules: every optional number is `number | null`, never `number`, so a
   missing value cannot be silently rendered as 0. */

export type Confidence = 'official' | 'index' | 'crowd'
export type ThemeName = 'compass' | 'editorial' | 'terminal' | 'warm'
export type Mode = 'light' | 'dark'
export type Band = 'new_grad' | 'mid' | 'senior'
export type Lens = 'gross' | 'net' | 'after'

export interface Climate {
  sunshine_hours_yr: number | null
  summer_avg_high_c: number | null
  winter_avg_low_c: number | null
  rainy_days_yr: number | null
}

export interface SalaryBands {
  new_grad: number | null
  mid: number | null
  senior: number | null
  confidence?: Confidence
  note?: string
}

export interface LevelsFyi {
  median_total_comp_usd: number | null
  p25_total_comp_usd?: number | null
  p75_total_comp_usd?: number | null
  currency_original?: string
  as_of?: string
  basis?: string
  confidence?: Confidence
  source?: string
  unavailable_reason?: string
}

/** Precomputed defaults. Every field is always present; null means "we could not
 *  compute this", and `missing_inputs` says which figures were absent. */
export interface Computed {
  gross_usd: number | null
  net_usd: number | null
  monthly_rent_usd: number | null
  monthly_living_usd: number | null
  savings_usd_year: number | null
  years_to_home: number | null
  m2_per_year: number | null
  missing_inputs: string[]
  never_note?: string
}

export interface City {
  id: string
  name: string
  country: string
  salary_usd_year: SalaryBands
  rent_1br_center_usd_month: number | null
  rent_1br_outside_usd_month: number | null
  col_single_no_rent_usd_month: number | null
  apt_price_center_usd_m2: number | null
  apt_price_outside_usd_m2: number | null
  climate: Climate
  tehran_travel?: { typical_hours: number | null; stops: number | null; note?: string }
  tech_scene_note?: string
  sources: string[]
  as_of: string
  salary_levels_fyi?: LevelsFyi
  computed: Record<Band, Computed>
  formulas: Record<string, string>
  net_pct: number | null
}

export interface VisaRoute {
  name: string
  type: string
  summary: string
  salary_threshold_usd: number | null
  threshold_note?: string
}

export interface Country {
  id: string
  name: string
  visa: {
    skilled_routes: VisaRoute[]
    study_pathway?: {
      masters_tuition_intl_usd_yr: number | null
      post_study_visa_months: number | null
      note?: string
    }
    processing_months_typical?: string
    iran_friction?: { level: 'low' | 'medium' | 'high'; notes: string; sources?: string[] }
  }
  pr_years_typical: number | null
  citizenship_years_typical: number | null
  dual_citizenship: { allowed: boolean | null; note?: string }
  tax: {
    summary?: string
    net_pct_single_mid_dev: number | null
    net_note?: string
    expat_scheme?: string | null
  }
  sources: string[]
  as_of: string
  indices: {
    whr_score: number | null
    whr_rank: number | null
    gpi_rank: number | null
    hdi: number | null
    ef_epi_score: number | null
    ef_epi_band?: string | null
    numbeo_qol_index: number | null
    numbeo_healthcare_index: number | null
    freedom_note?: string
  }
  job_market: { summary?: string; new_grad_reality?: string; english_work?: string }
  language: { official: string; english_work: string; pr_citizenship_language_req?: string }
  reality_paragraph: string
  flags?: unknown
  enriched: {
    foreign_born?: { count: number; year: number; share_pct: number; formula: string }
    iranian_born?: { count: number; year: number }
    top_origins?: { origin_m49: number; origin: string; value: number }[]
    ict_specialists?: { thousands: number; year: number; share_pct: number | null }
    total_employment?: { thousands: number; year: number }
    happiness?: { score: number | null; rank: number | null; of: number | null; year: number }
  }
}

export interface Metrics {
  meta: {
    fx_rates_usd_base: Record<string, number | string>
    confidence_tiers: Record<Confidence, string>
    staleness_rules_months: Record<string, number>
  }
  city_metrics: Record<string, { desc: string; direction?: string; primary?: string; confidence?: Confidence }>
  country_metrics: Record<string, { desc: string; direction?: string; primary?: string; confidence?: Confidence }>
  computed_metrics: Record<string, string>
}

export interface Core {
  as_of: string
  metrics: Metrics
  countries: Country[]
  cities: City[]
  home_reference_m2: number
  principles: Record<string, string>
}

export interface ProvenanceEntry {
  source_id: string
  name: string
  urls: string[]
  fetched_at: string
  license: string
  redistribution?: string
  transforms: string[]
  output: string | null
  status: string
  rows: number | null
  coverage: string | null
  notes: string | null
}

export interface Provenance {
  schema: string
  updated_at?: string
  entries: ProvenanceEntry[]
}

export interface HistoryManifestEntry {
  theme: string
  file: string
  kb: number
  kind?: string
  confidence?: Confidence
  institution?: string
  attribution_chip?: string
  status: string
  empty: boolean
}

export interface Series {
  year?: number
  period?: string
  month?: string
  date?: string
  value?: number
  index?: number
  is_projection?: boolean
}
