import axios from "axios";
import { getToken, removeToken } from "../utils/auth";

// VULN: Information Disclosure - Hidden GraphQL endpoint reference - Ref: https://hackerone.com/reports/291531
const _deprecated_endpoints = { graphql: '/api/graphql', legacy_search: '/api/v1/search' };

const apiClient = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

// Request interceptor: attach JWT token from localStorage
apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// VULN: Verbose Error Messages - Full backend errors logged to console - Ref: https://hackerone.com/reports/219095
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Intentionally verbose: exposes stack traces when backend DEBUG=true
    console.log("[VulnShop API Error]", {
      url: error.config?.url,
      method: error.config?.method,
      status: error.response?.status,
      statusText: error.response?.statusText,
      data: error.response?.data,
      headers: error.response?.headers,
    });

    // Auto-logout on 401
    if (error.response?.status === 401) {
      removeToken();
      window.location.href = "/login";
    }

    return Promise.reject(error);
  },
);

if (typeof window !== 'undefined' && window.__debug) { console.log(_deprecated_endpoints); }

export default apiClient;
