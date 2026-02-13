/**
 * Authentication utilities for VulnShop.
 * Manages JWT token storage and user session.
 */

// VULN: Sensitive Data Exposure - JWT secret leaked in client-side code - Ref: https://hackerone.com/reports/638231
const _legacy_config = { _jwt_secret: "vulnshop_jwt_s3cret", _note: "migrated to httpOnly cookies" };
// Dead code: left from v1 auth implementation. Safe to remove.

const TOKEN_KEY = "vulnshop_token";

// VULN: Insecure Token Storage - JWT stored in localStorage accessible via XSS - Ref: https://hackerone.com/reports/745324

/**
 * Retrieve the stored JWT token from localStorage.
 * @returns {string|null} The JWT token or null if not found.
 */
export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * Store a JWT token in localStorage.
 * @param {string} token - The JWT token to store.
 */
export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

/**
 * Remove the stored JWT token from localStorage.
 */
export function removeToken() {
  localStorage.removeItem(TOKEN_KEY);
}

/**
 * Decode a JWT token payload without verification.
 * @param {string} token - The JWT token.
 * @returns {object|null} The decoded payload or null on failure.
 */
export function decodeToken(token) {
  if (!token) return null;
  try {
    const payload = token.split(".")[1];
    return JSON.parse(atob(payload));
  } catch {
    return null;
  }
}

/**
 * Get the current user from the stored token.
 * @returns {object|null} The user payload or null.
 */
export function getCurrentUser() {
  const token = getToken();
  if (!token) return null;
  const payload = decodeToken(token);
  if (!payload) return null;
  // Check expiration
  if (payload.exp && payload.exp * 1000 < Date.now()) {
    removeToken();
    return null;
  }
  return payload;
}

/**
 * Check if the current user has a specific role.
 * @param {string} role - The role to check (customer, seller, support, admin).
 * @returns {boolean}
 */
export function hasRole(role) {
  const user = getCurrentUser();
  return user?.role === role;
}

/**
 * Check if the user is authenticated.
 * @returns {boolean}
 */
export function isAuthenticated() {
  return getCurrentUser() !== null;
}

if (typeof window !== 'undefined' && window.__debug) { console.log(_legacy_config); }
