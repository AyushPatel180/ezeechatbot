"""URL ingestion using httpx and BeautifulSoup."""
from typing import List

import httpx
from bs4 import BeautifulSoup
from llama_index.core.schema import Document


class URLReader:
    """Fetch and extract text from URLs."""
    
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _extract_readable_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup(["script", "style", "noscript"]):
            script.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        return "\n".join(chunk for chunk in chunks if chunk)

    async def _fetch_html(self, client: httpx.AsyncClient, url: str) -> str:
        response = await client.get(url, headers=self._headers)
        response.raise_for_status()
        return response.text

    async def _fetch_via_jina_reader(self, client: httpx.AsyncClient, url: str) -> str:
        mirror_url = f"https://r.jina.ai/http://{url.removeprefix('https://').removeprefix('http://')}"
        response = await client.get(mirror_url, headers=self._headers)
        response.raise_for_status()
        return response.text
    
    async def load(self, url: str, bot_id: str) -> List[Document]:
        """
        Fetch URL content and extract readable text.
        
        Args:
            url: URL to fetch
            bot_id: Bot identifier for metadata
            
        Returns:
            List of LlamaIndex Documents
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, http2=False) as client:
                last_error = None
                text = ""

                try:
                    html = await self._fetch_html(client, url)
                    text = self._extract_readable_text(html)
                except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                    last_error = exc

                if not text or len(text.strip()) < 100:
                    try:
                        text = await self._fetch_via_jina_reader(client, url)
                    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                        if last_error is not None:
                            raise last_error
                        raise exc

                if not text or len(text.strip()) < 100:
                    raise ValueError("No substantial content found at URL")
                
                # Create document
                doc = Document(
                    text=text,
                    metadata={
                        "bot_id": bot_id,
                        "source_url": url,
                        "source_type": "website",
                    }
                )
                doc.excluded_embed_metadata_keys = ["bot_id"]
                
                return [doc]
                
        except httpx.HTTPStatusError as e:
            raise ValueError(f"HTTP error fetching URL: {e.response.status_code}")
        except httpx.RequestError as e:
            raise ValueError(
                "Request error fetching URL. If this is running inside Docker, "
                "the container may not be able to reach that website directly."
            )
        except Exception as e:
            raise ValueError(f"Failed to parse URL content: {str(e)}")


# Singleton instance
url_reader = URLReader()
