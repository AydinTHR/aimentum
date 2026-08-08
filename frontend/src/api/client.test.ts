import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, tokenStore } from "./client";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api client", () => {
  beforeEach(() => {
    tokenStore.set("test-token");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    tokenStore.clear();
  });

  it("sends the stored token as a bearer header", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(200, { applications_floor: 3 }));

    await api.settings();

    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer test-token");
  });

  it("clears the token on 401 so the gate takes over", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(401, { detail: "Not authenticated" }),
    );

    await expect(api.today()).rejects.toBeInstanceOf(ApiError);
    expect(tokenStore.get()).toBeNull();
  });

  it("surfaces the server's detail message on other errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(413, { detail: "audio is too long" }),
    );

    await expect(api.today()).rejects.toThrow("audio is too long");
    // A 413 is not an auth problem, so the token survives.
    expect(tokenStore.get()).toBe("test-token");
  });

  it("reports a network failure as a readable message", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(api.today()).rejects.toThrow(/Could not reach the server/);
  });

  it("leaves multipart uploads without a JSON content type", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(200, { transcript: "hello" }));

    await api.transcribe(new Blob(["audio"]), "checkin.webm");

    const [, init] = fetchMock.mock.calls[0];
    // The browser has to set the multipart boundary itself.
    expect(new Headers(init?.headers).get("Content-Type")).toBeNull();
  });

  it("notifies subscribers when the token changes", () => {
    const listener = vi.fn();
    const unsubscribe = tokenStore.subscribe(listener);

    tokenStore.set("another");
    tokenStore.clear();
    unsubscribe();
    tokenStore.set("ignored");

    expect(listener).toHaveBeenCalledTimes(2);
  });
});
