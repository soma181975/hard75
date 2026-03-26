import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { daysApi, mealsApi } from '../api/client';
import type { Day, NutritionSummary, Meal } from '../types';
import { Layout } from '../components/Layout';

export function Dashboard() {
  const { user } = useAuth();
  const [days, setDays] = useState<Day[]>([]);
  const [nutrition, setNutrition] = useState<NutritionSummary | null>(null);
  const [meals, setMeals] = useState<Meal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [daysRes, nutritionRes, mealsRes] = await Promise.all([
          daysApi.list(),
          mealsApi.today(),
          mealsApi.list(),
        ]);
        setDays(daysRes.data);
        setNutrition(nutritionRes.data);
        setMeals(mealsRes.data);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-500">Loading...</div>
        </div>
      </Layout>
    );
  }

  const totalCompleted = days.filter((d) => d.all_done).length;

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">Your Progress</h1>
          <div className="text-right">
            <p className="text-sm text-gray-500">Current Streak</p>
            <p className="text-2xl font-bold text-blue-600">
              {user?.current_streak || 0} days
            </p>
          </div>
        </div>

        {/* Progress Overview */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">75-Day Challenge</h2>
            <span className="text-sm text-gray-500">
              {totalCompleted}/75 days completed
            </span>
          </div>

          {/* Progress bar */}
          <div className="w-full bg-gray-200 rounded-full h-4 mb-4">
            <div
              className="bg-blue-600 h-4 rounded-full transition-all duration-500"
              style={{ width: `${(totalCompleted / 75) * 100}%` }}
            />
          </div>

          {/* Day grid */}
          <div className="grid grid-cols-15 gap-1">
            {Array.from({ length: 75 }, (_, i) => i + 1).map((dayNum) => {
              const day = days.find((d) => d.day_number === dayNum);
              return (
                <div
                  key={dayNum}
                  className={`w-6 h-6 rounded flex items-center justify-center text-xs cursor-pointer ${
                    day?.all_done
                      ? 'bg-green-500 text-white'
                      : day
                      ? 'bg-yellow-400 text-gray-800'
                      : 'bg-gray-200 text-gray-500'
                  }`}
                  title={`Day ${dayNum}${day ? `: ${day.all_done ? 'Complete' : 'In progress'}` : ''}`}
                >
                  {dayNum}
                </div>
              );
            })}
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500">Current Streak</h3>
            <p className="text-3xl font-bold text-gray-900 mt-2">
              {user?.current_streak || 0}
            </p>
            <p className="text-sm text-gray-500 mt-1">consecutive days</p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500">Days Remaining</h3>
            <p className="text-3xl font-bold text-gray-900 mt-2">
              {75 - totalCompleted}
            </p>
            <p className="text-sm text-gray-500 mt-1">to complete the challenge</p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500">Completion Rate</h3>
            <p className="text-3xl font-bold text-gray-900 mt-2">
              {((totalCompleted / 75) * 100).toFixed(1)}%
            </p>
            <p className="text-sm text-gray-500 mt-1">of the challenge</p>
          </div>
        </div>

        {/* Today's Nutrition */}
        {nutrition && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Today's Nutrition
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="text-center p-4 bg-orange-50 rounded-lg">
                <p className="text-2xl font-bold text-orange-600">
                  {nutrition.total_calories}
                </p>
                <p className="text-xs text-gray-500 mt-1">Calories</p>
              </div>
              <div className="text-center p-4 bg-purple-50 rounded-lg">
                <p className="text-2xl font-bold text-purple-600">
                  {nutrition.total_protein_g}g
                </p>
                <p className="text-xs text-gray-500 mt-1">Protein</p>
              </div>
              <div className="text-center p-4 bg-blue-50 rounded-lg">
                <p className="text-2xl font-bold text-blue-600">
                  {nutrition.total_carbs_g}g
                </p>
                <p className="text-xs text-gray-500 mt-1">Carbs</p>
              </div>
              <div className="text-center p-4 bg-yellow-50 rounded-lg">
                <p className="text-2xl font-bold text-yellow-600">
                  {nutrition.total_fat_g}g
                </p>
                <p className="text-xs text-gray-500 mt-1">Fat</p>
              </div>
              <div className="text-center p-4 bg-green-50 rounded-lg">
                <p className="text-2xl font-bold text-green-600">
                  {nutrition.total_fiber_g}g
                </p>
                <p className="text-xs text-gray-500 mt-1">Fiber</p>
              </div>
            </div>
            <p className="text-sm text-gray-500 mt-4">
              {nutrition.meal_count} meal(s) logged today
            </p>
          </div>
        )}

        {/* Recent Meals */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Meals</h3>
          {meals.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {meals.slice(0, 6).map((meal) => (
                <MealCard key={meal.id} meal={meal} />
              ))}
            </div>
          ) : (
            <p className="text-gray-500">No meals logged yet.</p>
          )}
        </div>
      </div>
    </Layout>
  );
}

function MealCard({ meal }: { meal: Meal }) {
  const mealTypeColors: Record<string, string> = {
    breakfast: 'bg-yellow-100 text-yellow-700',
    lunch: 'bg-green-100 text-green-700',
    dinner: 'bg-blue-100 text-blue-700',
    snack: 'bg-purple-100 text-purple-700',
    'pre-workout': 'bg-orange-100 text-orange-700',
    'post-workout': 'bg-red-100 text-red-700',
  };

  return (
    <div className="border rounded-lg p-4 hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-2">
        <span className="text-sm font-medium text-gray-900">{meal.date}</span>
        <span
          className={`px-2 py-0.5 text-xs rounded-full ${
            mealTypeColors[meal.meal_type] || 'bg-gray-100 text-gray-700'
          }`}
        >
          {meal.meal_type.charAt(0).toUpperCase() + meal.meal_type.slice(1)}
        </span>
      </div>

      {meal.description && (
        <p className="text-sm text-gray-600 mb-2">{meal.description}</p>
      )}

      <div className="grid grid-cols-4 gap-2 text-center text-xs">
        {meal.calories && (
          <div>
            <p className="font-semibold text-gray-900">{meal.calories}</p>
            <p className="text-gray-500">cal</p>
          </div>
        )}
        {meal.protein_g && (
          <div>
            <p className="font-semibold text-purple-600">{meal.protein_g}g</p>
            <p className="text-gray-500">protein</p>
          </div>
        )}
        {meal.carbs_g && (
          <div>
            <p className="font-semibold text-blue-600">{meal.carbs_g}g</p>
            <p className="text-gray-500">carbs</p>
          </div>
        )}
        {meal.fat_g && (
          <div>
            <p className="font-semibold text-yellow-600">{meal.fat_g}g</p>
            <p className="text-gray-500">fat</p>
          </div>
        )}
      </div>
    </div>
  );
}
