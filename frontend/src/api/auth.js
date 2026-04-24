import axios from 'axios';

// Base API URL - for local development
const API_BASE_URL = 'http://localhost:8001/payroll';

const api = axios.create({
  baseURL: API_BASE_URL,
});

// Interceptor to add Auth Token to every request
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Interceptor to handle 401 Unauthorized
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('role');
      // Only redirect if not already on login page
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  /**
   * Login with OAuth2 Password Flow
   */
  login: async (username, password) => {
    // FastAPI OAuth2PasswordRequestForm expects form-data
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);

    const response = await api.post('/auth/login', params, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  },

  /**
   * Get current user info (debug helper)
   */
  getMe: async () => {
    const response = await api.get('/auth/me');
    return response.data;
  },
};

export default api;
