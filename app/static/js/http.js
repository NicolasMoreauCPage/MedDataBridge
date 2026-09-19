/* Client HTTP commun pour les interactions frontend MedData Bridge. */
(function (global) {
  "use strict";

  const DEFAULT_TIMEOUT_MS = 15_000;

  class HttpError extends Error {
    constructor(message, { status = 0, data = null, response = null } = {}) {
      super(message);
      this.name = "HttpError";
      this.status = status;
      this.data = data;
      this.response = response;
    }
  }

  async function responseData(response, responseType = "auto") {
    if (response.status === 204) return null;
    if (responseType === "blob") return response.blob();
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) return response.json();
    return response.text();
  }

  async function request(url, options = {}) {
    const {
      timeout = DEFAULT_TIMEOUT_MS,
      signal,
      headers = {},
      responseType = "auto",
      ...fetchOptions
    } = options;
    const controller = new AbortController();
    const timer = global.setTimeout(
      () => controller.abort(new DOMException("Délai d'attente dépassé", "TimeoutError")),
      timeout,
    );
    const abortFromCaller = () => controller.abort(signal.reason);
    if (signal) {
      if (signal.aborted) abortFromCaller();
      else signal.addEventListener("abort", abortFromCaller, { once: true });
    }

    try {
      const response = await global.fetch(url, {
        ...fetchOptions,
        headers: { Accept: "application/json, text/plain;q=0.9, */*;q=0.8", ...headers },
        signal: controller.signal,
      });
      const data = await responseData(response, responseType);
      if (!response.ok) {
        const message =
          (data && typeof data === "object" && (
            data.detail || data.message || data.error?.message
          )) ||
          `La requête a échoué (${response.status}).`;
        throw new HttpError(String(message), { status: response.status, data, response });
      }
      return { response, data };
    } catch (error) {
      if (error instanceof HttpError) throw error;
      if (controller.signal.aborted && !signal?.aborted) {
        throw new HttpError("La requête a expiré. Réessaie dans un instant.");
      }
      throw error;
    } finally {
      global.clearTimeout(timer);
      signal?.removeEventListener("abort", abortFromCaller);
    }
  }

  global.medbridgeHttp = {
    HttpError,
    request,
    get: (url, options) => request(url, { ...options, method: "GET" }),
    post: (url, body, options = {}) =>
      request(url, {
        ...options,
        method: "POST",
        headers: { "Content-Type": "application/json", ...options.headers },
        body: JSON.stringify(body),
      }),
  };
})(window);
