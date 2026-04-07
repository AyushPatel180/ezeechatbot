"""URL ingestion using httpx and BeautifulSoup."""
import httpx
from bs4 import BeautifulSoup
from typing import List
from llama_index.core.schema import Document


class URLReader:
    """Fetch and extract text from URLs."""
    
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
    
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
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Parse HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Get text content
                text = soup.get_text(separator='\n', strip=True)
                
                # Clean up excessive whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = '\n'.join(chunk for chunk in chunks if chunk)
                
                if not text or len(text.strip()) < 100:
                    raise ValueError("No substantial content found at URL")
                
                # Create document
                doc = Document(
                    text=text,
                    metadata={
                        "bot_id": bot_id,
                        "source_url": url,
                        "source_type": "url",
                    }
                )
                doc.excluded_embed_metadata_keys = ["bot_id"]
                
                return [doc]
                
        except httpx.HTTPStatusError as e:
            raise ValueError(f"HTTP error fetching URL: {e.response.status_code}")
        except httpx.RequestError as e:
            raise ValueError(f"Request error fetching URL: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to parse URL content: {str(e)}")


# Singleton instance
url_reader = URLReader()
