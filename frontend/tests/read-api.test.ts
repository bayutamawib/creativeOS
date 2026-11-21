import { afterEach, expect, test, vi } from "vitest";
import { readApi } from "../lib/read-api";
import { mutate } from "../lib/browser-api";

const url = "https://example.invalid/read";
const getText = (response: Response) => response.text();

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("retries an interrupted GET once within its original deadline", async () => {
  const fetch = vi
    .fn()
    .mockRejectedValueOnce(new TypeError("Socket closed"))
    .mockResolvedValueOnce(new Response("ok"));
  vi.stubGlobal("fetch", fetch);
  expect(await readApi(url, "synthetic", getText)).toBe("ok");
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls[1][1].method).toBe("GET");
  expect(fetch.mock.calls[1][1].signal).toBe(fetch.mock.calls[0][1].signal);
});

test("preserves access denials and bounds persistent network failures", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(new Response(null, { status: 403 }))
    .mockRejectedValue(new TypeError("Unavailable"));
  vi.stubGlobal("fetch", fetch);
  expect(await readApi(url, "synthetic", async (res) => res.status)).toBe(403);
  expect(fetch).toHaveBeenCalledTimes(1);
  await expect(readApi(url, "synthetic", getText)).rejects.toThrow(
    "Unavailable",
  );
  expect(fetch).toHaveBeenCalledTimes(3);
});

test("recovers when the GET response body is interrupted", async () => {
  const interrupted = new ReadableStream({
    start(controller) {
      controller.error(new TypeError("Response interrupted"));
    },
  });
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(new Response(interrupted))
    .mockResolvedValueOnce(Response.json({ data: "recovered" }));
  vi.stubGlobal("fetch", fetch);
  expect(await readApi(url, "synthetic", (res) => res.json())).toEqual({
    data: "recovered",
  });
  expect(fetch).toHaveBeenCalledTimes(2);
});

test("does not retry after the shared deadline has expired", async () => {
  const signal = AbortSignal.abort();
  const timeout = vi.spyOn(AbortSignal, "timeout").mockReturnValue(signal);
  const fetch = vi.fn().mockRejectedValue(new TypeError("Stopped"));
  vi.stubGlobal("fetch", fetch);
  await expect(readApi(url, "synthetic", getText)).rejects.toThrow("Stopped");
  expect(timeout).toHaveBeenCalledWith(8000);
  expect(fetch).toHaveBeenCalledTimes(1);
});

test("sends a state-changing browser request only once after a transport failure", async () => {
  const fetch = vi
    .fn()
    .mockRejectedValue(new TypeError("Response interrupted"));
  vi.stubGlobal("fetch", fetch);
  vi.stubGlobal("document", { cookie: "" });
  await expect(mutate("/leads", "POST", {})).rejects.toThrow(
    "Response interrupted",
  );
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][1].method).toBe("POST");
});
