/**
 * Extracts a displayable error message from a FastAPI error response.
 *
 * Handles three formats:
 * - String detail: "Invalid credentials" → returned as-is
 * - Pydantic validation array: [{msg: "...", loc: [...]}] → joined messages
 * - Unknown shape → returns fallback
 *
 * @param {import("axios").AxiosError} err - Axios error from a failed request.
 * @param {string} fallback - Default message when detail is missing.
 * @returns {string} Human-readable error message.
 */
export function extractApiError(err, fallback = "Something went wrong") {
  const detail = err.response?.data?.detail;

  if (!detail) return fallback;
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === "string" ? item : item.msg || JSON.stringify(item)))
      .join(". ");
  }

  return fallback;
}
