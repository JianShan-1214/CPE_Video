"""Fetch UVa problem PDFs from onlinejudge.org."""

import anyio
import httpx

MAX_PDF_BYTES = 5 * 1024 * 1024
# Overall wall-clock cap for the whole download; httpx's timeout is per read/connect only.
FETCH_DEADLINE_SECONDS = 30


class ProblemFetchError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def uva_pdf_url(problem_id: int) -> str:
    return f"https://onlinejudge.org/external/{problem_id // 100}/{problem_id}.pdf"


async def fetch_uva_pdf(problem_id: int, transport: httpx.AsyncBaseTransport | None = None) -> bytes:
    """Download the problem PDF. ``transport`` lets tests mock the network."""
    if isinstance(problem_id, bool) or not isinstance(problem_id, int) or not 100 <= problem_id <= 99999:
        raise ValueError(f"UVa 題號必須是 100–99999 的整數：{problem_id!r}")

    try:
        with anyio.fail_after(FETCH_DEADLINE_SECONDS):
            # Redirects are never followed: a 3xx could point at any host/scheme (SSRF).
            async with httpx.AsyncClient(timeout=20, follow_redirects=False, transport=transport) as client:
                async with client.stream("GET", uva_pdf_url(problem_id)) as response:
                    if response.status_code == 404:
                        raise ProblemFetchError(f"找不到 UVa {problem_id}", 404)
                    if 300 <= response.status_code < 400:
                        raise ProblemFetchError(
                            f"下載 UVa {problem_id} 失敗：伺服器回傳重新導向（HTTP {response.status_code}），已拒絕", 502
                        )
                    if response.status_code != 200:
                        raise ProblemFetchError(f"下載 UVa {problem_id} 失敗（HTTP {response.status_code}）", 502)
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_PDF_BYTES:
                            raise ProblemFetchError(f"UVa {problem_id} 的 PDF 超過 5 MB，已拒絕", 502)
    except TimeoutError as exc:
        raise ProblemFetchError(f"下載 UVa {problem_id} 逾時", 502) from exc
    except httpx.HTTPError as exc:
        raise ProblemFetchError(f"下載 UVa {problem_id} 失敗：{exc}", 502) from exc

    if not data.startswith(b"%PDF"):
        raise ProblemFetchError(f"UVa {problem_id} 回傳的不是 PDF 檔", 502)
    return bytes(data)
