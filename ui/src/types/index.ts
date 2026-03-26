export interface User {
  id: number;
  email: string;
  name: string;
  role: 'user' | 'admin';
  avatar_url?: string;
  start_date?: string;
  timezone: string;
  current_streak: number;
  total_completed: number;
}

export interface Day {
  id: number;
  day_number: number;
  date: string;
  workout1_done: boolean;
  workout2_done: boolean;
  diet_done: boolean;
  water_done: boolean;
  reading_done: boolean;
  photo_done: boolean;
  all_done: boolean;
  steps?: number;
  water_oz?: number;
  reading_minutes?: number;
  calories?: number;
  protein_g?: number;
  carbs_g?: number;
  fat_g?: number;
  fiber_g?: number;
  photo_url?: string;
  raw_notes?: string;
}

export interface Workout {
  id: number;
  date: string;
  workout_number: 1 | 2;
  workout_type?: string;
  duration_minutes?: number;
  location?: string;
  is_outdoor: boolean;
  notes?: string;
}

export interface Meal {
  id: number;
  date: string;
  meal_type: 'breakfast' | 'lunch' | 'dinner' | 'snack' | 'pre-workout' | 'post-workout';
  description?: string;
  calories?: number;
  protein_g?: number;
  carbs_g?: number;
  fat_g?: number;
  fiber_g?: number;
  sugar_g?: number;
  food_items?: FoodItem[];
}

export interface FoodItem {
  name: string;
  quantity?: string;
  calories?: number;
  protein_g?: number;
  carbs_g?: number;
  fat_g?: number;
}

export interface NutritionSummary {
  date: string;
  total_calories: number;
  total_protein_g: number;
  total_carbs_g: number;
  total_fat_g: number;
  total_fiber_g: number;
  meal_count: number;
}
