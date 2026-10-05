import axios from "axios";
import { useAuthStore } from "../store/authStore";

const baseURL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

const axiosInstance = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json",
  },
});

axiosInstance.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().accessToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

axiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = useAuthStore.getState().refreshToken;
        if (!refreshToken) throw new Error("No refresh token");
        
        // Use standard axios to avoid interceptor loop
        const res = await axios.post(`${baseURL}/auth/refresh`, { refresh_token: refreshToken });
        
        const newAccessToken = res.data.access_token;
        const newRefreshToken = res.data.refresh_token || refreshToken;
        
        useAuthStore.getState().setTokens(newAccessToken, newRefreshToken);
        
        // Update the failed request with the new token
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return axiosInstance(originalRequest);
      } catch (refreshError) {
        useAuthStore.getState().logout();
        window.location.href = "/login";
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

export default axiosInstance;
