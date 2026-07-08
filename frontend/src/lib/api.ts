const BASE_URL = import.meta.env.VITE_API_URL || "/api/v1";
const API_KEY_HEADER = import.meta.env.VITE_API_KEY_HEADER || "X-API-Key";
const API_KEY = import.meta.env.VITE_API_KEY || "";

function withApiKeyHeaders(headers?: HeadersInit): Headers {
  const merged = new Headers(headers);
  if (API_KEY) {
    merged.set(API_KEY_HEADER, API_KEY);
  }
  return merged;
}

class ApiClient {
  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const headers = withApiKeyHeaders(options?.headers);
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    const response = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(error.detail || `API Error: ${response.status}`);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  get<T>(path: string) {
    return this.request<T>(path, { method: "GET" });
  }

  /** Fetch a plain-text (or markdown) response as a string. */
  async getText(path: string): Promise<string> {
    const response = await fetch(`${BASE_URL}${path}`, {
      method: "GET",
      headers: withApiKeyHeaders(),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(error.detail || `API Error: ${response.status}`);
    }
    return response.text();
  }

  post<T>(path: string, data?: unknown) {
    return this.request<T>(path, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  put<T>(path: string, data?: unknown) {
    return this.request<T>(path, {
      method: "PUT",
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  patch<T>(path: string, data: unknown) {
    return this.request<T>(path, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  delete(path: string) {
    return this.request(path, { method: "DELETE" });
  }

  async downloadFile(path: string, filename: string): Promise<void> {
    const response = await fetch(`${BASE_URL}${path}`, {
      headers: withApiKeyHeaders(),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Download failed" }));
      throw new Error(error.detail || `Download Error: ${response.status}`);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async uploadFile<T>(
    path: string,
    file: File,
    fields?: Record<string, string | number | boolean | null | undefined>
  ): Promise<T> {
    const formData = new FormData();
    formData.append("file", file);
    Object.entries(fields ?? {}).forEach(([key, value]) => {
      if (value === null || value === undefined) return;
      formData.append(key, String(value));
    });

    const response = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      body: formData,
      headers: withApiKeyHeaders(),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Upload failed" }));
      throw new Error(error.detail);
    }

    return response.json();
  }
}

export const api = new ApiClient();
export { API_KEY_HEADER, API_KEY, withApiKeyHeaders };

export function applyCandidateToJob(jobId: number, candidateId: number) {
  return api.post<{
    job_id: number;
    candidate_id: number;
    status: "applied" | "withdrawn";
    application_id: number;
    created: boolean;
  }>(`/jobs/${jobId}/apply/${candidateId}`, {});
}
