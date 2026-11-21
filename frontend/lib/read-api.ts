// A pooled connection can close during a server-rendered GET.
export async function readApi<T>(
  url: string,
  cookie: string,
  decode: (response: Response) => Promise<T>,
): Promise<T> {
  const signal = AbortSignal.timeout(8000);
  async function read() {
    const response = await fetch(url, {
      method: "GET",
      headers: { cookie },
      cache: "no-store",
      signal,
    });
    return decode(response);
  }
  try {
    return await read();
  } catch (error) {
    if (signal.aborted || !(error instanceof TypeError)) throw error;
    return read();
  }
}
