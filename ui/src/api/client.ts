import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';

export const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API endpoints
export const authApi = {
  login: () => `${API_BASE_URL}/auth/login`,
  logout: () => api.get('/logout'),
  me: () => api.get('/api/users/me'),
};

export const daysApi = {
  list: () => api.get('/api/days'),
  get: (dayNumber: number) => api.get(`/api/days/${dayNumber}`),
};

export const workoutsApi = {
  list: () => api.get('/api/workouts'),
  volume: (days = 30) => api.get(`/api/workouts/volume?days=${days}`),
};

export const mealsApi = {
  list: () => api.get('/api/meals'),
  today: () => api.get('/api/meals/today'),
  trends: (days = 30) => api.get(`/api/meals/trends?days=${days}`),
};

export const usersApi = {
  list: () => api.get('/api/users'),
  get: (id: number) => api.get(`/api/users/${id}`),
  update: (id: number, data: any) => api.patch(`/api/users/${id}`, data),
};

export const pendingApi = {
  list: () => api.get('/api/pending'),
  approve: (id: number) => api.post(`/api/pending/${id}/approve`),
  reject: (id: number) => api.post(`/api/pending/${id}/reject`),
};
